"""RED-first contracts for the pure WO-0148 protection semantic center.

The suite uses only explicit immutable values and the genuine venue-recovery
reducer.  It imports the not-yet-implemented protection vocabulary lazily so
every example is collected and independently failure-capable before production
code exists.  No clock, database, broker, adapter, or runtime fixture is used.
"""

from __future__ import annotations

import ast
import builtins
from collections.abc import Callable
from copy import copy
from dataclasses import (
    MISSING,
    FrozenInstanceError,
    dataclass,
    fields,
    is_dataclass,
    make_dataclass,
    replace,
)
from decimal import Decimal
import dis
from enum import Enum
from fractions import Fraction
import importlib
import inspect
from pathlib import Path
import textwrap
from types import CodeType, FunctionType, ModuleType
import typing

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
    PositionIntegrity,
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
_PUBLIC_ENTRYPOINT_PAYLOAD_CALLS: list[str] = []


def _public_entrypoint_source_swap_payload(
    transition: object,
    mandate: object,
) -> None:
    del transition, mandate
    _PUBLIC_ENTRYPOINT_PAYLOAD_CALLS.append("executed")


def _synthetic_public_entrypoint(
    transition: object,
    mandate: object,
) -> object:
    del mandate
    return transition


def _synthetic_dependency_helper(value: object) -> object:
    return value


def _synthetic_dependency_root(value: object) -> object:
    return _synthetic_dependency_helper(value)


def _synthetic_imported_dependency_root(value: object) -> object:
    return copy(value)


def _dependency_source_swap_payload(value: object) -> object:
    _PUBLIC_ENTRYPOINT_PAYLOAD_CALLS.append("dependency-executed")
    return value


def _no_access_lookalike(events: list[str]) -> object:
    """Create an object whose every observable protocol is a test failure."""

    def record(event: str) -> typing.NoReturn:
        events.append(event)
        raise AssertionError(f"no-access lookalike protocol executed: {event}")

    class _NoAccessMeta(type):
        def __getattribute__(cls, name: str) -> object:
            return record(f"type-attribute:{name}")

        def __bool__(cls) -> bool:
            return record("type-bool")

        def __eq__(cls, other: object) -> bool:
            del other
            return record("type-eq")

        def __ne__(cls, other: object) -> bool:
            del other
            return record("type-ne")

        def __hash__(cls) -> int:
            return record("type-hash")

        def __iter__(cls) -> object:
            return record("type-iter")

        def __call__(cls, *args: object, **kwargs: object) -> object:
            del args, kwargs
            return record("type-call")

        def __str__(cls) -> str:
            return record("type-str")

        def __repr__(cls) -> str:
            return record("type-repr")

        def __format__(cls, specification: str) -> str:
            del specification
            return record("type-format")

    class _NoAccessDuck(metaclass=_NoAccessMeta):
        def __getattribute__(self, name: str) -> object:
            return record(f"attribute:{name}")

        def __bool__(self) -> bool:
            return record("bool")

        def __eq__(self, other: object) -> bool:
            del other
            return record("eq")

        def __ne__(self, other: object) -> bool:
            del other
            return record("ne")

        def __lt__(self, other: object) -> bool:
            del other
            return record("lt")

        def __le__(self, other: object) -> bool:
            del other
            return record("le")

        def __gt__(self, other: object) -> bool:
            del other
            return record("gt")

        def __ge__(self, other: object) -> bool:
            del other
            return record("ge")

        def __add__(self, other: object) -> object:
            del other
            return record("add")

        def __radd__(self, other: object) -> object:
            del other
            return record("radd")

        def __sub__(self, other: object) -> object:
            del other
            return record("sub")

        def __rsub__(self, other: object) -> object:
            del other
            return record("rsub")

        def __mul__(self, other: object) -> object:
            del other
            return record("mul")

        def __rmul__(self, other: object) -> object:
            del other
            return record("rmul")

        def __truediv__(self, other: object) -> object:
            del other
            return record("truediv")

        def __rtruediv__(self, other: object) -> object:
            del other
            return record("rtruediv")

        def __floordiv__(self, other: object) -> object:
            del other
            return record("floordiv")

        def __rfloordiv__(self, other: object) -> object:
            del other
            return record("rfloordiv")

        def __mod__(self, other: object) -> object:
            del other
            return record("mod")

        def __rmod__(self, other: object) -> object:
            del other
            return record("rmod")

        def __divmod__(self, other: object) -> object:
            del other
            return record("divmod")

        def __rdivmod__(self, other: object) -> object:
            del other
            return record("rdivmod")

        def __pow__(self, other: object, modulo: object = None) -> object:
            del other, modulo
            return record("pow")

        def __rpow__(self, other: object, modulo: object = None) -> object:
            del other, modulo
            return record("rpow")

        def __matmul__(self, other: object) -> object:
            del other
            return record("matmul")

        def __rmatmul__(self, other: object) -> object:
            del other
            return record("rmatmul")

        def __and__(self, other: object) -> object:
            del other
            return record("and")

        def __rand__(self, other: object) -> object:
            del other
            return record("rand")

        def __or__(self, other: object) -> object:
            del other
            return record("or")

        def __ror__(self, other: object) -> object:
            del other
            return record("ror")

        def __xor__(self, other: object) -> object:
            del other
            return record("xor")

        def __rxor__(self, other: object) -> object:
            del other
            return record("rxor")

        def __lshift__(self, other: object) -> object:
            del other
            return record("lshift")

        def __rlshift__(self, other: object) -> object:
            del other
            return record("rlshift")

        def __rshift__(self, other: object) -> object:
            del other
            return record("rshift")

        def __rrshift__(self, other: object) -> object:
            del other
            return record("rrshift")

        def __neg__(self) -> object:
            return record("neg")

        def __pos__(self) -> object:
            return record("pos")

        def __abs__(self) -> object:
            return record("abs")

        def __invert__(self) -> object:
            return record("invert")

        def __hash__(self) -> int:
            return record("hash")

        def __iter__(self) -> object:
            return record("iter")

        def __next__(self) -> object:
            return record("next")

        def __len__(self) -> int:
            return record("len")

        def __contains__(self, item: object) -> bool:
            del item
            return record("contains")

        def __getitem__(self, item: object) -> object:
            del item
            return record("getitem")

        def __call__(self, *args: object, **kwargs: object) -> object:
            del args, kwargs
            return record("call")

        def __str__(self) -> str:
            return record("str")

        def __repr__(self) -> str:
            return record("repr")

        def __format__(self, specification: str) -> str:
            del specification
            return record("format")

        def __bytes__(self) -> bytes:
            return record("bytes")

        def __int__(self) -> int:
            return record("int")

        def __index__(self) -> int:
            return record("index")

        def __float__(self) -> float:
            return record("float")

    return object.__new__(_NoAccessDuck)


def _price(
    units: int,
    *,
    tick_units: int = 1,
    scale: PriceScale = SCALE,
) -> ReportedPrice:
    tick = TickMetadata(tick_units=PriceUnits(tick_units), scale=scale)
    return ReportedPrice(units=PriceUnits(units), scale=scale, tick=tick)


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
    session_id: object | None = None,
    source_id: object | None = None,
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
        source_id=(source_id if source_id is not None else source_type("sip-primary")),
        max_age=max_age,
        corroboration_window=corroboration_window,
        max_step_fraction=max_step_fraction,
    )
    return mandate_type(
        mandate_id=mandate_id,
        position_scope=position_scope,
        session_id=(
            session_id if session_id is not None else session_type("session-rth-1")
        ),
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
    scale: PriceScale = SCALE,
):
    book, execution = venue_fixtures._seed_needs_review(capacity=capacity)
    fact = venue_fixtures._broker_fill(
        f"{label}-source",
        f"{label}-root",
        quantity=quantity,
        units=units,
    )
    if tick_units != 1 or scale != SCALE:
        fact = replace(
            fact,
            price=_price(units, tick_units=tick_units, scale=scale),
        )
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
    scale: PriceScale = SCALE,
):
    return _owned_fill_fixture(
        label=label,
        quantity=quantity,
        units=units,
        capacity=capacity,
        tick_units=tick_units,
        scale=scale,
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
    tick_units: int = 1,
    scale: PriceScale = SCALE,
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
        source_id=(
            source_id if source_id is not None else source_id_type("sip-primary")
        ),
        position_scope=position_scope,
        session_id=(
            session_id if session_id is not None else session_type("session-rth-1")
        ),
        market_epoch=market_epoch,
        source_sequence=sequence,
        source_time=source_time,
        evaluation_time=evaluation_time,
        kind=getattr(market_kind, kind),
        best_bid=(
            None if bid is None else _price(bid, tick_units=tick_units, scale=scale)
        ),
        best_ask=(
            None if ask is None else _price(ask, tick_units=tick_units, scale=scale)
        ),
        trade_price=(
            None if trade is None else _price(trade, tick_units=tick_units, scale=scale)
        ),
        atr_distance=(
            None
            if atr_distance is None
            else _price(atr_distance, tick_units=tick_units, scale=scale)
        ),
        structure_trail=(
            None
            if structure_trail is None
            else _price(structure_trail, tick_units=tick_units, scale=scale)
        ),
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


def _clone_opaque(original: object, **overrides: object) -> object:
    clone = object.__new__(type(original))
    for retained in fields(original):
        object.__setattr__(
            clone,
            retained.name,
            (
                overrides[retained.name]
                if retained.name in overrides
                else object.__getattribute__(original, retained.name)
            ),
        )
    return clone


def _flip_digest(value: bytes) -> bytes:
    return bytes((value[0] ^ 1,)) + value[1:]


_LEAF_MUTATION_SENTINEL = object()


@dataclass(frozen=True, slots=True)
class _LeafMutation:
    path: tuple[object, ...]
    forged: object


def _is_retained_leaf(value: object) -> bool:
    return (
        value is None
        or any(
            type(value) is allowed
            for allowed in (bool, bytes, int, str, Decimal, Fraction)
        )
        or isinstance(value, Enum)
    )


def _leaf_mutation_candidates(value: object) -> tuple[object, ...]:
    """Return deterministic unequal candidates without traversing arbitrary values."""
    if type(value) is bool:
        return (not value, _LEAF_MUTATION_SENTINEL)
    if type(value) is int:
        return (value + 1, value - 1, value + 2, _LEAF_MUTATION_SENTINEL)
    if type(value) is bytes:
        changed = _flip_digest(value) if value else b"\x00"
        return (changed, value + b"\x00", _LEAF_MUTATION_SENTINEL)
    if type(value) is str:
        return (
            f"{value}-forged",
            f"forged-{value}",
            _LEAF_MUTATION_SENTINEL,
        )
    if type(value) is Decimal:
        return (value + 1, value - 1, value + 2, _LEAF_MUTATION_SENTINEL)
    if type(value) is Fraction:
        return (value + 1, value - 1, value + 2, _LEAF_MUTATION_SENTINEL)
    if isinstance(value, Enum):
        alternatives = tuple(member for member in type(value) if member is not value)
        return alternatives + (_LEAF_MUTATION_SENTINEL,)
    raise AssertionError(f"unsupported retained leaf: {type(value).__name__}")


def _leaf_sort_key(value: object) -> tuple[object, ...]:
    """Canonicalize only the bounded passive grammar used by leaf mutations."""
    if value is None:
        return ("none",)
    if type(value) is bool:
        return ("bool", int(value))
    if type(value) is int:
        return ("int", value)
    if type(value) is bytes:
        return ("bytes", value.hex())
    if type(value) is str:
        return ("str", value)
    if type(value) is Decimal:
        decimal = value.as_tuple()
        return ("decimal", decimal.sign, decimal.digits, decimal.exponent)
    if type(value) is Fraction:
        return ("fraction", value.numerator, value.denominator)
    if isinstance(value, Enum):
        value_type = type(value)
        return (
            "enum",
            value_type.__module__,
            value_type.__qualname__,
            object.__getattribute__(value, "_name_"),
        )
    if type(value) is tuple:
        return ("tuple", tuple(_leaf_sort_key(item) for item in value))
    if type(value) is frozenset:
        return (
            "frozenset",
            tuple(sorted(_leaf_sort_key(item) for item in value)),
        )
    if is_dataclass(value) and not isinstance(value, type):
        value_type = type(value)
        assert value_type is not VenueRecoveryBook, (
            "leaf mutation cannot traverse VenueRecoveryBook"
        )
        return (
            "dataclass",
            value_type.__module__,
            value_type.__qualname__,
            tuple(
                (
                    retained.name,
                    _leaf_sort_key(object.__getattribute__(value, retained.name)),
                )
                for retained in fields(value)
            ),
        )
    raise AssertionError(f"unsupported retained value: {type(value).__name__}")


_DECLARED_REPLACEMENT_TYPES: dict[str, type[object]] = {
    "bool": bool,
    "bytes": bytes,
    "_Decimal": Decimal,
    "_Fraction": Fraction,
    "_ReportedPrice": ReportedPrice,
    "int": int,
    "str": str,
}


def _declared_annotation_expression(retained: object) -> ast.AST:
    annotation = object.__getattribute__(retained, "type")
    assert type(annotation) is str, "retained annotation is not inert text"
    return ast.parse(annotation, mode="eval", feature_version=(3, 11)).body


def _collection_element_annotation(
    annotation: ast.AST,
    collection_type: type[object],
    index: int,
) -> ast.AST:
    assert isinstance(annotation, ast.Subscript), (
        "indexed retained value lacks a collection annotation"
    )
    owner = annotation.value
    owner_name = (
        owner.id
        if isinstance(owner, ast.Name)
        else owner.attr
        if isinstance(owner, ast.Attribute)
        else ""
    )
    assert owner_name == collection_type.__name__, (
        "retained collection annotation does not match its exact type"
    )
    element = annotation.slice
    if collection_type is frozenset:
        return element
    assert collection_type is tuple and isinstance(element, ast.Tuple)
    if (
        len(element.elts) == 2
        and isinstance(element.elts[1], ast.Constant)
        and element.elts[1].value is Ellipsis
    ):
        return element.elts[0]
    assert index < len(element.elts), "retained tuple annotation is incomplete"
    return element.elts[index]


def _retained_value_and_annotation_at_path(
    root: object,
    path: tuple[object, ...],
) -> tuple[object, ast.AST]:
    """Resolve a retained value and inert annotation through the passive grammar."""

    assert path, "replacement path cannot be the root"
    current = root
    annotation: ast.AST | None = None
    for component in path:
        if isinstance(component, str):
            assert is_dataclass(current) and not isinstance(current, type)
            retained = next(
                (field for field in fields(current) if field.name == component),
                None,
            )
            assert retained is not None, f"unknown retained field path: {path!r}"
            annotation = _declared_annotation_expression(retained)
            current = object.__getattribute__(current, component)
            continue
        assert type(component) is int
        assert annotation is not None
        collection_type = type(current)
        assert collection_type in {tuple, frozenset}
        annotation = _collection_element_annotation(
            annotation,
            collection_type,
            component,
        )
        if type(current) is tuple:
            current = current[component]
            continue
        current = tuple(sorted(current, key=_leaf_sort_key))[component]
    assert annotation is not None
    return current, annotation


def _annotation_member_names(node: ast.AST) -> frozenset[str]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _annotation_member_names(node.left) | _annotation_member_names(
            node.right
        )
    if isinstance(node, ast.Name):
        return frozenset({node.id})
    if isinstance(node, ast.Attribute):
        return frozenset({node.attr})
    if isinstance(node, ast.Constant) and node.value is None:
        return frozenset({"None"})
    raise AssertionError(f"unsupported retained annotation member: {ast.dump(node)}")


def _validate_union_replacement(
    root: object,
    path: tuple[object, ...],
    replacement: object,
) -> None:
    current, annotation = _retained_value_and_annotation_at_path(root, path)
    assert current is None, f"union replacement path is not None: {path!r}"
    names = _annotation_member_names(annotation)
    assert "None" in names, f"replacement path is not an optional union: {path!r}"
    allowed = tuple(
        _DECLARED_REPLACEMENT_TYPES[name]
        for name in names - {"None"}
        if name in _DECLARED_REPLACEMENT_TYPES
    )
    assert len(allowed) == len(names - {"None"}) and allowed, (
        f"optional union has no authenticated replacement type: {path!r}"
    )
    assert any(type(replacement) is expected for expected in allowed), (
        f"replacement is outside the declared optional union: {path!r}"
    )


def _validate_empty_collection_replacement(
    root: object,
    path: tuple[object, ...],
    replacement: object,
) -> None:
    current, annotation = _retained_value_and_annotation_at_path(root, path)
    assert type(current) in {tuple, frozenset} and not current
    assert type(replacement) is type(current) and replacement, (
        f"empty collection replacement changed shape or stayed empty: {path!r}"
    )
    assert isinstance(annotation, ast.Subscript) and isinstance(
        annotation.value, ast.Name
    )
    assert annotation.value.id == type(current).__name__
    element_annotation = annotation.slice
    if type(current) is tuple:
        assert (
            isinstance(element_annotation, ast.Tuple)
            and len(element_annotation.elts) == 2
            and isinstance(element_annotation.elts[1], ast.Constant)
            and element_annotation.elts[1].value is Ellipsis
        ), f"empty tuple replacement lacks a homogeneous declaration: {path!r}"
        element_annotation = element_annotation.elts[0]
    names = _annotation_member_names(element_annotation)
    allowed = tuple(
        _DECLARED_REPLACEMENT_TYPES[name]
        for name in names
        if name in _DECLARED_REPLACEMENT_TYPES
    )
    assert len(allowed) == len(names) and allowed, (
        f"empty collection has no authenticated element type: {path!r}"
    )
    assert all(
        any(type(item) is expected for expected in allowed) for item in replacement
    ), f"empty collection replacement has an undeclared element: {path!r}"


def test_private_import_annotation_names_resolve_exact_replacement_types() -> None:
    """Deferred field annotations use the same private names as runtime imports."""

    source = (
        "from __future__ import annotations as _annotations\n"
        "from dataclasses import dataclass as _dataclass\n"
        "from decimal import Decimal as _Decimal\n"
        "from fractions import Fraction as _Fraction\n"
        "@_dataclass(frozen=True, slots=True)\n"
        "class _PrivateAnnotationProbe:\n"
        "    price: _ReportedPrice | None\n"
        "    decimal: _Decimal | None\n"
        "    fraction: _Fraction | None\n"
    )
    namespace: dict[str, object] = {"_ReportedPrice": ReportedPrice}
    exec(compile(source, "<private-annotation-probe>", "exec"), namespace)
    probe_type = namespace["_PrivateAnnotationProbe"]
    probe = probe_type(price=None, decimal=None, fraction=None)
    replacements = {
        "price": _price(101),
        "decimal": Decimal("1.25"),
        "fraction": Fraction(1, 4),
    }
    for field_name, replacement in replacements.items():
        _validate_union_replacement(probe, (field_name,), replacement)


def _walk_single_leaf_mutations(
    value: object,
    path: tuple[object, ...],
    ancestors: frozenset[int],
    union_replacements: dict[tuple[object, ...], object],
    empty_collection_replacements: dict[tuple[object, ...], object],
) -> tuple[_LeafMutation, ...]:
    if value is None:
        assert path in union_replacements, (
            f"missing valid union replacement for optional leaf: {path!r}"
        )
        replacement = union_replacements[path]
        assert replacement is not None and replacement is not _LEAF_MUTATION_SENTINEL
        return (_LeafMutation(path=path, forged=replacement),)
    if _is_retained_leaf(value):
        candidates = tuple(
            replacement
            for replacement in _leaf_mutation_candidates(value)
            if type(replacement) is type(value) and replacement != value
        )
        assert candidates, f"retained leaf has no same-type alternative: {path!r}"
        return tuple(
            _LeafMutation(path=path, forged=candidate) for candidate in candidates
        )

    if type(value) is tuple:
        if not value:
            assert path in empty_collection_replacements, (
                f"missing valid empty-tuple replacement: {path!r}"
            )
            return (
                _LeafMutation(path=path, forged=empty_collection_replacements[path]),
            )
        assert id(value) not in ancestors, "cyclic retained tuple"
        nested_ancestors = ancestors | {id(value)}
        mutations: list[_LeafMutation] = []
        for index, item in enumerate(value):
            for mutation in _walk_single_leaf_mutations(
                item,
                path + (index,),
                nested_ancestors,
                union_replacements,
                empty_collection_replacements,
            ):
                forged = value[:index] + (mutation.forged,) + value[index + 1 :]
                assert len(forged) == len(value)
                mutations.append(_LeafMutation(mutation.path, forged))
        return tuple(mutations)

    if type(value) is frozenset:
        if not value:
            assert path in empty_collection_replacements, (
                f"missing valid empty-frozenset replacement: {path!r}"
            )
            return (
                _LeafMutation(
                    path=path,
                    forged=empty_collection_replacements[path],
                ),
            )
        assert id(value) not in ancestors, "cyclic retained frozenset"
        nested_ancestors = ancestors | {id(value)}
        members = tuple(sorted(value, key=_leaf_sort_key))
        mutations = []
        for index, item in enumerate(members):
            siblings = members[:index] + members[index + 1 :]
            item_path = path + (index,)
            emitted_paths: set[tuple[object, ...]] = set()
            candidates = _walk_single_leaf_mutations(
                item,
                item_path,
                nested_ancestors,
                union_replacements,
                empty_collection_replacements,
            )
            candidate_paths = {mutation.path for mutation in candidates}
            for mutation in candidates:
                valid_union_swap = item is None and mutation.path in union_replacements
                if type(mutation.forged) is not type(item) and not valid_union_swap:
                    continue
                if mutation.path in emitted_paths:
                    continue
                forged = frozenset((*siblings, mutation.forged))
                if len(forged) != len(value) or forged == value:
                    continue
                mutations.append(_LeafMutation(mutation.path, forged))
                emitted_paths.add(mutation.path)
            missing_paths = candidate_paths - emitted_paths
            assert not missing_paths, (
                f"frozenset leaf has no non-colliding same-type mutation: "
                f"{sorted(missing_paths)!r}"
            )
        return tuple(mutations)

    assert is_dataclass(value) and not isinstance(value, type), (
        f"unsupported retained value: {type(value).__name__}"
    )
    assert type(value) is not VenueRecoveryBook, (
        "leaf mutation cannot traverse VenueRecoveryBook"
    )
    assert id(value) not in ancestors, "cyclic retained dataclass"
    retained_fields = fields(value)
    assert retained_fields, "empty retained dataclass has no independent leaf"
    nested_ancestors = ancestors | {id(value)}
    mutations = []
    for retained in retained_fields:
        current = object.__getattribute__(value, retained.name)
        for mutation in _walk_single_leaf_mutations(
            current,
            path + (retained.name,),
            nested_ancestors,
            union_replacements,
            empty_collection_replacements,
        ):
            mutations.append(
                _LeafMutation(
                    mutation.path,
                    _clone_opaque(value, **{retained.name: mutation.forged}),
                )
            )
    return tuple(mutations)


def _single_leaf_mutations(
    root: object,
    *,
    allowed_root_types: tuple[type[object], ...],
    union_replacements: dict[tuple[object, ...], object] | None = None,
    empty_collection_replacements: dict[tuple[object, ...], object] | None = None,
) -> tuple[_LeafMutation, ...]:
    assert any(type(root) is allowed for allowed in allowed_root_types), (
        f"leaf mutation root is out of scope: {type(root).__name__}"
    )
    replacements = {} if union_replacements is None else union_replacements
    for path, replacement in replacements.items():
        _validate_union_replacement(root, path, replacement)
    empty_replacements = (
        {} if empty_collection_replacements is None else empty_collection_replacements
    )
    for path, replacement in empty_replacements.items():
        _validate_empty_collection_replacement(root, path, replacement)
    candidates = _walk_single_leaf_mutations(
        root,
        (),
        frozenset(),
        replacements,
        empty_replacements,
    )
    selected: dict[tuple[object, ...], _LeafMutation] = {}
    for mutation in candidates:
        selected.setdefault(mutation.path, mutation)
    return tuple(selected.values())


def _retained_leaf_paths(
    value: object,
    path: tuple[object, ...] = (),
) -> frozenset[tuple[object, ...]]:
    """Independently enumerate retained leaves without rebuilding mutations."""
    if _is_retained_leaf(value):
        return frozenset({path})
    if type(value) is tuple:
        if not value:
            return frozenset({path})
        return frozenset(
            nested
            for index, item in enumerate(value)
            for nested in _retained_leaf_paths(item, path + (index,))
        )
    if type(value) is frozenset:
        if not value:
            return frozenset({path})
        members = tuple(sorted(value, key=_leaf_sort_key))
        return frozenset(
            nested
            for index, item in enumerate(members)
            for nested in _retained_leaf_paths(item, path + (index,))
        )
    assert is_dataclass(value) and not isinstance(value, type)
    assert type(value) is not VenueRecoveryBook
    return frozenset(
        nested
        for retained in fields(value)
        for nested in _retained_leaf_paths(
            object.__getattribute__(value, retained.name),
            path + (retained.name,),
        )
    )


def _changed_leaf_paths(
    before: object,
    after: object,
    path: tuple[object, ...] = (),
) -> frozenset[tuple[object, ...]]:
    """Independently prove a rebuilt graph changed exactly one original leaf."""
    if _is_retained_leaf(before):
        return (
            frozenset()
            if type(after) is type(before) and after == before
            else frozenset({path})
        )
    if type(before) is tuple:
        if type(after) is not tuple or len(after) != len(before):
            return frozenset({path})
        return frozenset(
            nested
            for index, (left, right) in enumerate(zip(before, after, strict=True))
            for nested in _changed_leaf_paths(left, right, path + (index,))
        )
    if type(before) is frozenset:
        if type(after) is not frozenset or len(after) != len(before):
            return frozenset({path})
        if after == before:
            return frozenset()
        removed = tuple(before - after)
        added = tuple(after - before)
        assert len(removed) == len(added) == 1
        members = tuple(sorted(before, key=_leaf_sort_key))
        index = members.index(removed[0])
        return _changed_leaf_paths(removed[0], added[0], path + (index,))
    if type(after) is not type(before):
        return frozenset({path})
    assert is_dataclass(before) and not isinstance(before, type)
    assert type(before) is not VenueRecoveryBook
    return frozenset(
        nested
        for retained in fields(before)
        for nested in _changed_leaf_paths(
            object.__getattribute__(before, retained.name),
            object.__getattribute__(after, retained.name),
            path + (retained.name,),
        )
    )


def _different_value(value: object) -> object:
    """Return one deterministic unequal value for top-level envelope pins."""
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is bytes:
        return _flip_digest(value) if value else b"forged"
    if type(value) is str:
        return f"{value}-forged"
    if isinstance(value, Fraction):
        return value + 1
    if isinstance(value, Decimal):
        return value + 1
    if isinstance(value, Enum):
        alternatives = tuple(member for member in type(value) if member is not value)
        return alternatives[0] if alternatives else object()
    if isinstance(value, tuple):
        return value + (object(),)
    if value is None:
        return object()
    if is_dataclass(value):
        retained_fields = fields(value)
        if retained_fields:
            target = retained_fields[0]
            clone = _clone_opaque(
                value,
                **{
                    target.name: _different_value(getattr(value, target.name)),
                },
            )
            assert clone != value
            return clone
    return object()


@dataclass(frozen=True, slots=True)
class _PassiveDataclassProbe:
    """Version-adaptive baseline for behaviorless frozen dataclass machinery."""

    value: object

    def __post_init__(self) -> None:
        return None


_PASSIVE_SLOT_DESCRIPTOR_TYPE = type(vars(_PassiveDataclassProbe)["value"])
_PASSIVE_FIELD_METADATA_TYPE = type(
    vars(_PassiveDataclassProbe)["__dataclass_fields__"]["value"]
)
_PASSIVE_PARAMS_TYPE = type(vars(_PassiveDataclassProbe)["__dataclass_params__"])
_PASSIVE_FIELD_KIND = vars(_PassiveDataclassProbe)["__dataclass_fields__"][
    "value"
]._field_type
_PASSIVE_FIELD_METADATA_MAPPING_TYPE = type(
    vars(_PassiveDataclassProbe)["__dataclass_fields__"]["value"].metadata
)
_LIFECYCLE_SOURCE_SWAP_CALLS: list[str] = []
_LIFECYCLE_ATTRIBUTE_ACCESS_CALLS: list[str] = []


class _ActiveGuardedGetattribute:
    __slots__ = ("value",)
    __module__ = "app.execution_core.synthetic"

    def __init__(self, value: int) -> None:
        object.__setattr__(self, "value", value)

    def __getattribute__(self, name: str) -> object:
        _LIFECYCLE_ATTRIBUTE_ACCESS_CALLS.append(f"getattribute:{name}")
        return object.__getattribute__(self, name)


class _ActiveGuardedGetattr:
    __slots__ = ("value",)
    __module__ = "app.execution_core.synthetic"

    def __getattr__(self, name: str) -> object:
        _LIFECYCLE_ATTRIBUTE_ACCESS_CALLS.append(f"getattr:{name}")
        if name == "value":
            return -1
        raise AttributeError(name)


def _lifecycle_source_swap_payload(_self: object) -> None:
    _LIFECYCLE_SOURCE_SWAP_CALLS.append("executed")


_DATACLASS_METADATA_SPECIALS = frozenset(
    {
        "__annotations__",
        "__classcell__",
        "__dataclass_fields__",
        "__dataclass_params__",
        "__dict__",
        "__doc__",
        "__firstlineno__",
        "__match_args__",
        "__module__",
        "__qualname__",
        "__slots__",
        "__static_attributes__",
        "__weakref__",
    }
)
_DATACLASS_LIFECYCLE_SPECIALS = frozenset(
    {"__init__", "__init_subclass__", "__post_init__"}
)
_DATACLASS_GENERATED_SPECIALS = frozenset(
    name
    for name in vars(_PassiveDataclassProbe)
    if name.startswith("__")
    and name not in _DATACLASS_METADATA_SPECIALS
    and name not in {"__init_subclass__", "__post_init__"}
)


class _PassiveEnumProbe(Enum):
    """Version-adaptive baseline for a behaviorless plain enum."""

    FIRST = 1
    SECOND = 2


class _PassiveStrEnumProbe(str, Enum):
    """Version-adaptive baseline for a behaviorless string enum."""

    FIRST = "FIRST"
    SECOND = "SECOND"


def _assert_passive_enum_type(
    enum_type: type[Enum],
    expected_members: tuple[str, ...],
) -> None:
    """Seal enum behavior and member payloads without freezing wire representation."""
    assert type(enum_type) is type(Enum), "enum metaclass changed"
    enum_mro = inspect.getmro(enum_type)
    if enum_mro == (enum_type, Enum, object):
        reference_type: type[Enum] = _PassiveEnumProbe
        required_value_type: type[object] | None = None
    else:
        assert enum_mro == (enum_type, str, Enum, object), (
            "enum class hierarchy retains an unsafe mixin"
        )
        reference_type = _PassiveStrEnumProbe
        required_value_type = str

    actual = vars(enum_type)
    actual_members = actual["_member_map_"]
    assert type(actual_members) is dict
    assert tuple(actual_members) == expected_members, "enum member inventory changed"
    assert all(type(member) is enum_type for member in actual_members.values())
    assert len({id(member) for member in actual_members.values()}) == len(
        expected_members
    ), "enum aliases changed"

    reference = vars(reference_type)
    reference_members = reference["_member_map_"]
    reference_residual = set(reference) - set(reference_members)
    actual_residual = set(actual) - set(actual_members)
    assert actual_residual == reference_residual, "enum class shape changed"

    reference_member = next(iter(reference_members.values()))
    reference_member_shape = vars(reference_member)
    for index, (name, member) in enumerate(actual_members.items()):
        member_state = object.__getattribute__(member, "__dict__")
        assert type(member_state) is dict
        assert set(member_state) == set(reference_member_shape), (
            f"enum member payload changed: {name}"
        )
        value = member_state["_value_"]
        assert any(
            type(value) is allowed
            for allowed in (bool, bytes, int, str, Decimal, Fraction, type(None))
        ), f"enum member retains a capability value: {name}"
        if required_value_type is not None:
            assert type(value) is required_value_type, "string enum value type changed"
        assert member_state["_name_"] == name
        assert member_state["__objclass__"] is enum_type
        if "_sort_order_" in reference_member_shape:
            assert type(member_state["_sort_order_"]) is int
            assert member_state["_sort_order_"] == index
        for retained_name in set(reference_member_shape) - {
            "_value_",
            "_name_",
            "__objclass__",
            "_sort_order_",
        }:
            assert type(member_state[retained_name]) is type(
                reference_member_shape[retained_name]
            )

    for name in reference_residual:
        expected = reference[name]
        retained = actual[name]
        if name == "__module__":
            assert type(retained) is str
        elif name == "__doc__":
            assert retained is None or type(retained) is str
        elif name == "_member_names_":
            assert type(retained) is list and retained == list(expected_members)
        elif name == "_member_map_":
            assert type(retained) is dict and tuple(retained) == expected_members
            assert all(retained[key] is actual_members[key] for key in expected_members)
        elif name == "_value2member_map_":
            assert type(retained) is dict and len(retained) == len(expected_members)
            assert all(
                retained.get(object.__getattribute__(member, "_value_")) is member
                for member in actual_members.values()
            )
        elif name in {"_unhashable_values_", "_unhashable_values_map_"}:
            assert type(retained) is type(expected) and not retained
        elif isinstance(expected, staticmethod):
            assert isinstance(retained, staticmethod)
            assert retained.__func__ is expected.__func__
        elif name in {"__dict__", "__weakref__"}:
            assert type(retained) is type(expected)
        else:
            assert retained is expected, f"enum behavior changed: {name}"


_PASSIVE_RUNTIME_CODE_FLAGS = sum(
    getattr(inspect, name, 0)
    for name in (
        "CO_OPTIMIZED",
        "CO_NEWLOCALS",
        "CO_VARARGS",
        "CO_VARKEYWORDS",
        "CO_GENERATOR",
        "CO_COROUTINE",
        "CO_ASYNC_GENERATOR",
    )
)


def _passive_constant_signature(
    value: object,
    *,
    include_code_location: bool,
) -> tuple[object, ...]:
    """Describe code constants without invoking attacker-controlled protocols."""
    if value is None or value is Ellipsis or value is NotImplemented:
        return ("singleton", value)
    if any(
        type(value) is allowed for allowed in (bool, bytes, complex, float, int, str)
    ):
        return ("scalar", type(value), value)
    if type(value) is tuple:
        return (
            "tuple",
            tuple(
                _passive_constant_signature(
                    item,
                    include_code_location=include_code_location,
                )
                for item in value
            ),
        )
    if type(value) is frozenset:
        return (
            "frozenset",
            frozenset(
                _passive_constant_signature(
                    item,
                    include_code_location=include_code_location,
                )
                for item in value
            ),
        )
    if type(value) is CodeType:
        return (
            "code",
            _passive_code_signature(
                value,
                include_location=include_code_location,
            ),
        )
    raise AssertionError(
        f"generated or lifecycle code retains a capability constant: {type(value).__name__}"
    )


def _passive_code_signature(
    code: CodeType,
    *,
    include_location: bool,
) -> tuple[object, ...]:
    """Return exact executable semantics, optionally including source location metadata."""
    signature: tuple[object, ...] = (
        code.co_code,
        tuple(
            _passive_constant_signature(
                item,
                include_code_location=include_location,
            )
            for item in code.co_consts
        ),
        code.co_names,
        code.co_varnames,
        code.co_freevars,
        code.co_cellvars,
        code.co_argcount,
        code.co_posonlyargcount,
        code.co_kwonlyargcount,
        code.co_nlocals,
        code.co_stacksize,
        code.co_flags & _PASSIVE_RUNTIME_CODE_FLAGS,
        getattr(code, "co_exceptiontable", b""),
    )
    if not include_location:
        return signature
    return signature + (
        code.co_name,
        code.co_qualname,
        code.co_filename,
        code.co_firstlineno,
        code.co_linetable,
    )


def _assert_function_matches_inspected_source(
    function: Callable[..., object],
    source: str,
    *,
    message: str,
) -> None:
    """Tie executable bytecode to the exact source inspected by a static oracle."""
    compiled = compile(
        source,
        "<inspected-function-source>",
        "exec",
        dont_inherit=True,
    )
    source_codes = [
        constant
        for constant in compiled.co_consts
        if type(constant) is CodeType and constant.co_name == function.__name__
    ]
    assert len(source_codes) == 1
    assert _passive_code_signature(
        function.__code__, include_location=False
    ) == _passive_code_signature(source_codes[0], include_location=False), message


def _canonical_function_source(
    owner_module: ModuleType,
    qualified_name: str,
) -> str:
    """Read one exact function body from its canonical module file."""
    module_path = Path(owner_module.__file__).resolve()
    source = module_path.read_text(encoding="utf-8")
    scope: list[ast.stmt] = ast.parse(source, filename=str(module_path)).body
    target: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for part in qualified_name.split("."):
        matches = [
            node
            for node in scope
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == part
        ]
        assert len(matches) == 1, (
            f"canonical function source is ambiguous: {qualified_name}"
        )
        target = matches[0]
        scope = target.body
    assert isinstance(target, (ast.FunctionDef, ast.AsyncFunctionDef))
    segment = ast.get_source_segment(source, target)
    assert type(segment) is str
    return textwrap.dedent(segment)


def _target_binds_name(target: ast.AST, name: str) -> bool:
    if isinstance(target, ast.Name):
        return target.id == name
    if isinstance(target, (ast.List, ast.Tuple)):
        return any(_target_binds_name(item, name) for item in target.elts)
    if isinstance(target, ast.Starred):
        return _target_binds_name(target.value, name)
    return False


def _module_scope_binding_kinds(source: str, name: str) -> tuple[str, ...]:
    """Inventory one module name without descending into local scopes."""
    bindings: list[str] = []

    class _BindingVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node.name == name:
                bindings.append("function")

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node.name == name:
                bindings.append("async-function")

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            if node.name == name:
                bindings.append("class")

        def visit_Assign(self, node: ast.Assign) -> None:
            if any(_target_binds_name(target, name) for target in node.targets):
                bindings.append("assignment")
            self.visit(node.value)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if _target_binds_name(node.target, name):
                bindings.append("annotated-assignment")
            if node.value is not None:
                self.visit(node.value)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            if _target_binds_name(node.target, name):
                bindings.append("augmented-assignment")
            self.visit(node.value)

        def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
            if _target_binds_name(node.target, name):
                bindings.append("named-expression")
            self.visit(node.value)

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                retained = alias.asname or alias.name.split(".", 1)[0]
                if retained == name:
                    bindings.append("import")

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            for alias in node.names:
                retained = alias.asname or alias.name
                if retained == name or retained == "*":
                    bindings.append("import")

        def visit_For(self, node: ast.For) -> None:
            if _target_binds_name(node.target, name):
                bindings.append("for-target")
            self.generic_visit(node)

        visit_AsyncFor = visit_For

        def visit_With(self, node: ast.With) -> None:
            if any(
                item.optional_vars is not None
                and _target_binds_name(item.optional_vars, name)
                for item in node.items
            ):
                bindings.append("with-target")
            self.generic_visit(node)

        visit_AsyncWith = visit_With

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if node.name == name:
                bindings.append("except-target")
            self.generic_visit(node)

        def visit_Delete(self, node: ast.Delete) -> None:
            if any(_target_binds_name(target, name) for target in node.targets):
                bindings.append("deletion")

    _BindingVisitor().visit(ast.parse(source))
    return tuple(bindings)


def _assert_public_entrypoint_provenance(
    owner_module: ModuleType,
    name: str,
    parameter_names: tuple[str, ...],
    expected_annotations: dict[str, str],
) -> None:
    """Seal one public binding to canonical source and inert runtime metadata."""
    module_path = Path(owner_module.__file__).resolve()
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module_path))
    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    assert len(matches) == 1 and isinstance(matches[0], ast.FunctionDef)
    function_node = matches[0]
    assert _module_scope_binding_kinds(source, name) == ("function",), (
        f"public entrypoint was rebound: {name}"
    )
    assert not function_node.decorator_list
    assert not function_node.args.posonlyargs
    assert not function_node.args.kwonlyargs
    assert function_node.args.vararg is None and function_node.args.kwarg is None
    assert not function_node.args.defaults and not function_node.args.kw_defaults
    assert (
        tuple(argument.arg for argument in function_node.args.args) == parameter_names
    )

    candidate = vars(owner_module).get(name)
    assert type(candidate) is FunctionType, (
        f"public entrypoint is not an exact function: {name}"
    )
    assert vars(execution_core).get(name) is candidate, (
        f"public entrypoint package binding changed: {name}"
    )
    assert candidate.__globals__ is vars(owner_module)
    assert candidate.__module__ == owner_module.__name__
    assert candidate.__name__ == name and candidate.__qualname__ == name
    assert Path(candidate.__code__.co_filename).resolve() == module_path
    assert candidate.__code__.co_name == name
    assert candidate.__code__.co_qualname == name
    assert candidate.__code__.co_firstlineno == function_node.lineno
    assert candidate.__defaults__ is None
    assert candidate.__kwdefaults__ is None
    assert candidate.__closure__ is None and not candidate.__code__.co_freevars
    assert type(candidate.__dict__) is dict and not candidate.__dict__
    assert candidate.__doc__ is None or type(candidate.__doc__) is str
    annotations = candidate.__annotations__
    assert type(annotations) is dict
    assert all(type(key) is str for key in annotations)
    assert all(type(value) is str for value in annotations.values())
    assert annotations == expected_annotations
    signature = inspect.signature(candidate, eval_str=False)
    assert tuple(signature.parameters) == parameter_names
    assert all(
        parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        and parameter.default is inspect.Parameter.empty
        for parameter in signature.parameters.values()
    )
    _assert_function_matches_inspected_source(
        candidate,
        _canonical_function_source(owner_module, name),
        message=f"public entrypoint bytecode does not match canonical source: {name}",
    )


