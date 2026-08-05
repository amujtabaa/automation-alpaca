"""RED-first contracts for the pure WO-0148 protection semantic center.

The suite uses only explicit immutable values and the genuine venue-recovery
reducer.  It imports the not-yet-implemented protection vocabulary lazily so
every example is collected and independently failure-capable before production
code exists.  No clock, database, broker, adapter, or runtime fixture is used.
"""

from __future__ import annotations

import __future__
import ast
import builtins
from collections.abc import Callable
from copy import copy
from dataclasses import (
    MISSING,
    FrozenInstanceError,
    dataclass,
    field,
    fields,
    is_dataclass,
    make_dataclass,
    replace,
)
from decimal import Decimal
import dis
from enum import Enum
from fractions import Fraction
from hashlib import sha256
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
    EngageKill,
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
    _PersistentKeyMap,
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
from tests.execution_core import test_authority as authority_fixtures
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
_U64_MAX = (1 << 64) - 1
_MARKET_OCCURRENCE_FIELDS = (
    "occurrence_id",
    "source_id",
    "stream_generation",
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
)
_MARKET_OCCURRENCE_INIT_FIELDS = _MARKET_OCCURRENCE_FIELDS[1:]
_ADR023_MARKET_CURSOR_FIELD_ORDER = (
    "_market_occurrence_epoch",
    "_market_committed_epoch",
    "_market_expected_epoch",
    "_market_source_sequence",
    "_market_source_time",
    "_market_evaluation_time",
    "_market_occurrence_identity",
    "_market_halted",
    "_market_baseline_required",
    "_market_exhausted",
    "_market_last_primary",
    "_hard_bid_identity",
    "_hard_bid_source_time",
    "_trade_identity",
    "_trade_source_time",
    "_trail_bid_identity",
    "_trail_bid_source_time",
)
assert len(_ADR023_MARKET_CURSOR_FIELD_ORDER) == len(
    set(_ADR023_MARKET_CURSOR_FIELD_ORDER)
)
_ADR023_MARKET_CURSOR_FIELDS = frozenset(_ADR023_MARKET_CURSOR_FIELD_ORDER)
_ADR023_OPTIONAL_MARKET_CURSOR_FIELDS = (
    "_market_occurrence_epoch",
    "_market_committed_epoch",
    "_market_expected_epoch",
    "_market_source_sequence",
    "_market_source_time",
    "_market_evaluation_time",
    "_market_occurrence_identity",
    "_market_last_primary",
    "_hard_bid_identity",
    "_hard_bid_source_time",
    "_trade_identity",
    "_trade_source_time",
    "_trail_bid_identity",
    "_trail_bid_source_time",
)
_ADR023_STATE_FIELDS = (
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
    "_cursor_ordinal",
    "_cursor_head",
    *_ADR023_MARKET_CURSOR_FIELD_ORDER,
    "_exit_provenance",
)
_ADR023_CURSOR_PREIMAGE_PARAMETERS = (
    "stream_generation",
    "sequence_mode",
    "occurrence_epoch",
    "committed_epoch",
    "expected_epoch",
    "source_sequence",
    "source_time",
    "evaluation_time",
    "occurrence_identity",
    "halted",
    "baseline_required",
    "exhausted",
    "last_primary_commitment",
    "hard_bid_identity",
    "hard_bid_source_time",
    "trade_identity",
    "trade_source_time",
    "trail_bid_identity",
    "trail_bid_source_time",
)
_ADR023_STATE_CURSOR_PARAMETERS = tuple(
    "last_primary" if name == "last_primary_commitment" else name
    for name in _ADR023_CURSOR_PREIMAGE_PARAMETERS
)
_ADR023_LAST_PRIMARY_COMMITMENT_SOURCE = (
    "None if last_primary is None else _encode_reported_price(last_primary)"
)
_ADR023_STATE_COMMITMENT_PARAMETERS = (
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
    "cursor_ordinal",
    "cursor_head",
    *_ADR023_STATE_CURSOR_PARAMETERS,
    "exit_provenance",
)
_ADR023_STATE_COMMITMENT_PART_SOURCES = (
    "_encode_text(policy.value)",
    "_commit_mandate(mandate)",
    "_encode_int(raw_quantity)",
    "execution_commitment",
    "_encode_int(1 if formula_available else 0)",
    "_encode_reported_price(armed_hard_bail_trigger)",
    "_encode_reported_price(activation_price)",
    "_encode_reported_price(high_watermark)",
    "_encode_reported_price(trail)",
    "_encode_int(1 if waiting_buy_resolution else 0)",
    "_encode_int(cursor_ordinal)",
    "cursor_head",
    "<CURSOR_DIGEST>",
    "exit_provenance",
)
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
    stream_generation: object | None = None,
    sequence_mode: str = "SEQUENCED",
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
    source_type, generation_type = _required(
        execution_core,
        "MarketDataSourceId",
        "MarketStreamGenerationId",
    )
    (session_type,) = _required(execution_core, "SessionId")
    (sequence_mode_type,) = _required(module, "MarketSequenceMode")
    evidence = evidence_type(
        source_id=(source_id if source_id is not None else source_type("sip-primary")),
        stream_generation=(
            stream_generation
            if stream_generation is not None
            else generation_type("11" * 32)
        ),
        sequence_mode=getattr(sequence_mode_type, sequence_mode),
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
    mandate_id: MandateId = MANDATE_ID,
):
    if mandate_id == MANDATE_ID:
        book, execution = venue_fixtures._seed_needs_review(capacity=capacity)
    else:
        book = VenueRecoveryBook.empty(VENUE_SCOPE)
        execution = ExecutionSnapshot.flat(POSITION_SCOPE)
        commands = (
            RequestedEffect(
                input_id=VenueInputId("request-effect"),
                effect_id=BASE_EFFECT,
                request_occurrence_id=venue_fixtures.REQUEST,
                mandate_id=mandate_id,
                kind=EffectKind.SUBMIT,
                client_order_id=venue_fixtures.CLIENT,
                symbol_id=SYMBOL,
                side=ExecutionSide.BUY,
                quantity=Quantity(capacity),
                economic_scope=b"AAPL|BUY-or-SELL|fixed-order-capacity",
            ),
            RecordDispatchClaim(
                input_id=VenueInputId("claim-effect"),
                effect_id=BASE_EFFECT,
                claim_occurrence_id=BASE_CLAIM,
            ),
            RecordTransportOutcome(
                input_id=VenueInputId("transport-unknown"),
                effect_id=BASE_EFFECT,
                state=BrokerEffectState.OUTCOME_UNKNOWN,
            ),
            DiscoverVenueLeg(
                input_id=VenueInputId("discover-leg-1"),
                effect_id=BASE_EFFECT,
                leg_key=BASE_LEG,
                observation_id=VenueObservationId("acceptance-observation-1"),
            ),
            ObserveVenueStatus(
                input_id=VenueInputId("needs-review-leg-1"),
                leg_key=BASE_LEG,
                status=VenueAttemptState.NEEDS_REVIEW,
                observation_id=VenueObservationId("review-observation-1"),
                cumulative_quantity=Quantity(0),
            ),
            RecordTransportOutcome(
                input_id=VenueInputId("transport-needs-review"),
                effect_id=BASE_EFFECT,
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
    mandate_id: MandateId = MANDATE_ID,
):
    return _owned_fill_fixture(
        label=label,
        quantity=quantity,
        units=units,
        capacity=capacity,
        tick_units=tick_units,
        scale=scale,
        mandate_id=mandate_id,
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
    *,
    establish_baseline: bool = True,
) -> tuple[object, object, object]:
    current_mandate = mandate or _mandate(module)
    projection = _projection(module, venue_transition, current_mandate)
    (initialize,) = _required(module, "initialize_position_protection")
    state = initialize(current_mandate, projection)
    if establish_baseline:
        tick_units = current_mandate.tick.tick_units.value
        baseline_bid = ((100 + tick_units - 1) // tick_units) * tick_units
        sequence = (
            0
            if current_mandate.evidence_policy.sequence_mode.value == "SEQUENCED"
            else None
        )
        baseline = _occurrence(
            module,
            "fixture-initial-baseline",
            bid=baseline_bid,
            ask=baseline_bid + tick_units,
            sequence=sequence,
            source_time=0,
            evaluation_time=0,
            market_epoch=0,
            tick_units=tick_units,
            scale=current_mandate.tick.scale,
            source_id=current_mandate.evidence_policy.source_id,
            stream_generation=current_mandate.evidence_policy.stream_generation,
            position_scope=current_mandate.position_scope,
            session_id=current_mandate.session_id,
        )
        applied = _reduce_market(module, state, projection, baseline)
        (disposition,) = _required(module, "ProtectionDisposition")
        assert applied.disposition is disposition.APPLIED
        assert applied.goal is None
        assert applied.critical_alert is None
        state = applied.state
    return current_mandate, projection, state


def _reduce_projection(
    module: ModuleType,
    state: object,
    projection: object,
) -> object:
    (reducer,) = _required(module, "reduce_position_protection")
    before = (state, projection)
    first = reducer(state, projection)
    second = reducer(state, projection)
    assert first == second
    assert before == (state, projection)
    return first


def _reduce_market(
    module: ModuleType,
    state: object,
    projection: object,
    occurrence: object,
) -> object:
    (reducer,) = _required(module, "reduce_position_protection_market")
    before = (state, projection, occurrence)
    first = reducer(state, projection, occurrence)
    second = reducer(state, projection, occurrence)
    assert first == second
    assert before == (state, projection, occurrence)
    return first


def _invalidate_market(
    module: ModuleType,
    state: object,
    projection: object,
) -> object:
    (invalidate,) = _required(module, "invalidate_position_protection_market")
    before = (state, projection)
    first = invalidate(state, projection)
    second = invalidate(state, projection)
    assert first == second
    assert before == (state, projection)
    return first


def _reduce(
    module: ModuleType,
    state: object,
    projection: object,
    occurrence: object | None = None,
) -> object:
    if occurrence is None:
        return _reduce_projection(module, state, projection)
    return _reduce_market(module, state, projection, occurrence)


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
    stream_generation: object | None = None,
    position_scope: PositionScope = POSITION_SCOPE,
    session_id: object | None = None,
) -> object:
    del label
    market_kind, occurrence_type = _required(module, "MarketKind", "MarketOccurrence")
    source_id_type, generation_type, session_type = _required(
        execution_core,
        "MarketDataSourceId",
        "MarketStreamGenerationId",
        "SessionId",
    )
    return occurrence_type(
        source_id=(
            source_id if source_id is not None else source_id_type("sip-primary")
        ),
        stream_generation=(
            stream_generation
            if stream_generation is not None
            else generation_type("11" * 32)
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


def _routed_occurrence(
    module: ModuleType,
    mandate: object,
    label: str,
    *,
    bid: int | None = 100,
    ask: int | None = 101,
    sequence: int | None = 1,
    source_time: int = 1,
    evaluation_time: int = 1,
    market_epoch: int = 0,
    halted: bool = False,
    kind: str = "BEST_BID",
    trade: int | None = None,
    atr_distance: int | None = None,
    structure_trail: int | None = None,
    source_id: object | None = None,
    stream_generation: object | None = None,
    position_scope: PositionScope | None = None,
    session_id: object | None = None,
) -> object:
    return _occurrence(
        module,
        label,
        kind=kind,
        bid=None if kind == "TRADE" else bid,
        ask=None if kind == "TRADE" else ask,
        trade=trade if kind == "TRADE" else None,
        sequence=sequence,
        source_time=source_time,
        evaluation_time=evaluation_time,
        market_epoch=market_epoch,
        atr_distance=atr_distance,
        structure_trail=structure_trail,
        tick_units=mandate.tick.tick_units.value,
        scale=mandate.tick.scale,
        halted=halted,
        source_id=(
            mandate.evidence_policy.source_id if source_id is None else source_id
        ),
        stream_generation=(
            mandate.evidence_policy.stream_generation
            if stream_generation is None
            else stream_generation
        ),
        position_scope=(
            mandate.position_scope if position_scope is None else position_scope
        ),
        session_id=mandate.session_id if session_id is None else session_id,
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
    attempt = transition.book.active_attempt(BASE_LEG)
    assert attempt is not None
    _, terminal = _terminal_fixture(
        transition,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-base",
        cumulative_quantity=attempt.cumulative_quantity.value,
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
        or type(value) is _PersistentKeyMap
        or any(
            type(value) is allowed
            for allowed in (bool, bytes, int, str, Decimal, Fraction)
        )
        or isinstance(value, Enum)
    )


def _leaf_mutation_candidates(value: object) -> tuple[object, ...]:
    """Return deterministic unequal candidates without traversing arbitrary values."""
    if type(value) is _PersistentKeyMap:
        return (
            _PersistentKeyMap.insert_new(
                value,
                b"\xfc" * 32,
                b"\xfd" * 32,
                b"\xfd" * 32,
            ),
            _LEAF_MUTATION_SENTINEL,
        )
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
    if type(value) is _PersistentKeyMap:
        return (
            "persistent-key-map",
            value.size,
            value.commitment.hex(),
        )
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
    "EffectId": EffectId,
    "VenueLegKey": VenueLegKey,
    "bool": bool,
    "bytes": bytes,
    "_Decimal": Decimal,
    "_Fraction": Fraction,
    "_MarketOccurrenceId": execution_core.MarketOccurrenceId,
    "_ReportedPrice": ReportedPrice,
    "MarketOccurrenceId": execution_core.MarketOccurrenceId,
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
    module_path = Path(function.__code__.co_filename).resolve()
    module_source = module_path.read_text(encoding="utf-8")
    import_prelude = "\n".join(
        ast.unparse(statement)
        for statement in ast.parse(module_source, filename=str(module_path)).body
        if isinstance(statement, (ast.Import, ast.ImportFrom))
        and not (
            isinstance(statement, ast.ImportFrom) and statement.module == "__future__"
        )
    )
    compiled = compile(
        f"{import_prelude}\n{source}",
        "<inspected-function-source>",
        "exec",
        flags=function.__code__.co_flags & __future__.annotations.compiler_flag,
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


def _imported_class_method_provenance_probe(
    retained: _PersistentKeyMap[bytes],
) -> bytes | None:
    return _PersistentKeyMap.get(retained, b"\x01")


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
    *,
    expected_init_fields: tuple[str, ...] | None = None,
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
    init_field_names = (
        field_names if expected_init_fields is None else expected_init_fields
    )
    assert (
        tuple(name for name in field_names if name in init_field_names)
        == init_field_names
    ), "dataclass field init inventory changed"
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
        assert object.__getattribute__(retained, "init") is (
            name in init_field_names
        ), "dataclass field init inventory changed"
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
    assert type(match_args) is tuple and match_args == init_field_names

    reference_namespace: dict[str, object] = {}
    if "__post_init__" in namespace:

        def __post_init__(_self: object) -> None:
            return None

        reference_namespace["__post_init__"] = __post_init__
    reference_type = make_dataclass(
        "_PassiveDataclassReference",
        [
            (name, object)
            if name in init_field_names
            else (name, object, field(init=False))
            for name in field_names
        ],
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


def _market_occurrence_validation_prefix(
    statements: list[ast.stmt],
) -> list[ast.stmt]:
    """Remove one exact deterministic derived-id tail from passive validation."""

    assert len(statements) >= 2
    assignment = statements[-2]
    assert isinstance(assignment, ast.Assign)
    assert len(assignment.targets) == 1
    assert isinstance(assignment.targets[0], ast.Name)
    assert assignment.targets[0].id == "preimage"
    assert isinstance(assignment.value, ast.Call)
    assert isinstance(assignment.value.func, ast.Name)
    assert assignment.value.func.id == "_market_occurrence_preimage"
    assert not assignment.value.args
    assert all(keyword.arg is not None for keyword in assignment.value.keywords)
    observed = tuple(
        (keyword.arg, ast.unparse(keyword.value))
        for keyword in assignment.value.keywords
    )
    assert observed == (
        ("source_id", "self.source_id.value"),
        ("position_scope", "self.position_scope"),
        ("session_id", "self.session_id.value"),
        ("stream_generation", "self.stream_generation._bytes"),
        ("market_epoch", "self.market_epoch"),
        ("source_sequence", "self.source_sequence"),
        ("source_time", "self.source_time"),
        ("kind", "self.kind.value"),
        ("best_bid", "self.best_bid"),
        ("best_ask", "self.best_ask"),
        ("trade_price", "self.trade_price"),
        ("atr_distance", "self.atr_distance"),
        ("structure_trail", "self.structure_trail"),
        ("halted", "self.halted"),
    )

    statement = statements[-1]
    assert isinstance(statement, ast.Expr)
    setter = statement.value
    assert isinstance(setter, ast.Call)
    assert _lifecycle_attribute_path(setter.func) == ("object", "__setattr__")
    assert len(setter.args) == 3 and not setter.keywords
    assert isinstance(setter.args[0], ast.Name) and setter.args[0].id == "self"
    assert isinstance(setter.args[1], ast.Constant)
    assert setter.args[1].value == "occurrence_id"
    constructor = setter.args[2]
    assert isinstance(constructor, ast.Call)
    assert isinstance(constructor.func, ast.Name)
    assert constructor.func.id == "_MarketOccurrenceId"
    assert len(constructor.args) == 1 and not constructor.keywords
    digest = constructor.args[0]
    assert isinstance(digest, ast.Call)
    assert _lifecycle_attribute_path(digest.func) is None
    assert isinstance(digest.func, ast.Attribute) and digest.func.attr == "hexdigest"
    assert not digest.args and not digest.keywords
    hash_call = digest.func.value
    assert isinstance(hash_call, ast.Call)
    assert isinstance(hash_call.func, ast.Name) and hash_call.func.id == "_sha256"
    assert len(hash_call.args) == 1 and not hash_call.keywords
    assert isinstance(hash_call.args[0], ast.Name)
    assert hash_call.args[0].id == "preimage"
    return statements[:-2]


def _assert_passive_lifecycle(
    value_type: type[object],
    owner_module: ModuleType,
    *,
    expected_init_fields: tuple[str, ...] | None = None,
) -> None:
    """Constrain lifecycle code to exact opaque or sequential validation forms."""
    field_names = _assert_passive_dataclass_metadata(
        value_type,
        expected_init_fields=expected_init_fields,
    )
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
        statements = function.body
        if value_type.__name__ == "MarketOccurrence":
            statements = _market_occurrence_validation_prefix(statements)
        _assert_passive_post_init_statements(
            statements,
            lifecycle=lifecycle,
            field_names=frozenset(field_names),
            guarded_types={},
        )


def _assert_passive_value_graph(
    value: object,
    *,
    allowed_shapes: dict[type[object], tuple[str, ...]],
    allowed_init_shapes: dict[type[object], tuple[str, ...]] | None = None,
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
        expected_init_fields = (
            None
            if allowed_init_shapes is None
            else allowed_init_shapes.get(current_type)
        )
        actual_fields = _assert_passive_dataclass_metadata(
            current_type,
            expected_shape,
            expected_init_fields=expected_init_fields,
        )
        _assert_passive_slot_descriptors(current_type, actual_fields)
        behavior = _retained_behavior_names(current_type)
        assert behavior <= _DATACLASS_LIFECYCLE_SPECIALS, (
            f"passive value retains behavior: {sorted(behavior)!r}"
        )
        owner_module = inspect.getmodule(current_type)
        assert owner_module is not None
        _assert_passive_lifecycle(
            current_type,
            owner_module,
            expected_init_fields=expected_init_fields,
        )
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


def _assert_recorded_market_inert(
    module: ModuleType,
    before: object,
    result: object,
) -> None:
    """Prove a well-routed ineligible occurrence advances only the bounded cursor."""
    after = result.state
    assert type(after) is type(before)
    retained_fields = {field.name for field in fields(before)}
    market_cursor_fields = {"commitment", *_ADR023_MARKET_CURSOR_FIELDS}
    assert market_cursor_fields <= retained_fields
    assert "_seen_occurrence_receipts" not in retained_fields
    for field_name in retained_fields - market_cursor_fields:
        assert getattr(after, field_name) == getattr(before, field_name), field_name
    assert after.commitment != before.commitment
    assert after != before

    (disposition,) = _required(module, "ProtectionDisposition")
    assert result.disposition is disposition.APPLIED
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
    mandate_id: MandateId = MANDATE_ID,
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
            mandate_id=mandate_id,
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
    fill_quantity: int = 4,
    fill_units: int = 100,
    tick_units: int = 1,
    scale: PriceScale = SCALE,
    position_scope: PositionScope = POSITION_SCOPE,
    first_bid: int = 92,
    second_bid: int = 91,
) -> tuple[object, object, object, object]:
    occurrence_label = label
    current_mandate = (
        mandate
        if mandate is not None
        else _mandate(module, position_scope=position_scope)
    )
    if position_scope == POSITION_SCOPE:
        fill = _owned_fill_transition(
            label=f"{label}-fill",
            quantity=fill_quantity,
            units=fill_units,
            capacity=max(20, fill_quantity),
            tick_units=tick_units,
            scale=scale,
            mandate_id=current_mandate.mandate_id,
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
            mandate_id=current_mandate.mandate_id,
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
    sequence_mode = current_mandate.evidence_policy.sequence_mode.value
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            f"{occurrence_label}-first",
            bid=first_bid,
            ask=first_bid + tick_units,
            sequence=1 if sequence_mode == "SEQUENCED" else None,
            tick_units=tick_units,
            scale=scale,
            source_id=current_mandate.evidence_policy.source_id,
            stream_generation=current_mandate.evidence_policy.stream_generation,
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
            sequence=2 if sequence_mode == "SEQUENCED" else None,
            source_time=106,
            evaluation_time=110,
            tick_units=tick_units,
            scale=scale,
            source_id=current_mandate.evidence_policy.source_id,
            stream_generation=current_mandate.evidence_policy.stream_generation,
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


def test_public_protection_contract_is_exported_with_five_exact_transitions() -> None:
    module = _protection_module()
    names = {
        "EvidencePolicy",
        "ExecutionGoal",
        "ExecutionGuard",
        "MarketKind",
        "MarketOccurrence",
        "MarketSequenceMode",
        "PositionProtectionState",
        "ProtectionAlert",
        "ProtectionDisposition",
        "ProtectionMandate",
        "ProtectionPolicy",
        "ProtectionTransition",
        "ProtectionUrgency",
        "ProtectionVenueProjection",
        "initialize_position_protection",
        "invalidate_position_protection_market",
        "project_protection_venue",
        "reduce_position_protection",
        "reduce_position_protection_market",
    }
    _required(module, *sorted(names))
    assert set(module.__all__) == names
    _required(
        execution_core,
        *sorted(names),
        "MarketDataSourceId",
        "MarketOccurrenceId",
        "MarketStreamGenerationId",
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
            ("state", "projection"),
            {
                "state": "PositionProtectionState",
                "projection": "ProtectionVenueProjection",
                "return": "ProtectionTransition",
            },
        ),
        (
            "reduce_position_protection_market",
            ("state", "projection", "occurrence"),
            {
                "state": "PositionProtectionState",
                "projection": "ProtectionVenueProjection",
                "occurrence": "MarketOccurrence",
                "return": "ProtectionTransition",
            },
        ),
        (
            "invalidate_position_protection_market",
            ("state", "projection"),
            {
                "state": "PositionProtectionState",
                "projection": "ProtectionVenueProjection",
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
            "reduce_position_protection_market",
            "invalidate_position_protection_market",
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
        _assert_passive_lifecycle(
            value_type,
            owner_module,
            expected_init_fields=(
                _MARKET_OCCURRENCE_INIT_FIELDS if label == "occurrence" else None
            ),
        )
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
    project, initialize, reduce, reduce_market, invalidate = _required(
        module,
        "project_protection_venue",
        "initialize_position_protection",
        "reduce_position_protection",
        "reduce_position_protection_market",
        "invalidate_position_protection_market",
    )
    matrix = (
        ("project.transition", project, (fill, mandate), 0),
        ("project.mandate", project, (fill, mandate), 1),
        ("initialize.mandate", initialize, (mandate, projection), 0),
        ("initialize.projection", initialize, (mandate, projection), 1),
        ("reduce.state", reduce, (state, projection), 0),
        ("reduce.projection", reduce, (state, projection), 1),
        ("market.state", reduce_market, (state, projection, occurrence), 0),
        ("market.projection", reduce_market, (state, projection, occurrence), 1),
        ("market.occurrence", reduce_market, (state, projection, occurrence), 2),
        ("invalidate.state", invalidate, (state, projection), 0),
        ("invalidate.projection", invalidate, (state, projection), 1),
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
    project, initialize, reduce, reduce_market, invalidate = _required(
        module,
        "project_protection_venue",
        "initialize_position_protection",
        "reduce_position_protection",
        "reduce_position_protection_market",
        "invalidate_position_protection_market",
    )
    capsys.readouterr()

    projection = project(fill, mandate)
    assert capsys.readouterr() == ("", "")
    state = initialize(mandate, projection)
    assert capsys.readouterr() == ("", "")
    reduce(state, projection)
    assert capsys.readouterr() == ("", "")
    occurrence = _occurrence(
        module,
        "public-entrypoint-no-output",
        bid=100,
        ask=101,
    )
    reduce_market(state, projection, occurrence)
    assert capsys.readouterr() == ("", "")
    invalidate(state, projection)
    assert capsys.readouterr() == ("", "")


def test_public_value_shapes_and_enum_members_are_exact() -> None:
    module = _protection_module()
    expected_fields = {
        "EvidencePolicy": (
            "source_id",
            "stream_generation",
            "sequence_mode",
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
        "MarketOccurrence": _MARKET_OCCURRENCE_FIELDS,
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
        "MarketSequenceMode": ("SEQUENCED", "SOURCE_TIME"),
        "ProtectionPolicy": (
            "FLOOR_ONLY",
            "TRAIL_ACTIVE",
            "EXIT_NORMAL",
            "HARD_BAIL",
            "FLAT",
        ),
        "ProtectionUrgency": ("NORMAL", "EMERGENCY"),
        "ProtectionDisposition": ("APPLIED", "EXACT_REPLAY", "STALE", "REFUSED"),
        "ProtectionAlert": (
            "LATE_POSITIVE_AFTER_FLAT",
            "MARKET_BASELINE_REQUIRED",
            "MARKET_COORDINATE_EXHAUSTED",
        ),
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
        expected_init_fields = (
            _MARKET_OCCURRENCE_INIT_FIELDS if name == "MarketOccurrence" else None
        )
        actual_fields = _assert_passive_dataclass_metadata(
            value_type,
            expected_init_fields=expected_init_fields,
        )
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
        _assert_passive_lifecycle(
            value_type,
            module,
            expected_init_fields=expected_init_fields,
        )


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


def test_passive_dataclass_seal_pins_one_derived_identity_field() -> None:
    """Only the named derived field may be absent from constructor metadata."""

    @dataclass(frozen=True, slots=True)
    class _DerivedIdentityProbe:
        occurrence_id: object = field(init=False)
        source_id: object

    @dataclass(frozen=True, slots=True)
    class _ExtraDerivedFieldMutant:
        occurrence_id: object = field(init=False)
        source_id: object = field(init=False)

    shape = ("occurrence_id", "source_id")
    assert (
        _assert_passive_dataclass_metadata(
            _DerivedIdentityProbe,
            shape,
            expected_init_fields=("source_id",),
        )
        == shape
    )
    with pytest.raises(AssertionError, match="field init inventory changed"):
        _assert_passive_dataclass_metadata(
            _DerivedIdentityProbe,
            shape,
            expected_init_fields=shape,
        )
    with pytest.raises(AssertionError, match="field init inventory changed"):
        _assert_passive_dataclass_metadata(
            _ExtraDerivedFieldMutant,
            shape,
            expected_init_fields=("source_id",),
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


def test_passive_lifecycle_derived_identity_tail_is_failure_capable() -> None:
    module = _protection_module()
    lifecycle = module.MarketOccurrence.__post_init__
    source = textwrap.dedent(inspect.getsource(lifecycle))

    def statements_from(candidate: str) -> list[ast.stmt]:
        tree = ast.parse(candidate)
        function = tree.body[0]
        assert isinstance(function, ast.FunctionDef)
        return function.body

    def validate(candidate: str) -> None:
        statements = _market_occurrence_validation_prefix(statements_from(candidate))
        _assert_passive_post_init_statements(
            statements,
            lifecycle=lifecycle,
            field_names=frozenset(
                retained_field.name
                for retained_field in fields(module.MarketOccurrence)
            ),
            guarded_types={},
        )

    validate(source)
    setter = source[source.index("    object.__setattr__(") :]
    mutants = {
        "wrong local": source.replace("preimage =", "other =", 1),
        "wrong helper": source.replace(
            "_market_occurrence_preimage(",
            "_other_preimage(",
            1,
        ),
        "wrong source": source.replace(
            "source_id=self.source_id.value",
            "source_id=self.session_id.value",
            1,
        ),
        "wrong receiver": source.replace(
            '        self,\n        "occurrence_id",',
            '        other,\n        "occurrence_id",',
            1,
        ),
        "wrong field": source.replace('"occurrence_id",', '"source_id",', 1),
        "wrong constructor": source.replace(
            "_MarketOccurrenceId(",
            "_MarketDataSourceId(",
            1,
        ),
        "wrong hash input": source.replace(
            "_sha256(preimage)",
            "_sha256(other)",
            1,
        ),
        "duplicate setter": source + setter,
        "self rebinding": source.replace(
            "    preimage = _market_occurrence_preimage(",
            "    self = other\n    preimage = _market_occurrence_preimage(",
            1,
        ),
        "dependency rebinding": source.replace(
            "    preimage = _market_occurrence_preimage(",
            "    _sha256 = other\n    preimage = _market_occurrence_preimage(",
            1,
        ),
        "preimage rebinding": source.replace(
            "    object.__setattr__(",
            "    preimage = other\n    object.__setattr__(",
            1,
        ),
        "reordered preimage": source.replace(
            "        source_id=self.source_id.value,\n"
            "        position_scope=self.position_scope,",
            "        position_scope=self.position_scope,\n"
            "        source_id=self.source_id.value,",
            1,
        ),
        "unrelated assignment": source.replace(
            "    preimage = _market_occurrence_preimage(",
            "    unrelated = other\n    preimage = _market_occurrence_preimage(",
            1,
        ),
        "trailing statement": source + "    pass\n",
    }
    for label, mutant in mutants.items():
        assert mutant != source, label
        with pytest.raises(AssertionError):
            validate(mutant)


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


def test_source_attestation_preserves_imported_class_method_codegen() -> None:
    owner_module = inspect.getmodule(_imported_class_method_provenance_probe)
    assert owner_module is not None
    source = _canonical_function_source(
        owner_module,
        "_imported_class_method_provenance_probe",
    )
    _assert_function_matches_inspected_source(
        _imported_class_method_provenance_probe,
        source,
        message="imported-class method bytecode does not match inspected source",
    )

    mutant = ast.parse(source)
    (function,) = mutant.body
    assert isinstance(function, ast.FunctionDef)
    function.body = [ast.Return(value=ast.Constant(value=None))]
    with pytest.raises(
        AssertionError,
        match="imported-class method bytecode does not match inspected source",
    ):
        _assert_function_matches_inspected_source(
            _imported_class_method_provenance_probe,
            ast.unparse(mutant),
            message="imported-class method bytecode does not match inspected source",
        )


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
        ("stream_generation", "11" * 32, TypeError),
        ("sequence_mode", "SEQUENCED", TypeError),
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
        ("source_id", "source", TypeError),
        ("stream_generation", "11" * 32, TypeError),
        ("position_scope", "scope", TypeError),
        ("session_id", "session", TypeError),
        ("market_epoch", True, TypeError),
        ("market_epoch", -1, ValueError),
        ("market_epoch", _U64_MAX + 1, ValueError),
        ("source_sequence", True, TypeError),
        ("source_sequence", -1, ValueError),
        ("source_sequence", _U64_MAX + 1, ValueError),
        ("source_time", True, TypeError),
        ("source_time", -1, ValueError),
        ("source_time", _U64_MAX + 1, ValueError),
        ("evaluation_time", True, TypeError),
        ("evaluation_time", -1, ValueError),
        ("evaluation_time", _U64_MAX + 1, ValueError),
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


def test_market_occurrence_identity_is_derived_and_not_replaceable() -> None:
    module = _protection_module()
    occurrence = _occurrence(module, "derived-identity", bid=100, ask=101)
    occurrence_field = next(
        retained
        for retained in fields(type(occurrence))
        if retained.name == "occurrence_id"
    )
    assert occurrence_field.init is False
    with pytest.raises((TypeError, ValueError)):
        type(occurrence)(occurrence_id=occurrence.occurrence_id)
    with pytest.raises((TypeError, ValueError)):
        replace(occurrence, occurrence_id=occurrence.occurrence_id)
    with pytest.raises(FrozenInstanceError):
        occurrence.occurrence_id = occurrence.occurrence_id


@pytest.mark.parametrize(
    ("sequence_mode", "sequence", "expected"),
    [
        ("SEQUENCED", 1, "APPLIED"),
        ("SEQUENCED", None, "REFUSED"),
        ("SOURCE_TIME", None, "APPLIED"),
        ("SOURCE_TIME", 1, "REFUSED"),
    ],
)
def test_market_sequence_presence_is_bound_to_the_fixed_mandate_mode(
    sequence_mode: str,
    sequence: int | None,
    expected: str,
) -> None:
    module = _protection_module()
    current = _owned_fill_transition(label=f"mode-{sequence_mode}-{sequence}")
    mandate = _mandate(module, sequence_mode=sequence_mode)
    mandate, projection, state = _start(
        module,
        current,
        mandate,
        establish_baseline=False,
    )
    occurrence = _occurrence(
        module,
        "mode-binding",
        bid=100,
        ask=101,
        sequence=sequence,
        source_time=1,
        evaluation_time=1,
        source_id=mandate.evidence_policy.source_id,
        stream_generation=mandate.evidence_policy.stream_generation,
        position_scope=mandate.position_scope,
        session_id=mandate.session_id,
    )
    result = _reduce_market(module, state, projection, occurrence)
    (disposition,) = _required(module, "ProtectionDisposition")
    assert result.disposition is getattr(disposition, expected)
    if expected == "REFUSED":
        assert result.state == state


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
    disposition, state_is_authentic = _required(
        module,
        "ProtectionDisposition",
        "_state_is_authentic",
    )
    (occurrence_id_type,) = _required(execution_core, "MarketOccurrenceId")
    assert state.high_watermark is None
    assert state.trail is None
    assert unavailable_state.formula_available is False
    assert unavailable_state.armed_hard_bail_trigger is None
    assert unavailable_state.high_watermark is None
    assert unavailable_state.trail is None
    optional_cursor_replacements = {
        ("_market_occurrence_epoch",): 7,
        ("_market_committed_epoch",): 7,
        ("_market_expected_epoch",): 8,
        ("_market_source_sequence",): 9,
        ("_market_source_time",): 10,
        ("_market_evaluation_time",): 11,
        ("_market_occurrence_identity",): occurrence_id_type("a1" * 32),
        ("_market_last_primary",): _price(107),
        ("_hard_bid_identity",): occurrence_id_type("a3" * 32),
        ("_hard_bid_source_time",): 12,
        ("_trade_identity",): occurrence_id_type("a4" * 32),
        ("_trade_source_time",): 13,
        ("_trail_bid_identity",): occurrence_id_type("a5" * 32),
        ("_trail_bid_source_time",): 14,
    }
    assert tuple(path[0] for path in optional_cursor_replacements) == (
        _ADR023_OPTIONAL_MARKET_CURSOR_FIELDS
    )
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
                ("activation_price",): _price(108),
                ("high_watermark",): _price(101),
                ("trail",): _price(99),
            },
        ),
    )
    for sealed_state, sealed_successor, price_replacements in scenarios:
        possible_replacements = {
            **price_replacements,
            **optional_cursor_replacements,
        }
        union_replacements = {
            path: replacement
            for path, replacement in possible_replacements.items()
            if getattr(sealed_state, path[0]) is None
        }
        assert {
            (field_name,)
            for field_name in _ADR023_OPTIONAL_MARKET_CURSOR_FIELDS
            if getattr(sealed_state, field_name) is None
        } <= set(union_replacements)
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
            assert state_is_authentic(mutation.forged) is False, mutation.path
            result = _reduce(module, mutation.forged, sealed_successor)
            assert result.disposition is disposition.REFUSED, mutation.path
            assert result.state == mutation.forged, mutation.path
            assert result.goal is None, mutation.path
            assert result.critical_alert is None, mutation.path


def test_market_identity_authenticity_binds_text_to_cached_bytes() -> None:
    module = _protection_module()
    occurrence_id_type, generation_id_type = _required(
        execution_core,
        "MarketOccurrenceId",
        "MarketStreamGenerationId",
    )
    occurrence_is_authentic, generation_is_authentic = _required(
        module,
        "_market_occurrence_identity_is_authentic",
        "_market_generation_is_authentic",
    )

    for identity_type, is_authentic in (
        (occurrence_id_type, occurrence_is_authentic),
        (generation_id_type, generation_is_authentic),
    ):
        canonical = identity_type("11" * 32)
        forged = copy(canonical)
        object.__setattr__(forged, "value", "22" * 32)
        encoded = forged.value.encode("ascii")
        object.__setattr__(
            forged,
            "_seal",
            sha256(len(encoded).to_bytes(8, "big") + encoded + forged._bytes).digest(),
        )

        assert canonical.value == canonical._bytes.hex()
        assert forged.value != forged._bytes.hex()
        assert is_authentic(canonical) is True
        assert is_authentic(forged) is False

        forged_bytes = copy(canonical)
        object.__setattr__(forged_bytes, "_bytes", b"\x22" * 32)
        canonical_encoded = forged_bytes.value.encode("ascii")
        object.__setattr__(
            forged_bytes,
            "_seal",
            sha256(
                len(canonical_encoded).to_bytes(8, "big")
                + canonical_encoded
                + forged_bytes._bytes
            ).digest(),
        )
        assert forged_bytes.value != forged_bytes._bytes.hex()
        assert is_authentic(forged_bytes) is False

    fill = _owned_fill_transition(label="protection-coordinated-identity-forgery")
    _, projection, state = _start(module, fill)
    occurrence = _occurrence(
        module,
        "protection-coordinated-identity-forgery-current",
        bid=101,
        ask=102,
        sequence=1,
    )
    applied = _reduce(module, state, projection, occurrence)
    (disposition,) = _required(module, "ProtectionDisposition")
    replay = _reduce(
        module,
        applied.state,
        projection,
        replace(occurrence, evaluation_time=occurrence.evaluation_time + 1),
    )
    assert replay.disposition is disposition.EXACT_REPLAY

    forged_identity = copy(applied.state._market_occurrence_identity)
    object.__setattr__(forged_identity, "value", "ff" * 32)
    forged_encoded = forged_identity.value.encode("ascii")
    object.__setattr__(
        forged_identity,
        "_seal",
        sha256(
            len(forged_encoded).to_bytes(8, "big")
            + forged_encoded
            + forged_identity._bytes
        ).digest(),
    )
    forged_state = copy(applied.state)
    object.__setattr__(
        forged_state,
        "_market_occurrence_identity",
        forged_identity,
    )
    (state_is_authentic,) = _required(module, "_state_is_authentic")
    assert state_is_authentic(forged_state) is False
    refused = _reduce(module, forged_state, projection, occurrence)
    assert refused.disposition is disposition.REFUSED
    assert refused.state is forged_state
    assert refused.goal is None


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


def test_every_protection_proof_leaf_is_bound_into_its_cursor_lineage() -> None:
    module = _protection_module()
    _, _, _, applied = _owned_fill_fixture(label="protection-proof-leaf-seal")
    mandate = _mandate(module)
    proof = applied._protection_proof
    empty_collection_replacements: dict[tuple[object, ...], object] = {}
    for summary_name in ("predecessor_summary", "summary"):
        summary = getattr(proof, summary_name)
        for field_name, replacement in (
            ("stand_downable_buy_effect_ids", (BASE_EFFECT,)),
            ("known_cancellable_buy_leg_keys", (BASE_LEG,)),
            ("known_cancel_pending_buy_leg_keys", (BASE_LEG,)),
        ):
            if not getattr(summary, field_name):
                empty_collection_replacements[(summary_name, field_name)] = replacement
    mutations = _single_leaf_mutations(
        proof,
        allowed_root_types=(type(proof),),
        empty_collection_replacements=empty_collection_replacements,
    )
    expected_paths = _retained_leaf_paths(proof)
    assert frozenset(mutation.path for mutation in mutations) == expected_paths
    assert len(mutations) == len(expected_paths)
    for mutation in mutations:
        assert _changed_leaf_paths(proof, mutation.forged) == frozenset({mutation.path})
        forged = _clone_opaque(
            applied,
            _protection_proof=mutation.forged,
            _protection_proof_commitment=mutation.forged.commitment,
        )
        with pytest.raises((TypeError, ValueError)):
            _projection(module, forged, mandate)


def test_projection_rejects_forged_nonextractor_book_envelope_field() -> None:
    module = _protection_module()
    _, _, _, applied = _owned_fill_fixture(label="protection-book-envelope-seal")
    mandate = _mandate(module)
    forged_book = _clone_opaque(
        applied.book,
        _account_authority_epoch=applied.book._account_authority_epoch + 1,
    )
    forged = _clone_opaque(applied, book=forged_book)
    with pytest.raises(ValueError, match="book envelope"):
        _projection(module, forged, mandate)


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


def test_reducer_rejects_predecessor_execution_discontinuity() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    _, advanced = _terminal_fixture(
        fill,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-predecessor-execution-gap",
        cumulative_quantity=4,
    )
    projection = _projection(module, advanced, mandate)
    assert projection.predecessor_cursor_ordinal == state._cursor_ordinal
    assert projection.predecessor_cursor_head == state._cursor_head
    assert projection.predecessor_execution_commitment == state.execution_commitment

    forged = _clone_opaque(
        projection,
        predecessor_execution_commitment=_flip_digest(state.execution_commitment),
    )
    projection_commitment = getattr(module, "_projection_commitment")
    object.__setattr__(
        forged,
        "_seal",
        projection_commitment(
            forged.predecessor_cursor_ordinal,
            forged.predecessor_cursor_head,
            forged.cursor_ordinal,
            forged.cursor_head,
            forged.predecessor_execution_commitment,
            forged.execution_commitment,
            forged.predecessor_blocking_effect_count,
            forged.predecessor_blocking_buy_effect_count,
            forged.blocking_effect_count,
            forged.blocking_buy_effect_count,
            forged.predecessor_execution_binding_matches,
            forged.execution_binding_matches,
            forged.predecessor_account_reconciliation_clear,
            forged.account_reconciliation_clear,
            forged._position_scope,
            forged._mandate_commitment,
            forged._raw_quantity,
            forged._position_root_count,
            forged._basis_available,
            forged._cost_basis,
            forged._basis_metadata_available,
            forged._basis_price,
            forged._integrity,
        ),
    )
    assert getattr(module, "_projection_is_authentic")(forged)

    result = _reduce(module, state, forged)
    (disposition,) = _required(module, "ProtectionDisposition")
    assert result.disposition is disposition.STALE
    assert result.state == state
    assert result.goal is None
    assert result.critical_alert is None


def test_transition_proof_rejects_predecessor_execution_seal_discontinuity() -> None:
    import app.execution_core.venue as venue_module

    fill = _owned_fill_transition()
    _, advanced = _terminal_fixture(
        fill,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-proof-predecessor-execution-gap",
        cumulative_quantity=4,
    )
    proof = advanced._protection_proof
    assert proof.predecessor_cursor.ordinal > 0
    changed_predecessor_commitment = _flip_digest(
        proof.predecessor_execution_commitment
    )
    changed_cursor = venue_module._next_protection_cursor(
        proof.predecessor_cursor,
        proof.position_scope,
        proof.cursor.mandate_id,
        proof.predecessor_book_scope,
        proof.book_scope,
        proof.predecessor_book_commitment,
        proof.book_commitment,
        changed_predecessor_commitment,
        proof.execution_commitment,
        proof.predecessor_execution_checkpoint,
        proof.execution_checkpoint,
        proof.predecessor_summary,
        proof.summary,
        proof.predecessor_binding,
        proof.binding,
        proof.predecessor_execution_binding_matches,
        proof.execution_binding_matches,
        proof.predecessor_account_reconciliation_clear,
        proof.account_reconciliation_clear,
        proof.command_commitment,
        proof.disposition,
        proof.quantity_delta,
    )
    internally_recomputed = replace(
        proof,
        predecessor_execution_commitment=changed_predecessor_commitment,
        cursor=changed_cursor,
    )

    assert not internally_recomputed.lineage_is_authentic


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

    forged_proof = _clone_opaque(
        branch_b._protection_proof,
        predecessor_cursor=branch_a._protection_proof.cursor,
    )
    forged_branch_b = _clone_opaque(
        branch_b,
        _protection_proof=forged_proof,
        _protection_proof_commitment=forged_proof.commitment,
    )
    with pytest.raises(ValueError, match="lineage"):
        _projection(module, forged_branch_b, mandate)


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
    state, pre_flat_projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (buy_terminal, buy_closed),
    )
    pre_flat_occurrence = _occurrence(
        module,
        "protection-late-pre-flat-occurrence",
        bid=100,
        ask=101,
        sequence=1,
    )
    pre_flat_seen = _reduce(
        module,
        state,
        pre_flat_projection,
        pre_flat_occurrence,
    )
    state = pre_flat_seen.state
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
    flat_projection = _projection(module, sell_closed, mandate)
    flat = _reduce(module, state, flat_projection)
    policy, alert = _required(module, "ProtectionPolicy", "ProtectionAlert")
    assert flat.state.policy is policy.FLAT
    flat_occurrence = _occurrence(
        module,
        "protection-late-flat-occurrence",
        bid=92,
        ask=93,
        sequence=2,
        source_time=106,
        evaluation_time=110,
    )
    flat_seen = _reduce(
        module,
        flat.state,
        flat_projection,
        flat_occurrence,
    )
    _assert_recorded_market_inert(module, flat.state, flat_seen)
    late_chain, late_effect, late_leg, _ = _append_needs_review_effect(
        sell_closed,
        prefix="protection-late-buy",
        side=ExecutionSide.BUY,
        quantity=2,
    )
    state, _, _ = _sync_transitions(
        module,
        flat_seen.state,
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
    late_projection = _projection(module, late, mandate)
    recovered = _reduce(module, state, late_projection)
    assert recovered.state.raw_quantity == 2
    assert recovered.state.policy is policy.HARD_BAIL
    assert recovered.state.mandate == mandate
    assert recovered.state.waiting_buy_resolution is True
    assert recovered.critical_alert is alert.LATE_POSITIVE_AFTER_FLAT
    assert recovered.goal is None

    (disposition,) = _required(module, "ProtectionDisposition")
    for replayed_occurrence, expected_disposition in (
        (pre_flat_occurrence, disposition.STALE),
        (flat_occurrence, disposition.EXACT_REPLAY),
    ):
        replayed = _reduce(
            module,
            recovered.state,
            late_projection,
            replace(
                replayed_occurrence,
                evaluation_time=replayed_occurrence.evaluation_time + 100,
            ),
        )
        assert replayed.disposition is expected_disposition
        assert replayed.state == recovered.state
        assert replayed.goal is None


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


def test_prefill_state_tracks_venue_chain_before_first_fill_arms_floor() -> None:
    module = _protection_module()
    mandate = _mandate(module)
    book = VenueRecoveryBook.empty(VENUE_SCOPE)
    execution = ExecutionSnapshot.flat(POSITION_SCOPE)
    commands = (
        RequestedEffect(
            input_id=VenueInputId("protection-prefill-request"),
            effect_id=BASE_EFFECT,
            request_occurrence_id=venue_fixtures.REQUEST,
            mandate_id=MANDATE_ID,
            kind=EffectKind.SUBMIT,
            client_order_id=venue_fixtures.CLIENT,
            symbol_id=SYMBOL,
            side=ExecutionSide.BUY,
            quantity=Quantity(20),
            economic_scope=b"AAPL|BUY-or-SELL|fixed-order-capacity",
        ),
        RecordDispatchClaim(
            input_id=VenueInputId("protection-prefill-claim"),
            effect_id=BASE_EFFECT,
            claim_occurrence_id=BASE_CLAIM,
        ),
        RecordTransportOutcome(
            input_id=VenueInputId("protection-prefill-unknown"),
            effect_id=BASE_EFFECT,
            state=BrokerEffectState.OUTCOME_UNKNOWN,
        ),
        DiscoverVenueLeg(
            input_id=VenueInputId("protection-prefill-discover"),
            effect_id=BASE_EFFECT,
            leg_key=BASE_LEG,
            observation_id=VenueObservationId("protection-prefill-accept"),
        ),
        ObserveVenueStatus(
            input_id=VenueInputId("protection-prefill-review"),
            leg_key=BASE_LEG,
            status=VenueAttemptState.NEEDS_REVIEW,
            observation_id=VenueObservationId("protection-prefill-review-observation"),
            cumulative_quantity=Quantity(0),
        ),
        RecordTransportOutcome(
            input_id=VenueInputId("protection-prefill-needs-review"),
            effect_id=BASE_EFFECT,
            state=BrokerEffectState.NEEDS_REVIEW,
        ),
    )
    (initialize,) = _required(module, "initialize_position_protection")
    state = None
    for command in commands:
        transition = venue_fixtures.apply_venue_recovery_input(
            book,
            execution,
            command,
        )
        assert transition.disposition is VenueRecoveryDisposition.APPLIED
        projection = _projection(module, transition, mandate)
        assert projection._position_root_count == 0
        if state is None:
            state = initialize(mandate, projection)
        else:
            advanced = _reduce(module, state, projection)
            (disposition,) = _required(module, "ProtectionDisposition")
            assert advanced.disposition is disposition.APPLIED
            assert advanced.goal is None
            state = advanced.state
        assert state.raw_quantity == 0
        assert state.formula_available is False
        book = transition.book
        execution = transition.execution

    fact = venue_fixtures._broker_fill(
        "protection-prefill-source",
        "protection-prefill-root",
        quantity=4,
        units=100,
    )
    filled = venue_fixtures.apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("protection-prefill-fill"),
            effect_id=BASE_EFFECT,
            leg_key=BASE_LEG,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=fact,
            evidence_digest=b"\x91" * 32,
        ),
    )
    assert filled.disposition is VenueRecoveryDisposition.APPLIED
    assert state is not None
    filled_projection = _projection(module, filled, mandate)
    assert filled_projection._position_root_count == 1
    first_fill = _reduce(module, state, filled_projection)
    policy, disposition = _required(
        module,
        "ProtectionPolicy",
        "ProtectionDisposition",
    )
    assert first_fill.disposition is disposition.APPLIED
    assert first_fill.state.raw_quantity == 4
    assert first_fill.state.formula_available is True
    assert first_fill.state.policy is policy.FLOOR_ONLY
    assert first_fill.state.armed_hard_bail_trigger == _price(93)
    assert first_fill.state.activation_price == _price(108)
    assert first_fill.critical_alert is None
    assert first_fill.goal is None


def test_zero_projection_with_execution_history_is_not_prefill() -> None:
    module = _protection_module()
    _, _, fill_command, fill = _owned_fill_fixture(
        label="protection-zero-history-fill",
        quantity=4,
        units=100,
    )
    mandate = _mandate(module)
    _, busted = _bust_owned_root(
        fill,
        label="protection-zero-history-bust",
        root_fill_id=fill_command.fact.root_fill_id,
        predecessor_source_event_id=fill_command.fact.key.source_event_id,
        prior_root_quantity=4,
        prior_venue_cumulative=4,
    )
    projection = _projection(module, busted, mandate)
    assert projection._raw_quantity == 0
    assert projection._position_root_count == 1
    (initialize,) = _required(module, "initialize_position_protection")
    state = initialize(mandate, projection)
    (pre_exposure_origin,) = _required(module, "_pre_exposure_origin")
    assert state._exit_provenance != pre_exposure_origin()

    _, restored = _correct_owned_root(
        busted,
        label="protection-zero-history-restored",
        root_fill_id=fill_command.fact.root_fill_id,
        predecessor_source_event_id=SourceEventId(
            "protection-zero-history-bust-source"
        ),
        prior_root_quantity=0,
        resulting_quantity=4,
        units=100,
        prior_venue_cumulative=0,
    )
    result = _reduce(module, state, _projection(module, restored, mandate))
    (policy,) = _required(module, "ProtectionPolicy")
    assert result.state.raw_quantity == 4
    assert result.state.formula_available is True
    assert result.state.policy is policy.HARD_BAIL
    assert result.critical_alert is None
    assert result.goal is None


def test_fill_bust_to_zero_then_correction_remains_hard_bail() -> None:
    module = _protection_module()
    _, _, fill_command, fill = _owned_fill_fixture(
        label="protection-sequential-zero-history-fill",
        quantity=4,
        units=100,
    )
    mandate, _, state = _start(module, fill)
    policy, disposition = _required(
        module,
        "ProtectionPolicy",
        "ProtectionDisposition",
    )
    assert state.policy is policy.FLOOR_ONLY

    _, busted = _bust_owned_root(
        fill,
        label="protection-sequential-zero-history-bust",
        root_fill_id=fill_command.fact.root_fill_id,
        predecessor_source_event_id=fill_command.fact.key.source_event_id,
        prior_root_quantity=4,
        prior_venue_cumulative=4,
    )
    bust_result = _reduce(module, state, _projection(module, busted, mandate))
    assert bust_result.disposition is disposition.APPLIED
    assert bust_result.state.raw_quantity == 0
    assert bust_result.state.formula_available is False
    assert bust_result.state.policy is policy.HARD_BAIL

    _, restored = _correct_owned_root(
        busted,
        label="protection-sequential-zero-history-restored",
        root_fill_id=fill_command.fact.root_fill_id,
        predecessor_source_event_id=SourceEventId(
            "protection-sequential-zero-history-bust-source"
        ),
        prior_root_quantity=0,
        resulting_quantity=4,
        units=100,
        prior_venue_cumulative=0,
    )
    corrected = _reduce(
        module,
        bust_result.state,
        _projection(module, restored, mandate),
    )
    assert corrected.disposition is disposition.APPLIED
    assert corrected.state.raw_quantity == 4
    assert corrected.state.formula_available is True
    assert corrected.state.policy is policy.HARD_BAIL
    assert corrected.critical_alert is None
    assert corrected.goal is None


def test_cross_scope_registry_catch_up_preserves_prefill_until_first_owned_fill() -> (
    None
):
    module = _protection_module()
    book, seeded, effect_ids = authority_fixtures._seed_multi_scope_requests(
        "protection-prefill-cross-scope"
    )
    source_execution, _ = seeded[0]
    target_execution, seed_transition = seeded[1]
    mandate_id = seed_transition._protection_proof.cursor.mandate_id
    assert mandate_id is not None
    mandate = _mandate(
        module,
        mandate_id=mandate_id,
        position_scope=target_execution.position.scope,
        session_id=execution_core.SessionId("session-1"),
    )
    _, seed_projection, state = _start(module, seed_transition, mandate)
    pre_exposure_origin, formula_loss_origin = _required(
        module,
        "_pre_exposure_origin",
        "_formula_loss_origin",
    )
    assert seed_projection._raw_quantity == 0
    assert seed_projection._position_root_count == 0
    assert state._exit_provenance == pre_exposure_origin()

    def prefill_commands(
        prefix: str,
        effect_id: EffectId,
        claim_id: ClaimOccurrenceId,
        leg_key: VenueLegKey,
    ) -> tuple[object, ...]:
        return (
            RecordDispatchClaim(
                input_id=VenueInputId(f"{prefix}-claim-input"),
                effect_id=effect_id,
                claim_occurrence_id=claim_id,
            ),
            RecordTransportOutcome(
                input_id=VenueInputId(f"{prefix}-unknown"),
                effect_id=effect_id,
                state=BrokerEffectState.OUTCOME_UNKNOWN,
            ),
            DiscoverVenueLeg(
                input_id=VenueInputId(f"{prefix}-discover"),
                effect_id=effect_id,
                leg_key=leg_key,
                observation_id=VenueObservationId(f"{prefix}-accept"),
            ),
            ObserveVenueStatus(
                input_id=VenueInputId(f"{prefix}-review"),
                leg_key=leg_key,
                status=VenueAttemptState.NEEDS_REVIEW,
                observation_id=VenueObservationId(f"{prefix}-review-observation"),
                cumulative_quantity=Quantity(0),
            ),
            RecordTransportOutcome(
                input_id=VenueInputId(f"{prefix}-needs-review"),
                effect_id=effect_id,
                state=BrokerEffectState.NEEDS_REVIEW,
            ),
        )

    source_effect = effect_ids[0]
    source_scope = source_execution.position.scope
    source_leg = VenueLegKey(
        broker=source_scope.broker,
        environment=source_scope.environment,
        account=source_scope.account,
        order_id=OrderId("protection-prefill-cross-scope-source-order"),
    )
    for command in prefill_commands(
        "protection-prefill-cross-scope-source",
        source_effect,
        ClaimOccurrenceId("protection-prefill-cross-scope-source-claim"),
        source_leg,
    ):
        source_transition = authority_fixtures._private_venue_apply(
            book,
            source_execution,
            command,
        )
        assert source_transition.disposition is VenueRecoveryDisposition.APPLIED, type(
            command
        ).__name__
        book = source_transition.book
        source_execution = source_transition.execution
    source_fact = replace(
        venue_fixtures._broker_fill(
            "protection-prefill-cross-scope-source-fill-source",
            "protection-prefill-cross-scope-source-fill-root",
            leg_key=source_leg,
            quantity=1,
            units=100,
        ),
        key=ExecutionFactKey(
            broker=source_scope.broker,
            environment=source_scope.environment,
            account=source_scope.account,
            source_event_id=SourceEventId(
                "protection-prefill-cross-scope-source-fill-source"
            ),
        ),
        scope=ExecutionScope(
            broker=source_scope.broker,
            environment=source_scope.environment,
            account=source_scope.account,
            order_id=source_leg.order_id,
            symbol_id=source_scope.symbol_id,
            side=ExecutionSide.BUY,
        ),
    )
    source_filled = authority_fixtures._private_venue_apply(
        book,
        source_execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("protection-prefill-cross-scope-source-fill-input"),
            effect_id=source_effect,
            leg_key=source_leg,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(1),
            fact=source_fact,
            evidence_digest=b"\x7a" * 32,
        ),
    )
    assert source_filled.disposition is VenueRecoveryDisposition.APPLIED
    book = source_filled.book
    source_execution = source_filled.execution
    assert source_execution.position.root_count == 1
    assert source_execution.seen_facts.count == 1
    assert book.execution_registry_count == 1
    assert book._unresolved_account_execution_reconciliation_count == 0

    target_catch_up = authority_fixtures._private_venue_apply(
        book,
        target_execution,
        CatchUpExecutionRegistry(
            input_id=VenueInputId("protection-prefill-cross-scope-target-catch-up"),
            target_checkpoint=VenueExecutionCheckpoint.from_execution(target_execution),
            prior_account_registry_count=book.execution_registry_count,
            prior_account_registry_commitment=book.execution_registry_commitment,
            prior_source_binding=book.execution_binding(
                source_execution.position.scope
            ),
            source_execution=source_execution,
        ),
    )
    assert target_catch_up.disposition is VenueRecoveryDisposition.APPLIED
    catch_up_projection = _projection(module, target_catch_up, mandate)
    assert catch_up_projection._raw_quantity == 0
    assert catch_up_projection._position_root_count == 0
    result = _reduce(module, state, catch_up_projection)
    (disposition,) = _required(module, "ProtectionDisposition")
    assert result.disposition is disposition.APPLIED
    assert result.state.raw_quantity == 0
    assert result.state.formula_available is False
    assert result.state._exit_provenance == pre_exposure_origin()
    assert result.state._exit_provenance != formula_loss_origin()
    assert result.goal is None

    target_effect = effect_ids[1]
    target_claim = ClaimOccurrenceId("protection-prefill-history-target-claim")
    target_scope = target_execution.position.scope
    target_leg = VenueLegKey(
        broker=target_scope.broker,
        environment=target_scope.environment,
        account=target_scope.account,
        order_id=OrderId("protection-prefill-history-target-order"),
    )
    book = target_catch_up.book
    execution = target_catch_up.execution
    state = result.state
    for command in prefill_commands(
        "protection-prefill-history-target",
        target_effect,
        target_claim,
        target_leg,
    ):
        transition = authority_fixtures._private_venue_apply(
            book,
            execution,
            command,
        )
        assert transition.disposition is VenueRecoveryDisposition.APPLIED, type(
            command
        ).__name__
        advanced = _reduce(module, state, _projection(module, transition, mandate))
        assert advanced.disposition is disposition.APPLIED
        assert advanced.state._exit_provenance == pre_exposure_origin()
        state = advanced.state
        book = transition.book
        execution = transition.execution

    target_fact = replace(
        venue_fixtures._broker_fill(
            "protection-prefill-history-target-fill-source",
            "protection-prefill-history-target-fill-root",
            leg_key=target_leg,
            quantity=1,
            units=100,
        ),
        key=ExecutionFactKey(
            broker=target_scope.broker,
            environment=target_scope.environment,
            account=target_scope.account,
            source_event_id=SourceEventId(
                "protection-prefill-history-target-fill-source"
            ),
        ),
        scope=ExecutionScope(
            broker=target_scope.broker,
            environment=target_scope.environment,
            account=target_scope.account,
            order_id=target_leg.order_id,
            symbol_id=target_scope.symbol_id,
            side=ExecutionSide.BUY,
        ),
    )
    filled = authority_fixtures._private_venue_apply(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("protection-prefill-history-target-fill-input"),
            effect_id=target_effect,
            leg_key=target_leg,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(1),
            fact=target_fact,
            evidence_digest=b"\x7b" * 32,
        ),
    )
    assert filled.disposition is VenueRecoveryDisposition.APPLIED
    filled_projection = _projection(module, filled, mandate)
    assert filled_projection._position_root_count == 1
    first_fill = _reduce(module, state, filled_projection)
    policy, disposition = _required(
        module,
        "ProtectionPolicy",
        "ProtectionDisposition",
    )
    assert first_fill.disposition is disposition.APPLIED
    assert first_fill.state.raw_quantity == 1
    assert first_fill.state.formula_available is True
    assert first_fill.state.policy is policy.FLOOR_ONLY
    assert first_fill.critical_alert is None
    assert first_fill.goal is None


def test_authentic_projection_rejects_changed_mandate_authority_and_scope() -> None:
    module = _protection_module()
    venue_transition = _owned_fill_transition(label="protection-mandate-binding")
    mandate, projection, state = _start(module, venue_transition)
    (initialize,) = _required(module, "initialize_position_protection")
    changed_configuration = _mandate(
        module,
        configuration_version="protection-v2",
    )
    with pytest.raises(ValueError, match="authority"):
        initialize(changed_configuration, projection)

    changed_projection = _projection(
        module,
        venue_transition,
        changed_configuration,
    )
    rejected = _reduce(module, state, changed_projection)
    (disposition,) = _required(module, "ProtectionDisposition")
    assert rejected.disposition is disposition.REFUSED
    assert rejected.state == state
    assert rejected.goal is None

    changed_scope = PositionScope(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        symbol_id=type(SYMBOL)("MSFT"),
    )
    with pytest.raises(ValueError, match="scopes differ"):
        initialize(
            _mandate(module, position_scope=changed_scope),
            projection,
        )


def test_formula_uses_fraction_then_one_upward_tick_conversion() -> None:
    module = _protection_module()
    venue_transition = _owned_fill_transition(quantity=4, units=100)
    _, _, state = _start(module, venue_transition)
    assert state.armed_hard_bail_trigger.exact_value == Fraction(93)
    assert state.activation_price.exact_value == Fraction(108)


def test_fractional_average_rounds_formula_candidates_up_to_the_next_tick() -> None:
    module = _protection_module()
    first = _owned_fill_transition(
        label="protection-fractional-average-first",
        quantity=1,
        units=100,
    )
    mandate, _, state = _start(module, first)
    second = _advance_owned_fill(
        first,
        label="protection-fractional-average-second",
        quantity=1,
        units=101,
        prior_cumulative=1,
    )
    result = _reduce(
        module,
        state,
        _projection(module, second, mandate),
    )
    assert result.state.armed_hard_bail_trigger.exact_value == Fraction(93)
    assert result.state.activation_price.exact_value == Fraction(109)


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


def test_projection_and_market_transitions_are_separate_and_ordered() -> None:
    module = _protection_module()
    first = _owned_fill_transition(
        label="protection-same-call-first",
        quantity=2,
        units=100,
    )
    mandate, _, state = _start(module, first)
    higher = _advance_owned_fill(
        first,
        label="protection-same-call-higher",
        quantity=2,
        units=120,
        prior_cumulative=2,
    )
    higher_projection = _projection(module, higher, mandate)
    occurrence = _routed_occurrence(
        module,
        mandate,
        "protection-split-first-bid",
        bid=101,
        ask=102,
        sequence=1,
        source_time=1,
        evaluation_time=1,
    )
    refused = _reduce_market(
        module,
        state,
        higher_projection,
        occurrence,
    )
    (disposition,) = _required(module, "ProtectionDisposition")
    assert refused.disposition is disposition.REFUSED
    assert refused.state == state

    economics = _reduce_projection(module, state, higher_projection)
    assert economics.state.raw_quantity == 4
    assert economics.state.armed_hard_bail_trigger.exact_value == Fraction(102)
    first_market = _reduce_market(
        module,
        economics.state,
        higher_projection,
        occurrence,
    )
    assert first_market.disposition is disposition.APPLIED
    second = _reduce_market(
        module,
        first_market.state,
        higher_projection,
        _routed_occurrence(
            module,
            mandate,
            "protection-split-second-bid",
            bid=100,
            ask=101,
            sequence=2,
            source_time=2,
            evaluation_time=2,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert second.state.policy is policy.HARD_BAIL


@pytest.mark.parametrize("case", ["exact_replay", "conflict", "halt"])
def test_projection_goal_release_is_independent_from_later_market_classification(
    case: str,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label=f"protection-advance-market-{case}")
    mandate, projection, state = _start(module, fill)
    first_occurrence = _occurrence(
        module,
        f"protection-advance-market-{case}-first",
        bid=92,
        ask=93,
        sequence=1,
    )
    first = _reduce(module, state, projection, first_occurrence)
    second_occurrence = _occurrence(
        module,
        f"protection-advance-market-{case}-second",
        bid=91,
        ask=92,
        sequence=2,
        source_time=106,
        evaluation_time=110,
    )
    waiting = _reduce(module, first.state, projection, second_occurrence)
    assert waiting.goal is None
    terminal, closed = _close_base_parent(fill)
    terminal_result = _reduce(
        module,
        waiting.state,
        _projection(module, terminal, mandate),
    )
    assert terminal_result.goal is None

    released = _reduce_projection(
        module,
        terminal_result.state,
        _projection(module, closed, mandate),
    )
    disposition, policy = _required(
        module,
        "ProtectionDisposition",
        "ProtectionPolicy",
    )
    assert released.disposition is disposition.APPLIED
    assert released.state.policy is policy.HARD_BAIL
    assert released.state.waiting_buy_resolution is False
    assert released.state.execution_commitment == closed.execution.commitment
    assert released.goal is not None
    if case == "exact_replay":
        occurrence = second_occurrence
    elif case == "conflict":
        occurrence = replace(
            second_occurrence,
            best_bid=_price(90),
            best_ask=_price(91),
        )
    else:
        occurrence = _routed_occurrence(
            module,
            mandate,
            "protection-release-halt",
            bid=90,
            ask=91,
            sequence=3,
            source_time=112,
            evaluation_time=116,
            halted=True,
        )
    classified = _reduce_market(
        module,
        released.state,
        _projection(module, closed, mandate),
        occurrence,
    )
    assert classified.goal is None
    if case == "exact_replay":
        assert classified.disposition is disposition.EXACT_REPLAY
        assert classified.state == released.state
    else:
        (alert,) = _required(module, "ProtectionAlert")
        assert classified.disposition is disposition.APPLIED
        assert classified.critical_alert is alert.MARKET_BASELINE_REQUIRED
        assert classified.state._market_baseline_required is True


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


def test_positive_broker_overfill_cannot_emit_after_trigger_shaped_evidence() -> None:
    module = _protection_module()
    overfill = _owned_fill_transition(
        label="protection-positive-overfill-goal",
        quantity=5,
        capacity=4,
    )
    mandate, _, state = _start(module, overfill)
    terminal, closed = _close_base_parent(overfill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        (terminal, closed),
    )
    result = None
    for index, bid in enumerate((92, 91), start=1):
        result = _reduce(
            module,
            state,
            projection,
            _occurrence(
                module,
                f"positive-overfill-goal-{index}",
                bid=bid,
                ask=bid + 1,
                sequence=index,
                source_time=94 + index * 6,
                evaluation_time=98 + index * 6,
            ),
        )
        state = result.state
    assert result is not None
    assert result.goal is None


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
    activation_occurrence = _occurrence(
        module,
        "formula-loss-activation",
        bid=120,
        ask=121,
        sequence=1,
    )
    activated = _reduce(
        module,
        state,
        projection,
        activation_occurrence,
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert activated.state.policy is policy.TRAIL_ACTIVE
    assert activated.state.armed_hard_bail_trigger.exact_value == Fraction(93)
    assert activated.state.trail.exact_value == Fraction(111)

    _, unavailable_transition = _correct_owned_root(
        closed,
        label="protection-formula-loss-rounding-unavailable",
        root_fill_id=fill_command.fact.root_fill_id,
        predecessor_source_event_id=fill_command.fact.key.source_event_id,
        prior_root_quantity=4,
        resulting_quantity=4,
        units=1,
        prior_venue_cumulative=4,
        closure_id=ClosureId("protection-formula-loss-unavailable-closure"),
        evidence_reference=EvidenceReference(
            "protection-formula-loss-unavailable-evidence"
        ),
    )
    unavailable = _reduce(
        module,
        activated.state,
        _projection(module, unavailable_transition, mandate),
    )
    assert unavailable.state.raw_quantity == 4
    assert unavailable.state.formula_available is False
    assert unavailable.state.policy is policy.HARD_BAIL
    assert unavailable.goal is None
    state = unavailable.state
    projection = _projection(module, unavailable_transition, mandate)
    ignored_occurrences = []
    for index, bid in enumerate((92, 91), start=2):
        occurrence = _occurrence(
            module,
            f"formula-loss-ignored-{index}",
            bid=bid,
            ask=bid + 1,
            sequence=index,
            source_time=94 + index * 6,
            evaluation_time=98 + index * 6,
        )
        ignored_occurrences.append(occurrence)
        ignored = _reduce(
            module,
            state,
            projection,
            occurrence,
        )
        state = ignored.state
        assert state.formula_available is False
        assert state.policy is policy.HARD_BAIL
        assert ignored.goal is None

    _, restored_transition = _correct_owned_root(
        unavailable_transition,
        label="protection-formula-loss-restored",
        root_fill_id=fill_command.fact.root_fill_id,
        predecessor_source_event_id=SourceEventId(
            "protection-formula-loss-rounding-unavailable-source"
        ),
        prior_root_quantity=4,
        resulting_quantity=4,
        units=100,
        prior_venue_cumulative=4,
        closure_id=ClosureId("protection-formula-loss-restored-closure"),
        evidence_reference=EvidenceReference(
            "protection-formula-loss-restored-evidence"
        ),
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

    (disposition,) = _required(module, "ProtectionDisposition")
    for replayed_occurrence in (activation_occurrence, ignored_occurrences[0]):
        replayed = _reduce(
            module,
            restored.state,
            restored_projection,
            replace(
                replayed_occurrence,
                evaluation_time=replayed_occurrence.evaluation_time + 100,
            ),
        )
        assert replayed.disposition is disposition.STALE
        assert replayed.state == restored.state
        assert replayed.goal is None

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


def test_two_distinct_bids_at_the_exact_trigger_activate_hard_bail() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="hard-trigger-inclusive")
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    assert state.armed_hard_bail_trigger.exact_value == Fraction(93)
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            "hard-trigger-inclusive-1",
            bid=93,
            ask=94,
            sequence=1,
        ),
    )
    second = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            "hard-trigger-inclusive-2",
            bid=93,
            ask=94,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    policy, urgency = _required(module, "ProtectionPolicy", "ProtectionUrgency")
    assert second.state.policy is policy.HARD_BAIL
    assert second.goal is not None
    assert second.goal.urgency is urgency.EMERGENCY


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


@pytest.mark.parametrize("sequence_mode", ["SEQUENCED", "SOURCE_TIME"])
@pytest.mark.parametrize("first_kind", ["BEST_BID", "TRADE"])
def test_changed_delivery_context_replay_is_exact_for_every_occurrence_form(
    first_kind: str,
    sequence_mode: str,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(
        label=f"changed-context-{first_kind.lower()}-{sequence_mode.lower()}"
    )
    mandate = _mandate(module, sequence_mode=sequence_mode)
    mandate, _, state = _start(module, fill, mandate)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    sequenced = sequence_mode == "SEQUENCED"
    occurrence = _routed_occurrence(
        module,
        mandate,
        "changed-context-first",
        kind=first_kind,
        bid=92,
        ask=93,
        trade=92,
        sequence=7 if sequenced else None,
        source_time=100,
        evaluation_time=104,
    )
    first = _reduce_market(module, state, projection, occurrence)
    replay_occurrence = replace(occurrence, evaluation_time=105)
    replay = _reduce_market(module, first.state, projection, replay_occurrence)
    disposition, policy = _required(
        module,
        "ProtectionDisposition",
        "ProtectionPolicy",
    )
    assert replay_occurrence.occurrence_id == occurrence.occurrence_id
    assert replay.disposition is disposition.EXACT_REPLAY
    assert replay.state == first.state
    assert replay.state.policy is policy.FLOOR_ONLY
    assert replay.goal is None
    assert replay.critical_alert is None

    successor = _routed_occurrence(
        module,
        mandate,
        "changed-context-successor",
        bid=91,
        ask=92,
        sequence=8 if sequenced else None,
        source_time=106,
        evaluation_time=107,
    )
    valid_after_replay = _reduce_market(
        module,
        replay.state,
        projection,
        successor,
    )
    assert valid_after_replay.state.policy is policy.HARD_BAIL
    assert valid_after_replay.goal is not None


def test_equal_sequence_conflict_latches_baseline_without_replacing_cursor() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="equal-sequence-conflict")
    mandate, projection, state = _start(module, fill)
    first_occurrence = _routed_occurrence(
        module,
        mandate,
        "equal-sequence-first",
        bid=92,
        ask=93,
        sequence=7,
        source_time=100,
        evaluation_time=104,
    )
    first = _reduce_market(module, state, projection, first_occurrence)
    conflict_occurrence = _routed_occurrence(
        module,
        mandate,
        "equal-sequence-conflict",
        bid=91,
        ask=92,
        sequence=7,
        source_time=106,
        evaluation_time=110,
    )
    conflict = _reduce_market(module, first.state, projection, conflict_occurrence)
    disposition, alert = _required(
        module,
        "ProtectionDisposition",
        "ProtectionAlert",
    )
    assert conflict.disposition is disposition.APPLIED
    assert conflict.critical_alert is alert.MARKET_BASELINE_REQUIRED
    assert conflict.state._market_baseline_required is True
    assert conflict.state._market_occurrence_identity == first_occurrence.occurrence_id
    assert conflict.goal is None


def test_wrong_mode_refusal_preserves_the_sequenced_high_water() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="fixed-sequence-high-water")
    mandate, projection, state = _start(module, fill)
    first = _reduce_market(
        module,
        state,
        projection,
        _routed_occurrence(
            module,
            mandate,
            "fixed-sequence-seven",
            sequence=7,
            source_time=100,
            evaluation_time=104,
        ),
    )
    wrong_mode = _routed_occurrence(
        module,
        mandate,
        "fixed-sequence-absent",
        sequence=None,
        source_time=106,
        evaluation_time=110,
    )
    refused = _reduce_market(module, first.state, projection, wrong_mode)
    (disposition,) = _required(module, "ProtectionDisposition")
    assert refused.disposition is disposition.REFUSED
    assert refused.state == first.state
    assert refused.state._market_source_sequence == 7

    advanced = _reduce_market(
        module,
        refused.state,
        projection,
        _routed_occurrence(
            module,
            mandate,
            "fixed-sequence-eight",
            sequence=8,
            source_time=106,
            evaluation_time=110,
        ),
    )
    assert advanced.disposition is disposition.APPLIED
    assert advanced.state._market_source_sequence == 8


@pytest.mark.parametrize("sequence_mode", ["SEQUENCED", "SOURCE_TIME"])
@pytest.mark.parametrize("first_kind", ["BEST_BID", "TRADE"])
def test_derived_identity_conflict_is_one_shot_before_recovery(
    first_kind: str,
    sequence_mode: str,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(
        label=f"identity-conflict-{first_kind.lower()}-{sequence_mode.lower()}"
    )
    mandate = _mandate(module, sequence_mode=sequence_mode)
    mandate, projection, state = _start(module, fill, mandate)
    sequenced = sequence_mode == "SEQUENCED"
    first_occurrence = _routed_occurrence(
        module,
        mandate,
        "identity-conflict-first",
        kind=first_kind,
        bid=92,
        ask=93,
        trade=92,
        sequence=1 if sequenced else None,
        source_time=100,
        evaluation_time=104,
    )
    first = _reduce_market(module, state, projection, first_occurrence)
    changed = _routed_occurrence(
        module,
        mandate,
        "identity-conflict-changed",
        bid=91,
        ask=92,
        sequence=1 if sequenced else None,
        source_time=100,
        evaluation_time=105,
    )
    assert changed.occurrence_id != first_occurrence.occurrence_id
    conflict = _reduce_market(module, first.state, projection, changed)
    disposition, alert = _required(
        module,
        "ProtectionDisposition",
        "ProtectionAlert",
    )
    assert conflict.disposition is disposition.APPLIED
    assert conflict.critical_alert is alert.MARKET_BASELINE_REQUIRED
    assert conflict.state._market_occurrence_identity == first_occurrence.occurrence_id

    another = replace(changed, best_bid=_price(90), best_ask=_price(91))
    refused = _reduce_market(module, conflict.state, projection, another)
    assert refused.disposition is disposition.REFUSED
    assert refused.state == conflict.state
    assert refused.critical_alert is None


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
    old_occurrence = _occurrence(
        module,
        "old-trigger-branch",
        bid=92,
        ask=93,
        sequence=1,
    )
    old_branch = _reduce(
        module,
        state,
        projection,
        old_occurrence,
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
    ratchet_replay = _reduce(
        module,
        synced.state,
        _projection(module, higher, mandate),
        replace(old_occurrence, evaluation_time=110),
    )
    (disposition,) = _required(module, "ProtectionDisposition")
    assert ratchet_replay.disposition is disposition.EXACT_REPLAY
    assert ratchet_replay.state == synced.state
    assert ratchet_replay.goal is None
    first_new = _reduce(
        module,
        ratchet_replay.state,
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


def test_source_time_mode_requires_strictly_timed_distinct_occurrences() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate = _mandate(module, sequence_mode="SOURCE_TIME")
    mandate, _, state = _start(module, fill, mandate)
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


@pytest.mark.parametrize("first_kind", ["BEST_BID", "TRADE"])
def test_nonlast_sequence_absent_replay_cannot_rebuild_hard_bail_evidence(
    first_kind: str,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label=f"nonlast-hard-replay-{first_kind.lower()}")
    mandate = _mandate(module, sequence_mode="SOURCE_TIME")
    mandate, _, state = _start(module, fill, mandate)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    first_occurrence = _occurrence(
        module,
        f"nonlast-hard-replay-{first_kind.lower()}-a",
        kind=first_kind,
        bid=92 if first_kind == "BEST_BID" else None,
        ask=93 if first_kind == "BEST_BID" else None,
        trade=92 if first_kind == "TRADE" else None,
        sequence=None,
        source_time=100,
        evaluation_time=104,
    )
    first = _reduce(module, state, projection, first_occurrence)
    interrupted = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            f"nonlast-hard-replay-{first_kind.lower()}-b",
            bid=95,
            ask=96,
            sequence=None,
            source_time=101,
            evaluation_time=105,
        ),
    )
    restarted_state = _clone_opaque(interrupted.state)
    replay = _reduce(
        module,
        restarted_state,
        projection,
        replace(first_occurrence, evaluation_time=106),
    )
    disposition, policy = _required(
        module,
        "ProtectionDisposition",
        "ProtectionPolicy",
    )
    assert replay.disposition is disposition.STALE
    assert replay.state == restarted_state
    assert replay.goal is None
    assert replay.critical_alert is None

    successor = _reduce(
        module,
        replay.state,
        projection,
        _occurrence(
            module,
            f"nonlast-hard-replay-{first_kind.lower()}-c",
            bid=91,
            ask=92,
            sequence=None,
            source_time=106,
            evaluation_time=110,
        ),
    )
    assert successor.state.policy is policy.FLOOR_ONLY
    assert successor.goal is None


def test_nonlast_old_coordinate_payload_change_is_stale() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="nonlast-identity-equivocation")
    mandate = _mandate(module, sequence_mode="SOURCE_TIME")
    mandate, _, state = _start(module, fill, mandate)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    shared_id = "nonlast-identity-equivocation-a"
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            shared_id,
            bid=92,
            ask=93,
            sequence=None,
            source_time=100,
            evaluation_time=104,
        ),
    )
    interrupted = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            "nonlast-identity-equivocation-b",
            bid=95,
            ask=96,
            sequence=None,
            source_time=101,
            evaluation_time=105,
        ),
    )
    equivocated = _reduce(
        module,
        interrupted.state,
        projection,
        _occurrence(
            module,
            shared_id,
            bid=91,
            ask=92,
            sequence=None,
            source_time=100,
            evaluation_time=106,
        ),
    )
    disposition, policy = _required(
        module,
        "ProtectionDisposition",
        "ProtectionPolicy",
    )
    assert equivocated.disposition is disposition.STALE
    assert equivocated.state == interrupted.state
    assert equivocated.state.policy is policy.FLOOR_ONLY
    assert equivocated.goal is None
    assert equivocated.critical_alert is None


def test_nonlast_sequence_absent_replay_cannot_rebuild_trail_exit_evidence() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="nonlast-trail-replay")
    mandate = _mandate(module, sequence_mode="SOURCE_TIME")
    mandate, _, state = _start(module, fill, mandate)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    activated = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            "nonlast-trail-replay-activation",
            bid=110,
            ask=111,
            sequence=None,
            source_time=100,
            evaluation_time=104,
        ),
    )
    assert activated.state.trail.exact_value == Fraction(102)
    first_occurrence = _occurrence(
        module,
        "nonlast-trail-replay-a",
        bid=101,
        ask=102,
        sequence=None,
        source_time=106,
        evaluation_time=110,
    )
    first = _reduce(module, activated.state, projection, first_occurrence)
    interrupted = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            "nonlast-trail-replay-b",
            bid=105,
            ask=106,
            sequence=None,
            source_time=107,
            evaluation_time=111,
        ),
    )
    restarted_state = _clone_opaque(interrupted.state)
    replay = _reduce(
        module,
        restarted_state,
        projection,
        replace(first_occurrence, evaluation_time=112),
    )
    disposition, policy = _required(
        module,
        "ProtectionDisposition",
        "ProtectionPolicy",
    )
    assert replay.disposition is disposition.STALE
    assert replay.state == restarted_state
    assert replay.goal is None

    successor = _reduce(
        module,
        replay.state,
        projection,
        _occurrence(
            module,
            "nonlast-trail-replay-c",
            bid=100,
            ask=101,
            sequence=None,
            source_time=112,
            evaluation_time=116,
        ),
    )
    assert successor.state.policy is policy.TRAIL_ACTIVE
    assert successor.goal is None


