"""Pure immutable acquisition authority values for the reset execution kernel.

This module owns no broker syntax, I/O, clock, persistence, or serving state.
It binds the structural entry policy to a complete protection mandate; later
WO-0149 reducer and authority seams consume only the resulting sealed values.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction

from .fills import (
    PositionScope,
    _commit_parts,
    _encode_fraction,
    _encode_int,
    _encode_position_scope,
    _encode_reported_price,
    _encode_text,
)
from .identity import (
    AcquisitionMandateId,
    ClientOrderId,
    DualMandateBinding,
    EffectId,
    RequestOccurrenceId,
    SessionId,
)
from .protection import (
    ExecutionGoal,
    MarketOccurrence,
    PositionProtectionState,
    ProtectionAlert,
    ProtectionDisposition,
    ProtectionMandate,
    ProtectionPolicy,
    initialize_position_protection,
    project_protection_venue,
    reduce_position_protection,
    reduce_position_protection_market,
)
from .values import Quantity, ReportedPrice
from .venue import (
    AcquisitionVenueProjection,
    VenueRecoveryDisposition,
    VenueRecoveryTransition,
    project_acquisition_venue,
)


class AcquisitionOrderType(str, Enum):
    """Broker-neutral entry order types admitted by the initial pure kernel."""

    LIMIT = "LIMIT"


def _require(name: str, value: object, expected: type[object]) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must be the exact {expected.__name__} type")


def _require_non_negative_time(name: str, value: object) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _require_positive_quantity(name: str, value: object) -> None:
    _require(name, value, Quantity)
    if value.value <= 0:
        raise ValueError(f"{name} must be positive")


def _require_price(name: str, value: object) -> None:
    _require(name, value, ReportedPrice)
    if not value.is_aligned:
        raise ValueError(f"{name} must be aligned to its exact tick")
    if value.exact_value <= 0:
        raise ValueError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class AcquisitionEffectTerms:
    """One typed, broker-neutral candidate child constrained by a mandate."""

    effect_id: EffectId
    request_occurrence_id: RequestOccurrenceId
    client_order_id: ClientOrderId
    quantity: Quantity
    limit_price: ReportedPrice
    order_type: AcquisitionOrderType
    evaluation_time: int

    def __post_init__(self) -> None:
        _require("effect_id", self.effect_id, EffectId)
        _require(
            "request_occurrence_id", self.request_occurrence_id, RequestOccurrenceId
        )
        _require("client_order_id", self.client_order_id, ClientOrderId)
        _require_positive_quantity("quantity", self.quantity)
        _require_price("limit_price", self.limit_price)
        _require("order_type", self.order_type, AcquisitionOrderType)
        _require_non_negative_time("evaluation_time", self.evaluation_time)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionEffectTerms is exact and cannot be subclassed")

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/acquisition-effect-terms/v1",
            _encode_text(self.effect_id.value),
            _encode_text(self.request_occurrence_id.value),
            _encode_text(self.client_order_id.value),
            _encode_int(self.quantity.value),
            _encode_reported_price(self.limit_price),
            _encode_text(self.order_type.value),
            _encode_int(self.evaluation_time),
        )


@dataclass(frozen=True, slots=True)
class AcquisitionMandate:
    """Exact immutable operator-approved BUY policy bound to protection policy."""

    acquisition_mandate_id: AcquisitionMandateId
    position_scope: PositionScope
    session_id: SessionId
    configuration_version: str
    maximum_quantity: Quantity
    maximum_notional: Fraction
    maximum_entry_price: ReportedPrice
    allowed_order_types: tuple[AcquisitionOrderType, ...]
    expiry: int
    deadline: int
    fixed_child_cap: Quantity
    certified_participation_cap: Fraction | None
    cancel_reprice_budget: int
    protection_mandate: ProtectionMandate

    def __post_init__(self) -> None:
        _require(
            "acquisition_mandate_id", self.acquisition_mandate_id, AcquisitionMandateId
        )
        _require("position_scope", self.position_scope, PositionScope)
        _require("session_id", self.session_id, SessionId)
        if type(self.configuration_version) is not str:
            raise TypeError("configuration_version must be a string")
        if not self.configuration_version.strip():
            raise ValueError("configuration_version must be nonblank")
        _require_positive_quantity("maximum_quantity", self.maximum_quantity)
        if type(self.maximum_notional) is not Fraction:
            raise TypeError("maximum_notional must be the exact Fraction type")
        if self.maximum_notional <= 0:
            raise ValueError("maximum_notional must be positive")
        _require_price("maximum_entry_price", self.maximum_entry_price)
        if type(self.allowed_order_types) is not tuple:
            raise TypeError("allowed_order_types must be a tuple")
        if not self.allowed_order_types:
            raise ValueError("allowed_order_types must be nonempty")
        if len(set(self.allowed_order_types)) != len(self.allowed_order_types):
            raise ValueError("allowed_order_types must not contain duplicates")
        for order_type in self.allowed_order_types:
            _require("allowed_order_types item", order_type, AcquisitionOrderType)
        _require_non_negative_time("expiry", self.expiry)
        _require_non_negative_time("deadline", self.deadline)
        if self.expiry > self.deadline:
            raise ValueError("expiry cannot follow deadline")
        _require_positive_quantity("fixed_child_cap", self.fixed_child_cap)
        if self.fixed_child_cap.value > self.maximum_quantity.value:
            raise ValueError("fixed_child_cap cannot exceed maximum_quantity")
        if self.certified_participation_cap is not None:
            if type(self.certified_participation_cap) is not Fraction:
                raise TypeError("certified_participation_cap must be Fraction or None")
            if not 0 < self.certified_participation_cap <= 1:
                raise ValueError("certified_participation_cap must be in (0, 1]")
        if type(self.cancel_reprice_budget) is not int:
            raise TypeError("cancel_reprice_budget must be an exact integer")
        if self.cancel_reprice_budget < 0:
            raise ValueError("cancel_reprice_budget must be non-negative")
        _require("protection_mandate", self.protection_mandate, ProtectionMandate)
        protection = self.protection_mandate
        if protection.position_scope != self.position_scope:
            raise ValueError("protection mandate position scope must match")
        if protection.session_id != self.session_id:
            raise ValueError("protection mandate session must match")
        if protection.configuration_version != self.configuration_version:
            raise ValueError("protection mandate configuration must match")
        if protection.maximum_quantity.value < self.maximum_quantity.value:
            raise ValueError("protection mandate capacity must cover acquisition")
        if self.deadline > protection.deadline:
            raise ValueError("acquisition deadline cannot exceed protection deadline")
        if (
            self.maximum_entry_price.tick != protection.tick
            or not self.maximum_entry_price.is_aligned
        ):
            raise ValueError("maximum_entry_price tick must match protection mandate")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionMandate is exact and cannot be subclassed")

    @property
    def commitment(self) -> bytes:
        """Return the complete immutable acquisition-policy commitment."""

        participation = (
            _commit_parts(b"execution-core/acquisition-participation/none/v1")
            if self.certified_participation_cap is None
            else _encode_fraction(self.certified_participation_cap)
        )
        return _commit_parts(
            b"execution-core/acquisition-mandate/v1",
            _encode_text(self.acquisition_mandate_id.value),
            _encode_position_scope(self.position_scope),
            _encode_text(self.session_id.value),
            _encode_text(self.configuration_version),
            _encode_int(self.maximum_quantity.value),
            _encode_fraction(self.maximum_notional),
            _encode_reported_price(self.maximum_entry_price),
            _encode_text("|".join(item.value for item in self.allowed_order_types)),
            _encode_int(self.expiry),
            _encode_int(self.deadline),
            _encode_int(self.fixed_child_cap.value),
            participation,
            _encode_int(self.cancel_reprice_budget),
            self.protection_mandate.commitment,
        )

    @property
    def binding(self) -> DualMandateBinding:
        """Return the bounded distinct acquisition/protection authority pair."""

        return DualMandateBinding(
            acquisition_mandate_id=self.acquisition_mandate_id,
            acquisition_commitment=self.commitment,
            protection_mandate_id=self.protection_mandate.mandate_id,
            protection_commitment=self.protection_mandate.commitment,
        )


class AcquisitionDisposition(str, Enum):
    """Stable result classification for pure acquisition reductions."""

    APPLIED = "APPLIED"
    REFUSED = "REFUSED"
    EXACT_REPLAY = "EXACT_REPLAY"


class _AcquisitionLifecycle(str, Enum):
    READY = "READY"
    WORKING = "WORKING"
    CANCELING = "CANCELING"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


def _state_seal(
    mandate: AcquisitionMandate,
    lifecycle: _AcquisitionLifecycle,
    owned_quantity: int,
    owned_notional: Fraction,
    preempted: bool,
    projection_head: bytes,
    execution_commitment: bytes,
    venue_commitment: bytes,
    protection_commitment: bytes,
    predecessor_currentness_head: bytes | None,
) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-state/v1",
        mandate.commitment,
        _encode_text(lifecycle.value),
        _encode_int(owned_quantity),
        _encode_fraction(owned_notional),
        b"1" if preempted else b"0",
        projection_head,
        execution_commitment,
        venue_commitment,
        protection_commitment,
        (
            predecessor_currentness_head
            if predecessor_currentness_head is not None
            else _commit_parts(b"execution-core/acquisition-currentness/genesis/v1")
        ),
    )


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionState:
    """Opaque bounded acquisition lifecycle and owned canonical economics."""

    _mandate: AcquisitionMandate
    _projection: AcquisitionVenueProjection
    _lifecycle: _AcquisitionLifecycle
    _owned_quantity: int
    _owned_notional: Fraction
    _preempted: bool
    _projection_head: bytes
    _execution_commitment: bytes
    _venue_commitment: bytes
    _protection_state: PositionProtectionState | None
    _predecessor_currentness_head: bytes | None
    _seal: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionState is opaque; use acquisition reducers")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionState cannot be subclassed")

    @property
    def mandate(self) -> AcquisitionMandate:
        return self._mandate

    @property
    def commitment(self) -> bytes:
        return self._seal


def _protection_state_commitment(
    mandate: AcquisitionMandate,
    protection_state: PositionProtectionState | None,
) -> bytes:
    """Commit exactly one bounded linked protection state or its explicit absence."""

    if protection_state is None:
        return _commit_parts(
            b"execution-core/acquisition-protection/uninitialized/v1",
            mandate.protection_mandate.commitment,
        )
    return _commit_parts(
        b"execution-core/acquisition-protection/state/v1",
        protection_state.commitment,
    )


def _state_is_authentic(state: AcquisitionState) -> bool:
    if type(state) is not AcquisitionState:
        return False
    if type(state._mandate) is not AcquisitionMandate:
        return False
    if (
        type(state._projection) is not AcquisitionVenueProjection
        or not state._projection.is_authentic
    ):
        return False
    if type(state._lifecycle) is not _AcquisitionLifecycle:
        return False
    if type(state._owned_quantity) is not int or state._owned_quantity < 0:
        return False
    if type(state._owned_notional) is not Fraction or state._owned_notional < 0:
        return False
    if type(state._preempted) is not bool:
        return False
    if state._protection_state is not None:
        if type(state._protection_state) is not PositionProtectionState:
            return False
        if (
            state._protection_state.mandate != state._mandate.protection_mandate
            or state._protection_state.execution_commitment
            != state._execution_commitment
        ):
            return False
    for value in (
        state._projection_head,
        state._execution_commitment,
        state._venue_commitment,
        state._seal,
    ):
        if type(value) is not bytes or len(value) != 32:
            return False
    if state._predecessor_currentness_head is not None and (
        type(state._predecessor_currentness_head) is not bytes
        or len(state._predecessor_currentness_head) != 32
    ):
        return False
    if (
        state._projection.head != state._projection_head
        or state._projection.execution_commitment != state._execution_commitment
        or state._projection.venue_commitment != state._venue_commitment
    ):
        return False
    return state._seal == _state_seal(
        state._mandate,
        state._lifecycle,
        state._owned_quantity,
        state._owned_notional,
        state._preempted,
        state._projection_head,
        state._execution_commitment,
        state._venue_commitment,
        _protection_state_commitment(state._mandate, state._protection_state),
        state._predecessor_currentness_head,
    )


def _new_state(
    mandate: AcquisitionMandate,
    lifecycle: _AcquisitionLifecycle,
    owned_quantity: int,
    owned_notional: Fraction,
    preempted: bool,
    projection: AcquisitionVenueProjection,
    protection_state: PositionProtectionState | None,
    predecessor_currentness_head: bytes | None,
) -> AcquisitionState:
    result = object.__new__(AcquisitionState)
    for name, value in (
        ("_mandate", mandate),
        ("_projection", projection),
        ("_lifecycle", lifecycle),
        ("_owned_quantity", owned_quantity),
        ("_owned_notional", owned_notional),
        ("_preempted", preempted),
        ("_projection_head", projection.head),
        ("_execution_commitment", projection.execution_commitment),
        ("_venue_commitment", projection.venue_commitment),
        ("_protection_state", protection_state),
        ("_predecessor_currentness_head", predecessor_currentness_head),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _state_seal(
            mandate,
            lifecycle,
            owned_quantity,
            owned_notional,
            preempted,
            projection.head,
            projection.execution_commitment,
            projection.venue_commitment,
            _protection_state_commitment(mandate, protection_state),
            predecessor_currentness_head,
        ),
    )
    if not _state_is_authentic(result):
        raise ValueError("acquisition state is not exact")
    return result


def _currentness_seal(
    state: AcquisitionState,
) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-currentness/v1",
        state.commitment,
        state._projection_head,
        (
            state._predecessor_currentness_head
            if state._predecessor_currentness_head is not None
            else _commit_parts(b"execution-core/acquisition-currentness/genesis/v1")
        ),
    )


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionCurrentness:
    """Opaque monotonic composite head that the authority registers and rechecks."""

    _state: AcquisitionState
    _projection: AcquisitionVenueProjection
    _predecessor_head: bytes | None
    _seal: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionCurrentness is reducer-minted only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionCurrentness cannot be subclassed")

    @property
    def binding(self) -> DualMandateBinding:
        return self._projection.binding

    @property
    def position_scope(self) -> PositionScope:
        return self._projection.position_scope

    @property
    def session_id(self) -> SessionId:
        return self._state.mandate.session_id

    @property
    def head(self) -> bytes:
        return self._seal

    @property
    def predecessor_head(self) -> bytes | None:
        """Return the one authentic prior composite head, if any."""

        return self._predecessor_head

    @property
    def execution_commitment(self) -> bytes:
        return self._projection.execution_commitment

    @property
    def venue_commitment(self) -> bytes:
        return self._projection.venue_commitment

    @property
    def protection_commitment(self) -> bytes:
        return _protection_state_commitment(
            self._state.mandate,
            self._state._protection_state,
        )

    @property
    def source_effect_id(self) -> EffectId | None:
        return self._projection.source_effect_id

    @property
    def is_authentic(self) -> bool:
        return _currentness_is_authentic(self)


def _currentness_is_authentic(currentness: AcquisitionCurrentness) -> bool:
    if type(currentness) is not AcquisitionCurrentness:
        return False
    if not _state_is_authentic(currentness._state):
        return False
    if (
        type(currentness._projection) is not AcquisitionVenueProjection
        or not currentness._projection.is_authentic
    ):
        return False
    if currentness._predecessor_head is not None and (
        type(currentness._predecessor_head) is not bytes
        or len(currentness._predecessor_head) != 32
    ):
        return False
    if type(currentness._seal) is not bytes or len(currentness._seal) != 32:
        return False
    if currentness._state.mandate.binding != currentness._projection.binding:
        return False
    if currentness._state._projection != currentness._projection:
        return False
    if (
        currentness._state._predecessor_currentness_head
        != currentness._predecessor_head
    ):
        return False
    return currentness._seal == _currentness_seal(currentness._state)


def _new_currentness(
    state: AcquisitionState,
) -> AcquisitionCurrentness:
    result = object.__new__(AcquisitionCurrentness)
    object.__setattr__(result, "_state", state)
    object.__setattr__(result, "_projection", state._projection)
    object.__setattr__(
        result,
        "_predecessor_head",
        state._predecessor_currentness_head,
    )
    object.__setattr__(result, "_seal", _currentness_seal(state))
    if not result.is_authentic:
        raise ValueError("acquisition currentness is not exact")
    return result


def _authorization_seal(
    currentness: AcquisitionCurrentness,
    terms: AcquisitionEffectTerms,
) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-authorization/v1",
        currentness.head,
        terms.commitment,
    )


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionAuthorization:
    """Opaque term-bound BUY capability minted only by the composite reducer."""

    _currentness: AcquisitionCurrentness
    _terms: AcquisitionEffectTerms
    _seal: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionAuthorization is reducer-minted only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionAuthorization cannot be subclassed")

    @property
    def currentness(self) -> AcquisitionCurrentness:
        return self._currentness

    @property
    def terms(self) -> AcquisitionEffectTerms:
        return self._terms

    @property
    def binding(self) -> DualMandateBinding:
        return self._currentness.binding

    @property
    def is_authentic(self) -> bool:
        return (
            _currentness_is_authentic(self._currentness)
            and type(self._terms) is AcquisitionEffectTerms
            and self._seal == _authorization_seal(self._currentness, self._terms)
        )


@dataclass(frozen=True, slots=True, init=False)
class ProtectionExitProjection:
    """Opaque current protection-owned preemption capability."""

    _currentness: AcquisitionCurrentness
    _protection_state: PositionProtectionState
    _goal: ExecutionGoal | None
    _seal: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("ProtectionExitProjection is composite-reducer minted only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("ProtectionExitProjection cannot be subclassed")

    @property
    def currentness(self) -> AcquisitionCurrentness:
        """Return the exact composite head that this capability binds."""

        return self._currentness

    @property
    def binding(self) -> DualMandateBinding:
        """Return the distinct immutable authority pair for this one scope."""

        return self._currentness.binding

    @property
    def position_scope(self) -> PositionScope:
        """Return the exact scope governed by the sealed exit capability."""

        return self._currentness.position_scope

    @property
    def commitment(self) -> bytes:
        """Return a sealed exit-terms commitment, not a caller-mintable capability."""

        return self._seal

    @property
    def residual(self) -> Quantity | None:
        """Return the sealed SELL residual, or ``None`` while BUY resolution waits."""

        return None if self._goal is None else self._goal.residual

    @property
    def deadline(self) -> int | None:
        """Return the sealed deadline without exposing the underlying M1D goal."""

        return None if self._goal is None else self._goal.deadline

    @property
    def is_authentic(self) -> bool:
        return _exit_projection_is_authentic(self)


def _exit_projection_seal(
    currentness: AcquisitionCurrentness,
    protection_state: PositionProtectionState,
    goal: ExecutionGoal | None,
) -> bytes:
    """Commit reducer-owned exit state without exposing raw M1D authority."""

    if goal is None:
        goal_commitment = _commit_parts(b"execution-core/acquisition-exit/waiting/v1")
    else:
        goal_commitment = _commit_parts(
            b"execution-core/acquisition-exit-goal/v1",
            _encode_text(goal.side.value),
            _encode_int(goal.residual.value),
            _encode_text(goal.urgency.value),
            _encode_text(goal.guard.guard_id),
            goal.guard.policy_commitment,
            _encode_int(goal.deadline),
            _encode_text(goal.session_id.value),
            _encode_text(goal.mandate_id.value),
            _encode_int(goal.maximum_goal_rate),
            goal.execution_commitment,
            goal.protection_commitment,
        )
    return _commit_parts(
        b"execution-core/acquisition-protection-exit/v1",
        currentness.head,
        protection_state.commitment,
        goal_commitment,
    )


def _exit_projection_is_authentic(projection: ProtectionExitProjection) -> bool:
    """Validate the one reducer-minted preemption capability structurally."""

    if type(projection) is not ProtectionExitProjection:
        return False
    if not _currentness_is_authentic(projection._currentness):
        return False
    if type(projection._protection_state) is not PositionProtectionState:
        return False
    if projection._currentness._state._protection_state != projection._protection_state:
        return False
    if projection._protection_state.mandate != (
        projection._currentness._state.mandate.protection_mandate
    ):
        return False
    goal = projection._goal
    if goal is not None:
        if type(goal) is not ExecutionGoal:
            return False
        if (
            goal.execution_commitment != projection._currentness.execution_commitment
            or goal.protection_commitment != projection._protection_state.commitment
            or goal.session_id != projection._currentness.session_id
            or goal.mandate_id
            != projection._currentness._state.mandate.protection_mandate.mandate_id
        ):
            return False
    return (
        type(projection._seal) is bytes
        and len(projection._seal) == 32
        and projection._seal
        == _exit_projection_seal(
            projection._currentness,
            projection._protection_state,
            goal,
        )
    )


def _new_exit_projection(
    currentness: AcquisitionCurrentness,
    protection_state: PositionProtectionState,
    goal: ExecutionGoal | None,
) -> ProtectionExitProjection:
    """Mint the only admissible preemption capability for one successor head."""

    result = object.__new__(ProtectionExitProjection)
    object.__setattr__(result, "_currentness", currentness)
    object.__setattr__(result, "_protection_state", protection_state)
    object.__setattr__(result, "_goal", goal)
    object.__setattr__(
        result,
        "_seal",
        _exit_projection_seal(currentness, protection_state, goal),
    )
    if not result.is_authentic:
        raise ValueError("protection exit projection is not exact")
    return result


def _protection_exit_requires_preemption(
    state: PositionProtectionState | None,
) -> bool:
    """Identify an M1D exit/wait state without promoting its urgency or goal."""

    return bool(
        state is not None
        and state.raw_quantity > 0
        and state.policy in {ProtectionPolicy.EXIT_NORMAL, ProtectionPolicy.HARD_BAIL}
    )


def _lifecycle_after_preemption(
    lifecycle: _AcquisitionLifecycle,
    preempted: bool,
) -> _AcquisitionLifecycle:
    """Latch only active acquisition work into its one-way cancellation phase."""

    if preempted and lifecycle is _AcquisitionLifecycle.WORKING:
        return _AcquisitionLifecycle.CANCELING
    return lifecycle


def _lifecycle_after_integration(
    lifecycle: _AcquisitionLifecycle,
    owned_quantity: int,
    preempted: bool,
) -> _AcquisitionLifecycle:
    """Advance READY only on actual owned exposure, then apply a legal preemption latch."""

    next_lifecycle = (
        _AcquisitionLifecycle.WORKING
        if lifecycle is _AcquisitionLifecycle.READY and owned_quantity > 0
        else lifecycle
    )
    return _lifecycle_after_preemption(next_lifecycle, preempted)


@dataclass(frozen=True, slots=True)
class AcquisitionTransition:
    """Exact public composite acquisition/protection transition result."""

    state: AcquisitionState
    protection_state: PositionProtectionState | None
    protection_alert: ProtectionAlert | None
    currentness: AcquisitionCurrentness
    authorization: AcquisitionAuthorization | None
    exit_projection: ProtectionExitProjection | None
    disposition: AcquisitionDisposition

    def __post_init__(self) -> None:
        _require("state", self.state, AcquisitionState)
        if self.protection_state is not None:
            _require("protection_state", self.protection_state, PositionProtectionState)
        if self.protection_alert is not None:
            _require("protection_alert", self.protection_alert, ProtectionAlert)
        _require("currentness", self.currentness, AcquisitionCurrentness)
        if self.authorization is not None:
            _require("authorization", self.authorization, AcquisitionAuthorization)
        if self.exit_projection is not None:
            _require("exit_projection", self.exit_projection, ProtectionExitProjection)
        _require("disposition", self.disposition, AcquisitionDisposition)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionTransition is exact and cannot be subclassed")


def _require_projection(value: object) -> AcquisitionVenueProjection:
    _require("venue_projection", value, AcquisitionVenueProjection)
    projection = value
    if not projection.is_authentic:
        raise ValueError("venue_projection is not authentic")
    return projection


def _transition(
    state: AcquisitionState,
    disposition: AcquisitionDisposition,
    *,
    authorization: AcquisitionAuthorization | None = None,
    protection_alert: ProtectionAlert | None = None,
    exit_goal: ExecutionGoal | None = None,
    mint_exit: bool = False,
) -> AcquisitionTransition:
    currentness = _new_currentness(state)
    exit_projection = (
        _new_exit_projection(currentness, state._protection_state, exit_goal)
        if mint_exit and state._protection_state is not None
        else None
    )
    return AcquisitionTransition(
        state=state,
        protection_state=state._protection_state,
        protection_alert=protection_alert,
        currentness=currentness,
        authorization=authorization,
        exit_projection=exit_projection,
        disposition=disposition,
    )


def initialize_acquisition(
    mandate: AcquisitionMandate,
    venue_projection: AcquisitionVenueProjection,
) -> AcquisitionTransition:
    """Create the bounded READY state from one exact bound venue projection."""

    _require("mandate", mandate, AcquisitionMandate)
    projection = _require_projection(venue_projection)
    if projection.position_scope != mandate.position_scope:
        raise ValueError("venue projection position scope must match mandate")
    if projection.binding != mandate.binding:
        raise ValueError("venue projection binding must match complete mandate")
    state = _new_state(
        mandate,
        _AcquisitionLifecycle.READY,
        0,
        Fraction(0),
        False,
        projection,
        None,
        None,
    )
    return _transition(state, AcquisitionDisposition.APPLIED)


def apply_acquisition_integration(
    state: AcquisitionState,
    transition: VenueRecoveryTransition,
) -> AcquisitionTransition:
    """Advance both acquisition and protection from one exact venue transition."""

    _require("state", state, AcquisitionState)
    if not _state_is_authentic(state):
        raise ValueError("state is not authentic")
    _require("transition", transition, VenueRecoveryTransition)
    if transition.disposition not in {
        VenueRecoveryDisposition.APPLIED,
        VenueRecoveryDisposition.EXACT_REPLAY,
    }:
        return _transition(state, AcquisitionDisposition.REFUSED)
    projection = project_acquisition_venue(transition, state.mandate.binding)
    protection_projection = project_protection_venue(
        transition,
        state.mandate.protection_mandate,
    )
    if (
        projection.position_scope != state.mandate.position_scope
        or projection.binding != state.mandate.binding
    ):
        raise ValueError("venue projection does not match acquisition state")
    if projection.head == state._projection_head:
        return _transition(
            state,
            AcquisitionDisposition.EXACT_REPLAY,
        )
    if transition.disposition is not VenueRecoveryDisposition.APPLIED:
        return _transition(state, AcquisitionDisposition.REFUSED)
    next_owned_quantity = state._owned_quantity + projection.owned_quantity_delta
    next_owned_notional = state._owned_notional + projection.owned_notional_delta
    if (
        next_owned_quantity < 0
        or next_owned_notional < 0
        or (next_owned_quantity == 0 and next_owned_notional != 0)
        or (next_owned_quantity > 0 and next_owned_notional <= 0)
    ):
        return _transition(state, AcquisitionDisposition.REFUSED)
    protection_state = state._protection_state
    protection_alert: ProtectionAlert | None = None
    exit_goal: ExecutionGoal | None = None
    has_owned_buy_exposure = next_owned_quantity > 0
    if protection_state is None:
        next_protection_state = (
            initialize_position_protection(
                state.mandate.protection_mandate,
                protection_projection,
            )
            if has_owned_buy_exposure
            else None
        )
    else:
        protection_transition = reduce_position_protection(
            protection_state,
            protection_projection,
        )
        if protection_transition.disposition not in {
            ProtectionDisposition.APPLIED,
            ProtectionDisposition.EXACT_REPLAY,
        }:
            return _transition(state, AcquisitionDisposition.REFUSED)
        next_protection_state = protection_transition.state
        protection_alert = protection_transition.critical_alert
        exit_goal = protection_transition.goal
    predecessor_head = _new_currentness(state).head
    preempted = state._preempted or _protection_exit_requires_preemption(
        next_protection_state,
    )
    next_state = _new_state(
        state.mandate,
        _lifecycle_after_integration(
            state._lifecycle,
            next_owned_quantity,
            preempted,
        ),
        next_owned_quantity,
        next_owned_notional,
        preempted,
        projection,
        next_protection_state,
        predecessor_head,
    )
    return _transition(
        next_state,
        AcquisitionDisposition.APPLIED,
        protection_alert=protection_alert,
        exit_goal=exit_goal,
        mint_exit=_protection_exit_requires_preemption(next_protection_state),
    )


def reduce_acquisition_market(
    state: AcquisitionState,
    transition: VenueRecoveryTransition,
    occurrence: MarketOccurrence,
) -> AcquisitionTransition:
    """Advance M1D market state only from the exact sealed current venue head."""

    _require("state", state, AcquisitionState)
    _require("transition", transition, VenueRecoveryTransition)
    _require("occurrence", occurrence, MarketOccurrence)
    if not _state_is_authentic(state):
        raise ValueError("state is not authentic")
    if transition.disposition not in {
        VenueRecoveryDisposition.APPLIED,
        VenueRecoveryDisposition.EXACT_REPLAY,
    }:
        return _transition(state, AcquisitionDisposition.REFUSED)
    projection = project_acquisition_venue(transition, state.mandate.binding)
    if projection != state._projection:
        return _transition(state, AcquisitionDisposition.REFUSED)
    if state._protection_state is None:
        return _transition(state, AcquisitionDisposition.REFUSED)
    protection_projection = project_protection_venue(
        transition,
        state.mandate.protection_mandate,
    )
    protection_transition = reduce_position_protection_market(
        state._protection_state,
        protection_projection,
        occurrence,
    )
    if protection_transition.disposition is ProtectionDisposition.EXACT_REPLAY:
        return _transition(state, AcquisitionDisposition.EXACT_REPLAY)
    if protection_transition.disposition is not ProtectionDisposition.APPLIED:
        return _transition(state, AcquisitionDisposition.REFUSED)
    preempted = state._preempted or _protection_exit_requires_preemption(
        protection_transition.state,
    )
    next_state = _new_state(
        state.mandate,
        _lifecycle_after_preemption(state._lifecycle, preempted),
        state._owned_quantity,
        state._owned_notional,
        preempted,
        projection,
        protection_transition.state,
        _new_currentness(state).head,
    )
    return _transition(
        next_state,
        AcquisitionDisposition.APPLIED,
        protection_alert=protection_transition.critical_alert,
        exit_goal=protection_transition.goal,
        mint_exit=_protection_exit_requires_preemption(protection_transition.state),
    )


def authorize_acquisition_effect(
    currentness: AcquisitionCurrentness,
    terms: AcquisitionEffectTerms,
) -> AcquisitionAuthorization:
    """Mint a term-bound sealed BUY capability only inside immutable ceilings."""

    _require("currentness", currentness, AcquisitionCurrentness)
    _require("terms", terms, AcquisitionEffectTerms)
    if not currentness.is_authentic:
        raise ValueError("currentness is not authentic")
    state = currentness._state
    mandate = state.mandate
    if (
        state._lifecycle
        in {
            _AcquisitionLifecycle.CANCELING,
            _AcquisitionLifecycle.OUTCOME_UNKNOWN,
            _AcquisitionLifecycle.COMPLETED,
            _AcquisitionLifecycle.ABORTED,
        }
        or state._preempted
    ):
        raise ValueError("acquisition lifecycle does not permit a new BUY effect")
    if terms.order_type not in mandate.allowed_order_types:
        raise ValueError("order type is not allowed by the acquisition mandate")
    if not terms.limit_price.is_compatible_with(mandate.maximum_entry_price):
        raise ValueError("limit price metadata does not match the mandate")
    if terms.limit_price.exact_value > mandate.maximum_entry_price.exact_value:
        raise ValueError("limit price exceeds the acquisition mandate")
    if terms.quantity.value > mandate.fixed_child_cap.value:
        raise ValueError("quantity exceeds fixed child capacity")
    if state._owned_quantity + terms.quantity.value > mandate.maximum_quantity.value:
        raise ValueError("quantity exceeds acquisition capacity")
    if (
        state._owned_notional + terms.quantity.value * terms.limit_price.exact_value
        > mandate.maximum_notional
    ):
        raise ValueError("notional exceeds acquisition capacity")
    if (
        terms.evaluation_time > mandate.expiry
        or terms.evaluation_time > mandate.deadline
    ):
        raise ValueError("evaluation time exceeds acquisition authority")
    result = object.__new__(AcquisitionAuthorization)
    object.__setattr__(result, "_currentness", currentness)
    object.__setattr__(result, "_terms", terms)
    object.__setattr__(result, "_seal", _authorization_seal(currentness, terms))
    if not result.is_authentic:
        raise ValueError("acquisition authorization is not exact")
    return result


__all__ = [
    "AcquisitionAuthorization",
    "AcquisitionCurrentness",
    "AcquisitionDisposition",
    "AcquisitionEffectTerms",
    "AcquisitionMandate",
    "AcquisitionOrderType",
    "AcquisitionState",
    "AcquisitionTransition",
    "ProtectionExitProjection",
    "apply_acquisition_integration",
    "authorize_acquisition_effect",
    "initialize_acquisition",
    "reduce_acquisition_market",
]