def _assert_local_function_dependency_provenance(
    owner_module: ModuleType,
    root_names: tuple[str, ...],
) -> None:
    """Seal every source-reachable module helper without executing production."""

    module_path = Path(owner_module.__file__).resolve()
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module_path))
    declarations = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    assert set(root_names) <= set(declarations)

    pending = list(root_names)
    reachable: set[str] = set()
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        pending.extend(
            call.func.id
            for call in ast.walk(declarations[name])
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id in declarations
            and call.func.id not in reachable
        )

    imported_origins: dict[str, tuple[str, str]] = {}
    package_parts = owner_module.__package__.split(".")
    for statement in tree.body:
        if not isinstance(statement, ast.ImportFrom) or statement.module is None:
            continue
        if statement.level:
            retained_parts = package_parts[: len(package_parts) - statement.level + 1]
            origin_module = ".".join((*retained_parts, statement.module))
        else:
            origin_module = statement.module
        for alias in statement.names:
            if alias.name != "*":
                imported_origins[alias.asname or alias.name] = (
                    origin_module,
                    alias.name,
                )

    referenced_names = {
        node.id
        for name in reachable
        for node in ast.walk(declarations[name])
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    for retained_name in sorted(referenced_names & set(imported_origins)):
        origin_module_name, origin_name = imported_origins[retained_name]
        origin_module = importlib.import_module(origin_module_name)
        assert vars(owner_module).get(retained_name) is vars(origin_module).get(
            origin_name
        ), f"imported dependency binding changed: {retained_name}"

    for name in sorted(reachable):
        function_node = declarations[name]
        assert _module_scope_binding_kinds(source, name) == ("function",), (
            f"module helper was rebound: {name}"
        )
        assert not function_node.decorator_list
        assert not function_node.args.defaults
        assert not any(
            default is not None for default in function_node.args.kw_defaults
        )

        candidate = vars(owner_module).get(name)
        assert type(candidate) is FunctionType, (
            f"module helper is not an exact function: {name}"
        )
        assert candidate.__globals__ is vars(owner_module)
        assert candidate.__module__ == owner_module.__name__
        assert candidate.__name__ == name and candidate.__qualname__ == name
        assert Path(candidate.__code__.co_filename).resolve() == module_path
        assert candidate.__code__.co_name == name
        assert candidate.__code__.co_qualname == name
        assert candidate.__code__.co_firstlineno == function_node.lineno
        assert candidate.__defaults__ is None
        assert candidate.__kwdefaults__ is None
        assert candidate.__closure__ is None and not candidate.__code__.co_freevars
        assert type(candidate.__dict__) is dict and not candidate.__dict__
        assert candidate.__doc__ is None or type(candidate.__doc__) is str
        assert type(candidate.__annotations__) is dict
        assert all(type(key) is str for key in candidate.__annotations__)
        assert all(type(value) is str for value in candidate.__annotations__.values())
        _assert_function_matches_inspected_source(
            candidate,
            _canonical_function_source(owner_module, name),
            message=f"module helper bytecode does not match canonical source: {name}",
        )


def _clone_entrypoint_function(
    function: Callable[..., object],
    *,
    code: CodeType | None = None,
    defaults: tuple[object, ...] | None = None,
    closure: tuple[object, ...] | None = None,
) -> Callable[..., object]:
    retained_closure = function.__closure__ if closure is None else closure
    clone = FunctionType(
        function.__code__ if code is None else code,
        function.__globals__,
        function.__name__,
        defaults,
        retained_closure,
    )
    clone.__qualname__ = function.__qualname__
    clone.__module__ = function.__module__
    clone.__doc__ = function.__doc__
    clone.__kwdefaults__ = function.__kwdefaults__
    clone.__annotations__ = dict(function.__annotations__)
    return clone


def _resolved_exact_global(function: Callable[..., object], name: str) -> object:
    globals_map = function.__globals__
    if name in globals_map:
        return globals_map[name]
    retained_builtins = globals_map.get("__builtins__", builtins)
    if retained_builtins is builtins:
        return vars(builtins)[name]
    assert type(retained_builtins) is dict, "function builtins source changed"
    return retained_builtins[name]


def _assert_exact_function_dependency_closure(
    function: Callable[..., object],
    owner_module: ModuleType,
    *,
    qualified_name: str,
    exact_externals: dict[str, object],
    seen: set[int] | None = None,
) -> None:
    """Seal executable globals recursively before a bounded map method runs."""
    visited = set() if seen is None else seen
    if id(function) in visited:
        return
    visited.add(id(function))

    assert inspect.isfunction(function)
    assert function.__globals__ is vars(owner_module), (
        f"{qualified_name} dependency globals changed"
    )
    assert function.__module__ == owner_module.__name__
    assert function.__name__ == qualified_name.rsplit(".", 1)[-1]
    assert function.__qualname__ == qualified_name
    module_path = Path(owner_module.__file__).resolve()
    assert Path(function.__code__.co_filename).resolve() == module_path
    assert function.__defaults__ is None
    assert function.__kwdefaults__ is None
    assert function.__closure__ is None and not function.__code__.co_freevars
    assert type(function.__dict__) is dict and not function.__dict__
    assert function.__doc__ is None or type(function.__doc__) is str
    assert type(function.__annotations__) is dict
    assert all(type(name) is str for name in function.__annotations__)
    assert all(type(value) is str for value in function.__annotations__.values())
    _assert_function_matches_inspected_source(
        function,
        _canonical_function_source(owner_module, qualified_name),
        message=f"{qualified_name} bytecode does not match canonical source",
    )

    dependencies = {
        instruction.argval
        for instruction in dis.get_instructions(function)
        if instruction.opname == "LOAD_GLOBAL" and type(instruction.argval) is str
    }
    for name in dependencies:
        candidate = _resolved_exact_global(function, name)
        if name in exact_externals:
            assert candidate is exact_externals[name], (
                f"{qualified_name} global identity changed: {name}"
            )
            continue
        assert inspect.isfunction(candidate), (
            f"{qualified_name} has an unsealed executable global: {name}"
        )
        assert candidate is vars(owner_module).get(name), (
            f"{qualified_name} same-module dependency was rebound: {name}"
        )
        _assert_exact_function_dependency_closure(
            candidate,
            owner_module,
            qualified_name=name,
            exact_externals=exact_externals,
            seen=visited,
        )


def _assert_generated_function_metadata(function: Callable[..., object]) -> None:
    """Reject defaults, annotations, or attributes that retain executable capability."""
    assert function.__defaults__ is None
    assert function.__kwdefaults__ is None
    annotations = function.__annotations__
    assert type(annotations) is dict
    assert all(type(name) is str for name in annotations)
    assert all(
        type(value) is str or value is None or value is type(None) or value is object
        for value in annotations.values()
    ), "generated function annotation retains a capability"
    assert function.__doc__ is None or type(function.__doc__) is str
    assert type(function.__dict__) is dict


def _assert_generated_special_matches(
    member: object,
    reference: object,
    *,
    owner: type[object],
    reference_owner: type[object],
) -> None:
    """Match generated behavior to a fresh same-shape dataclass reference."""
    assert type(member) is type(reference), "dataclass generated special type changed"
    assert inspect.isfunction(member) and inspect.isfunction(reference)
    _assert_generated_function_metadata(member)
    assert member.__name__ == reference.__name__
    assert _passive_code_signature(
        member.__code__, include_location=True
    ) == _passive_code_signature(reference.__code__, include_location=True), (
        f"dataclass generated behavior changed: {member.__name__}"
    )

    member_attributes = member.__dict__
    reference_attributes = reference.__dict__
    assert set(member_attributes) == set(reference_attributes)
    for name, reference_attribute in reference_attributes.items():
        attribute = member_attributes[name]
        if inspect.isfunction(reference_attribute):
            _assert_generated_special_matches(
                attribute,
                reference_attribute,
                owner=owner,
                reference_owner=reference_owner,
            )
        else:
            assert attribute is reference_attribute

    member_closure = member.__closure__ or ()
    reference_closure = reference.__closure__ or ()
    assert len(member_closure) == len(reference_closure)
    for member_cell, reference_cell in zip(
        member_closure,
        reference_closure,
        strict=True,
    ):
        member_value = member_cell.cell_contents
        reference_value = reference_cell.cell_contents
        if reference_value is reference_owner:
            assert member_value is owner
        elif inspect.isfunction(reference_value):
            _assert_generated_special_matches(
                member_value,
                reference_value,
                owner=owner,
                reference_owner=reference_owner,
            )
        elif (
            inspect.isclass(reference_value)
            and type(reference_value) is type
            and reference_value.__name__ == reference_owner.__name__
            and reference_value is not reference_owner
        ):
            assert inspect.isclass(member_value) and type(member_value) is type
            assert member_value is not owner
            assert member_value.__name__ == owner.__name__
            assert member_value.__module__ == owner.__module__
            assert member_value.__qualname__ == owner.__qualname__
            assert inspect.getmro(member_value) == (member_value, object)
        elif type(reference_value) is set:
            assert (
                type(member_value) is set and not member_value and not reference_value
            )
        elif reference_value is None or any(
            type(reference_value) is allowed
            for allowed in (bool, bytes, complex, float, int, str)
        ):
            assert type(member_value) is type(reference_value)
            assert member_value == reference_value
        else:
            assert member_value is reference_value


def _assert_passive_dataclass_metadata(
    value_type: type[object],
    expected_shape: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Pin dataclass metadata before any helper or descriptor is allowed to read it."""
    assert type(value_type) is type, "dataclass has a custom metaclass"
    namespace = vars(value_type)
    assert type(namespace["__module__"]) is str
    assert type(value_type.__qualname__) is str
    assert namespace.get("__doc__") is None or type(namespace["__doc__"]) is str, (
        "dataclass documentation retains a capability"
    )
    assert "__classcell__" not in namespace
    assert "__dict__" not in namespace and "__weakref__" not in namespace
    if "__firstlineno__" in namespace:
        assert type(namespace["__firstlineno__"]) is int
    if "__static_attributes__" in namespace:
        static_attributes = namespace["__static_attributes__"]
        assert type(static_attributes) is tuple
        assert all(type(name) is str for name in static_attributes)

    annotations = namespace.get("__annotations__")
    assert type(annotations) is dict, "dataclass annotations are not an exact dict"
    assert all(type(name) is str for name in annotations)
    assert all(type(annotation) is str for annotation in annotations.values()), (
        "dataclass annotation retains a capability"
    )

    raw_fields = namespace.get("__dataclass_fields__")
    assert type(raw_fields) is dict, "dataclass field metadata is not an exact dict"
    field_names = tuple(raw_fields)
    if expected_shape is not None:
        assert field_names == expected_shape, "passive value field inventory changed"
    assert tuple(annotations) == field_names, "dataclass annotation inventory changed"
    for name, retained in raw_fields.items():
        assert type(retained) is _PASSIVE_FIELD_METADATA_TYPE
        assert object.__getattribute__(retained, "name") == name
        assert type(object.__getattribute__(retained, "type")) is str, (
            "dataclass field annotation retains a capability"
        )
        assert object.__getattribute__(retained, "default") is MISSING
        assert object.__getattribute__(retained, "default_factory") is MISSING
        assert object.__getattribute__(retained, "repr") is True
        assert object.__getattribute__(retained, "hash") is None
        assert object.__getattribute__(retained, "init") is True
        assert object.__getattribute__(retained, "compare") is True
        assert object.__getattribute__(retained, "kw_only") is False
        assert object.__getattribute__(retained, "_field_type") is _PASSIVE_FIELD_KIND
        metadata = object.__getattribute__(retained, "metadata")
        assert type(metadata) is _PASSIVE_FIELD_METADATA_MAPPING_TYPE and not metadata

    params = namespace.get("__dataclass_params__")
    assert type(params) is _PASSIVE_PARAMS_TYPE, (
        "dataclass parameters are not interpreter-owned metadata"
    )
    parameter_names = type(params).__slots__
    assert type(parameter_names) is tuple
    parameter_values = {
        name: object.__getattribute__(params, name) for name in parameter_names
    }
    assert all(type(value) is bool for value in parameter_values.values())
    assert parameter_values["frozen"] is True
    for name, expected in {
        "repr": True,
        "eq": True,
        "order": False,
        "unsafe_hash": False,
        "slots": True,
        "match_args": True,
        "kw_only": False,
        "weakref_slot": False,
    }.items():
        if name in parameter_values:
            assert parameter_values[name] is expected, (
                f"unsafe dataclass parameter: {name}"
            )
    assert type(parameter_values["init"]) is bool

    slots = namespace.get("__slots__")
    assert type(slots) is tuple and slots == field_names
    match_args = namespace.get("__match_args__")
    assert type(match_args) is tuple and match_args == field_names

    reference_namespace: dict[str, object] = {}
    if "__post_init__" in namespace:

        def __post_init__(_self: object) -> None:
            return None

        reference_namespace["__post_init__"] = __post_init__
    reference_type = make_dataclass(
        "_PassiveDataclassReference",
        [(name, object) for name in field_names],
        namespace=reference_namespace,
        init=parameter_values["init"],
        repr=True,
        eq=True,
        order=False,
        unsafe_hash=False,
        frozen=True,
        match_args=True,
        kw_only=False,
        slots=True,
        weakref_slot=False,
    )
    reference_members = vars(reference_type)
    for name in _DATACLASS_GENERATED_SPECIALS:
        reference = reference_members.get(name)
        if reference is None:
            continue
        member = namespace.get(name)
        assert member is not None, f"missing dataclass generated behavior: {name}"
        _assert_generated_special_matches(
            member,
            reference,
            owner=value_type,
            reference_owner=reference_type,
        )
    return field_names


def _assert_passive_slot_descriptors(
    value_type: type[object],
    field_names: tuple[str, ...] | None = None,
) -> None:
    """Pin every dataclass field to its original inert slot descriptor."""
    namespace = vars(value_type)
    if field_names is None:
        raw_fields = namespace.get("__dataclass_fields__")
        assert type(raw_fields) is dict
        field_names = tuple(raw_fields)
    for name in field_names:
        descriptor = namespace.get(name)
        assert type(descriptor) is _PASSIVE_SLOT_DESCRIPTOR_TYPE, (
            f"dataclass field descriptor changed: {name}"
        )
        assert descriptor.__objclass__ is value_type
        assert descriptor.__name__ == name


def _retained_behavior_names(value_type: type[object]) -> set[str]:
    """Return every member outside exact passive dataclass fields and machinery."""
    behavior_names: set[str] = set()
    raw_fields = vars(value_type).get("__dataclass_fields__")
    retained_names = set(raw_fields) if type(raw_fields) is dict else set()
    if type(value_type) is not type:
        behavior_names.add("<custom-metaclass>")
    for base in inspect.getmro(value_type):
        if base is object:
            continue
        for name, member in vars(base).items():
            if base is value_type and name in retained_names:
                continue
            if name in _DATACLASS_METADATA_SPECIALS:
                continue
            if base is value_type and name in _DATACLASS_GENERATED_SPECIALS:
                params = vars(value_type).get("__dataclass_params__")
                if (
                    name == "__init__"
                    and type(params) is _PASSIVE_PARAMS_TYPE
                    and object.__getattribute__(params, "init") is False
                ):
                    behavior_names.add(name)
                continue
            inspect.getattr_static(value_type, name)
            behavior_names.add(name)
    return behavior_names


def _lifecycle_attribute_path(node: ast.AST) -> tuple[str, ...] | None:
    if isinstance(node, ast.Name):
        return (node.id,)
    if not isinstance(node, ast.Attribute):
        return None
    prefix = _lifecycle_attribute_path(node.value)
    return None if prefix is None else prefix + (node.attr,)


def _lifecycle_value_path(
    node: ast.AST,
    field_names: frozenset[str],
    guarded_types: dict[tuple[str, ...], type[object]],
) -> tuple[str, ...] | None:
    path = _lifecycle_attribute_path(node)
    if path is None or len(path) < 2 or path[:1] != ("self",):
        return None
    if len(path) == 2 and path[1] in field_names:
        return path
    parent_type = guarded_types.get(path[:-1])
    if parent_type is None:
        return None
    descriptor = vars(parent_type).get(path[-1])
    if (
        type(descriptor) is _PASSIVE_SLOT_DESCRIPTOR_TYPE
        and descriptor.__objclass__ is parent_type
        and descriptor.__name__ == path[-1]
    ):
        return path
    return None


def _resolve_lifecycle_name(lifecycle: Callable[..., object], name: str) -> object:
    if name in lifecycle.__globals__:
        return lifecycle.__globals__[name]
    retained_builtins = lifecycle.__globals__.get("__builtins__", builtins)
    if retained_builtins is builtins:
        return getattr(builtins, name, None)
    assert type(retained_builtins) is dict, "lifecycle builtins source changed"
    return retained_builtins.get(name)


def _assert_lifecycle_builtin(
    lifecycle: Callable[..., object],
    name: str,
    expected: object,
) -> None:
    assert _resolve_lifecycle_name(lifecycle, name) is expected, (
        f"shadowed lifecycle builtin: {name}"
    )


def _assert_guarded_lifecycle_type_is_passive(
    value_type: type[object],
) -> None:
    """Reject nested exact-type guards whose attribute reads can execute code."""
    trusted_bases = (object, bool, bytes, int, str, Decimal, Fraction, type(None), Enum)
    for base in inspect.getmro(value_type):
        if any(base is trusted for trusted in trusted_bases):
            continue
        namespace = vars(base)
        assert namespace.get("__getattribute__", object.__getattribute__) is (
            object.__getattribute__
        ), f"guarded lifecycle type has custom attribute access: {value_type.__name__}"
        assert "__getattr__" not in namespace, (
            f"guarded lifecycle type has custom attribute access: {value_type.__name__}"
        )


def _lifecycle_global_type(
    lifecycle: Callable[..., object],
    name: str,
) -> type[object]:
    candidate = _resolve_lifecycle_name(lifecycle, name)
    assert inspect.isclass(candidate), f"lifecycle type target is not a class: {name}"
    assert any(
        type(candidate) is allowed for allowed in (type, type(Enum), type(Fraction))
    ), f"lifecycle type target has a custom metaclass: {name}"
    _assert_guarded_lifecycle_type_is_passive(candidate)
    module_name = candidate.__module__
    assert type(module_name) is str, "lifecycle type module is not exact text"
    assert module_name in {"builtins", "decimal", "enum", "fractions"} or (
        module_name.startswith("app.execution_core")
    ), f"unapproved lifecycle type target: {name}"
    return candidate


def _is_lifecycle_enum_member(
    lifecycle: Callable[..., object],
    node: ast.AST,
) -> bool:
    path = _lifecycle_attribute_path(node)
    if path is None or len(path) != 2:
        return False
    enum_type = _resolve_lifecycle_name(lifecycle, path[0])
    if not inspect.isclass(enum_type) or type(enum_type) is not type(Enum):
        return False
    members = vars(enum_type).get("_member_map_")
    return type(members) is dict and path[1] in members


def _lifecycle_type_guard(
    node: ast.AST,
    *,
    lifecycle: Callable[..., object],
    field_names: frozenset[str],
    guarded_types: dict[tuple[str, ...], type[object]],
) -> tuple[tuple[str, ...], type[object], ast.cmpop] | None:
    if not (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], (ast.Is, ast.IsNot))
        and len(node.comparators) == 1
        and isinstance(node.left, ast.Call)
        and isinstance(node.left.func, ast.Name)
        and node.left.func.id == "type"
        and len(node.left.args) == 1
        and not node.left.keywords
        and isinstance(node.comparators[0], ast.Name)
    ):
        return None
    _assert_lifecycle_builtin(lifecycle, "type", builtins.type)
    path = _lifecycle_value_path(
        node.left.args[0],
        field_names,
        guarded_types,
    )
    assert path is not None, "lifecycle type guard targets an unaudited value"
    expected_type = _lifecycle_global_type(lifecycle, node.comparators[0].id)
    return path, expected_type, node.ops[0]


def _lifecycle_safe_call_result_type(
    node: ast.Call,
    *,
    lifecycle: Callable[..., object],
    field_names: frozenset[str],
    guarded_types: dict[tuple[str, ...], type[object]],
) -> type[object]:
    if isinstance(node.func, ast.Name) and node.func.id == "len":
        _assert_lifecycle_builtin(lifecycle, "len", builtins.len)
        assert len(node.args) == 1 and not node.keywords
        path = _lifecycle_value_path(node.args[0], field_names, guarded_types)
        retained_type = None if path is None else guarded_types.get(path)
        assert path is not None and (retained_type is bytes or retained_type is str), (
            "lifecycle len requires a prior exact bytes or str guard"
        )
        return int
    if isinstance(node.func, ast.Attribute) and node.func.attr == "strip":
        assert not node.args and not node.keywords
        path = _lifecycle_value_path(node.func.value, field_names, guarded_types)
        assert path is not None and guarded_types.get(path) is str, (
            "lifecycle strip requires a prior exact str guard"
        )
        return str
    raise AssertionError(
        f"unapproved lifecycle call: {_lifecycle_attribute_path(node.func)!r}"
    )


def _assert_lifecycle_operand(
    node: ast.AST,
    *,
    lifecycle: Callable[..., object],
    field_names: frozenset[str],
    guarded_types: dict[tuple[str, ...], type[object]],
    protocol_comparison: bool,
) -> None:
    if isinstance(node, ast.Constant):
        assert any(
            type(node.value) is allowed
            for allowed in (bool, bytes, int, str, type(None))
        ), "unsupported lifecycle constant"
        return
    path = _lifecycle_value_path(node, field_names, guarded_types)
    if path is not None:
        if protocol_comparison:
            retained_type = guarded_types.get(path)
            assert any(
                retained_type is allowed
                for allowed in (bool, bytes, int, str, Decimal, Fraction)
            ), "lifecycle comparison lacks a prior exact scalar guard"
        return
    if _is_lifecycle_enum_member(lifecycle, node):
        assert not protocol_comparison, (
            "enum lifecycle validation must use identity comparison"
        )
        return
    if isinstance(node, ast.Call):
        _lifecycle_safe_call_result_type(
            node,
            lifecycle=lifecycle,
            field_names=field_names,
            guarded_types=guarded_types,
        )
        return
    raise AssertionError("unsupported lifecycle comparison operand")


def _assert_passive_lifecycle_test(
    node: ast.AST,
    *,
    lifecycle: Callable[..., object],
    field_names: frozenset[str],
    guarded_types: dict[tuple[str, ...], type[object]],
) -> None:
    """Accept only identity tests and guarded exact-scalar validation."""
    if (
        _lifecycle_type_guard(
            node,
            lifecycle=lifecycle,
            field_names=field_names,
            guarded_types=guarded_types,
        )
        is not None
    ):
        return
    if isinstance(node, ast.BoolOp):
        assert isinstance(node.op, (ast.And, ast.Or))
        for value in node.values:
            _assert_passive_lifecycle_test(
                value,
                lifecycle=lifecycle,
                field_names=field_names,
                guarded_types=guarded_types,
            )
        return
    if isinstance(node, ast.UnaryOp):
        assert isinstance(node.op, ast.Not), "unsupported lifecycle unary operator"
        _assert_passive_lifecycle_test(
            node.operand,
            lifecycle=lifecycle,
            field_names=field_names,
            guarded_types=guarded_types,
        )
        return
    if isinstance(node, ast.Compare):
        assert all(
            isinstance(
                operator,
                (
                    ast.Is,
                    ast.IsNot,
                    ast.Eq,
                    ast.NotEq,
                    ast.Lt,
                    ast.LtE,
                    ast.Gt,
                    ast.GtE,
                ),
            )
            for operator in node.ops
        ), "unsupported lifecycle comparison"
        protocol_comparison = any(
            not isinstance(operator, (ast.Is, ast.IsNot)) for operator in node.ops
        )
        for operand in (node.left, *node.comparators):
            _assert_lifecycle_operand(
                operand,
                lifecycle=lifecycle,
                field_names=field_names,
                guarded_types=guarded_types,
                protocol_comparison=protocol_comparison,
            )
        return
    if isinstance(node, ast.Call):
        _lifecycle_safe_call_result_type(
            node,
            lifecycle=lifecycle,
            field_names=field_names,
            guarded_types=guarded_types,
        )
        return
    if isinstance(node, ast.Constant):
        assert type(node.value) is bool, "lifecycle truth test is not boolean"
        return
    path = _lifecycle_value_path(node, field_names, guarded_types)
    retained_type = None if path is None else guarded_types.get(path)
    assert path is not None and any(
        retained_type is allowed for allowed in (bool, bytes, int, str)
    ), "lifecycle truth test lacks a prior exact scalar guard"


def _assert_lifecycle_raise(
    node: ast.Raise,
    *,
    lifecycle: Callable[..., object],
    error_names: tuple[str, ...] = ("TypeError", "ValueError"),
) -> None:
    assert isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name), (
        "lifecycle raises a nonlocal value"
    )
    assert node.exc.func.id in error_names
    expected = getattr(builtins, node.exc.func.id)
    _assert_lifecycle_builtin(lifecycle, node.exc.func.id, expected)
    assert (
        len(node.exc.args) == 1
        and isinstance(node.exc.args[0], ast.Constant)
        and type(node.exc.args[0].value) is str
        and not node.exc.keywords
    ), "lifecycle errors require one constant message"
    assert node.cause is None or (
        isinstance(node.cause, ast.Constant) and node.cause.value is None
    )


def _assert_passive_post_init_statements(
    statements: list[ast.stmt],
    *,
    lifecycle: Callable[..., object],
    field_names: frozenset[str],
    guarded_types: dict[tuple[str, ...], type[object]],
) -> None:
    retained_guards = dict(guarded_types)
    for statement in statements:
        if isinstance(statement, ast.If):
            guard = _lifecycle_type_guard(
                statement.test,
                lifecycle=lifecycle,
                field_names=field_names,
                guarded_types=retained_guards,
            )
            _assert_passive_lifecycle_test(
                statement.test,
                lifecycle=lifecycle,
                field_names=field_names,
                guarded_types=retained_guards,
            )
            if (
                guard is not None
                and isinstance(guard[2], ast.IsNot)
                and len(statement.body) == 1
                and isinstance(statement.body[0], ast.Raise)
                and not statement.orelse
            ):
                _assert_lifecycle_raise(statement.body[0], lifecycle=lifecycle)
                retained_guards[guard[0]] = guard[1]
                continue
            body_guards = dict(retained_guards)
            else_guards = dict(retained_guards)
            if guard is not None:
                target = body_guards if isinstance(guard[2], ast.Is) else else_guards
                target[guard[0]] = guard[1]
            _assert_passive_post_init_statements(
                statement.body,
                lifecycle=lifecycle,
                field_names=field_names,
                guarded_types=body_guards,
            )
            _assert_passive_post_init_statements(
                statement.orelse,
                lifecycle=lifecycle,
                field_names=field_names,
                guarded_types=else_guards,
            )
        elif isinstance(statement, ast.Raise):
            _assert_lifecycle_raise(statement, lifecycle=lifecycle)
        elif isinstance(statement, ast.Return):
            assert statement.value is None or (
                isinstance(statement.value, ast.Constant)
                and statement.value.value is None
            ), "lifecycle returns a capability"
        elif isinstance(statement, ast.Expr):
            assert (
                isinstance(statement.value, ast.Constant)
                and type(statement.value.value) is str
            ), "lifecycle expression is not a docstring"
        else:
            assert isinstance(statement, ast.Pass), (
                f"unsupported lifecycle statement: {type(statement).__name__}"
            )


def _assert_lifecycle_function_metadata(
    lifecycle: Callable[..., object],
    function: ast.FunctionDef,
    owner_module: ModuleType,
    source: str,
) -> None:
    assert lifecycle.__globals__ is vars(owner_module)
    assert lifecycle.__module__ == owner_module.__name__
    assert lifecycle.__defaults__ is None
    assert lifecycle.__kwdefaults__ is None
    assert lifecycle.__closure__ is None and not lifecycle.__code__.co_freevars
    assert type(lifecycle.__dict__) is dict and not lifecycle.__dict__
    assert not function.decorator_list, "decorated lifecycle is forbidden"
    annotations = lifecycle.__annotations__
    assert type(annotations) is dict
    assert all(type(name) is str for name in annotations), (
        "lifecycle annotation name is not exact text"
    )
    assert set(annotations) <= {
        argument.arg
        for argument in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
            *((function.args.vararg,) if function.args.vararg is not None else ()),
            *((function.args.kwarg,) if function.args.kwarg is not None else ()),
        )
    } | {"return"}
    assert all(
        type(value) is str or value is None or value is type(None) or value is object
        for value in annotations.values()
    ), "lifecycle annotation retains a capability"
    _assert_function_matches_inspected_source(
        lifecycle,
        source,
        message="lifecycle bytecode does not match inspected source",
    )


def _assert_opaque_lifecycle(
    name: str,
    lifecycle: Callable[..., object],
    function: ast.FunctionDef,
) -> None:
    positional = (*function.args.posonlyargs, *function.args.args)
    assert len(positional) == 1 and not function.args.posonlyargs
    assert not function.args.kwonlyargs
    assert not function.args.defaults and not function.args.kw_defaults
    if name == "__init__":
        assert function.args.vararg is not None and function.args.kwarg is not None
    else:
        assert function.args.vararg is None and function.args.kwarg is not None
    local_names = {
        positional[0].arg,
        *((function.args.vararg.arg,) if function.args.vararg is not None else ()),
        function.args.kwarg.arg,
    }
    statements = list(function.body)
    if statements and isinstance(statements[0], ast.Expr):
        assert (
            isinstance(statements[0].value, ast.Constant)
            and type(statements[0].value.value) is str
        )
        statements.pop(0)
    assert statements and len(statements) <= 2
    if len(statements) == 2:
        deletion = statements[0]
        assert isinstance(deletion, ast.Delete)
        assert all(
            isinstance(target, ast.Name) and target.id in local_names
            for target in deletion.targets
        ), "opaque lifecycle deletes external state"
    terminal = statements[-1]
    assert isinstance(terminal, ast.Raise)
    _assert_lifecycle_raise(
        terminal,
        lifecycle=lifecycle,
        error_names=("TypeError",),
    )


def _assert_passive_lifecycle(
    value_type: type[object],
    owner_module: ModuleType,
) -> None:
    """Constrain lifecycle code to exact opaque or sequential validation forms."""
    field_names = _assert_passive_dataclass_metadata(value_type)
    _assert_passive_slot_descriptors(value_type, field_names)
    for name in _retained_behavior_names(value_type) & _DATACLASS_LIFECYCLE_SPECIALS:
        raw_lifecycle = inspect.getattr_static(value_type, name)
        if name == "__init_subclass__":
            assert isinstance(raw_lifecycle, classmethod)
            lifecycle = raw_lifecycle.__func__
        else:
            assert inspect.isfunction(raw_lifecycle)
            lifecycle = raw_lifecycle
        assert inspect.isfunction(lifecycle), f"{name} is not an exact function"
        source = textwrap.dedent(inspect.getsource(lifecycle))
        tree = ast.parse(source)
        functions = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert len(functions) == 1
        function = functions[0]
        assert isinstance(function, ast.FunctionDef), "async lifecycle is forbidden"
        _assert_lifecycle_function_metadata(lifecycle, function, owner_module, source)
        if name in {"__init__", "__init_subclass__"}:
            _assert_opaque_lifecycle(name, lifecycle, function)
            continue
        assert not function.args.posonlyargs
        assert tuple(argument.arg for argument in function.args.args) == ("self",)
        assert function.args.vararg is None and function.args.kwarg is None
        assert not function.args.kwonlyargs
        assert not function.args.defaults and not function.args.kw_defaults
        _assert_passive_post_init_statements(
            function.body,
            lifecycle=lifecycle,
            field_names=frozenset(field_names),
            guarded_types={},
        )


def _assert_passive_value_graph(
    value: object,
    *,
    allowed_shapes: dict[type[object], tuple[str, ...]],
    trusted_leaf_types: frozenset[type[object]] = frozenset(),
    allowed_enum_shapes: dict[type[Enum], tuple[str, ...]] | None = None,
) -> None:
    """Seal every retained field, slot, lifecycle, and nested value type."""
    pending = [value]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        current_type = type(current)
        if current is None or any(
            current_type is allowed
            for allowed in (bool, bytes, int, str, Decimal, Fraction)
        ):
            continue
        if any(current_type is trusted for trusted in trusted_leaf_types):
            _assert_guarded_lifecycle_type_is_passive(current_type)
            continue
        enum_shape = (
            None
            if allowed_enum_shapes is None
            else next(
                (
                    shape
                    for enum_type, shape in allowed_enum_shapes.items()
                    if current_type is enum_type
                ),
                None,
            )
        )
        if enum_shape is not None:
            _assert_passive_enum_type(
                current_type,
                enum_shape,
            )
            continue
        assert type(current_type) is type, (
            f"passive value retains a custom metaclass: {current_type.__name__}"
        )
        if current_type is tuple or current_type is frozenset:
            pending.extend(current)
            continue
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        assert not callable(current), (
            f"passive value retains callable capability: {type(current).__name__}"
        )
        expected_shape = next(
            (
                shape
                for allowed_type, shape in allowed_shapes.items()
                if current_type is allowed_type
            ),
            None,
        )
        assert expected_shape is not None, (
            f"passive value retains unapproved dataclass or capability type: "
            f"{current_type.__name__}"
        )
        assert inspect.getmro(current_type) == (current_type, object)
        actual_fields = _assert_passive_dataclass_metadata(
            current_type,
            expected_shape,
        )
        _assert_passive_slot_descriptors(current_type, actual_fields)
        behavior = _retained_behavior_names(current_type)
        assert behavior <= _DATACLASS_LIFECYCLE_SPECIALS, (
            f"passive value retains behavior: {sorted(behavior)!r}"
        )
        owner_module = inspect.getmodule(current_type)
        assert owner_module is not None
        _assert_passive_lifecycle(current_type, owner_module)
        pending.extend(object.__getattribute__(current, name) for name in actual_fields)


_CONSTANT_WORK_ALLOWED_EXTERNAL_CALLS = frozenset(
    {
        "TypeError",
        "ValueError",
        "_commit_parts",
        "_encode_text",
        "bool",
        "bytes",
        "cast",
        "int",
        "isinstance",
        "len",
        "str",
        "type",
    }
)


def _constant_work_call_graph(
    root: Callable[..., object],
    owner_module: ModuleType,
) -> tuple[dict[str, ast.AST], dict[str, set[str]], set[str]]:
    """Resolve every direct/global helper and reject unresolved callable aliases."""
    pending = [root]
    scanned: dict[str, ast.AST] = {}
    call_graph: dict[str, set[str]] = {}
    unresolved: set[str] = set()
    while pending:
        current = pending.pop()
        current_name = current.__name__
        if current_name in scanned:
            continue
        tree = ast.parse(textwrap.dedent(inspect.getsource(current)))
        scanned[current_name] = tree
        call_graph[current_name] = set()
        function_node = next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
        local_bindings = {
            argument.arg
            for argument in (
                *function_node.args.posonlyargs,
                *function_node.args.args,
                *function_node.args.kwonlyargs,
            )
        }
        if function_node.args.vararg is not None:
            local_bindings.add(function_node.args.vararg.arg)
        if function_node.args.kwarg is not None:
            local_bindings.add(function_node.args.kwarg.arg)
        local_bindings.update(
            node.id
            for node in ast.walk(function_node)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        )
        local_bindings.update(
            node.name
            for node in ast.walk(function_node)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node is not function_node
        )
        free_bindings = set(current.__code__.co_freevars)
        local_calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        for called_name in local_calls:
            candidate = vars(owner_module).get(called_name)
            if called_name in local_bindings or called_name in free_bindings:
                unresolved.add(called_name)
            elif (
                inspect.isfunction(candidate)
                and candidate.__module__ == owner_module.__name__
            ):
                candidate_name = candidate.__name__
                call_graph[current_name].add(candidate_name)
                pending.append(candidate)
            elif called_name in _CONSTANT_WORK_ALLOWED_EXTERNAL_CALLS and (
                candidate is None
                or (
                    inspect.isfunction(candidate)
                    and candidate.__module__ in {"app.execution_core.fills", "typing"}
                )
            ):
                continue
            else:
                unresolved.add(called_name)
    return scanned, call_graph, unresolved


def _raw_ledger_scan_mutant(book: object) -> object:
    return tuple(book._input_ledger)


def _local_alias_scan_mutant(book: object) -> object:
    scan = _raw_ledger_scan_mutant
    return scan(book)


def _default_alias_scan_mutant(
    book: object,
    scan: Callable[[object], object] = _raw_ledger_scan_mutant,
) -> object:
    return scan(book)


class _CallableScanMutant:
    def __call__(self, book: object) -> object:
        return tuple(book._input_ledger)


_CALLABLE_SCAN_MUTANT = _CallableScanMutant()


def _callable_object_scan_mutant(book: object) -> object:
    return _CALLABLE_SCAN_MUTANT(book)


_GLOBAL_ALIAS_SCAN_MUTANT = _raw_ledger_scan_mutant


def _global_alias_scan_mutant(book: object) -> object:
    return _GLOBAL_ALIAS_SCAN_MUTANT(book)


def _make_closure_scan_mutant() -> Callable[[object], object]:
    scan = _raw_ledger_scan_mutant

    def closure_scan_mutant(book: object) -> object:
        return scan(book)

    return closure_scan_mutant


_CLOSURE_SCAN_MUTANT = _make_closure_scan_mutant()


class _SlowGetter:
    def get(self, book: object) -> object:
        return tuple(book._input_ledger)


_SLOW_GETTER = _SlowGetter()


def _hidden_get_scan_mutant(book: object) -> object:
    return _SLOW_GETTER.get(book)


@dataclass(frozen=True, slots=True)
class _BoundedMapLookalikeProxy:
    _authority_summary_by_scope: object


_BOUNDED_MAP_LOOKALIKE = _BoundedMapLookalikeProxy(
    _authority_summary_by_scope=_SLOW_GETTER
)


def _lookalike_field_get_scan_mutant(book: object) -> object:
    return _BOUNDED_MAP_LOOKALIKE._authority_summary_by_scope.get(book)


@dataclass(frozen=True, slots=True)
class _ExactShapeLookalikeProof:
    position_scope: object


@dataclass(frozen=True, slots=True)
class _ExactShapeLookalikeBook:
    _authority_summary_by_scope: object
    _binding_by_scope: object
    _protection_cursor_by_scope: object


@dataclass(frozen=True, slots=True)
class _ExactShapeLookalikeTransition:
    book: _ExactShapeLookalikeBook
    _protection_proof: _ExactShapeLookalikeProof


class _LedgerTripwire:
    @property
    def _input_ledger(self) -> object:
        raise AssertionError("lookalike get reached a private venue ledger")


_EXACT_SHAPE_LOOKALIKE_TRANSITION = _ExactShapeLookalikeTransition(
    book=_ExactShapeLookalikeBook(
        _authority_summary_by_scope=_SLOW_GETTER,
        _binding_by_scope=_SLOW_GETTER,
        _protection_cursor_by_scope=_SLOW_GETTER,
    ),
    _protection_proof=_ExactShapeLookalikeProof(position_scope=_LedgerTripwire()),
)


def _position_scope_index_key(position_scope: object) -> object:
    """Test-only spelling twin for exact-shape receiver mutants."""
    return position_scope


def _make_rebound_exact_shape_get_mutant() -> Callable[[object], object]:
    def _extract_protection_transition(transition: object) -> object:
        transition = _EXACT_SHAPE_LOOKALIKE_TRANSITION
        return (
            transition.book._authority_summary_by_scope.get(
                _position_scope_index_key(transition._protection_proof.position_scope)
            ),
            transition.book._binding_by_scope.get(
                _position_scope_index_key(transition._protection_proof.position_scope)
            ),
            transition.book._protection_cursor_by_scope.get(
                _position_scope_index_key(transition._protection_proof.position_scope)
            ),
        )

    return _extract_protection_transition


def _make_extra_exact_shape_get_mutant() -> Callable[[object], object]:
    def _extract_protection_transition(transition: object) -> object:
        return (
            transition.book._authority_summary_by_scope.get(
                _position_scope_index_key(transition._protection_proof.position_scope)
            ),
            transition.book._binding_by_scope.get(
                _position_scope_index_key(transition._protection_proof.position_scope)
            ),
            transition.book._protection_cursor_by_scope.get(
                _position_scope_index_key(transition._protection_proof.position_scope)
            ),
            transition.book._authority_summary_by_scope.get(
                _position_scope_index_key(transition._protection_proof.position_scope)
            ),
        )

    return _extract_protection_transition


_REBOUND_EXACT_SHAPE_GET_MUTANT = _make_rebound_exact_shape_get_mutant()
_EXTRA_EXACT_SHAPE_GET_MUTANT = _make_extra_exact_shape_get_mutant()


class _BenignBoundedGetter:
    def get(self, _key: object) -> None:
        return None


class _DescriptorLedgerTripwire:
    def __iter__(self) -> object:
        raise AssertionError("descriptor reached a private venue ledger")


@dataclass(frozen=True, slots=True)
class _DescriptorSlowBook:
    _authority_summary_by_scope: object
    _binding_by_scope: object
    _protection_cursor_by_scope: object
    _input_ledger: object

    @property
    def _slow_summary(self) -> object:
        return tuple(self._input_ledger)


@dataclass(frozen=True, slots=True)
class _DescriptorSlowTransition:
    book: _DescriptorSlowBook
    _protection_proof: _ExactShapeLookalikeProof


_DESCRIPTOR_SLOW_TRANSITION = _DescriptorSlowTransition(
    book=_DescriptorSlowBook(
        _authority_summary_by_scope=_BenignBoundedGetter(),
        _binding_by_scope=_BenignBoundedGetter(),
        _protection_cursor_by_scope=_BenignBoundedGetter(),
        _input_ledger=_DescriptorLedgerTripwire(),
    ),
    _protection_proof=_ExactShapeLookalikeProof(position_scope=object()),
)


def _make_descriptor_slow_scan_mutant() -> Callable[[object], object]:
    def _extract_protection_transition(transition: object) -> object:
        authority = transition.book._authority_summary_by_scope.get(
            _position_scope_index_key(transition._protection_proof.position_scope)
        )
        binding = transition.book._binding_by_scope.get(
            _position_scope_index_key(transition._protection_proof.position_scope)
        )
        cursor = transition.book._protection_cursor_by_scope.get(
            _position_scope_index_key(transition._protection_proof.position_scope)
        )
        return authority, binding, cursor, transition.book._slow_summary

    return _extract_protection_transition


_DESCRIPTOR_SLOW_SCAN_MUTANT = _make_descriptor_slow_scan_mutant()


def _make_exact_leaf_extractor_probe() -> Callable[[object], object]:
    def _extract_protection_transition(transition: object) -> object:
        scope_key = _position_scope_index_key(
            transition._protection_proof.position_scope
        )
        return (
            transition.book._authority_summary_by_scope.get(scope_key),
            transition.book._binding_by_scope.get(scope_key),
            transition.book._protection_cursor_by_scope.get(scope_key),
        )

    return _extract_protection_transition


def _transition_descriptor_helper(candidate: object) -> object:
    return candidate.book._slow_summary


def _make_helper_escape_mutant() -> Callable[[object], object]:
    def _extract_protection_transition(transition: object) -> object:
        scope_key = _position_scope_index_key(
            transition._protection_proof.position_scope
        )
        _transition_descriptor_helper(transition)
        return (
            transition.book._authority_summary_by_scope.get(scope_key),
            transition.book._binding_by_scope.get(scope_key),
            transition.book._protection_cursor_by_scope.get(scope_key),
        )

    return _extract_protection_transition


def _make_wrapped_receiver_mutant() -> Callable[[object], object]:
    def _extract_protection_transition(transition: object) -> object:
        wrapped = (transition,)[0]
        scope_key = _position_scope_index_key(wrapped._protection_proof.position_scope)
        return (
            wrapped.book._authority_summary_by_scope.get(scope_key),
            wrapped.book._binding_by_scope.get(scope_key),
            wrapped.book._protection_cursor_by_scope.get(scope_key),
        )

    return _extract_protection_transition


def _make_aggregate_map_mutant() -> Callable[[object], object]:
    def _extract_protection_transition(transition: object) -> object:
        scope_key = _position_scope_index_key(
            transition._protection_proof.position_scope
        )
        bounded_maps = (
            transition.book._authority_summary_by_scope,
            transition.book._binding_by_scope,
            transition.book._protection_cursor_by_scope,
        )
        return tuple(bounded_map.get(scope_key) for bounded_map in bounded_maps)

    return _extract_protection_transition


_EXACT_LEAF_EXTRACTOR_PROBE = _make_exact_leaf_extractor_probe()
_HELPER_ESCAPE_MUTANT = _make_helper_escape_mutant()
_WRAPPED_RECEIVER_MUTANT = _make_wrapped_receiver_mutant()
_AGGREGATE_MAP_MUTANT = _make_aggregate_map_mutant()


_BOUNDED_PROTECTION_MAP_FIELD_ORDER = (
    "_authority_summary_by_scope",
    "_binding_by_scope",
    "_protection_cursor_by_scope",
)
_BOUNDED_PROTECTION_MAP_FIELDS = frozenset(_BOUNDED_PROTECTION_MAP_FIELD_ORDER)


def _attribute_path(node: ast.AST) -> tuple[str, ...] | None:
    if isinstance(node, ast.Name):
        return (node.id,)
    if not isinstance(node, ast.Attribute):
        return None
    prefix = _attribute_path(node.value)
    return None if prefix is None else prefix + (node.attr,)


def _persistent_map_provenance_violations(tree: ast.AST) -> set[str]:
    """Forbid venue-local aliases or mutation of the trusted bounded-map class."""
    violations: set[str] = set()
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    annotation_nodes: set[ast.AST] = set()
    for candidate in ast.walk(tree):
        annotation: ast.AST | None = None
        if isinstance(candidate, ast.arg):
            annotation = candidate.annotation
        elif isinstance(candidate, ast.AnnAssign):
            annotation = candidate.annotation
        elif isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef)):
            annotation = candidate.returns
        if annotation is not None:
            annotation_nodes.update(ast.walk(annotation))

    imports = []
    for candidate in ast.walk(tree):
        if not isinstance(candidate, ast.ImportFrom):
            continue
        for imported in candidate.names:
            if imported.name == "_PersistentKeyMap":
                imports.append((candidate, imported))
    if len(imports) != 1:
        violations.add("persistent-map-import-count")
    for statement, imported in imports:
        if (
            statement.level != 1
            or statement.module != "fills"
            or imported.asname is not None
        ):
            violations.add("persistent-map-import-provenance")

    for candidate in ast.walk(tree):
        if isinstance(candidate, ast.Import):
            for imported in candidate.names:
                if (
                    imported.name == "app.execution_core.fills"
                    or imported.name.endswith(".fills")
                ):
                    violations.add("persistent-map-owner-module-import")
        if isinstance(candidate, ast.ImportFrom):
            if candidate.level == 1 and candidate.module is None:
                if any(imported.name == "fills" for imported in candidate.names):
                    violations.add("persistent-map-owner-module-import")
            if any(imported.name == "_child_at" for imported in candidate.names):
                violations.add("persistent-map-dependency-import")
        if (
            isinstance(candidate, ast.Attribute)
            and candidate.attr == "_PersistentKeyMap"
        ):
            violations.add("qualified-persistent-map-access")
        if isinstance(candidate, ast.Attribute) and candidate.attr == "_child_at":
            violations.add("qualified-persistent-map-dependency-access")
        if (
            isinstance(candidate, ast.Constant)
            and candidate.value == "_PersistentKeyMap"
        ):
            violations.add("dynamic-persistent-map-name")
        if isinstance(candidate, ast.Constant) and candidate.value == "_child_at":
            violations.add("dynamic-persistent-map-dependency-name")
        if isinstance(candidate, ast.Name) and candidate.id == "_child_at":
            violations.add("persistent-map-dependency-capability-escape")
        if not isinstance(candidate, ast.Name) or candidate.id != "_PersistentKeyMap":
            continue
        if not isinstance(candidate.ctx, ast.Load):
            violations.add("persistent-map-rebind")
            continue
        if candidate in annotation_nodes:
            continue
        attribute = parents.get(candidate)
        if not (
            isinstance(attribute, ast.Attribute)
            and attribute.value is candidate
            and attribute.attr == "empty"
        ):
            violations.add("persistent-map-capability-escape")
            continue
        retained = parents.get(attribute)
        if isinstance(retained, ast.Call) and retained.func is attribute:
            continue
        if isinstance(retained, ast.keyword) and retained.arg == "default_factory":
            call = parents.get(retained)
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "field"
            ):
                continue
        violations.add("persistent-map-member-capture")
    return violations


def _is_exact_scope_key_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_position_scope_index_key"
        and len(node.args) == 1
        and not node.keywords
        and _attribute_path(node.args[0])
        == ("transition", "_protection_proof", "position_scope")
    )


def _exact_protection_map_get_field(node: ast.AST) -> str | None:
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and len(node.args) == 1
        and not node.keywords
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "scope_key"
        and isinstance(node.args[0].ctx, ast.Load)
    ):
        return None
    receiver = _attribute_path(node.func.value)
    if (
        receiver is None
        or receiver[:2] != ("transition", "book")
        or len(receiver) != 3
        or receiver[2] not in _BOUNDED_PROTECTION_MAP_FIELDS
    ):
        return None
    return receiver[2]


def _extractor_receiver_violations(scanned: dict[str, ast.AST]) -> set[str]:
    """Require the complete two-statement bounded extractor leaf grammar."""
    violations: set[str] = set()
    root = scanned.get("_extract_protection_transition")
    if root is None:
        return {"missing-extractor"}
    top_level_functions = [
        node
        for node in root.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if len(top_level_functions) != 1 or not isinstance(
        top_level_functions[0], ast.FunctionDef
    ):
        return {"extractor-shape"}
    function = top_level_functions[0]
    positional = (*function.args.posonlyargs, *function.args.args)
    if (
        function.name != "_extract_protection_transition"
        or function.decorator_list
        or function.args.posonlyargs
        or tuple(argument.arg for argument in positional) != ("transition",)
        or function.args.vararg is not None
        or function.args.kwarg is not None
        or function.args.kwonlyargs
        or function.args.defaults
        or function.args.kw_defaults
    ):
        violations.add("extractor-signature")
    statements = list(function.body)
    if statements and isinstance(statements[0], ast.Expr):
        docstring = statements[0].value
        if isinstance(docstring, ast.Constant) and type(docstring.value) is str:
            statements.pop(0)
    if len(statements) != 2:
        violations.add("extractor-leaf-statement-count")
        return violations

    assignment, terminal = statements
    if not (
        isinstance(assignment, ast.Assign)
        and len(assignment.targets) == 1
        and isinstance(assignment.targets[0], ast.Name)
        and assignment.targets[0].id == "scope_key"
        and _is_exact_scope_key_call(assignment.value)
    ):
        violations.add("scope-key-assignment")
    if not (
        isinstance(terminal, ast.Return)
        and isinstance(terminal.value, ast.Tuple)
        and len(terminal.value.elts) == 3
    ):
        violations.add("bounded-get-tuple")
        return violations

    exact_fields = tuple(
        _exact_protection_map_get_field(item) for item in terminal.value.elts
    )
    if exact_fields != _BOUNDED_PROTECTION_MAP_FIELD_ORDER:
        violations.add("bounded-get-field-order")
    return violations


def _disallowed_constant_work_method_calls(
    scanned: dict[str, ast.AST],
) -> set[str]:
    disallowed: set[str] = set()
    for function_name, tree in scanned.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            if (
                function_name == "_extract_protection_transition"
                and _exact_protection_map_get_field(node) is not None
            ):
                continue
            disallowed.add(node.func.attr)
    return disallowed


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


def _owned_fill_transition_for_scope(
    *,
    label: str,
    position_scope: PositionScope,
    quantity: int = 4,
    units: int = 100,
    tick_units: int = 1,
    scale: PriceScale = SCALE,
) -> tuple[object, EffectId, VenueLegKey]:
    book = VenueRecoveryBook.empty(VENUE_SCOPE)
    execution = ExecutionSnapshot.flat(position_scope)
    effect_id = EffectId(f"{label}-effect")
    leg_key = VenueLegKey(
        broker=position_scope.broker,
        environment=position_scope.environment,
        account=position_scope.account,
        order_id=OrderId(f"{label}-leg"),
    )
    commands = (
        RequestedEffect(
            input_id=VenueInputId(f"{label}-request-input"),
            effect_id=effect_id,
            request_occurrence_id=RequestOccurrenceId(f"{label}-request"),
            mandate_id=MANDATE_ID,
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId(f"{label}-client"),
            symbol_id=position_scope.symbol_id,
            side=ExecutionSide.BUY,
            quantity=Quantity(max(20, quantity)),
            economic_scope=f"{label}|fixed-capacity".encode(),
        ),
        RecordDispatchClaim(
            input_id=VenueInputId(f"{label}-claim-input"),
            effect_id=effect_id,
            claim_occurrence_id=ClaimOccurrenceId(f"{label}-claim"),
        ),
        RecordTransportOutcome(
            input_id=VenueInputId(f"{label}-unknown-input"),
            effect_id=effect_id,
            state=BrokerEffectState.OUTCOME_UNKNOWN,
        ),
        DiscoverVenueLeg(
            input_id=VenueInputId(f"{label}-discover-input"),
            effect_id=effect_id,
            leg_key=leg_key,
            observation_id=VenueObservationId(f"{label}-discover-observation"),
        ),
        ObserveVenueStatus(
            input_id=VenueInputId(f"{label}-review-input"),
            leg_key=leg_key,
            status=VenueAttemptState.NEEDS_REVIEW,
            observation_id=VenueObservationId(f"{label}-review-observation"),
            cumulative_quantity=Quantity(0),
        ),
        RecordTransportOutcome(
            input_id=VenueInputId(f"{label}-review-outcome-input"),
            effect_id=effect_id,
            state=BrokerEffectState.NEEDS_REVIEW,
        ),
    )
    for command in commands:
        transition = venue_fixtures.apply_venue_recovery_input(
            book,
            execution,
            command,
        )
        assert transition.disposition is VenueRecoveryDisposition.APPLIED
        book = transition.book
        execution = transition.execution

    fact = venue_fixtures._broker_fill(
        f"{label}-source",
        f"{label}-root",
        leg_key=leg_key,
        quantity=quantity,
        units=units,
    )
    fact = replace(
        fact,
        scope=venue_fixtures._execution_scope(
            leg_key=leg_key,
            symbol=position_scope.symbol_id,
        ),
        price=_price(units, tick_units=tick_units, scale=scale),
    )
    filled = venue_fixtures.apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId(f"{label}-fill-input"),
            effect_id=effect_id,
            leg_key=leg_key,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(quantity),
            fact=fact,
            evidence_digest=b"\xa8" * 32,
        ),
    )
    assert filled.disposition is VenueRecoveryDisposition.APPLIED
    assert filled.quantity_delta == quantity
    return filled, effect_id, leg_key


def _emergency_goal_fixture(
    module: ModuleType,
    *,
    label: str,
    mandate: object | None = None,
    market_label: str | None = None,
    fill_quantity: int = 4,
    fill_units: int = 100,
    tick_units: int = 1,
    scale: PriceScale = SCALE,
    position_scope: PositionScope = POSITION_SCOPE,
    first_bid: int = 92,
    second_bid: int = 91,
) -> tuple[object, object, object, object]:
    occurrence_label = market_label or label
    if position_scope == POSITION_SCOPE:
        fill = _owned_fill_transition(
            label=f"{label}-fill",
            quantity=fill_quantity,
            units=fill_units,
            capacity=max(20, fill_quantity),
            tick_units=tick_units,
            scale=scale,
        )
        effect_id = BASE_EFFECT
        leg_key = BASE_LEG
    else:
        fill, effect_id, leg_key = _owned_fill_transition_for_scope(
            label=f"{label}-fill",
            position_scope=position_scope,
            quantity=fill_quantity,
            units=fill_units,
            tick_units=tick_units,
            scale=scale,
        )
    current_mandate = (
        mandate
        if mandate is not None
        else _mandate(module, position_scope=position_scope)
    )
    _, _, state = _start(module, fill, current_mandate)
    _, terminal = _terminal_fixture(
        fill,
        effect_id=effect_id,
        leg_key=leg_key,
        label=f"{label}-fill",
        cumulative_quantity=fill_quantity,
    )
    _, closed = _close_parent_fixture(
        terminal,
        effect_id=effect_id,
        label=f"{label}-fill",
    )
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
        _occurrence(
            module,
            f"{occurrence_label}-first",
            bid=first_bid,
            ask=first_bid + tick_units,
            sequence=1,
            tick_units=tick_units,
            scale=scale,
            source_id=current_mandate.evidence_policy.source_id,
            position_scope=position_scope,
            session_id=current_mandate.session_id,
        ),
    )
    result = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            f"{occurrence_label}-second",
            bid=second_bid,
            ask=second_bid + tick_units,
            sequence=2,
            source_time=106,
            evaluation_time=110,
            tick_units=tick_units,
            scale=scale,
            source_id=current_mandate.evidence_policy.source_id,
            position_scope=position_scope,
            session_id=current_mandate.session_id,
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


@pytest.mark.parametrize(
    ("name", "parameter_names", "annotations"),
    [
        (
            "project_protection_venue",
            ("transition", "mandate"),
            {
                "transition": "_VenueRecoveryTransition",
                "mandate": "ProtectionMandate",
                "return": "ProtectionVenueProjection",
            },
        ),
        (
            "initialize_position_protection",
            ("mandate", "projection"),
            {
                "mandate": "ProtectionMandate",
                "projection": "ProtectionVenueProjection",
                "return": "PositionProtectionState",
            },
        ),
        (
            "reduce_position_protection",
            ("state", "projection", "occurrence"),
            {
                "state": "PositionProtectionState",
                "projection": "ProtectionVenueProjection",
                "occurrence": "MarketOccurrence | None",
                "return": "ProtectionTransition",
            },
        ),
    ],
)
def test_public_entrypoints_have_exact_runtime_provenance(
    name: str,
    parameter_names: tuple[str, ...],
    annotations: dict[str, str],
) -> None:
    module = _protection_module()
    _assert_public_entrypoint_provenance(
        module,
        name,
        parameter_names,
        annotations,
    )


def test_public_entrypoint_dependency_closure_has_exact_runtime_provenance() -> None:
    module = _protection_module()
    _assert_local_function_dependency_provenance(
        module,
        (
            "project_protection_venue",
            "initialize_position_protection",
            "reduce_position_protection",
        ),
    )


def test_public_entrypoint_provenance_oracle_rejects_rebinding_and_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = inspect.getmodule(_synthetic_public_entrypoint)
    assert module is not None
    name = "_synthetic_public_entrypoint"
    parameter_names = ("transition", "mandate")
    annotations = {
        "transition": "object",
        "mandate": "object",
        "return": "object",
    }
    (original,) = _required(module, name)
    assert type(original) is FunctionType
    monkeypatch.setattr(execution_core, name, original, raising=False)
    _assert_public_entrypoint_provenance(
        module,
        name,
        parameter_names,
        annotations,
    )

    exact_clone = _clone_entrypoint_function(original)
    with monkeypatch.context() as patch:
        patch.setattr(module, name, exact_clone)
        patch.setattr(execution_core, name, exact_clone)
        _assert_public_entrypoint_provenance(
            module,
            name,
            parameter_names,
            annotations,
        )

    _PUBLIC_ENTRYPOINT_PAYLOAD_CALLS.clear()
    payload_calls = _PUBLIC_ENTRYPOINT_PAYLOAD_CALLS
    canonical_code = original.__code__
    payload_code = _public_entrypoint_source_swap_payload.__code__.replace(
        co_filename=canonical_code.co_filename,
        co_name=name,
        co_qualname=name,
        co_firstlineno=canonical_code.co_firstlineno,
    )
    source_swap = _clone_entrypoint_function(original, code=payload_code)
    with monkeypatch.context() as patch:
        patch.setattr(module, name, source_swap)
        patch.setattr(execution_core, name, source_swap)
        with pytest.raises(AssertionError, match="bytecode does not match"):
            _assert_public_entrypoint_provenance(
                module,
                name,
                parameter_names,
                annotations,
            )
        assert payload_calls == []
        source_swap(object(), object())
        assert payload_calls == ["executed"]
        payload_calls.clear()

    default_mutant = _clone_entrypoint_function(
        original,
        defaults=(object(),),
    )
    attribute_mutant = _clone_entrypoint_function(original)
    attribute_mutant.broker_client = object()
    annotation_mutant = _clone_entrypoint_function(original)
    annotation_mutant.__annotations__["return"] = lambda: None

    retained_capability = object()

    def make_closure_mutant() -> Callable[..., object]:
        capability = retained_capability

        def closure_mutant(transition: object, mandate: object) -> object:
            del transition, mandate
            return capability

        return closure_mutant

    closure_source = make_closure_mutant()
    closure_code = closure_source.__code__.replace(
        co_filename=canonical_code.co_filename,
        co_name=name,
        co_qualname=name,
        co_firstlineno=canonical_code.co_firstlineno,
    )
    closure_mutant = _clone_entrypoint_function(
        original,
        code=closure_code,
        closure=closure_source.__closure__,
    )
    for mutant in (
        default_mutant,
        attribute_mutant,
        annotation_mutant,
        closure_mutant,
    ):
        with monkeypatch.context() as patch:
            patch.setattr(module, name, mutant)
            patch.setattr(execution_core, name, mutant)
            with pytest.raises(AssertionError):
                _assert_public_entrypoint_provenance(
                    module,
                    name,
                    parameter_names,
                    annotations,
                )

    class _CallableMutant:
        def __call__(self, *_args: object, **_kwargs: object) -> None:
            payload_calls.append("callable-executed")

    callable_mutant = _CallableMutant()
    with monkeypatch.context() as patch:
        patch.setattr(module, name, callable_mutant)
        patch.setattr(execution_core, name, callable_mutant)
        with pytest.raises(AssertionError, match="not an exact function"):
            _assert_public_entrypoint_provenance(
                module,
                name,
                parameter_names,
                annotations,
            )
    assert payload_calls == []

    with monkeypatch.context() as patch:
        patch.setattr(execution_core, name, exact_clone)
        with pytest.raises(AssertionError, match="package binding changed"):
            _assert_public_entrypoint_provenance(
                module,
                name,
                parameter_names,
                annotations,
            )

    synthetic_rebind = """
def _synthetic_public_entrypoint(transition, mandate):
    return transition, mandate
_synthetic_public_entrypoint = wrapper
"""
    assert _module_scope_binding_kinds(synthetic_rebind, name) == (
        "function",
        "assignment",
    )


def test_dependency_provenance_oracle_rejects_helper_rebinding_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = inspect.getmodule(_synthetic_dependency_root)
    assert module is not None
    roots = (
        "_synthetic_dependency_root",
        "_synthetic_imported_dependency_root",
    )
    _assert_local_function_dependency_provenance(module, roots)

    helper = _synthetic_dependency_helper
    exact_clone = _clone_entrypoint_function(helper)
    with monkeypatch.context() as patch:
        patch.setattr(module, helper.__name__, exact_clone)
        _assert_local_function_dependency_provenance(module, roots)

    canonical_code = helper.__code__
    payload_code = _dependency_source_swap_payload.__code__.replace(
        co_filename=canonical_code.co_filename,
        co_name=helper.__name__,
        co_qualname=helper.__name__,
        co_firstlineno=canonical_code.co_firstlineno,
    )
    payload_mutant = _clone_entrypoint_function(helper, code=payload_code)
    default_mutant = _clone_entrypoint_function(helper, defaults=(object(),))
    attribute_mutant = _clone_entrypoint_function(helper)
    attribute_mutant.broker_client = object()

    _PUBLIC_ENTRYPOINT_PAYLOAD_CALLS.clear()
    for mutant in (payload_mutant, default_mutant, attribute_mutant):
        with monkeypatch.context() as patch:
            patch.setattr(module, helper.__name__, mutant)
            with pytest.raises(AssertionError):
                _assert_local_function_dependency_provenance(module, roots)
    with monkeypatch.context() as patch:
        patch.setattr(module, "copy", _dependency_source_swap_payload)
        with pytest.raises(AssertionError, match="imported dependency binding changed"):
            _assert_local_function_dependency_provenance(module, roots)
    assert _PUBLIC_ENTRYPOINT_PAYLOAD_CALLS == []


def test_no_access_lookalike_proves_identity_checks_are_protocol_free() -> None:
    negative_events: list[str] = []
    negative = _no_access_lookalike(negative_events)
    assert type(negative) is not object
    assert negative is not None
    assert negative_events == []

    format_events: list[str] = []
    with pytest.raises(AssertionError, match="protocol executed: format"):
        format(_no_access_lookalike(format_events), "")
    assert format_events == ["format"]

    truth_events: list[str] = []
    with pytest.raises(AssertionError, match="protocol executed: bool"):
        bool(_no_access_lookalike(truth_events))
    assert truth_events == ["bool"]

    arithmetic_events: list[str] = []
    with pytest.raises(AssertionError, match="protocol executed: radd"):
        1 + _no_access_lookalike(arithmetic_events)  # type: ignore[operator]
    assert arithmetic_events == ["radd"]

    floor_events: list[str] = []
    with pytest.raises(AssertionError, match="protocol executed: rfloordiv"):
        1 // _no_access_lookalike(floor_events)  # type: ignore[operator]
    assert floor_events == ["rfloordiv"]

    comparison_events: list[str] = []
    with pytest.raises(AssertionError, match="protocol executed: lt"):
        _no_access_lookalike(comparison_events) < 1  # type: ignore[operator]
    assert comparison_events == ["lt"]

    iteration_events: list[str] = []
    with pytest.raises(AssertionError, match="protocol executed: iter"):
        iter(_no_access_lookalike(iteration_events))  # type: ignore[arg-type]
    assert iteration_events == ["iter"]

    def unsafe_field_read(value: object) -> None:
        value.authority  # type: ignore[attr-defined]
        raise TypeError("value")

    with pytest.raises(AssertionError, match="attribute:authority"):
        unsafe_field_read(negative)
    assert negative_events == ["attribute:authority"]

    type_events: list[str] = []
    type_probe = _no_access_lookalike(type_events)
    with pytest.raises(AssertionError, match="type-attribute:__name__"):
        type(type_probe).__name__
    assert type_events == ["type-attribute:__name__"]


def test_public_entrypoint_argument_types_are_unconditionally_sealed() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="public-entrypoint-sealed-types")
    mandate, projection, state = _start(module, fill)
    occurrence = _occurrence(
        module,
        "public-entrypoint-sealed-types",
        bid=100,
        ask=101,
    )
    accepted_values = (
        ("transition", fill),
        ("mandate", mandate),
        ("projection", projection),
        ("state", state),
        ("occurrence", occurrence),
    )
    for label, value in accepted_values:
        value_type = type(value)
        owner_module = inspect.getmodule(value_type)
        assert owner_module is not None, label
        assert "__init_subclass__" in _retained_behavior_names(value_type), label
        _assert_passive_lifecycle(value_type, owner_module)
        with pytest.raises(TypeError):
            type(f"Forged{label.title()}", (value_type,), {"__slots__": ()})

    with pytest.raises(TypeError):
        type("ForgedNone", (type(None),), {"__slots__": ()})


def test_public_entrypoints_reject_every_wrong_exact_type_before_protocol_access() -> (
    None
):
    module = _protection_module()
    fill = _owned_fill_transition(label="public-entrypoint-no-access")
    mandate, projection, state = _start(module, fill)
    occurrence = _occurrence(
        module,
        "public-entrypoint-no-access",
        bid=100,
        ask=101,
    )
    project, initialize, reduce = _required(
        module,
        "project_protection_venue",
        "initialize_position_protection",
        "reduce_position_protection",
    )
    matrix = (
        ("project.transition", project, (fill, mandate), 0),
        ("project.mandate", project, (fill, mandate), 1),
        ("initialize.mandate", initialize, (mandate, projection), 0),
        ("initialize.projection", initialize, (mandate, projection), 1),
        ("reduce.state", reduce, (state, projection, occurrence), 0),
        ("reduce.projection", reduce, (state, projection, occurrence), 1),
        ("reduce.occurrence", reduce, (state, projection, occurrence), 2),
    )
    for label, entrypoint, valid_arguments, attacked_index in matrix:
        events: list[str] = []
        arguments = list(valid_arguments)
        arguments[attacked_index] = _no_access_lookalike(events)
        with pytest.raises(TypeError):
            entrypoint(*arguments)
        assert events == [], label


def test_public_entrypoints_emit_no_stdout_or_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="public-entrypoint-no-output")
    mandate = _mandate(module)
    project, initialize, reduce = _required(
        module,
        "project_protection_venue",
        "initialize_position_protection",
        "reduce_position_protection",
    )
    capsys.readouterr()

    projection = project(fill, mandate)
    assert capsys.readouterr() == ("", "")
    state = initialize(mandate, projection)
    assert capsys.readouterr() == ("", "")
    reduce(state, projection, None)
    assert capsys.readouterr() == ("", "")
    occurrence = _occurrence(
        module,
        "public-entrypoint-no-output",
        bid=100,
        ask=101,
    )
    reduce(state, projection, occurrence)
    assert capsys.readouterr() == ("", "")


def test_public_value_shapes_and_enum_members_are_exact() -> None:
    module = _protection_module()
    expected_fields = {
        "EvidencePolicy": (
            "source_id",
            "max_age",
            "corroboration_window",
            "max_step_fraction",
        ),
        "ExecutionGuard": ("guard_id", "policy_commitment"),
        "ProtectionMandate": (
            "mandate_id",
            "position_scope",
            "session_id",
            "configuration_version",
            "loss_fraction",
            "approved_gain",
            "percent_trail_fraction",
            "atr_multiple",
            "tick",
            "normal_guard",
            "emergency_guard",
            "evidence_policy",
            "maximum_quantity",
            "maximum_goal_rate",
            "deadline",
        ),
        "MarketOccurrence": (
            "occurrence_id",
            "source_id",
            "position_scope",
            "session_id",
            "market_epoch",
            "source_sequence",
            "source_time",
            "evaluation_time",
            "kind",
            "best_bid",
            "best_ask",
            "trade_price",
            "atr_distance",
            "structure_trail",
            "halted",
        ),
        "PositionProtectionState": (
            "policy",
            "mandate",
            "raw_quantity",
            "execution_commitment",
            "formula_available",
            "armed_hard_bail_trigger",
            "activation_price",
            "high_watermark",
            "trail",
            "waiting_buy_resolution",
            "commitment",
        ),
        "ProtectionVenueProjection": (
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
            "predecessor_execution_binding_matches",
            "execution_binding_matches",
            "predecessor_account_reconciliation_clear",
            "account_reconciliation_clear",
        ),
        "ExecutionGoal": (
            "side",
            "residual",
            "urgency",
            "guard",
            "deadline",
            "session_id",
            "mandate_id",
            "maximum_goal_rate",
            "execution_commitment",
            "protection_commitment",
        ),
        "ProtectionTransition": (
            "state",
            "disposition",
            "goal",
            "critical_alert",
        ),
    }
    expected_enums = {
        "MarketKind": ("BEST_BID", "TRADE"),
        "ProtectionPolicy": (
            "FLOOR_ONLY",
            "TRAIL_ACTIVE",
            "EXIT_NORMAL",
            "HARD_BAIL",
            "FLAT",
        ),
        "ProtectionUrgency": ("NORMAL", "EMERGENCY"),
        "ProtectionDisposition": ("APPLIED", "EXACT_REPLAY", "STALE", "REFUSED"),
        "ProtectionAlert": ("LATE_POSITIVE_AFTER_FLAT",),
    }
    public_names = {name for name in vars(module) if not name.startswith("_")}
    assert public_names == set(module.__all__)
    for name, expected in expected_enums.items():
        (enum_type,) = _required(module, name)
        _assert_passive_enum_type(enum_type, expected)
    for name, expected in expected_fields.items():
        (value_type,) = _required(module, name)
        assert type(value_type) is type
        assert inspect.getmro(value_type) == (value_type, object)
        actual_fields = _assert_passive_dataclass_metadata(value_type)
        assert (
            tuple(
                field_name
                for field_name in actual_fields
                if not field_name.startswith("_")
            )
            == expected
        )
        if name not in {"PositionProtectionState", "ProtectionVenueProjection"}:
            assert actual_fields == expected
        _assert_passive_slot_descriptors(value_type, actual_fields)
        behavior = _retained_behavior_names(value_type)
        if name in {"PositionProtectionState", "ProtectionVenueProjection"}:
            assert behavior == {"__init__", "__init_subclass__"}
        else:
            assert behavior <= _DATACLASS_LIFECYCLE_SPECIALS
        _assert_passive_lifecycle(value_type, module)


def test_public_behavior_seal_detects_inherited_capability_mutant() -> None:
    class _HiddenCapabilityMixin:
        def __call__(self) -> None:
            raise AssertionError("mutant callable capability must never run")

        def __await__(self) -> object:
            raise AssertionError("mutant await capability must never run")

        def __enter__(self) -> object:
            raise AssertionError("mutant context capability must never run")

        def __exit__(self, *_args: object) -> None:
            raise AssertionError("mutant context capability must never run")

        def __getattr__(self, name: str) -> object:
            if name == "submit_order":
                return lambda: None
            raise AttributeError(name)

        def __setitem__(self, _key: object, _value: object) -> None:
            raise AssertionError("mutant index-mutation capability must never run")

        def submit_order(self) -> None:
            raise AssertionError("mutant capability must never run")

        @property
        def broker_client(self) -> object:
            raise AssertionError("mutant capability must never run")

    class _ApparentlySafeValue(_HiddenCapabilityMixin):
        pass

    assert _retained_behavior_names(_ApparentlySafeValue) == {
        "__call__",
        "__await__",
        "__enter__",
        "__exit__",
        "__getattr__",
        "__setitem__",
        "broker_client",
        "submit_order",
    }


def test_passive_enum_seal_rejects_capability_method_mutant() -> None:
    class _PlainEnum(Enum):
        SAFE = 1
        HALT = 7

    class _CapabilityEnum(str, Enum):
        SAFE = "SAFE"

        def submit_order(self) -> None:
            raise AssertionError("enum capability mutant must never run")

    class _OverrideEnum(str, Enum):
        SAFE = "SAFE"

        def __str__(self) -> str:
            raise AssertionError("enum override mutant must never run")

    class _MemberPayloadEnum(Enum):
        SAFE = 1

    object.__setattr__(_MemberPayloadEnum.SAFE, "broker_client", lambda: None)

    _assert_passive_enum_type(_PlainEnum, ("SAFE", "HALT"))
    with pytest.raises(AssertionError, match="enum class shape changed"):
        _assert_passive_enum_type(_CapabilityEnum, ("SAFE",))
    with pytest.raises(AssertionError, match="enum behavior changed: __str__"):
        _assert_passive_enum_type(_OverrideEnum, ("SAFE",))
    with pytest.raises(AssertionError, match="enum member payload changed"):
        _assert_passive_enum_type(_MemberPayloadEnum, ("SAFE",))
    with pytest.raises(AssertionError, match="enum class shape changed"):
        _assert_passive_value_graph(
            _CapabilityEnum.SAFE,
            allowed_shapes={},
            allowed_enum_shapes={_CapabilityEnum: ("SAFE",)},
        )


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (False, True),
        (b"first", b"second"),
        (1, 2),
        ("first", "second"),
        (Decimal("1.25"), Decimal("2.5")),
        (Fraction(1, 3), Fraction(2, 3)),
        (None, "present"),
    ],
)
def test_passive_enum_seal_accepts_every_inert_exact_payload_type(
    first: object,
    second: object,
) -> None:
    enum_type = Enum(
        "_PassivePayloadProbe",
        {"FIRST": first, "SECOND": second},
    )
    _assert_passive_enum_type(enum_type, ("FIRST", "SECOND"))


def test_passive_value_graph_rejects_private_capability_field_mutant() -> None:
    @dataclass(frozen=True, slots=True)
    class _SafeDefaultPrivateFieldMutant:
        value: int
        _broker_client: None = None

    @dataclass(frozen=True, slots=True)
    class _PrivateCapabilityFieldMutant:
        _broker_client: object

    @dataclass(frozen=True, slots=True)
    class _FrozenBrokerClient:
        def submit_order(self) -> None:
            raise AssertionError("nested mutant capability must never run")

    @dataclass(frozen=True, slots=True)
    class _NestedCapabilityFieldMutant:
        value: int
        _payload: object

    with pytest.raises(AssertionError, match="field inventory changed"):
        _assert_passive_value_graph(
            _SafeDefaultPrivateFieldMutant(value=1),
            allowed_shapes={_SafeDefaultPrivateFieldMutant: ("value",)},
        )
    with pytest.raises(AssertionError, match="callable capability"):
        _assert_passive_value_graph(
            _PrivateCapabilityFieldMutant(_broker_client=lambda: None),
            allowed_shapes={
                _PrivateCapabilityFieldMutant: ("_broker_client",),
            },
        )
    with pytest.raises(AssertionError, match="unapproved dataclass or capability"):
        _assert_passive_value_graph(
            _PrivateCapabilityFieldMutant(_broker_client=object()),
            allowed_shapes={
                _PrivateCapabilityFieldMutant: ("_broker_client",),
            },
        )
    with pytest.raises(AssertionError, match="unapproved dataclass or capability"):
        _assert_passive_value_graph(
            _NestedCapabilityFieldMutant(
                value=1,
                _payload=_FrozenBrokerClient(),
            ),
            allowed_shapes={
                _NestedCapabilityFieldMutant: ("value", "_payload"),
            },
        )


def test_passive_value_graph_rejects_metaclass_and_descriptor_spoofs() -> None:
    metaclass_calls: list[str] = []

    class _SpoofMeta(type):
        def __hash__(cls) -> int:
            metaclass_calls.append("hash")
            return hash(int)

        def __eq__(cls, _other: object) -> bool:
            metaclass_calls.append("eq")
            return True

    class _MetaclassCapability(metaclass=_SpoofMeta):
        def submit_order(self) -> None:
            raise AssertionError("metaclass mutant capability must never run")

    with pytest.raises(AssertionError, match="custom metaclass"):
        _assert_passive_value_graph(
            _MetaclassCapability(),
            allowed_shapes={},
        )
    assert metaclass_calls == []

    trusted_dispatch_calls: list[str] = []

    class _TrustedDispatchMutant:
        __slots__ = ("value",)

        def __getattribute__(self, name: str) -> object:
            trusted_dispatch_calls.append(name)
            return object.__getattribute__(self, name)

    trusted_mutant = object.__new__(_TrustedDispatchMutant)
    object.__setattr__(trusted_mutant, "value", 1)
    with pytest.raises(AssertionError, match="custom attribute access"):
        _assert_passive_value_graph(
            trusted_mutant,
            allowed_shapes={},
            trusted_leaf_types=frozenset({_TrustedDispatchMutant}),
        )
    assert trusted_dispatch_calls == []

    @dataclass(frozen=True, slots=True)
    class _DescriptorReplacementMutant:
        value: int

    retained = _DescriptorReplacementMutant(value=1)
    descriptor_reads: list[str] = []

    def read_value(_instance: object) -> int:
        descriptor_reads.append("read")
        return 1

    _DescriptorReplacementMutant.value = property(read_value)  # type: ignore[assignment]
    with pytest.raises(AssertionError, match="field descriptor changed"):
        _assert_passive_value_graph(
            retained,
            allowed_shapes={_DescriptorReplacementMutant: ("value",)},
        )
    assert descriptor_reads == []


def test_passive_value_graph_rejects_forged_generated_freeze_behavior() -> None:
    @dataclass(frozen=True, slots=True)
    class _GeneratedFreezeMutant:
        value: int

    retained = _GeneratedFreezeMutant(value=1)

    def mutable_setattr(self: object, name: str, value: object) -> None:
        object.__setattr__(self, name, value)

    mutable_setattr.__code__ = mutable_setattr.__code__.replace(co_filename="<string>")
    _GeneratedFreezeMutant.__setattr__ = mutable_setattr  # type: ignore[assignment]
    with pytest.raises(AssertionError):
        _assert_passive_value_graph(
            retained,
            allowed_shapes={_GeneratedFreezeMutant: ("value",)},
        )
    retained.value = 2
    assert retained.value == 2


def test_passive_value_graph_rejects_capability_and_forged_dataclass_metadata() -> None:
    @dataclass(frozen=True, slots=True)
    class _AnnotationMetadataMutant:
        value: int

    _AnnotationMetadataMutant.__annotations__["value"] = lambda: None
    with pytest.raises(AssertionError, match="annotation retains a capability"):
        _assert_passive_value_graph(
            _AnnotationMetadataMutant(value=1),
            allowed_shapes={_AnnotationMetadataMutant: ("value",)},
        )

    @dataclass(frozen=True, slots=True)
    class _DocumentationMetadataMutant:
        value: int

    _DocumentationMetadataMutant.__doc__ = lambda: None  # type: ignore[assignment]
    with pytest.raises(AssertionError, match="documentation retains a capability"):
        _assert_passive_value_graph(
            _DocumentationMetadataMutant(value=1),
            allowed_shapes={_DocumentationMetadataMutant: ("value",)},
        )

    field_metadata_calls: list[str] = []

    class _FieldMetadataDict(dict[str, object]):
        def values(self) -> object:
            field_metadata_calls.append("values")
            return super().values()

    @dataclass(frozen=True, slots=True)
    class _FieldMetadataMutant:
        value: int

    _FieldMetadataMutant.__dataclass_fields__ = _FieldMetadataDict(  # type: ignore[assignment]
        vars(_FieldMetadataMutant)["__dataclass_fields__"]
    )
    with pytest.raises(AssertionError, match="field metadata is not an exact dict"):
        _assert_passive_value_graph(
            _FieldMetadataMutant(value=1),
            allowed_shapes={_FieldMetadataMutant: ("value",)},
        )
    assert field_metadata_calls == []

    @dataclass(slots=True)
    class _ForgedFrozenMetadataMutant:
        value: int

    mutable = _ForgedFrozenMetadataMutant(value=1)
    _ForgedFrozenMetadataMutant.__dataclass_params__ = vars(_PassiveDataclassProbe)[  # type: ignore[assignment]
        "__dataclass_params__"
    ]
    with pytest.raises(AssertionError, match="dataclass generated"):
        _assert_passive_value_graph(
            mutable,
            allowed_shapes={_ForgedFrozenMetadataMutant: ("value",)},
        )
    mutable.value = 2
    assert mutable.value == 2


def test_passive_lifecycle_accepts_exact_sequential_validation() -> None:
    @dataclass(frozen=True, slots=True)
    class _SequentialValidationProbe:
        label: str
        commitment: bytes
        fraction: Fraction
        source_time: int
        evaluation_time: int
        optional_time: int | None
        kind: _PassiveEnumProbe
        active: bool

        def __post_init__(self) -> None:
            if type(self.label) is not str:
                raise TypeError("label")
            if not self.label.strip():
                raise ValueError("label")
            if type(self.commitment) is not bytes:
                raise TypeError("commitment")
            if len(self.commitment) != 32:
                raise ValueError("commitment")
            if type(self.fraction) is not Fraction:
                raise TypeError("fraction")
            if type(self.source_time) is not int:
                raise TypeError("source_time")
            if self.source_time < 0:
                raise ValueError("source_time")
            if type(self.evaluation_time) is not int:
                raise TypeError("evaluation_time")
            if self.evaluation_time < self.source_time:
                raise ValueError("evaluation_time")
            if self.optional_time is not None:
                if type(self.optional_time) is not int:
                    raise TypeError("optional_time")
                if self.optional_time < 0:
                    raise ValueError("optional_time")
            if self.kind is not _PassiveEnumProbe.FIRST:
                raise ValueError("kind")
            if type(self.active) is not bool:
                raise TypeError("active")
            if not self.active:
                raise ValueError("active")

    owner_module = inspect.getmodule(_SequentialValidationProbe)
    assert owner_module is not None
    _assert_passive_lifecycle(_SequentialValidationProbe, owner_module)
    valid = _SequentialValidationProbe(
        label="exact",
        commitment=b"x" * 32,
        fraction=Fraction(1, 4),
        source_time=10,
        evaluation_time=10,
        optional_time=11,
        kind=_PassiveEnumProbe.FIRST,
        active=True,
    )
    assert valid.label == "exact"
    with pytest.raises(ValueError, match="label"):
        replace(valid, label=" ")
    with pytest.raises(ValueError, match="commitment"):
        replace(valid, commitment=b"x" * 31)
    with pytest.raises(TypeError, match="fraction"):
        replace(valid, fraction=True)
    with pytest.raises(ValueError, match="evaluation_time"):
        replace(valid, evaluation_time=9)


def test_passive_lifecycle_rejects_active_nested_attribute_access_before_payload() -> (
    None
):
    @dataclass(frozen=True, slots=True)
    class _PassiveNestedValueProbe:
        tick: object

        def __post_init__(self) -> None:
            if type(self.tick) is not TickMetadata:
                raise TypeError("tick")
            if type(self.tick.tick_units) is not PriceUnits:
                raise TypeError("tick_units")

    @dataclass(frozen=True, slots=True)
    class _GetattributeLifecycleMutant:
        nested: object

        def __post_init__(self) -> None:
            if type(self.nested) is not _ActiveGuardedGetattribute:
                raise TypeError("nested")
            if self.nested.value < 0:
                raise ValueError("value")

    @dataclass(frozen=True, slots=True)
    class _GetattrLifecycleMutant:
        nested: object

        def __post_init__(self) -> None:
            if type(self.nested) is not _ActiveGuardedGetattr:
                raise TypeError("nested")
            if self.nested.value < 0:
                raise ValueError("value")

    owner_module = inspect.getmodule(_PassiveNestedValueProbe)
    assert owner_module is not None
    _assert_passive_lifecycle(_PassiveNestedValueProbe, owner_module)
    _PassiveNestedValueProbe(tick=TICK)

    _LIFECYCLE_ATTRIBUTE_ACCESS_CALLS.clear()
    for mutant in (_GetattributeLifecycleMutant, _GetattrLifecycleMutant):
        with pytest.raises(AssertionError, match="custom attribute access"):
            _assert_passive_lifecycle(mutant, owner_module)
    assert _LIFECYCLE_ATTRIBUTE_ACCESS_CALLS == []

    _GetattributeLifecycleMutant(nested=_ActiveGuardedGetattribute(1))
    with pytest.raises(ValueError, match="value"):
        _GetattrLifecycleMutant(nested=object.__new__(_ActiveGuardedGetattr))
    assert _LIFECYCLE_ATTRIBUTE_ACCESS_CALLS == [
        "getattribute:value",
        "getattr:value",
    ]
    _LIFECYCLE_ATTRIBUTE_ACCESS_CALLS.clear()


def test_passive_lifecycle_rejects_capability_and_metadata_mutants() -> None:
    @dataclass(frozen=True, slots=True, init=False)
    class _PassiveOpaqueProbe:
        value: int

        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            raise TypeError("opaque")

        def __init_subclass__(cls, **kwargs: object) -> None:
            del cls, kwargs
            raise TypeError("sealed")

    @dataclass(frozen=True, slots=True)
    class _CustomPostInitMutant:
        _broker_client: object

        def __post_init__(self) -> None:
            if self._broker_client.submit_order():
                raise ValueError("capability")

    @dataclass(frozen=True, slots=True)
    class _GlobalSubscriptMutationMutant:
        value: int

        def __post_init__(self) -> None:
            globals()["_lifecycle_mutation_target"] = self

    @dataclass(frozen=True, slots=True)
    class _FakeStripMutant:
        value: object

        def __post_init__(self) -> None:
            if self.value.strip():
                raise ValueError("fake strip")

    @dataclass(frozen=True, slots=True)
    class _FakeLenMutant:
        value: object

        def __post_init__(self) -> None:
            if len(self.value) != 32:  # type: ignore[arg-type]
                raise ValueError("fake len")

    type_protocol_calls: list[str] = []

    class _TypeProbeMeta(type):
        def __bool__(cls) -> bool:
            type_protocol_calls.append("bool")
            return True

        def __eq__(cls, _other: object) -> bool:
            type_protocol_calls.append("eq")
            return True

    class _TypeProbe(metaclass=_TypeProbeMeta):
        pass

    @dataclass(frozen=True, slots=True)
    class _UnsafeTypeTruthMutant:
        value: object

        def __post_init__(self) -> None:
            if type(self.value):
                raise ValueError("unsafe type truth")

    @dataclass(frozen=True, slots=True)
    class _UnsafeTypeEqualityMutant:
        value: object

        def __post_init__(self) -> None:
            if type(self.value) == object:  # noqa: E721 - deliberate unsafe mutant
                raise ValueError("unsafe type equality")

    def shadowed_error(_message: str) -> bool:
        raise AssertionError("shadowed default must never run")

    @dataclass(frozen=True, slots=True)
    class _DefaultShadowMutant:
        value: int

        def __post_init__(self, TypeError=shadowed_error) -> None:  # noqa: N803
            if TypeError("shadowed"):
                raise ValueError("shadowed")

    def make_closure_mutant() -> type[object]:
        def capability() -> None:
            return None

        @dataclass(frozen=True, slots=True)
        class _ClosureMutant:
            value: int

            def __post_init__(self) -> None:
                capability()

        return _ClosureMutant

    _ClosureMutant = make_closure_mutant()

    @dataclass(frozen=True, slots=True)
    class _DecoratedLifecycleMutant:
        value: int

        @staticmethod
        def __post_init__() -> None:
            return None

    @dataclass(frozen=True, slots=True)
    class _AnnotationMutant:
        value: int

        def __post_init__(self) -> None:
            return None

    _AnnotationMutant.__post_init__.__annotations__["return"] = lambda: None

    @dataclass(frozen=True, slots=True)
    class _FunctionAttributeMutant:
        value: int

        def __post_init__(self) -> None:
            return None

    _FunctionAttributeMutant.__post_init__.broker_client = lambda: None

    owner_module = inspect.getmodule(_PassiveOpaqueProbe)
    assert owner_module is not None
    assert _retained_behavior_names(_PassiveOpaqueProbe) == {
        "__init__",
        "__init_subclass__",
    }
    _assert_passive_lifecycle(_PassiveOpaqueProbe, owner_module)

    assert "__post_init__" in _retained_behavior_names(_CustomPostInitMutant)
    with pytest.raises(AssertionError, match="unapproved lifecycle call"):
        _assert_passive_lifecycle(_CustomPostInitMutant, owner_module)
    with pytest.raises(AssertionError, match="unsupported lifecycle statement"):
        _assert_passive_lifecycle(_GlobalSubscriptMutationMutant, owner_module)
    with pytest.raises(AssertionError, match="prior exact str guard"):
        _assert_passive_lifecycle(_FakeStripMutant, owner_module)
    with pytest.raises(AssertionError, match="prior exact bytes or str guard"):
        _assert_passive_lifecycle(_FakeLenMutant, owner_module)
    with pytest.raises(AssertionError, match="unapproved lifecycle call"):
        _assert_passive_lifecycle(_UnsafeTypeTruthMutant, owner_module)
    with pytest.raises(AssertionError, match="unapproved lifecycle call"):
        _assert_passive_lifecycle(_UnsafeTypeEqualityMutant, owner_module)
    assert type_protocol_calls == []
    with pytest.raises(AssertionError):
        _assert_passive_lifecycle(_DefaultShadowMutant, owner_module)
    with pytest.raises(AssertionError):
        _assert_passive_lifecycle(_ClosureMutant, owner_module)
    with pytest.raises(AssertionError):
        _assert_passive_lifecycle(_DecoratedLifecycleMutant, owner_module)
    with pytest.raises(AssertionError, match="annotation retains a capability"):
        _assert_passive_lifecycle(_AnnotationMutant, owner_module)
    with pytest.raises(AssertionError):
        _assert_passive_lifecycle(_FunctionAttributeMutant, owner_module)


def test_passive_lifecycle_rejects_source_and_bytecode_provenance_split() -> None:
    @dataclass(frozen=True, slots=True)
    class _SourceSwapMutant:
        value: int

        def __post_init__(self) -> None:
            return None

    benign = _SourceSwapMutant.__post_init__
    benign.__code__ = _lifecycle_source_swap_payload.__code__.replace(
        co_filename=benign.__code__.co_filename,
        co_firstlineno=benign.__code__.co_firstlineno,
    )
    owner_module = inspect.getmodule(_SourceSwapMutant)
    assert owner_module is not None
    _LIFECYCLE_SOURCE_SWAP_CALLS.clear()
    with pytest.raises(
        AssertionError,
        match="bytecode does not match inspected source",
    ):
        _assert_passive_lifecycle(_SourceSwapMutant, owner_module)
    assert _LIFECYCLE_SOURCE_SWAP_CALLS == []
    _SourceSwapMutant(value=1)
    assert _LIFECYCLE_SOURCE_SWAP_CALLS == ["executed"]
    _LIFECYCLE_SOURCE_SWAP_CALLS.clear()


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


def test_market_kind_owns_one_exact_payload_shape() -> None:
    module = _protection_module()
    quote = _occurrence(module, "shape-quote", bid=100, ask=101)
    trade = _occurrence(module, "shape-trade", kind="TRADE", trade=100)
    invalid = (
        (quote, {"best_bid": None}),
        (quote, {"best_ask": None}),
        (quote, {"trade_price": _price(100)}),
        (
            quote,
            {"best_bid": None, "best_ask": None, "trade_price": _price(100)},
        ),
        (trade, {"trade_price": None}),
        (trade, {"best_bid": _price(100), "best_ask": _price(101)}),
        (trade, {"atr_distance": _price(2)}),
        (trade, {"structure_trail": _price(99)}),
    )
    for occurrence, overrides in invalid:
        with pytest.raises(ValueError):
            replace(occurrence, **overrides)


def test_state_and_projection_are_opaque_and_sealed() -> None:
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


def test_single_leaf_mutation_walker_is_complete_local_and_shape_bounded() -> None:
    @dataclass(frozen=True, slots=True)
    class _NestedLeafProbe:
        value: int

    @dataclass(frozen=True, slots=True)
    class _LeafGraphProbe:
        scalar: int
        flag: bool
        payload: bytes
        label: str
        decimal: Decimal
        ratio: Fraction
        kind: _PassiveEnumProbe
        optional: int | None
        nested: _NestedLeafProbe
        items: tuple[object, ...]
        members: frozenset[int]
        optional_items: tuple[int | None, ...]
        optional_members: frozenset[int | None]
        empty_items: tuple[int, ...]
        empty_members: frozenset[int]

    @dataclass(frozen=True, slots=True)
    class _DenseSetProbe:
        values: frozenset[PriceUnits]

    @dataclass(frozen=True, slots=True)
    class _UnmutableDenseSetProbe:
        values: frozenset[bool]

    probe = _LeafGraphProbe(
        scalar=7,
        flag=True,
        payload=b"payload",
        label="label",
        decimal=Decimal("1.25"),
        ratio=Fraction(3, 5),
        kind=_PassiveEnumProbe.FIRST,
        optional=None,
        nested=_NestedLeafProbe(value=11),
        items=(b"first", "second"),
        members=frozenset({10, 30}),
        optional_items=(None,),
        optional_members=frozenset({None}),
        empty_items=(),
        empty_members=frozenset(),
    )
    mutations = _single_leaf_mutations(
        probe,
        allowed_root_types=(type(probe),),
        union_replacements={
            ("optional",): 13,
            ("optional_items", 0): 23,
            ("optional_members", 0): 29,
        },
        empty_collection_replacements={
            ("empty_items",): (17,),
            ("empty_members",): frozenset({19}),
        },
    )
    expected_paths = frozenset(
        {
            ("scalar",),
            ("flag",),
            ("payload",),
            ("label",),
            ("decimal",),
            ("ratio",),
            ("kind",),
            ("optional",),
            ("nested", "value"),
            ("items", 0),
            ("items", 1),
            ("members", 0),
            ("members", 1),
            ("optional_items", 0),
            ("optional_members", 0),
            ("empty_items",),
            ("empty_members",),
        }
    )
    assert _retained_leaf_paths(probe) == expected_paths
    assert tuple(mutation.path for mutation in mutations) == tuple(
        mutation.path
        for mutation in _single_leaf_mutations(
            probe,
            allowed_root_types=(type(probe),),
            union_replacements={
                ("optional",): 13,
                ("optional_items", 0): 23,
                ("optional_members", 0): 29,
            },
            empty_collection_replacements={
                ("empty_items",): (17,),
                ("empty_members",): frozenset({19}),
            },
        )
    )
    assert frozenset(mutation.path for mutation in mutations) == expected_paths
    assert len(mutations) == len(expected_paths)

    for mutation in mutations:
        assert type(mutation.forged) is type(probe)
        assert _changed_leaf_paths(probe, mutation.forged) == frozenset({mutation.path})
    optional = next(
        mutation for mutation in mutations if mutation.path == ("optional",)
    )
    assert type(optional.forged.optional) is int
    assert optional.forged.optional == 13
    optional_item = next(
        mutation for mutation in mutations if mutation.path == ("optional_items", 0)
    )
    assert optional_item.forged.optional_items == (23,)
    optional_member = next(
        mutation for mutation in mutations if mutation.path == ("optional_members", 0)
    )
    assert optional_member.forged.optional_members == frozenset({29})

    with pytest.raises(AssertionError, match="outside the declared optional union"):
        _single_leaf_mutations(
            probe,
            allowed_root_types=(type(probe),),
            union_replacements={
                ("optional",): object(),
                ("optional_items", 0): 23,
                ("optional_members", 0): 29,
            },
            empty_collection_replacements={
                ("empty_items",): (17,),
                ("empty_members",): frozenset({19}),
            },
        )

    dense = _DenseSetProbe(values=frozenset({PriceUnits(1), PriceUnits(2)}))
    dense_mutations = _single_leaf_mutations(
        dense,
        allowed_root_types=(type(dense),),
    )
    assert frozenset(mutation.path for mutation in dense_mutations) == frozenset(
        {("values", 0, "value"), ("values", 1, "value")}
    )
    for mutation in dense_mutations:
        assert type(mutation.forged) is type(dense)
        assert all(type(member) is PriceUnits for member in mutation.forged.values)
        assert _changed_leaf_paths(dense, mutation.forged) == frozenset({mutation.path})

    unmutable = _UnmutableDenseSetProbe(values=frozenset({False, True}))
    with pytest.raises(
        AssertionError,
        match="frozenset leaf has no non-colliding same-type mutation",
    ):
        _single_leaf_mutations(
            unmutable,
            allowed_root_types=(type(unmutable),),
        )

    _, _, _, transition = _owned_fill_fixture(label="real-mutation-primitive")
    real_kernel_values = (
        MandateId("real-mutation-primitive"),
        PriceUnits(7),
        _price(101),
        transition,
    )
    for current in real_kernel_values:
        replacement = _different_value(current)
        assert type(replacement) is type(current)
        assert replacement != current

    reported = _price(101)
    reported_mutations = _single_leaf_mutations(
        reported,
        allowed_root_types=(ReportedPrice,),
    )
    reported_paths = frozenset(
        {
            ("units", "value"),
            ("scale", "value"),
            ("tick", "tick_units", "value"),
            ("tick", "scale", "value"),
        }
    )
    assert _retained_leaf_paths(reported) == reported_paths
    assert frozenset(mutation.path for mutation in reported_mutations) == reported_paths
    for mutation in reported_mutations:
        assert type(mutation.forged) is ReportedPrice
        assert _changed_leaf_paths(reported, mutation.forged) == frozenset(
            {mutation.path}
        )


def test_every_reducer_owned_state_field_is_authenticated_before_advancement() -> None:
    module = _protection_module()
    (state_type,) = _required(module, "PositionProtectionState")
    fill = _owned_fill_transition(label="protection-state-seal")
    mandate, _, state = _start(module, fill)
    _, terminal = _terminal_fixture(
        fill,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-state-seal",
        cumulative_quantity=4,
    )
    successor = _projection(module, terminal, mandate)
    unavailable_fill = _owned_fill_transition(
        label="protection-state-seal-unavailable",
        quantity=1,
        units=100,
    )
    unavailable_mandate = _mandate(
        module,
        loss_fraction=Fraction(1, 100),
        tick=TickMetadata(tick_units=PriceUnits(100), scale=SCALE),
    )
    _, _, unavailable_state = _start(
        module,
        unavailable_fill,
        unavailable_mandate,
    )
    _, unavailable_terminal = _terminal_fixture(
        unavailable_fill,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-state-seal-unavailable",
        cumulative_quantity=1,
    )
    unavailable_successor = _projection(
        module,
        unavailable_terminal,
        unavailable_mandate,
    )
    (disposition,) = _required(module, "ProtectionDisposition")
    assert state.high_watermark is None
    assert state.trail is None
    assert unavailable_state.formula_available is False
    assert unavailable_state.armed_hard_bail_trigger is None
    assert unavailable_state.high_watermark is None
    assert unavailable_state.trail is None
    scenarios = (
        (
            state,
            successor,
            {
                ("high_watermark",): _price(101),
                ("trail",): _price(99),
            },
        ),
        (
            unavailable_state,
            unavailable_successor,
            {
                ("armed_hard_bail_trigger",): _price(93),
                ("high_watermark",): _price(101),
                ("trail",): _price(99),
            },
        ),
    )
    for sealed_state, sealed_successor, union_replacements in scenarios:
        assert all(
            type(value) is ReportedPrice for value in union_replacements.values()
        )
        mutations = _single_leaf_mutations(
            sealed_state,
            allowed_root_types=(state_type,),
            union_replacements=union_replacements,
        )
        expected_paths = _retained_leaf_paths(sealed_state)
        assert frozenset(mutation.path for mutation in mutations) == expected_paths
        assert len(mutations) == len(expected_paths)
        for mutation in mutations:
            assert _changed_leaf_paths(
                sealed_state,
                mutation.forged,
            ) == frozenset({mutation.path})
            result = _reduce(module, mutation.forged, sealed_successor)
            assert result.disposition is disposition.REFUSED, mutation.path
            assert result.state == mutation.forged, mutation.path
            assert result.goal is None, mutation.path
            assert result.critical_alert is None, mutation.path


def test_every_projection_field_is_sealed_against_single_field_forgery() -> None:
    module = _protection_module()
    (projection_type,) = _required(module, "ProtectionVenueProjection")
    fill = _owned_fill_transition(label="protection-projection-seal")
    mandate, _, state = _start(module, fill)
    _, terminal = _terminal_fixture(
        fill,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-projection-seal",
        cumulative_quantity=4,
    )
    projection = _projection(module, terminal, mandate)
    (disposition,) = _required(module, "ProtectionDisposition")
    mutations = _single_leaf_mutations(
        projection,
        allowed_root_types=(projection_type,),
    )
    expected_paths = _retained_leaf_paths(projection)
    assert frozenset(mutation.path for mutation in mutations) == expected_paths
    assert len(mutations) == len(expected_paths)
    for mutation in mutations:
        assert _changed_leaf_paths(projection, mutation.forged) == frozenset(
            {mutation.path}
        )
        result = _reduce(module, state, mutation.forged)
        assert result.disposition is disposition.REFUSED, mutation.path
        assert result.state == state, mutation.path
        assert result.goal is None, mutation.path
        assert result.critical_alert is None, mutation.path


def test_every_venue_transition_field_is_bound_into_the_protection_proof() -> None:
    module = _protection_module()
    _, _, _, applied = _owned_fill_fixture(label="protection-envelope-seal")
    mandate = _mandate(module)
    tested = set()
    for retained in fields(applied):
        current = getattr(applied, retained.name)
        replacement = _different_value(current)
        assert replacement != current
        forged = _clone_opaque(applied, **{retained.name: replacement})
        with pytest.raises((TypeError, ValueError)):
            _projection(module, forged, mandate)
        tested.add(retained.name)
    assert tested == {retained.name for retained in fields(applied)}


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

    _, closed = _close_parent_fixture(
        terminal,
        effect_id=BASE_EFFECT,
        label="protection-terminal-replay-later-advance",
    )
    closed_projection = _projection(module, closed, mandate)
    assert closed_projection.cursor_ordinal > replay_projection.cursor_ordinal
    assert closed_projection.cursor_head != replay_projection.cursor_head
    advanced = _reduce(
        module,
        replayed.state,
        closed_projection,
    )
    assert advanced.state != replayed.state
    _assert_stale_unchanged(module, advanced.state, replay_projection)


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
    mandate, fill_projection, state = _start(module, fill)
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
    old_projections = []
    (disposition,) = _required(module, "ProtectionDisposition")
    for transition in (refused, conflict):
        assert transition.book == fill.book
        assert transition.execution == fill.execution
        assert transition.quantity_delta == 0
        projection = _projection(module, transition, mandate)
        assert projection.predecessor_cursor_ordinal == projection.cursor_ordinal
        assert projection.predecessor_cursor_head == projection.cursor_head
        assert projection.cursor_ordinal == fill_projection.cursor_ordinal
        assert projection.cursor_head == fill_projection.cursor_head
        result = _reduce(module, state, projection)
        assert result.disposition is disposition.EXACT_REPLAY
        assert result.state == state
        assert result.goal is None
        assert result.critical_alert is None
        old_projections.append(projection)

    _, terminal = _terminal_fixture(
        fill,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-nonadvancing-current",
        cumulative_quantity=4,
    )
    advanced = _reduce(module, state, _projection(module, terminal, mandate))
    assert advanced.state != state
    for old_projection in old_projections:
        _assert_stale_unchanged(module, advanced.state, old_projection)


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
    contradicted_projection = _projection(module, contradicted, mandate)
    synced = _reduce(
        module,
        state,
        contradicted_projection,
    )
    (disposition,) = _required(module, "ProtectionDisposition")
    assert synced.disposition is disposition.EXACT_REPLAY
    assert synced.state == state
    assert synced.goal is None
    assert synced.critical_alert is None
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
    assert projection.cursor_ordinal == contradicted_projection.cursor_ordinal
    assert projection.cursor_head == contradicted_projection.cursor_head
    result = _reduce(module, synced.state, projection)
    assert result.disposition is disposition.EXACT_REPLAY
    assert result.state == synced.state
    assert result.goal is None
    assert result.critical_alert is None

    advance_chain, _, _, _ = _append_needs_review_effect(
        release,
        prefix="protection-nonmutating-later-advance",
        side=ExecutionSide.SELL,
        quantity=1,
    )
    advanced_projection = _projection(module, advance_chain[0], mandate)
    assert advanced_projection.cursor_ordinal > projection.cursor_ordinal
    assert advanced_projection.cursor_head != projection.cursor_head
    advanced = _reduce(
        module,
        result.state,
        advanced_projection,
    )
    assert advanced.state != result.state
    _assert_stale_unchanged(module, advanced.state, projection)


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
    policy, alert = _required(module, "ProtectionPolicy", "ProtectionAlert")
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
    assert recovered.critical_alert is alert.LATE_POSITIVE_AFTER_FLAT
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
    (alert,) = _required(module, "ProtectionAlert")
    assert recovered.critical_alert is alert.LATE_POSITIVE_AFTER_FLAT
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
    fills_module = importlib.import_module("app.execution_core.fills")
    venue_source = inspect.getsource(venue_module)
    provenance_violations = _persistent_map_provenance_violations(
        ast.parse(venue_source)
    )
    assert not provenance_violations, (
        f"venue mutates or aliases the trusted bounded map: {provenance_violations!r}"
    )
    map_type = getattr(venue_module, "_PersistentKeyMap")
    assert map_type is getattr(fills_module, "_PersistentKeyMap")
    original_map_get = inspect.getattr_static(map_type, "get")
    _assert_exact_function_dependency_closure(
        original_map_get,
        fills_module,
        qualified_name="_PersistentKeyMap.get",
        exact_externals={
            "ValueError": builtins.ValueError,
            "_ValueT": vars(fills_module)["_ValueT"],
            "bytes": builtins.bytes,
            "cast": typing.cast,
            "isinstance": builtins.isinstance,
            "len": builtins.len,
        },
    )
    for name in _BOUNDED_PROTECTION_MAP_FIELD_ORDER:
        descriptor = inspect.getattr_static(VenueRecoveryBook, name)
        assert type(descriptor) is _PASSIVE_SLOT_DESCRIPTOR_TYPE
        assert descriptor.__objclass__ is VenueRecoveryBook
        assert descriptor.__name__ == name
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
    monkeypatch.setattr(sequence_type, "get", fail_if_called)
    calls = 0
    receiver_types: set[type[object]] = set()

    def counted_map_get(retained: object, key: bytes) -> object:
        nonlocal calls
        receiver_types.add(type(retained))
        assert type(retained) is map_type
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
    assert small_calls == 3
    assert large_calls == small_calls
    assert receiver_types == {map_type}

    extractor = getattr(venue_module, "_extract_protection_transition")
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
    forbidden.update({"_root", "__dict__"})
    scanned, call_graph, unresolved_calls = _constant_work_call_graph(
        extractor,
        venue_module,
    )

    accessed = {
        node.attr
        for tree in scanned.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in forbidden
    }
    dynamic_calls = {
        node.func.id
        for tree in scanned.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id
        in {
            "all",
            "any",
            "dict",
            "enumerate",
            "filter",
            "getattr",
            "iter",
            "list",
            "map",
            "max",
            "min",
            "next",
            "set",
            "sorted",
            "sum",
            "tuple",
            "vars",
            "zip",
        }
    }
    indirect_calls = _disallowed_constant_work_method_calls(scanned)
    receiver_violations = _extractor_receiver_violations(scanned)
    opaque_call_targets = {
        ast.dump(node.func, include_attributes=False)
        for tree in scanned.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and not isinstance(node.func, (ast.Name, ast.Attribute))
    }
    iterative_nodes = {
        type(node).__name__
        for tree in scanned.values()
        for node in ast.walk(tree)
        if isinstance(
            node,
            (
                ast.For,
                ast.While,
                ast.comprehension,
                ast.GeneratorExp,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
            ),
        )
    }

    def assert_acyclic(name: str, path: tuple[str, ...] = ()) -> None:
        assert name not in path, (
            f"recursive protection extractor path: {path + (name,)!r}"
        )
        for called_name in call_graph.get(name, set()):
            assert_acyclic(called_name, path + (name,))

    assert_acyclic(extractor.__name__)
    assert not accessed, f"protection extractor traverses raw venue state: {accessed!r}"
    assert not dynamic_calls, (
        f"protection extractor uses dynamic traversal: {dynamic_calls!r}"
    )
    assert not unresolved_calls, (
        f"protection extractor uses unresolved callable aliases: {unresolved_calls!r}"
    )
    assert not indirect_calls, (
        f"protection extractor hides work behind method calls: {indirect_calls!r}"
    )
    assert not receiver_violations, (
        f"protection extractor receiver provenance is not exact: "
        f"{receiver_violations!r}"
    )
    assert not opaque_call_targets, (
        f"protection extractor uses opaque callable targets: {opaque_call_targets!r}"
    )
    assert not iterative_nodes, (
        f"protection extractor uses history-shaped iteration: {iterative_nodes!r}"
    )


def test_constant_work_oracle_pins_trusted_bounded_map_provenance() -> None:
    safe_source = """
from dataclasses import field
from .fills import _PersistentKeyMap

class Book:
    retained: _PersistentKeyMap[int] = field(
        default_factory=_PersistentKeyMap.empty
    )

def fresh() -> _PersistentKeyMap[int]:
    return _PersistentKeyMap.empty()
"""
    assert not _persistent_map_provenance_violations(ast.parse(safe_source))


def test_bounded_map_provenance_rejects_transitive_global_rebind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fills_module = importlib.import_module("app.execution_core.fills")
    map_type = getattr(fills_module, "_PersistentKeyMap")
    map_get = inspect.getattr_static(map_type, "get")
    child_at = getattr(fills_module, "_child_at")
    payload_calls: list[str] = []

    def replacement(*args: object, **kwargs: object) -> object:
        payload_calls.append("executed")
        return child_at(*args, **kwargs)

    monkeypatch.setattr(fills_module, "_child_at", replacement)
    with pytest.raises(AssertionError, match="dependency globals changed"):
        _assert_exact_function_dependency_closure(
            map_get,
            fills_module,
            qualified_name="_PersistentKeyMap.get",
            exact_externals={
                "ValueError": builtins.ValueError,
                "_ValueT": vars(fills_module)["_ValueT"],
                "bytes": builtins.bytes,
                "cast": typing.cast,
                "isinstance": builtins.isinstance,
                "len": builtins.len,
            },
        )
    assert payload_calls == []
    assert map_get(map_type.empty(), b"key") is None
    assert payload_calls == ["executed"]


@pytest.mark.parametrize(
    ("mutation", "expected_violation"),
    [
        (
            "_PersistentKeyMap.get = slow_get",
            "persistent-map-capability-escape",
        ),
        (
            "setattr(_PersistentKeyMap, 'get', slow_get)",
            "persistent-map-capability-escape",
        ),
        (
            "_Map = _PersistentKeyMap\n_Map.get = slow_get",
            "persistent-map-capability-escape",
        ),
        (
            "original_get = _PersistentKeyMap.get",
            "persistent-map-capability-escape",
        ),
        (
            "vars(_PersistentKeyMap)['get'] = slow_get",
            "persistent-map-capability-escape",
        ),
        (
            "from .fills import _PersistentKeyMap as _Map",
            "persistent-map-import-provenance",
        ),
        (
            "import app.execution_core.fills as fills\n"
            "fills._PersistentKeyMap.get = slow_get",
            "qualified-persistent-map-access",
        ),
        (
            "from . import fills\nfills._child_at = slow_get",
            "persistent-map-owner-module-import",
        ),
        (
            "from .fills import _child_at\n_child_at = slow_get",
            "persistent-map-dependency-import",
        ),
    ],
)
def test_constant_work_oracle_rejects_bounded_map_mutation_and_aliases(
    mutation: str,
    expected_violation: str,
) -> None:
    source = f"from .fills import _PersistentKeyMap\n{mutation}\n"
    violations = _persistent_map_provenance_violations(ast.parse(source))
    assert expected_violation in violations


@pytest.mark.parametrize(
    ("mutant", "unresolved_name", "raw_attribute"),
    [
        (_local_alias_scan_mutant, "scan", None),
        (_default_alias_scan_mutant, "scan", None),
        (_callable_object_scan_mutant, "_CALLABLE_SCAN_MUTANT", None),
        (_CLOSURE_SCAN_MUTANT, "scan", None),
        (_global_alias_scan_mutant, None, "_input_ledger"),
    ],
)
def test_constant_work_oracle_rejects_alias_and_callable_mutants(
    mutant: Callable[..., object],
    unresolved_name: str | None,
    raw_attribute: str | None,
) -> None:
    owner_module = inspect.getmodule(mutant)
    assert owner_module is not None
    scanned, _, unresolved = _constant_work_call_graph(mutant, owner_module)
    accessed = {
        node.attr
        for tree in scanned.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    }
    if unresolved_name is not None:
        assert unresolved_name in unresolved
    if raw_attribute is not None:
        assert raw_attribute in accessed


def test_constant_work_oracle_rejects_hidden_get_scan_mutant() -> None:
    owner_module = inspect.getmodule(_hidden_get_scan_mutant)
    assert owner_module is not None
    scanned, _, unresolved = _constant_work_call_graph(
        _hidden_get_scan_mutant,
        owner_module,
    )
    assert not unresolved
    assert "get" in _disallowed_constant_work_method_calls(scanned)


def test_constant_work_oracle_rejects_approved_name_lookalike_get_mutant() -> None:
    owner_module = inspect.getmodule(_lookalike_field_get_scan_mutant)
    assert owner_module is not None
    scanned, _, unresolved = _constant_work_call_graph(
        _lookalike_field_get_scan_mutant,
        owner_module,
    )
    assert not unresolved
    assert "get" in _disallowed_constant_work_method_calls(scanned)

    with pytest.raises(AssertionError, match="private venue ledger"):
        _lookalike_field_get_scan_mutant(_LedgerTripwire())


@pytest.mark.parametrize(
    ("mutant", "expected_violation"),
    [
        (_REBOUND_EXACT_SHAPE_GET_MUTANT, "scope-key-assignment"),
        (_EXTRA_EXACT_SHAPE_GET_MUTANT, "extractor-leaf-statement-count"),
    ],
)
def test_constant_work_oracle_rejects_exact_shape_receiver_mutants(
    mutant: Callable[[object], object],
    expected_violation: str,
) -> None:
    owner_module = inspect.getmodule(mutant)
    assert owner_module is not None
    scanned, _, unresolved = _constant_work_call_graph(mutant, owner_module)
    assert not unresolved
    assert expected_violation in _extractor_receiver_violations(scanned)
    with pytest.raises(AssertionError, match="private venue ledger"):
        mutant(_EXACT_SHAPE_LOOKALIKE_TRANSITION)


def test_constant_work_oracle_accepts_only_exact_leaf_extractor_grammar() -> None:
    owner_module = inspect.getmodule(_EXACT_LEAF_EXTRACTOR_PROBE)
    assert owner_module is not None
    scanned, _, unresolved = _constant_work_call_graph(
        _EXACT_LEAF_EXTRACTOR_PROBE,
        owner_module,
    )
    assert not unresolved
    assert not _disallowed_constant_work_method_calls(scanned)
    assert not _extractor_receiver_violations(scanned)


@pytest.mark.parametrize(
    ("mutant", "transition", "runtime_message"),
    [
        (
            _HELPER_ESCAPE_MUTANT,
            _DESCRIPTOR_SLOW_TRANSITION,
            "descriptor reached a private venue ledger",
        ),
        (
            _WRAPPED_RECEIVER_MUTANT,
            _EXACT_SHAPE_LOOKALIKE_TRANSITION,
            "private venue ledger",
        ),
        (
            _AGGREGATE_MAP_MUTANT,
            _EXACT_SHAPE_LOOKALIKE_TRANSITION,
            "private venue ledger",
        ),
    ],
)
def test_constant_work_oracle_rejects_helper_wrapping_and_aggregate_escapes(
    mutant: Callable[[object], object],
    transition: object,
    runtime_message: str,
) -> None:
    owner_module = inspect.getmodule(mutant)
    assert owner_module is not None
    scanned, _, _ = _constant_work_call_graph(mutant, owner_module)
    assert _extractor_receiver_violations(scanned)
    with pytest.raises(AssertionError, match=runtime_message):
        mutant(transition)


def test_constant_work_oracle_rejects_descriptor_slow_scan_mutant() -> None:
    owner_module = inspect.getmodule(_DESCRIPTOR_SLOW_SCAN_MUTANT)
    assert owner_module is not None
    scanned, _, unresolved = _constant_work_call_graph(
        _DESCRIPTOR_SLOW_SCAN_MUTANT,
        owner_module,
    )
    assert not unresolved
    assert "extractor-leaf-statement-count" in _extractor_receiver_violations(scanned)
    with pytest.raises(
        AssertionError, match="descriptor reached a private venue ledger"
    ):
        _DESCRIPTOR_SLOW_SCAN_MUTANT(_DESCRIPTOR_SLOW_TRANSITION)


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


def test_positive_broker_overfill_is_quarantined_before_any_goal_authority() -> None:
    module = _protection_module()
    overfill = _owned_fill_transition(
        label="protection-positive-overfill",
        quantity=5,
        capacity=4,
    )
    assert overfill.execution.position.raw_quantity == 5
    assert overfill.execution.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    mandate, _, state = _start(module, overfill)
    (policy,) = _required(module, "ProtectionPolicy")
    assert state.raw_quantity == 5
    assert state.policy is policy.HARD_BAIL
    assert state.formula_available is False
    terminal, closed = _close_base_parent(overfill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    for index, bid in enumerate((92, 91), start=1):
        result = _reduce(
            module,
            state,
            projection,
            _occurrence(
                module,
                f"positive-overfill-{index}",
                bid=bid,
                ask=bid + 1,
                sequence=index,
                source_time=94 + index * 6,
                evaluation_time=98 + index * 6,
            ),
        )
        state = result.state
        assert result.goal is None
    assert state.policy is policy.HARD_BAIL


@pytest.mark.parametrize(
    "bids",
    [
        (120, 110, 109),
        (92, 91),
    ],
)
def test_residual_above_mandate_quantity_is_never_truncated_or_emitted(
    bids: tuple[int, ...],
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(
        label=f"protection-over-authority-{len(bids)}",
        quantity=5,
        capacity=20,
    )
    mandate, _, state = _start(
        module,
        fill,
        _mandate(module, maximum_quantity=4),
    )
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert state.raw_quantity == 5
    assert state.policy is policy.HARD_BAIL
    for index, bid in enumerate(bids, start=1):
        result = _reduce(
            module,
            state,
            projection,
            _occurrence(
                module,
                f"over-authority-{len(bids)}-{index}",
                bid=bid,
                ask=bid + 1,
                sequence=index,
                source_time=94 + index * 6,
                evaluation_time=98 + index * 6,
            ),
        )
        state = result.state
        assert result.goal is None
    assert state.raw_quantity == 5
    assert state.policy is policy.HARD_BAIL


@pytest.mark.parametrize("crossing", ["mandate-cap", "broker-overfill"])
@pytest.mark.parametrize("bids", [(120, 110, 109), (92, 91)])
def test_later_owned_buy_crossing_a_serving_boundary_is_never_goal_authority(
    crossing: str,
    bids: tuple[int, ...],
) -> None:
    module = _protection_module()
    label = f"later-{crossing}-{len(bids)}"
    fill = _owned_fill_transition(
        label=f"{label}-root",
        quantity=4,
        capacity=4,
    )
    maximum_quantity = 4 if crossing == "mandate-cap" else 20
    mandate, _, state = _start(
        module,
        fill,
        _mandate(module, maximum_quantity=maximum_quantity),
    )
    terminal, closed = _close_base_parent(fill)
    state, serving_projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    policy, urgency = _required(
        module,
        "ProtectionPolicy",
        "ProtectionUrgency",
    )
    assert state.policy is policy.FLOOR_ONLY
    assert state.formula_available is True

    serving_state = state
    for index, bid in enumerate(bids, start=1):
        serving_result = _reduce(
            module,
            serving_state,
            serving_projection,
            _occurrence(
                module,
                f"{label}-pre-buy-serving-{index}",
                bid=bid,
                ask=bid + 1,
                sequence=index,
                source_time=94 + index * 6,
                evaluation_time=98 + index * 6,
            ),
        )
        serving_state = serving_result.state
    assert serving_result.goal is not None
    if len(bids) == 3:
        assert serving_state.policy is policy.EXIT_NORMAL
        assert serving_result.goal.urgency is urgency.NORMAL
        assert serving_result.goal.guard == mandate.normal_guard
    else:
        assert serving_state.policy is policy.HARD_BAIL
        assert serving_result.goal.urgency is urgency.EMERGENCY
        assert serving_result.goal.guard == mandate.emergency_guard

    buy_chain, buy_effect, buy_leg, _ = _append_needs_review_effect(
        closed,
        prefix=f"{label}-buy",
        side=ExecutionSide.BUY,
        quantity=1,
    )
    state, _, _ = _sync_transitions(
        module,
        state,
        mandate,
        buy_chain,
    )
    fill_quantity = 1 if crossing == "mandate-cap" else 2
    later_fill = venue_fixtures.apply_venue_recovery_input(
        buy_chain[-1].book,
        buy_chain[-1].execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId(f"{label}-buy-fill"),
            effect_id=buy_effect,
            leg_key=buy_leg,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(fill_quantity),
            fact=venue_fixtures._broker_fill(
                f"{label}-buy-source",
                f"{label}-buy-root",
                leg_key=buy_leg,
                quantity=fill_quantity,
                units=110,
            ),
            evidence_digest=b"\xa7" * 32,
        ),
    )
    assert later_fill.disposition is VenueRecoveryDisposition.APPLIED
    assert later_fill.quantity_delta == fill_quantity
    assert later_fill.execution.position.raw_quantity == 4 + fill_quantity
    crossed = _reduce(
        module,
        state,
        _projection(module, later_fill, mandate),
    )
    assert crossed.state.raw_quantity == 4 + fill_quantity
    assert crossed.state.policy is policy.HARD_BAIL
    assert crossed.goal is None
    if crossing == "mandate-cap":
        assert not (
            later_fill.execution.integrity & PositionIntegrity.OVERFILL_QUARANTINE
        )
        assert crossed.state.formula_available is True
    else:
        assert later_fill.execution.integrity & PositionIntegrity.OVERFILL_QUARANTINE
        assert crossed.state.formula_available is False

    _, buy_terminal = _terminal_fixture(
        later_fill,
        effect_id=buy_effect,
        leg_key=buy_leg,
        label=f"{label}-buy",
        cumulative_quantity=fill_quantity,
    )
    _, buy_closed = _close_parent_fixture(
        buy_terminal,
        effect_id=buy_effect,
        label=f"{label}-buy",
    )
    state, projection, closed_result = _sync_transitions(
        module,
        crossed.state,
        mandate,
        (buy_terminal, buy_closed),
    )
    assert projection.blocking_effect_count == 0
    assert projection.blocking_buy_effect_count == 0
    assert closed_result.goal is None
    for index, bid in enumerate(bids, start=1):
        result = _reduce(
            module,
            state,
            projection,
            _occurrence(
                module,
                f"{label}-market-{index}",
                bid=bid,
                ask=bid + 1,
                sequence=index,
                source_time=94 + index * 6,
                evaluation_time=98 + index * 6,
            ),
        )
        state = result.state
        assert state.raw_quantity == 4 + fill_quantity
        assert state.policy is policy.HARD_BAIL
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


def test_formula_loss_discards_market_evidence_and_restores_a_fresh_branch() -> None:
    module = _protection_module()
    _, _, fill_command, fill = _owned_fill_fixture(
        label="protection-formula-loss",
        quantity=4,
        units=100,
        capacity=4,
    )
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    activated = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            "formula-loss-activation",
            bid=120,
            ask=121,
            sequence=1,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert activated.state.policy is policy.TRAIL_ACTIVE
    assert activated.state.armed_hard_bail_trigger.exact_value == Fraction(93)
    assert activated.state.trail.exact_value == Fraction(111)

    _, incompatible = _correct_owned_root(
        closed,
        label="protection-formula-loss-incompatible",
        root_fill_id=fill_command.fact.root_fill_id,
        predecessor_source_event_id=fill_command.fact.key.source_event_id,
        prior_root_quantity=4,
        resulting_quantity=4,
        units=102,
        prior_venue_cumulative=4,
        tick_units=2,
    )
    unavailable = _reduce(
        module,
        activated.state,
        _projection(module, incompatible, mandate),
    )
    assert unavailable.state.raw_quantity == 4
    assert unavailable.state.formula_available is False
    assert unavailable.state.policy is policy.HARD_BAIL
    assert unavailable.goal is None
    state = unavailable.state
    projection = _projection(module, incompatible, mandate)
    for index, bid in enumerate((92, 91), start=2):
        ignored = _reduce(
            module,
            state,
            projection,
            _occurrence(
                module,
                f"formula-loss-ignored-{index}",
                bid=bid,
                ask=bid + 1,
                sequence=index,
                source_time=94 + index * 6,
                evaluation_time=98 + index * 6,
            ),
        )
        state = ignored.state
        assert state.formula_available is False
        assert state.policy is policy.HARD_BAIL
        assert ignored.goal is None

    _, restored_transition = _correct_owned_root(
        incompatible,
        label="protection-formula-loss-restored",
        root_fill_id=fill_command.fact.root_fill_id,
        predecessor_source_event_id=SourceEventId(
            "protection-formula-loss-incompatible-source"
        ),
        prior_root_quantity=4,
        resulting_quantity=4,
        units=100,
        prior_venue_cumulative=4,
    )
    restored_projection = _projection(module, restored_transition, mandate)
    restored = _reduce(module, state, restored_projection)
    assert restored.state.formula_available is True
    assert restored.state.armed_hard_bail_trigger.exact_value == Fraction(93)
    assert restored.state.activation_price.exact_value == Fraction(108)
    assert restored.state.high_watermark.exact_value == Fraction(120)
    assert restored.state.trail.exact_value == Fraction(111)
    assert restored.state.policy is policy.HARD_BAIL
    assert restored.goal is None

    fresh_first = _reduce(
        module,
        restored.state,
        restored_projection,
        _occurrence(
            module,
            "formula-loss-fresh-1",
            bid=92,
            ask=93,
            sequence=4,
            source_time=124,
            evaluation_time=128,
        ),
    )
    assert fresh_first.goal is None
    fresh_second = _reduce(
        module,
        fresh_first.state,
        restored_projection,
        _occurrence(
            module,
            "formula-loss-fresh-2",
            bid=91,
            ask=92,
            sequence=5,
            source_time=130,
            evaluation_time=134,
        ),
    )
    assert fresh_second.state.policy is policy.HARD_BAIL
    assert fresh_second.goal is not None


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


@pytest.mark.parametrize("source_sequence", [7, None])
@pytest.mark.parametrize("first_kind", ["BEST_BID", "TRADE"])
def test_changed_delivery_context_replay_is_exact_for_every_occurrence_form(
    first_kind: str,
    source_sequence: int | None,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(
        label=f"changed-context-{first_kind.lower()}-{source_sequence}"
    )
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    occurrence = _occurrence(
        module,
        f"changed-context-{first_kind.lower()}-{source_sequence}",
        kind=first_kind,
        bid=92 if first_kind == "BEST_BID" else None,
        ask=93 if first_kind == "BEST_BID" else None,
        trade=92 if first_kind == "TRADE" else None,
        sequence=source_sequence,
    )
    first = _reduce(module, state, projection, occurrence)
    retained_before_replay = _leaf_sort_key(first.state)
    replay = _reduce(
        module, first.state, projection, replace(occurrence, evaluation_time=109)
    )
    valid_after_replay = _reduce(
        module,
        replay.state,
        projection,
        _occurrence(
            module,
            f"valid-after-{first_kind.lower()}-{source_sequence}-replay",
            bid=91,
            ask=92,
            sequence=8 if source_sequence is not None else None,
            source_time=106,
            evaluation_time=107,
        ),
    )
    disposition, policy = _required(
        module,
        "ProtectionDisposition",
        "ProtectionPolicy",
    )
    assert replay.disposition is disposition.EXACT_REPLAY
    assert _leaf_sort_key(replay.state) == retained_before_replay
    assert replay.state == first.state
    assert replay.state.commitment == first.state.commitment
    assert replay.state.policy is policy.FLOOR_ONLY
    assert replay.goal is None
    assert replay.critical_alert is None
    assert valid_after_replay.state.policy is policy.HARD_BAIL
    assert valid_after_replay.goal is not None


def test_nonadvancing_sequence_does_not_corroborate() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="nonadvancing-sequence")
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "advancing-sequence", bid=92, ask=93, sequence=7),
    )
    equal_sequence = _reduce(
        module,
        first.state,
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
    assert equal_sequence.state == first.state
    assert equal_sequence.state.commitment == first.state.commitment
    assert equal_sequence.state.policy is policy.FLOOR_ONLY
    assert equal_sequence.goal is None
    assert equal_sequence.critical_alert is None


@pytest.mark.parametrize("second_sequence", [2, None])
@pytest.mark.parametrize("first_kind", ["BEST_BID", "TRADE"])
def test_occurrence_identity_equivocation_is_refused_before_corroboration(
    first_kind: str,
    second_sequence: int | None,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(
        label=f"equivocation-{first_kind.lower()}-{second_sequence}"
    )
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    shared_id = "equivocated-source-occurrence"
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            shared_id,
            kind=first_kind,
            bid=92 if first_kind == "BEST_BID" else None,
            ask=93 if first_kind == "BEST_BID" else None,
            trade=92 if first_kind == "TRADE" else None,
            sequence=1 if second_sequence is not None else None,
            source_time=100,
            evaluation_time=104,
        ),
    )
    equivocated = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            shared_id,
            kind="BEST_BID",
            bid=91,
            ask=92,
            sequence=second_sequence,
            source_time=106,
            evaluation_time=110,
        ),
    )
    disposition, policy = _required(
        module,
        "ProtectionDisposition",
        "ProtectionPolicy",
    )
    assert equivocated.disposition is disposition.REFUSED
    assert equivocated.state == first.state
    assert equivocated.state.policy is policy.FLOOR_ONLY
    assert equivocated.goal is None
    assert equivocated.critical_alert is None

    distinct = _reduce(
        module,
        equivocated.state,
        projection,
        _occurrence(
            module,
            "equivocation-distinct-successor",
            bid=91,
            ask=92,
            sequence=3 if second_sequence is not None else None,
            source_time=112,
            evaluation_time=116,
        ),
    )
    assert distinct.state.policy is policy.HARD_BAIL
    assert distinct.goal is not None


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
    ("second_source_time", "second_evaluation_time", "triggers"),
    [
        (105, 105, True),
        (103, 104, False),
    ],
)
def test_evaluation_time_is_monotone_nondecreasing_per_market_stream(
    second_source_time: int,
    second_evaluation_time: int,
    triggers: bool,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label=f"evaluation-time-{triggers}")
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            f"evaluation-time-{triggers}-first",
            bid=92,
            ask=93,
            sequence=1,
            source_time=100,
            evaluation_time=105,
        ),
    )
    second = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            f"evaluation-time-{triggers}-second",
            bid=91,
            ask=92,
            sequence=2,
            source_time=second_source_time,
            evaluation_time=second_evaluation_time,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert (second.state.policy is policy.HARD_BAIL) is triggers
    assert (second.goal is not None) is triggers
    if not triggers:
        assert second.state == first.state


def test_new_market_epoch_owns_a_fresh_evaluation_time_watermark() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="evaluation-epoch-reset")
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    epoch_zero = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            "evaluation-epoch-zero",
            bid=100,
            ask=101,
            sequence=1,
            source_time=100,
            evaluation_time=105,
        ),
    )
    halted = _reduce(
        module,
        epoch_zero.state,
        projection,
        _occurrence(
            module,
            "evaluation-epoch-halt",
            bid=100,
            ask=101,
            sequence=2,
            source_time=106,
            evaluation_time=110,
            halted=True,
        ),
    )
    reopened = _reduce(
        module,
        halted.state,
        projection,
        _occurrence(
            module,
            "evaluation-epoch-one-first",
            bid=92,
            ask=93,
            sequence=1,
            source_time=1,
            evaluation_time=5,
            market_epoch=1,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert reopened.state.policy is policy.FLOOR_ONLY
    assert reopened.state != halted.state
    assert reopened.goal is None

    regressed = _reduce(
        module,
        reopened.state,
        projection,
        _occurrence(
            module,
            "evaluation-epoch-one-regressed",
            bid=91,
            ask=92,
            sequence=2,
            source_time=2,
            evaluation_time=4,
            market_epoch=1,
        ),
    )
    assert regressed.state == reopened.state
    assert regressed.goal is None

    valid_second = _reduce(
        module,
        regressed.state,
        projection,
        _occurrence(
            module,
            "evaluation-epoch-one-second",
            bid=91,
            ask=92,
            sequence=2,
            source_time=3,
            evaluation_time=6,
            market_epoch=1,
        ),
    )
    (urgency,) = _required(module, "ProtectionUrgency")
    assert valid_second.state.policy is policy.HARD_BAIL
    assert valid_second.goal is not None
    assert valid_second.goal.urgency is urgency.EMERGENCY


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
    ("order", "second_source_time", "second_evaluation_time", "triggers"),
    [
        ("trade-bid", 110, 204, True),
        ("trade-bid", 111, 111, False),
        ("bid-trade", 110, 204, True),
        ("bid-trade", 111, 111, False),
    ],
)
def test_trade_bid_window_is_owned_by_source_time_not_evaluation_time(
    order: str,
    second_source_time: int,
    second_evaluation_time: int,
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
            f"window-{order}-first-{second_source_time}-{second_evaluation_time}",
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
            f"window-{order}-second-{second_source_time}-{second_evaluation_time}",
            kind=second_kind.upper().replace("BID", "BEST_BID"),
            bid=91 if second_kind == "bid" else None,
            ask=92 if second_kind == "bid" else None,
            trade=91 if second_kind == "trade" else None,
            sequence=2,
            source_time=second_source_time,
            evaluation_time=second_evaluation_time,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert (second.state.policy is policy.HARD_BAIL) is triggers
    assert (second.goal is not None) is triggers


@pytest.mark.parametrize(
    ("trade_price", "bid_price"),
    [
        (92, 94),
        (94, 92),
    ],
)
def test_trade_bid_pair_with_one_price_above_trigger_cannot_trip_hard_bail(
    trade_price: int,
    bid_price: int,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    trade = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            f"mixed-threshold-trade-{trade_price}",
            kind="TRADE",
            trade=trade_price,
        ),
    )
    bid = _reduce(
        module,
        trade.state,
        projection,
        _occurrence(
            module,
            f"mixed-threshold-bid-{bid_price}",
            bid=bid_price,
            ask=bid_price + 1,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert bid.state.policy is policy.FLOOR_ONLY
    assert bid.goal is None


def test_trade_never_activates_ratchets_or_satisfies_a_trail_exit() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="protection-trade-trail-ownership")
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    favorable_trade = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            "trade-cannot-activate",
            kind="TRADE",
            trade=130,
            sequence=1,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert favorable_trade.state.policy is policy.FLOOR_ONLY
    assert favorable_trade.state.high_watermark is None
    assert favorable_trade.state.trail is None

    activated = _reduce(
        module,
        favorable_trade.state,
        projection,
        _occurrence(
            module,
            "trade-control-activation",
            bid=120,
            ask=121,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    assert activated.state.policy is policy.TRAIL_ACTIVE
    favorable_after_activation = _reduce(
        module,
        activated.state,
        projection,
        _occurrence(
            module,
            "trade-cannot-ratchet",
            kind="TRADE",
            trade=130,
            sequence=3,
            source_time=112,
            evaluation_time=116,
        ),
    )
    assert (
        favorable_after_activation.state.high_watermark
        == activated.state.high_watermark
    )
    assert favorable_after_activation.state.trail == activated.state.trail

    ratcheted = _reduce(
        module,
        favorable_after_activation.state,
        projection,
        _occurrence(
            module,
            "trade-control-ratchet",
            bid=130,
            ask=131,
            sequence=4,
            source_time=118,
            evaluation_time=122,
        ),
    )
    below_trade = _reduce(
        module,
        ratcheted.state,
        projection,
        _occurrence(
            module,
            "trade-cannot-exit",
            kind="TRADE",
            trade=110,
            sequence=5,
            source_time=124,
            evaluation_time=128,
        ),
    )
    assert below_trade.state.policy is policy.TRAIL_ACTIVE
    assert below_trade.goal is None
    one_bid = _reduce(
        module,
        below_trade.state,
        projection,
        _occurrence(
            module,
            "trade-control-one-exit-bid",
            bid=110,
            ask=111,
            sequence=6,
            source_time=130,
            evaluation_time=134,
        ),
    )
    assert one_bid.state.policy is policy.TRAIL_ACTIVE
    assert one_bid.goal is None


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


@pytest.mark.parametrize("candidate_kind", ["atr", "structure"])
def test_new_trail_governs_the_same_occurrence_that_tightens_it(
    candidate_kind: str,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label=f"same-occurrence-trail-{candidate_kind}")
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    activated = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            f"same-occurrence-trail-{candidate_kind}-activation",
            bid=120,
            ask=121,
            sequence=1,
        ),
    )
    assert activated.state.trail.exact_value == Fraction(111)

    tightened = _reduce(
        module,
        activated.state,
        projection,
        _occurrence(
            module,
            f"same-occurrence-trail-{candidate_kind}-tighten",
            bid=115,
            ask=116,
            sequence=2,
            source_time=106,
            evaluation_time=110,
            atr_distance=1 if candidate_kind == "atr" else None,
            structure_trail=118 if candidate_kind == "structure" else None,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert tightened.state.policy is policy.TRAIL_ACTIVE
    assert tightened.state.high_watermark.exact_value == Fraction(120)
    assert tightened.state.trail.exact_value == Fraction(118)
    assert tightened.goal is None

    exited = _reduce(
        module,
        tightened.state,
        projection,
        _occurrence(
            module,
            f"same-occurrence-trail-{candidate_kind}-second-below",
            bid=114,
            ask=115,
            sequence=3,
            source_time=112,
            evaluation_time=116,
        ),
    )
    (urgency,) = _required(module, "ProtectionUrgency")
    assert exited.state.policy is policy.EXIT_NORMAL
    assert exited.goal is not None
    assert exited.goal.urgency is urgency.NORMAL
    assert exited.goal.guard == mandate.normal_guard


def test_structure_can_be_the_exact_dominant_trail_candidate() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="protection-structure-dominant")
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    activated = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            "structure-dominant-activation",
            bid=120,
            ask=121,
            sequence=1,
            atr_distance=10,
            structure_trail=118,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert activated.state.policy is policy.TRAIL_ACTIVE
    assert activated.state.high_watermark.exact_value == Fraction(120)
    assert activated.state.trail.exact_value == Fraction(118)


def test_nonunit_tick_rounds_each_trail_candidate_once_and_forgets_missing_inputs() -> (
    None
):
    module = _protection_module()
    tick = TickMetadata(tick_units=PriceUnits(2), scale=SCALE)
    fill = _owned_fill_transition(
        label="protection-nonunit-trail",
        tick_units=2,
    )
    mandate, _, state = _start(module, fill, _mandate(module, tick=tick))
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    activated = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            "nonunit-trail-activation",
            bid=120,
            ask=122,
            sequence=1,
            atr_distance=2,
            structure_trail=114,
            tick_units=2,
        ),
    )
    assert activated.state.high_watermark.exact_value == Fraction(120)
    assert activated.state.trail.exact_value == Fraction(116)
    missing = _reduce(
        module,
        activated.state,
        projection,
        _occurrence(
            module,
            "nonunit-trail-missing",
            bid=122,
            ask=124,
            sequence=2,
            source_time=106,
            evaluation_time=110,
            tick_units=2,
        ),
    )
    assert missing.state.high_watermark.exact_value == Fraction(122)
    assert missing.state.trail.exact_value == Fraction(116)


@pytest.mark.parametrize(
    ("case", "field_name", "value"),
    [
        ("atr-nonpositive", "atr_distance", _price(0)),
        ("atr-wrong-tick", "atr_distance", _price(3, tick_units=2)),
        ("structure-nonpositive", "structure_trail", _price(0)),
        ("structure-above-high", "structure_trail", _price(122)),
        ("structure-wrong-tick", "structure_trail", _price(115, tick_units=2)),
    ],
)
def test_invalid_optional_trail_components_are_omitted_without_authority(
    case: str,
    field_name: str,
    value: ReportedPrice,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label=f"invalid-optional-{case}")
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    occurrence = _occurrence(
        module,
        f"invalid-optional-{case}",
        bid=120,
        ask=121,
        sequence=1,
    )
    result = _reduce(
        module,
        state,
        projection,
        replace(occurrence, **{field_name: value}),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert result.state.policy is policy.TRAIL_ACTIVE
    assert result.state.high_watermark.exact_value == Fraction(120)
    assert result.state.trail.exact_value == Fraction(111)
    assert result.goal is None


def test_invalid_optional_components_cannot_suppress_core_hard_bail_evidence() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="invalid-optional-hard-bail")
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    for index, bid in enumerate((92, 91), start=1):
        occurrence = _occurrence(
            module,
            f"invalid-optional-hard-bail-{index}",
            bid=bid,
            ask=bid + 1,
            sequence=index,
            source_time=94 + index * 6,
            evaluation_time=98 + index * 6,
        )
        result = _reduce(
            module,
            state,
            projection,
            replace(occurrence, atr_distance=_price(0)),
        )
        state = result.state
    (policy,) = _required(module, "ProtectionPolicy")
    assert state.policy is policy.HARD_BAIL
    assert result.goal is not None


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
    assert bought_result.state.armed_hard_bail_trigger.exact_value == Fraction(105)
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
    assert corrected_result.state.armed_hard_bail_trigger.exact_value == Fraction(105)
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
    assert busted_result.state.armed_hard_bail_trigger.exact_value == Fraction(105)
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


@pytest.mark.parametrize("exit_kind", ["normal", "emergency"])
def test_any_live_sell_effect_suppresses_goal_until_leg_and_parent_close(
    exit_kind: str,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label=f"all-effect-{exit_kind}")
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, _, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    sell_chain, sell_effect, sell_leg, _ = _append_needs_review_effect(
        closed,
        prefix=f"all-effect-{exit_kind}-sell",
        side=ExecutionSide.SELL,
        quantity=4,
    )
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        sell_chain,
    )
    assert projection.blocking_effect_count == 1
    assert projection.blocking_buy_effect_count == 0
    if exit_kind == "normal":
        bids = (120, 110, 109)
    else:
        bids = (92, 91)
    result = None
    for index, bid in enumerate(bids, start=1):
        result = _reduce(
            module,
            state,
            projection,
            _occurrence(
                module,
                f"all-effect-{exit_kind}-{index}",
                bid=bid,
                ask=bid + 1,
                sequence=index,
                source_time=94 + index * 6,
                evaluation_time=98 + index * 6,
            ),
        )
        state = result.state
    assert result is not None
    policy, urgency = _required(module, "ProtectionPolicy", "ProtectionUrgency")
    expected_policy = policy.EXIT_NORMAL if exit_kind == "normal" else policy.HARD_BAIL
    expected_urgency = urgency.NORMAL if exit_kind == "normal" else urgency.EMERGENCY
    expected_guard = (
        mandate.normal_guard if exit_kind == "normal" else mandate.emergency_guard
    )
    assert result.state.policy is expected_policy
    assert result.state.waiting_buy_resolution is False
    assert result.goal is None

    _, sell_terminal = _terminal_fixture(
        sell_chain[-1],
        effect_id=sell_effect,
        leg_key=sell_leg,
        label=f"all-effect-{exit_kind}-sell",
        cumulative_quantity=0,
    )
    terminal_result = _reduce(
        module,
        state,
        _projection(module, sell_terminal, mandate),
    )
    assert terminal_result.state.policy is expected_policy
    assert terminal_result.goal is None
    _, sell_closed = _close_parent_fixture(
        sell_terminal,
        effect_id=sell_effect,
        label=f"all-effect-{exit_kind}-sell",
    )
    released = _reduce(
        module,
        terminal_result.state,
        _projection(module, sell_closed, mandate),
    )
    assert released.state.policy is expected_policy
    assert released.goal is not None
    assert released.goal.urgency is expected_urgency
    assert released.goal.guard == expected_guard

    late_leg = VenueLegKey(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        order_id=OrderId(f"all-effect-{exit_kind}-late-sell-leg"),
    )
    invalidated_sell = venue_fixtures.apply_venue_recovery_input(
        sell_closed.book,
        sell_closed.execution,
        DiscoverVenueLeg(
            input_id=VenueInputId(f"all-effect-{exit_kind}-late-sell-input"),
            effect_id=sell_effect,
            leg_key=late_leg,
            observation_id=VenueObservationId(
                f"all-effect-{exit_kind}-late-sell-observation"
            ),
        ),
    )
    assert (
        invalidated_sell.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    )
    assert (
        invalidated_sell.book.effect(sell_effect).acceptance_set_state
        is AcceptanceSetState.INVALIDATED
    )
    invalidated_projection = _projection(module, invalidated_sell, mandate)
    assert invalidated_projection.blocking_effect_count == 1
    assert invalidated_projection.blocking_buy_effect_count == 0
    blocked_again = _reduce(
        module,
        released.state,
        invalidated_projection,
    )
    assert blocked_again.state.policy is expected_policy
    assert blocked_again.state.waiting_buy_resolution is False
    assert blocked_again.goal is None
    assert blocked_again.critical_alert is None


@pytest.mark.parametrize("exit_kind", ["normal", "emergency"])
def test_partial_sell_economics_rebind_each_successor_goal_to_exact_residual(
    exit_kind: str,
) -> None:
    module = _protection_module()
    label = f"exact-sell-residual-{exit_kind}"
    fill = _owned_fill_transition(label=label)
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    bids = (120, 110, 109) if exit_kind == "normal" else (92, 91)
    exited = None
    for index, bid in enumerate(bids, start=1):
        exited = _reduce(
            module,
            state,
            projection,
            _occurrence(
                module,
                f"{label}-exit-{index}",
                bid=bid,
                ask=bid + 1,
                sequence=index,
                source_time=94 + index * 6,
                evaluation_time=98 + index * 6,
            ),
        )
        state = exited.state
    assert exited is not None and exited.goal is not None
    policy, urgency = _required(module, "ProtectionPolicy", "ProtectionUrgency")
    expected_policy = policy.EXIT_NORMAL if exit_kind == "normal" else policy.HARD_BAIL
    expected_urgency = urgency.NORMAL if exit_kind == "normal" else urgency.EMERGENCY
    expected_guard = (
        mandate.normal_guard if exit_kind == "normal" else mandate.emergency_guard
    )
    assert exited.state.policy is expected_policy
    assert exited.goal.residual == Quantity(4)
    assert exited.goal.urgency is expected_urgency
    assert exited.goal.guard == expected_guard

    sell_chain, sell_effect, sell_leg, _ = _append_needs_review_effect(
        closed,
        prefix=f"{label}-effect",
        side=ExecutionSide.SELL,
        quantity=4,
    )
    state, _, blocked = _sync_transitions(
        module,
        state,
        mandate,
        sell_chain,
    )
    assert blocked.goal is None

    sell_fact = venue_fixtures._broker_fill(
        f"{label}-fill-source",
        f"{label}-fill-root",
        leg_key=sell_leg,
        side=ExecutionSide.SELL,
        quantity=1,
        units=110,
    )
    partial_fill = venue_fixtures.apply_venue_recovery_input(
        sell_chain[-1].book,
        sell_chain[-1].execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId(f"{label}-fill-input"),
            effect_id=sell_effect,
            leg_key=sell_leg,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(1),
            fact=sell_fact,
            evidence_digest=b"\xa1" * 32,
        ),
    )
    assert partial_fill.quantity_delta == -1
    assert partial_fill.execution.position.raw_quantity == 3
    partial = _reduce(
        module,
        state,
        _projection(module, partial_fill, mandate),
    )
    assert partial.state.policy is expected_policy
    assert partial.state.raw_quantity == 3
    assert partial.goal is None

    _, sell_terminal = _terminal_fixture(
        partial_fill,
        effect_id=sell_effect,
        leg_key=sell_leg,
        label=f"{label}-effect",
        cumulative_quantity=1,
    )
    terminal_result = _reduce(
        module,
        partial.state,
        _projection(module, sell_terminal, mandate),
    )
    assert terminal_result.goal is None
    _, sell_closed = _close_parent_fixture(
        sell_terminal,
        effect_id=sell_effect,
        label=f"{label}-effect",
    )
    released = _reduce(
        module,
        terminal_result.state,
        _projection(module, sell_closed, mandate),
    )
    assert released.state.policy is expected_policy
    assert released.goal is not None
    assert released.goal.residual == Quantity(3)
    assert released.goal.urgency is expected_urgency
    assert released.goal.guard == expected_guard
    assert released.goal.execution_commitment == sell_closed.execution.commitment

    correction, corrected = _correct_owned_root(
        sell_closed,
        label=f"{label}-correction",
        root_fill_id=sell_fact.root_fill_id,
        predecessor_source_event_id=sell_fact.key.source_event_id,
        prior_root_quantity=1,
        resulting_quantity=2,
        units=110,
        prior_venue_cumulative=1,
        effect_id=sell_effect,
        leg_key=sell_leg,
        scope=sell_fact.scope,
        closure_id=ClosureId(f"{label}-correction-closure"),
        evidence_reference=EvidenceReference(f"{label}-correction-evidence"),
    )
    assert corrected.quantity_delta == -1
    assert corrected.execution.position.raw_quantity == 2
    corrected_result = _reduce(
        module,
        released.state,
        _projection(module, corrected, mandate),
    )
    assert corrected_result.state.policy is expected_policy
    assert corrected_result.goal is not None
    assert corrected_result.goal.residual == Quantity(2)
    assert corrected_result.goal.urgency is expected_urgency
    assert corrected_result.goal.guard == expected_guard
    assert corrected_result.goal.execution_commitment == corrected.execution.commitment

    _, busted = _bust_owned_root(
        corrected,
        label=f"{label}-bust",
        root_fill_id=sell_fact.root_fill_id,
        predecessor_source_event_id=correction.fact.key.source_event_id,
        prior_root_quantity=2,
        prior_venue_cumulative=2,
        effect_id=sell_effect,
        leg_key=sell_leg,
        scope=sell_fact.scope,
        closure_id=ClosureId(f"{label}-bust-closure"),
        evidence_reference=EvidenceReference(f"{label}-bust-evidence"),
    )
    assert busted.quantity_delta == 2
    assert busted.execution.position.raw_quantity == 4
    busted_result = _reduce(
        module,
        corrected_result.state,
        _projection(module, busted, mandate),
    )
    assert busted_result.state.policy is expected_policy
    assert busted_result.goal is not None
    assert busted_result.goal.residual == Quantity(4)
    assert busted_result.goal.urgency is expected_urgency
    assert busted_result.goal.guard == expected_guard
    assert busted_result.goal.execution_commitment == busted.execution.commitment


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


@pytest.mark.parametrize(
    "binding",
    [
        "mandate_id",
        "position_scope",
        "session_id",
        "configuration_version",
        "loss_fraction",
        "approved_gain",
        "percent_trail_fraction",
        "atr_multiple",
        "normal_guard_id",
        "normal_guard_policy_commitment",
        "emergency_guard_id",
        "emergency_guard_policy_commitment",
        "evidence_source",
        "evidence_max_age",
        "evidence_window",
        "evidence_max_step",
        "maximum_quantity",
        "maximum_goal_rate",
        "deadline",
        "execution_quantity",
        "execution_price",
        "exit_provenance",
    ],
)
def test_protection_commitment_binds_each_retained_authority_independently(
    binding: str,
) -> None:
    module = _protection_module()
    baseline_mandate = _mandate(module)
    _, baseline_closed, baseline_state, baseline_goal = _emergency_goal_fixture(
        module,
        label="goal-binding-sensitivity",
        mandate=baseline_mandate,
    )
    mandate_kwargs: dict[str, object] = {}
    fixture_kwargs: dict[str, object] = {}
    market_label: str | None = None
    if binding == "mandate_id":
        mandate_kwargs["mandate_id"] = MandateId("protection-mandate-v2")
    elif binding == "position_scope":
        changed_scope = PositionScope(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            symbol_id=type(SYMBOL)("MSFT"),
        )
        mandate_kwargs["position_scope"] = changed_scope
        fixture_kwargs["position_scope"] = changed_scope
    elif binding == "session_id":
        mandate_kwargs["session_id"] = execution_core.SessionId("session-rth-2")
    elif binding == "configuration_version":
        mandate_kwargs["configuration_version"] = "protection-v2"
    elif binding == "loss_fraction":
        mandate_kwargs["loss_fraction"] = Fraction(1, 20)
    elif binding == "approved_gain":
        mandate_kwargs["approved_gain"] = Fraction(1, 10)
    elif binding == "percent_trail_fraction":
        mandate_kwargs["percent_trail_fraction"] = Fraction(1, 10)
    elif binding == "atr_multiple":
        mandate_kwargs["atr_multiple"] = Fraction(3)
    elif binding == "normal_guard_id":
        changed_guard = replace(
            baseline_mandate.normal_guard,
            guard_id="normal-guard-v2",
        )
        assert (
            changed_guard.policy_commitment
            == baseline_mandate.normal_guard.policy_commitment
        )
        mandate_kwargs["normal_guard"] = changed_guard
    elif binding == "normal_guard_policy_commitment":
        changed_guard = replace(
            baseline_mandate.normal_guard,
            policy_commitment=b"N" * 32,
        )
        assert changed_guard.guard_id == baseline_mandate.normal_guard.guard_id
        mandate_kwargs["normal_guard"] = changed_guard
    elif binding == "emergency_guard_id":
        changed_guard = replace(
            baseline_mandate.emergency_guard,
            guard_id="emergency-guard-v2",
        )
        assert (
            changed_guard.policy_commitment
            == baseline_mandate.emergency_guard.policy_commitment
        )
        mandate_kwargs["emergency_guard"] = changed_guard
    elif binding == "emergency_guard_policy_commitment":
        changed_guard = replace(
            baseline_mandate.emergency_guard,
            policy_commitment=b"E" * 32,
        )
        assert changed_guard.guard_id == baseline_mandate.emergency_guard.guard_id
        mandate_kwargs["emergency_guard"] = changed_guard
    elif binding == "evidence_source":
        mandate_kwargs["source_id"] = execution_core.MarketDataSourceId("sip-backup")
    elif binding == "evidence_max_age":
        mandate_kwargs["max_age"] = 20
    elif binding == "evidence_window":
        mandate_kwargs["corroboration_window"] = 20
    elif binding == "evidence_max_step":
        mandate_kwargs["max_step_fraction"] = Fraction(1, 3)
    elif binding == "maximum_quantity":
        mandate_kwargs["maximum_quantity"] = 21
    elif binding == "maximum_goal_rate":
        mandate_kwargs["maximum_goal_rate"] = 5
    elif binding == "deadline":
        mandate_kwargs["deadline"] = 1_001
    elif binding == "execution_quantity":
        fixture_kwargs["fill_quantity"] = 5
    elif binding == "execution_price":
        fixture_kwargs["fill_units"] = 102
    else:
        market_label = "goal-binding-sensitivity-other-exit"

    changed_mandate = _mandate(module, **mandate_kwargs)
    _, changed_closed, changed_state, changed_goal = _emergency_goal_fixture(
        module,
        label="goal-binding-sensitivity",
        mandate=changed_mandate,
        market_label=market_label,
        **fixture_kwargs,
    )
    assert baseline_goal.execution_commitment == baseline_closed.execution.commitment
    assert baseline_goal.protection_commitment == baseline_state.commitment
    assert changed_goal.execution_commitment == changed_closed.execution.commitment
    if binding in {"execution_quantity", "execution_price", "position_scope"}:
        assert changed_goal.execution_commitment != baseline_goal.execution_commitment
    else:
        assert changed_goal.execution_commitment == baseline_goal.execution_commitment
    assert changed_goal.protection_commitment == changed_state.commitment
    assert changed_goal.protection_commitment != baseline_goal.protection_commitment
    assert changed_goal.side is ExecutionSide.SELL
    assert changed_goal.residual == Quantity(changed_state.raw_quantity)
    assert changed_goal.guard == changed_mandate.emergency_guard
    assert changed_goal.deadline == changed_mandate.deadline
    assert changed_goal.session_id == changed_mandate.session_id
    assert changed_goal.mandate_id == changed_mandate.mandate_id
    assert changed_goal.maximum_goal_rate == changed_mandate.maximum_goal_rate


def test_state_replay_rejects_scope_only_mandate_forgery_without_execution_confound() -> (
    None
):
    module = _protection_module()
    fill = _owned_fill_transition(label="state-scope-only-forgery")
    mandate, projection, state = _start(module, fill)
    changed_scope = PositionScope(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        symbol_id=type(SYMBOL)("MSFT"),
    )
    changed_mandate = replace(mandate, position_scope=changed_scope)
    for retained in fields(mandate):
        if retained.name == "position_scope":
            assert getattr(changed_mandate, retained.name) != getattr(
                mandate,
                retained.name,
            )
        else:
            assert getattr(changed_mandate, retained.name) == getattr(
                mandate,
                retained.name,
            )

    forged = _clone_opaque(state, mandate=changed_mandate)
    assert forged.execution_commitment == state.execution_commitment
    assert forged.raw_quantity == state.raw_quantity
    result = _reduce(module, forged, projection)
    (disposition,) = _required(module, "ProtectionDisposition")
    assert result.disposition is disposition.REFUSED
    assert result.state == forged
    assert result.goal is None
    assert result.critical_alert is None


@pytest.mark.parametrize("tick_leaf", ["tick_units", "scale"])
def test_protection_commitment_binds_each_nested_tick_authority_leaf(
    tick_leaf: str,
) -> None:
    module = _protection_module()
    overfill = _owned_fill_transition(
        label=f"goal-binding-{tick_leaf}-overfill",
        quantity=5,
        capacity=4,
    )
    assert overfill.execution.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    baseline_mandate = _mandate(module)
    if tick_leaf == "tick_units":
        changed_tick = TickMetadata(tick_units=PriceUnits(2), scale=SCALE)
        assert changed_tick.scale == baseline_mandate.tick.scale
        assert changed_tick.tick_units != baseline_mandate.tick.tick_units
    else:
        changed_scale = PriceScale(Decimal("0.01"))
        changed_tick = TickMetadata(tick_units=PriceUnits(1), scale=changed_scale)
        assert changed_tick.tick_units == baseline_mandate.tick.tick_units
        assert changed_tick.scale != baseline_mandate.tick.scale
    changed_mandate = _mandate(module, tick=changed_tick)
    for retained in fields(baseline_mandate):
        if retained.name != "tick":
            assert getattr(changed_mandate, retained.name) == getattr(
                baseline_mandate,
                retained.name,
            )

    _, baseline_projection, baseline_state = _start(
        module,
        overfill,
        baseline_mandate,
    )
    _, changed_projection, changed_state = _start(
        module,
        overfill,
        changed_mandate,
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert baseline_projection.execution_commitment == overfill.execution.commitment
    assert changed_projection.execution_commitment == overfill.execution.commitment
    assert baseline_state.execution_commitment == changed_state.execution_commitment
    assert baseline_state.raw_quantity == changed_state.raw_quantity == 5
    assert baseline_state.policy is changed_state.policy is policy.HARD_BAIL
    assert baseline_state.formula_available is changed_state.formula_available is False
    for retained in fields(baseline_state):
        if retained.name.startswith("_") or retained.name in {"mandate", "commitment"}:
            continue
        assert getattr(changed_state, retained.name) == getattr(
            baseline_state,
            retained.name,
        )
    assert changed_state.commitment != baseline_state.commitment


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
    value_names = (
        "EvidencePolicy",
        "ExecutionGuard",
        "MarketOccurrence",
        "ProtectionMandate",
        "PositionProtectionState",
        "ProtectionVenueProjection",
        "ExecutionGoal",
        "ProtectionTransition",
    )
    for name in value_names:
        (value_type,) = _required(module, name)
        assert forbidden.isdisjoint(field.name for field in fields(value_type))

    venue_transition = _owned_fill_transition(label="passive-value-surface")
    mandate, projection, state = _start(module, venue_transition)
    goal_type, urgency = _required(module, "ExecutionGoal", "ProtectionUrgency")
    goal = goal_type(
        side=ExecutionSide.SELL,
        residual=Quantity(state.raw_quantity),
        urgency=urgency.NORMAL,
        guard=mandate.normal_guard,
        deadline=mandate.deadline,
        session_id=mandate.session_id,
        mandate_id=mandate.mandate_id,
        maximum_goal_rate=mandate.maximum_goal_rate,
        execution_commitment=state.execution_commitment,
        protection_commitment=state.commitment,
    )
    occurrence = _occurrence(
        module,
        "passive-value-occurrence",
        bid=120,
        ask=121,
    )
    replay = _reduce(module, state, projection)
    allowed_shapes = {
        value_type: tuple(retained.name for retained in fields(value_type))
        for value_type in _required(module, *value_names)
    }
    market_source_type, occurrence_id_type, session_type = _required(
        execution_core,
        "MarketDataSourceId",
        "MarketOccurrenceId",
        "SessionId",
    )
    trusted_leaf_types = frozenset(
        {
            ExecutionSnapshot,
            ExecutionSide,
            MandateId,
            PositionIntegrity,
            PositionScope,
            PriceScale,
            PriceUnits,
            Quantity,
            ReportedPrice,
            TickMetadata,
            market_source_type,
            occurrence_id_type,
            session_type,
        }
    )
    protection_enum_types = _required(
        module,
        "MarketKind",
        "ProtectionPolicy",
        "ProtectionUrgency",
        "ProtectionDisposition",
        "ProtectionAlert",
    )
    allowed_enum_shapes = dict(
        zip(
            protection_enum_types,
            (
                ("BEST_BID", "TRADE"),
                ("FLOOR_ONLY", "TRAIL_ACTIVE", "EXIT_NORMAL", "HARD_BAIL", "FLAT"),
                ("NORMAL", "EMERGENCY"),
                ("APPLIED", "EXACT_REPLAY", "STALE", "REFUSED"),
                ("LATE_POSITIVE_AFTER_FLAT",),
            ),
            strict=True,
        )
    )
    for retained in (mandate, projection, state, goal, occurrence, replay):
        _assert_passive_value_graph(
            retained,
            allowed_shapes=allowed_shapes,
            trusted_leaf_types=trusted_leaf_types,
            allowed_enum_shapes=allowed_enum_shapes,
        )