def test_stale_first_delivery_cannot_become_fresh_when_redelivered() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="stale-first-delivery-replay")
    mandate = _mandate(module, sequence_mode="SOURCE_TIME")
    mandate, _, state = _start(module, fill, mandate)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    stale = _occurrence(
        module,
        "stale-first-delivery-replay-a",
        bid=92,
        ask=93,
        sequence=None,
        source_time=100,
        evaluation_time=111,
    )
    first_delivery = _reduce(module, state, projection, stale)
    interruption = _reduce(
        module,
        first_delivery.state,
        projection,
        _occurrence(
            module,
            "stale-first-delivery-replay-b",
            bid=95,
            ask=96,
            sequence=None,
            source_time=101,
            evaluation_time=105,
        ),
    )
    replay = _reduce(
        module,
        interruption.state,
        projection,
        replace(stale, evaluation_time=106),
    )
    disposition, policy = _required(
        module,
        "ProtectionDisposition",
        "ProtectionPolicy",
    )
    assert first_delivery.disposition is disposition.APPLIED
    assert first_delivery.goal is None
    assert replay.disposition is disposition.STALE
    assert replay.state == interruption.state
    assert replay.state.policy is policy.FLOOR_ONLY
    assert replay.goal is None


def test_step_invalid_first_delivery_cannot_become_eligible_after_anchor_moves() -> (
    None
):
    module = _protection_module()
    fill = _owned_fill_transition(label="step-first-delivery-replay")
    mandate = _mandate(module, sequence_mode="SOURCE_TIME")
    mandate, _, state = _start(module, fill, mandate)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    anchored = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            "step-first-delivery-anchor",
            bid=100,
            ask=101,
            sequence=None,
            source_time=100,
            evaluation_time=104,
        ),
    )
    step_invalid = _occurrence(
        module,
        "step-first-delivery-replay-a",
        bid=160,
        ask=161,
        sequence=None,
        source_time=106,
        evaluation_time=110,
    )
    first_delivery = _reduce(module, anchored.state, projection, step_invalid)
    moved_anchor = _reduce(
        module,
        first_delivery.state,
        projection,
        _occurrence(
            module,
            "step-first-delivery-replay-b",
            bid=120,
            ask=121,
            sequence=None,
            source_time=107,
            evaluation_time=111,
        ),
    )
    replay = _reduce(
        module,
        moved_anchor.state,
        projection,
        replace(step_invalid, evaluation_time=112),
    )
    disposition, policy = _required(
        module,
        "ProtectionDisposition",
        "ProtectionPolicy",
    )
    assert first_delivery.disposition is disposition.APPLIED
    assert first_delivery.goal is None
    assert replay.disposition is disposition.STALE
    assert replay.state == moved_anchor.state
    assert replay.state.policy is policy.TRAIL_ACTIVE
    assert replay.state.high_watermark.exact_value == Fraction(120)
    assert replay.goal is None


