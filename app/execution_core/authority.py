"""Pure deny-by-default execution authority for the reset kernel.

This module decides whether one exact broker effect or query may be created or
finally claimed.  It owns no clock, persistence, credentials, broker adapter,
or runtime wiring; later milestones must hydrate its environmental fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from typing import TypeVar, cast

from .fills import ExecutionSide, PositionScope, _PersistentKeyMap, _commit_parts
from .identity import (
    AccountId,
    ActorId,
    AuthorityInputId,
    ClaimOccurrenceId,
    ClientOrderId,
    EffectId,
    EmergencyGrantId,
    EvidenceReference,
    MandateId,
    ManualFlattenId,
    QueryClaimId,
    RequestOccurrenceId,
    SessionId,
    SymbolId,
    VenueInputId,
    VenueLegKey,
)
from .position import ExecutionSnapshot
from .values import Quantity
from .venue import (
    AcceptanceSetState,
    EffectKind,
    RequestedEffect,
    RecordDispatchClaim,
    VenueEffectScope,
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    VenueRecoveryTransition,
    VenueScope,
    _authority_begin_symbol_flatten,
    _authority_claim_effect,
    _authority_effect_identity_conflicts,
    _authority_request_effect,
    _authority_stand_down_account_requested_effects,
    _authority_stand_down_requested_effect,
    _authority_symbol_flatten_ready,
    _venue_authority_view,
)


class EnginePhase(str, Enum):
    BOOTSTRAPPING = "BOOTSTRAPPING"
    RECONCILING = "RECONCILING"
    SERVING = "SERVING"


class TradingMode(str, Enum):
    ACTIVE = "ACTIVE"
    REDUCING = "REDUCING"
    HALTED = "HALTED"


class SupervisorFence(str, Enum):
    UNAUTHENTICATED = "UNAUTHENTICATED"
    RECONCILIATION_ONLY = "RECONCILIATION_ONLY"
    PAPER_MUTATION_ELIGIBLE = "PAPER_MUTATION_ELIGIBLE"


class AuthorityQueryKind(str, Enum):
    QUERY = "QUERY"
    RECONCILE = "RECONCILE"


class AuthorityDisposition(str, Enum):
    APPLIED = "APPLIED"
    REFUSED = "REFUSED"
    EXACT_REPLAY = "EXACT_REPLAY"
    CONFLICT = "CONFLICT"


class AuthorityReason(str, Enum):
    PHASE_BLOCKED = "PHASE_BLOCKED"
    MODE_BLOCKED = "MODE_BLOCKED"
    SUPERVISOR_FENCE_BLOCKED = "SUPERVISOR_FENCE_BLOCKED"
    KILL_ENGAGED = "KILL_ENGAGED"
    SAFETY_RESERVE_PROTECTED = "SAFETY_RESERVE_PROTECTED"
    REQUEST_BUDGET_EXHAUSTED = "REQUEST_BUDGET_EXHAUSTED"
    SESSION_MISMATCH = "SESSION_MISMATCH"
    EXECUTION_BINDING_MISMATCH = "EXECUTION_BINDING_MISMATCH"
    ACCOUNT_RECONCILIATION_REQUIRED = "ACCOUNT_RECONCILIATION_REQUIRED"
    VENUE_UNCERTAIN = "VENUE_UNCERTAIN"
    RESIDUAL_EXCEEDED = "RESIDUAL_EXCEEDED"
    NATIVE_REPLACE_DISABLED = "NATIVE_REPLACE_DISABLED"
    EMERGENCY_GRANT_REQUIRED = "EMERGENCY_GRANT_REQUIRED"
    EMERGENCY_GRANT_MISMATCH = "EMERGENCY_GRANT_MISMATCH"
    EMERGENCY_GRANT_REDUCE_ONLY = "EMERGENCY_GRANT_REDUCE_ONLY"
    EFFECT_UNKNOWN = "EFFECT_UNKNOWN"
    MANUAL_FLATTEN_INVALID = "MANUAL_FLATTEN_INVALID"


def _require(name: str, value: object, expected: type[object]) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must be the exact {expected.__name__} type")


def _require_optional(name: str, value: object, expected: type[object]) -> None:
    if value is not None and type(value) is not expected:
        raise TypeError(f"{name} must be {expected.__name__} or None")


def _require_text(name: str, value: object) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must be nonblank")


@dataclass(frozen=True, slots=True)
class RequestBudget:
    remaining: int
    safety_reserve: int

    def __post_init__(self) -> None:
        for name in ("remaining", "safety_reserve"):
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError(f"{name} must be an exact integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True, slots=True)
class BrokerEffectRequest:
    effect_id: EffectId
    request_occurrence_id: RequestOccurrenceId
    mandate_id: MandateId
    kind: EffectKind
    client_order_id: ClientOrderId | None
    symbol_id: SymbolId
    side: ExecutionSide
    quantity: Quantity
    economic_scope: bytes
    target_leg_key: VenueLegKey | None

    def __post_init__(self) -> None:
        for name, expected in (
            ("effect_id", EffectId),
            ("request_occurrence_id", RequestOccurrenceId),
            ("mandate_id", MandateId),
            ("kind", EffectKind),
            ("symbol_id", SymbolId),
            ("side", ExecutionSide),
            ("quantity", Quantity),
        ):
            _require(name, getattr(self, name), expected)
        _require_optional("client_order_id", self.client_order_id, ClientOrderId)
        _require_optional("target_leg_key", self.target_leg_key, VenueLegKey)
        if self.quantity.value <= 0:
            raise ValueError("quantity must be positive")
        if type(self.economic_scope) is not bytes:
            raise TypeError("economic_scope must be bytes")
        if not self.economic_scope:
            raise ValueError("economic_scope must be nonempty")
        if self.kind is EffectKind.SUBMIT:
            if self.client_order_id is None:
                raise ValueError("SUBMIT requires a client_order_id")
            if self.target_leg_key is not None:
                raise ValueError("SUBMIT cannot target a venue leg")
        elif self.kind is EffectKind.CANCEL:
            if self.client_order_id is not None:
                raise ValueError("CANCEL cannot carry a client_order_id")
            if self.target_leg_key is None:
                raise ValueError("CANCEL requires a target_leg_key")
        elif self.kind is EffectKind.REPLACE:
            if self.client_order_id is None:
                raise ValueError("REPLACE requires a client_order_id")
            if self.target_leg_key is None:
                raise ValueError("REPLACE requires a target_leg_key")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("BrokerEffectRequest is exact and cannot be subclassed")


@dataclass(frozen=True, slots=True)
class CreateBrokerEffect:
    input_id: AuthorityInputId
    session_id: SessionId
    request: BrokerEffectRequest
    manual_flatten_id: ManualFlattenId | None
    emergency_grant_id: EmergencyGrantId | None

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, AuthorityInputId)
        _require("session_id", self.session_id, SessionId)
        _require("request", self.request, BrokerEffectRequest)
        _require_optional("manual_flatten_id", self.manual_flatten_id, ManualFlattenId)
        _require_optional(
            "emergency_grant_id", self.emergency_grant_id, EmergencyGrantId
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("CreateBrokerEffect is exact and cannot be subclassed")


@dataclass(frozen=True, slots=True)
class ClaimEffect:
    input_id: AuthorityInputId
    effect_id: EffectId
    claim_occurrence_id: ClaimOccurrenceId

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, AuthorityInputId)
        _require("effect_id", self.effect_id, EffectId)
        _require("claim_occurrence_id", self.claim_occurrence_id, ClaimOccurrenceId)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("ClaimEffect is exact and cannot be subclassed")


@dataclass(frozen=True, slots=True)
class ClaimBrokerQuery:
    input_id: AuthorityInputId
    query_claim_id: QueryClaimId
    symbol_id: SymbolId
    kind: AuthorityQueryKind

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, AuthorityInputId)
        _require("query_claim_id", self.query_claim_id, QueryClaimId)
        _require("symbol_id", self.symbol_id, SymbolId)
        _require("kind", self.kind, AuthorityQueryKind)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("ClaimBrokerQuery is exact and cannot be subclassed")


@dataclass(frozen=True, slots=True)
class EngageKill:
    input_id: AuthorityInputId
    actor: ActorId
    reason: str
    evidence_reference: EvidenceReference

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, AuthorityInputId)
        _require("actor", self.actor, ActorId)
        _require_text("reason", self.reason)
        _require("evidence_reference", self.evidence_reference, EvidenceReference)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("EngageKill is exact and cannot be subclassed")


@dataclass(frozen=True, slots=True)
class BeginManualFlatten:
    input_id: AuthorityInputId
    flatten_id: ManualFlattenId
    session_id: SessionId
    symbol_id: SymbolId
    actor: ActorId
    reason: str
    evidence_reference: EvidenceReference
    emergency_grant_id: EmergencyGrantId | None

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, AuthorityInputId)
        _require("flatten_id", self.flatten_id, ManualFlattenId)
        _require("session_id", self.session_id, SessionId)
        _require("symbol_id", self.symbol_id, SymbolId)
        _require("actor", self.actor, ActorId)
        _require_text("reason", self.reason)
        _require("evidence_reference", self.evidence_reference, EvidenceReference)
        _require_optional(
            "emergency_grant_id", self.emergency_grant_id, EmergencyGrantId
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("BeginManualFlatten is exact and cannot be subclassed")


@dataclass(frozen=True, slots=True)
class AdvanceManualFlatten:
    input_id: AuthorityInputId
    flatten_id: ManualFlattenId

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, AuthorityInputId)
        _require("flatten_id", self.flatten_id, ManualFlattenId)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AdvanceManualFlatten is exact and cannot be subclassed")


_AuthorityCommand = (
    CreateBrokerEffect
    | ClaimEffect
    | ClaimBrokerQuery
    | EngageKill
    | BeginManualFlatten
    | AdvanceManualFlatten
)


@dataclass(frozen=True, slots=True)
class _EmergencyGrant:
    grant_id: EmergencyGrantId
    account: AccountId
    symbol_id: SymbolId
    session_id: SessionId
    actor: ActorId
    reason: str
    evidence_reference: EvidenceReference

    def __post_init__(self) -> None:
        for name, expected in (
            ("grant_id", EmergencyGrantId),
            ("account", AccountId),
            ("symbol_id", SymbolId),
            ("session_id", SessionId),
            ("actor", ActorId),
            ("evidence_reference", EvidenceReference),
        ):
            _require(name, getattr(self, name), expected)
        _require_text("reason", self.reason)


@dataclass(frozen=True, slots=True)
class _EffectAuthorization:
    request: BrokerEffectRequest
    session_id: SessionId
    manual_flatten_id: ManualFlattenId | None
    emergency_grant_id: EmergencyGrantId | None


class _FlattenPhase(str, Enum):
    WAITING = "WAITING"
    READY = "READY"
    SELL_CREATED = "SELL_CREATED"


@dataclass(frozen=True, slots=True)
class _ManualFlatten:
    command: BeginManualFlatten
    phase: _FlattenPhase
    cancel_effect_ids: tuple[EffectId, ...]
    sell_effect_id: EffectId | None = None


@dataclass(frozen=True, slots=True)
class _FreshEffectClaim:
    effect_id: EffectId
    effect_scope: VenueEffectScope
    claim_occurrence_id: ClaimOccurrenceId


@dataclass(frozen=True, slots=True)
class _FreshQueryClaim:
    query_claim_id: QueryClaimId
    symbol_id: SymbolId
    kind: AuthorityQueryKind


def _index_key(domain: bytes, value: str) -> bytes:
    return _commit_parts(
        b"execution-core/authority-index-key/v1",
        domain,
        value.encode("utf-8"),
    )


def _input_key(value: AuthorityInputId) -> bytes:
    return _index_key(b"input", value.value)


def _effect_key(value: EffectId) -> bytes:
    return _index_key(b"effect", value.value)


def _claim_key(value: ClaimOccurrenceId) -> bytes:
    return _index_key(b"claim", value.value)


def _query_key(value: QueryClaimId) -> bytes:
    return _index_key(b"query", value.value)


def _manual_key(value: ManualFlattenId) -> bytes:
    return _index_key(b"manual", value.value)


def _grant_key(value: EmergencyGrantId) -> bytes:
    return _index_key(b"grant", value.value)


@dataclass(frozen=True, slots=True, init=False)
class ExecutionAuthorityState:
    phase: EnginePhase
    mode: TradingMode
    supervisor_fence: SupervisorFence
    kill_engaged: bool
    session_id: SessionId | None
    budget: RequestBudget
    venue: VenueRecoveryBook
    _input_by_id: _PersistentKeyMap[object] = field(repr=False)
    _effect_authority_by_id: _PersistentKeyMap[_EffectAuthorization] = field(repr=False)
    _claim_by_effect: _PersistentKeyMap[ClaimEffect] = field(repr=False)
    _claim_by_occurrence: _PersistentKeyMap[ClaimEffect] = field(repr=False)
    _query_by_id: _PersistentKeyMap[ClaimBrokerQuery] = field(repr=False)
    _manual_by_id: _PersistentKeyMap[_ManualFlatten] = field(repr=False)
    _consumed_grant_ids: _PersistentKeyMap[bool] = field(repr=False)
    _emergency_grant: _EmergencyGrant | None = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("ExecutionAuthorityState is opaque; use deny-only genesis")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("ExecutionAuthorityState is opaque and cannot be subclassed")

    def _grant_consumed(self, grant_id: EmergencyGrantId) -> bool:
        _require("grant_id", grant_id, EmergencyGrantId)
        return self._consumed_grant_ids.get(_grant_key(grant_id)) is True


_AUTHORITY_STATE_INDEX_FIELDS = (
    "_input_by_id",
    "_effect_authority_by_id",
    "_claim_by_effect",
    "_claim_by_occurrence",
    "_query_by_id",
    "_manual_by_id",
    "_consumed_grant_ids",
)


def _validate_authority_state(state: object) -> ExecutionAuthorityState:
    """Validate constant-work state shape before any authority decision."""

    _require("state", state, ExecutionAuthorityState)
    exact = cast(ExecutionAuthorityState, state)
    for name, expected in (
        ("phase", EnginePhase),
        ("mode", TradingMode),
        ("supervisor_fence", SupervisorFence),
        ("budget", RequestBudget),
        ("venue", VenueRecoveryBook),
    ):
        _require(name, getattr(exact, name), expected)
    if type(exact.kill_engaged) is not bool:
        raise TypeError("kill_engaged must be the exact bool type")
    _require_optional("session_id", exact.session_id, SessionId)
    for name in ("remaining", "safety_reserve"):
        value = getattr(exact.budget, name)
        if type(value) is not int:
            raise TypeError(f"budget.{name} must be the exact int type")
        if value < 0:
            raise ValueError(f"budget.{name} must be non-negative")
    for name in _AUTHORITY_STATE_INDEX_FIELDS:
        _require(name, getattr(exact, name), _PersistentKeyMap)
    _require_optional("_emergency_grant", exact._emergency_grant, _EmergencyGrant)
    return exact


@dataclass(frozen=True, slots=True)
class ExecutionAuthorityTransition:
    state: ExecutionAuthorityState
    disposition: AuthorityDisposition
    reason: AuthorityReason | None
    created_effect_ids: tuple[EffectId, ...]
    fresh_claim: _FreshEffectClaim | _FreshQueryClaim | None
    venue_transitions: tuple[VenueRecoveryTransition, ...]


def _new_state(**values: object) -> ExecutionAuthorityState:
    result = object.__new__(ExecutionAuthorityState)
    for item in fields(ExecutionAuthorityState):
        object.__setattr__(result, item.name, values[item.name])
    return _validate_authority_state(result)


def _state_with(
    state: ExecutionAuthorityState, **changes: object
) -> ExecutionAuthorityState:
    values = {item.name: getattr(state, item.name) for item in fields(state)}
    values.update(changes)
    return _new_state(**values)


_Value = TypeVar("_Value")


def _value_commitment(value: object) -> bytes:
    return _commit_parts(
        b"execution-core/authority-index-value/v1",
        repr(value).encode("utf-8"),
    )


def _inserted(
    retained: _PersistentKeyMap[_Value], key: bytes, value: _Value
) -> _PersistentKeyMap[_Value]:
    return retained.insert_new(key, value, _value_commitment(value))


def _replaced(
    retained: _PersistentKeyMap[_Value], key: bytes, value: _Value
) -> _PersistentKeyMap[_Value]:
    return retained.replace_existing(key, value, _value_commitment(value))


def initial_execution_authority_state(scope: VenueScope) -> ExecutionAuthorityState:
    _require("scope", scope, VenueScope)
    return _new_state(
        phase=EnginePhase.BOOTSTRAPPING,
        mode=TradingMode.HALTED,
        supervisor_fence=SupervisorFence.UNAUTHENTICATED,
        kill_engaged=True,
        session_id=None,
        budget=RequestBudget(remaining=0, safety_reserve=0),
        venue=VenueRecoveryBook.empty(scope),
        _input_by_id=_PersistentKeyMap.empty(),
        _effect_authority_by_id=_PersistentKeyMap.empty(),
        _claim_by_effect=_PersistentKeyMap.empty(),
        _claim_by_occurrence=_PersistentKeyMap.empty(),
        _query_by_id=_PersistentKeyMap.empty(),
        _manual_by_id=_PersistentKeyMap.empty(),
        _consumed_grant_ids=_PersistentKeyMap.empty(),
        _emergency_grant=None,
    )


def _result(
    state: ExecutionAuthorityState,
    disposition: AuthorityDisposition,
    reason: AuthorityReason | None = None,
    *,
    created: tuple[EffectId, ...] = (),
    claim: _FreshEffectClaim | _FreshQueryClaim | None = None,
    venue_transitions: tuple[VenueRecoveryTransition, ...] = (),
) -> ExecutionAuthorityTransition:
    return ExecutionAuthorityTransition(
        state,
        disposition,
        reason,
        created,
        claim,
        venue_transitions,
    )


def _record_input(
    state: ExecutionAuthorityState, item: _AuthorityCommand
) -> ExecutionAuthorityState:
    return _state_with(
        state,
        _input_by_id=_inserted(state._input_by_id, _input_key(item.input_id), item),
    )


def _position_scope(
    state: ExecutionAuthorityState, symbol_id: SymbolId
) -> PositionScope:
    scope = state.venue.scope
    return PositionScope(
        broker=scope.broker,
        environment=scope.environment,
        account=scope.account,
        symbol_id=symbol_id,
    )


def _execution_scope_matches(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    symbol_id: SymbolId,
) -> bool:
    return execution.position.scope == _position_scope(state, symbol_id)


def _venue_input_id(input_id: AuthorityInputId, suffix: str) -> VenueInputId:
    return VenueInputId(f"authority:{input_id.value}:{suffix}")


def _venue_request(item: CreateBrokerEffect) -> RequestedEffect:
    request = item.request
    return RequestedEffect(
        input_id=_venue_input_id(item.input_id, "request"),
        effect_id=request.effect_id,
        request_occurrence_id=request.request_occurrence_id,
        mandate_id=request.mandate_id,
        kind=request.kind,
        client_order_id=request.client_order_id,
        symbol_id=request.symbol_id,
        side=request.side,
        quantity=request.quantity,
        economic_scope=request.economic_scope,
        target_leg_key=request.target_leg_key,
    )


def _scope_from_request(
    state: ExecutionAuthorityState, request: BrokerEffectRequest
) -> VenueEffectScope:
    scope = state.venue.scope
    return VenueEffectScope(
        generation=scope.generation,
        broker=scope.broker,
        environment=scope.environment,
        account=scope.account,
        effect_id=request.effect_id,
        request_occurrence_id=request.request_occurrence_id,
        mandate_id=request.mandate_id,
        kind=request.kind,
        client_order_id=request.client_order_id,
        symbol_id=request.symbol_id,
        side=request.side,
        quantity=request.quantity,
        economic_scope=request.economic_scope,
        target_leg_key=request.target_leg_key,
    )


def _replay_or_conflict(
    state: ExecutionAuthorityState, item: _AuthorityCommand
) -> ExecutionAuthorityTransition | None:
    retained = state._input_by_id.get(_input_key(item.input_id))
    if retained is None:
        return None
    if retained == item:
        return _result(state, AuthorityDisposition.EXACT_REPLAY)
    return _result(state, AuthorityDisposition.CONFLICT)


def _mutation_fence_reason(
    state: ExecutionAuthorityState,
) -> AuthorityReason | None:
    if state.supervisor_fence is not SupervisorFence.PAPER_MUTATION_ELIGIBLE:
        return AuthorityReason.SUPERVISOR_FENCE_BLOCKED
    if state.phase is not EnginePhase.SERVING:
        return AuthorityReason.PHASE_BLOCKED
    return None


def _normal_budget_reason(state: ExecutionAuthorityState) -> AuthorityReason | None:
    if state.budget.remaining == 0:
        return AuthorityReason.REQUEST_BUDGET_EXHAUSTED
    if state.budget.remaining <= state.budget.safety_reserve:
        return AuthorityReason.SAFETY_RESERVE_PROTECTED
    return None


def _reserved_budget_reason(state: ExecutionAuthorityState) -> AuthorityReason | None:
    if state.budget.remaining == 0:
        return AuthorityReason.REQUEST_BUDGET_EXHAUSTED
    return None


def _venue_reason(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    symbol_id: SymbolId,
    target_effect_id: EffectId | None,
    *,
    require_clear: bool,
) -> AuthorityReason | None:
    if not _execution_scope_matches(state, execution, symbol_id):
        return AuthorityReason.EXECUTION_BINDING_MISMATCH
    view = _venue_authority_view(
        state.venue,
        execution,
        _position_scope(state, symbol_id),
        target_effect_id,
    )
    if not view.account_reconciliation_clear:
        return AuthorityReason.ACCOUNT_RECONCILIATION_REQUIRED
    if not view.execution_binding_matches:
        return AuthorityReason.EXECUTION_BINDING_MISMATCH
    if require_clear and view.blocking_effect_count > view.target_exemptible_count:
        return AuthorityReason.VENUE_UNCERTAIN
    return None


def _grant_reason(
    state: ExecutionAuthorityState,
    item: CreateBrokerEffect,
) -> AuthorityReason | None:
    request = item.request
    if request.side is not ExecutionSide.SELL:
        return AuthorityReason.EMERGENCY_GRANT_REDUCE_ONLY
    if item.emergency_grant_id is None:
        return AuthorityReason.EMERGENCY_GRANT_REQUIRED
    grant = state._emergency_grant
    if grant is None or grant.grant_id != item.emergency_grant_id:
        return AuthorityReason.EMERGENCY_GRANT_MISMATCH
    if state._grant_consumed(grant.grant_id):
        return AuthorityReason.EMERGENCY_GRANT_MISMATCH
    if (
        grant.account != state.venue.scope.account
        or grant.symbol_id != request.symbol_id
        or grant.session_id != item.session_id
    ):
        return AuthorityReason.EMERGENCY_GRANT_MISMATCH
    return None


def _create_gate_reason(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: CreateBrokerEffect,
) -> AuthorityReason | None:
    request = item.request
    if item.emergency_grant_id is not None and not (
        request.kind is EffectKind.SUBMIT and request.side is ExecutionSide.SELL
    ):
        return AuthorityReason.EMERGENCY_GRANT_REDUCE_ONLY
    if request.kind is EffectKind.REPLACE:
        return AuthorityReason.NATIVE_REPLACE_DISABLED
    fence = _mutation_fence_reason(state)
    if fence is not None:
        return fence
    if item.session_id != state.session_id:
        return AuthorityReason.SESSION_MISMATCH
    if request.kind is EffectKind.CANCEL:
        return None
    emergency = (
        item.emergency_grant_id is not None or state._emergency_grant is not None
    )
    if emergency:
        grant_reason = _grant_reason(state, item)
        if grant_reason is not None:
            return grant_reason
    elif request.side is ExecutionSide.BUY:
        if state.mode is not TradingMode.ACTIVE:
            return AuthorityReason.MODE_BLOCKED
        if state.kill_engaged:
            return AuthorityReason.KILL_ENGAGED
    else:
        if state.mode not in {TradingMode.ACTIVE, TradingMode.REDUCING}:
            return AuthorityReason.MODE_BLOCKED
        if state.kill_engaged:
            return AuthorityReason.KILL_ENGAGED
    if request.side is ExecutionSide.SELL and (
        request.quantity.value > execution.position.authorized_residual_sell.value
    ):
        return AuthorityReason.RESIDUAL_EXCEEDED
    if not emergency:
        return _normal_budget_reason(state)
    return None


def _create_effect(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: CreateBrokerEffect,
) -> ExecutionAuthorityTransition:
    request = item.request
    if _authority_effect_identity_conflicts(
        state.venue,
        request.effect_id,
        request.request_occurrence_id,
        request.client_order_id,
    ):
        return _result(state, AuthorityDisposition.CONFLICT)
    if request.kind is EffectKind.REPLACE:
        return _result(
            state, AuthorityDisposition.REFUSED, AuthorityReason.NATIVE_REPLACE_DISABLED
        )
    if item.manual_flatten_id is not None:
        manual = state._manual_by_id.get(_manual_key(item.manual_flatten_id))
        if (
            manual is None
            or manual.phase is not _FlattenPhase.READY
            or manual.command.session_id != item.session_id
            or manual.command.symbol_id != request.symbol_id
            or request.kind is not EffectKind.SUBMIT
            or request.side is not ExecutionSide.SELL
            or request.quantity != execution.position.authorized_residual_sell
        ):
            return _result(
                state,
                AuthorityDisposition.REFUSED,
                AuthorityReason.MANUAL_FLATTEN_INVALID,
            )
    reason = _create_gate_reason(state, execution, item)
    if reason is not None:
        return _result(state, AuthorityDisposition.REFUSED, reason)
    if request.kind is EffectKind.CANCEL:
        view_reason = _venue_reason(
            state,
            execution,
            request.symbol_id,
            None,
            require_clear=False,
        )
    else:
        view_reason = _venue_reason(
            state,
            execution,
            request.symbol_id,
            None,
            require_clear=True,
        )
    if view_reason is not None:
        return _result(state, AuthorityDisposition.REFUSED, view_reason)
    venue_transition = _authority_request_effect(
        state.venue, execution, _venue_request(item)
    )
    if venue_transition.disposition is VenueRecoveryDisposition.CONFLICT:
        return _result(state, AuthorityDisposition.CONFLICT)
    if venue_transition.disposition is not VenueRecoveryDisposition.APPLIED:
        return _result(
            state, AuthorityDisposition.REFUSED, AuthorityReason.VENUE_UNCERTAIN
        )
    authorization = _EffectAuthorization(
        request=request,
        session_id=item.session_id,
        manual_flatten_id=item.manual_flatten_id,
        emergency_grant_id=item.emergency_grant_id,
    )
    manuals = state._manual_by_id
    if item.manual_flatten_id is not None:
        manual = state._manual_by_id.get(_manual_key(item.manual_flatten_id))
        assert manual is not None
        manuals = _replaced(
            manuals,
            _manual_key(item.manual_flatten_id),
            _ManualFlatten(
                command=manual.command,
                phase=_FlattenPhase.SELL_CREATED,
                cancel_effect_ids=manual.cancel_effect_ids,
                sell_effect_id=request.effect_id,
            ),
        )
    next_state = _state_with(
        state,
        venue=venue_transition.book,
        _effect_authority_by_id=_inserted(
            state._effect_authority_by_id, _effect_key(request.effect_id), authorization
        ),
        _manual_by_id=manuals,
    )
    next_state = _record_input(next_state, item)
    return _result(
        next_state,
        AuthorityDisposition.APPLIED,
        created=(request.effect_id,),
        venue_transitions=(venue_transition,),
    )


def _claim_gate_reason(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    authorization: _EffectAuthorization,
) -> AuthorityReason | None:
    request = authorization.request
    if authorization.emergency_grant_id is not None and not (
        request.kind is EffectKind.SUBMIT and request.side is ExecutionSide.SELL
    ):
        return AuthorityReason.EMERGENCY_GRANT_REDUCE_ONLY
    fence = _mutation_fence_reason(state)
    if fence is not None:
        return fence
    if authorization.session_id != state.session_id:
        return AuthorityReason.SESSION_MISMATCH
    if request.kind is EffectKind.CANCEL:
        return _reserved_budget_reason(state)
    emergency = authorization.emergency_grant_id is not None
    if emergency:
        synthetic = CreateBrokerEffect(
            input_id=AuthorityInputId("internal-grant-regate"),
            session_id=authorization.session_id,
            request=request,
            manual_flatten_id=authorization.manual_flatten_id,
            emergency_grant_id=authorization.emergency_grant_id,
        )
        grant_reason = _grant_reason(state, synthetic)
        if grant_reason is not None:
            return grant_reason
    elif request.side is ExecutionSide.BUY:
        if state.mode is not TradingMode.ACTIVE:
            return AuthorityReason.MODE_BLOCKED
        if state.kill_engaged:
            return AuthorityReason.KILL_ENGAGED
    else:
        if state.mode not in {TradingMode.ACTIVE, TradingMode.REDUCING}:
            return AuthorityReason.MODE_BLOCKED
        if state.kill_engaged:
            return AuthorityReason.KILL_ENGAGED
    if request.side is ExecutionSide.SELL and (
        request.quantity.value > execution.position.authorized_residual_sell.value
    ):
        return AuthorityReason.RESIDUAL_EXCEEDED
    return _reserved_budget_reason(state) if emergency else _normal_budget_reason(state)


def _claim_effect(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: ClaimEffect,
) -> ExecutionAuthorityTransition:
    if (
        state._claim_by_effect.get(_effect_key(item.effect_id)) is not None
        or state._claim_by_occurrence.get(_claim_key(item.claim_occurrence_id))
        is not None
    ):
        return _result(state, AuthorityDisposition.CONFLICT)
    authorization = state._effect_authority_by_id.get(_effect_key(item.effect_id))
    if authorization is None:
        return _result(
            state, AuthorityDisposition.REFUSED, AuthorityReason.EFFECT_UNKNOWN
        )
    reason = _claim_gate_reason(state, execution, authorization)
    if reason is not None:
        return _result(state, AuthorityDisposition.REFUSED, reason)
    request = authorization.request
    if (
        authorization.manual_flatten_id is not None
        and request.kind is EffectKind.SUBMIT
        and request.side is ExecutionSide.SELL
        and request.quantity != execution.position.authorized_residual_sell
    ):
        return _result(
            state, AuthorityDisposition.REFUSED, AuthorityReason.RESIDUAL_EXCEEDED
        )
    reason = _venue_reason(
        state,
        execution,
        request.symbol_id,
        item.effect_id,
        require_clear=request.kind is not EffectKind.CANCEL,
    )
    if reason is not None:
        return _result(state, AuthorityDisposition.REFUSED, reason)
    venue_transition = _authority_claim_effect(
        state.venue,
        execution,
        RecordDispatchClaim(
            input_id=_venue_input_id(item.input_id, "claim"),
            effect_id=item.effect_id,
            claim_occurrence_id=item.claim_occurrence_id,
        ),
    )
    if venue_transition.disposition in {
        VenueRecoveryDisposition.CONFLICT,
        VenueRecoveryDisposition.EXACT_REPLAY,
    }:
        return _result(state, AuthorityDisposition.CONFLICT)
    if venue_transition.disposition is not VenueRecoveryDisposition.APPLIED:
        return _result(
            state, AuthorityDisposition.REFUSED, AuthorityReason.VENUE_UNCERTAIN
        )
    consumed = state._consumed_grant_ids
    grant = state._emergency_grant
    if (
        authorization.emergency_grant_id is not None
        and request.kind is EffectKind.SUBMIT
        and request.side is ExecutionSide.SELL
    ):
        consumed = _inserted(
            consumed,
            _grant_key(authorization.emergency_grant_id),
            True,
        )
        grant = None
    next_state = _state_with(
        state,
        venue=venue_transition.book,
        budget=RequestBudget(
            remaining=state.budget.remaining - 1,
            safety_reserve=state.budget.safety_reserve,
        ),
        _consumed_grant_ids=consumed,
        _emergency_grant=grant,
        _claim_by_effect=_inserted(
            state._claim_by_effect, _effect_key(item.effect_id), item
        ),
        _claim_by_occurrence=_inserted(
            state._claim_by_occurrence, _claim_key(item.claim_occurrence_id), item
        ),
    )
    next_state = _record_input(next_state, item)
    return _result(
        next_state,
        AuthorityDisposition.APPLIED,
        claim=_FreshEffectClaim(
            effect_id=item.effect_id,
            effect_scope=_scope_from_request(state, request),
            claim_occurrence_id=item.claim_occurrence_id,
        ),
        venue_transitions=(venue_transition,),
    )


def _claim_query(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: ClaimBrokerQuery,
) -> ExecutionAuthorityTransition:
    retained = state._query_by_id.get(_query_key(item.query_claim_id))
    if retained is not None:
        return _result(state, AuthorityDisposition.CONFLICT)
    if (
        state.phase is not EnginePhase.RECONCILING
        and state.phase is not EnginePhase.SERVING
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.PHASE_BLOCKED,
        )
    if (
        state.supervisor_fence is not SupervisorFence.RECONCILIATION_ONLY
        and state.supervisor_fence is not SupervisorFence.PAPER_MUTATION_ELIGIBLE
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.SUPERVISOR_FENCE_BLOCKED,
        )
    if not _execution_scope_matches(state, execution, item.symbol_id):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.EXECUTION_BINDING_MISMATCH,
        )
    reason = _reserved_budget_reason(state)
    if reason is not None:
        return _result(state, AuthorityDisposition.REFUSED, reason)
    next_state = _state_with(
        state,
        budget=RequestBudget(
            remaining=state.budget.remaining - 1,
            safety_reserve=state.budget.safety_reserve,
        ),
        _query_by_id=_inserted(
            state._query_by_id, _query_key(item.query_claim_id), item
        ),
    )
    next_state = _record_input(next_state, item)
    return _result(
        next_state,
        AuthorityDisposition.APPLIED,
        claim=_FreshQueryClaim(item.query_claim_id, item.symbol_id, item.kind),
    )


def _engage_kill(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: EngageKill,
) -> ExecutionAuthorityTransition:
    stand_down = _authority_stand_down_account_requested_effects(
        state.venue,
        execution,
        f"kill:{item.input_id.value}",
    )
    if stand_down is None:
        venue = state.venue
        venue_transitions: tuple[VenueRecoveryTransition, ...] = ()
    else:
        venue, venue_transitions = stand_down
    next_state = _state_with(state, kill_engaged=True, venue=venue)
    next_state = _record_input(next_state, item)
    return _result(
        next_state,
        AuthorityDisposition.APPLIED,
        venue_transitions=venue_transitions,
    )


def _begin_manual_flatten(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: BeginManualFlatten,
) -> ExecutionAuthorityTransition:
    if state._manual_by_id.get(_manual_key(item.flatten_id)) is not None:
        return _result(state, AuthorityDisposition.CONFLICT)
    reason = _mutation_fence_reason(state)
    if reason is None and item.session_id != state.session_id:
        reason = AuthorityReason.SESSION_MISMATCH
    if reason is None and state.mode is not TradingMode.REDUCING:
        reason = AuthorityReason.MODE_BLOCKED
    if reason is None and state.kill_engaged:
        reason = AuthorityReason.KILL_ENGAGED
    if reason is None and item.emergency_grant_id is not None:
        reason = AuthorityReason.MANUAL_FLATTEN_INVALID
    if reason is None:
        reason = _venue_reason(
            state,
            execution,
            item.symbol_id,
            None,
            require_clear=False,
        )
    if reason is not None:
        return _result(state, AuthorityDisposition.REFUSED, reason)
    result = _authority_begin_symbol_flatten(
        state.venue,
        execution,
        _position_scope(state, item.symbol_id),
        MandateId(f"manual-flatten:{item.flatten_id.value}"),
        f"manual-flatten:{item.flatten_id.value}",
    )
    if result is None:
        return _result(
            state, AuthorityDisposition.REFUSED, AuthorityReason.VENUE_UNCERTAIN
        )
    venue, cancel_ids, venue_transitions = result
    effect_authority = state._effect_authority_by_id
    for effect_id in cancel_ids:
        effect = venue._current_effect(effect_id)
        if effect is None:
            raise RuntimeError("venue flatten helper omitted a created cancel effect")
        scope = effect.scope
        request = BrokerEffectRequest(
            effect_id=scope.effect_id,
            request_occurrence_id=scope.request_occurrence_id,
            mandate_id=scope.mandate_id,
            kind=scope.kind,
            client_order_id=scope.client_order_id,
            symbol_id=scope.symbol_id,
            side=scope.side,
            quantity=scope.quantity,
            economic_scope=scope.economic_scope,
            target_leg_key=scope.target_leg_key,
        )
        effect_authority = _inserted(
            effect_authority,
            _effect_key(effect_id),
            _EffectAuthorization(request, item.session_id, item.flatten_id, None),
        )
    manual = _ManualFlatten(item, _FlattenPhase.WAITING, cancel_ids)
    next_state = _state_with(
        state,
        venue=venue,
        _effect_authority_by_id=effect_authority,
        _manual_by_id=_inserted(
            state._manual_by_id, _manual_key(item.flatten_id), manual
        ),
    )
    next_state = _record_input(next_state, item)
    return _result(
        next_state,
        AuthorityDisposition.APPLIED,
        created=cancel_ids,
        venue_transitions=venue_transitions,
    )


def _advance_manual_flatten(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: AdvanceManualFlatten,
) -> ExecutionAuthorityTransition:
    manual = state._manual_by_id.get(_manual_key(item.flatten_id))
    if manual is None:
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.MANUAL_FLATTEN_INVALID,
        )
    if manual.phase is _FlattenPhase.SELL_CREATED:
        sell_effect_id = manual.sell_effect_id
        authorization = (
            None
            if sell_effect_id is None
            else state._effect_authority_by_id.get(_effect_key(sell_effect_id))
        )
        request = None if authorization is None else authorization.request
        effect = (
            None
            if sell_effect_id is None
            else state.venue._current_effect(sell_effect_id)
        )
        if (
            sell_effect_id is None
            or authorization is None
            or request is None
            or effect is None
            or manual.command.flatten_id != item.flatten_id
            or authorization.manual_flatten_id != item.flatten_id
            or authorization.session_id != manual.command.session_id
            or authorization.emergency_grant_id is not None
            or request.effect_id != sell_effect_id
            or request.kind is not EffectKind.SUBMIT
            or request.side is not ExecutionSide.SELL
            or request.symbol_id != manual.command.symbol_id
            or effect.scope != _scope_from_request(state, request)
            or request.quantity == execution.position.authorized_residual_sell
        ):
            return _result(
                state,
                AuthorityDisposition.REFUSED,
                AuthorityReason.MANUAL_FLATTEN_INVALID,
            )
        reason = _venue_reason(
            state,
            execution,
            request.symbol_id,
            sell_effect_id,
            require_clear=True,
        )
        if reason is not None:
            return _result(state, AuthorityDisposition.REFUSED, reason)
        stand_down = _authority_stand_down_requested_effect(
            state.venue,
            execution,
            sell_effect_id,
            f"manual-flatten-retry:{item.input_id.value}",
        )
        if stand_down is None:
            return _result(
                state,
                AuthorityDisposition.REFUSED,
                AuthorityReason.VENUE_UNCERTAIN,
            )
        venue, venue_transitions = stand_down
        ready = _ManualFlatten(
            manual.command,
            _FlattenPhase.READY,
            manual.cancel_effect_ids,
        )
        next_state = _state_with(
            state,
            venue=venue,
            _manual_by_id=_replaced(
                state._manual_by_id,
                _manual_key(item.flatten_id),
                ready,
            ),
        )
        next_state = _record_input(next_state, item)
        return _result(
            next_state,
            AuthorityDisposition.APPLIED,
            venue_transitions=venue_transitions,
        )
    if manual.phase is not _FlattenPhase.WAITING:
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.MANUAL_FLATTEN_INVALID,
        )
    cancel_parents_closed = all(
        (effect := state.venue._current_effect(effect_id)) is not None
        and effect.acceptance_set_state is AcceptanceSetState.CLOSED
        for effect_id in manual.cancel_effect_ids
    )
    if not cancel_parents_closed or not _authority_symbol_flatten_ready(
        state.venue,
        execution,
        _position_scope(state, manual.command.symbol_id),
    ):
        return _result(
            state, AuthorityDisposition.REFUSED, AuthorityReason.VENUE_UNCERTAIN
        )
    ready = _ManualFlatten(
        manual.command,
        _FlattenPhase.READY,
        manual.cancel_effect_ids,
    )
    next_state = _state_with(
        state,
        _manual_by_id=_replaced(
            state._manual_by_id, _manual_key(item.flatten_id), ready
        ),
    )
    next_state = _record_input(next_state, item)
    return _result(next_state, AuthorityDisposition.APPLIED)


_COMMAND_TYPES = (
    CreateBrokerEffect,
    ClaimEffect,
    ClaimBrokerQuery,
    EngageKill,
    BeginManualFlatten,
    AdvanceManualFlatten,
)


def apply_execution_authority_input(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: object,
) -> ExecutionAuthorityTransition:
    """Apply one exact authority input without I/O or caller-minted authority."""

    state = _validate_authority_state(state)
    _require("execution", execution, ExecutionSnapshot)
    if type(item) not in _COMMAND_TYPES:
        raise TypeError("authority input must be an exact admitted command type")
    command = cast(_AuthorityCommand, item)
    replay = _replay_or_conflict(state, command)
    if replay is not None:
        return replay
    if type(item) is CreateBrokerEffect:
        return _create_effect(state, execution, item)
    if type(item) is ClaimEffect:
        return _claim_effect(state, execution, item)
    if type(item) is ClaimBrokerQuery:
        return _claim_query(state, execution, item)
    if type(item) is EngageKill:
        return _engage_kill(state, execution, item)
    if type(item) is BeginManualFlatten:
        return _begin_manual_flatten(state, execution, item)
    return _advance_manual_flatten(state, execution, cast(AdvanceManualFlatten, item))


__all__ = [
    "AdvanceManualFlatten",
    "AuthorityDisposition",
    "AuthorityInputId",
    "AuthorityQueryKind",
    "AuthorityReason",
    "BeginManualFlatten",
    "BrokerEffectRequest",
    "ClaimBrokerQuery",
    "ClaimEffect",
    "CreateBrokerEffect",
    "EmergencyGrantId",
    "EngageKill",
    "EnginePhase",
    "ExecutionAuthorityState",
    "ExecutionAuthorityTransition",
    "ManualFlattenId",
    "QueryClaimId",
    "RequestBudget",
    "SessionId",
    "SupervisorFence",
    "TradingMode",
    "apply_execution_authority_input",
    "initial_execution_authority_state",
]