def test_crossed_first_delivery_reserves_identity_against_payload_correction() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label="crossed-first-delivery-equivocation")
    mandate = _mandate(module, sequence_mode="SOURCE_TIME")
    mandate, _, state = _start(module, fill, mandate)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    crossed_occurrence = _routed_occurrence(
        module,
        mandate,
        "crossed-first-delivery",
        bid=101,
        ask=100,
        sequence=None,
        source_time=100,
        evaluation_time=104,
    )
    crossed = _reduce_market(module, state, projection, crossed_occurrence)
    corrected_occurrence = _routed_occurrence(
        module,
        mandate,
        "crossed-first-delivery-corrected",
        bid=92,
        ask=93,
        sequence=None,
        source_time=100,
        evaluation_time=105,
    )
    corrected = _reduce_market(
        module,
        crossed.state,
        projection,
        corrected_occurrence,
    )
    disposition, alert = _required(
        module,
        "ProtectionDisposition",
        "ProtectionAlert",
    )
    assert crossed.disposition is disposition.APPLIED
    assert corrected.disposition is disposition.APPLIED
    assert corrected.critical_alert is alert.MARKET_BASELINE_REQUIRED
    assert corrected.state._market_baseline_required is True
    assert (
        corrected.state._market_occurrence_identity == crossed_occurrence.occurrence_id
    )
    assert corrected.goal is None

    another = replace(corrected_occurrence, best_bid=_price(91), best_ask=_price(92))
    refused = _reduce_market(module, corrected.state, projection, another)
    assert refused.disposition is disposition.REFUSED
    assert refused.state == corrected.state
    assert refused.critical_alert is None


def test_source_time_regression_and_halt_reopen_start_fresh_branches() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate = _mandate(module, sequence_mode="SOURCE_TIME")
    mandate, _, state = _start(module, fill, mandate)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    first_occurrence = _routed_occurrence(
        module,
        mandate,
        "time-before-halt",
        bid=92,
        ask=93,
        sequence=None,
        source_time=100,
        evaluation_time=105,
    )
    first = _reduce(
        module,
        state,
        projection,
        first_occurrence,
    )
    regressed = _reduce(
        module,
        first.state,
        projection,
        _routed_occurrence(
            module,
            mandate,
            "time-regressed",
            bid=91,
            ask=92,
            sequence=None,
            source_time=99,
            evaluation_time=104,
        ),
    )
    (disposition,) = _required(module, "ProtectionDisposition")
    assert regressed.disposition is disposition.STALE
    assert regressed.state == first.state
    halted = _reduce(
        module,
        regressed.state,
        projection,
        _routed_occurrence(
            module,
            mandate,
            "halted-market",
            bid=91,
            ask=92,
            sequence=None,
            source_time=106,
            evaluation_time=110,
            halted=True,
        ),
    )
    assert halted.state != regressed.state
    halted_replay = _reduce(
        module,
        halted.state,
        projection,
        replace(first_occurrence, evaluation_time=111),
    )
    assert halted_replay.disposition is disposition.STALE
    assert halted_replay.state == halted.state
    assert halted_replay.goal is None
    same_epoch = _reduce(
        module,
        halted_replay.state,
        projection,
        _routed_occurrence(
            module,
            mandate,
            "same-epoch-after-halt",
            bid=91,
            ask=92,
            sequence=None,
            source_time=112,
            evaluation_time=116,
        ),
    )
    assert same_epoch.disposition is disposition.STALE
    assert same_epoch.state == halted.state
    reopened_baseline = _reduce(
        module,
        same_epoch.state,
        projection,
        _routed_occurrence(
            module,
            mandate,
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
    assert reopened_baseline.state.policy is policy.FLOOR_ONLY
    assert reopened_baseline.state._hard_bid_identity is None
    assert reopened_baseline.goal is None
    reopened_first = _reduce(
        module,
        reopened_baseline.state,
        projection,
        _routed_occurrence(
            module,
            mandate,
            "reopen-below-2",
            bid=91,
            ask=92,
            sequence=None,
            source_time=118,
            evaluation_time=122,
            market_epoch=1,
        ),
    )
    assert reopened_first.state.policy is policy.FLOOR_ONLY
    assert reopened_first.goal is None
    reopened_second = _reduce(
        module,
        reopened_first.state,
        projection,
        _routed_occurrence(
            module,
            mandate,
            "reopen-below-3",
            bid=90,
            ask=91,
            sequence=None,
            source_time=124,
            evaluation_time=128,
            market_epoch=1,
        ),
    )
    assert reopened_second.state.policy is policy.HARD_BAIL


@pytest.mark.parametrize("first_kind", ["BEST_BID", "TRADE"])
def test_cross_kind_market_step_limit_uses_the_last_eligible_primary(
    first_kind: str,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label=f"protection-cross-kind-step-{first_kind}")
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            f"protection-cross-kind-step-{first_kind}-first",
            kind=first_kind,
            bid=92 if first_kind == "BEST_BID" else None,
            ask=93 if first_kind == "BEST_BID" else None,
            trade=92 if first_kind == "TRADE" else None,
            sequence=1,
        ),
    )
    assert type(first.state._market_last_primary) is ReportedPrice
    assert first.state._market_last_primary == _price(92)
    second_kind = "TRADE" if first_kind == "BEST_BID" else "BEST_BID"
    second = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            f"protection-cross-kind-step-{first_kind}-second",
            kind=second_kind,
            bid=1 if second_kind == "BEST_BID" else None,
            ask=2 if second_kind == "BEST_BID" else None,
            trade=1 if second_kind == "TRADE" else None,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    _assert_recorded_market_inert(module, first.state, second)
    assert second.state.policy is policy.FLOOR_ONLY


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
        _assert_recorded_market_inert(module, first.state, second)


def test_recovery_epoch_preserves_generation_global_coordinates_and_watermarks() -> (
    None
):
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
    regressed_baseline_occurrence = _occurrence(
        module,
        "evaluation-epoch-one-regressed-baseline",
        bid=92,
        ask=93,
        sequence=3,
        source_time=107,
        evaluation_time=109,
        market_epoch=1,
    )
    regressed = _reduce(
        module,
        halted.state,
        projection,
        regressed_baseline_occurrence,
    )
    (disposition,) = _required(module, "ProtectionDisposition")
    assert regressed.disposition is disposition.APPLIED
    assert regressed.state._market_source_sequence == 3
    assert regressed.state._market_source_time == 107
    assert regressed.state._market_evaluation_time == 110
    assert regressed.state._market_baseline_required is True
    assert regressed.state._market_committed_epoch == 0
    assert regressed.goal is None

    corrected_same_coordinate = _reduce(
        module,
        regressed.state,
        projection,
        replace(regressed_baseline_occurrence, evaluation_time=111),
    )
    assert corrected_same_coordinate.disposition is disposition.EXACT_REPLAY
    assert corrected_same_coordinate.state == regressed.state

    reopened = _reduce(
        module,
        corrected_same_coordinate.state,
        projection,
        _occurrence(
            module,
            "evaluation-epoch-one-baseline",
            bid=92,
            ask=93,
            sequence=4,
            source_time=108,
            evaluation_time=110,
            market_epoch=1,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert reopened.state.policy is policy.FLOOR_ONLY
    assert reopened.state._market_committed_epoch == 1
    assert reopened.state._market_baseline_required is False
    assert reopened.state._hard_bid_identity is None
    assert reopened.goal is None

    first = _reduce(
        module,
        reopened.state,
        projection,
        _occurrence(
            module,
            "evaluation-epoch-one-first-evidence",
            bid=92,
            ask=93,
            sequence=5,
            source_time=109,
            evaluation_time=111,
            market_epoch=1,
        ),
    )
    assert first.state.policy is policy.FLOOR_ONLY
    assert first.goal is None

    valid_second = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            "evaluation-epoch-one-second",
            bid=91,
            ask=92,
            sequence=6,
            source_time=110,
            evaluation_time=112,
            market_epoch=1,
        ),
    )
    (urgency,) = _required(module, "ProtectionUrgency")
    assert valid_second.state.policy is policy.HARD_BAIL
    assert valid_second.goal is not None
    assert valid_second.goal.urgency is urgency.EMERGENCY


@pytest.mark.parametrize(
    "case",
    ["stale", "crossed", "wrong_scope", "wrong_source"],
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
    result = _reduce(
        module,
        state,
        projection,
        _occurrence(module, f"ineligible-{case}", **kwargs),
    )
    if case in {"stale", "crossed"}:
        _assert_recorded_market_inert(module, state, result)
    else:
        assert result.state == state
        assert result.goal is None
        assert result.critical_alert is None


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
    if case == "wrong_session":
        assert result.state == state
        assert result.goal is None
        assert result.critical_alert is None
    else:
        _assert_recorded_market_inert(module, state, result)


@pytest.mark.parametrize(
    "case",
    ["nonpositive", "misaligned", "tick_mismatch"],
)
def test_invalid_trade_price_cannot_supply_hard_bail_corroboration(case: str) -> None:
    module = _protection_module()
    fill = _owned_fill_transition(label=f"protection-invalid-trade-{case}")
    mandate = _mandate(
        module,
        tick=(
            TickMetadata(tick_units=PriceUnits(2), scale=SCALE)
            if case == "misaligned"
            else TICK
        ),
    )
    mandate, _, state = _start(module, fill, mandate)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    invalid_trade = _occurrence(
        module,
        f"protection-invalid-trade-{case}-first",
        kind="TRADE",
        trade=92,
        sequence=1,
    )
    if case == "nonpositive":
        invalid_trade = replace(invalid_trade, trade_price=_price(0))
    elif case == "misaligned":
        invalid_trade = replace(invalid_trade, trade_price=_price(93))
    else:
        invalid_trade = replace(
            invalid_trade,
            trade_price=_price(92, tick_units=2),
        )
    ignored = _reduce(module, state, projection, invalid_trade)
    _assert_recorded_market_inert(module, state, ignored)

    second = _reduce(
        module,
        ignored.state,
        projection,
        _occurrence(
            module,
            f"protection-invalid-trade-{case}-second",
            bid=92,
            ask=94 if case == "misaligned" else 93,
            sequence=2,
            source_time=106,
            evaluation_time=110,
            tick_units=2 if case == "misaligned" else 1,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert second.state.policy is policy.FLOOR_ONLY
    assert second.goal is None


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
        label="goal-binding",
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
        "evidence_generation",
        "evidence_sequence_mode",
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
    elif binding == "evidence_generation":
        (generation_type,) = _required(execution_core, "MarketStreamGenerationId")
        mandate_kwargs["stream_generation"] = generation_type("22" * 32)
    elif binding == "evidence_sequence_mode":
        mandate_kwargs["sequence_mode"] = "SOURCE_TIME"
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
        fixture_kwargs["first_bid"] = 93

    changed_mandate = _mandate(module, **mandate_kwargs)
    _, changed_closed, changed_state, changed_goal = _emergency_goal_fixture(
        module,
        label="goal-binding-sensitivity",
        mandate=changed_mandate,
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
    if binding == "exit_provenance":
        changed_fields = {
            retained.name
            for retained in fields(baseline_state)
            if getattr(baseline_state, retained.name)
            != getattr(changed_state, retained.name)
        }
        assert changed_fields == {"commitment", "_exit_provenance"}
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


def test_m1c_create_claim_and_outcome_publish_ordered_protection_provenance() -> None:
    module = _protection_module()
    mandate, closed, protection_state, goal = _emergency_goal_fixture(
        module,
        label="goal-m1c-provenance",
    )
    request = BrokerEffectRequest(
        effect_id=EffectId("protection-goal-provenance-effect"),
        request_occurrence_id=RequestOccurrenceId(
            "protection-goal-provenance-occurrence"
        ),
        mandate_id=goal.mandate_id,
        kind=EffectKind.SUBMIT,
        client_order_id=ClientOrderId("protection-goal-provenance-client"),
        symbol_id=SYMBOL,
        side=goal.side,
        quantity=goal.residual,
        economic_scope=goal.protection_commitment,
        target_leg_key=None,
    )
    authority = _forge_authority_predecessor(
        closed.book,
        session_id=goal.session_id,
    )
    created = apply_execution_authority_input(
        authority,
        closed.execution,
        CreateBrokerEffect(
            input_id=execution_core.AuthorityInputId("provenance-create"),
            session_id=goal.session_id,
            request=request,
            manual_flatten_id=None,
            emergency_grant_id=None,
        ),
    )
    assert created.disposition is AuthorityDisposition.APPLIED
    assert len(created.venue_transitions) == 1
    for transition in created.venue_transitions:
        result = _reduce(
            module,
            protection_state,
            _projection(module, transition, mandate),
        )
        protection_state = result.state

    claimed = apply_execution_authority_input(
        created.state,
        closed.execution,
        ClaimEffect(
            input_id=execution_core.AuthorityInputId("provenance-claim"),
            effect_id=request.effect_id,
            claim_occurrence_id=ClaimOccurrenceId("provenance-claim-occurrence"),
        ),
    )
    assert claimed.disposition is AuthorityDisposition.APPLIED
    assert len(claimed.venue_transitions) == 1
    for transition in claimed.venue_transitions:
        result = _reduce(
            module,
            protection_state,
            _projection(module, transition, mandate),
        )
        protection_state = result.state

    observed = venue_fixtures.apply_venue_recovery_input(
        claimed.state.venue,
        closed.execution,
        RecordTransportOutcome(
            input_id=VenueInputId("provenance-outcome"),
            effect_id=request.effect_id,
            state=BrokerEffectState.OUTCOME_UNKNOWN,
        ),
    )
    final = _reduce(
        module,
        protection_state,
        _projection(module, observed, mandate),
    )
    disposition, policy = _required(
        module,
        "ProtectionDisposition",
        "ProtectionPolicy",
    )
    assert final.disposition is disposition.APPLIED
    assert final.state.policy is policy.HARD_BAIL
    assert final.state._cursor_ordinal == observed._protection_proof.cursor.ordinal


def test_m1c_compound_kill_publishes_every_protection_transition_in_order() -> None:
    module = _protection_module()
    mandate, closed, protection_state, goal = _emergency_goal_fixture(
        module,
        label="goal-m1c-kill-provenance",
    )
    request = BrokerEffectRequest(
        effect_id=EffectId("protection-kill-provenance-effect"),
        request_occurrence_id=RequestOccurrenceId(
            "protection-kill-provenance-occurrence"
        ),
        mandate_id=goal.mandate_id,
        kind=EffectKind.SUBMIT,
        client_order_id=ClientOrderId("protection-kill-provenance-client"),
        symbol_id=SYMBOL,
        side=goal.side,
        quantity=goal.residual,
        economic_scope=goal.protection_commitment,
        target_leg_key=None,
    )
    authority = _forge_authority_predecessor(
        closed.book,
        session_id=goal.session_id,
    )
    created = apply_execution_authority_input(
        authority,
        closed.execution,
        CreateBrokerEffect(
            input_id=execution_core.AuthorityInputId("kill-provenance-create"),
            session_id=goal.session_id,
            request=request,
            manual_flatten_id=None,
            emergency_grant_id=None,
        ),
    )
    assert created.disposition is AuthorityDisposition.APPLIED
    for transition in created.venue_transitions:
        protection_state = _reduce(
            module,
            protection_state,
            _projection(module, transition, mandate),
        ).state

    killed = apply_execution_authority_input(
        created.state,
        closed.execution,
        EngageKill(
            input_id=execution_core.AuthorityInputId("kill-provenance-engage"),
            actor=execution_core.ActorId("kill-provenance-operator"),
            reason="stand down the unclaimed protection request",
            evidence_reference=EvidenceReference("kill-provenance-evidence"),
        ),
    )
    assert killed.disposition is AuthorityDisposition.APPLIED
    assert len(killed.venue_transitions) == 2
    for transition in killed.venue_transitions:
        result = _reduce(
            module,
            protection_state,
            _projection(module, transition, mandate),
        )
        protection_state = result.state
    (policy,) = _required(module, "ProtectionPolicy")
    assert protection_state.policy is policy.HARD_BAIL
    assert protection_state._cursor_ordinal == (
        killed.venue_transitions[-1]._protection_proof.cursor.ordinal
    )


def test_m1c_multi_scope_kill_provenance_is_scope_correct_and_gap_free() -> None:
    module = _protection_module()
    authority_module = authority_fixtures._authority_module()
    killed, seeded, _, _ = authority_fixtures._multi_scope_kill_fixture(
        authority_module,
        "protection-kill-multi",
    )
    (protection_disposition,) = _required(module, "ProtectionDisposition")
    by_scope: dict[PositionScope, list[object]] = {}
    mandates: dict[PositionScope, object] = {}
    states: dict[PositionScope, object] = {}
    executions: dict[PositionScope, ExecutionSnapshot] = {}
    for execution, seed_transition in seeded:
        scope = execution.position.scope
        mandate_id = seed_transition._protection_proof.cursor.mandate_id
        assert mandate_id is not None
        mandate = _mandate(
            module,
            mandate_id=mandate_id,
            position_scope=scope,
            session_id=execution_core.SessionId("session-1"),
        )
        _, _, state = _start(module, seed_transition, mandate)
        mandates[scope] = mandate
        states[scope] = state
        executions[scope] = execution

    for transition in killed.venue_transitions:
        scope = transition._protection_proof.position_scope
        by_scope.setdefault(scope, []).append(transition)
    assert set(by_scope) == set(states)

    for scope, transitions in by_scope.items():
        assert len(transitions) == 2
        assert (
            transitions[1]._protection_proof.predecessor_cursor
            == transitions[0]._protection_proof.cursor
        )
        state = states[scope]
        mandate = mandates[scope]
        for transition in transitions:
            assert transition.execution.position.scope == scope
            assert transition._protection_proof.lineage_is_authentic
            projection = _projection(module, transition, mandate)
            assert projection.predecessor_cursor_ordinal == state._cursor_ordinal
            assert projection.predecessor_cursor_head == state._cursor_head
            result = _reduce(module, state, projection)
            assert result.disposition is protection_disposition.APPLIED
            assert result.state.raw_quantity == executions[scope].position.raw_quantity
            state = result.state
        states[scope] = state

        suffix = scope.symbol_id.value.lower()
        next_transition = authority_fixtures._private_venue_apply(
            killed.state.venue,
            executions[scope],
            RequestedEffect(
                input_id=VenueInputId(f"protection-kill-next-{suffix}-input"),
                effect_id=EffectId(f"protection-kill-next-{suffix}-effect"),
                request_occurrence_id=RequestOccurrenceId(
                    f"protection-kill-next-{suffix}-occurrence"
                ),
                mandate_id=mandate.mandate_id,
                kind=EffectKind.SUBMIT,
                client_order_id=ClientOrderId(f"protection-kill-next-{suffix}-client"),
                symbol_id=scope.symbol_id,
                side=ExecutionSide.BUY,
                quantity=Quantity(1),
                economic_scope=f"protection-kill-next-{suffix}-scope".encode(),
                target_leg_key=None,
            ),
        )
        assert next_transition.disposition is VenueRecoveryDisposition.APPLIED
        next_result = _reduce(
            module,
            state,
            _projection(module, next_transition, mandate),
        )
        assert next_result.disposition is protection_disposition.APPLIED
        assert next_result.state._cursor_ordinal == (
            next_transition._protection_proof.cursor.ordinal
        )


def test_m1c_multi_scope_kill_publishes_registry_catch_up_before_cleanup() -> None:
    module = _protection_module()
    authority_module = authority_fixtures._authority_module()
    killed, seeded, source_advance, _ = (
        authority_fixtures._stale_multi_scope_kill_fixture(
            authority_module,
            "protection-kill-stale-multi",
        )
    )
    (protection_disposition,) = _required(module, "ProtectionDisposition")
    states: dict[PositionScope, object] = {}
    mandates: dict[PositionScope, object] = {}
    for execution, seed_transition in seeded:
        scope = execution.position.scope
        mandate_id = seed_transition._protection_proof.cursor.mandate_id
        assert mandate_id is not None
        mandate = _mandate(
            module,
            mandate_id=mandate_id,
            position_scope=scope,
            session_id=execution_core.SessionId("session-1"),
        )
        _, _, state = _start(module, seed_transition, mandate)
        mandates[scope] = mandate
        states[scope] = state

    source_scope = source_advance.execution.position.scope
    source_result = _reduce(
        module,
        states[source_scope],
        _projection(module, source_advance, mandates[source_scope]),
    )
    assert source_result.disposition is protection_disposition.APPLIED
    states[source_scope] = source_result.state

    by_scope: dict[PositionScope, list[object]] = {}
    for transition in killed.venue_transitions:
        by_scope.setdefault(
            transition._protection_proof.position_scope,
            [],
        ).append(transition)
    target_scope = seeded[1][0].position.scope
    assert len(by_scope[source_scope]) == 2
    assert len(by_scope[target_scope]) == 3

    for scope, transitions in by_scope.items():
        state = states[scope]
        mandate = mandates[scope]
        for transition in transitions:
            assert transition.execution.position.scope == scope
            assert transition._protection_proof.lineage_is_authentic
            projection = _projection(module, transition, mandate)
            assert projection.predecessor_cursor_ordinal == state._cursor_ordinal
            assert projection.predecessor_cursor_head == state._cursor_head
            result = _reduce(module, state, projection)
            assert result.disposition is protection_disposition.APPLIED
            state = result.state
        states[scope] = state

        suffix = scope.symbol_id.value.lower()
        next_transition = authority_fixtures._private_venue_apply(
            killed.state.venue,
            transitions[-1].execution,
            RequestedEffect(
                input_id=VenueInputId(f"protection-stale-next-{suffix}-input"),
                effect_id=EffectId(f"protection-stale-next-{suffix}-effect"),
                request_occurrence_id=RequestOccurrenceId(
                    f"protection-stale-next-{suffix}-occurrence"
                ),
                mandate_id=mandate.mandate_id,
                kind=EffectKind.SUBMIT,
                client_order_id=ClientOrderId(f"protection-stale-next-{suffix}-client"),
                symbol_id=scope.symbol_id,
                side=ExecutionSide.BUY,
                quantity=Quantity(1),
                economic_scope=f"protection-stale-next-{suffix}-scope".encode(),
                target_leg_key=None,
            ),
        )
        assert next_transition.disposition is VenueRecoveryDisposition.APPLIED
        next_result = _reduce(
            module,
            state,
            _projection(module, next_transition, mandate),
        )
        assert next_result.disposition is protection_disposition.APPLIED
        assert next_result.state._cursor_ordinal == (
            next_transition._protection_proof.cursor.ordinal
        )


def test_m1c_multi_scope_kill_bridges_registry_current_cursor_lag() -> None:
    module = _protection_module()
    authority_module = authority_fixtures._authority_module()
    killed, seeded, source_advance, target_catch_up, _ = (
        authority_fixtures._cursor_lag_multi_scope_kill_fixture(
            authority_module,
            "protection-kill-cursor-lag",
        )
    )
    (protection_disposition,) = _required(module, "ProtectionDisposition")
    states: dict[PositionScope, object] = {}
    mandates: dict[PositionScope, object] = {}
    for execution, seed_transition in seeded:
        scope = execution.position.scope
        mandate_id = seed_transition._protection_proof.cursor.mandate_id
        assert mandate_id is not None
        mandate = _mandate(
            module,
            mandate_id=mandate_id,
            position_scope=scope,
            session_id=execution_core.SessionId("session-1"),
        )
        _, _, state = _start(module, seed_transition, mandate)
        mandates[scope] = mandate
        states[scope] = state

    for transition in (source_advance, target_catch_up):
        scope = transition._protection_proof.position_scope
        result = _reduce(
            module,
            states[scope],
            _projection(module, transition, mandates[scope]),
        )
        assert result.disposition is protection_disposition.APPLIED
        states[scope] = result.state

    by_scope: dict[PositionScope, list[object]] = {}
    for transition in killed.venue_transitions:
        by_scope.setdefault(
            transition._protection_proof.position_scope,
            [],
        ).append(transition)
    assert set(by_scope) == set(states)
    assert all(len(transitions) == 3 for transitions in by_scope.values())

    for scope, transitions in by_scope.items():
        state = states[scope]
        mandate = mandates[scope]
        for transition in transitions:
            projection = _projection(module, transition, mandate)
            assert (
                projection.predecessor_execution_commitment
                == state.execution_commitment
            )
            result = _reduce(module, state, projection)
            assert result.disposition is protection_disposition.APPLIED
            state = result.state
        states[scope] = state


def test_m1c_manual_flatten_provenance_remains_consumable_in_order() -> None:
    module = _protection_module()
    mandate, closed, protection_state, goal = _emergency_goal_fixture(
        module,
        label="goal-m1c-flatten-provenance",
    )
    (protection_disposition,) = _required(module, "ProtectionDisposition")

    def consume(transition: object) -> None:
        nonlocal protection_state
        result = _reduce(
            module,
            protection_state,
            _projection(module, transition, mandate),
        )
        assert result.disposition is protection_disposition.APPLIED
        protection_state = result.state

    known_request = BrokerEffectRequest(
        effect_id=EffectId("protection-flatten-known-effect"),
        request_occurrence_id=RequestOccurrenceId(
            "protection-flatten-known-occurrence"
        ),
        mandate_id=goal.mandate_id,
        kind=EffectKind.SUBMIT,
        client_order_id=ClientOrderId("protection-flatten-known-client"),
        symbol_id=SYMBOL,
        side=ExecutionSide.BUY,
        quantity=Quantity(1),
        economic_scope=goal.protection_commitment,
        target_leg_key=None,
    )
    authority = _forge_authority_predecessor(
        closed.book,
        session_id=goal.session_id,
    )
    created = apply_execution_authority_input(
        authority,
        closed.execution,
        CreateBrokerEffect(
            input_id=execution_core.AuthorityInputId("flatten-known-create"),
            session_id=goal.session_id,
            request=known_request,
            manual_flatten_id=None,
            emergency_grant_id=None,
        ),
    )
    assert created.disposition is AuthorityDisposition.APPLIED
    assert len(created.venue_transitions) == 1
    consume(created.venue_transitions[0])

    claimed = apply_execution_authority_input(
        created.state,
        closed.execution,
        ClaimEffect(
            input_id=execution_core.AuthorityInputId("flatten-known-claim"),
            effect_id=known_request.effect_id,
            claim_occurrence_id=ClaimOccurrenceId("flatten-known-claim-occurrence"),
        ),
    )
    assert claimed.disposition is AuthorityDisposition.APPLIED
    assert len(claimed.venue_transitions) == 1
    consume(claimed.venue_transitions[0])

    acknowledged = venue_fixtures.apply_venue_recovery_input(
        claimed.state.venue,
        closed.execution,
        RecordTransportOutcome(
            input_id=VenueInputId("flatten-known-outcome"),
            effect_id=known_request.effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    consume(acknowledged)
    current_authority = copy(claimed.state)
    object.__setattr__(current_authority, "venue", acknowledged.book)

    legs = (
        VenueLegKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            order_id=OrderId("flatten-known-leg-one"),
        ),
        VenueLegKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            order_id=OrderId("flatten-known-leg-two"),
        ),
    )
    for ordinal, leg_key in enumerate(legs, start=1):
        discovered = venue_fixtures.apply_venue_recovery_input(
            current_authority.venue,
            closed.execution,
            DiscoverVenueLeg(
                input_id=VenueInputId(f"flatten-known-discover-{ordinal}"),
                effect_id=known_request.effect_id,
                leg_key=leg_key,
                observation_id=VenueObservationId(
                    f"flatten-known-observation-{ordinal}"
                ),
            ),
        )
        consume(discovered)
        current_authority = copy(current_authority)
        object.__setattr__(current_authority, "venue", discovered.book)

    local_request = RequestedEffect(
        input_id=VenueInputId("flatten-local-request"),
        effect_id=EffectId("protection-flatten-local-effect"),
        request_occurrence_id=RequestOccurrenceId(
            "protection-flatten-local-occurrence"
        ),
        mandate_id=goal.mandate_id,
        kind=EffectKind.SUBMIT,
        client_order_id=ClientOrderId("protection-flatten-local-client"),
        symbol_id=SYMBOL,
        side=ExecutionSide.BUY,
        quantity=Quantity(1),
        economic_scope=goal.protection_commitment,
        target_leg_key=None,
    )
    local = venue_fixtures.apply_venue_recovery_input(
        current_authority.venue,
        closed.execution,
        local_request,
    )
    assert local.disposition is VenueRecoveryDisposition.APPLIED
    consume(local)
    current_authority = copy(current_authority)
    object.__setattr__(current_authority, "venue", local.book)

    reducing = copy(current_authority)
    object.__setattr__(reducing, "mode", TradingMode.REDUCING)
    command = execution_core.BeginManualFlatten(
        input_id=execution_core.AuthorityInputId("flatten-provenance-begin"),
        flatten_id=execution_core.ManualFlattenId("flatten-provenance"),
        session_id=goal.session_id,
        symbol_id=SYMBOL,
        actor=execution_core.ActorId("flatten-provenance-operator"),
        reason="stand down local BUY and cancel every known BUY leg",
        evidence_reference=EvidenceReference("flatten-provenance-evidence"),
        emergency_grant_id=None,
    )
    flattened = apply_execution_authority_input(
        reducing,
        closed.execution,
        command,
    )
    assert flattened.disposition is AuthorityDisposition.APPLIED
    assert len(flattened.created_effect_ids) == 2
    assert len(flattened.venue_transitions) == 4
    for ordinal in range(1, len(flattened.venue_transitions)):
        predecessor = flattened.venue_transitions[ordinal - 1]
        successor = flattened.venue_transitions[ordinal]
        assert (
            successor._protection_proof.predecessor_cursor
            == predecessor._protection_proof.cursor
        )
    for transition, effect_id in zip(
        flattened.venue_transitions[-2:],
        flattened.created_effect_ids,
        strict=True,
    ):
        effect = transition.book.effect(effect_id)
        assert effect is not None
        assert effect.scope.kind is EffectKind.CANCEL
    for transition in flattened.venue_transitions:
        consume(transition)
    assert protection_state._cursor_ordinal == (
        flattened.venue_transitions[-1]._protection_proof.cursor.ordinal
    )
    assert flattened.venue_transitions[-1].book == flattened.state.venue

    replay = apply_execution_authority_input(
        flattened.state,
        closed.execution,
        command,
    )
    assert replay.disposition is AuthorityDisposition.EXACT_REPLAY
    assert replay.venue_transitions == ()


def test_m1c_manual_flatten_retry_provenance_accepts_the_next_projection() -> None:
    module = _protection_module()
    authority_module = authority_fixtures._authority_module()
    retired, execution, _ = authority_fixtures._manual_flatten_retry_fixture(
        authority_module,
        "protection-flatten-retry",
    )
    assert len(retired.venue_transitions) == 2
    mandate_id = MandateId("protection-flatten-retry-sell-mandate")
    mandate = _mandate(
        module,
        mandate_id=mandate_id,
        position_scope=execution.position.scope,
        session_id=execution_core.SessionId("session-1"),
    )
    _, _, state = _start(module, retired.venue_transitions[0], mandate)
    second = _reduce(
        module,
        state,
        _projection(module, retired.venue_transitions[1], mandate),
    )
    (protection_disposition,) = _required(module, "ProtectionDisposition")
    assert second.disposition is protection_disposition.APPLIED
    assert second.state._cursor_ordinal == (
        retired.venue_transitions[1]._protection_proof.cursor.ordinal
    )

    next_transition = venue_fixtures.apply_venue_recovery_input(
        retired.state.venue,
        execution,
        RequestedEffect(
            input_id=VenueInputId("protection-flatten-retry-next-input"),
            effect_id=EffectId("protection-flatten-retry-next-effect"),
            request_occurrence_id=RequestOccurrenceId(
                "protection-flatten-retry-next-occurrence"
            ),
            mandate_id=mandate_id,
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId("protection-flatten-retry-next-client"),
            symbol_id=execution.position.scope.symbol_id,
            side=ExecutionSide.BUY,
            quantity=Quantity(1),
            economic_scope=b"protection-flatten-retry-next-scope",
            target_leg_key=None,
        ),
    )
    next_result = _reduce(
        module,
        second.state,
        _projection(module, next_transition, mandate),
    )
    assert next_result.disposition is protection_disposition.APPLIED
    assert next_result.state._cursor_ordinal == (
        next_transition._protection_proof.cursor.ordinal
    )


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
    market_source_type, generation_type, occurrence_id_type, session_type = _required(
        execution_core,
        "MarketDataSourceId",
        "MarketStreamGenerationId",
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
            generation_type,
            occurrence_id_type,
            session_type,
        }
    )
    protection_enum_types = _required(
        module,
        "MarketKind",
        "MarketSequenceMode",
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
                ("SEQUENCED", "SOURCE_TIME"),
                ("FLOOR_ONLY", "TRAIL_ACTIVE", "EXIT_NORMAL", "HARD_BAIL", "FLAT"),
                ("NORMAL", "EMERGENCY"),
                ("APPLIED", "EXACT_REPLAY", "STALE", "REFUSED"),
                (
                    "LATE_POSITIVE_AFTER_FLAT",
                    "MARKET_BASELINE_REQUIRED",
                    "MARKET_COORDINATE_EXHAUSTED",
                ),
            ),
            strict=True,
        )
    )
    for retained in (mandate, projection, state, goal, occurrence, replay):
        _assert_passive_value_graph(
            retained,
            allowed_shapes=allowed_shapes,
            allowed_init_shapes={
                type(occurrence): _MARKET_OCCURRENCE_INIT_FIELDS,
            },
            trusted_leaf_types=trusted_leaf_types,
            allowed_enum_shapes=allowed_enum_shapes,
        )


# ADR-023 literal oracles intentionally do not call production canonical encoders.
_OCCURRENCE_DOMAIN = b"execution-core/market-occurrence/v1"
_CURSOR_DOMAIN = b"execution-core/protection-market-cursor/v1"


def _literal_pack_parts(domain: bytes, *parts: bytes) -> bytes:
    packed = len(domain).to_bytes(4, "big") + domain
    for part in parts:
        packed += len(part).to_bytes(8, "big") + part
    return packed


def _literal_pack_parts_variant(
    domain: bytes,
    *parts: bytes,
    domain_prefix_width: int = 4,
    part_prefix_width: int = 8,
) -> bytes:
    packed = len(domain).to_bytes(domain_prefix_width, "big") + domain
    for part in parts:
        packed += len(part).to_bytes(part_prefix_width, "big") + part
    return packed


def _literal_encode_text(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(8, "big") + encoded


def _literal_encode_int(value: int) -> bytes:
    magnitude = abs(value)
    encoded = magnitude.to_bytes(
        max(1, (magnitude.bit_length() + 7) // 8),
        "big",
    )
    return (
        (b"\x01" if value < 0 else b"\x00") + len(encoded).to_bytes(4, "big") + encoded
    )


def _literal_encode_fraction(value: Fraction) -> bytes:
    return sha256(
        _literal_pack_parts(
            b"execution-core/fraction/v1",
            _literal_encode_int(value.numerator),
            _literal_encode_int(value.denominator),
        )
    ).digest()


def _literal_encode_position_scope(scope: PositionScope) -> bytes:
    return _literal_pack_parts(
        b"execution-core/position-scope/v1",
        _literal_encode_text(scope.broker.value),
        _literal_encode_text(scope.environment.value),
        _literal_encode_text(scope.account.value),
        _literal_encode_text(scope.symbol_id.value),
    )


def _literal_encode_reported_price(value: ReportedPrice | None) -> bytes:
    if value is None:
        return sha256(
            _literal_pack_parts(b"execution-core/reported-price/none/v1")
        ).digest()
    return sha256(
        _literal_pack_parts(
            b"execution-core/reported-price/v1",
            _literal_encode_int(value.units.value),
            _literal_encode_fraction(Fraction(value.scale.value)),
            _literal_encode_int(value.tick.tick_units.value),
            _literal_encode_fraction(Fraction(value.tick.scale.value)),
        )
    ).digest()


def _literal_occurrence_preimage(
    *,
    source_id: str,
    position_scope: PositionScope,
    session_id: str,
    stream_generation_hex: str,
    market_epoch: int,
    source_sequence: int | None,
    source_time: int,
    kind: str,
    best_bid: ReportedPrice | None,
    best_ask: ReportedPrice | None,
    trade_price: ReportedPrice | None,
    atr_distance: ReportedPrice | None,
    structure_trail: ReportedPrice | None,
    halted: bool,
    domain: bytes = _OCCURRENCE_DOMAIN,
    endian: str = "big",
    include_evaluation_time: int | None = None,
    swap_part_indices: tuple[int, int] | None = None,
    domain_prefix_width: int = 4,
    part_prefix_width: int = 8,
    sequence_marker: bytes | None = None,
    absent_sequence_payload: bytes = b"\x00" * 8,
) -> bytes:
    sequence_present = source_sequence is not None
    parts = [
        _literal_encode_text(source_id),
        _literal_encode_position_scope(position_scope),
        _literal_encode_text(session_id),
        bytes.fromhex(stream_generation_hex),
        market_epoch.to_bytes(8, endian),
        (
            sequence_marker
            if sequence_marker is not None
            else (b"\x01" if sequence_present else b"\x00")
        ),
        (
            source_sequence.to_bytes(8, endian)
            if source_sequence is not None
            else absent_sequence_payload
        ),
        source_time.to_bytes(8, endian),
        _literal_encode_text(kind),
        _literal_encode_reported_price(best_bid),
        _literal_encode_reported_price(best_ask),
        _literal_encode_reported_price(trade_price),
        _literal_encode_reported_price(atr_distance),
        _literal_encode_reported_price(structure_trail),
        b"\x01" if halted else b"\x00",
    ]
    if include_evaluation_time is not None:
        parts.append(include_evaluation_time.to_bytes(8, endian))
    if swap_part_indices is not None:
        left, right = swap_part_indices
        parts[left], parts[right] = parts[right], parts[left]
    return _literal_pack_parts_variant(
        domain,
        *parts,
        domain_prefix_width=domain_prefix_width,
        part_prefix_width=part_prefix_width,
    )


def _literal_optional_u64(value: int | None) -> bytes:
    return (
        b"\x00" + b"\x00" * 8 if value is None else b"\x01" + value.to_bytes(8, "big")
    )


def _literal_optional_32(value: bytes | None) -> bytes:
    return b"\x00" + b"\x00" * 32 if value is None else b"\x01" + value


def _literal_cursor_preimage(
    *,
    stream_generation_hex: str,
    sequence_mode: int,
    occurrence_epoch: int | None,
    committed_epoch: int | None,
    expected_epoch: int | None,
    source_sequence: int | None,
    source_time: int | None,
    evaluation_time: int | None,
    occurrence_identity: bytes | None,
    halted: bool,
    baseline_required: bool,
    exhausted: bool,
    last_primary_commitment: bytes | None,
    hard_bid_identity: bytes | None,
    hard_bid_source_time: int | None,
    trade_identity: bytes | None,
    trade_source_time: int | None,
    trail_bid_identity: bytes | None,
    trail_bid_source_time: int | None,
) -> bytes:
    parts = (
        bytes.fromhex(stream_generation_hex),
        bytes((sequence_mode,)),
        _literal_optional_u64(occurrence_epoch),
        _literal_optional_u64(committed_epoch),
        _literal_optional_u64(expected_epoch),
        _literal_optional_u64(source_sequence),
        _literal_optional_u64(source_time),
        _literal_optional_u64(evaluation_time),
        _literal_optional_32(occurrence_identity),
        b"\x01" if halted else b"\x00",
        b"\x01" if baseline_required else b"\x00",
        b"\x01" if exhausted else b"\x00",
        _literal_optional_32(last_primary_commitment),
        _literal_optional_32(hard_bid_identity),
        _literal_optional_u64(hard_bid_source_time),
        _literal_optional_32(trade_identity),
        _literal_optional_u64(trade_source_time),
        _literal_optional_32(trail_bid_identity),
        _literal_optional_u64(trail_bid_source_time),
    )
    assert len(parts) == 19
    return _literal_pack_parts(_CURSOR_DOMAIN, *parts)


_SEQUENCED_OCCURRENCE_PREIMAGE_HEX = (
    "00000023657865637574696f6e2d636f72652f6d61726b65742d6f6363757272656e63652f7631000000000000001300"
    "0000000000000b7369702d7072696d617279000000000000007e00000020657865637574696f6e2d636f72652f706f73"
    "6974696f6e2d73636f70652f7631000000000000000e0000000000000006616c70616361000000000000000d00000000"
    "0000000570617065720000000000000013000000000000000b6163636f756e742d303031000000000000000c00000000"
    "000000044141504c0000000000000015000000000000000d73657373696f6e2d7274682d310000000000000020111111"
    "111111111111111111111111111111111111111111111111111111111100000000000000080000000000000000000000"
    "000000000101000000000000000800000000000000000000000000000008000000000000000000000000000000100000"
    "000000000008424553545f4249440000000000000020b7e19ab62a158aea307a7e8c5361922d3effcfb7161414f2430f"
    "f180e5b155be00000000000000206b3ed3cdd0d94d0d276896b235600d24cb38bdb3d89c6a92b4b5b8a299a2a5d00000"
    "000000000020ff749ef794de421a13efa87be274fbaa9374838910b4aa0b4051fd3ccc7ef7890000000000000020ff74"
    "9ef794de421a13efa87be274fbaa9374838910b4aa0b4051fd3ccc7ef7890000000000000020ff749ef794de421a13ef"
    "a87be274fbaa9374838910b4aa0b4051fd3ccc7ef789000000000000000100"
)
_SOURCE_TIME_OCCURRENCE_PREIMAGE_HEX = (
    "00000023657865637574696f6e2d636f72652f6d61726b65742d6f6363757272656e63652f7631000000000000001300"
    "0000000000000b7369702d7072696d617279000000000000007e00000020657865637574696f6e2d636f72652f706f73"
    "6974696f6e2d73636f70652f7631000000000000000e0000000000000006616c70616361000000000000000d00000000"
    "0000000570617065720000000000000013000000000000000b6163636f756e742d303031000000000000000c00000000"
    "000000044141504c0000000000000015000000000000000d73657373696f6e2d7274682d310000000000000020222222"
    "222222222222222222222222222222222222222222222222222222222200000000000000080000000000000007000000"
    "000000000100000000000000000800000000000000000000000000000008000000000000007b00000000000000100000"
    "000000000008424553545f4249440000000000000020bb3ca4fe9ce7f0f1031b178e8b298e52162dc490a61a786600be"
    "b6fd65840b280000000000000020e850ca419ee475673cef8f2bc6ec0d365978e456d08620022e3f4e7152316a310000"
    "000000000020ff749ef794de421a13efa87be274fbaa9374838910b4aa0b4051fd3ccc7ef7890000000000000020fc95"
    "a555f8203fe03a16045a018e183545acb5e7a44ef4f0786d7e1194be60f70000000000000020e3020031fc165c1188e4"
    "8e795154d44bedbf772df76b1aed0f7b3dc3d6496d16000000000000000100"
)
_TRADE_OCCURRENCE_PREIMAGE_HEX = (
    "00000023657865637574696f6e2d636f72652f6d61726b65742d6f6363757272656e63652f7631000000000000001300"
    "0000000000000b7369702d7072696d617279000000000000007e00000020657865637574696f6e2d636f72652f706f73"
    "6974696f6e2d73636f70652f7631000000000000000e0000000000000006616c70616361000000000000000d00000000"
    "0000000570617065720000000000000013000000000000000b6163636f756e742d303031000000000000000c00000000"
    "000000044141504c0000000000000015000000000000000d73657373696f6e2d7274682d310000000000000020333333"
    "333333333333333333333333333333333333333333333333333333333300000000000000080000000000000009000000"
    "0000000001010000000000000008000000000000000a000000000000000800000000000000c8000000000000000d0000"
    "00000000000554524144450000000000000020ff749ef794de421a13efa87be274fbaa9374838910b4aa0b4051fd3ccc"
    "7ef7890000000000000020ff749ef794de421a13efa87be274fbaa9374838910b4aa0b4051fd3ccc7ef7890000000000"
    "00002035b4409f58105137bcf0e4bd01a71c3ec81485fb2b2d1482f71a8be1116ee9a60000000000000020ff749ef794"
    "de421a13efa87be274fbaa9374838910b4aa0b4051fd3ccc7ef7890000000000000020ff749ef794de421a13efa87be274"
    "fbaa9374838910b4aa0b4051fd3ccc7ef789000000000000000100"
)
_ABSENT_CURSOR_PREIMAGE_HEX = (
    "0000002a657865637574696f6e2d636f72652f70726f74656374696f6e2d6d61726b65742d637572736f722f76310000"
    "000000000020111111111111111111111111111111111111111111111111111111111111111100000000000000010000"
    "000000000000090000000000000000000000000000000009000000000000000000000000000000000901000000000000"
    "000000000000000000090000000000000000000000000000000009000000000000000000000000000000000900000000"
    "000000000000000000000000210000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000001000000000000000001010000000000000001000000000000000021000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000002100000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000090000000000000000000000000000000021000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000900000000000000000000000000000000210000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000009000000000000000000"
)
_PRESENT_CURSOR_PREIMAGE_HEX = (
    "0000002a657865637574696f6e2d636f72652f70726f74656374696f6e2d6d61726b65742d637572736f722f76310000"
    "000000000020222222222222222222222222222222222222222222222222222222222222222200000000000000010100"
    "000000000000090100000000000000070000000000000009010000000000000007000000000000000901000000000000"
    "00080000000000000009000000000000000000000000000000000901000000000000007b000000000000000901000000"
    "00000000820000000000000021015fd6cf1fc78dda1d26965a9579ab48668b2d6276d88f947d24ae623a631d310c0000"
    "00000000000101000000000000000101000000000000000100000000000000002101bb3ca4fe9ce7f0f1031b178e8b29"
    "8e52162dc490a61a786600beb6fd65840b28000000000000002101333333333333333333333333333333333333333333"
    "333333333333333333333300000000000000090100000000000000780000000000000021014444444444444444444444"
    "444444444444444444444444444444444444444444000000000000000901000000000000007900000000000000210155"
    "55555555555555555555555555555555555555555555555555555555555555000000000000000901000000000000007a"
)
_SEQUENCED_PRESENT_CURSOR_PREIMAGE_HEX = (
    "0000002a657865637574696f6e2d636f72652f70726f74656374696f6e2d6d61726b65742d637572736f722f76310000"
    "000000000020333333333333333333333333333333333333333333333333333333333333333300000000000000010000"
    "000000000000090100000000000000090000000000000009010000000000000009000000000000000900000000000000"
    "0000000000000000000901000000000000000a00000000000000090100000000000000c8000000000000000901000000"
    "00000000cd0000000000000021014f45b5f91f633c4b2a72b5bd8b48da27159eb03907692e0b32ce0e132c6e50500000"
    "0000000000010000000000000000010000000000000000010000000000000000210135b4409f58105137bcf0e4bd01a7"
    "1c3ec81485fb2b2d1482f71a8be1116ee9a6000000000000002101444444444444444444444444444444444444444444"
    "444444444444444444444400000000000000090100000000000000c60000000000000021014f45b5f91f633c4b2a72b5"
    "bd8b48da27159eb03907692e0b32ce0e132c6e505000000000000000090100000000000000c800000000000000210155"
    "5555555555555555555555555555555555555555555555555555555555555500000000000000090100000000000000c7"
)


def test_literal_occurrence_known_answer_oracle_is_failure_capable() -> None:
    sequenced = _literal_occurrence_preimage(
        source_id="sip-primary",
        position_scope=POSITION_SCOPE,
        session_id="session-rth-1",
        stream_generation_hex="11" * 32,
        market_epoch=0,
        source_sequence=0,
        source_time=0,
        kind="BEST_BID",
        best_bid=_price(100),
        best_ask=_price(101),
        trade_price=None,
        atr_distance=None,
        structure_trail=None,
        halted=False,
    )
    source_time = _literal_occurrence_preimage(
        source_id="sip-primary",
        position_scope=POSITION_SCOPE,
        session_id="session-rth-1",
        stream_generation_hex="22" * 32,
        market_epoch=7,
        source_sequence=None,
        source_time=123,
        kind="BEST_BID",
        best_bid=_price(110),
        best_ask=_price(111),
        trade_price=None,
        atr_distance=_price(3),
        structure_trail=_price(102),
        halted=False,
    )
    trade = _literal_occurrence_preimage(
        source_id="sip-primary",
        position_scope=POSITION_SCOPE,
        session_id="session-rth-1",
        stream_generation_hex="33" * 32,
        market_epoch=9,
        source_sequence=10,
        source_time=200,
        kind="TRADE",
        best_bid=None,
        best_ask=None,
        trade_price=_price(115),
        atr_distance=None,
        structure_trail=None,
        halted=False,
    )
    assert sequenced == bytes.fromhex(_SEQUENCED_OCCURRENCE_PREIMAGE_HEX)
    assert source_time == bytes.fromhex(_SOURCE_TIME_OCCURRENCE_PREIMAGE_HEX)
    assert trade == bytes.fromhex(_TRADE_OCCURRENCE_PREIMAGE_HEX)
    assert sha256(sequenced).hexdigest() == (
        "75d3ede2c6cd8f01bc0096eb7bf66efc088815ff5a25b2f65c9403fd85a4992c"
    )
    assert sha256(source_time).hexdigest() == (
        "5fd6cf1fc78dda1d26965a9579ab48668b2d6276d88f947d24ae623a631d310c"
    )
    assert sha256(trade).hexdigest() == (
        "4f45b5f91f633c4b2a72b5bd8b48da27159eb03907692e0b32ce0e132c6e5050"
    )

    sequenced_mutants = (
        _literal_occurrence_preimage(
            source_id="sip-primary",
            position_scope=POSITION_SCOPE,
            session_id="session-rth-1",
            stream_generation_hex="11" * 32,
            market_epoch=0,
            source_sequence=0,
            source_time=0,
            kind="BEST_BID",
            best_bid=_price(100),
            best_ask=_price(101),
            trade_price=None,
            atr_distance=None,
            structure_trail=None,
            halted=False,
            domain=b"execution-core/market-occurrence/v0",
        ),
        _literal_occurrence_preimage(
            source_id="sip-primary",
            position_scope=POSITION_SCOPE,
            session_id="session-rth-1",
            stream_generation_hex="11" * 32,
            market_epoch=0,
            source_sequence=0,
            source_time=0,
            kind="BEST_BID",
            best_bid=_price(100),
            best_ask=_price(101),
            trade_price=None,
            atr_distance=None,
            structure_trail=None,
            halted=False,
            swap_part_indices=(0, 1),
        ),
        _literal_occurrence_preimage(
            source_id="sip-primary",
            position_scope=POSITION_SCOPE,
            session_id="session-rth-1",
            stream_generation_hex="11" * 32,
            market_epoch=0,
            source_sequence=0,
            source_time=0,
            kind="BEST_BID",
            best_bid=_price(100),
            best_ask=_price(101),
            trade_price=None,
            atr_distance=None,
            structure_trail=None,
            halted=False,
            domain_prefix_width=8,
        ),
        _literal_occurrence_preimage(
            source_id="sip-primary",
            position_scope=POSITION_SCOPE,
            session_id="session-rth-1",
            stream_generation_hex="11" * 32,
            market_epoch=0,
            source_sequence=0,
            source_time=0,
            kind="BEST_BID",
            best_bid=_price(100),
            best_ask=_price(101),
            trade_price=None,
            atr_distance=None,
            structure_trail=None,
            halted=False,
            part_prefix_width=4,
        ),
        _literal_occurrence_preimage(
            source_id="sip-primary",
            position_scope=POSITION_SCOPE,
            session_id="session-rth-1",
            stream_generation_hex="11" * 32,
            market_epoch=0,
            source_sequence=0,
            source_time=0,
            kind="BEST_BID",
            best_bid=_price(100),
            best_ask=_price(101),
            trade_price=None,
            atr_distance=None,
            structure_trail=None,
            halted=False,
            sequence_marker=b"\x00",
        ),
        _literal_occurrence_preimage(
            source_id="sip-primary",
            position_scope=POSITION_SCOPE,
            session_id="session-rth-1",
            stream_generation_hex="11" * 32,
            market_epoch=0,
            source_sequence=0,
            source_time=0,
            kind="BEST_BID",
            best_bid=_price(100),
            best_ask=_price(101),
            trade_price=None,
            atr_distance=None,
            structure_trail=None,
            halted=False,
            include_evaluation_time=5,
        ),
    )
    source_time_mutants = (
        _literal_occurrence_preimage(
            source_id="sip-primary",
            position_scope=POSITION_SCOPE,
            session_id="session-rth-1",
            stream_generation_hex="22" * 32,
            market_epoch=7,
            source_sequence=None,
            source_time=123,
            kind="BEST_BID",
            best_bid=_price(110),
            best_ask=_price(111),
            trade_price=None,
            atr_distance=_price(3),
            structure_trail=_price(102),
            halted=False,
            endian="little",
        ),
        _literal_occurrence_preimage(
            source_id="sip-primary",
            position_scope=POSITION_SCOPE,
            session_id="session-rth-1",
            stream_generation_hex="22" * 32,
            market_epoch=7,
            source_sequence=None,
            source_time=123,
            kind="BEST_BID",
            best_bid=_price(110),
            best_ask=_price(111),
            trade_price=None,
            atr_distance=_price(3),
            structure_trail=_price(102),
            halted=False,
            sequence_marker=b"\x01",
        ),
        _literal_occurrence_preimage(
            source_id="sip-primary",
            position_scope=POSITION_SCOPE,
            session_id="session-rth-1",
            stream_generation_hex="22" * 32,
            market_epoch=7,
            source_sequence=None,
            source_time=123,
            kind="BEST_BID",
            best_bid=_price(110),
            best_ask=_price(111),
            trade_price=None,
            atr_distance=_price(3),
            structure_trail=_price(102),
            halted=False,
            absent_sequence_payload=b"\x01" + b"\x00" * 7,
        ),
    )
    assert all(mutant != sequenced for mutant in sequenced_mutants)
    assert all(mutant != source_time for mutant in source_time_mutants)


def test_literal_occurrence_identity_covers_every_immutable_field_only() -> None:
    (symbol_type,) = _required(execution_core, "SymbolId")
    base = {
        "source_id": "sip-primary",
        "position_scope": POSITION_SCOPE,
        "session_id": "session-rth-1",
        "stream_generation_hex": "11" * 32,
        "market_epoch": 7,
        "source_sequence": 8,
        "source_time": 9,
        "kind": "BEST_BID",
        "best_bid": _price(100),
        "best_ask": _price(101),
        "trade_price": None,
        "atr_distance": None,
        "structure_trail": None,
        "halted": False,
    }
    canonical = _literal_occurrence_preimage(**base)
    immutable_mutations = (
        {"source_id": "sip-secondary"},
        {
            "position_scope": replace(
                POSITION_SCOPE,
                symbol_id=symbol_type("MSFT"),
            )
        },
        {"session_id": "session-rth-2"},
        {"stream_generation_hex": "22" * 32},
        {"market_epoch": 8},
        {"source_sequence": 9},
        {"source_time": 10},
        {"kind": "TRADE"},
        {"best_bid": _price(99)},
        {"best_ask": _price(102)},
        {"trade_price": _price(100)},
        {"atr_distance": _price(2)},
        {"structure_trail": _price(98)},
        {"halted": True},
    )
    for mutation in immutable_mutations:
        candidate = dict(base)
        candidate.update(mutation)
        assert _literal_occurrence_preimage(**candidate) != canonical

    with_evaluation_context = dict(base)
    with_evaluation_context["include_evaluation_time"] = 10
    assert _literal_occurrence_preimage(**with_evaluation_context) != canonical
    assert _literal_occurrence_preimage(**base) == canonical


def test_production_occurrence_preimage_matches_independent_known_answers() -> None:
    module = _protection_module()
    (preimage,) = _required(module, "_market_occurrence_preimage")
    sequenced = preimage(
        source_id="sip-primary",
        position_scope=POSITION_SCOPE,
        session_id="session-rth-1",
        stream_generation=bytes.fromhex("11" * 32),
        market_epoch=0,
        source_sequence=0,
        source_time=0,
        kind="BEST_BID",
        best_bid=_price(100),
        best_ask=_price(101),
        trade_price=None,
        atr_distance=None,
        structure_trail=None,
        halted=False,
    )
    source_time = preimage(
        source_id="sip-primary",
        position_scope=POSITION_SCOPE,
        session_id="session-rth-1",
        stream_generation=bytes.fromhex("22" * 32),
        market_epoch=7,
        source_sequence=None,
        source_time=123,
        kind="BEST_BID",
        best_bid=_price(110),
        best_ask=_price(111),
        trade_price=None,
        atr_distance=_price(3),
        structure_trail=_price(102),
        halted=False,
    )
    trade = preimage(
        source_id="sip-primary",
        position_scope=POSITION_SCOPE,
        session_id="session-rth-1",
        stream_generation=bytes.fromhex("33" * 32),
        market_epoch=9,
        source_sequence=10,
        source_time=200,
        kind="TRADE",
        best_bid=None,
        best_ask=None,
        trade_price=_price(115),
        atr_distance=None,
        structure_trail=None,
        halted=False,
    )
    assert sequenced == bytes.fromhex(_SEQUENCED_OCCURRENCE_PREIMAGE_HEX)
    assert source_time == bytes.fromhex(_SOURCE_TIME_OCCURRENCE_PREIMAGE_HEX)
    assert trade == bytes.fromhex(_TRADE_OCCURRENCE_PREIMAGE_HEX)

    generation_type, source_type, session_type = _required(
        execution_core,
        "MarketStreamGenerationId",
        "MarketDataSourceId",
        "SessionId",
    )
    constructor_cases = (
        (
            _occurrence(
                module,
                "kat-sequenced-constructor",
                bid=100,
                ask=101,
                sequence=0,
                source_time=0,
                evaluation_time=17,
                market_epoch=0,
                stream_generation=generation_type("11" * 32),
                source_id=source_type("sip-primary"),
                session_id=session_type("session-rth-1"),
            ),
            "75d3ede2c6cd8f01bc0096eb7bf66efc088815ff5a25b2f65c9403fd85a4992c",
        ),
        (
            _occurrence(
                module,
                "kat-source-time-constructor",
                bid=110,
                ask=111,
                sequence=None,
                source_time=123,
                evaluation_time=130,
                market_epoch=7,
                atr_distance=3,
                structure_trail=102,
                stream_generation=generation_type("22" * 32),
                source_id=source_type("sip-primary"),
                session_id=session_type("session-rth-1"),
            ),
            "5fd6cf1fc78dda1d26965a9579ab48668b2d6276d88f947d24ae623a631d310c",
        ),
        (
            _occurrence(
                module,
                "kat-trade-constructor",
                kind="TRADE",
                trade=115,
                sequence=10,
                source_time=200,
                evaluation_time=205,
                market_epoch=9,
                stream_generation=generation_type("33" * 32),
                source_id=source_type("sip-primary"),
                session_id=session_type("session-rth-1"),
            ),
            "4f45b5f91f633c4b2a72b5bd8b48da27159eb03907692e0b32ce0e132c6e5050",
        ),
    )
    for occurrence, expected_digest in constructor_cases:
        assert occurrence.occurrence_id.value == expected_digest

    source = inspect.getsource(module.MarketOccurrence)
    tree = ast.parse(textwrap.dedent(source))
    helper_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_market_occurrence_preimage"
    ]
    assert len(helper_calls) == 1


def test_production_occurrence_identity_is_immutable_field_sensitive_only() -> None:
    module = _protection_module()
    source_type, generation_type, session_type, symbol_type = _required(
        execution_core,
        "MarketDataSourceId",
        "MarketStreamGenerationId",
        "SessionId",
        "SymbolId",
    )
    base = _occurrence(
        module,
        "identity-base",
        bid=100,
        ask=101,
        sequence=7,
        source_time=8,
        evaluation_time=9,
        market_epoch=6,
    )
    same_identity = _occurrence(
        module,
        "identity-evaluation-context-only",
        bid=100,
        ask=101,
        sequence=7,
        source_time=8,
        evaluation_time=10,
        market_epoch=6,
    )
    assert same_identity.occurrence_id == base.occurrence_id

    variants = (
        _occurrence(
            module,
            "identity-source",
            bid=100,
            ask=101,
            sequence=7,
            source_time=8,
            evaluation_time=9,
            market_epoch=6,
            source_id=source_type("sip-secondary"),
        ),
        _occurrence(
            module,
            "identity-generation",
            bid=100,
            ask=101,
            sequence=7,
            source_time=8,
            evaluation_time=9,
            market_epoch=6,
            stream_generation=generation_type("22" * 32),
        ),
        _occurrence(
            module,
            "identity-scope",
            bid=100,
            ask=101,
            sequence=7,
            source_time=8,
            evaluation_time=9,
            market_epoch=6,
            position_scope=replace(
                POSITION_SCOPE,
                symbol_id=symbol_type("MSFT"),
            ),
        ),
        _occurrence(
            module,
            "identity-session",
            bid=100,
            ask=101,
            sequence=7,
            source_time=8,
            evaluation_time=9,
            market_epoch=6,
            session_id=session_type("session-rth-2"),
        ),
        _occurrence(
            module,
            "identity-epoch",
            bid=100,
            ask=101,
            sequence=7,
            source_time=8,
            evaluation_time=9,
            market_epoch=7,
        ),
        _occurrence(
            module,
            "identity-sequence",
            bid=100,
            ask=101,
            sequence=8,
            source_time=8,
            evaluation_time=9,
            market_epoch=6,
        ),
        _occurrence(
            module,
            "identity-source-time",
            bid=100,
            ask=101,
            sequence=7,
            source_time=9,
            evaluation_time=9,
            market_epoch=6,
        ),
        _occurrence(
            module,
            "identity-kind-and-payload",
            kind="TRADE",
            trade=100,
            sequence=7,
            source_time=8,
            evaluation_time=9,
            market_epoch=6,
        ),
        _occurrence(
            module,
            "identity-bid",
            bid=99,
            ask=101,
            sequence=7,
            source_time=8,
            evaluation_time=9,
            market_epoch=6,
        ),
        _occurrence(
            module,
            "identity-ask",
            bid=100,
            ask=102,
            sequence=7,
            source_time=8,
            evaluation_time=9,
            market_epoch=6,
        ),
        _occurrence(
            module,
            "identity-trail-inputs",
            bid=100,
            ask=101,
            sequence=7,
            source_time=8,
            evaluation_time=9,
            market_epoch=6,
            atr_distance=2,
            structure_trail=98,
        ),
        _occurrence(
            module,
            "identity-halt",
            bid=100,
            ask=101,
            sequence=7,
            source_time=8,
            evaluation_time=9,
            market_epoch=6,
            halted=True,
        ),
    )
    assert all(variant.occurrence_id != base.occurrence_id for variant in variants)


def test_literal_cursor_known_answer_oracle_is_failure_capable() -> None:
    absent = _literal_cursor_preimage(
        stream_generation_hex="11" * 32,
        sequence_mode=0,
        occurrence_epoch=None,
        committed_epoch=None,
        expected_epoch=0,
        source_sequence=None,
        source_time=None,
        evaluation_time=None,
        occurrence_identity=None,
        halted=False,
        baseline_required=True,
        exhausted=False,
        last_primary_commitment=None,
        hard_bid_identity=None,
        hard_bid_source_time=None,
        trade_identity=None,
        trade_source_time=None,
        trail_bid_identity=None,
        trail_bid_source_time=None,
    )
    present = _literal_cursor_preimage(
        stream_generation_hex="22" * 32,
        sequence_mode=1,
        occurrence_epoch=7,
        committed_epoch=7,
        expected_epoch=8,
        source_sequence=None,
        source_time=123,
        evaluation_time=130,
        occurrence_identity=bytes.fromhex(
            "5fd6cf1fc78dda1d26965a9579ab48668b2d6276d88f947d24ae623a631d310c"
        ),
        halted=True,
        baseline_required=True,
        exhausted=False,
        last_primary_commitment=_literal_encode_reported_price(_price(110)),
        hard_bid_identity=bytes.fromhex("33" * 32),
        hard_bid_source_time=120,
        trade_identity=bytes.fromhex("44" * 32),
        trade_source_time=121,
        trail_bid_identity=bytes.fromhex("55" * 32),
        trail_bid_source_time=122,
    )
    sequenced_present = _literal_cursor_preimage(
        stream_generation_hex="33" * 32,
        sequence_mode=0,
        occurrence_epoch=9,
        committed_epoch=9,
        expected_epoch=None,
        source_sequence=10,
        source_time=200,
        evaluation_time=205,
        occurrence_identity=bytes.fromhex(
            "4f45b5f91f633c4b2a72b5bd8b48da27159eb03907692e0b32ce0e132c6e5050"
        ),
        halted=False,
        baseline_required=False,
        exhausted=False,
        last_primary_commitment=_literal_encode_reported_price(_price(115)),
        hard_bid_identity=bytes.fromhex("44" * 32),
        hard_bid_source_time=198,
        trade_identity=bytes.fromhex(
            "4f45b5f91f633c4b2a72b5bd8b48da27159eb03907692e0b32ce0e132c6e5050"
        ),
        trade_source_time=200,
        trail_bid_identity=bytes.fromhex("55" * 32),
        trail_bid_source_time=199,
    )
    assert absent == bytes.fromhex(_ABSENT_CURSOR_PREIMAGE_HEX)
    assert present == bytes.fromhex(_PRESENT_CURSOR_PREIMAGE_HEX)
    assert sequenced_present == bytes.fromhex(_SEQUENCED_PRESENT_CURSOR_PREIMAGE_HEX)
    assert len(absent) == len(present) == len(sequenced_present) == 480
    assert sha256(absent).hexdigest() == (
        "f38159b3599dcee2f7798d98c729e4ff0cf64d7b1035b2934da88ffa59e20af8"
    )
    assert sha256(present).hexdigest() == (
        "b6f669db29246602042b752141ed3c6dbb71ef9107c52212da3ba9a30621c673"
    )
    assert sha256(sequenced_present).hexdigest() == (
        "0f8e4b245248bd83eb10ebe2f3f189e28fc088139f0cfa0bd926641ff4d94f51"
    )
    omitted_current_epoch = _literal_cursor_preimage(
        stream_generation_hex="22" * 32,
        sequence_mode=1,
        occurrence_epoch=None,
        committed_epoch=7,
        expected_epoch=8,
        source_sequence=None,
        source_time=123,
        evaluation_time=130,
        occurrence_identity=bytes.fromhex(
            "5fd6cf1fc78dda1d26965a9579ab48668b2d6276d88f947d24ae623a631d310c"
        ),
        halted=True,
        baseline_required=True,
        exhausted=False,
        last_primary_commitment=_literal_encode_reported_price(_price(110)),
        hard_bid_identity=bytes.fromhex("33" * 32),
        hard_bid_source_time=120,
        trade_identity=bytes.fromhex("44" * 32),
        trade_source_time=121,
        trail_bid_identity=bytes.fromhex("55" * 32),
        trail_bid_source_time=122,
    )
    assert omitted_current_epoch != present


def test_literal_cursor_preimage_binds_all_nineteen_parts_independently() -> None:
    base = {
        "stream_generation_hex": "22" * 32,
        "sequence_mode": 1,
        "occurrence_epoch": 7,
        "committed_epoch": 7,
        "expected_epoch": 8,
        "source_sequence": None,
        "source_time": 123,
        "evaluation_time": 130,
        "occurrence_identity": bytes.fromhex(
            "5fd6cf1fc78dda1d26965a9579ab48668b2d6276d88f947d24ae623a631d310c"
        ),
        "halted": True,
        "baseline_required": True,
        "exhausted": False,
        "last_primary_commitment": _literal_encode_reported_price(_price(110)),
        "hard_bid_identity": bytes.fromhex("33" * 32),
        "hard_bid_source_time": 120,
        "trade_identity": bytes.fromhex("44" * 32),
        "trade_source_time": 121,
        "trail_bid_identity": bytes.fromhex("55" * 32),
        "trail_bid_source_time": 122,
    }
    canonical = _literal_cursor_preimage(**base)
    mutations = (
        {"stream_generation_hex": "23" * 32},
        {"sequence_mode": 0},
        {"occurrence_epoch": 8},
        {"committed_epoch": 8},
        {"expected_epoch": 9},
        {"source_sequence": 124},
        {"source_time": 124},
        {"evaluation_time": 131},
        {"occurrence_identity": bytes.fromhex("66" * 32)},
        {"halted": False},
        {"baseline_required": False},
        {"exhausted": True},
        {"last_primary_commitment": bytes.fromhex("77" * 32)},
        {"hard_bid_identity": bytes.fromhex("88" * 32)},
        {"hard_bid_source_time": 124},
        {"trade_identity": bytes.fromhex("99" * 32)},
        {"trade_source_time": 125},
        {"trail_bid_identity": bytes.fromhex("aa" * 32)},
        {"trail_bid_source_time": 126},
    )
    assert len(mutations) == 19
    for mutation in mutations:
        candidate = dict(base)
        candidate.update(mutation)
        assert _literal_cursor_preimage(**candidate) != canonical


def test_production_cursor_preimage_matches_independent_known_answers() -> None:
    module = _protection_module()
    (preimage,) = _required(module, "_protection_market_cursor_preimage")
    absent = preimage(
        stream_generation=bytes.fromhex("11" * 32),
        sequence_mode=0,
        occurrence_epoch=None,
        committed_epoch=None,
        expected_epoch=0,
        source_sequence=None,
        source_time=None,
        evaluation_time=None,
        occurrence_identity=None,
        halted=False,
        baseline_required=True,
        exhausted=False,
        last_primary_commitment=None,
        hard_bid_identity=None,
        hard_bid_source_time=None,
        trade_identity=None,
        trade_source_time=None,
        trail_bid_identity=None,
        trail_bid_source_time=None,
    )
    present = preimage(
        stream_generation=bytes.fromhex("22" * 32),
        sequence_mode=1,
        occurrence_epoch=7,
        committed_epoch=7,
        expected_epoch=8,
        source_sequence=None,
        source_time=123,
        evaluation_time=130,
        occurrence_identity=bytes.fromhex(
            "5fd6cf1fc78dda1d26965a9579ab48668b2d6276d88f947d24ae623a631d310c"
        ),
        halted=True,
        baseline_required=True,
        exhausted=False,
        last_primary_commitment=_literal_encode_reported_price(_price(110)),
        hard_bid_identity=bytes.fromhex("33" * 32),
        hard_bid_source_time=120,
        trade_identity=bytes.fromhex("44" * 32),
        trade_source_time=121,
        trail_bid_identity=bytes.fromhex("55" * 32),
        trail_bid_source_time=122,
    )
    sequenced_present = preimage(
        stream_generation=bytes.fromhex("33" * 32),
        sequence_mode=0,
        occurrence_epoch=9,
        committed_epoch=9,
        expected_epoch=None,
        source_sequence=10,
        source_time=200,
        evaluation_time=205,
        occurrence_identity=bytes.fromhex(
            "4f45b5f91f633c4b2a72b5bd8b48da27159eb03907692e0b32ce0e132c6e5050"
        ),
        halted=False,
        baseline_required=False,
        exhausted=False,
        last_primary_commitment=_literal_encode_reported_price(_price(115)),
        hard_bid_identity=bytes.fromhex("44" * 32),
        hard_bid_source_time=198,
        trade_identity=bytes.fromhex(
            "4f45b5f91f633c4b2a72b5bd8b48da27159eb03907692e0b32ce0e132c6e5050"
        ),
        trade_source_time=200,
        trail_bid_identity=bytes.fromhex("55" * 32),
        trail_bid_source_time=199,
    )
    assert absent == bytes.fromhex(_ABSENT_CURSOR_PREIMAGE_HEX)
    assert present == bytes.fromhex(_PRESENT_CURSOR_PREIMAGE_HEX)
    assert sequenced_present == bytes.fromhex(_SEQUENCED_PRESENT_CURSOR_PREIMAGE_HEX)
    assert len(absent) == len(present) == len(sequenced_present) == 480


def _state_cursor_digest_binding_violations(source: str) -> list[str]:
    tree = ast.parse(textwrap.dedent(source))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_state_commitment"
    ]
    if len(functions) != 1:
        return ["expected exactly one _state_commitment"]
    function = functions[0]
    violations: list[str] = []
    positional_parameters = tuple(argument.arg for argument in function.args.args)
    if (
        function.decorator_list
        or function.args.posonlyargs
        or function.args.vararg is not None
        or function.args.kwonlyargs
        or function.args.kwarg is not None
        or function.args.defaults
        or function.args.kw_defaults
        or positional_parameters != _ADR023_STATE_COMMITMENT_PARAMETERS
    ):
        violations.append(
            f"state commitment signature differs: observed={positional_parameters!r}"
        )
    if not (
        len(function.body) == 1
        and isinstance(function.body[0], ast.Return)
        and isinstance(function.body[0].value, ast.Call)
        and isinstance(function.body[0].value.func, ast.Name)
        and function.body[0].value.func.id == "_commit_parts"
    ):
        violations.append("state commitment must be one straight-line return")
    commit_calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_commit_parts"
    ]
    if len(commit_calls) != 1:
        violations.append("state commitment must own one _commit_parts call")
        return violations

    commit_call = commit_calls[0]
    expected_argument_count = 1 + len(_ADR023_STATE_COMMITMENT_PART_SOURCES)
    if len(commit_call.args) != expected_argument_count:
        violations.append(
            "state commitment must pass exactly 15 ordered commitment arguments"
        )
    if (
        commit_call.keywords
        or not commit_call.args
        or not isinstance(commit_call.args[0], ast.Constant)
        or commit_call.args[0].value != b"execution-core/position-protection-state/v4"
        or any(isinstance(part, ast.Starred) for part in commit_call.args)
    ):
        violations.append("state commitment must use the exact v4 domain part")
    for index, expected_source in enumerate(
        _ADR023_STATE_COMMITMENT_PART_SOURCES,
        start=1,
    ):
        if expected_source == "<CURSOR_DIGEST>" or index >= len(commit_call.args):
            continue
        expected_expression = ast.parse(
            expected_source,
            mode="eval",
            feature_version=(3, 11),
        ).body
        if ast.dump(commit_call.args[index], include_attributes=False) != ast.dump(
            expected_expression,
            include_attributes=False,
        ):
            violations.append(
                f"state commitment part {index} differs: expected {expected_source}"
            )
    cursor_digests: list[tuple[ast.Call, ast.Call]] = []
    for part in commit_call.args[1:]:
        if not (
            isinstance(part, ast.Call)
            and isinstance(part.func, ast.Attribute)
            and part.func.attr == "digest"
            and not part.args
            and not part.keywords
            and isinstance(part.func.value, ast.Call)
            and isinstance(part.func.value.func, ast.Name)
            and part.func.value.func.id == "_sha256"
            and len(part.func.value.args) == 1
            and not part.func.value.keywords
            and isinstance(part.func.value.args[0], ast.Call)
            and isinstance(part.func.value.args[0].func, ast.Name)
            and part.func.value.args[0].func.id == "_protection_market_cursor_preimage"
        ):
            continue
        cursor_digests.append((part, part.func.value.args[0]))

    if len(cursor_digests) != 1:
        violations.append("state commitment must bind one exact cursor digest part")
        return violations

    digest_part, preimage_call = cursor_digests[0]
    expected_digest_index = 1 + _ADR023_STATE_COMMITMENT_PART_SOURCES.index(
        "<CURSOR_DIGEST>"
    )
    if (
        expected_digest_index >= len(commit_call.args)
        or commit_call.args[expected_digest_index] is not digest_part
    ):
        violations.append("state commitment cursor digest is out of order")
    if preimage_call.args or any(
        keyword.arg is None for keyword in preimage_call.keywords
    ):
        violations.append("cursor preimage call must use fixed named arguments")
    observed = tuple(keyword.arg for keyword in preimage_call.keywords)
    if observed != _ADR023_CURSOR_PREIMAGE_PARAMETERS:
        violations.append(f"cursor digest parameters differ: observed={observed!r}")
    for expected, keyword in zip(
        _ADR023_CURSOR_PREIMAGE_PARAMETERS,
        preimage_call.keywords,
        strict=False,
    ):
        expected_source = (
            _ADR023_LAST_PRIMARY_COMMITMENT_SOURCE
            if expected == "last_primary_commitment"
            else expected
        )
        expected_expression = ast.parse(
            expected_source,
            mode="eval",
            feature_version=(3, 11),
        ).body
        if not (
            keyword.arg == expected
            and ast.dump(keyword.value, include_attributes=False)
            == ast.dump(expected_expression, include_attributes=False)
        ):
            violations.append(
                f"cursor digest slot {expected} must use exact source {expected_source}"
            )

    cursor_names = set(_ADR023_STATE_CURSOR_PARAMETERS)
    for part in commit_call.args:
        if part is digest_part:
            continue
        leaked = sorted(
            {
                node.id
                for node in ast.walk(part)
                if isinstance(node, ast.Name) and node.id in cursor_names
            }
        )
        if leaked:
            violations.append(
                f"raw cursor components bypass exact digest part: {leaked!r}"
            )
    return violations


def test_state_commitment_binds_one_exact_cursor_digest_part() -> None:
    module = _protection_module()
    (state_commitment,) = _required(module, "_state_commitment")
    assert not _state_cursor_digest_binding_violations(
        inspect.getsource(state_commitment)
    )


def test_state_commitment_cursor_digest_runtime_dependencies_are_canonical() -> None:
    module = _protection_module()
    state_commitment, commit_parts, encode_reported_price, preimage = _required(
        module,
        "_state_commitment",
        "_commit_parts",
        "_encode_reported_price",
        "_protection_market_cursor_preimage",
    )
    fills_module = importlib.import_module("app.execution_core.fills")
    assert type(state_commitment) is FunctionType
    assert type(preimage) is FunctionType
    assert state_commitment.__globals__ is vars(module)
    assert preimage.__globals__ is vars(module)
    assert vars(module).get("_state_commitment") is state_commitment
    assert vars(module).get("_protection_market_cursor_preimage") is preimage
    assert vars(module).get("_commit_parts") is commit_parts
    assert vars(module).get("_encode_reported_price") is encode_reported_price
    assert commit_parts is vars(fills_module).get("_commit_parts")
    assert encode_reported_price is vars(fills_module).get("_encode_reported_price")
    assert state_commitment.__globals__.get("_commit_parts") is commit_parts
    assert (
        state_commitment.__globals__.get("_encode_reported_price")
        is encode_reported_price
    )
    assert (
        state_commitment.__globals__.get("_protection_market_cursor_preimage")
        is preimage
    )
    assert state_commitment.__globals__.get("_sha256") is sha256


def test_state_cursor_digest_binding_oracle_is_failure_capable() -> None:
    parameters = ", ".join(_ADR023_STATE_COMMITMENT_PARAMETERS)
    keyword_sources = {name: name for name in _ADR023_CURSOR_PREIMAGE_PARAMETERS}
    keyword_sources["last_primary_commitment"] = (
        f"({_ADR023_LAST_PRIMARY_COMMITMENT_SOURCE})"
    )

    def render_keywords(overrides: dict[str, str] | None = None) -> str:
        sources = dict(keyword_sources)
        if overrides is not None:
            sources.update(overrides)
        return ", ".join(
            f"{name}={sources[name]}" for name in _ADR023_CURSOR_PREIMAGE_PARAMETERS
        )

    keywords = render_keywords()
    digest_part_index = _ADR023_STATE_COMMITMENT_PART_SOURCES.index("<CURSOR_DIGEST>")
    canonical_leading_parts = _ADR023_STATE_COMMITMENT_PART_SOURCES[:digest_part_index]

    def source_with(
        cursor_part: str,
        extra_part: str = "",
        *,
        prelude: tuple[str, ...] = (),
        parameter_source: str = parameters,
        decorator: str = "",
        leading_parts: tuple[str, ...] = canonical_leading_parts,
        provenance_part: str = "exit_provenance",
    ) -> str:
        suffix = f", {extra_part}" if extra_part else ""
        preparation = "".join(f"    {statement}\n" for statement in prelude)
        prepared_parts = ",\n".join(f"        {source}" for source in leading_parts)
        prepared_provenance = f"        {provenance_part},\n" if provenance_part else ""
        return (
            f"{decorator}def _state_commitment({parameter_source}):\n"
            f"{preparation}"
            "    return _commit_parts(\n"
            "        b'execution-core/position-protection-state/v4',\n"
            f"{prepared_parts},\n"
            f"        {cursor_part}{suffix},\n"
            f"{prepared_provenance}"
            "    )\n"
        )

    exact_part = (
        "_sha256(_protection_market_cursor_preimage(" + keywords + ")).digest()"
    )
    assert _state_cursor_digest_binding_violations(source_with(exact_part)) == []
    swapped_keywords = render_keywords(
        {
            "stream_generation": "sequence_mode",
            "sequence_mode": "stream_generation",
        }
    )
    constant_keywords = render_keywords(
        {
            "occurrence_epoch": "0",
        }
    )
    transformed_keywords = render_keywords(
        {
            "source_time": "_encode_int(source_time)",
        }
    )
    transformed_retained_parts = list(canonical_leading_parts)
    transformed_retained_parts[2] = "_encode_int(raw_quantity + 0)"
    dead_expression_parts = list(canonical_leading_parts)
    dead_expression_parts[3] = "execution_commitment if True else execution_commitment"
    reordered_retained_parts = list(canonical_leading_parts)
    reordered_retained_parts[7], reordered_retained_parts[8] = (
        reordered_retained_parts[8],
        reordered_retained_parts[7],
    )
    mutants = {
        "omitted cursor": source_with("other"),
        "raw cursor": source_with(
            "_protection_market_cursor_preimage(" + keywords + ")"
        ),
        "missing cursor field": source_with(
            "_sha256(_protection_market_cursor_preimage("
            + ", ".join(
                f"{name}={keyword_sources[name]}"
                for name in _ADR023_CURSOR_PREIMAGE_PARAMETERS
                if name != "trade_identity"
            )
            + ")).digest()"
        ),
        "duplicated raw component": source_with(exact_part, "source_time"),
        "explicit cursor slot swap": source_with(
            "_sha256(_protection_market_cursor_preimage("
            + swapped_keywords
            + ")).digest()"
        ),
        "constant cursor slot substitution": source_with(
            "_sha256(_protection_market_cursor_preimage("
            + constant_keywords
            + ")).digest()"
        ),
        "transformed cursor slot": source_with(
            "_sha256(_protection_market_cursor_preimage("
            + transformed_keywords
            + ")).digest()"
        ),
        "raw last primary instead of commitment": source_with(
            "_sha256(_protection_market_cursor_preimage("
            + render_keywords({"last_primary_commitment": "last_primary"})
            + ")).digest()"
        ),
        "last primary commitment loses absence": source_with(
            "_sha256(_protection_market_cursor_preimage("
            + render_keywords(
                {"last_primary_commitment": ("_encode_reported_price(last_primary)")}
            )
            + ")).digest()"
        ),
        "raw component through local alias": source_with(
            exact_part,
            "duplicate",
            prelude=("duplicate = source_time",),
        ),
        "raw component through transitive aliases": source_with(
            exact_part,
            "second",
            prelude=("first = source_time", "second = first"),
        ),
        "extra parameter duplicate": source_with(
            exact_part,
            "source_time_duplicate",
            parameter_source=f"{parameters}, source_time_duplicate",
        ),
        "commit-packer callable shadow": source_with(
            exact_part,
            parameter_source=f"{parameters}, _commit_parts",
        ),
        "cursor-preimage callable shadow": source_with(
            exact_part,
            parameter_source=f"{parameters}, _protection_market_cursor_preimage",
        ),
        "sha256 callable shadow": source_with(
            exact_part,
            parameter_source=f"{parameters}, _sha256",
        ),
        "default parameter": source_with(
            exact_part,
            parameter_source=parameters.replace(
                "exit_provenance",
                "exit_provenance=b''",
            ),
        ),
        "positional-only parameters": source_with(
            exact_part,
            parameter_source=f"{parameters}, /",
        ),
        "variadic positional parameter": source_with(
            exact_part,
            parameter_source=f"{parameters}, *extra",
        ),
        "keyword-only parameter": source_with(
            exact_part,
            parameter_source=f"{parameters}, *, extra",
        ),
        "variadic keyword parameter": source_with(
            exact_part,
            parameter_source=f"{parameters}, **extra",
        ),
        "decorated commitment": source_with(
            exact_part,
            decorator="@staticmethod\n",
        ),
        "transformed retained source": source_with(
            exact_part,
            leading_parts=tuple(transformed_retained_parts),
        ),
        "dead retained expression": source_with(
            exact_part,
            leading_parts=tuple(dead_expression_parts),
        ),
        "omitted retained part": source_with(
            exact_part,
            leading_parts=(
                *canonical_leading_parts[:6],
                *canonical_leading_parts[7:],
            ),
        ),
        "reordered retained parts": source_with(
            exact_part,
            leading_parts=tuple(reordered_retained_parts),
        ),
        "duplicated retained part": source_with(
            exact_part,
            leading_parts=(
                *canonical_leading_parts[:3],
                canonical_leading_parts[2],
                *canonical_leading_parts[3:],
            ),
        ),
        "omitted exit provenance": source_with(
            exact_part,
            provenance_part="",
        ),
    }
    assert len(mutants) == 27
    expected_findings = {
        "explicit cursor slot swap": "cursor digest slot stream_generation",
        "constant cursor slot substitution": "cursor digest slot occurrence_epoch",
        "transformed cursor slot": "cursor digest slot source_time",
        "raw last primary instead of commitment": (
            "cursor digest slot last_primary_commitment"
        ),
        "last primary commitment loses absence": (
            "cursor digest slot last_primary_commitment"
        ),
        "raw component through local alias": "one straight-line return",
        "raw component through transitive aliases": "one straight-line return",
        "extra parameter duplicate": "signature differs",
        "commit-packer callable shadow": "signature differs",
        "cursor-preimage callable shadow": "signature differs",
        "sha256 callable shadow": "signature differs",
        "default parameter": "signature differs",
        "positional-only parameters": "signature differs",
        "variadic positional parameter": "signature differs",
        "keyword-only parameter": "signature differs",
        "variadic keyword parameter": "signature differs",
        "decorated commitment": "signature differs",
        "transformed retained source": "part 3 differs",
        "dead retained expression": "part 4 differs",
        "omitted retained part": "exactly 15 ordered commitment arguments",
        "reordered retained parts": "part 8 differs",
        "duplicated retained part": "exactly 15 ordered commitment arguments",
        "omitted exit provenance": "exactly 15 ordered commitment arguments",
    }
    for label, source in mutants.items():
        violations = _state_cursor_digest_binding_violations(source)
        assert violations, label
        if label in expected_findings:
            assert any(expected_findings[label] in item for item in violations), label


def test_main_state_commitment_authenticates_every_cursor_component() -> None:
    module = _protection_module()
    current = _owned_fill_transition(label="adr023-cursor-main-commitment")
    mandate, _, state = _start(module, current)
    (occurrence_id_type,) = _required(execution_core, "MarketOccurrenceId")
    retained = _rebuild_authentic_state(
        module,
        state,
        _market_occurrence_epoch=7,
        _market_committed_epoch=7,
        _market_expected_epoch=None,
        _market_source_sequence=9,
        _market_source_time=10,
        _market_evaluation_time=11,
        _market_occurrence_identity=occurrence_id_type("11" * 32),
        _market_halted=False,
        _market_baseline_required=False,
        _market_exhausted=False,
        _market_last_primary=_price(110),
        _hard_bid_identity=occurrence_id_type("33" * 32),
        _hard_bid_source_time=8,
        _trade_identity=occurrence_id_type("44" * 32),
        _trade_source_time=9,
        _trail_bid_identity=occurrence_id_type("55" * 32),
        _trail_bid_source_time=10,
    )
    (is_authentic,) = _required(module, "_state_is_authentic")
    assert is_authentic(retained) is True
    mutations = {
        "_market_occurrence_epoch": 8,
        "_market_committed_epoch": 8,
        "_market_expected_epoch": 8,
        "_market_source_sequence": 10,
        "_market_source_time": 11,
        "_market_evaluation_time": 12,
        "_market_occurrence_identity": occurrence_id_type("66" * 32),
        "_market_halted": True,
        "_market_baseline_required": True,
        "_market_exhausted": True,
        "_market_last_primary": _price(115),
        "_hard_bid_identity": occurrence_id_type("88" * 32),
        "_hard_bid_source_time": 7,
        "_trade_identity": occurrence_id_type("99" * 32),
        "_trade_source_time": 8,
        "_trail_bid_identity": occurrence_id_type("aa" * 32),
        "_trail_bid_source_time": 9,
    }
    assert set(mutations) == set(_ADR023_MARKET_CURSOR_FIELDS)
    for field_name, changed_value in mutations.items():
        forged = _clone_opaque(retained, **{field_name: changed_value})
        assert forged.commitment == retained.commitment
        assert is_authentic(forged) is False, field_name
    assert mandate.evidence_policy.stream_generation.value == "11" * 32


@pytest.mark.parametrize(
    ("identity_field", "time_field", "identity_present"),
    [
        pytest.param(
            identity_field,
            time_field,
            identity_present,
            id=f"{identity_field}-{'identity-only' if identity_present else 'coordinate-only'}",
        )
        for identity_field, time_field in (
            ("occurrence_identity", "occurrence_epoch"),
            ("hard_bid_identity", "hard_bid_source_time"),
            ("trade_identity", "trade_source_time"),
            ("trail_bid_identity", "trail_bid_source_time"),
        )
        for identity_present in (True, False)
    ],
)
def test_production_cursor_preimage_rejects_mismatched_optional_pairs(
    identity_field: str,
    time_field: str,
    identity_present: bool,
) -> None:
    module = _protection_module()
    (preimage,) = _required(module, "_protection_market_cursor_preimage")
    values = {
        "stream_generation": bytes.fromhex("11" * 32),
        "sequence_mode": 0,
        "occurrence_epoch": None,
        "committed_epoch": None,
        "expected_epoch": 0,
        "source_sequence": None,
        "source_time": None,
        "evaluation_time": None,
        "occurrence_identity": None,
        "halted": False,
        "baseline_required": True,
        "exhausted": False,
        "last_primary_commitment": None,
        "hard_bid_identity": None,
        "hard_bid_source_time": None,
        "trade_identity": None,
        "trade_source_time": None,
        "trail_bid_identity": None,
        "trail_bid_source_time": None,
    }
    if identity_present:
        values[identity_field] = bytes.fromhex("aa" * 32)
    else:
        values[time_field] = 1
    with pytest.raises(ValueError):
        preimage(**values)


def _assert_no_variable_cardinality_market_value(
    value: object,
    *,
    path: tuple[str, ...],
) -> None:
    forbidden_exact_types = {
        list,
        dict,
        set,
        frozenset,
        tuple,
        _PersistentKeyMap,
    }
    assert type(value) not in forbidden_exact_types, (
        f"variable-cardinality market value at {'.'.join(path)}: {type(value).__name__}"
    )
    if value is None or type(value) in {bool, bytes, int, str, Decimal, Fraction}:
        return
    if isinstance(value, Enum):
        return
    assert is_dataclass(value) and not isinstance(value, type), (
        f"unbounded or opaque market value at {'.'.join(path)}: {type(value).__name__}"
    )
    for retained in fields(value):
        _assert_no_variable_cardinality_market_value(
            getattr(value, retained.name),
            path=(*path, retained.name),
        )


def _production_cursor_preimage_from_state(
    module: ModuleType,
    state: object,
    mandate: object,
) -> bytes:
    (preimage,) = _required(module, "_protection_market_cursor_preimage")
    mode = mandate.evidence_policy.sequence_mode
    mode_byte = 0 if mode.value == "SEQUENCED" else 1
    return preimage(
        stream_generation=bytes.fromhex(
            mandate.evidence_policy.stream_generation.value
        ),
        sequence_mode=mode_byte,
        occurrence_epoch=state._market_occurrence_epoch,
        committed_epoch=state._market_committed_epoch,
        expected_epoch=state._market_expected_epoch,
        source_sequence=state._market_source_sequence,
        source_time=state._market_source_time,
        evaluation_time=state._market_evaluation_time,
        occurrence_identity=(
            None
            if state._market_occurrence_identity is None
            else bytes.fromhex(state._market_occurrence_identity.value)
        ),
        halted=state._market_halted,
        baseline_required=state._market_baseline_required,
        exhausted=state._market_exhausted,
        last_primary_commitment=(
            None
            if state._market_last_primary is None
            else _literal_encode_reported_price(state._market_last_primary)
        ),
        hard_bid_identity=(
            None
            if state._hard_bid_identity is None
            else bytes.fromhex(state._hard_bid_identity.value)
        ),
        hard_bid_source_time=state._hard_bid_source_time,
        trade_identity=(
            None
            if state._trade_identity is None
            else bytes.fromhex(state._trade_identity.value)
        ),
        trade_source_time=state._trade_source_time,
        trail_bid_identity=(
            None
            if state._trail_bid_identity is None
            else bytes.fromhex(state._trail_bid_identity.value)
        ),
        trail_bid_source_time=state._trail_bid_source_time,
    )


def _rebuild_authentic_state(
    module: ModuleType,
    state: object,
    **overrides: object,
) -> object:
    (rebuild,) = _required(module, "_rebuild_state")
    values: dict[str, object] = {}
    consumed: set[str] = set()
    for parameter_name in inspect.signature(rebuild).parameters:
        candidates = (parameter_name, f"_{parameter_name}")
        override_name = next(
            (name for name in candidates if name in overrides),
            None,
        )
        if override_name is not None:
            values[parameter_name] = overrides[override_name]
            consumed.add(override_name)
            continue
        retained_name = next(
            (name for name in candidates if hasattr(state, name)),
            None,
        )
        assert retained_name is not None, (
            f"cannot map authentic rebuild parameter {parameter_name!r}"
        )
        values[parameter_name] = getattr(state, retained_name)
    assert consumed == set(overrides), (
        f"unused authentic rebuild overrides: {sorted(set(overrides) - consumed)!r}"
    )
    return rebuild(**values)


def _exercise_near_boundary_market_history(module: ModuleType) -> tuple[object, object]:
    current = _owned_fill_transition(label="bounded-market-near-u64")
    mandate = _mandate(module, sequence_mode="SEQUENCED", max_age=_U64_MAX)
    mandate, projection, state = _start(module, current, mandate)
    starting_coordinate = _U64_MAX - 12
    anchor = _routed_occurrence(
        module,
        mandate,
        "bounded-market-near-u64-anchor",
        sequence=starting_coordinate,
        source_time=starting_coordinate,
        evaluation_time=starting_coordinate,
        market_epoch=0,
    )
    state = _rebuild_authentic_state(
        module,
        state,
        _market_occurrence_epoch=0,
        _market_committed_epoch=0,
        _market_expected_epoch=None,
        _market_source_sequence=starting_coordinate,
        _market_source_time=starting_coordinate,
        _market_evaluation_time=starting_coordinate,
        _market_occurrence_identity=anchor.occurrence_id,
        _market_halted=False,
        _market_baseline_required=False,
        _market_exhausted=False,
    )
    (disposition,) = _required(module, "ProtectionDisposition")
    for offset in range(1, 11):
        coordinate = starting_coordinate + offset
        occurrence = _routed_occurrence(
            module,
            mandate,
            f"bounded-market-near-u64-{offset}",
            sequence=coordinate,
            source_time=coordinate,
            evaluation_time=coordinate,
            market_epoch=0,
        )
        result = _reduce_market(module, state, projection, occurrence)
        assert result.disposition is disposition.APPLIED
        assert result.state._market_exhausted is False
        state = result.state
    assert state._market_source_sequence == _U64_MAX - 2
    return mandate, state


@dataclass(frozen=True, slots=True)
class _BoundedHistoryEvidence:
    mixed_step_count: int
    projection_advance_count: int
    late_projection_advance_step: int
    pending_bid_count_before: int
    pending_bid_count_after: int
    pending_trade_count_before: int
    pending_trade_count_after: int
    initial_armed_trigger: Fraction
    armed_trigger_after_bid_reset: Fraction
    armed_trigger_after_trade_reset: Fraction


def _exercise_bounded_market_history(
    module: ModuleType,
    *,
    count: int,
) -> tuple[object, object, _BoundedHistoryEvidence]:
    transition = _owned_fill_transition(
        label=f"bounded-market-{count}",
        quantity=4,
        units=100,
    )
    mandate = _mandate(module)
    mandate, projection, state = _start(module, transition, mandate)
    (reducer,) = _required(module, "reduce_position_protection_market")
    (disposition,) = _required(module, "ProtectionDisposition")
    epoch = 0
    sequence = 1
    last = _routed_occurrence(
        module,
        mandate,
        f"bounded-branch-before-economics-{count}",
        bid=92,
        ask=93,
        sequence=sequence,
        source_time=sequence,
        evaluation_time=sequence,
    )
    branched = reducer(state, projection, last)
    assert branched.disposition is disposition.APPLIED
    assert branched.goal is None
    pending_bid_count_before = sum(
        identity is not None
        for identity in (
            branched.state._hard_bid_identity,
            branched.state._trade_identity,
            branched.state._trail_bid_identity,
        )
    )
    assert pending_bid_count_before == 1
    assert branched.state._hard_bid_identity == last.occurrence_id
    assert branched.state._trade_identity is None
    assert branched.state._trail_bid_identity is None
    initial_armed_trigger = branched.state.armed_hard_bail_trigger.exact_value

    economics_transition = _advance_owned_fill(
        transition,
        label=f"bounded-economics-advance-{count}",
        quantity=1,
        units=120,
        prior_cumulative=4,
    )
    projection = _projection(module, economics_transition, mandate)
    economics = _reduce_projection(module, branched.state, projection)
    assert economics.disposition is disposition.APPLIED
    assert economics.state.execution_commitment == (
        economics_transition.execution.commitment
    )
    armed_trigger_after_bid_reset = economics.state.armed_hard_bail_trigger.exact_value
    assert armed_trigger_after_bid_reset > initial_armed_trigger
    pending_bid_count_after = sum(
        identity is not None
        for identity in (
            economics.state._hard_bid_identity,
            economics.state._trade_identity,
            economics.state._trail_bid_identity,
        )
    )
    assert pending_bid_count_after == 0
    state = economics.state
    late_projection_advance_step = count - 10
    pending_trade_count_before = -1
    pending_trade_count_after = -1
    armed_trigger_after_trade_reset = Fraction(-1)

    for index in range(count):
        if index == late_projection_advance_step:
            sequence += 1
            pending_trade = _routed_occurrence(
                module,
                mandate,
                f"bounded-trade-before-economics-{count}",
                bid=None,
                ask=None,
                sequence=sequence,
                source_time=sequence,
                evaluation_time=sequence,
                market_epoch=epoch,
                kind="TRADE",
                trade=97,
            )
            traded = reducer(state, projection, pending_trade)
            assert traded.disposition is disposition.APPLIED
            assert traded.goal is None
            pending_trade_count_before = sum(
                identity is not None
                for identity in (
                    traded.state._hard_bid_identity,
                    traded.state._trade_identity,
                    traded.state._trail_bid_identity,
                )
            )
            assert pending_trade_count_before == 1
            assert traded.state._hard_bid_identity is None
            assert traded.state._trade_identity == pending_trade.occurrence_id
            assert traded.state._trail_bid_identity is None
            assert (
                traded.state.armed_hard_bail_trigger.exact_value
                == armed_trigger_after_bid_reset
            )

            economics_transition = _advance_owned_fill(
                economics_transition,
                label=f"bounded-late-economics-advance-{count}",
                quantity=1,
                units=140,
                prior_cumulative=5,
            )
            projection = _projection(module, economics_transition, mandate)
            late_economics = _reduce_projection(
                module,
                traded.state,
                projection,
            )
            assert late_economics.disposition is disposition.APPLIED
            assert late_economics.state.execution_commitment == (
                economics_transition.execution.commitment
            )
            armed_trigger_after_trade_reset = (
                late_economics.state.armed_hard_bail_trigger.exact_value
            )
            assert armed_trigger_after_trade_reset > armed_trigger_after_bid_reset
            pending_trade_count_after = sum(
                identity is not None
                for identity in (
                    late_economics.state._hard_bid_identity,
                    late_economics.state._trade_identity,
                    late_economics.state._trail_bid_identity,
                )
            )
            assert pending_trade_count_after == 0
            state = late_economics.state
            last = pending_trade

        phase = index % 10
        if phase == 1:
            replay = reducer(state, projection, last)
            assert replay.disposition is disposition.EXACT_REPLAY
            assert replay.state == state
            continue
        if phase == 6:
            conflict = replace(last, best_ask=_price(102))
            latched = reducer(state, projection, conflict)
            assert latched.disposition is disposition.APPLIED
            state = latched.state
            continue
        if phase == 8:
            invalidated = _invalidate_market(module, state, projection)
            assert invalidated.disposition is disposition.APPLIED
            state = invalidated.state
            continue

        if phase in {5, 7, 9}:
            epoch += 1
        sequence += 1
        halted = phase == 4
        crossed = phase == 2
        occurrence = _occurrence(
            module,
            f"bounded-{index}",
            bid=102 if crossed else 100,
            ask=101,
            sequence=sequence,
            source_time=sequence,
            evaluation_time=sequence,
            market_epoch=epoch,
            halted=halted,
            source_id=mandate.evidence_policy.source_id,
            stream_generation=mandate.evidence_policy.stream_generation,
            position_scope=mandate.position_scope,
            session_id=mandate.session_id,
        )
        applied = reducer(state, projection, occurrence)
        assert applied.disposition is disposition.APPLIED
        state = applied.state
        last = occurrence
    assert pending_trade_count_before == 1
    assert pending_trade_count_after == 0
    assert armed_trigger_after_trade_reset > armed_trigger_after_bid_reset
    return (
        mandate,
        state,
        _BoundedHistoryEvidence(
            mixed_step_count=count,
            projection_advance_count=2,
            late_projection_advance_step=late_projection_advance_step,
            pending_bid_count_before=pending_bid_count_before,
            pending_bid_count_after=pending_bid_count_after,
            pending_trade_count_before=pending_trade_count_before,
            pending_trade_count_after=pending_trade_count_after,
            initial_armed_trigger=initial_armed_trigger,
            armed_trigger_after_bid_reset=armed_trigger_after_bid_reset,
            armed_trigger_after_trade_reset=armed_trigger_after_trade_reset,
        ),
    )


def test_market_state_and_work_are_constant_after_ten_and_one_hundred_thousand() -> (
    None
):
    module = _protection_module()
    small_mandate, small, small_evidence = _exercise_bounded_market_history(
        module,
        count=10,
    )
    large_mandate, large, large_evidence = _exercise_bounded_market_history(
        module,
        count=100_000,
    )
    boundary_mandate, boundary = _exercise_near_boundary_market_history(module)
    assert small_evidence == _BoundedHistoryEvidence(
        mixed_step_count=10,
        projection_advance_count=2,
        late_projection_advance_step=0,
        pending_bid_count_before=1,
        pending_bid_count_after=0,
        pending_trade_count_before=1,
        pending_trade_count_after=0,
        initial_armed_trigger=Fraction(93),
        armed_trigger_after_bid_reset=Fraction(97),
        armed_trigger_after_trade_reset=Fraction(102),
    )
    assert large_evidence == _BoundedHistoryEvidence(
        mixed_step_count=100_000,
        projection_advance_count=2,
        late_projection_advance_step=99_990,
        pending_bid_count_before=1,
        pending_bid_count_after=0,
        pending_trade_count_before=1,
        pending_trade_count_after=0,
        initial_armed_trigger=Fraction(93),
        armed_trigger_after_bid_reset=Fraction(97),
        armed_trigger_after_trade_reset=Fraction(102),
    )
    for state in (small, large, boundary):
        state_fields = tuple(retained.name for retained in fields(state))
        assert state_fields == _ADR023_STATE_FIELDS
        for field_name in state_fields:
            _assert_no_variable_cardinality_market_value(
                getattr(state, field_name),
                path=(field_name,),
            )
        assert state._market_occurrence_identity is not None
        evidence_identity_count = sum(
            identity is not None
            for identity in (
                state._hard_bid_identity,
                state._trade_identity,
                state._trail_bid_identity,
            )
        )
        assert evidence_identity_count <= 3

    small_preimage = _production_cursor_preimage_from_state(
        module,
        small,
        small_mandate,
    )
    large_preimage = _production_cursor_preimage_from_state(
        module,
        large,
        large_mandate,
    )
    boundary_preimage = _production_cursor_preimage_from_state(
        module,
        boundary,
        boundary_mandate,
    )
    assert len(small_preimage) == len(large_preimage) == len(boundary_preimage) == 480
    assert tuple(retained.name for retained in fields(small)) == tuple(
        retained.name for retained in fields(large)
    )


@dataclass(frozen=True, slots=True)
class _ClassifierCase:
    name: str
    lifecycle: str
    sequence_mode: str = "SEQUENCED"
    projection: str = "current"
    route: str = "exact"
    epoch: str = "admitted"
    coordinate: str = "greater"
    identity: str = "different"
    context: str = "eligible"


@dataclass(frozen=True, slots=True)
class _ClassifierExpectation:
    disposition: str
    alert: str | None
    cursor_delta: bool
    baseline_required: bool
    exhausted: bool
    evidence_cleared: bool
    goal_suppressed: bool


def _expect(
    disposition: str,
    *,
    alert: str | None = None,
    cursor_delta: bool = False,
    baseline_required: bool = False,
    exhausted: bool = False,
    evidence_cleared: bool = False,
    goal_suppressed: bool = True,
) -> _ClassifierExpectation:
    return _ClassifierExpectation(
        disposition=disposition,
        alert=alert,
        cursor_delta=cursor_delta,
        baseline_required=baseline_required,
        exhausted=exhausted,
        evidence_cleared=evidence_cleared,
        goal_suppressed=goal_suppressed,
    )


def _classify_adr023_case(
    case: _ClassifierCase,
    *,
    exact_current_before_epoch: bool = True,
    exhaust_secondary_watermarks: bool = False,
    route_before_cursor: bool = True,
    reserve_before_context: bool = True,
    conflict_latches_baseline: bool = True,
    valid_baseline_clears_latch: bool = True,
    exhaustion_before_admission: bool = False,
    source_time_exhaustion_before_admission: bool = False,
    source_time_evaluation_max_exhausts: bool = False,
) -> _ClassifierExpectation:
    initially_restrictive = case.lifecycle in {"baseline", "exhausted"}
    premature_exhaustion = exhaustion_before_admission or (
        source_time_exhaustion_before_admission and case.sequence_mode == "SOURCE_TIME"
    )
    if premature_exhaustion and (
        case.coordinate == "strict-max" or case.epoch == "commit-max"
    ):
        return _expect(
            "APPLIED",
            alert="MARKET_COORDINATE_EXHAUSTED",
            cursor_delta=True,
            baseline_required=True,
            exhausted=True,
            evidence_cleared=True,
        )
    if route_before_cursor and (case.projection != "current" or case.route != "exact"):
        return _expect(
            "REFUSED",
            baseline_required=initially_restrictive,
            exhausted=case.lifecycle == "exhausted",
            evidence_cleared=initially_restrictive,
        )
    exact_current = (
        case.epoch == "retained"
        and case.coordinate == "equal"
        and case.identity == "identical"
    )
    conflict = (
        case.epoch == "retained"
        and case.coordinate == "equal"
        and case.identity == "different"
    )
    if exact_current_before_epoch and exact_current:
        return _expect(
            "EXACT_REPLAY",
            baseline_required=initially_restrictive,
            exhausted=case.lifecycle == "exhausted",
            evidence_cleared=initially_restrictive,
        )
    if exact_current_before_epoch and conflict:
        if case.lifecycle == "serving":
            return _expect(
                "APPLIED" if conflict_latches_baseline else "STALE",
                alert=(
                    "MARKET_BASELINE_REQUIRED" if conflict_latches_baseline else None
                ),
                baseline_required=conflict_latches_baseline,
                evidence_cleared=conflict_latches_baseline,
            )
        return _expect(
            "REFUSED",
            baseline_required=True,
            exhausted=case.lifecycle == "exhausted",
            evidence_cleared=True,
        )
    if case.lifecycle == "exhausted":
        if case.epoch == "old" or case.coordinate == "lower":
            return _expect(
                "STALE",
                baseline_required=True,
                exhausted=True,
                evidence_cleared=True,
            )
        return _expect(
            "REFUSED",
            baseline_required=True,
            exhausted=True,
            evidence_cleared=True,
        )
    if case.epoch == "old":
        return _expect(
            "STALE",
            baseline_required=initially_restrictive,
            evidence_cleared=initially_restrictive,
        )
    if case.epoch == "future":
        return _expect(
            "REFUSED",
            baseline_required=initially_restrictive,
            evidence_cleared=initially_restrictive,
        )
    if case.coordinate in {"lower", "equal"}:
        return _expect(
            "STALE",
            baseline_required=initially_restrictive,
            evidence_cleared=initially_restrictive,
        )
    if case.coordinate == "secondary-max" and (
        exhaust_secondary_watermarks
        or (source_time_evaluation_max_exhausts and case.sequence_mode == "SOURCE_TIME")
    ):
        return _expect(
            "APPLIED",
            alert="MARKET_COORDINATE_EXHAUSTED",
            cursor_delta=True,
            baseline_required=True,
            exhausted=True,
            evidence_cleared=True,
        )
    if case.coordinate == "strict-max" or case.epoch == "commit-max":
        return _expect(
            "APPLIED",
            alert="MARKET_COORDINATE_EXHAUSTED",
            cursor_delta=True,
            baseline_required=True,
            exhausted=True,
            evidence_cleared=True,
        )
    contextually_ineligible = case.context != "eligible"
    cursor_delta = not contextually_ineligible or reserve_before_context
    if not route_before_cursor and (
        case.projection != "current" or case.route != "exact"
    ):
        return _expect(
            "REFUSED",
            cursor_delta=cursor_delta,
            baseline_required=initially_restrictive,
            evidence_cleared=initially_restrictive,
        )
    if case.context == "halted":
        return _expect(
            "APPLIED",
            alert=("MARKET_BASELINE_REQUIRED" if case.lifecycle == "serving" else None),
            cursor_delta=cursor_delta,
            baseline_required=True,
            evidence_cleared=True,
        )
    if case.lifecycle == "baseline":
        remains_latched = contextually_ineligible or not valid_baseline_clears_latch
        return _expect(
            "APPLIED",
            cursor_delta=cursor_delta,
            baseline_required=remains_latched,
            evidence_cleared=True,
        )
    return _expect(
        "APPLIED",
        cursor_delta=cursor_delta,
        evidence_cleared=contextually_ineligible,
        goal_suppressed=contextually_ineligible,
    )


_CLASSIFIER_ROWS = (
    (
        _ClassifierCase("stale-projection", "serving", projection="stale"),
        _expect("REFUSED"),
    ),
    (
        _ClassifierCase("forked-projection", "serving", projection="forked"),
        _expect("REFUSED"),
    ),
    (
        _ClassifierCase("advancing-projection", "serving", projection="advancing"),
        _expect("REFUSED"),
    ),
    (_ClassifierCase("wrong-source", "serving", route="source"), _expect("REFUSED")),
    (
        _ClassifierCase("wrong-generation", "serving", route="generation"),
        _expect("REFUSED"),
    ),
    (_ClassifierCase("wrong-mode", "serving", route="mode"), _expect("REFUSED")),
    (_ClassifierCase("wrong-scope", "serving", route="scope"), _expect("REFUSED")),
    (_ClassifierCase("wrong-session", "serving", route="session"), _expect("REFUSED")),
    (
        _ClassifierCase(
            "serving-replay",
            "serving",
            epoch="retained",
            coordinate="equal",
            identity="identical",
        ),
        _expect("EXACT_REPLAY"),
    ),
    (
        _ClassifierCase(
            "serving-conflict", "serving", epoch="retained", coordinate="equal"
        ),
        _expect(
            "APPLIED",
            alert="MARKET_BASELINE_REQUIRED",
            baseline_required=True,
            evidence_cleared=True,
        ),
    ),
    (_ClassifierCase("serving-old-epoch", "serving", epoch="old"), _expect("STALE")),
    (
        _ClassifierCase("serving-future-epoch", "serving", epoch="future"),
        _expect("REFUSED"),
    ),
    (_ClassifierCase("serving-lower", "serving", coordinate="lower"), _expect("STALE")),
    (
        _ClassifierCase("serving-advance", "serving"),
        _expect("APPLIED", cursor_delta=True, goal_suppressed=False),
    ),
    (
        _ClassifierCase("expired-reserves", "serving", context="expired"),
        _expect("APPLIED", cursor_delta=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase("crossed-reserves", "serving", context="crossed"),
        _expect("APPLIED", cursor_delta=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase("step-invalid-reserves", "serving", context="step"),
        _expect("APPLIED", cursor_delta=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase("formula-loss-reserves", "serving", context="formula"),
        _expect("APPLIED", cursor_delta=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase("flat-reserves", "serving", context="flat"),
        _expect("APPLIED", cursor_delta=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase("serving-halt", "serving", context="halted"),
        _expect(
            "APPLIED",
            alert="MARKET_BASELINE_REQUIRED",
            cursor_delta=True,
            baseline_required=True,
            evidence_cleared=True,
        ),
    ),
    (
        _ClassifierCase(
            "baseline-retained-replay",
            "baseline",
            epoch="retained",
            coordinate="equal",
            identity="identical",
        ),
        _expect("EXACT_REPLAY", baseline_required=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase(
            "baseline-retained-conflict",
            "baseline",
            epoch="retained",
            coordinate="equal",
        ),
        _expect("REFUSED", baseline_required=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase("baseline-old", "baseline", epoch="old"),
        _expect("STALE", baseline_required=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase("baseline-future", "baseline", epoch="future"),
        _expect("REFUSED", baseline_required=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase("baseline-lower", "baseline", coordinate="lower"),
        _expect("STALE", baseline_required=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase("baseline-equal", "baseline", coordinate="equal"),
        _expect("STALE", baseline_required=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase("baseline-invalid-consumes", "baseline", context="expired"),
        _expect(
            "APPLIED", cursor_delta=True, baseline_required=True, evidence_cleared=True
        ),
    ),
    (
        _ClassifierCase("baseline-halted-consumes", "baseline", context="halted"),
        _expect(
            "APPLIED", cursor_delta=True, baseline_required=True, evidence_cleared=True
        ),
    ),
    (
        _ClassifierCase("baseline-recovers", "baseline"),
        _expect("APPLIED", cursor_delta=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase("strict-coordinate-max", "serving", coordinate="strict-max"),
        _expect(
            "APPLIED",
            alert="MARKET_COORDINATE_EXHAUSTED",
            cursor_delta=True,
            baseline_required=True,
            exhausted=True,
            evidence_cleared=True,
        ),
    ),
    (
        _ClassifierCase("commit-epoch-max", "baseline", epoch="commit-max"),
        _expect(
            "APPLIED",
            alert="MARKET_COORDINATE_EXHAUSTED",
            cursor_delta=True,
            baseline_required=True,
            exhausted=True,
            evidence_cleared=True,
        ),
    ),
    (
        _ClassifierCase(
            "evaluation-max-not-terminal", "serving", coordinate="secondary-max"
        ),
        _expect("APPLIED", cursor_delta=True, goal_suppressed=False),
    ),
    (
        _ClassifierCase(
            "source-time-evaluation-max-not-terminal",
            "serving",
            sequence_mode="SOURCE_TIME",
            coordinate="secondary-max",
        ),
        _expect("APPLIED", cursor_delta=True, goal_suppressed=False),
    ),
    (
        _ClassifierCase(
            "exhausted-replay",
            "exhausted",
            epoch="retained",
            coordinate="equal",
            identity="identical",
        ),
        _expect(
            "EXACT_REPLAY",
            baseline_required=True,
            exhausted=True,
            evidence_cleared=True,
        ),
    ),
    (
        _ClassifierCase(
            "exhausted-conflict", "exhausted", epoch="retained", coordinate="equal"
        ),
        _expect(
            "REFUSED", baseline_required=True, exhausted=True, evidence_cleared=True
        ),
    ),
    (
        _ClassifierCase("exhausted-old", "exhausted", epoch="old"),
        _expect("STALE", baseline_required=True, exhausted=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase("exhausted-lower", "exhausted", coordinate="lower"),
        _expect("STALE", baseline_required=True, exhausted=True, evidence_cleared=True),
    ),
    (
        _ClassifierCase("exhausted-greater", "exhausted"),
        _expect(
            "REFUSED", baseline_required=True, exhausted=True, evidence_cleared=True
        ),
    ),
    (
        _ClassifierCase("exhausted-future", "exhausted", epoch="future"),
        _expect(
            "REFUSED", baseline_required=True, exhausted=True, evidence_cleared=True
        ),
    ),
)

_STATE_PRESERVING_CLASSIFIER_EXPECTATIONS = {
    ("serving", "STALE"): _expect("STALE"),
    ("serving", "REFUSED"): _expect("REFUSED"),
    ("baseline", "STALE"): _expect(
        "STALE", baseline_required=True, evidence_cleared=True
    ),
    ("baseline", "REFUSED"): _expect(
        "REFUSED", baseline_required=True, evidence_cleared=True
    ),
    ("exhausted", "STALE"): _expect(
        "STALE",
        baseline_required=True,
        exhausted=True,
        evidence_cleared=True,
    ),
    ("exhausted", "REFUSED"): _expect(
        "REFUSED",
        baseline_required=True,
        exhausted=True,
        evidence_cleared=True,
    ),
}
_CROSSED_CLASSIFIER_ROWS = (
    *(
        (
            _ClassifierCase(
                (
                    f"{lifecycle}-{mismatch}-{coordinate}"
                    if sequence_mode == "SEQUENCED"
                    else f"source-time-{lifecycle}-{mismatch}-{coordinate}"
                ),
                lifecycle,
                sequence_mode=sequence_mode,
                projection="stale" if mismatch == "wrong-projection" else "current",
                route="source" if mismatch == "wrong-route" else "exact",
                epoch="retained" if coordinate == "equal" else "admitted",
                coordinate=coordinate,
                identity="identical" if coordinate == "equal" else "different",
            ),
            _STATE_PRESERVING_CLASSIFIER_EXPECTATIONS[(lifecycle, "REFUSED")],
        )
        for lifecycle in ("serving", "baseline", "exhausted")
        for mismatch in ("wrong-route", "wrong-projection")
        for coordinate in ("equal", "strict-max")
        for sequence_mode in ("SEQUENCED", "SOURCE_TIME")
    ),
    *(
        (
            _ClassifierCase(
                (
                    f"{lifecycle}-{epoch}-{coordinate}"
                    if sequence_mode == "SEQUENCED"
                    else f"source-time-{lifecycle}-{epoch}-{coordinate}"
                ),
                lifecycle,
                sequence_mode=sequence_mode,
                epoch=epoch,
                coordinate=coordinate,
                identity="identical" if coordinate == "equal" else "different",
            ),
            _STATE_PRESERVING_CLASSIFIER_EXPECTATIONS[
                (lifecycle, "STALE" if epoch == "old" else "REFUSED")
            ],
        )
        for lifecycle in ("serving", "baseline", "exhausted")
        for epoch in ("old", "future")
        for coordinate in ("equal", "strict-max")
        for sequence_mode in ("SEQUENCED", "SOURCE_TIME")
    ),
)


_ALL_CLASSIFIER_ROWS = (*_CLASSIFIER_ROWS, *_CROSSED_CLASSIFIER_ROWS)


def test_classifier_reference_oracle_is_failure_capable() -> None:
    for case, expected in _ALL_CLASSIFIER_ROWS:
        assert _classify_adr023_case(case) == expected, case.name

    mutations = {
        "exact-current-after-epoch": (
            {"exact_current_before_epoch": False},
            {
                "baseline-retained-replay",
                "baseline-retained-conflict",
            },
        ),
        "secondary-watermark-exhaustion": (
            {"exhaust_secondary_watermarks": True},
            {"evaluation-max-not-terminal"},
        ),
        "route-after-cursor": (
            {"route_before_cursor": False},
            {"wrong-source", "wrong-generation", "wrong-mode"},
        ),
        "context-before-cursor": (
            {"reserve_before_context": False},
            {"expired-reserves", "crossed-reserves", "step-invalid-reserves"},
        ),
        "conflict-does-not-latch": (
            {"conflict_latches_baseline": False},
            {"serving-conflict"},
        ),
        "baseline-does-not-clear": (
            {"valid_baseline_clears_latch": False},
            {"baseline-recovers"},
        ),
        "exhaustion-before-admission": (
            {"exhaustion_before_admission": True},
            {
                "serving-old-strict-max",
                "serving-future-strict-max",
                "baseline-old-strict-max",
                "baseline-future-strict-max",
                "exhausted-old-strict-max",
                "exhausted-future-strict-max",
                "serving-wrong-route-strict-max",
                "baseline-wrong-projection-strict-max",
            },
        ),
    }
    for label, (mutation, required_kills) in mutations.items():
        mismatches = {
            case.name
            for case, expected in _ALL_CLASSIFIER_ROWS
            if _classify_adr023_case(case, **mutation) != expected
        }
        assert required_kills <= mismatches, (
            label,
            sorted(required_kills - mismatches),
        )

    source_time_admission_kills = {
        *(
            f"source-time-{lifecycle}-{mismatch}-strict-max"
            for lifecycle in ("serving", "baseline", "exhausted")
            for mismatch in ("wrong-route", "wrong-projection")
        ),
        *(
            f"source-time-{lifecycle}-{epoch}-strict-max"
            for lifecycle in ("serving", "baseline", "exhausted")
            for epoch in ("old", "future")
        ),
    }
    observed_admission_kills = {
        case.name
        for case, expected in _ALL_CLASSIFIER_ROWS
        if _classify_adr023_case(
            case,
            source_time_exhaustion_before_admission=True,
        )
        != expected
    }
    assert observed_admission_kills == source_time_admission_kills

    observed_evaluation_kills = {
        case.name
        for case, expected in _ALL_CLASSIFIER_ROWS
        if _classify_adr023_case(
            case,
            source_time_evaluation_max_exhausts=True,
        )
        != expected
    }
    assert observed_evaluation_kills == {"source-time-evaluation-max-not-terminal"}


@pytest.mark.parametrize("lifecycle", ["serving", "baseline", "exhausted"])
@pytest.mark.parametrize("boundary", ["equal", "strict-max"])
@pytest.mark.parametrize("sequence_mode", ["SEQUENCED", "SOURCE_TIME"])
@pytest.mark.parametrize(
    ("admission_case", "expected_disposition"),
    [
        pytest.param("wrong-route", "REFUSED", id="route-before-coordinate"),
        pytest.param(
            "wrong-projection",
            "REFUSED",
            id="projection-before-coordinate",
        ),
        pytest.param("old-epoch", "STALE", id="old-epoch-before-coordinate"),
        pytest.param("future-epoch", "REFUSED", id="future-epoch-before-coordinate"),
    ],
)
def test_production_admission_precedes_equal_or_maximum_coordinate(
    lifecycle: str,
    boundary: str,
    sequence_mode: str,
    admission_case: str,
    expected_disposition: str,
) -> None:
    module = _protection_module()
    current = _owned_fill_transition(
        label=(
            f"adr023-crossed-{sequence_mode}-{lifecycle}-{boundary}-{admission_case}"
        )
    )
    mandate = _mandate(module, sequence_mode=sequence_mode, max_age=_U64_MAX)
    mandate, projection, initial = _start(module, current, mandate)
    state = _authentic_serving_state_at_epoch(
        module,
        initial,
        mandate,
        epoch=1,
        coordinate=1,
    )
    if lifecycle == "baseline":
        state = _rebuild_authentic_state(
            module,
            state,
            _market_expected_epoch=2,
            _market_baseline_required=True,
            _market_exhausted=False,
            _hard_bid_identity=None,
            _hard_bid_source_time=None,
            _trade_identity=None,
            _trade_source_time=None,
            _trail_bid_identity=None,
            _trail_bid_source_time=None,
        )
    elif lifecycle == "exhausted":
        state = _rebuild_authentic_state(
            module,
            state,
            _market_expected_epoch=None,
            _market_baseline_required=True,
            _market_exhausted=True,
            _hard_bid_identity=None,
            _hard_bid_source_time=None,
            _trade_identity=None,
            _trade_source_time=None,
            _trail_bid_identity=None,
            _trail_bid_source_time=None,
        )

    coordinate = 1 if boundary == "equal" else _U64_MAX
    admitted_epoch = 2 if lifecycle == "baseline" else 1
    if admission_case == "old-epoch":
        epoch = 0
    elif admission_case == "future-epoch":
        epoch = admitted_epoch + 1
    else:
        epoch = admitted_epoch
    sequenced = sequence_mode == "SEQUENCED"
    source_time = 2 if sequenced else coordinate
    evaluation_time = 2 if sequenced or coordinate != _U64_MAX else _U64_MAX
    occurrence = _routed_occurrence(
        module,
        mandate,
        (
            f"adr023-crossed-input-{sequence_mode}-{lifecycle}-{boundary}-"
            f"{admission_case}"
        ),
        sequence=coordinate if sequenced else None,
        source_time=source_time,
        evaluation_time=evaluation_time,
        market_epoch=epoch,
        source_id=(
            execution_core.MarketDataSourceId("sip-secondary")
            if admission_case == "wrong-route"
            else mandate.evidence_policy.source_id
        ),
    )
    candidate_projection = projection
    if admission_case == "wrong-projection":
        additional = _advance_owned_fill(
            current,
            label=(f"adr023-crossed-projection-{sequence_mode}-{lifecycle}-{boundary}"),
            quantity=1,
            units=120,
            prior_cumulative=4,
        )
        candidate_projection = _projection(module, additional, mandate)

    before = state
    result = _reduce_market(
        module,
        state,
        candidate_projection,
        occurrence,
    )
    (disposition,) = _required(module, "ProtectionDisposition")
    assert result.disposition is getattr(disposition, expected_disposition)
    assert result.state == before
    assert result.goal is None
    assert result.critical_alert is None


def _invalidation_projection_fixture(
    module: ModuleType,
    *,
    lifecycle: str,
    projection_case: str,
) -> tuple[object, object, object]:
    current = _owned_fill_transition(
        label=f"adr023-invalidation-projection-{lifecycle}-{projection_case}"
    )
    mandate, initial_projection, state = _start(module, current)
    current_projection = initial_projection
    candidate_projection = initial_projection

    if projection_case in {"stale", "forked", "advancing"}:
        branch_a = _advance_owned_fill(
            current,
            label=f"adr023-invalidation-{lifecycle}-{projection_case}-branch-a",
            quantity=1,
            units=120,
            prior_cumulative=4,
        )
        branch_a_projection = _projection(module, branch_a, mandate)
        if projection_case == "advancing":
            candidate_projection = branch_a_projection
        else:
            advanced = _reduce_projection(module, state, branch_a_projection)
            (disposition,) = _required(module, "ProtectionDisposition")
            assert advanced.disposition is disposition.APPLIED
            state = advanced.state
            current_projection = branch_a_projection
            if projection_case == "stale":
                candidate_projection = initial_projection
            else:
                branch_b = _advance_owned_fill(
                    current,
                    label=(
                        f"adr023-invalidation-{lifecycle}-{projection_case}-branch-b"
                    ),
                    quantity=1,
                    units=121,
                    prior_cumulative=4,
                )
                candidate_projection = _projection(module, branch_b, mandate)
                assert (
                    candidate_projection.predecessor_cursor_ordinal
                    == branch_a_projection.predecessor_cursor_ordinal
                )
                assert (
                    candidate_projection.predecessor_cursor_head
                    == branch_a_projection.predecessor_cursor_head
                )
                assert (
                    candidate_projection.cursor_head != branch_a_projection.cursor_head
                )

    if lifecycle == "baseline-required":
        baseline_required = _invalidate_market(module, state, current_projection)
        disposition, alert = _required(
            module,
            "ProtectionDisposition",
            "ProtectionAlert",
        )
        assert baseline_required.disposition is disposition.APPLIED
        assert baseline_required.critical_alert is alert.MARKET_BASELINE_REQUIRED
        state = baseline_required.state
    elif lifecycle == "exhausted":
        exhausted = _reduce_market(
            module,
            state,
            current_projection,
            _routed_occurrence(
                module,
                mandate,
                f"adr023-invalidation-{projection_case}-exhaustion",
                sequence=_U64_MAX,
                source_time=1,
                evaluation_time=1,
                market_epoch=0,
            ),
        )
        disposition, alert = _required(
            module,
            "ProtectionDisposition",
            "ProtectionAlert",
        )
        assert exhausted.disposition is disposition.APPLIED
        assert exhausted.critical_alert is alert.MARKET_COORDINATE_EXHAUSTED
        assert exhausted.state._market_exhausted is True
        state = exhausted.state
    else:
        assert lifecycle == "serving"

    return state, current_projection, candidate_projection


@pytest.mark.parametrize(
    "lifecycle",
    ["serving", "baseline-required", "exhausted"],
)
@pytest.mark.parametrize(
    "projection_case",
    ["current", "stale", "forked", "advancing"],
)
def test_invalidation_projection_authority_matrix(
    lifecycle: str,
    projection_case: str,
) -> None:
    module = _protection_module()
    state, current_projection, candidate_projection = _invalidation_projection_fixture(
        module,
        lifecycle=lifecycle,
        projection_case=projection_case,
    )
    before_cursor = tuple(
        getattr(state, field_name)
        for field_name in sorted(_ADR023_MARKET_CURSOR_FIELDS)
    )
    result = _invalidate_market(module, state, candidate_projection)
    disposition, alert = _required(
        module,
        "ProtectionDisposition",
        "ProtectionAlert",
    )

    if projection_case != "current":
        assert candidate_projection != current_projection
        assert result.disposition is disposition.REFUSED
        assert result.state == state
        assert (
            tuple(
                getattr(result.state, field_name)
                for field_name in sorted(_ADR023_MARKET_CURSOR_FIELDS)
            )
            == before_cursor
        )
        assert result.goal is None
        assert result.critical_alert is None
        return

    assert candidate_projection == current_projection
    assert result.goal is None
    if lifecycle == "serving":
        assert result.disposition is disposition.APPLIED
        assert result.critical_alert is alert.MARKET_BASELINE_REQUIRED
        assert result.state._market_baseline_required is True
        assert result.state._market_exhausted is False
    else:
        assert result.disposition is disposition.EXACT_REPLAY
        assert result.state == state
        assert result.critical_alert is None


def test_initial_baseline_and_prebaseline_invalidation_are_exact() -> None:
    module = _protection_module()
    current = _owned_fill_transition(label="adr023-initial-baseline")
    mandate = _mandate(module)
    mandate, projection, state = _start(
        module,
        current,
        mandate,
        establish_baseline=False,
    )
    assert state._market_occurrence_epoch is None
    assert state._market_committed_epoch is None
    assert state._market_expected_epoch == 0
    assert state._market_source_sequence is None
    assert state._market_source_time is None
    assert state._market_evaluation_time is None
    assert state._market_occurrence_identity is None
    assert state._market_baseline_required is True
    assert state._market_halted is False
    assert state._market_exhausted is False

    unchanged = _invalidate_market(module, state, projection)
    (disposition,) = _required(module, "ProtectionDisposition")
    assert unchanged.disposition is disposition.EXACT_REPLAY
    assert unchanged.state == state
    assert unchanged.goal is None
    assert unchanged.critical_alert is None

    baseline = _routed_occurrence(
        module,
        mandate,
        "adr023-initial-baseline",
        sequence=7,
        source_time=8,
        evaluation_time=9,
        market_epoch=0,
    )
    applied = _reduce_market(module, state, projection, baseline)
    assert applied.disposition is disposition.APPLIED
    assert applied.state._market_committed_epoch == 0
    assert applied.state._market_expected_epoch is None
    assert applied.state._market_baseline_required is False
    assert applied.state._market_halted is False
    assert applied.state._market_occurrence_identity == baseline.occurrence_id
    assert applied.state._hard_bid_identity is None
    assert applied.state._trade_identity is None
    assert applied.state._trail_bid_identity is None
    assert applied.goal is None
    assert applied.critical_alert is None


def test_invalidation_recovery_is_exact_next_epoch_and_cursor_strict() -> None:
    module = _protection_module()
    current = _owned_fill_transition(label="adr023-invalidation")
    mandate, projection, serving = _start(module, current)
    (disposition, alert) = _required(
        module,
        "ProtectionDisposition",
        "ProtectionAlert",
    )
    retained = (
        serving._market_occurrence_epoch,
        serving._market_committed_epoch,
        serving._market_source_sequence,
        serving._market_source_time,
        serving._market_evaluation_time,
        serving._market_occurrence_identity,
        serving.raw_quantity,
        serving.armed_hard_bail_trigger,
        serving.activation_price,
        serving.high_watermark,
        serving.trail,
        serving._exit_provenance,
    )
    invalidated = _invalidate_market(module, serving, projection)
    assert invalidated.disposition is disposition.APPLIED
    assert invalidated.critical_alert is alert.MARKET_BASELINE_REQUIRED
    assert invalidated.goal is None
    state = invalidated.state
    assert state._market_baseline_required is True
    assert state._market_expected_epoch == 1
    assert (
        state._market_occurrence_epoch,
        state._market_committed_epoch,
        state._market_source_sequence,
        state._market_source_time,
        state._market_evaluation_time,
        state._market_occurrence_identity,
        state.raw_quantity,
        state.armed_hard_bail_trigger,
        state.activation_price,
        state.high_watermark,
        state.trail,
        state._exit_provenance,
    ) == retained

    replay = _invalidate_market(module, state, projection)
    assert replay.disposition is disposition.EXACT_REPLAY
    assert replay.state == state
    assert replay.critical_alert is None

    old_epoch = _routed_occurrence(
        module,
        mandate,
        "adr023-recovery-old",
        sequence=1,
        source_time=1,
        evaluation_time=1,
        market_epoch=0,
    )
    stale = _reduce_market(module, state, projection, old_epoch)
    assert stale.disposition is disposition.STALE
    assert stale.state == state

    future_epoch = _routed_occurrence(
        module,
        mandate,
        "adr023-recovery-future",
        sequence=1,
        source_time=1,
        evaluation_time=1,
        market_epoch=2,
    )
    refused = _reduce_market(module, state, projection, future_epoch)
    assert refused.disposition is disposition.REFUSED
    assert refused.state == state

    equal_coordinate = _routed_occurrence(
        module,
        mandate,
        "adr023-recovery-equal",
        sequence=0,
        source_time=0,
        evaluation_time=1,
        market_epoch=1,
    )
    equal = _reduce_market(module, state, projection, equal_coordinate)
    assert equal.disposition is disposition.STALE
    assert equal.state == state

    crossed = _routed_occurrence(
        module,
        mandate,
        "adr023-recovery-crossed",
        bid=102,
        ask=101,
        sequence=1,
        source_time=1,
        evaluation_time=1,
        market_epoch=1,
    )
    consumed = _reduce_market(module, state, projection, crossed)
    assert consumed.disposition is disposition.APPLIED
    assert consumed.state._market_source_sequence == 1
    assert consumed.state._market_baseline_required is True
    assert consumed.state._market_committed_epoch == 0
    assert consumed.critical_alert is None
    assert consumed.goal is None

    corrected_same_coordinate = _routed_occurrence(
        module,
        mandate,
        "adr023-recovery-corrected-same-coordinate",
        sequence=1,
        source_time=1,
        evaluation_time=2,
        market_epoch=1,
    )
    conflict = _reduce_market(
        module,
        consumed.state,
        projection,
        corrected_same_coordinate,
    )
    assert conflict.disposition is disposition.REFUSED
    assert conflict.state == consumed.state

    baseline = _routed_occurrence(
        module,
        mandate,
        "adr023-recovery-valid",
        sequence=2,
        source_time=2,
        evaluation_time=2,
        market_epoch=1,
    )
    recovered = _reduce_market(module, consumed.state, projection, baseline)
    assert recovered.disposition is disposition.APPLIED
    assert recovered.state._market_committed_epoch == 1
    assert recovered.state._market_expected_epoch is None
    assert recovered.state._market_baseline_required is False
    assert recovered.state._market_halted is False
    assert recovered.state._hard_bid_identity is None
    assert recovered.state._trade_identity is None
    assert recovered.state._trail_bid_identity is None
    assert recovered.goal is None
    assert recovered.critical_alert is None


@pytest.mark.parametrize("sequence_mode", ["SEQUENCED", "SOURCE_TIME"])
@pytest.mark.parametrize(
    ("case", "expected", "alert_name"),
    [
        ("immediate-replay", "EXACT_REPLAY", None),
        ("non-last-replay", "STALE", None),
        ("lower-coordinate", "STALE", None),
        ("equal-conflict", "APPLIED", "MARKET_BASELINE_REQUIRED"),
        ("strict-advance", "APPLIED", None),
    ],
)
def test_fixed_mode_replay_conflict_and_advance_matrix(
    sequence_mode: str,
    case: str,
    expected: str,
    alert_name: str | None,
) -> None:
    module = _protection_module()
    current = _owned_fill_transition(label=f"adr023-{sequence_mode}-{case}")
    mandate = _mandate(module, sequence_mode=sequence_mode)
    mandate, projection, state = _start(module, current, mandate)
    sequenced = sequence_mode == "SEQUENCED"
    first = _routed_occurrence(
        module,
        mandate,
        "adr023-matrix-first",
        bid=100,
        ask=101,
        sequence=1 if sequenced else None,
        source_time=1,
        evaluation_time=1,
    )
    first_result = _reduce_market(module, state, projection, first)
    state = first_result.state
    candidate = first
    if case == "immediate-replay":
        candidate = replace(first, evaluation_time=2)
    elif case == "non-last-replay":
        second = _routed_occurrence(
            module,
            mandate,
            "adr023-matrix-second",
            bid=100,
            ask=101,
            sequence=2 if sequenced else None,
            source_time=2,
            evaluation_time=2,
        )
        state = _reduce_market(module, state, projection, second).state
    elif case == "lower-coordinate":
        second = _routed_occurrence(
            module,
            mandate,
            "adr023-matrix-second",
            bid=100,
            ask=101,
            sequence=3 if sequenced else None,
            source_time=3,
            evaluation_time=3,
        )
        state = _reduce_market(module, state, projection, second).state
        candidate = _routed_occurrence(
            module,
            mandate,
            "adr023-matrix-lower",
            bid=99,
            ask=100,
            sequence=2 if sequenced else None,
            source_time=2,
            evaluation_time=4,
        )
    elif case == "equal-conflict":
        candidate = replace(first, best_ask=_price(102))
    elif case == "strict-advance":
        candidate = _routed_occurrence(
            module,
            mandate,
            "adr023-matrix-advance",
            bid=100,
            ask=101,
            sequence=2 if sequenced else None,
            source_time=2,
            evaluation_time=2,
        )

    before = state
    result = _reduce_market(module, state, projection, candidate)
    disposition, alert = _required(
        module,
        "ProtectionDisposition",
        "ProtectionAlert",
    )
    assert result.disposition is getattr(disposition, expected)
    assert result.critical_alert is (
        None if alert_name is None else getattr(alert, alert_name)
    )
    assert result.goal is None
    if expected in {"EXACT_REPLAY", "STALE", "REFUSED"}:
        assert result.state == before
    if case == "equal-conflict":
        assert result.state._market_baseline_required is True
        assert result.state._market_occurrence_identity == first.occurrence_id


@pytest.mark.parametrize(
    "case",
    [
        "stale-projection",
        "forked-projection",
        "advancing-projection",
        "wrong-source",
        "wrong-generation",
        "wrong-mode",
        "wrong-scope",
        "wrong-session",
    ],
)
def test_route_and_projection_mismatch_precede_cursor_reservation(case: str) -> None:
    module = _protection_module()
    current = _owned_fill_transition(label=f"adr023-route-{case}")
    mandate = _mandate(module)
    mandate, projection, state = _start(
        module,
        current,
        mandate,
        establish_baseline=False,
    )
    tested_projection = projection
    current_projection = projection
    current_state = state
    if case in {"stale-projection", "advancing-projection"}:
        higher = _advance_owned_fill(
            current,
            label=f"adr023-route-{case}-higher",
            quantity=1,
            units=100,
            prior_cumulative=4,
        )
        higher_projection = _projection(module, higher, mandate)
        if case == "stale-projection":
            advanced = _reduce_projection(module, state, higher_projection)
            current_state = advanced.state
            current_projection = higher_projection
            tested_projection = projection
        else:
            tested_projection = higher_projection
    elif case == "forked-projection":
        tested_projection = _clone_opaque(
            projection,
            execution_commitment=_flip_digest(projection.execution_commitment),
        )

    source_type, generation_type, session_type, symbol_type = _required(
        execution_core,
        "MarketDataSourceId",
        "MarketStreamGenerationId",
        "SessionId",
        "SymbolId",
    )
    overrides = {
        "source_id": (
            source_type("sip-secondary")
            if case == "wrong-source"
            else mandate.evidence_policy.source_id
        ),
        "stream_generation": (
            generation_type("22" * 32)
            if case == "wrong-generation"
            else mandate.evidence_policy.stream_generation
        ),
        "position_scope": (
            replace(mandate.position_scope, symbol_id=symbol_type("MSFT"))
            if case == "wrong-scope"
            else mandate.position_scope
        ),
        "session_id": (
            session_type("session-rth-2")
            if case == "wrong-session"
            else mandate.session_id
        ),
    }
    candidate = _routed_occurrence(
        module,
        mandate,
        f"adr023-route-{case}-candidate",
        sequence=None if case == "wrong-mode" else 1,
        source_time=1,
        evaluation_time=1,
        market_epoch=0,
        **overrides,
    )
    refused = _reduce_market(
        module,
        current_state,
        tested_projection,
        candidate,
    )
    (disposition,) = _required(module, "ProtectionDisposition")
    assert refused.disposition is disposition.REFUSED
    assert refused.state == current_state
    assert refused.goal is None
    assert refused.critical_alert is None

    valid = _routed_occurrence(
        module,
        mandate,
        f"adr023-route-{case}-valid",
        sequence=1,
        source_time=1,
        evaluation_time=1,
        market_epoch=0,
    )
    applied = _reduce_market(
        module,
        current_state,
        current_projection,
        valid,
    )
    assert applied.disposition is disposition.APPLIED
    assert applied.state._market_source_sequence == 1


@pytest.mark.parametrize(
    "case",
    ["expired", "evaluation-regressed", "crossed", "tick-invalid", "step-invalid"],
)
def test_context_denial_happens_after_irreversible_cursor_reservation(
    case: str,
) -> None:
    module = _protection_module()
    current = _owned_fill_transition(label=f"adr023-context-{case}")
    mandate = _mandate(module)
    if case == "evaluation-regressed":
        mandate, projection, state = _start(
            module,
            current,
            mandate,
            establish_baseline=False,
        )
        baseline = _routed_occurrence(
            module,
            mandate,
            "adr023-context-evaluation-baseline",
            sequence=0,
            source_time=0,
            evaluation_time=10,
        )
        state = _reduce_market(module, state, projection, baseline).state
    else:
        mandate, projection, state = _start(module, current, mandate)

    occurrence = _routed_occurrence(
        module,
        mandate,
        f"adr023-context-{case}-first",
        bid=(102 if case == "crossed" else 200 if case == "step-invalid" else 100),
        ask=101 if case != "step-invalid" else 201,
        sequence=1,
        source_time=1 if case != "evaluation-regressed" else 10,
        evaluation_time=(
            20 if case == "expired" else 9 if case == "evaluation-regressed" else 1
        ),
    )
    if case == "tick-invalid":
        occurrence = replace(
            occurrence,
            best_bid=_price(100, tick_units=2),
            best_ask=_price(102, tick_units=2),
        )
    first = _reduce_market(module, state, projection, occurrence)
    disposition, alert = _required(
        module,
        "ProtectionDisposition",
        "ProtectionAlert",
    )
    assert first.disposition is disposition.APPLIED
    assert first.state._market_source_sequence == 1
    assert first.state._market_occurrence_identity == occurrence.occurrence_id
    assert first.goal is None
    assert first.critical_alert is None

    if case in {"expired", "evaluation-regressed"}:
        corrected = replace(
            occurrence,
            evaluation_time=(2 if case == "expired" else 11),
        )
        replay = _reduce_market(module, first.state, projection, corrected)
        assert corrected.occurrence_id == occurrence.occurrence_id
        assert replay.disposition is disposition.EXACT_REPLAY
        assert replay.state == first.state
        assert replay.critical_alert is None
    else:
        corrected = _routed_occurrence(
            module,
            mandate,
            f"adr023-context-{case}-corrected",
            bid=100,
            ask=101,
            sequence=1,
            source_time=1,
            evaluation_time=2,
        )
        conflict = _reduce_market(module, first.state, projection, corrected)
        assert corrected.occurrence_id != occurrence.occurrence_id
        assert conflict.disposition is disposition.APPLIED
        assert conflict.critical_alert is alert.MARKET_BASELINE_REQUIRED
        assert conflict.state._market_baseline_required is True
        assert conflict.state._market_occurrence_identity == occurrence.occurrence_id


def test_halt_and_favorable_baseline_reopen_without_goal_or_evidence() -> None:
    module = _protection_module()
    current = _owned_fill_transition(label="adr023-halt-reopen")
    mandate, projection, state = _start(module, current)
    halt = _routed_occurrence(
        module,
        mandate,
        "adr023-halt",
        sequence=1,
        source_time=1,
        evaluation_time=1,
        halted=True,
    )
    halted = _reduce_market(module, state, projection, halt)
    disposition, alert, policy = _required(
        module,
        "ProtectionDisposition",
        "ProtectionAlert",
        "ProtectionPolicy",
    )
    assert halted.disposition is disposition.APPLIED
    assert halted.critical_alert is alert.MARKET_BASELINE_REQUIRED
    assert halted.state._market_halted is True
    assert halted.state._market_baseline_required is True
    assert halted.state._market_expected_epoch == 1
    assert halted.goal is None

    favorable = _routed_occurrence(
        module,
        mandate,
        "adr023-favorable-reopen",
        bid=120,
        ask=121,
        sequence=2,
        source_time=2,
        evaluation_time=2,
        market_epoch=1,
    )
    reopened = _reduce_market(module, halted.state, projection, favorable)
    assert reopened.disposition is disposition.APPLIED
    assert reopened.state._market_halted is False
    assert reopened.state._market_baseline_required is False
    assert reopened.state._market_committed_epoch == 1
    assert reopened.state.policy is policy.TRAIL_ACTIVE
    assert reopened.state.high_watermark is not None
    assert reopened.state.trail is not None
    assert reopened.state._hard_bid_identity is None
    assert reopened.state._trade_identity is None
    assert reopened.state._trail_bid_identity is None
    assert reopened.goal is None
    assert reopened.critical_alert is None


@pytest.mark.parametrize("sequence_mode", ["SEQUENCED", "SOURCE_TIME"])
def test_strict_coordinate_max_enters_terminal_exhaustion_once(
    sequence_mode: str,
) -> None:
    module = _protection_module()
    current = _owned_fill_transition(label=f"adr023-coordinate-max-{sequence_mode}")
    mandate = _mandate(
        module,
        sequence_mode=sequence_mode,
        max_age=_U64_MAX,
    )
    mandate, projection, state = _start(
        module,
        current,
        mandate,
        establish_baseline=False,
    )
    maximum = _routed_occurrence(
        module,
        mandate,
        f"adr023-coordinate-max-{sequence_mode}",
        sequence=_U64_MAX if sequence_mode == "SEQUENCED" else None,
        source_time=1 if sequence_mode == "SEQUENCED" else _U64_MAX,
        evaluation_time=1 if sequence_mode == "SEQUENCED" else _U64_MAX,
        market_epoch=0,
    )
    exhausted = _reduce_market(module, state, projection, maximum)
    disposition, alert = _required(
        module,
        "ProtectionDisposition",
        "ProtectionAlert",
    )
    assert exhausted.disposition is disposition.APPLIED
    assert exhausted.critical_alert is alert.MARKET_COORDINATE_EXHAUSTED
    assert exhausted.state._market_baseline_required is True
    assert exhausted.state._market_exhausted is True
    assert exhausted.state._market_expected_epoch is None
    assert exhausted.goal is None

    replay = _reduce_market(module, exhausted.state, projection, maximum)
    assert replay.disposition is disposition.EXACT_REPLAY
    assert replay.state == exhausted.state
    assert replay.critical_alert is None

    lower = _routed_occurrence(
        module,
        mandate,
        f"adr023-coordinate-lower-{sequence_mode}",
        sequence=_U64_MAX - 1 if sequence_mode == "SEQUENCED" else None,
        source_time=2 if sequence_mode == "SEQUENCED" else _U64_MAX - 1,
        evaluation_time=2 if sequence_mode == "SEQUENCED" else _U64_MAX,
        market_epoch=0,
    )
    stale = _reduce_market(module, exhausted.state, projection, lower)
    assert stale.disposition is disposition.STALE
    assert stale.state == exhausted.state

    conflict = replace(maximum, best_ask=_price(102))
    refused = _reduce_market(module, exhausted.state, projection, conflict)
    assert refused.disposition is disposition.REFUSED
    assert refused.state == exhausted.state
    repeated_invalidation = _invalidate_market(module, exhausted.state, projection)
    assert repeated_invalidation.disposition is disposition.EXACT_REPLAY
    assert repeated_invalidation.state == exhausted.state

    additional_fill = _advance_owned_fill(
        current,
        label="adr023-exhausted-economics-advance",
        quantity=1,
        units=120,
        prior_cumulative=4,
    )
    advanced_projection = _projection(module, additional_fill, mandate)
    economics = _reduce_projection(
        module,
        exhausted.state,
        advanced_projection,
    )
    assert economics.disposition is disposition.APPLIED
    assert economics.state.raw_quantity == exhausted.state.raw_quantity + 1
    assert economics.state.execution_commitment == additional_fill.execution.commitment
    assert economics.state._market_baseline_required is True
    assert economics.state._market_exhausted is True
    assert economics.goal is None
    assert economics.critical_alert is None


def _authentic_serving_state_at_epoch(
    module: ModuleType,
    state: object,
    mandate: object,
    *,
    epoch: int,
    coordinate: int,
) -> object:
    sequenced = mandate.evidence_policy.sequence_mode.value == "SEQUENCED"
    anchor = _routed_occurrence(
        module,
        mandate,
        f"adr023-authentic-epoch-{epoch}-{coordinate}",
        sequence=coordinate if sequenced else None,
        source_time=coordinate,
        evaluation_time=coordinate,
        market_epoch=epoch,
    )
    return _rebuild_authentic_state(
        module,
        state,
        _market_occurrence_epoch=epoch,
        _market_committed_epoch=epoch,
        _market_expected_epoch=None,
        _market_source_sequence=coordinate if sequenced else None,
        _market_source_time=coordinate,
        _market_evaluation_time=coordinate,
        _market_occurrence_identity=anchor.occurrence_id,
        _market_halted=False,
        _market_baseline_required=False,
        _market_exhausted=False,
        _hard_bid_identity=None,
        _hard_bid_source_time=None,
        _trade_identity=None,
        _trade_source_time=None,
        _trail_bid_identity=None,
        _trail_bid_source_time=None,
    )


def test_committing_epoch_max_enters_terminal_exhaustion_independently() -> None:
    module = _protection_module()
    current = _owned_fill_transition(label="adr023-commit-epoch-max")
    mandate = _mandate(module, sequence_mode="SEQUENCED", max_age=_U64_MAX)
    mandate, projection, state = _start(module, current, mandate)
    state = _authentic_serving_state_at_epoch(
        module,
        state,
        mandate,
        epoch=_U64_MAX - 1,
        coordinate=1,
    )
    invalidated = _invalidate_market(module, state, projection)
    disposition, alert = _required(
        module,
        "ProtectionDisposition",
        "ProtectionAlert",
    )
    assert invalidated.disposition is disposition.APPLIED
    assert invalidated.critical_alert is alert.MARKET_BASELINE_REQUIRED
    assert invalidated.state._market_expected_epoch == _U64_MAX
    assert invalidated.state._market_exhausted is False

    baseline = _routed_occurrence(
        module,
        mandate,
        "adr023-commit-epoch-max-baseline",
        sequence=2,
        source_time=2,
        evaluation_time=2,
        market_epoch=_U64_MAX,
    )
    exhausted = _reduce_market(module, invalidated.state, projection, baseline)
    assert exhausted.disposition is disposition.APPLIED
    assert exhausted.critical_alert is alert.MARKET_COORDINATE_EXHAUSTED
    assert exhausted.state._market_committed_epoch == _U64_MAX
    assert exhausted.state._market_occurrence_identity == baseline.occurrence_id
    assert exhausted.state._market_expected_epoch is None
    assert exhausted.state._market_baseline_required is True
    assert exhausted.state._market_exhausted is True
    assert exhausted.state._hard_bid_identity is None
    assert exhausted.state._trade_identity is None
    assert exhausted.state._trail_bid_identity is None
    assert exhausted.goal is None

    replay = _reduce_market(module, exhausted.state, projection, baseline)
    assert replay.disposition is disposition.EXACT_REPLAY
    assert replay.state == exhausted.state
    refused = _reduce_market(
        module,
        exhausted.state,
        projection,
        _routed_occurrence(
            module,
            mandate,
            "adr023-after-commit-epoch-max",
            sequence=3,
            source_time=3,
            evaluation_time=3,
            market_epoch=_U64_MAX,
        ),
    )
    assert refused.disposition is disposition.REFUSED
    assert refused.state == exhausted.state


@pytest.mark.parametrize("cause", ["invalidation", "halt"])
def test_increment_from_committed_epoch_max_exhausts_without_wrap(
    cause: str,
) -> None:
    module = _protection_module()
    current = _owned_fill_transition(label=f"adr023-increment-max-{cause}")
    mandate = _mandate(module, sequence_mode="SEQUENCED", max_age=_U64_MAX)
    mandate, projection, state = _start(module, current, mandate)
    state = _authentic_serving_state_at_epoch(
        module,
        state,
        mandate,
        epoch=_U64_MAX,
        coordinate=1,
    )
    if cause == "invalidation":
        exhausted = _invalidate_market(module, state, projection)
    else:
        exhausted = _reduce_market(
            module,
            state,
            projection,
            _routed_occurrence(
                module,
                mandate,
                "adr023-increment-max-halt",
                sequence=2,
                source_time=2,
                evaluation_time=2,
                market_epoch=_U64_MAX,
                halted=True,
            ),
        )
    disposition, alert = _required(
        module,
        "ProtectionDisposition",
        "ProtectionAlert",
    )
    assert exhausted.disposition is disposition.APPLIED
    assert exhausted.critical_alert is alert.MARKET_COORDINATE_EXHAUSTED
    assert exhausted.state._market_committed_epoch == _U64_MAX
    assert exhausted.state._market_expected_epoch is None
    assert exhausted.state._market_baseline_required is True
    assert exhausted.state._market_exhausted is True
    assert exhausted.goal is None
    repeated = _invalidate_market(module, exhausted.state, projection)
    assert repeated.disposition is disposition.EXACT_REPLAY
    assert repeated.state == exhausted.state


@pytest.mark.parametrize(
    ("source_time", "evaluation_time", "case"),
    [
        pytest.param(1, _U64_MAX, "evaluation-only", id="evaluation-time-max"),
        pytest.param(
            _U64_MAX,
            _U64_MAX,
            "source-after-evaluation-control",
            id="sequenced-source-time-max",
        ),
    ],
)
def test_secondary_watermark_maxima_do_not_exhaust_sequenced_mode(
    source_time: int,
    evaluation_time: int,
    case: str,
) -> None:
    module = _protection_module()
    current = _owned_fill_transition(label=f"adr023-secondary-max-{case}")
    mandate = _mandate(module, sequence_mode="SEQUENCED")
    mandate, projection, state = _start(module, current, mandate)
    first = _routed_occurrence(
        module,
        mandate,
        f"adr023-secondary-max-{case}-first",
        sequence=1,
        source_time=source_time,
        evaluation_time=evaluation_time,
    )
    applied = _reduce_market(module, state, projection, first)
    (disposition,) = _required(module, "ProtectionDisposition")
    assert applied.disposition is disposition.APPLIED
    assert applied.state._market_exhausted is False
    assert applied.critical_alert is None

    second = _routed_occurrence(
        module,
        mandate,
        f"adr023-secondary-max-{case}-second",
        sequence=2,
        source_time=source_time,
        evaluation_time=evaluation_time,
    )
    advanced = _reduce_market(module, applied.state, projection, second)
    assert advanced.disposition is disposition.APPLIED
    assert advanced.state._market_source_sequence == 2
    assert advanced.state._market_source_time == source_time
    assert advanced.state._market_evaluation_time == evaluation_time
    assert advanced.state._market_exhausted is False
    assert advanced.critical_alert is None


def test_evaluation_time_max_does_not_exhaust_source_time_mode() -> None:
    module = _protection_module()
    current = _owned_fill_transition(label="adr023-source-time-evaluation-max")
    mandate = _mandate(
        module,
        sequence_mode="SOURCE_TIME",
        max_age=_U64_MAX,
    )
    mandate, projection, state = _start(module, current, mandate)
    (disposition,) = _required(module, "ProtectionDisposition")

    first = _routed_occurrence(
        module,
        mandate,
        "adr023-source-time-evaluation-max-first",
        sequence=None,
        source_time=1,
        evaluation_time=_U64_MAX,
    )
    applied = _reduce_market(module, state, projection, first)
    assert applied.disposition is disposition.APPLIED
    assert applied.state._market_source_sequence is None
    assert applied.state._market_source_time == 1
    assert applied.state._market_evaluation_time == _U64_MAX
    assert applied.state._market_exhausted is False
    assert applied.critical_alert is None

    second = _routed_occurrence(
        module,
        mandate,
        "adr023-source-time-evaluation-max-second",
        sequence=None,
        source_time=2,
        evaluation_time=_U64_MAX,
    )
    advanced = _reduce_market(module, applied.state, projection, second)
    assert advanced.disposition is disposition.APPLIED
    assert advanced.state._market_source_sequence is None
    assert advanced.state._market_source_time == 2
    assert advanced.state._market_evaluation_time == _U64_MAX
    assert advanced.state._market_exhausted is False
    assert advanced.critical_alert is None


def _reference_exhausts(
    cause: str,
    *,
    omit_strict_max: bool = False,
    omit_commit_max: bool = False,
    wrap_increment_max: bool = False,
    exhaust_secondary_max: bool = False,
    exhaust_source_time_evaluation_max: bool = False,
) -> bool:
    if cause == "strict-coordinate-max":
        return not omit_strict_max
    if cause == "commit-epoch-max":
        return not omit_commit_max
    if cause == "increment-from-committed-max":
        return not wrap_increment_max
    if cause == "source-time-evaluation-max":
        return exhaust_secondary_max or exhaust_source_time_evaluation_max
    if cause in {"evaluation-time-max", "sequenced-source-time-max"}:
        return exhaust_secondary_max
    raise AssertionError(cause)


def test_three_exhaustion_causes_and_three_nontriggers_are_failure_capable() -> None:
    expected = {
        "strict-coordinate-max": True,
        "commit-epoch-max": True,
        "increment-from-committed-max": True,
        "evaluation-time-max": False,
        "sequenced-source-time-max": False,
        "source-time-evaluation-max": False,
    }
    for cause, terminal in expected.items():
        assert _reference_exhausts(cause) is terminal
    mutations = {
        "omit-strict-max": (
            {"omit_strict_max": True},
            {"strict-coordinate-max"},
        ),
        "omit-commit-max": (
            {"omit_commit_max": True},
            {"commit-epoch-max"},
        ),
        "wrap-increment-max": (
            {"wrap_increment_max": True},
            {"increment-from-committed-max"},
        ),
        "exhaust-secondary-max": (
            {"exhaust_secondary_max": True},
            {
                "evaluation-time-max",
                "sequenced-source-time-max",
                "source-time-evaluation-max",
            },
        ),
        "exhaust-source-time-evaluation-max": (
            {"exhaust_source_time_evaluation_max": True},
            {"source-time-evaluation-max"},
        ),
    }
    for label, (mutation, required_kills) in mutations.items():
        killed = {
            cause
            for cause, terminal in expected.items()
            if _reference_exhausts(cause, **mutation) is not terminal
        }
        assert killed == required_kills, (label, killed)


def test_epoch_increment_is_fixed_width_and_never_wraps() -> None:
    module = _protection_module()
    (next_epoch,) = _required(module, "_next_market_epoch")
    assert next_epoch(0) == 1
    assert next_epoch(_U64_MAX - 1) == _U64_MAX
    assert next_epoch(_U64_MAX) is None
    for malformed in (True, -1, _U64_MAX + 1):
        with pytest.raises((TypeError, ValueError)):
            next_epoch(malformed)


def test_market_stream_generation_identity_is_exact_canonical_hex() -> None:
    (generation_type,) = _required(execution_core, "MarketStreamGenerationId")
    value = generation_type("ab" * 32)
    assert value.value == "ab" * 32
    for malformed in ("AB" * 32, "ab" * 31, "ab" * 33, "g0" * 32):
        with pytest.raises((TypeError, ValueError)):
            generation_type(malformed)


def test_market_occurrence_identity_is_exact_canonical_hex() -> None:
    (occurrence_id_type,) = _required(execution_core, "MarketOccurrenceId")
    value = occurrence_id_type("ab" * 32)
    assert value.value == "ab" * 32
    for malformed in ("AB" * 32, "ab" * 31, "ab" * 33, "g0" * 32):
        with pytest.raises((TypeError, ValueError)):
            occurrence_id_type(malformed)


def test_market_sequence_mode_and_alert_vocabularies_are_exact() -> None:
    module = _protection_module()
    sequence_mode, alert = _required(
        module,
        "MarketSequenceMode",
        "ProtectionAlert",
    )
    assert tuple(member.name for member in sequence_mode) == (
        "SEQUENCED",
        "SOURCE_TIME",
    )
    assert tuple(member.name for member in alert) == (
        "LATE_POSITIVE_AFTER_FLAT",
        "MARKET_BASELINE_REQUIRED",
        "MARKET_COORDINATE_EXHAUSTED",
    )


def test_adr023_split_transition_signatures_are_exact() -> None:
    module = _protection_module()
    reduce_projection, reduce_market, invalidate = _required(
        module,
        "reduce_position_protection",
        "reduce_position_protection_market",
        "invalidate_position_protection_market",
    )
    assert tuple(inspect.signature(reduce_projection).parameters) == (
        "state",
        "projection",
    )
    assert tuple(inspect.signature(reduce_market).parameters) == (
        "state",
        "projection",
        "occurrence",
    )
    assert tuple(inspect.signature(invalidate).parameters) == ("state", "projection")


def test_market_occurrence_public_shape_excludes_identity_construction() -> None:
    module = _protection_module()
    (occurrence_type,) = _required(module, "MarketOccurrence")
    assert inspect.signature(occurrence_type).parameters.get("occurrence_id") is None
    occurrence_field = next(
        retained
        for retained in fields(occurrence_type)
        if retained.name == "occurrence_id"
    )
    assert occurrence_field.init is False


def test_public_surface_cannot_accept_caller_recovery_authority() -> None:
    module = _protection_module()
    forbidden_fragments = {
        "baseline_flag",
        "baseline_ready",
        "recovery_fence",
        "restart_provenance",
        "subscription_ack",
    }
    public_types = _required(module, "EvidencePolicy", "MarketOccurrence")
    public_functions = _required(
        module,
        "reduce_position_protection_market",
        "invalidate_position_protection_market",
    )
    exposed = {
        retained.name for value_type in public_types for retained in fields(value_type)
    }
    exposed.update(
        parameter
        for function in public_functions
        for parameter in inspect.signature(function).parameters
    )
    assert exposed.isdisjoint(forbidden_fragments)


_PY311_AST_API = frozenset(
    {
        "AST",
        "Add",
        "And",
        "AnnAssign",
        "Assert",
        "Assign",
        "AsyncFor",
        "AsyncFunctionDef",
        "AsyncWith",
        "Attribute",
        "AugAssign",
        "Await",
        "BinOp",
        "BitOr",
        "BoolOp",
        "Call",
        "ClassDef",
        "Compare",
        "Constant",
        "Del",
        "Delete",
        "Dict",
        "DictComp",
        "Div",
        "Eq",
        "ExceptHandler",
        "Expr",
        "FloorDiv",
        "For",
        "FunctionDef",
        "GeneratorExp",
        "Global",
        "Gt",
        "GtE",
        "If",
        "Import",
        "ImportFrom",
        "In",
        "Is",
        "IsNot",
        "Lambda",
        "List",
        "ListComp",
        "Load",
        "Lt",
        "LtE",
        "Match",
        "MatchAs",
        "MatchMapping",
        "MatchStar",
        "Mod",
        "Module",
        "Mult",
        "Name",
        "NamedExpr",
        "NodeVisitor",
        "Nonlocal",
        "Not",
        "NotEq",
        "NotIn",
        "Or",
        "Pass",
        "Raise",
        "Return",
        "Set",
        "SetComp",
        "Starred",
        "Store",
        "Sub",
        "Subscript",
        "Try",
        "TryStar",
        "Tuple",
        "UAdd",
        "USub",
        "UnaryOp",
        "While",
        "With",
        "Yield",
        "YieldFrom",
        "arg",
        "cmpop",
        "comprehension",
        "dump",
        "get_source_segment",
        "iter_child_nodes",
        "keyword",
        "parse",
        "stmt",
        "unparse",
        "walk",
    }
)


def _unsupported_python311_ast_api(source: str) -> frozenset[str]:
    tree = ast.parse(source)
    used = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "ast"
    }
    return frozenset(used - _PY311_AST_API)


def test_changed_red_python_is_python311_grammar_and_ast_api_compatible() -> None:
    paths = (
        Path(__file__),
        Path(__file__).with_name("test_protection_stateful.py"),
        Path(__file__).with_name("test_import_boundary.py"),
    )
    for path in paths:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path), feature_version=(3, 11))
        assert not _unsupported_python311_ast_api(source), path

    with pytest.raises(SyntaxError):
        ast.parse("type Python312Only = int", feature_version=(3, 11))
    assert _unsupported_python311_ast_api("value = ast.TypeAlias") == frozenset(
        {"TypeAlias"}
    )
