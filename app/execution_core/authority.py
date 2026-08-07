"""Pure deny-by-default execution authority for the reset kernel.

This module decides whether one exact broker effect or query may be created or
finally claimed.  It owns no clock, persistence, credentials, broker adapter,
or runtime wiring; later milestones must hydrate its environmental fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Protocol, TypeGuard, TypeVar, cast

from .fills import ExecutionSide, PositionScope, _PersistentKeyMap, _commit_parts
from .identity import (
    AccountId,
    AcquisitionGenerationId,
    AcquisitionMandateId,
    ApplicationGenerationId,
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
    _acquisition_generation_id_is_canonical,
)
from .position import ExecutionSnapshot, PositionIntegrity
from .values import Quantity, ReportedPrice
from .venue import (
    AcquisitionVenueSourceKind,
    AcquisitionVenueContext,
    AcquisitionVenueProjection,
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
    _authority_bootstrap_unbound_target_pair_for_scope,
    _authority_claim_effect,
    _authority_execution_pair_for_scope,
    _authority_effect_identity_conflicts,
    _authority_request_acquisition_effect,
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


class AcquisitionOrderType(str, Enum):
    """The single pure-M1 acquisition order form."""

    LIMIT = "LIMIT"


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
class AcquisitionEffectTerms:
    """Exact economics for one specialized acquisition request.

    Identity, ownership, and authority are intentionally absent: the later
    authority permit derives those from its sealed controller coordinate.
    """

    quantity: Quantity
    limit_price: ReportedPrice
    order_type: AcquisitionOrderType
    evaluation_time: int
    commitment: bytes = field(init=False)

    def __post_init__(self) -> None:
        _require("quantity", self.quantity, Quantity)
        _require("limit_price", self.limit_price, ReportedPrice)
        _require("order_type", self.order_type, AcquisitionOrderType)
        if type(self.evaluation_time) is not int:
            raise TypeError("evaluation_time must be an exact integer")
        if self.evaluation_time < 0:
            raise ValueError("evaluation_time must be non-negative")
        if self.quantity.value <= 0:
            raise ValueError("acquisition quantity must be positive")
        if self.limit_price.exact_value <= 0 or not self.limit_price.is_aligned:
            raise ValueError(
                "acquisition limit_price must be positive and tick-aligned"
            )
        object.__setattr__(
            self,
            "commitment",
            _commit_parts(
                b"execution-core/acquisition-effect-terms/v1",
                str(self.quantity.value).encode("utf-8"),
                str(self.limit_price.units.value).encode("utf-8"),
                str(self.limit_price.scale.value).encode("utf-8"),
                str(self.limit_price.tick.tick_units.value).encode("utf-8"),
                str(self.limit_price.tick.scale.value).encode("utf-8"),
                self.order_type.value.encode("utf-8"),
                str(self.evaluation_time).encode("utf-8"),
            ),
        )


def _acquisition_effect_terms_is_authentic(
    value: object,
) -> TypeGuard[AcquisitionEffectTerms]:
    """Recompute the exact economic leaf instead of trusting its cached digest."""

    if type(value) is not AcquisitionEffectTerms:
        return False
    try:
        canonical = AcquisitionEffectTerms(
            quantity=value.quantity,
            limit_price=value.limit_price,
            order_type=value.order_type,
            evaluation_time=value.evaluation_time,
        )
        return value.commitment == canonical.commitment
    except (AttributeError, TypeError, ValueError):
        return False


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
class CreateAcquisitionEffect:
    """One public envelope for an authority-sealed acquisition BUY permit.

    The envelope carries no caller-shaped execution economics or lifecycle
    identities.  Those are retained in the opaque permit and rederived by the
    authority handler immediately before the one venue mutation.
    """

    input_id: AuthorityInputId
    permit: "AcquisitionEffectPermit"

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, AuthorityInputId)
        _require("permit", self.permit, AcquisitionEffectPermit)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("CreateAcquisitionEffect is exact and cannot be subclassed")


@dataclass(frozen=True, slots=True)
class ClaimAcquisitionEffect:
    """One public envelope for an authority-sealed acquisition final claim."""

    input_id: AuthorityInputId
    effect_id: EffectId
    claim_occurrence_id: ClaimOccurrenceId
    permit: "AcquisitionClaimPermit"

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, AuthorityInputId)
        _require("effect_id", self.effect_id, EffectId)
        _require("claim_occurrence_id", self.claim_occurrence_id, ClaimOccurrenceId)
        _require("permit", self.permit, AcquisitionClaimPermit)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("ClaimAcquisitionEffect is exact and cannot be subclassed")


@dataclass(frozen=True, slots=True)
class BeginAcquisitionPreemption:
    """One public envelope for a sealed cancel-only acquisition permit."""

    input_id: AuthorityInputId
    permit: "AcquisitionExitPermit"

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, AuthorityInputId)
        _require("permit", self.permit, AcquisitionExitPermit)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("BeginAcquisitionPreemption is exact and cannot be subclassed")


@dataclass(frozen=True, slots=True)
class CreateAcquisitionProtectionExit:
    """One public envelope for a sealed protective-SELL permit."""

    input_id: AuthorityInputId
    permit: "AcquisitionExitPermit"

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, AuthorityInputId)
        _require("permit", self.permit, AcquisitionExitPermit)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError(
            "CreateAcquisitionProtectionExit is exact and cannot be subclassed"
        )


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


@dataclass(frozen=True, slots=True, init=False)
class _RegisterAcquisitionCurrentness:
    """Internal R8 bootstrap command with an authority-derived ledger key."""

    input_id: AuthorityInputId = field(init=False)
    registration: _AcquisitionCurrentnessRegistration = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError(
            "bootstrap registration commands are authority-constructed only"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("bootstrap registration commands cannot be subclassed")


@dataclass(frozen=True, slots=True, init=False)
class RegisterAcquisitionCurrentness:
    """Opaque sealed currentness-registration command.

    The constructor is intentionally unavailable.  Only the authority-owned
    currentness mint can supply its sealed registration.  Bootstrap remains
    private to controller initialization; this wrapper admits only the two
    post-bootstrap sealed sources owned by the controller composition.
    """

    input_id: AuthorityInputId = field(init=False)
    registration: (
        _CanonicalFactCurrentnessRegistration | _ProtectionRebaseCurrentnessRegistration
    ) = field(
        init=False,
        repr=False,
    )
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError(
            "currentness registration commands are authority-constructed only"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("currentness registration commands cannot be subclassed")

    @classmethod
    def from_registration(
        cls,
        registration: (
            _AcquisitionCurrentnessRegistration
            | _CanonicalFactCurrentnessRegistration
            | _ProtectionRebaseCurrentnessRegistration
        ),
    ) -> RegisterAcquisitionCurrentness:
        """Return the sole dispatch wrapper for one sealed post-bootstrap source."""

        if type(registration) is _CanonicalFactCurrentnessRegistration:
            return _new_register_canonical_fact_currentness(registration)
        if type(registration) is _ProtectionRebaseCurrentnessRegistration:
            return _new_register_protection_rebase_currentness(registration)
        raise TypeError("currentness registration must be one sealed owner source")


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
    | CreateAcquisitionEffect
    | ClaimAcquisitionEffect
    | BeginAcquisitionPreemption
    | CreateAcquisitionProtectionExit
    | ClaimEffect
    | _RegisterAcquisitionCurrentness
    | RegisterAcquisitionCurrentness
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
    _claim_by_effect: _PersistentKeyMap[ClaimEffect | ClaimAcquisitionEffect] = field(
        repr=False
    )
    _claim_by_occurrence: _PersistentKeyMap[ClaimEffect | ClaimAcquisitionEffect] = (
        field(repr=False)
    )
    _query_by_id: _PersistentKeyMap[ClaimBrokerQuery] = field(repr=False)
    _manual_by_id: _PersistentKeyMap[_ManualFlatten] = field(repr=False)
    _manual_flatten_by_scope: _PersistentKeyMap[ManualFlattenId] = field(repr=False)
    _consumed_grant_ids: _PersistentKeyMap[bool] = field(repr=False)
    _acquisition_currentness_by_scope: _PersistentKeyMap[
        _AcquisitionCurrentnessEntry
    ] = field(repr=False)
    _acquisition_descriptor_by_scope: _PersistentKeyMap[
        _AcquisitionEffectDescriptor | _AcquisitionInactiveSlot
    ] = field(repr=False)
    _acquisition_descriptor_by_effect: _PersistentKeyMap[
        _AcquisitionEffectDescriptor
    ] = field(repr=False)
    _acquisition_active_by_scope: _PersistentKeyMap[
        _AcquisitionActiveEffect | _AcquisitionInactiveSlot
    ] = field(repr=False)
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
    "_manual_flatten_by_scope",
    "_consumed_grant_ids",
    "_acquisition_currentness_by_scope",
    "_acquisition_descriptor_by_scope",
    "_acquisition_descriptor_by_effect",
    "_acquisition_active_by_scope",
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


class AcquisitionContextRefreshDisposition(str, Enum):
    """Authority-owned target-source freshness result."""

    CURRENT = "CURRENT"
    REFRESHED = "REFRESHED"
    UNBOUND_BOOTSTRAP = "UNBOUND_BOOTSTRAP"
    REFUSED = "REFUSED"


class AcquisitionAdmissionKind(str, Enum):
    """The only target-local controller-admission classifications."""

    GENESIS_EMPTY = "GENESIS_EMPTY"
    SUCCESSOR = "SUCCESSOR"


class AcquisitionAuthorityOperation(str, Enum):
    """The bounded operation family retained by acquisition authority receipts."""

    REGISTER = "REGISTER"
    CREATE = "CREATE"
    CLAIM = "CLAIM"
    PREEMPT = "PREEMPT"
    PROTECTION_EXIT = "PROTECTION_EXIT"


class _AcquisitionExitPurpose(str, Enum):
    PREEMPT_BUY_ONLY = "PREEMPT_BUY_ONLY"
    CREATE_PROTECTION_EXIT_ONLY = "CREATE_PROTECTION_EXIT_ONLY"


def _acquisition_scope_key(
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
) -> bytes:
    _require(
        "application_generation_id", application_generation_id, ApplicationGenerationId
    )
    _require("position_scope", position_scope, PositionScope)
    return _commit_parts(
        b"execution-core/acquisition-authority/scope-key/v1",
        application_generation_id.value.encode("utf-8"),
        position_scope.broker.value.encode("utf-8"),
        position_scope.environment.value.encode("utf-8"),
        position_scope.account.value.encode("utf-8"),
        position_scope.symbol_id.value.encode("utf-8"),
    )


def _currentness_entry_commitment(value: object) -> bytes | None:
    if value is None:
        return _commit_parts(
            b"execution-core/acquisition-authority/empty-currentness/v1"
        )
    if type(
        value
    ) is _AcquisitionCurrentnessEntry and _acquisition_currentness_entry_is_authentic(
        value
    ):
        return value.commitment
    return None


def _descriptor_entry_commitment(value: object) -> bytes | None:
    if value is None:
        return _commit_parts(
            b"execution-core/acquisition-authority/empty-descriptor/v1"
        )
    if type(
        value
    ) is _AcquisitionEffectDescriptor and _acquisition_effect_descriptor_is_authentic(
        value
    ):
        return value.commitment
    if type(
        value
    ) is _AcquisitionInactiveSlot and _acquisition_inactive_slot_is_authentic(value):
        return value.commitment
    return None


def _active_entry_commitment(value: object) -> bytes | None:
    if value is None:
        return _commit_parts(b"execution-core/acquisition-authority/empty-active/v1")
    if type(
        value
    ) is _AcquisitionActiveEffect and _acquisition_active_effect_is_authentic(value):
        return value.commitment
    if type(
        value
    ) is _AcquisitionInactiveSlot and _acquisition_inactive_slot_is_authentic(value):
        return value.commitment
    return None


def _manual_flatten_entry_commitment(value: object) -> bytes | None:
    if value is None:
        return _commit_parts(
            b"execution-core/acquisition-authority/empty-manual-flatten/v1"
        )
    if type(value) is ManualFlattenId:
        return _commit_parts(
            b"execution-core/acquisition-authority/manual-flatten-entry/v1",
            value.value.encode("utf-8"),
        )
    return None


def _acquisition_authority_commitment(
    state: ExecutionAuthorityState,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
) -> bytes | None:
    key = _acquisition_scope_key(application_generation_id, position_scope)
    committed = (
        _currentness_entry_commitment(state._acquisition_currentness_by_scope.get(key)),
        _descriptor_entry_commitment(state._acquisition_descriptor_by_scope.get(key)),
        _active_entry_commitment(state._acquisition_active_by_scope.get(key)),
        _manual_flatten_entry_commitment(state._manual_flatten_by_scope.get(key)),
    )
    if any(item is None for item in committed):
        return None
    return _commit_parts(
        b"execution-core/acquisition-authority/context/v1",
        key,
        cast(bytes, committed[0]),
        cast(bytes, committed[1]),
        cast(bytes, committed[2]),
        cast(bytes, committed[3]),
    )


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionAuthorityContext:
    """Bounded target authority reader with no public mutation surface."""

    application_generation_id: ApplicationGenerationId = field(init=False)
    position_scope: PositionScope = field(init=False)
    scope_execution_commitment: bytes = field(init=False)
    venue_commitment: bytes = field(init=False)
    authority_commitment: bytes = field(init=False)
    commitment: bytes = field(init=False)
    _source_execution_commitment: bytes = field(init=False, repr=False)
    _serving: bool = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionAuthorityContext is authority-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionAuthorityContext cannot be subclassed")

    def matches_current(
        self,
        state: ExecutionAuthorityState,
        execution: ExecutionSnapshot,
        venue_context: AcquisitionVenueContext,
    ) -> bool:
        if (
            not _acquisition_authority_context_is_authentic(self)
            or type(state) is not ExecutionAuthorityState
            or type(execution) is not ExecutionSnapshot
            or type(venue_context) is not AcquisitionVenueContext
        ):
            return False
        current = project_acquisition_authority_context(state, execution, venue_context)
        return bool(
            _acquisition_authority_context_is_authentic(current)
            and current.application_generation_id == self.application_generation_id
            and current.position_scope == self.position_scope
            and current.scope_execution_commitment == self.scope_execution_commitment
            and current.venue_commitment == self.venue_commitment
            and current.authority_commitment == self.authority_commitment
            and current.commitment == self.commitment
            and current._source_execution_commitment
            == self._source_execution_commitment
        )


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionAdmissionProjection:
    """Opaque target-local proof for one controller genesis or successor lane."""

    kind: AcquisitionAdmissionKind = field(init=False)
    application_generation_id: ApplicationGenerationId = field(init=False)
    position_scope: PositionScope = field(init=False)
    scope_execution_commitment: bytes = field(init=False)
    venue_commitment: bytes = field(init=False)
    authority_commitment: bytes = field(init=False)
    source_commitment: bytes = field(init=False)
    _authority: ExecutionAuthorityState = field(init=False, repr=False)
    _execution: ExecutionSnapshot = field(init=False, repr=False)
    _venue_context: AcquisitionVenueContext = field(init=False, repr=False)
    _authority_context: AcquisitionAuthorityContext = field(init=False, repr=False)
    _slot_key: bytes = field(init=False, repr=False)
    _serving: bool = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionAdmissionProjection is authority-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionAdmissionProjection cannot be subclassed")

    def permits_genesis(
        self,
        application_generation_id: ApplicationGenerationId,
        execution: ExecutionSnapshot,
        position_scope: PositionScope,
    ) -> bool:
        """Return whether this exact sealed proof still admits first genesis."""

        if (
            not _acquisition_admission_is_authentic(self)
            or type(application_generation_id) is not ApplicationGenerationId
            or type(execution) is not ExecutionSnapshot
            or type(position_scope) is not PositionScope
            or self.kind is not AcquisitionAdmissionKind.GENESIS_EMPTY
            or not self._serving
            or self.application_generation_id != application_generation_id
            or self.position_scope != position_scope
        ):
            return False
        current = project_acquisition_admission(
            self._authority,
            execution,
            position_scope,
        )
        return bool(
            _acquisition_admission_is_authentic(current)
            and current.kind is AcquisitionAdmissionKind.GENESIS_EMPTY
            and current._serving
            and current._seal == self._seal
        )

    def permits_successor(
        self,
        application_generation_id: ApplicationGenerationId,
        execution: ExecutionSnapshot,
        position_scope: PositionScope,
    ) -> bool:
        """Return whether this sealed current slot admits one serial successor."""

        if (
            not _acquisition_admission_is_authentic(self)
            or type(application_generation_id) is not ApplicationGenerationId
            or type(execution) is not ExecutionSnapshot
            or type(position_scope) is not PositionScope
            or self.kind is not AcquisitionAdmissionKind.SUCCESSOR
            or not self._serving
            or self.application_generation_id != application_generation_id
            or self.position_scope != position_scope
        ):
            return False
        current = project_acquisition_admission(
            self._authority,
            execution,
            position_scope,
        )
        return bool(
            _acquisition_admission_is_authentic(current)
            and current.kind is AcquisitionAdmissionKind.SUCCESSOR
            and current._serving
            and current._seal == self._seal
        )


class _AcquisitionCurrentnessSourceKind(str, Enum):
    BOOTSTRAP = "BOOTSTRAP"
    CANONICAL_FACT = "CANONICAL_FACT"
    AUTHORITY_MUTATION = "AUTHORITY_MUTATION"
    PROTECTION_REBASE = "PROTECTION_REBASE"


class _ProtectionRebaseKindView(Protocol):
    value: str


class _ProtectionRebaseProjectionView(Protocol):
    """The protection-owned public proof seen without an authority import."""

    kind: _ProtectionRebaseKindView
    application_generation_id: ApplicationGenerationId
    position_scope: PositionScope
    predecessor_execution_snapshot_commitment: bytes | None
    execution_snapshot_commitment: bytes | None
    predecessor_scope_execution_commitment: bytes | None
    scope_execution_commitment: bytes | None
    predecessor_venue_commitment: bytes | None
    venue_commitment: bytes | None
    predecessor_context_commitment: bytes
    context_commitment: bytes
    predecessor_source_protection_commitment: bytes | None
    source_protection_commitment: bytes | None
    resulting_state: object | None
    source_venue_transition_commitments: tuple[bytes, ...]
    source_commitment: bytes


def _optional_digest_is_exact(value: object) -> bool:
    return value is None or (type(value) is bytes and len(value) == 32)


def _require_digest(name: str, value: object) -> bytes:
    if type(value) is not bytes or len(value) != 32:
        raise TypeError(f"{name} must be exactly 32 bytes")
    return value


def _acquisition_currentness_entry_commitment(
    source_kind: _AcquisitionCurrentnessSourceKind,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    protection_commitment: bytes | None,
    predecessor_slot_commitment: bytes,
) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-authority/currentness-entry/v2",
        source_kind.value.encode("utf-8"),
        application_generation_id.value.encode("utf-8"),
        position_scope.broker.value.encode("utf-8"),
        position_scope.environment.value.encode("utf-8"),
        position_scope.account.value.encode("utf-8"),
        position_scope.symbol_id.value.encode("utf-8"),
        session_id.value.encode("utf-8"),
        generation_id.value.encode("utf-8"),
        acquisition_mandate_id.value.encode("utf-8"),
        protection_mandate_id.value.encode("utf-8"),
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        controller_head,
        successor_ordinal.to_bytes(8, "big"),
        scope_execution_commitment,
        venue_commitment,
        protection_commitment or b"",
        predecessor_slot_commitment,
    )


@dataclass(frozen=True, slots=True, init=False)
class _AcquisitionCurrentnessEntry:
    source_kind: _AcquisitionCurrentnessSourceKind = field(init=False)
    application_generation_id: ApplicationGenerationId = field(init=False)
    position_scope: PositionScope = field(init=False)
    session_id: SessionId = field(init=False)
    generation_id: AcquisitionGenerationId = field(init=False)
    acquisition_mandate_id: AcquisitionMandateId = field(init=False)
    protection_mandate_id: MandateId = field(init=False)
    binding_commitment: bytes = field(init=False)
    emergency_recovery_compatibility_commitment: bytes = field(init=False)
    controller_head: bytes = field(init=False)
    successor_ordinal: int = field(init=False)
    scope_execution_commitment: bytes = field(init=False)
    venue_commitment: bytes = field(init=False)
    protection_commitment: bytes | None = field(init=False)
    predecessor_slot_commitment: bytes = field(init=False)
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError(
            "acquisition currentness entries are authority-constructed only"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("acquisition currentness entries cannot be subclassed")


def _new_acquisition_currentness_entry(
    *,
    source_kind: _AcquisitionCurrentnessSourceKind,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    protection_commitment: bytes | None,
    predecessor_slot_commitment: bytes,
) -> _AcquisitionCurrentnessEntry:
    if (
        type(source_kind) is not _AcquisitionCurrentnessSourceKind
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(session_id) is not SessionId
        or type(generation_id) is not AcquisitionGenerationId
        or type(acquisition_mandate_id) is not AcquisitionMandateId
        or type(protection_mandate_id) is not MandateId
        or not _acquisition_generation_id_is_canonical(generation_id)
        or type(successor_ordinal) is not int
        or successor_ordinal < 0
        or successor_ordinal > 2**64 - 1
        or not _optional_digest_is_exact(protection_commitment)
    ):
        raise TypeError("acquisition currentness entry requires exact owner inputs")
    for digest in (
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        controller_head,
        scope_execution_commitment,
        venue_commitment,
        predecessor_slot_commitment,
    ):
        if type(digest) is not bytes or len(digest) != 32:
            raise TypeError("acquisition currentness entry requires exact commitments")
    commitment = _acquisition_currentness_entry_commitment(
        source_kind,
        application_generation_id,
        position_scope,
        session_id,
        generation_id,
        acquisition_mandate_id,
        protection_mandate_id,
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        controller_head,
        successor_ordinal,
        scope_execution_commitment,
        venue_commitment,
        protection_commitment,
        predecessor_slot_commitment,
    )
    result = object.__new__(_AcquisitionCurrentnessEntry)
    object.__setattr__(result, "source_kind", source_kind)
    object.__setattr__(result, "application_generation_id", application_generation_id)
    object.__setattr__(result, "position_scope", position_scope)
    object.__setattr__(result, "session_id", session_id)
    object.__setattr__(result, "generation_id", generation_id)
    object.__setattr__(result, "acquisition_mandate_id", acquisition_mandate_id)
    object.__setattr__(result, "protection_mandate_id", protection_mandate_id)
    object.__setattr__(result, "binding_commitment", binding_commitment)
    object.__setattr__(
        result,
        "emergency_recovery_compatibility_commitment",
        emergency_recovery_compatibility_commitment,
    )
    object.__setattr__(result, "controller_head", controller_head)
    object.__setattr__(result, "successor_ordinal", successor_ordinal)
    object.__setattr__(
        result,
        "scope_execution_commitment",
        scope_execution_commitment,
    )
    object.__setattr__(result, "venue_commitment", venue_commitment)
    object.__setattr__(result, "protection_commitment", protection_commitment)
    object.__setattr__(
        result,
        "predecessor_slot_commitment",
        predecessor_slot_commitment,
    )
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition-authority/currentness-entry-seal/v1",
            commitment,
        ),
    )
    return result


def _acquisition_currentness_entry_is_authentic(
    value: object,
) -> TypeGuard[_AcquisitionCurrentnessEntry]:
    if type(value) is not _AcquisitionCurrentnessEntry:
        return False
    try:
        source_kind = value.source_kind
        application_generation_id = value.application_generation_id
        position_scope = value.position_scope
        session_id = value.session_id
        generation_id = value.generation_id
        acquisition_mandate_id = value.acquisition_mandate_id
        protection_mandate_id = value.protection_mandate_id
        binding_commitment = value.binding_commitment
        compatibility_commitment = value.emergency_recovery_compatibility_commitment
        controller_head = value.controller_head
        successor_ordinal = value.successor_ordinal
        scope_execution_commitment = value.scope_execution_commitment
        venue_commitment = value.venue_commitment
        protection_commitment = value.protection_commitment
        predecessor_slot_commitment = value.predecessor_slot_commitment
        commitment = value.commitment
        seal = value._seal
    except AttributeError:
        return False
    if (
        type(source_kind) is not _AcquisitionCurrentnessSourceKind
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(session_id) is not SessionId
        or type(generation_id) is not AcquisitionGenerationId
        or type(acquisition_mandate_id) is not AcquisitionMandateId
        or type(protection_mandate_id) is not MandateId
        or not _acquisition_generation_id_is_canonical(generation_id)
        or type(successor_ordinal) is not int
        or successor_ordinal < 0
        or successor_ordinal > 2**64 - 1
        or not _optional_digest_is_exact(protection_commitment)
    ):
        return False
    for digest in (
        binding_commitment,
        compatibility_commitment,
        controller_head,
        scope_execution_commitment,
        venue_commitment,
        predecessor_slot_commitment,
        commitment,
        seal,
    ):
        if type(digest) is not bytes or len(digest) != 32:
            return False
    return bool(
        commitment
        == _acquisition_currentness_entry_commitment(
            source_kind,
            application_generation_id,
            position_scope,
            session_id,
            generation_id,
            acquisition_mandate_id,
            protection_mandate_id,
            binding_commitment,
            compatibility_commitment,
            controller_head,
            successor_ordinal,
            scope_execution_commitment,
            venue_commitment,
            protection_commitment,
            predecessor_slot_commitment,
        )
        and seal
        == _commit_parts(
            b"execution-core/acquisition-authority/currentness-entry-seal/v1",
            commitment,
        )
    )


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionContextRefresh:
    """The only authority-owned E2 handoff for target snapshot freshness."""

    disposition: AcquisitionContextRefreshDisposition = field(init=False)
    application_generation_id: ApplicationGenerationId = field(init=False)
    position_scope: PositionScope = field(init=False)
    source_execution_snapshot_commitment: bytes | None = field(init=False)
    predecessor_execution_snapshot_commitment: bytes | None = field(init=False)
    execution_snapshot_commitment: bytes | None = field(init=False)
    predecessor_scope_execution_commitment: bytes | None = field(init=False)
    scope_execution_commitment: bytes | None = field(init=False)
    predecessor_venue_commitment: bytes | None = field(init=False)
    venue_commitment: bytes | None = field(init=False)
    predecessor_authority_commitment: bytes | None = field(init=False)
    authority_commitment: bytes | None = field(init=False)
    ordered_venue_transition_commitments: tuple[bytes, ...] = field(init=False)
    venue_transitions: tuple[VenueRecoveryTransition, ...] = field(init=False)
    _source_execution: ExecutionSnapshot | None = field(init=False, repr=False)
    predecessor_authority: ExecutionAuthorityState | None = field(
        init=False, repr=False
    )
    predecessor_execution: ExecutionSnapshot | None = field(init=False, repr=False)
    predecessor_venue_context: AcquisitionVenueContext | None = field(
        init=False, repr=False
    )
    predecessor_authority_context: AcquisitionAuthorityContext | None = field(
        init=False,
        repr=False,
    )
    authority: ExecutionAuthorityState | None = field(init=False, repr=False)
    execution: ExecutionSnapshot | None = field(init=False, repr=False)
    venue_context: AcquisitionVenueContext | None = field(init=False, repr=False)
    authority_context: AcquisitionAuthorityContext | None = field(
        init=False, repr=False
    )
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionContextRefresh is authority-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionContextRefresh cannot be subclassed")

    def matches_current(
        self,
        state: ExecutionAuthorityState,
        application_generation_id: ApplicationGenerationId,
        position_scope: PositionScope,
    ) -> bool:
        if (
            not _acquisition_context_refresh_is_authentic(self)
            or self.disposition is AcquisitionContextRefreshDisposition.REFUSED
            or type(state) is not ExecutionAuthorityState
            or type(application_generation_id) is not ApplicationGenerationId
            or type(position_scope) is not PositionScope
            or self.application_generation_id != application_generation_id
            or self.position_scope != position_scope
            or self.authority is not state
            or self.execution is None
            or self.venue_context is None
            or self.authority_context is None
            or not self.venue_context._serving
            or not self.authority_context._serving
        ):
            return False
        return _acquisition_context_refresh_pairs_match_live(self)


@dataclass(frozen=True, slots=True, init=False)
class _AcquisitionCurrentnessRegistration:
    """Private sealed source used only by R8 initializer registration."""

    commitment: bytes = field(init=False)
    _entry: _AcquisitionCurrentnessEntry = field(init=False, repr=False)
    _bootstrap_target_commitment: bytes = field(init=False, repr=False)
    _admission_target_commitment: bytes = field(init=False, repr=False)
    _input_id: AuthorityInputId = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("bootstrap registration is authority-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("bootstrap registration cannot be subclassed")


@dataclass(frozen=True, slots=True, init=False)
class _CanonicalFactCurrentnessRegistration:
    """Private sealed source for one canonical-fact currentness rebase."""

    commitment: bytes = field(init=False)
    _entry: _AcquisitionCurrentnessEntry = field(init=False, repr=False)
    _fact_projection: AcquisitionVenueProjection = field(init=False, repr=False)
    _fact_transition: VenueRecoveryTransition = field(init=False, repr=False)
    _predecessor_authority_context_commitment: bytes = field(
        init=False,
        repr=False,
    )
    _input_id: AuthorityInputId = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("canonical fact registration is authority-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("canonical fact registration cannot be subclassed")


@dataclass(frozen=True, slots=True, init=False)
class _ProtectionRebaseCurrentnessRegistration:
    """Private sealed source for one semantic protection currentness rebase."""

    commitment: bytes = field(init=False)
    _entry: _AcquisitionCurrentnessEntry = field(init=False, repr=False)
    _projection: _ProtectionRebaseProjectionView = field(init=False, repr=False)
    _predecessor_authority_context_commitment: bytes = field(
        init=False,
        repr=False,
    )
    _input_id: AuthorityInputId = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("protection rebase registration is authority-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("protection rebase registration cannot be subclassed")


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionAuthorityReceipt:
    """Read-only proof of one specialized authority transition."""

    operation: AcquisitionAuthorityOperation = field(init=False)
    application_generation_id: ApplicationGenerationId = field(init=False)
    position_scope: PositionScope = field(init=False)
    predecessor_controller_head: bytes = field(init=False)
    controller_head: bytes = field(init=False)
    predecessor_scope_execution_commitment: bytes = field(init=False)
    scope_execution_commitment: bytes = field(init=False)
    predecessor_venue_commitment: bytes = field(init=False)
    venue_commitment: bytes = field(init=False)
    predecessor_authority_commitment: bytes = field(init=False)
    authority_commitment: bytes = field(init=False)
    ordered_venue_transition_commitments: tuple[bytes, ...] = field(init=False)
    permit_commitment: bytes = field(init=False)
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionAuthorityReceipt is authority-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionAuthorityReceipt cannot be subclassed")


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionClaimReceipt:
    """Opaque read receipt reserved for the later specialized final-claim route."""

    effect_id: EffectId = field(init=False)
    claim_occurrence_id: ClaimOccurrenceId = field(init=False)
    controller_head: bytes = field(init=False)
    scope_execution_commitment: bytes = field(init=False)
    venue_commitment: bytes = field(init=False)
    commitment: bytes = field(init=False)
    _input_id: AuthorityInputId = field(init=False, repr=False)
    _authority_context_commitment: bytes = field(init=False, repr=False)
    _permit_commitment: bytes = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionClaimReceipt is authority-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionClaimReceipt cannot be subclassed")


def _acquisition_claim_receipt_commitment(
    *,
    input_id: AuthorityInputId,
    effect_id: EffectId,
    claim_occurrence_id: ClaimOccurrenceId,
    controller_head: bytes,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_context_commitment: bytes,
    permit_commitment: bytes,
) -> bytes:
    if (
        type(input_id) is not AuthorityInputId
        or type(effect_id) is not EffectId
        or type(claim_occurrence_id) is not ClaimOccurrenceId
    ):
        raise TypeError("acquisition claim receipt requires exact identities")
    for digest in (
        controller_head,
        scope_execution_commitment,
        venue_commitment,
        authority_context_commitment,
        permit_commitment,
    ):
        _require_digest("acquisition claim receipt commitment", digest)
    return _commit_parts(
        b"execution-core/acquisition-authority/claim-receipt/v1",
        input_id.value.encode("utf-8"),
        effect_id.value.encode("utf-8"),
        claim_occurrence_id.value.encode("utf-8"),
        controller_head,
        scope_execution_commitment,
        venue_commitment,
        authority_context_commitment,
        permit_commitment,
    )


def _new_acquisition_claim_receipt(
    *,
    input_id: AuthorityInputId,
    effect_id: EffectId,
    claim_occurrence_id: ClaimOccurrenceId,
    controller_head: bytes,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_context_commitment: bytes,
    permit_commitment: bytes,
) -> AcquisitionClaimReceipt:
    commitment = _acquisition_claim_receipt_commitment(
        input_id=input_id,
        effect_id=effect_id,
        claim_occurrence_id=claim_occurrence_id,
        controller_head=controller_head,
        scope_execution_commitment=scope_execution_commitment,
        venue_commitment=venue_commitment,
        authority_context_commitment=authority_context_commitment,
        permit_commitment=permit_commitment,
    )
    result = object.__new__(AcquisitionClaimReceipt)
    for name, value in (
        ("effect_id", effect_id),
        ("claim_occurrence_id", claim_occurrence_id),
        ("controller_head", controller_head),
        ("scope_execution_commitment", scope_execution_commitment),
        ("venue_commitment", venue_commitment),
        ("commitment", commitment),
        ("_input_id", input_id),
        ("_authority_context_commitment", authority_context_commitment),
        ("_permit_commitment", permit_commitment),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition-authority/claim-receipt-seal/v1",
            commitment,
        ),
    )
    return result


def _acquisition_claim_receipt_is_authentic(
    value: object,
) -> TypeGuard[AcquisitionClaimReceipt]:
    if type(value) is not AcquisitionClaimReceipt:
        return False
    try:
        commitment = _acquisition_claim_receipt_commitment(
            input_id=value._input_id,
            effect_id=value.effect_id,
            claim_occurrence_id=value.claim_occurrence_id,
            controller_head=value.controller_head,
            scope_execution_commitment=value.scope_execution_commitment,
            venue_commitment=value.venue_commitment,
            authority_context_commitment=value._authority_context_commitment,
            permit_commitment=value._permit_commitment,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return bool(
        type(value._input_id) is AuthorityInputId
        and value.commitment == commitment
        and type(value._seal) is bytes
        and len(value._seal) == 32
        and value._seal
        == _commit_parts(
            b"execution-core/acquisition-authority/claim-receipt-seal/v1",
            value.commitment,
        )
    )


def _acquisition_effect_permit_commitment(
    *,
    input_id: AuthorityInputId,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    predecessor_controller_head: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    execution_snapshot_commitment: bytes,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_context_commitment: bytes,
    protection_commitment: bytes | None,
    terms: AcquisitionEffectTerms,
    effect_id: EffectId,
    request_occurrence_id: RequestOccurrenceId,
    client_order_id: ClientOrderId,
) -> bytes:
    if type(input_id) is not AuthorityInputId:
        raise TypeError("acquisition effect permit requires AuthorityInputId")
    if (
        type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(session_id) is not SessionId
        or not _acquisition_generation_id_is_canonical(generation_id)
        or type(acquisition_mandate_id) is not AcquisitionMandateId
        or type(protection_mandate_id) is not MandateId
        or type(successor_ordinal) is not int
        or successor_ordinal < 0
        or successor_ordinal > 2**64 - 1
        or type(terms) is not AcquisitionEffectTerms
        or type(effect_id) is not EffectId
        or type(request_occurrence_id) is not RequestOccurrenceId
        or type(client_order_id) is not ClientOrderId
        or not _optional_digest_is_exact(protection_commitment)
    ):
        raise TypeError("acquisition effect permit requires exact owner values")
    for digest in (
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        predecessor_controller_head,
        controller_head,
        execution_snapshot_commitment,
        scope_execution_commitment,
        venue_commitment,
        authority_context_commitment,
    ):
        _require_digest("acquisition effect permit commitment", digest)
    return _commit_parts(
        b"execution-core/acquisition-authority/effect-permit/v1",
        input_id.value.encode("utf-8"),
        application_generation_id.value.encode("utf-8"),
        position_scope.broker.value.encode("utf-8"),
        position_scope.environment.value.encode("utf-8"),
        position_scope.account.value.encode("utf-8"),
        position_scope.symbol_id.value.encode("utf-8"),
        session_id.value.encode("utf-8"),
        generation_id.value.encode("utf-8"),
        acquisition_mandate_id.value.encode("utf-8"),
        protection_mandate_id.value.encode("utf-8"),
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        predecessor_controller_head,
        controller_head,
        successor_ordinal.to_bytes(8, "big"),
        execution_snapshot_commitment,
        scope_execution_commitment,
        venue_commitment,
        authority_context_commitment,
        protection_commitment or b"",
        terms.commitment,
        effect_id.value.encode("utf-8"),
        request_occurrence_id.value.encode("utf-8"),
        client_order_id.value.encode("utf-8"),
    )


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionEffectPermit:
    """Sealed authority capability for one exact specialized acquisition BUY."""

    input_id: AuthorityInputId = field(init=False)
    application_generation_id: ApplicationGenerationId = field(init=False)
    position_scope: PositionScope = field(init=False)
    session_id: SessionId = field(init=False)
    generation_id: AcquisitionGenerationId = field(init=False)
    acquisition_mandate_id: AcquisitionMandateId = field(init=False)
    protection_mandate_id: MandateId = field(init=False)
    binding_commitment: bytes = field(init=False)
    emergency_recovery_compatibility_commitment: bytes = field(init=False)
    predecessor_controller_head: bytes = field(init=False)
    controller_head: bytes = field(init=False)
    successor_ordinal: int = field(init=False)
    execution_snapshot_commitment: bytes = field(init=False)
    scope_execution_commitment: bytes = field(init=False)
    venue_commitment: bytes = field(init=False)
    authority_context_commitment: bytes = field(init=False)
    protection_commitment: bytes | None = field(init=False)
    terms: AcquisitionEffectTerms = field(init=False)
    effect_id: EffectId = field(init=False)
    request_occurrence_id: RequestOccurrenceId = field(init=False)
    client_order_id: ClientOrderId = field(init=False)
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionEffectPermit is authority-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionEffectPermit cannot be subclassed")


def _new_acquisition_effect_permit(
    *,
    input_id: AuthorityInputId,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    predecessor_controller_head: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    execution_snapshot_commitment: bytes,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_context_commitment: bytes,
    protection_commitment: bytes | None,
    terms: AcquisitionEffectTerms,
    effect_id: EffectId,
    request_occurrence_id: RequestOccurrenceId,
    client_order_id: ClientOrderId,
) -> AcquisitionEffectPermit:
    commitment = _acquisition_effect_permit_commitment(
        input_id=input_id,
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        session_id=session_id,
        generation_id=generation_id,
        acquisition_mandate_id=acquisition_mandate_id,
        protection_mandate_id=protection_mandate_id,
        binding_commitment=binding_commitment,
        emergency_recovery_compatibility_commitment=(
            emergency_recovery_compatibility_commitment
        ),
        predecessor_controller_head=predecessor_controller_head,
        controller_head=controller_head,
        successor_ordinal=successor_ordinal,
        execution_snapshot_commitment=execution_snapshot_commitment,
        scope_execution_commitment=scope_execution_commitment,
        venue_commitment=venue_commitment,
        authority_context_commitment=authority_context_commitment,
        protection_commitment=protection_commitment,
        terms=terms,
        effect_id=effect_id,
        request_occurrence_id=request_occurrence_id,
        client_order_id=client_order_id,
    )
    result = object.__new__(AcquisitionEffectPermit)
    for name, value in (
        ("input_id", input_id),
        ("application_generation_id", application_generation_id),
        ("position_scope", position_scope),
        ("session_id", session_id),
        ("generation_id", generation_id),
        ("acquisition_mandate_id", acquisition_mandate_id),
        ("protection_mandate_id", protection_mandate_id),
        ("binding_commitment", binding_commitment),
        (
            "emergency_recovery_compatibility_commitment",
            emergency_recovery_compatibility_commitment,
        ),
        ("predecessor_controller_head", predecessor_controller_head),
        ("controller_head", controller_head),
        ("successor_ordinal", successor_ordinal),
        ("execution_snapshot_commitment", execution_snapshot_commitment),
        ("scope_execution_commitment", scope_execution_commitment),
        ("venue_commitment", venue_commitment),
        ("authority_context_commitment", authority_context_commitment),
        ("protection_commitment", protection_commitment),
        ("terms", terms),
        ("effect_id", effect_id),
        ("request_occurrence_id", request_occurrence_id),
        ("client_order_id", client_order_id),
        ("commitment", commitment),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition-authority/effect-permit-seal/v1",
            commitment,
        ),
    )
    return result


def _acquisition_effect_permit_is_authentic(
    value: object,
) -> TypeGuard[AcquisitionEffectPermit]:
    if type(value) is not AcquisitionEffectPermit:
        return False
    try:
        if not _acquisition_effect_terms_is_authentic(value.terms):
            return False
        commitment = _acquisition_effect_permit_commitment(
            input_id=value.input_id,
            application_generation_id=value.application_generation_id,
            position_scope=value.position_scope,
            session_id=value.session_id,
            generation_id=value.generation_id,
            acquisition_mandate_id=value.acquisition_mandate_id,
            protection_mandate_id=value.protection_mandate_id,
            binding_commitment=value.binding_commitment,
            emergency_recovery_compatibility_commitment=(
                value.emergency_recovery_compatibility_commitment
            ),
            predecessor_controller_head=value.predecessor_controller_head,
            controller_head=value.controller_head,
            successor_ordinal=value.successor_ordinal,
            execution_snapshot_commitment=value.execution_snapshot_commitment,
            scope_execution_commitment=value.scope_execution_commitment,
            venue_commitment=value.venue_commitment,
            authority_context_commitment=value.authority_context_commitment,
            protection_commitment=value.protection_commitment,
            terms=value.terms,
            effect_id=value.effect_id,
            request_occurrence_id=value.request_occurrence_id,
            client_order_id=value.client_order_id,
        )
        return bool(
            value.commitment == commitment
            and value._seal
            == _commit_parts(
                b"execution-core/acquisition-authority/effect-permit-seal/v1",
                commitment,
            )
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _acquisition_claim_permit_commitment(
    *,
    input_id: AuthorityInputId,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    execution_snapshot_commitment: bytes,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_context_commitment: bytes,
    protection_commitment: bytes | None,
    effect_id: EffectId,
    claim_occurrence_id: ClaimOccurrenceId,
    currentness_commitment: bytes,
    descriptor_commitment: bytes,
    active_commitment: bytes,
) -> bytes:
    if (
        type(input_id) is not AuthorityInputId
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(session_id) is not SessionId
        or not _acquisition_generation_id_is_canonical(generation_id)
        or type(acquisition_mandate_id) is not AcquisitionMandateId
        or type(protection_mandate_id) is not MandateId
        or type(successor_ordinal) is not int
        or successor_ordinal < 0
        or successor_ordinal > 2**64 - 1
        or type(effect_id) is not EffectId
        or type(claim_occurrence_id) is not ClaimOccurrenceId
        or not _optional_digest_is_exact(protection_commitment)
    ):
        raise TypeError("acquisition claim permit requires exact owner values")
    for digest in (
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        controller_head,
        execution_snapshot_commitment,
        scope_execution_commitment,
        venue_commitment,
        authority_context_commitment,
        currentness_commitment,
        descriptor_commitment,
        active_commitment,
    ):
        _require_digest("acquisition claim permit commitment", digest)
    return _commit_parts(
        b"execution-core/acquisition-authority/claim-permit/v1",
        input_id.value.encode("utf-8"),
        application_generation_id.value.encode("utf-8"),
        position_scope.broker.value.encode("utf-8"),
        position_scope.environment.value.encode("utf-8"),
        position_scope.account.value.encode("utf-8"),
        position_scope.symbol_id.value.encode("utf-8"),
        session_id.value.encode("utf-8"),
        generation_id.value.encode("utf-8"),
        acquisition_mandate_id.value.encode("utf-8"),
        protection_mandate_id.value.encode("utf-8"),
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        controller_head,
        successor_ordinal.to_bytes(8, "big"),
        execution_snapshot_commitment,
        scope_execution_commitment,
        venue_commitment,
        authority_context_commitment,
        protection_commitment or b"",
        effect_id.value.encode("utf-8"),
        claim_occurrence_id.value.encode("utf-8"),
        currentness_commitment,
        descriptor_commitment,
        active_commitment,
    )


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionClaimPermit:
    """Sealed authority capability for one exact acquisition final claim."""

    input_id: AuthorityInputId = field(init=False)
    application_generation_id: ApplicationGenerationId = field(init=False)
    position_scope: PositionScope = field(init=False)
    session_id: SessionId = field(init=False)
    generation_id: AcquisitionGenerationId = field(init=False)
    acquisition_mandate_id: AcquisitionMandateId = field(init=False)
    protection_mandate_id: MandateId = field(init=False)
    binding_commitment: bytes = field(init=False)
    emergency_recovery_compatibility_commitment: bytes = field(init=False)
    controller_head: bytes = field(init=False)
    successor_ordinal: int = field(init=False)
    execution_snapshot_commitment: bytes = field(init=False)
    scope_execution_commitment: bytes = field(init=False)
    venue_commitment: bytes = field(init=False)
    authority_context_commitment: bytes = field(init=False)
    protection_commitment: bytes | None = field(init=False)
    effect_id: EffectId = field(init=False)
    claim_occurrence_id: ClaimOccurrenceId = field(init=False)
    currentness_commitment: bytes = field(init=False)
    descriptor_commitment: bytes = field(init=False)
    active_commitment: bytes = field(init=False)
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionClaimPermit is authority-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionClaimPermit cannot be subclassed")


def _new_acquisition_claim_permit(
    *,
    input_id: AuthorityInputId,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    execution_snapshot_commitment: bytes,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_context_commitment: bytes,
    protection_commitment: bytes | None,
    effect_id: EffectId,
    claim_occurrence_id: ClaimOccurrenceId,
    currentness_commitment: bytes,
    descriptor_commitment: bytes,
    active_commitment: bytes,
) -> AcquisitionClaimPermit:
    commitment = _acquisition_claim_permit_commitment(
        input_id=input_id,
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        session_id=session_id,
        generation_id=generation_id,
        acquisition_mandate_id=acquisition_mandate_id,
        protection_mandate_id=protection_mandate_id,
        binding_commitment=binding_commitment,
        emergency_recovery_compatibility_commitment=(
            emergency_recovery_compatibility_commitment
        ),
        controller_head=controller_head,
        successor_ordinal=successor_ordinal,
        execution_snapshot_commitment=execution_snapshot_commitment,
        scope_execution_commitment=scope_execution_commitment,
        venue_commitment=venue_commitment,
        authority_context_commitment=authority_context_commitment,
        protection_commitment=protection_commitment,
        effect_id=effect_id,
        claim_occurrence_id=claim_occurrence_id,
        currentness_commitment=currentness_commitment,
        descriptor_commitment=descriptor_commitment,
        active_commitment=active_commitment,
    )
    result = object.__new__(AcquisitionClaimPermit)
    for name, value in (
        ("input_id", input_id),
        ("application_generation_id", application_generation_id),
        ("position_scope", position_scope),
        ("session_id", session_id),
        ("generation_id", generation_id),
        ("acquisition_mandate_id", acquisition_mandate_id),
        ("protection_mandate_id", protection_mandate_id),
        ("binding_commitment", binding_commitment),
        (
            "emergency_recovery_compatibility_commitment",
            emergency_recovery_compatibility_commitment,
        ),
        ("controller_head", controller_head),
        ("successor_ordinal", successor_ordinal),
        ("execution_snapshot_commitment", execution_snapshot_commitment),
        ("scope_execution_commitment", scope_execution_commitment),
        ("venue_commitment", venue_commitment),
        ("authority_context_commitment", authority_context_commitment),
        ("protection_commitment", protection_commitment),
        ("effect_id", effect_id),
        ("claim_occurrence_id", claim_occurrence_id),
        ("currentness_commitment", currentness_commitment),
        ("descriptor_commitment", descriptor_commitment),
        ("active_commitment", active_commitment),
        ("commitment", commitment),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition-authority/claim-permit-seal/v1",
            commitment,
        ),
    )
    return result


def _acquisition_claim_permit_is_authentic(
    value: object,
) -> TypeGuard[AcquisitionClaimPermit]:
    if type(value) is not AcquisitionClaimPermit:
        return False
    try:
        commitment = _acquisition_claim_permit_commitment(
            input_id=value.input_id,
            application_generation_id=value.application_generation_id,
            position_scope=value.position_scope,
            session_id=value.session_id,
            generation_id=value.generation_id,
            acquisition_mandate_id=value.acquisition_mandate_id,
            protection_mandate_id=value.protection_mandate_id,
            binding_commitment=value.binding_commitment,
            emergency_recovery_compatibility_commitment=(
                value.emergency_recovery_compatibility_commitment
            ),
            controller_head=value.controller_head,
            successor_ordinal=value.successor_ordinal,
            execution_snapshot_commitment=value.execution_snapshot_commitment,
            scope_execution_commitment=value.scope_execution_commitment,
            venue_commitment=value.venue_commitment,
            authority_context_commitment=value.authority_context_commitment,
            protection_commitment=value.protection_commitment,
            effect_id=value.effect_id,
            claim_occurrence_id=value.claim_occurrence_id,
            currentness_commitment=value.currentness_commitment,
            descriptor_commitment=value.descriptor_commitment,
            active_commitment=value.active_commitment,
        )
        return bool(
            value.commitment == commitment
            and value._seal
            == _commit_parts(
                b"execution-core/acquisition-authority/claim-permit-seal/v1",
                commitment,
            )
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _protective_request_commitment(request: BrokerEffectRequest | None) -> bytes:
    if request is None:
        return _commit_parts(
            b"execution-core/acquisition-authority/no-protective-request/v1"
        )
    _require("protective_request", request, BrokerEffectRequest)
    return _commit_parts(
        b"execution-core/acquisition-authority/protective-request/v1",
        request.effect_id.value.encode("utf-8"),
        request.request_occurrence_id.value.encode("utf-8"),
        request.mandate_id.value.encode("utf-8"),
        request.kind.value.encode("utf-8"),
        b""
        if request.client_order_id is None
        else request.client_order_id.value.encode("utf-8"),
        request.symbol_id.value.encode("utf-8"),
        request.side.value.encode("utf-8"),
        request.quantity.value.to_bytes(8, "big"),
        request.economic_scope,
        b""
        if request.target_leg_key is None
        else _commit_parts(
            b"execution-core/acquisition-authority/protective-target-leg/v1",
            request.target_leg_key.broker.value.encode("utf-8"),
            request.target_leg_key.environment.value.encode("utf-8"),
            request.target_leg_key.account.value.encode("utf-8"),
            request.target_leg_key.order_id.value.encode("utf-8"),
        ),
    )


def _acquisition_exit_permit_commitment(
    *,
    input_id: AuthorityInputId,
    purpose: _AcquisitionExitPurpose,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    predecessor_controller_head: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    execution_snapshot_commitment: bytes,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_context_commitment: bytes,
    predecessor_protection_commitment: bytes | None,
    protection_commitment: bytes,
    residual_quantity: Quantity,
    target_effect_id: EffectId | None,
    protective_request: BrokerEffectRequest | None,
    intent_commitment: bytes,
) -> bytes:
    if (
        type(input_id) is not AuthorityInputId
        or type(purpose) is not _AcquisitionExitPurpose
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(session_id) is not SessionId
        or not _acquisition_generation_id_is_canonical(generation_id)
        or type(acquisition_mandate_id) is not AcquisitionMandateId
        or type(protection_mandate_id) is not MandateId
        or type(successor_ordinal) is not int
        or successor_ordinal < 0
        or successor_ordinal > 2**64 - 1
        or type(residual_quantity) is not Quantity
        or residual_quantity.value <= 0
        or (target_effect_id is not None and type(target_effect_id) is not EffectId)
        or not _optional_digest_is_exact(predecessor_protection_commitment)
        or (
            protective_request is not None
            and type(protective_request) is not BrokerEffectRequest
        )
    ):
        raise TypeError("acquisition exit permit requires exact owner values")
    for digest in (
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        predecessor_controller_head,
        controller_head,
        execution_snapshot_commitment,
        scope_execution_commitment,
        venue_commitment,
        authority_context_commitment,
        protection_commitment,
        intent_commitment,
    ):
        _require_digest("acquisition exit permit commitment", digest)
    return _commit_parts(
        b"execution-core/acquisition-authority/exit-permit/v2",
        input_id.value.encode("utf-8"),
        purpose.value.encode("utf-8"),
        application_generation_id.value.encode("utf-8"),
        position_scope.broker.value.encode("utf-8"),
        position_scope.environment.value.encode("utf-8"),
        position_scope.account.value.encode("utf-8"),
        position_scope.symbol_id.value.encode("utf-8"),
        session_id.value.encode("utf-8"),
        generation_id.value.encode("utf-8"),
        acquisition_mandate_id.value.encode("utf-8"),
        protection_mandate_id.value.encode("utf-8"),
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        predecessor_controller_head,
        controller_head,
        successor_ordinal.to_bytes(8, "big"),
        execution_snapshot_commitment,
        scope_execution_commitment,
        venue_commitment,
        authority_context_commitment,
        b""
        if predecessor_protection_commitment is None
        else predecessor_protection_commitment,
        protection_commitment,
        residual_quantity.value.to_bytes(8, "big"),
        b"" if target_effect_id is None else target_effect_id.value.encode("utf-8"),
        _protective_request_commitment(protective_request),
        intent_commitment,
    )


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionExitPermit:
    """Opaque purpose-bound capability for one BUY preemption or SELL exit."""

    input_id: AuthorityInputId = field(init=False)
    purpose: _AcquisitionExitPurpose = field(init=False)
    application_generation_id: ApplicationGenerationId = field(init=False)
    position_scope: PositionScope = field(init=False)
    session_id: SessionId = field(init=False)
    generation_id: AcquisitionGenerationId = field(init=False)
    acquisition_mandate_id: AcquisitionMandateId = field(init=False)
    protection_mandate_id: MandateId = field(init=False)
    binding_commitment: bytes = field(init=False)
    emergency_recovery_compatibility_commitment: bytes = field(init=False)
    predecessor_controller_head: bytes = field(init=False)
    controller_head: bytes = field(init=False)
    successor_ordinal: int = field(init=False)
    execution_snapshot_commitment: bytes = field(init=False)
    scope_execution_commitment: bytes = field(init=False)
    venue_commitment: bytes = field(init=False)
    authority_context_commitment: bytes = field(init=False)
    predecessor_protection_commitment: bytes | None = field(init=False)
    protection_commitment: bytes = field(init=False)
    residual_quantity: Quantity = field(init=False)
    target_effect_id: EffectId | None = field(init=False)
    protective_request: BrokerEffectRequest | None = field(init=False, repr=False)
    intent_commitment: bytes = field(init=False)
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionExitPermit is authority-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionExitPermit cannot be subclassed")


def _new_acquisition_exit_permit(
    *,
    input_id: AuthorityInputId,
    purpose: _AcquisitionExitPurpose,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    predecessor_controller_head: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    execution_snapshot_commitment: bytes,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_context_commitment: bytes,
    predecessor_protection_commitment: bytes | None,
    protection_commitment: bytes,
    residual_quantity: Quantity,
    target_effect_id: EffectId | None,
    protective_request: BrokerEffectRequest | None,
    intent_commitment: bytes,
) -> AcquisitionExitPermit:
    values = (
        ("input_id", input_id),
        ("purpose", purpose),
        ("application_generation_id", application_generation_id),
        ("position_scope", position_scope),
        ("session_id", session_id),
        ("generation_id", generation_id),
        ("acquisition_mandate_id", acquisition_mandate_id),
        ("protection_mandate_id", protection_mandate_id),
        ("binding_commitment", binding_commitment),
        (
            "emergency_recovery_compatibility_commitment",
            emergency_recovery_compatibility_commitment,
        ),
        ("predecessor_controller_head", predecessor_controller_head),
        ("controller_head", controller_head),
        ("successor_ordinal", successor_ordinal),
        ("execution_snapshot_commitment", execution_snapshot_commitment),
        ("scope_execution_commitment", scope_execution_commitment),
        ("venue_commitment", venue_commitment),
        ("authority_context_commitment", authority_context_commitment),
        ("predecessor_protection_commitment", predecessor_protection_commitment),
        ("protection_commitment", protection_commitment),
        ("residual_quantity", residual_quantity),
        ("target_effect_id", target_effect_id),
        ("protective_request", protective_request),
        ("intent_commitment", intent_commitment),
    )
    commitment = _acquisition_exit_permit_commitment(
        input_id=input_id,
        purpose=purpose,
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        session_id=session_id,
        generation_id=generation_id,
        acquisition_mandate_id=acquisition_mandate_id,
        protection_mandate_id=protection_mandate_id,
        binding_commitment=binding_commitment,
        emergency_recovery_compatibility_commitment=(
            emergency_recovery_compatibility_commitment
        ),
        predecessor_controller_head=predecessor_controller_head,
        controller_head=controller_head,
        successor_ordinal=successor_ordinal,
        execution_snapshot_commitment=execution_snapshot_commitment,
        scope_execution_commitment=scope_execution_commitment,
        venue_commitment=venue_commitment,
        authority_context_commitment=authority_context_commitment,
        predecessor_protection_commitment=predecessor_protection_commitment,
        protection_commitment=protection_commitment,
        residual_quantity=residual_quantity,
        target_effect_id=target_effect_id,
        protective_request=protective_request,
        intent_commitment=intent_commitment,
    )
    result = object.__new__(AcquisitionExitPermit)
    for name, value in (*values, ("commitment", commitment)):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition-authority/exit-permit-seal/v2",
            commitment,
        ),
    )
    return result


def _acquisition_exit_permit_is_authentic(
    value: object,
) -> TypeGuard[AcquisitionExitPermit]:
    if type(value) is not AcquisitionExitPermit:
        return False
    try:
        commitment = _acquisition_exit_permit_commitment(
            input_id=value.input_id,
            purpose=value.purpose,
            application_generation_id=value.application_generation_id,
            position_scope=value.position_scope,
            session_id=value.session_id,
            generation_id=value.generation_id,
            acquisition_mandate_id=value.acquisition_mandate_id,
            protection_mandate_id=value.protection_mandate_id,
            binding_commitment=value.binding_commitment,
            emergency_recovery_compatibility_commitment=(
                value.emergency_recovery_compatibility_commitment
            ),
            predecessor_controller_head=value.predecessor_controller_head,
            controller_head=value.controller_head,
            successor_ordinal=value.successor_ordinal,
            execution_snapshot_commitment=value.execution_snapshot_commitment,
            scope_execution_commitment=value.scope_execution_commitment,
            venue_commitment=value.venue_commitment,
            authority_context_commitment=value.authority_context_commitment,
            predecessor_protection_commitment=(value.predecessor_protection_commitment),
            protection_commitment=value.protection_commitment,
            residual_quantity=value.residual_quantity,
            target_effect_id=value.target_effect_id,
            protective_request=value.protective_request,
            intent_commitment=value.intent_commitment,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return bool(
        value.commitment == commitment
        and value._seal
        == _commit_parts(
            b"execution-core/acquisition-authority/exit-permit-seal/v2",
            commitment,
        )
    )


@dataclass(frozen=True, slots=True, init=False)
class _AcquisitionFactPreemption:
    """One sealed private command for the ordered fact-plus-BUY mutation."""

    input_id: AuthorityInputId = field(init=False)
    permit: AcquisitionExitPermit = field(init=False, repr=False)
    _fact_transition: VenueRecoveryTransition = field(init=False, repr=False)
    _fact_projection: AcquisitionVenueProjection = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("fact-preemption commands are authority-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("fact-preemption commands cannot be subclassed")


def _acquisition_fact_preemption_seal(
    input_id: AuthorityInputId,
    permit: AcquisitionExitPermit,
    fact_transition: VenueRecoveryTransition,
    fact_projection: AcquisitionVenueProjection,
) -> bytes:
    if (
        type(input_id) is not AuthorityInputId
        or not _acquisition_exit_permit_is_authentic(permit)
        or type(fact_transition) is not VenueRecoveryTransition
        or type(fact_projection) is not AcquisitionVenueProjection
    ):
        raise TypeError("fact-preemption command requires exact owner values")
    return _commit_parts(
        b"execution-core/acquisition-authority/fact-preemption/v1",
        input_id.value.encode("utf-8"),
        permit.commitment,
        fact_transition._protection_proof_commitment,
        fact_projection.source_commitment,
    )


def _new_acquisition_fact_preemption(
    *,
    input_id: AuthorityInputId,
    permit: AcquisitionExitPermit,
    fact_transition: VenueRecoveryTransition,
    fact_projection: AcquisitionVenueProjection,
) -> _AcquisitionFactPreemption:
    result = object.__new__(_AcquisitionFactPreemption)
    for name, value in (
        ("input_id", input_id),
        ("permit", permit),
        ("_fact_transition", fact_transition),
        ("_fact_projection", fact_projection),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _acquisition_fact_preemption_seal(
            input_id,
            permit,
            fact_transition,
            fact_projection,
        ),
    )
    return result


def _acquisition_fact_preemption_is_authentic(
    value: object,
) -> TypeGuard[_AcquisitionFactPreemption]:
    if type(value) is not _AcquisitionFactPreemption:
        return False
    try:
        return bool(
            value._seal
            == _acquisition_fact_preemption_seal(
                value.input_id,
                value.permit,
                value._fact_transition,
                value._fact_projection,
            )
        )
    except (AttributeError, TypeError, ValueError):
        return False


@dataclass(frozen=True, slots=True, init=False)
class _AcquisitionEffectDescriptor:
    """Direct opaque terms/identity record indexed by scope and effect ID."""

    permit: AcquisitionEffectPermit = field(init=False, repr=False)
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("acquisition effect descriptors are authority-constructed only")


def _new_acquisition_effect_descriptor(
    permit: AcquisitionEffectPermit,
) -> _AcquisitionEffectDescriptor:
    if not _acquisition_effect_permit_is_authentic(permit):
        raise TypeError("acquisition descriptor requires an authentic permit")
    commitment = _commit_parts(
        b"execution-core/acquisition-authority/effect-descriptor/v1",
        permit.commitment,
    )
    result = object.__new__(_AcquisitionEffectDescriptor)
    object.__setattr__(result, "permit", permit)
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition-authority/effect-descriptor-seal/v1",
            commitment,
        ),
    )
    return result


def _acquisition_effect_descriptor_is_authentic(
    value: object,
) -> TypeGuard[_AcquisitionEffectDescriptor]:
    if type(value) is not _AcquisitionEffectDescriptor:
        return False
    try:
        permit = value.permit
        commitment = value.commitment
        seal = value._seal
    except AttributeError:
        return False
    return bool(
        _acquisition_effect_permit_is_authentic(permit)
        and type(commitment) is bytes
        and len(commitment) == 32
        and commitment
        == _commit_parts(
            b"execution-core/acquisition-authority/effect-descriptor/v1",
            permit.commitment,
        )
        and type(seal) is bytes
        and len(seal) == 32
        and seal
        == _commit_parts(
            b"execution-core/acquisition-authority/effect-descriptor-seal/v1",
            commitment,
        )
    )


@dataclass(frozen=True, slots=True, init=False)
class _AcquisitionActiveEffect:
    """Current serving record; completion handling is admitted in a later route."""

    effect_id: EffectId = field(init=False)
    descriptor_commitment: bytes = field(init=False)
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("acquisition active records are authority-constructed only")


def _new_acquisition_active_effect(
    descriptor: _AcquisitionEffectDescriptor,
) -> _AcquisitionActiveEffect:
    if not _acquisition_effect_descriptor_is_authentic(descriptor):
        raise TypeError("acquisition active record requires a descriptor")
    permit = descriptor.permit
    commitment = _commit_parts(
        b"execution-core/acquisition-authority/active-effect/v1",
        permit.effect_id.value.encode("utf-8"),
        descriptor.commitment,
    )
    result = object.__new__(_AcquisitionActiveEffect)
    object.__setattr__(result, "effect_id", permit.effect_id)
    object.__setattr__(result, "descriptor_commitment", descriptor.commitment)
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition-authority/active-effect-seal/v1",
            commitment,
        ),
    )
    return result


def _acquisition_active_effect_is_authentic(
    value: object,
) -> TypeGuard[_AcquisitionActiveEffect]:
    if type(value) is not _AcquisitionActiveEffect:
        return False
    try:
        effect_id = value.effect_id
        descriptor_commitment = value.descriptor_commitment
        commitment = value.commitment
        seal = value._seal
    except AttributeError:
        return False
    if (
        type(effect_id) is not EffectId
        or type(descriptor_commitment) is not bytes
        or len(descriptor_commitment) != 32
        or type(commitment) is not bytes
        or len(commitment) != 32
        or type(seal) is not bytes
        or len(seal) != 32
    ):
        return False
    return bool(
        commitment
        == _commit_parts(
            b"execution-core/acquisition-authority/active-effect/v1",
            effect_id.value.encode("utf-8"),
            descriptor_commitment,
        )
        and seal
        == _commit_parts(
            b"execution-core/acquisition-authority/active-effect-seal/v1",
            commitment,
        )
    )


@dataclass(frozen=True, slots=True, init=False)
class _AcquisitionInactiveSlot:
    """Sealed non-serving scope pointer retained across serial generations."""

    predecessor_effect_id: EffectId = field(init=False)
    predecessor_descriptor_commitment: bytes = field(init=False)
    successor_generation_id: AcquisitionGenerationId = field(init=False)
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("acquisition inactive slots are authority-constructed only")


def _new_acquisition_inactive_slot(
    active: _AcquisitionActiveEffect,
    descriptor: _AcquisitionEffectDescriptor,
    successor_generation_id: AcquisitionGenerationId,
) -> _AcquisitionInactiveSlot:
    if (
        not _acquisition_active_effect_is_authentic(active)
        or not _acquisition_effect_descriptor_is_authentic(descriptor)
        or active.effect_id != descriptor.permit.effect_id
        or active.descriptor_commitment != descriptor.commitment
        or not _acquisition_generation_id_is_canonical(successor_generation_id)
    ):
        raise TypeError("inactive acquisition slot requires exact terminal inputs")
    commitment = _commit_parts(
        b"execution-core/acquisition-authority/inactive-slot/v1",
        active.effect_id.value.encode("utf-8"),
        descriptor.commitment,
        successor_generation_id.value.encode("utf-8"),
    )
    result = object.__new__(_AcquisitionInactiveSlot)
    object.__setattr__(result, "predecessor_effect_id", active.effect_id)
    object.__setattr__(
        result,
        "predecessor_descriptor_commitment",
        descriptor.commitment,
    )
    object.__setattr__(result, "successor_generation_id", successor_generation_id)
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition-authority/inactive-slot-seal/v1",
            commitment,
        ),
    )
    return result


def _acquisition_inactive_slot_is_authentic(
    value: object,
) -> TypeGuard[_AcquisitionInactiveSlot]:
    if type(value) is not _AcquisitionInactiveSlot:
        return False
    try:
        commitment = _commit_parts(
            b"execution-core/acquisition-authority/inactive-slot/v1",
            value.predecessor_effect_id.value.encode("utf-8"),
            value.predecessor_descriptor_commitment,
            value.successor_generation_id.value.encode("utf-8"),
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return bool(
        type(value.predecessor_effect_id) is EffectId
        and type(value.predecessor_descriptor_commitment) is bytes
        and len(value.predecessor_descriptor_commitment) == 32
        and _acquisition_generation_id_is_canonical(value.successor_generation_id)
        and value.commitment == commitment
        and value._seal
        == _commit_parts(
            b"execution-core/acquisition-authority/inactive-slot-seal/v1",
            commitment,
        )
    )


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionEffectView:
    """Bounded, authority-free readback for one sealed acquisition request."""

    effect_id: EffectId = field(init=False)
    request_occurrence_id: RequestOccurrenceId = field(init=False)
    client_order_id: ClientOrderId = field(init=False)
    position_scope: PositionScope = field(init=False)
    generation_id: AcquisitionGenerationId = field(init=False)
    binding_commitment: bytes = field(init=False)
    controller_head: bytes = field(init=False)
    terms: AcquisitionEffectTerms = field(init=False)
    terms_commitment: bytes = field(init=False)
    economic_scope: bytes = field(init=False)
    serving: bool = field(init=False)
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionEffectView is authority-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionEffectView cannot be subclassed")


def _new_acquisition_effect_view(
    descriptor: _AcquisitionEffectDescriptor,
    *,
    serving: bool,
) -> AcquisitionEffectView:
    if (
        not _acquisition_effect_descriptor_is_authentic(descriptor)
        or type(serving) is not bool
    ):
        raise TypeError("acquisition effect view requires exact owner state")
    permit = descriptor.permit
    commitment = _commit_parts(
        b"execution-core/acquisition-authority/effect-view/v1",
        descriptor.commitment,
        b"1" if serving else b"0",
    )
    result = object.__new__(AcquisitionEffectView)
    for name, value in (
        ("effect_id", permit.effect_id),
        ("request_occurrence_id", permit.request_occurrence_id),
        ("client_order_id", permit.client_order_id),
        ("position_scope", permit.position_scope),
        ("generation_id", permit.generation_id),
        ("binding_commitment", permit.binding_commitment),
        ("controller_head", permit.controller_head),
        ("terms", permit.terms),
        ("terms_commitment", permit.terms.commitment),
        ("economic_scope", permit.terms.commitment),
        ("serving", serving),
        ("commitment", commitment),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition-authority/effect-view-seal/v1",
            commitment,
        ),
    )
    return result


def _acquisition_authority_context_commitment(
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_commitment: bytes,
) -> bytes:
    """Commit durable target semantics, excluding transient serving status."""

    return _commit_parts(
        b"execution-core/acquisition-authority/context-seal/v1",
        application_generation_id.value.encode("utf-8"),
        position_scope.broker.value.encode("utf-8"),
        position_scope.environment.value.encode("utf-8"),
        position_scope.account.value.encode("utf-8"),
        position_scope.symbol_id.value.encode("utf-8"),
        scope_execution_commitment,
        venue_commitment,
        authority_commitment,
    )


def _acquisition_authority_context_seal(
    commitment: bytes,
    source_execution_commitment: bytes,
    serving: bool,
) -> bytes:
    """Bind the semantic context to one exact raw source and serving result."""

    return _commit_parts(
        b"execution-core/acquisition-authority/context-proof/v2",
        commitment,
        source_execution_commitment,
        b"1" if serving else b"0",
    )


def _new_acquisition_authority_context(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    venue_context: AcquisitionVenueContext,
    serving: bool,
) -> AcquisitionAuthorityContext:
    application_generation_id = state.venue.scope.generation
    authority_commitment = _acquisition_authority_commitment(
        state,
        application_generation_id,
        venue_context.position_scope,
    )
    if authority_commitment is None:
        authority_commitment = _commit_parts(
            b"execution-core/acquisition-authority/invalid-context/v1"
        )
        serving = False
    commitment = _acquisition_authority_context_commitment(
        application_generation_id,
        venue_context.position_scope,
        venue_context.scope_execution_commitment,
        venue_context.commitment,
        authority_commitment,
    )
    result = object.__new__(AcquisitionAuthorityContext)
    object.__setattr__(result, "application_generation_id", application_generation_id)
    object.__setattr__(result, "position_scope", venue_context.position_scope)
    object.__setattr__(
        result,
        "scope_execution_commitment",
        venue_context.scope_execution_commitment,
    )
    object.__setattr__(result, "venue_commitment", venue_context.commitment)
    object.__setattr__(result, "authority_commitment", authority_commitment)
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(result, "_source_execution_commitment", execution.commitment)
    object.__setattr__(result, "_serving", serving)
    object.__setattr__(
        result,
        "_seal",
        _acquisition_authority_context_seal(
            commitment,
            execution.commitment,
            serving,
        ),
    )
    return result


def _acquisition_authority_context_is_authentic(
    value: object,
) -> TypeGuard[AcquisitionAuthorityContext]:
    if type(value) is not AcquisitionAuthorityContext:
        return False
    try:
        application_generation_id = value.application_generation_id
        position_scope = value.position_scope
        scope_execution_commitment = value.scope_execution_commitment
        venue_commitment = value.venue_commitment
        authority_commitment = value.authority_commitment
        commitment = value.commitment
        source_execution_commitment = value._source_execution_commitment
        serving = value._serving
        seal = value._seal
    except AttributeError:
        return False
    if (
        type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(serving) is not bool
    ):
        return False
    for digest in (
        scope_execution_commitment,
        venue_commitment,
        authority_commitment,
        commitment,
        source_execution_commitment,
        seal,
    ):
        if type(digest) is not bytes or len(digest) != 32:
            return False
    return commitment == _acquisition_authority_context_commitment(
        application_generation_id,
        position_scope,
        scope_execution_commitment,
        venue_commitment,
        authority_commitment,
    ) and seal == _acquisition_authority_context_seal(
        commitment,
        source_execution_commitment,
        serving,
    )


def project_acquisition_authority_context(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    venue_context: AcquisitionVenueContext,
) -> AcquisitionAuthorityContext:
    """Project one direct per-scope authority context with no map exposure."""

    exact = _validate_authority_state(state)
    _require("execution", execution, ExecutionSnapshot)
    _require("venue_context", venue_context, AcquisitionVenueContext)
    scope = venue_context.position_scope
    scope_matches = (
        scope.broker == exact.venue.scope.broker
        and scope.environment == exact.venue.scope.environment
        and scope.account == exact.venue.scope.account
    )
    serving = bool(
        scope_matches
        and venue_context.matches_current(
            exact.venue,
            execution,
            exact.venue.scope.generation,
            scope,
        )
    )
    return _new_acquisition_authority_context(
        exact,
        execution,
        venue_context,
        serving,
    )


def _acquisition_admission_source_commitment(
    kind: AcquisitionAdmissionKind,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_commitment: bytes,
    currentness_commitment: bytes,
    descriptor_commitment: bytes,
    active_commitment: bytes,
    manual_flatten_commitment: bytes,
) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-authority/admission-source/v1",
        kind.value.encode("utf-8"),
        application_generation_id.value.encode("utf-8"),
        position_scope.broker.value.encode("utf-8"),
        position_scope.environment.value.encode("utf-8"),
        position_scope.account.value.encode("utf-8"),
        position_scope.symbol_id.value.encode("utf-8"),
        scope_execution_commitment,
        venue_commitment,
        authority_commitment,
        currentness_commitment,
        descriptor_commitment,
        active_commitment,
        manual_flatten_commitment,
    )


def _acquisition_admission_seal(
    kind: AcquisitionAdmissionKind,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_commitment: bytes,
    source_commitment: bytes,
    slot_key: bytes,
    serving: bool,
) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-authority/admission-seal/v1",
        kind.value.encode("utf-8"),
        application_generation_id.value.encode("utf-8"),
        position_scope.broker.value.encode("utf-8"),
        position_scope.environment.value.encode("utf-8"),
        position_scope.account.value.encode("utf-8"),
        position_scope.symbol_id.value.encode("utf-8"),
        scope_execution_commitment,
        venue_commitment,
        authority_commitment,
        source_commitment,
        slot_key,
        b"1" if serving else b"0",
    )


def _new_acquisition_admission_projection(
    *,
    kind: AcquisitionAdmissionKind,
    authority: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    venue_context: AcquisitionVenueContext,
    authority_context: AcquisitionAuthorityContext,
    slot_key: bytes,
    source_commitment: bytes,
    serving: bool,
) -> AcquisitionAdmissionProjection:
    if (
        type(kind) is not AcquisitionAdmissionKind
        or type(authority) is not ExecutionAuthorityState
        or type(execution) is not ExecutionSnapshot
        or type(venue_context) is not AcquisitionVenueContext
        or not _acquisition_authority_context_is_authentic(authority_context)
        or type(slot_key) is not bytes
        or len(slot_key) != 32
        or type(source_commitment) is not bytes
        or len(source_commitment) != 32
        or type(serving) is not bool
    ):
        raise TypeError("acquisition admission requires exact owner inputs")
    result = object.__new__(AcquisitionAdmissionProjection)
    object.__setattr__(result, "kind", kind)
    object.__setattr__(
        result,
        "application_generation_id",
        authority_context.application_generation_id,
    )
    object.__setattr__(result, "position_scope", authority_context.position_scope)
    object.__setattr__(
        result,
        "scope_execution_commitment",
        authority_context.scope_execution_commitment,
    )
    object.__setattr__(result, "venue_commitment", authority_context.venue_commitment)
    object.__setattr__(
        result,
        "authority_commitment",
        authority_context.authority_commitment,
    )
    object.__setattr__(result, "source_commitment", source_commitment)
    object.__setattr__(result, "_authority", authority)
    object.__setattr__(result, "_execution", execution)
    object.__setattr__(result, "_venue_context", venue_context)
    object.__setattr__(result, "_authority_context", authority_context)
    object.__setattr__(result, "_slot_key", slot_key)
    object.__setattr__(result, "_serving", serving)
    object.__setattr__(
        result,
        "_seal",
        _acquisition_admission_seal(
            kind,
            authority_context.application_generation_id,
            authority_context.position_scope,
            authority_context.scope_execution_commitment,
            authority_context.venue_commitment,
            authority_context.authority_commitment,
            source_commitment,
            slot_key,
            serving,
        ),
    )
    return result


def _acquisition_admission_is_authentic(
    value: object,
) -> TypeGuard[AcquisitionAdmissionProjection]:
    if type(value) is not AcquisitionAdmissionProjection:
        return False
    try:
        kind = value.kind
        application_generation_id = value.application_generation_id
        position_scope = value.position_scope
        scope_execution_commitment = value.scope_execution_commitment
        venue_commitment = value.venue_commitment
        authority_commitment = value.authority_commitment
        source_commitment = value.source_commitment
        authority = value._authority
        execution = value._execution
        venue_context = value._venue_context
        authority_context = value._authority_context
        slot_key = value._slot_key
        serving = value._serving
        seal = value._seal
    except AttributeError:
        return False
    if (
        type(kind) is not AcquisitionAdmissionKind
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(authority) is not ExecutionAuthorityState
        or type(execution) is not ExecutionSnapshot
        or type(venue_context) is not AcquisitionVenueContext
        or not _acquisition_authority_context_is_authentic(authority_context)
        or type(serving) is not bool
    ):
        return False
    for digest in (
        scope_execution_commitment,
        venue_commitment,
        authority_commitment,
        source_commitment,
        slot_key,
        seal,
    ):
        if type(digest) is not bytes or len(digest) != 32:
            return False
    return bool(
        authority_context.application_generation_id == application_generation_id
        and authority_context.position_scope == position_scope
        and authority_context.scope_execution_commitment == scope_execution_commitment
        and authority_context.venue_commitment == venue_commitment
        and authority_context.authority_commitment == authority_commitment
        and slot_key
        == _acquisition_scope_key(application_generation_id, position_scope)
        and seal
        == _acquisition_admission_seal(
            kind,
            application_generation_id,
            position_scope,
            scope_execution_commitment,
            venue_commitment,
            authority_commitment,
            source_commitment,
            slot_key,
            serving,
        )
    )


def project_acquisition_admission(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    position_scope: PositionScope,
) -> AcquisitionAdmissionProjection:
    """Project one bounded target admission proof without exposing authority maps."""

    exact = _validate_authority_state(state)
    _require("execution", execution, ExecutionSnapshot)
    _require("position_scope", position_scope, PositionScope)
    application_generation_id = exact.venue.scope.generation
    slot_key = _acquisition_scope_key(application_generation_id, position_scope)
    venue_context = exact.venue.project_acquisition_context(execution, position_scope)
    authority_context = project_acquisition_authority_context(
        exact,
        execution,
        venue_context,
    )
    currentness = exact._acquisition_currentness_by_scope.get(slot_key)
    descriptor = exact._acquisition_descriptor_by_scope.get(slot_key)
    active = exact._acquisition_active_by_scope.get(slot_key)
    manual_flatten = exact._manual_flatten_by_scope.get(slot_key)
    currentness_commitment = _currentness_entry_commitment(currentness)
    descriptor_commitment = _descriptor_entry_commitment(descriptor)
    active_commitment = _active_entry_commitment(active)
    manual_flatten_commitment = _manual_flatten_entry_commitment(manual_flatten)
    commitments = (
        currentness_commitment,
        descriptor_commitment,
        active_commitment,
        manual_flatten_commitment,
    )
    all_direct_entries_are_exact = all(item is not None for item in commitments)
    empty = bool(
        currentness is None
        and descriptor is None
        and active is None
        and manual_flatten is None
    )
    inactive = bool(
        _acquisition_inactive_slot_is_authentic(descriptor)
        and descriptor is active
        and _acquisition_currentness_entry_is_authentic(currentness)
        and descriptor.successor_generation_id == currentness.generation_id
    )
    terminal = False
    if (
        _acquisition_currentness_entry_is_authentic(currentness)
        and _acquisition_effect_descriptor_is_authentic(descriptor)
        and _acquisition_active_effect_is_authentic(active)
        and active.effect_id == descriptor.permit.effect_id
        and active.descriptor_commitment == descriptor.commitment
        and descriptor.permit.generation_id == currentness.generation_id
    ):
        view = _venue_authority_view(
            exact.venue,
            execution,
            position_scope,
            active.effect_id,
        )
        terminal = bool(
            execution.position.raw_quantity == 0
            and execution.integrity is PositionIntegrity.CONSISTENT
            and not execution.account_reconciliation_required
            and view.execution_binding_matches
            and view.account_reconciliation_clear
            and view.blocking_effect_count == 0
            and view.blocking_buy_effect_count == 0
            and view.stand_downable_buy_count == 0
            and view.known_cancellable_buy_leg_count == 0
            and view.known_cancel_pending_buy_leg_count == 0
            and view.waiting_buy_parent_count == 0
            and view.unknown_buy_effect_count == 0
        )
    kind = (
        AcquisitionAdmissionKind.GENESIS_EMPTY
        if empty
        else AcquisitionAdmissionKind.SUCCESSOR
    )
    serving = bool(
        all_direct_entries_are_exact
        and venue_context.matches_current(
            exact.venue,
            execution,
            application_generation_id,
            position_scope,
        )
        and authority_context.matches_current(exact, execution, venue_context)
        and manual_flatten is None
        and (
            empty
            or inactive
            or terminal
            or (currentness is not None and active is None)
        )
    )
    source_commitment = _acquisition_admission_source_commitment(
        kind,
        application_generation_id,
        position_scope,
        authority_context.scope_execution_commitment,
        authority_context.venue_commitment,
        authority_context.authority_commitment,
        cast(bytes, currentness_commitment)
        if currentness_commitment is not None
        else b"",
        cast(bytes, descriptor_commitment)
        if descriptor_commitment is not None
        else b"",
        cast(bytes, active_commitment) if active_commitment is not None else b"",
        cast(bytes, manual_flatten_commitment)
        if manual_flatten_commitment is not None
        else b"",
    )
    return _new_acquisition_admission_projection(
        kind=kind,
        authority=exact,
        execution=execution,
        venue_context=venue_context,
        authority_context=authority_context,
        slot_key=slot_key,
        source_commitment=source_commitment,
        serving=serving,
    )


def project_acquisition_effect(
    state: ExecutionAuthorityState,
    effect_id: EffectId,
) -> AcquisitionEffectView | None:
    """Return one direct, bounded acquisition effect projection if retained."""

    exact = _validate_authority_state(state)
    _require("effect_id", effect_id, EffectId)
    descriptor = exact._acquisition_descriptor_by_effect.get(_effect_key(effect_id))
    if not _acquisition_effect_descriptor_is_authentic(descriptor):
        return None
    permit = descriptor.permit
    slot_key = _acquisition_scope_key(
        permit.application_generation_id,
        permit.position_scope,
    )
    currentness = exact._acquisition_currentness_by_scope.get(slot_key)
    active = exact._acquisition_active_by_scope.get(slot_key)
    authorization = exact._effect_authority_by_id.get(_effect_key(effect_id))
    effect = exact.venue._current_effect(effect_id)
    serving = bool(
        exact._acquisition_descriptor_by_scope.get(slot_key) is descriptor
        and _acquisition_currentness_entry_is_authentic(currentness)
        and currentness.source_kind
        is _AcquisitionCurrentnessSourceKind.AUTHORITY_MUTATION
        and currentness.application_generation_id == permit.application_generation_id
        and currentness.position_scope == permit.position_scope
        and currentness.generation_id == permit.generation_id
        and currentness.binding_commitment == permit.binding_commitment
        and currentness.controller_head == permit.controller_head
        and _acquisition_active_effect_is_authentic(active)
        and active.effect_id == effect_id
        and active.descriptor_commitment == descriptor.commitment
        and type(authorization) is _EffectAuthorization
        and authorization.request.effect_id == effect_id
        and authorization.request.request_occurrence_id == permit.request_occurrence_id
        and authorization.request.client_order_id == permit.client_order_id
        and authorization.request.mandate_id == permit.protection_mandate_id
        and effect is not None
        and effect.scope.effect_id == effect_id
        and effect.scope.request_occurrence_id == permit.request_occurrence_id
        and effect.scope.client_order_id == permit.client_order_id
        and effect.scope.mandate_id == permit.protection_mandate_id
        and effect.scope.position_scope == permit.position_scope
        and exact._claim_by_effect.get(_effect_key(effect_id)) is None
    )
    return _new_acquisition_effect_view(descriptor, serving=serving)


def _acquisition_context_refresh_commitment(
    disposition: AcquisitionContextRefreshDisposition,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    source_execution_snapshot_commitment: bytes | None,
    predecessor_execution_snapshot_commitment: bytes | None,
    execution_snapshot_commitment: bytes | None,
    predecessor_scope_execution_commitment: bytes | None,
    scope_execution_commitment: bytes | None,
    predecessor_venue_commitment: bytes | None,
    venue_commitment: bytes | None,
    predecessor_authority_commitment: bytes | None,
    authority_commitment: bytes | None,
    transition_proof_commitment: bytes | None,
) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-authority/refresh/v2",
        disposition.value.encode("utf-8"),
        application_generation_id.value.encode("utf-8"),
        position_scope.broker.value.encode("utf-8"),
        position_scope.environment.value.encode("utf-8"),
        position_scope.account.value.encode("utf-8"),
        position_scope.symbol_id.value.encode("utf-8"),
        source_execution_snapshot_commitment or b"",
        predecessor_execution_snapshot_commitment or b"",
        execution_snapshot_commitment or b"",
        predecessor_scope_execution_commitment or b"",
        scope_execution_commitment or b"",
        predecessor_venue_commitment or b"",
        venue_commitment or b"",
        predecessor_authority_commitment or b"",
        authority_commitment or b"",
        transition_proof_commitment or b"",
    )


def _acquisition_context_refresh_seal(commitment: bytes) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-authority/refresh-seal/v2",
        commitment,
    )


def _new_acquisition_context_refresh(
    *,
    disposition: AcquisitionContextRefreshDisposition,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    source_execution: ExecutionSnapshot | None,
    predecessor_authority: ExecutionAuthorityState | None,
    predecessor_execution: ExecutionSnapshot | None,
    predecessor_venue_context: AcquisitionVenueContext | None,
    predecessor_authority_context: AcquisitionAuthorityContext | None,
    authority: ExecutionAuthorityState | None,
    execution: ExecutionSnapshot | None,
    venue_context: AcquisitionVenueContext | None,
    authority_context: AcquisitionAuthorityContext | None,
    venue_transitions: tuple[VenueRecoveryTransition, ...],
) -> AcquisitionContextRefresh:
    if (
        type(disposition) is not AcquisitionContextRefreshDisposition
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(venue_transitions) is not tuple
    ):
        raise TypeError("acquisition context refresh requires exact owner inputs")
    transition_proof_commitment: bytes | None
    if len(venue_transitions) == 0:
        transition_proof_commitment = None
    elif (
        len(venue_transitions) == 1
        and type(venue_transitions[0]) is VenueRecoveryTransition
    ):
        transition_proof_commitment = venue_transitions[0]._protection_proof_commitment
        if (
            type(transition_proof_commitment) is not bytes
            or len(transition_proof_commitment) != 32
        ):
            raise TypeError("acquisition refresh transition proof is invalid")
    else:
        raise TypeError("acquisition refresh permits at most one transition")
    source_commitment = (
        None if source_execution is None else source_execution.commitment
    )
    predecessor_scope = (
        None
        if predecessor_venue_context is None
        else predecessor_venue_context.scope_execution_commitment
    )
    current_scope = (
        None if venue_context is None else venue_context.scope_execution_commitment
    )
    predecessor_venue = (
        None
        if predecessor_venue_context is None
        else predecessor_venue_context.commitment
    )
    current_venue = None if venue_context is None else venue_context.commitment
    predecessor_authority_commitment = (
        None
        if predecessor_authority_context is None
        else predecessor_authority_context.authority_commitment
    )
    current_authority_commitment = (
        None if authority_context is None else authority_context.authority_commitment
    )
    commitment = _acquisition_context_refresh_commitment(
        disposition,
        application_generation_id,
        position_scope,
        source_commitment,
        None if predecessor_execution is None else predecessor_execution.commitment,
        None if execution is None else execution.commitment,
        predecessor_scope,
        current_scope,
        predecessor_venue,
        current_venue,
        predecessor_authority_commitment,
        current_authority_commitment,
        transition_proof_commitment,
    )
    result = object.__new__(AcquisitionContextRefresh)
    object.__setattr__(result, "disposition", disposition)
    object.__setattr__(result, "application_generation_id", application_generation_id)
    object.__setattr__(result, "position_scope", position_scope)
    object.__setattr__(
        result, "source_execution_snapshot_commitment", source_commitment
    )
    object.__setattr__(result, "_source_execution", source_execution)
    object.__setattr__(
        result,
        "predecessor_execution_snapshot_commitment",
        None if predecessor_execution is None else predecessor_execution.commitment,
    )
    object.__setattr__(
        result,
        "execution_snapshot_commitment",
        None if execution is None else execution.commitment,
    )
    object.__setattr__(
        result,
        "predecessor_scope_execution_commitment",
        predecessor_scope,
    )
    object.__setattr__(result, "scope_execution_commitment", current_scope)
    object.__setattr__(result, "predecessor_venue_commitment", predecessor_venue)
    object.__setattr__(result, "venue_commitment", current_venue)
    object.__setattr__(
        result,
        "predecessor_authority_commitment",
        predecessor_authority_commitment,
    )
    object.__setattr__(result, "authority_commitment", current_authority_commitment)
    object.__setattr__(
        result,
        "ordered_venue_transition_commitments",
        () if transition_proof_commitment is None else (transition_proof_commitment,),
    )
    object.__setattr__(result, "venue_transitions", venue_transitions)
    object.__setattr__(result, "predecessor_authority", predecessor_authority)
    object.__setattr__(result, "predecessor_execution", predecessor_execution)
    object.__setattr__(result, "predecessor_venue_context", predecessor_venue_context)
    object.__setattr__(
        result,
        "predecessor_authority_context",
        predecessor_authority_context,
    )
    object.__setattr__(result, "authority", authority)
    object.__setattr__(result, "execution", execution)
    object.__setattr__(result, "venue_context", venue_context)
    object.__setattr__(result, "authority_context", authority_context)
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(
        result,
        "_seal",
        _acquisition_context_refresh_seal(commitment),
    )
    if not _acquisition_context_refresh_is_authentic(result):
        raise RuntimeError("acquisition refresh factory produced an invalid shape")
    return result


def _is_r8_bootstrap_checkpoint_refresh(
    predecessor_authority: ExecutionAuthorityState,
    predecessor_execution: ExecutionSnapshot,
    authority: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    transition: VenueRecoveryTransition,
    position_scope: PositionScope,
) -> bool:
    """Recognize the one R8 checkpoint-only refresh without widening R2."""

    if (
        type(predecessor_authority) is not ExecutionAuthorityState
        or type(predecessor_execution) is not ExecutionSnapshot
        or type(authority) is not ExecutionAuthorityState
        or type(execution) is not ExecutionSnapshot
        or type(transition) is not VenueRecoveryTransition
        or type(position_scope) is not PositionScope
        or transition.disposition is not VenueRecoveryDisposition.APPLIED
        or transition.quantity_delta != 0
        or transition.book is not authority.venue
        or transition.execution is not execution
        or predecessor_execution.position.scope != position_scope
        or execution.position.scope != position_scope
        or predecessor_execution.position.commitment != execution.position.commitment
        or predecessor_execution.root_heads.commitment
        != execution.root_heads.commitment
        or predecessor_execution.integrity != execution.integrity
        or predecessor_execution.position.raw_quantity != 0
        or execution.position.raw_quantity != 0
    ):
        return False
    predecessor_record = predecessor_authority.venue._bootstrap_bound_target_record(
        position_scope
    )
    current_record = authority.venue._bootstrap_bound_target_record(position_scope)
    if predecessor_record is None or current_record is None:
        return False
    if authority != _state_with(predecessor_authority, venue=authority.venue):
        return False
    return bool(
        predecessor_record.application_generation_id
        == current_record.application_generation_id
        and predecessor_record.position_scope == current_record.position_scope
        and predecessor_record.source_kind is current_record.source_kind
        and predecessor_record.source_execution_commitment
        == current_record.source_execution_commitment
        and predecessor_record.target_genesis_execution_commitment
        == current_record.target_genesis_execution_commitment
        and predecessor_record.bootstrap_input_id == current_record.bootstrap_input_id
        and predecessor_record.bootstrap_input_commitment
        == current_record.bootstrap_input_commitment
        and predecessor_record.bootstrap_target_execution_commitment
        == current_record.bootstrap_target_execution_commitment
        and predecessor_record.bootstrap_account_registry_count
        == current_record.bootstrap_account_registry_count
        and predecessor_record.bootstrap_account_registry_commitment
        == current_record.bootstrap_account_registry_commitment
        and predecessor_record.bootstrap_reconciliation_transition_count
        == current_record.bootstrap_reconciliation_transition_count
        and predecessor_record.bootstrap_reconciliation_transition_head
        == current_record.bootstrap_reconciliation_transition_head
        and predecessor_record.bootstrap_neutral_checkpoint_proof_commitment
        == current_record.bootstrap_neutral_checkpoint_proof_commitment
        and predecessor_record.binding == current_record.binding
        and current_record.neutral_checkpoint_proof_commitment
        == transition._protection_proof_commitment
        and authority.venue._bootstrap_bound_target_pair_matches(
            execution,
            position_scope,
        )
    )


def _acquisition_context_refresh_is_authentic(
    value: object,
) -> TypeGuard[AcquisitionContextRefresh]:
    if type(value) is not AcquisitionContextRefresh:
        return False
    try:
        disposition = value.disposition
        application_generation_id = value.application_generation_id
        position_scope = value.position_scope
        source_execution_snapshot_commitment = (
            value.source_execution_snapshot_commitment
        )
        predecessor_execution_snapshot_commitment = (
            value.predecessor_execution_snapshot_commitment
        )
        execution_snapshot_commitment = value.execution_snapshot_commitment
        predecessor_scope_execution_commitment = (
            value.predecessor_scope_execution_commitment
        )
        scope_execution_commitment = value.scope_execution_commitment
        predecessor_venue_commitment = value.predecessor_venue_commitment
        venue_commitment = value.venue_commitment
        predecessor_authority_commitment = value.predecessor_authority_commitment
        authority_commitment = value.authority_commitment
        ordered_transition_commitments = value.ordered_venue_transition_commitments
        venue_transitions = value.venue_transitions
        source_execution = value._source_execution
        predecessor_authority = value.predecessor_authority
        predecessor_execution = value.predecessor_execution
        predecessor_venue_context = value.predecessor_venue_context
        predecessor_authority_context = value.predecessor_authority_context
        authority = value.authority
        execution = value.execution
        venue_context = value.venue_context
        authority_context = value.authority_context
        commitment = value.commitment
        seal = value._seal
    except AttributeError:
        return False
    if (
        type(disposition) is not AcquisitionContextRefreshDisposition
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(ordered_transition_commitments) is not tuple
        or type(venue_transitions) is not tuple
        or not _optional_digest_is_exact(source_execution_snapshot_commitment)
        or not _optional_digest_is_exact(predecessor_execution_snapshot_commitment)
        or not _optional_digest_is_exact(execution_snapshot_commitment)
        or not _optional_digest_is_exact(predecessor_scope_execution_commitment)
        or not _optional_digest_is_exact(scope_execution_commitment)
        or not _optional_digest_is_exact(predecessor_venue_commitment)
        or not _optional_digest_is_exact(venue_commitment)
        or not _optional_digest_is_exact(predecessor_authority_commitment)
        or not _optional_digest_is_exact(authority_commitment)
        or type(commitment) is not bytes
        or len(commitment) != 32
        or type(seal) is not bytes
        or len(seal) != 32
    ):
        return False
    transition_proof_commitment: bytes | None
    transition: VenueRecoveryTransition | None
    if len(venue_transitions) == 0:
        if len(ordered_transition_commitments) != 0:
            return False
        transition = None
        transition_proof_commitment = None
    elif len(venue_transitions) == 1:
        transition = venue_transitions[0]
        if (
            type(transition) is not VenueRecoveryTransition
            or len(ordered_transition_commitments) != 1
            or type(ordered_transition_commitments[0]) is not bytes
            or len(ordered_transition_commitments[0]) != 32
            or type(transition._protection_proof_commitment) is not bytes
            or len(transition._protection_proof_commitment) != 32
            or ordered_transition_commitments[0]
            != transition._protection_proof_commitment
        ):
            return False
        transition_proof_commitment = transition._protection_proof_commitment
    else:
        return False
    if disposition is AcquisitionContextRefreshDisposition.REFUSED:
        if (
            source_execution is not None
            or predecessor_authority is not None
            or predecessor_execution is not None
            or predecessor_venue_context is not None
            or predecessor_authority_context is not None
            or authority is not None
            or execution is not None
            or venue_context is not None
            or authority_context is not None
            or source_execution_snapshot_commitment is not None
            or predecessor_execution_snapshot_commitment is not None
            or execution_snapshot_commitment is not None
            or predecessor_scope_execution_commitment is not None
            or scope_execution_commitment is not None
            or predecessor_venue_commitment is not None
            or venue_commitment is not None
            or predecessor_authority_commitment is not None
            or authority_commitment is not None
            or transition is not None
        ):
            return False
    elif disposition is AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP:
        if (
            type(source_execution) is not ExecutionSnapshot
            or type(predecessor_authority) is not ExecutionAuthorityState
            or predecessor_execution is not None
            or predecessor_venue_context is not None
            or predecessor_authority_context is not None
            or type(authority) is not ExecutionAuthorityState
            or type(execution) is not ExecutionSnapshot
            or type(venue_context) is not AcquisitionVenueContext
            or not _acquisition_authority_context_is_authentic(authority_context)
            or source_execution_snapshot_commitment != source_execution.commitment
            or predecessor_execution_snapshot_commitment is not None
            or predecessor_scope_execution_commitment is not None
            or predecessor_venue_commitment is not None
            or predecessor_authority_commitment is not None
            or execution_snapshot_commitment != execution.commitment
            or scope_execution_commitment != venue_context.scope_execution_commitment
            or venue_commitment != venue_context.commitment
            or authority_commitment != authority_context.authority_commitment
            or transition is None
            or predecessor_authority is authority
            or predecessor_authority.venue is authority.venue
            or transition.disposition is not VenueRecoveryDisposition.APPLIED
            or transition.quantity_delta != 0
            or transition.book is not authority.venue
            or transition.execution is not execution
            or venue_context.application_generation_id != application_generation_id
            or venue_context.position_scope != position_scope
            or authority_context.application_generation_id != application_generation_id
            or authority_context.position_scope != position_scope
        ):
            return False
    elif disposition in {
        AcquisitionContextRefreshDisposition.CURRENT,
        AcquisitionContextRefreshDisposition.REFRESHED,
    }:
        if (
            type(source_execution) is not ExecutionSnapshot
            or type(predecessor_authority) is not ExecutionAuthorityState
            or type(predecessor_execution) is not ExecutionSnapshot
            or type(predecessor_venue_context) is not AcquisitionVenueContext
            or not _acquisition_authority_context_is_authentic(
                predecessor_authority_context
            )
            or type(authority) is not ExecutionAuthorityState
            or type(execution) is not ExecutionSnapshot
            or type(venue_context) is not AcquisitionVenueContext
            or not _acquisition_authority_context_is_authentic(authority_context)
            or source_execution_snapshot_commitment != source_execution.commitment
            or predecessor_execution_snapshot_commitment
            != predecessor_execution.commitment
            or execution_snapshot_commitment != execution.commitment
            or predecessor_scope_execution_commitment
            != predecessor_venue_context.scope_execution_commitment
            or scope_execution_commitment != venue_context.scope_execution_commitment
            or predecessor_venue_commitment != predecessor_venue_context.commitment
            or venue_commitment != venue_context.commitment
            or predecessor_authority_commitment
            != predecessor_authority_context.authority_commitment
            or authority_commitment != authority_context.authority_commitment
        ):
            return False
        if disposition is AcquisitionContextRefreshDisposition.CURRENT:
            if (
                transition is not None
                or predecessor_authority is not authority
                or predecessor_execution is not execution
                or predecessor_scope_execution_commitment != scope_execution_commitment
                or predecessor_venue_commitment != venue_commitment
                or predecessor_authority_commitment != authority_commitment
            ):
                return False
        elif disposition is AcquisitionContextRefreshDisposition.REFRESHED:
            r8_checkpoint_refresh = (
                transition is not None
                and _is_r8_bootstrap_checkpoint_refresh(
                    predecessor_authority,
                    predecessor_execution,
                    authority,
                    execution,
                    transition,
                    position_scope,
                )
            )
            if (
                transition is None
                or predecessor_authority is authority
                or predecessor_authority.venue is authority.venue
                or transition.disposition is not VenueRecoveryDisposition.APPLIED
                or transition.quantity_delta != 0
                or transition.book is not authority.venue
                or transition.execution is not execution
                or (
                    not r8_checkpoint_refresh
                    and (
                        predecessor_scope_execution_commitment
                        != scope_execution_commitment
                        or predecessor_venue_commitment != venue_commitment
                        or predecessor_authority_commitment != authority_commitment
                    )
                )
            ):
                return False
        else:
            return False
    else:
        return False
    expected = _acquisition_context_refresh_commitment(
        disposition,
        application_generation_id,
        position_scope,
        source_execution_snapshot_commitment,
        predecessor_execution_snapshot_commitment,
        execution_snapshot_commitment,
        predecessor_scope_execution_commitment,
        scope_execution_commitment,
        predecessor_venue_commitment,
        venue_commitment,
        predecessor_authority_commitment,
        authority_commitment,
        transition_proof_commitment,
    )
    return bool(
        commitment == expected and seal == _acquisition_context_refresh_seal(commitment)
    )


def _acquisition_context_refresh_pairs_match_live(
    value: AcquisitionContextRefresh,
) -> bool:
    """Recheck both sealed target pairs and the ephemeral source boundary."""

    if (
        not _acquisition_context_refresh_is_authentic(value)
        or value.disposition is AcquisitionContextRefreshDisposition.REFUSED
    ):
        return False
    source_execution = value._source_execution
    predecessor_authority = value.predecessor_authority
    predecessor_execution = value.predecessor_execution
    predecessor_venue_context = value.predecessor_venue_context
    predecessor_authority_context = value.predecessor_authority_context
    authority = value.authority
    execution = value.execution
    venue_context = value.venue_context
    authority_context = value.authority_context
    if value.disposition is AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP:
        if (
            type(source_execution) is not ExecutionSnapshot
            or type(predecessor_authority) is not ExecutionAuthorityState
            or type(authority) is not ExecutionAuthorityState
            or type(execution) is not ExecutionSnapshot
            or type(venue_context) is not AcquisitionVenueContext
            or type(authority_context) is not AcquisitionAuthorityContext
            or not _bootstrap_target_authority_slot_is_clear(
                predecessor_authority,
                value.position_scope,
            )
        ):
            return False
        venue_scope = predecessor_authority.venue.scope
        source_scope = source_execution.position.scope
        if not (
            value.position_scope.broker == source_scope.broker == venue_scope.broker
            and value.position_scope.environment
            == source_scope.environment
            == venue_scope.environment
            and value.position_scope.account
            == source_scope.account
            == venue_scope.account
        ):
            return False
        bootstrap_resolved = _authority_bootstrap_unbound_target_pair_for_scope(
            predecessor_authority.venue,
            source_execution,
            value.position_scope,
        )
        if bootstrap_resolved is None:
            return False
        resolved_book, resolved_execution, resolved_transition = bootstrap_resolved
        replacement = _state_with(predecessor_authority, venue=resolved_book)
        expected_venue_context = resolved_book.project_acquisition_context(
            resolved_execution,
            value.position_scope,
        )
        expected_authority_context = project_acquisition_authority_context(
            replacement,
            resolved_execution,
            expected_venue_context,
        )
        try:
            return bool(
                predecessor_execution is None
                and predecessor_venue_context is None
                and predecessor_authority_context is None
                and authority == replacement
                and execution == resolved_execution
                and authority.venue == resolved_book
                and value.venue_transitions == (resolved_transition,)
                and venue_context == expected_venue_context
                and authority_context == expected_authority_context
                and expected_venue_context.matches_current(
                    resolved_book,
                    resolved_execution,
                    value.application_generation_id,
                    value.position_scope,
                )
                and expected_authority_context.matches_current(
                    replacement,
                    resolved_execution,
                    expected_venue_context,
                )
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False
    if (
        type(source_execution) is not ExecutionSnapshot
        or type(predecessor_authority) is not ExecutionAuthorityState
        or type(predecessor_execution) is not ExecutionSnapshot
        or type(predecessor_venue_context) is not AcquisitionVenueContext
        or type(predecessor_authority_context) is not AcquisitionAuthorityContext
        or type(authority) is not ExecutionAuthorityState
        or type(execution) is not ExecutionSnapshot
        or type(venue_context) is not AcquisitionVenueContext
        or type(authority_context) is not AcquisitionAuthorityContext
    ):
        return False
    venue_scope = predecessor_authority.venue.scope
    source_scope = source_execution.position.scope
    same_account = (
        value.position_scope.broker == source_scope.broker == venue_scope.broker
        and value.position_scope.environment
        == source_scope.environment
        == venue_scope.environment
        and value.position_scope.account == source_scope.account == venue_scope.account
    )
    if not same_account:
        return False
    resolved = _authority_execution_pair_for_scope(
        predecessor_authority.venue,
        source_execution,
        value.position_scope,
        _acquisition_refresh_namespace(
            predecessor_authority.venue,
            value.position_scope,
            source_execution,
        ),
    )
    if resolved is None:
        return False
    (
        resolved_predecessor_book,
        resolved_predecessor_execution,
        resolved_book,
        resolved_execution,
        resolved_transitions,
    ) = resolved
    try:
        return bool(
            resolved_predecessor_book is predecessor_authority.venue
            and resolved_predecessor_execution == predecessor_execution
            and resolved_book == authority.venue
            and resolved_execution == execution
            and resolved_transitions == value.venue_transitions
            and predecessor_authority_context.matches_current(
                predecessor_authority,
                predecessor_execution,
                predecessor_venue_context,
            )
            and venue_context.matches_current(
                authority.venue,
                execution,
                value.application_generation_id,
                value.position_scope,
            )
            and authority_context.matches_current(
                authority,
                execution,
                venue_context,
            )
        )
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return False


def _refused_acquisition_context_refresh(
    state: ExecutionAuthorityState,
    position_scope: PositionScope,
) -> AcquisitionContextRefresh:
    return _new_acquisition_context_refresh(
        disposition=AcquisitionContextRefreshDisposition.REFUSED,
        application_generation_id=state.venue.scope.generation,
        position_scope=position_scope,
        source_execution=None,
        predecessor_authority=None,
        predecessor_execution=None,
        predecessor_venue_context=None,
        predecessor_authority_context=None,
        authority=None,
        execution=None,
        venue_context=None,
        authority_context=None,
        venue_transitions=(),
    )


def _acquisition_refresh_namespace(
    book: VenueRecoveryBook,
    position_scope: PositionScope,
    source_execution: ExecutionSnapshot,
) -> str:
    return _commit_parts(
        b"execution-core/acquisition-authority/refresh-namespace/v1",
        book.scope.generation.value.encode("utf-8"),
        position_scope.broker.value.encode("utf-8"),
        position_scope.environment.value.encode("utf-8"),
        position_scope.account.value.encode("utf-8"),
        position_scope.symbol_id.value.encode("utf-8"),
        source_execution.commitment,
    ).hex()


def _bootstrap_target_authority_slot_is_clear(
    state: ExecutionAuthorityState,
    position_scope: PositionScope,
) -> bool:
    """Keep the unbound bootstrap limited to one genuinely empty target slot."""

    if (
        type(state) is not ExecutionAuthorityState
        or type(position_scope) is not PositionScope
    ):
        return False
    scope = state.venue.scope
    if not (
        position_scope.broker == scope.broker
        and position_scope.environment == scope.environment
        and position_scope.account == scope.account
    ):
        return False
    slot_key = _acquisition_scope_key(scope.generation, position_scope)
    return bool(
        state._acquisition_currentness_by_scope.get(slot_key) is None
        and state._acquisition_descriptor_by_scope.get(slot_key) is None
        and state._acquisition_active_by_scope.get(slot_key) is None
        and state._manual_flatten_by_scope.get(slot_key) is None
    )


def refresh_acquisition_context(
    state: ExecutionAuthorityState,
    source_execution: ExecutionSnapshot,
    position_scope: PositionScope,
) -> AcquisitionContextRefresh:
    """Refresh one target only through venue's authenticated private E1 seam."""

    exact = _validate_authority_state(state)
    _require("source_execution", source_execution, ExecutionSnapshot)
    _require("position_scope", position_scope, PositionScope)
    venue_scope = exact.venue.scope
    source_scope = source_execution.position.scope
    same_account = (
        position_scope.broker == source_scope.broker == venue_scope.broker
        and position_scope.environment
        == source_scope.environment
        == venue_scope.environment
        and position_scope.account == source_scope.account == venue_scope.account
    )
    if not same_account:
        return _refused_acquisition_context_refresh(exact, position_scope)
    resolved = _authority_execution_pair_for_scope(
        exact.venue,
        source_execution,
        position_scope,
        _acquisition_refresh_namespace(
            exact.venue,
            position_scope,
            source_execution,
        ),
    )
    if resolved is None:
        target_is_unbound = bool(exact.venue.execution_binding(position_scope) is None)
        if not target_is_unbound or not _bootstrap_target_authority_slot_is_clear(
            exact,
            position_scope,
        ):
            return _refused_acquisition_context_refresh(exact, position_scope)
        bootstrap = _authority_bootstrap_unbound_target_pair_for_scope(
            exact.venue,
            source_execution,
            position_scope,
        )
        if bootstrap is None:
            return _refused_acquisition_context_refresh(exact, position_scope)
        book, execution, transition = bootstrap
        replacement = _state_with(exact, venue=book)
        venue_context = book.project_acquisition_context(execution, position_scope)
        authority_context = project_acquisition_authority_context(
            replacement,
            execution,
            venue_context,
        )
        if not (
            venue_context.matches_current(
                book,
                execution,
                venue_scope.generation,
                position_scope,
            )
            and authority_context.matches_current(
                replacement,
                execution,
                venue_context,
            )
        ):
            return _refused_acquisition_context_refresh(exact, position_scope)
        return _new_acquisition_context_refresh(
            disposition=AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP,
            application_generation_id=venue_scope.generation,
            position_scope=position_scope,
            source_execution=source_execution,
            predecessor_authority=exact,
            predecessor_execution=None,
            predecessor_venue_context=None,
            predecessor_authority_context=None,
            authority=replacement,
            execution=execution,
            venue_context=venue_context,
            authority_context=authority_context,
            venue_transitions=(transition,),
        )
    (
        predecessor_book,
        predecessor_execution,
        book,
        execution,
        transitions,
    ) = resolved
    predecessor_venue_context = predecessor_book.project_acquisition_context(
        predecessor_execution,
        position_scope,
    )
    predecessor_authority_context = project_acquisition_authority_context(
        exact,
        predecessor_execution,
        predecessor_venue_context,
    )
    replacement = exact if book is exact.venue else _state_with(exact, venue=book)
    venue_context = book.project_acquisition_context(execution, position_scope)
    authority_context = project_acquisition_authority_context(
        replacement,
        execution,
        venue_context,
    )
    if not (
        predecessor_authority_context.matches_current(
            exact,
            predecessor_execution,
            predecessor_venue_context,
        )
        and predecessor_venue_context.application_generation_id
        == venue_scope.generation
        and predecessor_venue_context.position_scope == position_scope
        and venue_context.matches_current(
            book,
            execution,
            venue_scope.generation,
            position_scope,
        )
        and authority_context.matches_current(replacement, execution, venue_context)
    ):
        return _refused_acquisition_context_refresh(exact, position_scope)
    disposition = (
        AcquisitionContextRefreshDisposition.CURRENT
        if not transitions
        else AcquisitionContextRefreshDisposition.REFRESHED
    )
    return _new_acquisition_context_refresh(
        disposition=disposition,
        application_generation_id=venue_scope.generation,
        position_scope=position_scope,
        source_execution=source_execution,
        predecessor_authority=exact,
        predecessor_execution=predecessor_execution,
        predecessor_venue_context=predecessor_venue_context,
        predecessor_authority_context=predecessor_authority_context,
        authority=replacement,
        execution=execution,
        venue_context=venue_context,
        authority_context=authority_context,
        venue_transitions=transitions,
    )


def _acquisition_currentness_registration_commitment(
    entry: _AcquisitionCurrentnessEntry,
    bootstrap_target_commitment: bytes,
    admission_target_commitment: bytes,
    input_id: AuthorityInputId,
) -> bytes:
    _require_digest("bootstrap target commitment", bootstrap_target_commitment)
    _require_digest("admission target commitment", admission_target_commitment)
    _require("bootstrap registration input id", input_id, AuthorityInputId)
    return _commit_parts(
        b"execution-core/acquisition-authority/currentness-registration/v5",
        entry.commitment,
        bootstrap_target_commitment,
        admission_target_commitment,
        input_id.value.encode("utf-8"),
    )


def _acquisition_currentness_registration_seal(commitment: bytes) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-authority/currentness-registration-seal/v1",
        commitment,
    )


def _new_acquisition_currentness_registration(
    *,
    entry: _AcquisitionCurrentnessEntry,
    bootstrap_target_commitment: bytes,
    admission_target_commitment: bytes,
    input_id: AuthorityInputId,
) -> _AcquisitionCurrentnessRegistration:
    if (
        not _acquisition_currentness_entry_is_authentic(entry)
        or type(input_id) is not AuthorityInputId
    ):
        raise TypeError("acquisition registration requires exact owner sources")
    _require_digest("bootstrap target commitment", bootstrap_target_commitment)
    _require_digest("admission target commitment", admission_target_commitment)
    commitment = _acquisition_currentness_registration_commitment(
        entry,
        bootstrap_target_commitment,
        admission_target_commitment,
        input_id,
    )
    result = object.__new__(_AcquisitionCurrentnessRegistration)
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(result, "_entry", entry)
    object.__setattr__(
        result, "_bootstrap_target_commitment", bootstrap_target_commitment
    )
    object.__setattr__(
        result, "_admission_target_commitment", admission_target_commitment
    )
    object.__setattr__(result, "_input_id", input_id)
    object.__setattr__(
        result,
        "_seal",
        _acquisition_currentness_registration_seal(commitment),
    )
    return result


def _acquisition_currentness_registration_is_authentic(
    value: object,
) -> TypeGuard[_AcquisitionCurrentnessRegistration]:
    if type(value) is not _AcquisitionCurrentnessRegistration:
        return False
    try:
        commitment = value.commitment
        entry = value._entry
        bootstrap_target_commitment = value._bootstrap_target_commitment
        admission_target_commitment = value._admission_target_commitment
        input_id = value._input_id
        seal = value._seal
    except AttributeError:
        return False
    if (
        type(commitment) is not bytes
        or len(commitment) != 32
        or not _acquisition_currentness_entry_is_authentic(entry)
        or type(bootstrap_target_commitment) is not bytes
        or len(bootstrap_target_commitment) != 32
        or type(admission_target_commitment) is not bytes
        or len(admission_target_commitment) != 32
        or type(input_id) is not AuthorityInputId
        or type(seal) is not bytes
        or len(seal) != 32
    ):
        return False
    return bool(
        commitment
        == _acquisition_currentness_registration_commitment(
            entry,
            bootstrap_target_commitment,
            admission_target_commitment,
            input_id,
        )
        and seal == _acquisition_currentness_registration_seal(commitment)
    )


def _canonical_fact_registration_source_commitment(
    projection: AcquisitionVenueProjection,
    transition: VenueRecoveryTransition,
) -> bytes:
    """Commit one exact, reducer-authenticated canonical-fact pair.

    The commitment retains no raw book, snapshot, selector, or history reader.
    It only binds the sealed public projection, its direct relation, and the
    private venue proof already attached by the upstream reducer.
    """

    if (
        type(projection) is not AcquisitionVenueProjection
        or type(transition) is not VenueRecoveryTransition
        or projection.source_kind
        not in {
            AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT,
            AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION,
        }
        or not projection.matches_fact_transition(
            transition,
            projection.position_scope,
        )
    ):
        raise ValueError("canonical fact registration source is not exact")
    relation = projection.fact_relation()
    proof_commitment = transition._acquisition_fact_proof_commitment
    if (
        relation is None
        or type(proof_commitment) is not bytes
        or len(proof_commitment) != 32
    ):
        raise ValueError("canonical fact registration source has no direct proof")
    return _commit_parts(
        b"execution-core/acquisition-authority/canonical-fact-source/v1",
        projection._seal,
        relation._seal,
        projection.source_commitment,
        proof_commitment,
    )


def _canonical_fact_currentness_registration_commitment(
    entry: _AcquisitionCurrentnessEntry,
    fact_projection: AcquisitionVenueProjection,
    fact_transition: VenueRecoveryTransition,
    predecessor_authority_context_commitment: bytes,
    input_id: AuthorityInputId,
) -> bytes:
    if (
        not _acquisition_currentness_entry_is_authentic(entry)
        or entry.source_kind is not _AcquisitionCurrentnessSourceKind.CANONICAL_FACT
    ):
        raise TypeError("canonical fact registration requires a canonical entry")
    _require_digest(
        "canonical fact predecessor authority commitment",
        predecessor_authority_context_commitment,
    )
    _require("canonical fact registration input id", input_id, AuthorityInputId)
    return _commit_parts(
        b"execution-core/acquisition-authority/canonical-fact-registration/v1",
        entry.commitment,
        _canonical_fact_registration_source_commitment(
            fact_projection,
            fact_transition,
        ),
        predecessor_authority_context_commitment,
        input_id.value.encode("utf-8"),
    )


def _canonical_fact_currentness_registration_seal(commitment: bytes) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-authority/canonical-fact-registration-seal/v1",
        commitment,
    )


def _new_canonical_fact_currentness_registration(
    *,
    entry: _AcquisitionCurrentnessEntry,
    fact_projection: AcquisitionVenueProjection,
    fact_transition: VenueRecoveryTransition,
    predecessor_authority_context_commitment: bytes,
    input_id: AuthorityInputId,
) -> _CanonicalFactCurrentnessRegistration:
    commitment = _canonical_fact_currentness_registration_commitment(
        entry,
        fact_projection,
        fact_transition,
        predecessor_authority_context_commitment,
        input_id,
    )
    result = object.__new__(_CanonicalFactCurrentnessRegistration)
    for name, value in (
        ("commitment", commitment),
        ("_entry", entry),
        ("_fact_projection", fact_projection),
        ("_fact_transition", fact_transition),
        (
            "_predecessor_authority_context_commitment",
            predecessor_authority_context_commitment,
        ),
        ("_input_id", input_id),
        ("_seal", _canonical_fact_currentness_registration_seal(commitment)),
    ):
        object.__setattr__(result, name, value)
    return result


def _canonical_fact_currentness_registration_is_authentic(
    value: object,
) -> TypeGuard[_CanonicalFactCurrentnessRegistration]:
    if type(value) is not _CanonicalFactCurrentnessRegistration:
        return False
    try:
        commitment = _canonical_fact_currentness_registration_commitment(
            value._entry,
            value._fact_projection,
            value._fact_transition,
            value._predecessor_authority_context_commitment,
            value._input_id,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return bool(
        type(value.commitment) is bytes
        and len(value.commitment) == 32
        and value.commitment == commitment
        and type(value._seal) is bytes
        and len(value._seal) == 32
        and value._seal == _canonical_fact_currentness_registration_seal(commitment)
    )


def _canonical_fact_registration_input_id(
    *,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    controller_head: bytes,
    protection_commitment: bytes | None,
    projection: AcquisitionVenueProjection,
    transition: VenueRecoveryTransition,
) -> AuthorityInputId:
    """Derive a replay-stable input solely from sealed post-fact coordinates."""

    _require(
        "application_generation_id", application_generation_id, ApplicationGenerationId
    )
    _require("position_scope", position_scope, PositionScope)
    _require_digest("canonical fact controller head", controller_head)
    if not _optional_digest_is_exact(protection_commitment):
        raise TypeError("canonical fact protection commitment is not exact")
    if projection.application_generation_id != application_generation_id or (
        projection.position_scope != position_scope
    ):
        raise ValueError("canonical fact registration scope is not exact")
    source = _canonical_fact_registration_source_commitment(projection, transition)
    return AuthorityInputId(
        _commit_parts(
            b"execution-core/acquisition-authority/canonical-fact-registration-input/v1",
            application_generation_id.value.encode("utf-8"),
            position_scope.broker.value.encode("utf-8"),
            position_scope.environment.value.encode("utf-8"),
            position_scope.account.value.encode("utf-8"),
            position_scope.symbol_id.value.encode("utf-8"),
            controller_head,
            protection_commitment or b"",
            source,
        ).hex()
    )


def _bootstrap_registration_sources_are_current(
    authority: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    refresh: AcquisitionContextRefresh,
    bootstrap: AcquisitionVenueProjection,
    admission: AcquisitionAdmissionProjection,
) -> bool:
    """Authenticate the one sealed unbound-target initialization handoff."""

    if (
        type(authority) is not ExecutionAuthorityState
        or type(execution) is not ExecutionSnapshot
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or not _acquisition_context_refresh_is_authentic(refresh)
        or type(bootstrap) is not AcquisitionVenueProjection
        or not _acquisition_admission_is_authentic(admission)
    ):
        return False
    genesis = bool(
        refresh.disposition is AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP
        and len(refresh.venue_transitions) == 1
        and len(refresh.ordered_venue_transition_commitments) == 1
        and refresh.venue_transitions[0].book is authority.venue
        and refresh.venue_transitions[0].execution is execution
        and refresh.venue_transitions[0].disposition is VenueRecoveryDisposition.APPLIED
        and refresh.venue_transitions[0].quantity_delta == 0
        and admission.permits_genesis(
            application_generation_id,
            execution,
            position_scope,
        )
    )
    successor = bool(
        refresh.disposition is AcquisitionContextRefreshDisposition.CURRENT
        and refresh.venue_transitions == ()
        and refresh.ordered_venue_transition_commitments == ()
        and admission.permits_successor(
            application_generation_id,
            execution,
            position_scope,
        )
    )
    return bool(
        (genesis or successor)
        and refresh.authority is authority
        and refresh.execution is execution
        and refresh.venue_context is not None
        and refresh.authority_context is not None
        and refresh.matches_current(
            authority,
            application_generation_id,
            position_scope,
        )
        and admission._authority is authority
        and admission._execution.commitment == execution.commitment
        and admission._venue_context.matches_current(
            authority.venue,
            execution,
            application_generation_id,
            position_scope,
        )
        and admission._authority_context.matches_current(
            authority,
            execution,
            admission._venue_context,
        )
        and bootstrap.matches_bootstrap(execution, authority.venue, position_scope)
        and bootstrap.application_generation_id == application_generation_id
        and bootstrap.position_scope == position_scope
        and bootstrap.execution_snapshot_commitment == execution.commitment
        and bootstrap.scope_execution_commitment == admission.scope_execution_commitment
        and bootstrap.venue_commitment == admission.venue_commitment
    )


def _mint_acquisition_currentness_registration(
    *,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    protection_commitment: bytes | None,
    refresh: AcquisitionContextRefresh | None = None,
    bootstrap: AcquisitionVenueProjection | None = None,
    admission: AcquisitionAdmissionProjection | None = None,
    authority: ExecutionAuthorityState | None = None,
    fact_transition: VenueRecoveryTransition | None = None,
    fact_projection: AcquisitionVenueProjection | None = None,
    predecessor_authority_context_commitment: bytes | None = None,
    protection_rebase: object | None = None,
) -> (
    _AcquisitionCurrentnessRegistration
    | _CanonicalFactCurrentnessRegistration
    | _ProtectionRebaseCurrentnessRegistration
):
    """Mint the private R8 source consumed by initializer-owned registration.

    A first target controller is established directly from sealed target-local
    bootstrap and admission proofs.  This is the narrow R8 exception: it
    consumes only a sealed ``UNBOUND_BOOTSTRAP`` handoff and cannot make
    unrelated account history a bootstrap requirement.
    """

    if protection_rebase is not None:
        if any(
            value is not None
            for value in (
                bootstrap,
                admission,
                fact_transition,
                fact_projection,
            )
        ):
            raise TypeError("protection rebase registration cannot mix source families")
        return _mint_protection_rebase_currentness_registration(
            application_generation_id=application_generation_id,
            position_scope=position_scope,
            session_id=session_id,
            generation_id=generation_id,
            acquisition_mandate_id=acquisition_mandate_id,
            protection_mandate_id=protection_mandate_id,
            binding_commitment=binding_commitment,
            emergency_recovery_compatibility_commitment=(
                emergency_recovery_compatibility_commitment
            ),
            controller_head=controller_head,
            successor_ordinal=successor_ordinal,
            protection_commitment=protection_commitment,
            authority=authority,
            refresh=refresh,
            protection_rebase=protection_rebase,
            predecessor_authority_context_commitment=(
                predecessor_authority_context_commitment
            ),
        )
    if any(
        value is not None
        for value in (
            authority,
            fact_transition,
            fact_projection,
            predecessor_authority_context_commitment,
        )
    ):
        return _mint_canonical_fact_currentness_registration(
            application_generation_id=application_generation_id,
            position_scope=position_scope,
            session_id=session_id,
            generation_id=generation_id,
            acquisition_mandate_id=acquisition_mandate_id,
            protection_mandate_id=protection_mandate_id,
            binding_commitment=binding_commitment,
            emergency_recovery_compatibility_commitment=(
                emergency_recovery_compatibility_commitment
            ),
            controller_head=controller_head,
            successor_ordinal=successor_ordinal,
            protection_commitment=protection_commitment,
            authority=authority,
            fact_transition=fact_transition,
            fact_projection=fact_projection,
            predecessor_authority_context_commitment=(
                predecessor_authority_context_commitment
            ),
        )
    if (
        type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(session_id) is not SessionId
        or type(generation_id) is not AcquisitionGenerationId
        or type(acquisition_mandate_id) is not AcquisitionMandateId
        or type(protection_mandate_id) is not MandateId
        or not _acquisition_generation_id_is_canonical(generation_id)
        or type(successor_ordinal) is not int
        or successor_ordinal < 0
        or successor_ordinal > 2**64 - 1
        or protection_commitment is not None
    ):
        raise TypeError("bootstrap registration requires exact acquisition inputs")
    for digest in (
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        controller_head,
    ):
        if type(digest) is not bytes or len(digest) != 32:
            raise TypeError("bootstrap registration requires exact commitments")
    if (
        type(bootstrap) is not AcquisitionVenueProjection
        or not _acquisition_admission_is_authentic(admission)
        or not _acquisition_context_refresh_is_authentic(refresh)
    ):
        raise TypeError("bootstrap registration requires sealed source proofs")
    authority = refresh.authority
    execution = refresh.execution
    if (
        authority is None
        or execution is None
        or authority.session_id != session_id
        or not _bootstrap_registration_sources_are_current(
            authority,
            execution,
            application_generation_id,
            position_scope,
            refresh,
            bootstrap,
            admission,
        )
    ):
        raise ValueError("bootstrap registration source is not current")
    slot_key = _acquisition_scope_key(application_generation_id, position_scope)
    retained = authority._acquisition_currentness_by_scope.get(slot_key)
    predecessor_slot_commitment = _currentness_entry_commitment(retained)
    if predecessor_slot_commitment is None:
        raise ValueError("bootstrap registration requires one exact target slot")
    if successor_ordinal == 0:
        if (
            retained is not None
            or authority._acquisition_descriptor_by_scope.get(slot_key) is not None
            or authority._acquisition_active_by_scope.get(slot_key) is not None
            or authority._manual_flatten_by_scope.get(slot_key) is not None
        ):
            raise ValueError(
                "bootstrap registration requires one exact empty target slot"
            )
    retained_descriptor = authority._acquisition_descriptor_by_scope.get(slot_key)
    retained_active = authority._acquisition_active_by_scope.get(slot_key)
    terminal_retained = False
    if (
        successor_ordinal > 0
        and _acquisition_effect_descriptor_is_authentic(retained_descriptor)
        and _acquisition_active_effect_is_authentic(retained_active)
        and retained_active.effect_id == retained_descriptor.permit.effect_id
        and retained_active.descriptor_commitment == retained_descriptor.commitment
    ):
        view = _venue_authority_view(
            authority.venue,
            execution,
            position_scope,
            retained_active.effect_id,
        )
        terminal_retained = bool(
            execution.position.raw_quantity == 0
            and execution.integrity is PositionIntegrity.CONSISTENT
            and view.execution_binding_matches
            and view.account_reconciliation_clear
            and view.blocking_effect_count == 0
            and view.blocking_buy_effect_count == 0
            and view.known_cancellable_buy_leg_count == 0
            and view.known_cancel_pending_buy_leg_count == 0
            and view.waiting_buy_parent_count == 0
            and view.unknown_buy_effect_count == 0
        )
    if successor_ordinal > 0 and not (
        _acquisition_currentness_entry_is_authentic(retained)
        and retained.application_generation_id == application_generation_id
        and retained.position_scope == position_scope
        and retained.session_id == session_id
        and retained.successor_ordinal + 1 == successor_ordinal
        and retained.generation_id != generation_id
        and retained.acquisition_mandate_id != acquisition_mandate_id
        and retained.protection_mandate_id != protection_mandate_id
        and retained.binding_commitment != binding_commitment
        and retained.emergency_recovery_compatibility_commitment
        == emergency_recovery_compatibility_commitment
        and retained.controller_head != controller_head
        and (
            (
                retained.scope_execution_commitment
                == admission.scope_execution_commitment
                and retained.venue_commitment == admission.venue_commitment
            )
            or terminal_retained
        )
        and authority._manual_flatten_by_scope.get(slot_key) is None
    ):
        raise ValueError("successor registration requires one exact retained slot")
    entry = _new_acquisition_currentness_entry(
        source_kind=_AcquisitionCurrentnessSourceKind.BOOTSTRAP,
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        session_id=session_id,
        generation_id=generation_id,
        acquisition_mandate_id=acquisition_mandate_id,
        protection_mandate_id=protection_mandate_id,
        binding_commitment=binding_commitment,
        emergency_recovery_compatibility_commitment=(
            emergency_recovery_compatibility_commitment
        ),
        controller_head=controller_head,
        successor_ordinal=successor_ordinal,
        scope_execution_commitment=admission.scope_execution_commitment,
        venue_commitment=admission.venue_commitment,
        protection_commitment=protection_commitment,
        predecessor_slot_commitment=predecessor_slot_commitment,
    )
    return _new_acquisition_currentness_registration(
        entry=entry,
        bootstrap_target_commitment=bootstrap._seal,
        admission_target_commitment=admission._seal,
        input_id=_bootstrap_registration_input_id(
            entry=entry,
            refresh=refresh,
            bootstrap=bootstrap,
            admission=admission,
        ),
    )


def _canonical_fact_predecessor_is_current(
    state: ExecutionAuthorityState,
    transition: VenueRecoveryTransition,
    projection: AcquisitionVenueProjection,
    entry: _AcquisitionCurrentnessEntry,
    predecessor_authority_context_commitment: bytes,
) -> bool:
    """Reprove one current or retired acquisition fact from direct indexes only.

    Venue transport/status observations may legitimately advance between final
    claim and the canonical fact.  They have no authority-currentness mutation
    route, so the fence is the exact fact proof plus the unchanged economic and
    authority coordinates—not an arbitrary raw-book equality test.
    """

    if (
        type(state) is not ExecutionAuthorityState
        or type(transition) is not VenueRecoveryTransition
        or type(projection) is not AcquisitionVenueProjection
        or not _acquisition_currentness_entry_is_authentic(entry)
        or type(predecessor_authority_context_commitment) is not bytes
        or len(predecessor_authority_context_commitment) != 32
        or projection.source_kind
        not in {
            AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT,
            AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION,
        }
        or transition.disposition
        not in {
            VenueRecoveryDisposition.APPLIED,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
        }
        or not projection.matches_fact_transition(transition, entry.position_scope)
    ):
        return False
    relation = projection.fact_relation()
    if (
        relation is None
        or relation.application_generation_id != entry.application_generation_id
        or relation.position_scope != entry.position_scope
        or projection.application_generation_id != entry.application_generation_id
        or projection.position_scope != entry.position_scope
        or projection.predecessor_scope_execution_commitment
        != entry.scope_execution_commitment
        or projection.predecessor_execution_snapshot_commitment is None
        or projection.predecessor_venue_commitment is None
        or state.session_id != entry.session_id
        or _acquisition_authority_commitment(
            state,
            entry.application_generation_id,
            entry.position_scope,
        )
        != predecessor_authority_context_commitment
    ):
        return False
    slot_key = _acquisition_scope_key(
        entry.application_generation_id,
        entry.position_scope,
    )
    current = state._acquisition_currentness_by_scope.get(slot_key)
    current_descriptor = state._acquisition_descriptor_by_scope.get(slot_key)
    descriptor_by_effect = state._acquisition_descriptor_by_effect.get(
        _effect_key(relation.effect_id)
    )
    active = state._acquisition_active_by_scope.get(slot_key)
    claim = state._claim_by_effect.get(_effect_key(relation.effect_id))
    authorization = state._effect_authority_by_id.get(_effect_key(relation.effect_id))
    if not (
        current is entry
        and _acquisition_effect_descriptor_is_authentic(descriptor_by_effect)
        and type(claim) is ClaimAcquisitionEffect
        and type(authorization) is _EffectAuthorization
    ):
        return False
    descriptor = cast(_AcquisitionEffectDescriptor, descriptor_by_effect)
    permit = descriptor.permit
    if (
        claim.effect_id != relation.effect_id
        or claim.permit.effect_id != relation.effect_id
        or permit.effect_id != relation.effect_id
        or permit.request_occurrence_id != relation.request_occurrence_id
        or permit.application_generation_id != entry.application_generation_id
        or permit.position_scope != entry.position_scope
        or permit.session_id != entry.session_id
        or permit.emergency_recovery_compatibility_commitment
        != entry.emergency_recovery_compatibility_commitment
        or authorization.request.effect_id != relation.effect_id
        or authorization.request.request_occurrence_id != relation.request_occurrence_id
        or state._manual_flatten_by_scope.get(slot_key) is not None
    ):
        return False
    current_generation_fact = permit.generation_id == entry.generation_id
    if current_generation_fact:
        if (
            current_descriptor is not descriptor
            or not _acquisition_active_effect_is_authentic(active)
            or active.effect_id != relation.effect_id
            or active.descriptor_commitment != descriptor.commitment
            or permit.acquisition_mandate_id != entry.acquisition_mandate_id
            or permit.protection_mandate_id != entry.protection_mandate_id
            or permit.binding_commitment != entry.binding_commitment
            or permit.successor_ordinal != entry.successor_ordinal
        ):
            return False
    elif permit.successor_ordinal >= entry.successor_ordinal:
        return False
    return True


def _mint_canonical_fact_currentness_registration(
    *,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    protection_commitment: bytes | None,
    authority: ExecutionAuthorityState | None,
    fact_transition: VenueRecoveryTransition | None,
    fact_projection: AcquisitionVenueProjection | None,
    predecessor_authority_context_commitment: bytes | None,
) -> _CanonicalFactCurrentnessRegistration:
    """Mint the sealed fact-source registration without a caller-owned route."""

    if (
        type(authority) is not ExecutionAuthorityState
        or type(fact_transition) is not VenueRecoveryTransition
        or type(fact_projection) is not AcquisitionVenueProjection
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(session_id) is not SessionId
        or type(generation_id) is not AcquisitionGenerationId
        or not _acquisition_generation_id_is_canonical(generation_id)
        or type(acquisition_mandate_id) is not AcquisitionMandateId
        or type(protection_mandate_id) is not MandateId
        or type(successor_ordinal) is not int
        or successor_ordinal < 0
        or successor_ordinal > 2**64 - 1
        or type(protection_commitment) is not bytes
        or len(protection_commitment) != 32
    ):
        raise TypeError("canonical fact registration requires exact owner inputs")
    for digest in (
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        controller_head,
    ):
        _require_digest("canonical fact registration commitment", digest)
    state = _validate_authority_state(authority)
    if state.session_id != session_id:
        raise ValueError("canonical fact registration session is not current")
    if (
        fact_projection.application_generation_id != application_generation_id
        or fact_projection.position_scope != position_scope
        or fact_projection.source_kind
        not in {
            AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT,
            AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION,
        }
        or not fact_projection.matches_fact_transition(fact_transition, position_scope)
    ):
        raise ValueError("canonical fact registration source is not current")
    slot_key = _acquisition_scope_key(application_generation_id, position_scope)
    retained = state._acquisition_currentness_by_scope.get(slot_key)
    input_id = _canonical_fact_registration_input_id(
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        controller_head=controller_head,
        protection_commitment=protection_commitment,
        projection=fact_projection,
        transition=fact_transition,
    )
    if (
        _acquisition_currentness_entry_is_authentic(retained)
        and retained.source_kind is _AcquisitionCurrentnessSourceKind.CANONICAL_FACT
    ):
        replay = state._input_by_id.get(_input_key(input_id))
        if type(replay) is RegisterAcquisitionCurrentness:
            replay_registration = replay.registration
            if (
                type(replay_registration) is _CanonicalFactCurrentnessRegistration
                and _register_canonical_fact_currentness_command_is_authentic(replay)
                and replay_registration._entry is retained
                and replay_registration._fact_projection is not None
                and replay_registration._fact_transition is not None
                and replay_registration._fact_projection.source_commitment
                == fact_projection.source_commitment
                and replay_registration._fact_transition._acquisition_fact_proof_commitment
                == fact_transition._acquisition_fact_proof_commitment
            ):
                return replay_registration
        if retained.controller_head == controller_head:
            raise ValueError("canonical fact registration replay is not exact")
    if (
        not _acquisition_currentness_entry_is_authentic(retained)
        or type(predecessor_authority_context_commitment) is not bytes
        or len(predecessor_authority_context_commitment) != 32
        or retained.application_generation_id != application_generation_id
        or retained.position_scope != position_scope
        or retained.session_id != session_id
        or retained.generation_id != generation_id
        or retained.acquisition_mandate_id != acquisition_mandate_id
        or retained.protection_mandate_id != protection_mandate_id
        or retained.binding_commitment != binding_commitment
        or retained.emergency_recovery_compatibility_commitment
        != emergency_recovery_compatibility_commitment
        or retained.successor_ordinal != successor_ordinal
        or retained.controller_head == controller_head
        or not _canonical_fact_predecessor_is_current(
            state,
            fact_transition,
            fact_projection,
            retained,
            predecessor_authority_context_commitment,
        )
    ):
        raise ValueError("canonical fact registration predecessor is not current")
    entry = _new_acquisition_currentness_entry(
        source_kind=_AcquisitionCurrentnessSourceKind.CANONICAL_FACT,
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        session_id=session_id,
        generation_id=generation_id,
        acquisition_mandate_id=acquisition_mandate_id,
        protection_mandate_id=protection_mandate_id,
        binding_commitment=binding_commitment,
        emergency_recovery_compatibility_commitment=(
            emergency_recovery_compatibility_commitment
        ),
        controller_head=controller_head,
        successor_ordinal=successor_ordinal,
        scope_execution_commitment=fact_projection.scope_execution_commitment,
        venue_commitment=fact_projection.venue_commitment,
        protection_commitment=protection_commitment,
        predecessor_slot_commitment=retained.commitment,
    )
    return _new_canonical_fact_currentness_registration(
        entry=entry,
        fact_projection=fact_projection,
        fact_transition=fact_transition,
        predecessor_authority_context_commitment=(
            predecessor_authority_context_commitment
        ),
        input_id=input_id,
    )


def _protection_rebase_projection_is_current(
    projection: _ProtectionRebaseProjectionView,
    retained: _AcquisitionCurrentnessEntry,
    execution: ExecutionSnapshot,
    venue_context: AcquisitionVenueContext,
) -> bool:
    """Reprove the owner-sealed structural relation without importing protection."""

    try:
        kind_value = projection.kind.value
        source_transitions = projection.source_venue_transition_commitments
    except AttributeError:
        return False
    if (
        not _acquisition_currentness_entry_is_authentic(retained)
        or retained.protection_commitment is None
        or type(kind_value) is not str
        or kind_value != "SEMANTIC_REBASE"
        or projection.application_generation_id != retained.application_generation_id
        or projection.position_scope != retained.position_scope
        or projection.predecessor_execution_snapshot_commitment != execution.commitment
        or projection.execution_snapshot_commitment != execution.commitment
        or projection.predecessor_scope_execution_commitment
        != retained.scope_execution_commitment
        or projection.scope_execution_commitment != retained.scope_execution_commitment
        or projection.predecessor_scope_execution_commitment
        != venue_context.scope_execution_commitment
        or projection.scope_execution_commitment
        != venue_context.scope_execution_commitment
        or projection.predecessor_venue_commitment != retained.venue_commitment
        or projection.venue_commitment != retained.venue_commitment
        or projection.predecessor_venue_commitment != venue_context.commitment
        or projection.venue_commitment != venue_context.commitment
        or projection.resulting_state is None
        or type(projection.predecessor_context_commitment) is not bytes
        or len(projection.predecessor_context_commitment) != 32
        or type(projection.context_commitment) is not bytes
        or len(projection.context_commitment) != 32
        or type(projection.predecessor_source_protection_commitment) is not bytes
        or len(projection.predecessor_source_protection_commitment) != 32
        or type(projection.source_protection_commitment) is not bytes
        or len(projection.source_protection_commitment) != 32
        or type(projection.source_commitment) is not bytes
        or len(projection.source_commitment) != 32
        or type(source_transitions) is not tuple
        or any(
            type(commitment) is not bytes or len(commitment) != 32
            for commitment in source_transitions
        )
    ):
        return False
    return True


def _protection_rebase_registration_source_commitment(
    projection: _ProtectionRebaseProjectionView,
) -> bytes:
    """Bind only the protection-owned sealed source, never a raw state graph."""

    try:
        source_commitment = projection.source_commitment
        predecessor_context_commitment = projection.predecessor_context_commitment
        context_commitment = projection.context_commitment
        predecessor_source_protection_commitment = (
            projection.predecessor_source_protection_commitment
        )
        source_protection_commitment = projection.source_protection_commitment
        source_transitions = projection.source_venue_transition_commitments
    except AttributeError as error:
        raise TypeError(
            "protection rebase source must expose its sealed proof"
        ) from error
    source_commitment = _require_digest(
        "protection rebase source commitment", source_commitment
    )
    predecessor_context_commitment = _require_digest(
        "protection rebase predecessor context commitment",
        predecessor_context_commitment,
    )
    context_commitment = _require_digest(
        "protection rebase context commitment", context_commitment
    )
    predecessor_source_protection_commitment = _require_digest(
        "protection rebase predecessor source commitment",
        predecessor_source_protection_commitment,
    )
    source_protection_commitment = _require_digest(
        "protection rebase source protection commitment",
        source_protection_commitment,
    )
    if type(source_transitions) is not tuple or any(
        type(commitment) is not bytes or len(commitment) != 32
        for commitment in source_transitions
    ):
        raise TypeError("protection rebase source transitions must be exact")
    return _commit_parts(
        b"execution-core/acquisition-authority/protection-rebase-source/v1",
        source_commitment,
        predecessor_context_commitment,
        context_commitment,
        predecessor_source_protection_commitment,
        source_protection_commitment,
        _commit_parts(
            b"execution-core/acquisition-authority/protection-rebase-transitions/v1",
            *source_transitions,
        ),
    )


def _protection_rebase_currentness_registration_commitment(
    entry: _AcquisitionCurrentnessEntry,
    projection: _ProtectionRebaseProjectionView,
    predecessor_authority_context_commitment: bytes,
    input_id: AuthorityInputId,
) -> bytes:
    if (
        not _acquisition_currentness_entry_is_authentic(entry)
        or entry.source_kind is not _AcquisitionCurrentnessSourceKind.PROTECTION_REBASE
    ):
        raise TypeError("protection rebase registration requires a rebase entry")
    _require_digest(
        "protection rebase predecessor authority commitment",
        predecessor_authority_context_commitment,
    )
    _require("protection rebase registration input id", input_id, AuthorityInputId)
    return _commit_parts(
        b"execution-core/acquisition-authority/protection-rebase-registration/v1",
        entry.commitment,
        _protection_rebase_registration_source_commitment(projection),
        predecessor_authority_context_commitment,
        input_id.value.encode("utf-8"),
    )


def _protection_rebase_currentness_registration_seal(commitment: bytes) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-authority/protection-rebase-registration-seal/v1",
        commitment,
    )


def _new_protection_rebase_currentness_registration(
    *,
    entry: _AcquisitionCurrentnessEntry,
    projection: _ProtectionRebaseProjectionView,
    predecessor_authority_context_commitment: bytes,
    input_id: AuthorityInputId,
) -> _ProtectionRebaseCurrentnessRegistration:
    commitment = _protection_rebase_currentness_registration_commitment(
        entry,
        projection,
        predecessor_authority_context_commitment,
        input_id,
    )
    result = object.__new__(_ProtectionRebaseCurrentnessRegistration)
    for name, value in (
        ("commitment", commitment),
        ("_entry", entry),
        ("_projection", projection),
        (
            "_predecessor_authority_context_commitment",
            predecessor_authority_context_commitment,
        ),
        ("_input_id", input_id),
        ("_seal", _protection_rebase_currentness_registration_seal(commitment)),
    ):
        object.__setattr__(result, name, value)
    return result


def _protection_rebase_currentness_registration_is_authentic(
    value: object,
) -> TypeGuard[_ProtectionRebaseCurrentnessRegistration]:
    if type(value) is not _ProtectionRebaseCurrentnessRegistration:
        return False
    try:
        commitment = _protection_rebase_currentness_registration_commitment(
            value._entry,
            value._projection,
            value._predecessor_authority_context_commitment,
            value._input_id,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return bool(
        type(value.commitment) is bytes
        and len(value.commitment) == 32
        and value.commitment == commitment
        and type(value._seal) is bytes
        and len(value._seal) == 32
        and value._seal == _protection_rebase_currentness_registration_seal(commitment)
    )


def _protection_rebase_registration_input_id(
    *,
    entry: _AcquisitionCurrentnessEntry,
    projection: _ProtectionRebaseProjectionView,
    predecessor_authority_context_commitment: bytes,
) -> AuthorityInputId:
    if not _acquisition_currentness_entry_is_authentic(entry):
        raise TypeError("protection rebase registration requires an authentic entry")
    _require_digest(
        "protection rebase predecessor authority commitment",
        predecessor_authority_context_commitment,
    )
    return AuthorityInputId(
        _commit_parts(
            b"execution-core/acquisition-authority/protection-rebase-registration-input/v1",
            entry.commitment,
            _protection_rebase_registration_source_commitment(projection),
            predecessor_authority_context_commitment,
        ).hex()
    )


def _mint_protection_rebase_currentness_registration(
    *,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    protection_commitment: bytes | None,
    authority: ExecutionAuthorityState | None,
    refresh: AcquisitionContextRefresh | None,
    protection_rebase: object | None,
    predecessor_authority_context_commitment: bytes | None,
) -> _ProtectionRebaseCurrentnessRegistration:
    """Mint one private registration from the sealed controller/protection handoff."""

    if (
        type(authority) is not ExecutionAuthorityState
        or type(refresh) is not AcquisitionContextRefresh
        or protection_rebase is None
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(session_id) is not SessionId
        or type(generation_id) is not AcquisitionGenerationId
        or not _acquisition_generation_id_is_canonical(generation_id)
        or type(acquisition_mandate_id) is not AcquisitionMandateId
        or type(protection_mandate_id) is not MandateId
        or type(successor_ordinal) is not int
        or successor_ordinal < 0
        or successor_ordinal > 2**64 - 1
        or type(protection_commitment) is not bytes
        or len(protection_commitment) != 32
        or type(predecessor_authority_context_commitment) is not bytes
        or len(predecessor_authority_context_commitment) != 32
    ):
        raise TypeError("protection rebase registration requires exact owner inputs")
    for commitment in (
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        controller_head,
    ):
        _require_digest("protection rebase registration commitment", commitment)
    state = _validate_authority_state(authority)
    projection = cast(_ProtectionRebaseProjectionView, protection_rebase)
    execution = refresh.execution
    venue_context = refresh.venue_context
    authority_context = refresh.authority_context
    if (
        refresh.disposition is not AcquisitionContextRefreshDisposition.CURRENT
        or refresh.authority is not state
        or execution is None
        or venue_context is None
        or authority_context is None
        or state.session_id != session_id
        or refresh.application_generation_id != application_generation_id
        or refresh.position_scope != position_scope
        or not refresh.matches_current(state, application_generation_id, position_scope)
        or authority_context.authority_commitment
        != predecessor_authority_context_commitment
    ):
        raise ValueError("protection rebase registration handoff is not current")
    slot_key = _acquisition_scope_key(application_generation_id, position_scope)
    retained = state._acquisition_currentness_by_scope.get(slot_key)
    if (
        not _acquisition_currentness_entry_is_authentic(retained)
        or retained.application_generation_id != application_generation_id
        or retained.position_scope != position_scope
        or retained.session_id != session_id
        or retained.generation_id != generation_id
        or retained.acquisition_mandate_id != acquisition_mandate_id
        or retained.protection_mandate_id != protection_mandate_id
        or retained.binding_commitment != binding_commitment
        or retained.emergency_recovery_compatibility_commitment
        != emergency_recovery_compatibility_commitment
        or retained.successor_ordinal != successor_ordinal
        or retained.controller_head == controller_head
        or retained.protection_commitment is None
        or retained.protection_commitment == protection_commitment
        or retained.scope_execution_commitment
        != venue_context.scope_execution_commitment
        or retained.venue_commitment != venue_context.commitment
        or not _protection_rebase_projection_is_current(
            projection,
            retained,
            execution,
            venue_context,
        )
        or _acquisition_authority_commitment(
            state,
            application_generation_id,
            position_scope,
        )
        != predecessor_authority_context_commitment
    ):
        raise ValueError("protection rebase registration predecessor is not current")
    entry = _new_acquisition_currentness_entry(
        source_kind=_AcquisitionCurrentnessSourceKind.PROTECTION_REBASE,
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        session_id=session_id,
        generation_id=generation_id,
        acquisition_mandate_id=acquisition_mandate_id,
        protection_mandate_id=protection_mandate_id,
        binding_commitment=binding_commitment,
        emergency_recovery_compatibility_commitment=(
            emergency_recovery_compatibility_commitment
        ),
        controller_head=controller_head,
        successor_ordinal=successor_ordinal,
        scope_execution_commitment=venue_context.scope_execution_commitment,
        venue_commitment=venue_context.commitment,
        protection_commitment=protection_commitment,
        predecessor_slot_commitment=retained.commitment,
    )
    return _new_protection_rebase_currentness_registration(
        entry=entry,
        projection=projection,
        predecessor_authority_context_commitment=(
            predecessor_authority_context_commitment
        ),
        input_id=_protection_rebase_registration_input_id(
            entry=entry,
            projection=projection,
            predecessor_authority_context_commitment=(
                predecessor_authority_context_commitment
            ),
        ),
    )


def _bootstrap_registration_input_id(
    *,
    entry: _AcquisitionCurrentnessEntry,
    refresh: AcquisitionContextRefresh,
    bootstrap: AcquisitionVenueProjection,
    admission: AcquisitionAdmissionProjection,
) -> AuthorityInputId:
    """Derive the one dispatcher identity from the sealed R8 handoff.

    The result deliberately has no caller namespace or externally selected
    coordinate.  A registration is therefore replayable only at the exact
    authenticated handoff it was minted from.
    """

    if (
        not _acquisition_currentness_entry_is_authentic(entry)
        or not _acquisition_context_refresh_is_authentic(refresh)
        or type(bootstrap) is not AcquisitionVenueProjection
        or not _acquisition_admission_is_authentic(admission)
    ):
        raise TypeError("bootstrap registration requires exact owner sources")
    if refresh.disposition is AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP:
        if len(refresh.ordered_venue_transition_commitments) != 1:
            raise ValueError("bootstrap registration requires one sealed handoff")
        transition_commitment = refresh.ordered_venue_transition_commitments[0]
    elif refresh.disposition is AcquisitionContextRefreshDisposition.CURRENT:
        if refresh.ordered_venue_transition_commitments != ():
            raise ValueError("successor registration requires a current handoff")
        transition_commitment = b""
    else:
        raise ValueError("bootstrap registration requires one sealed handoff")
    return AuthorityInputId(
        _commit_parts(
            b"execution-core/acquisition-authority/bootstrap-registration-input/v1",
            entry.commitment,
            refresh.commitment,
            transition_commitment,
            bootstrap._seal,
            admission._seal,
        ).hex()
    )


def _register_acquisition_currentness_command_seal(
    input_id: AuthorityInputId,
    registration: _AcquisitionCurrentnessRegistration,
) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-authority/bootstrap-registration-command/v1",
        input_id.value.encode("utf-8"),
        registration.commitment,
    )


def _new_register_acquisition_currentness(
    registration: _AcquisitionCurrentnessRegistration,
) -> _RegisterAcquisitionCurrentness:
    """Construct one dispatcher command from its sealed registration only."""

    if not _acquisition_currentness_registration_is_authentic(registration):
        raise TypeError("bootstrap registration must be exact and sealed")
    result = object.__new__(_RegisterAcquisitionCurrentness)
    object.__setattr__(result, "input_id", registration._input_id)
    object.__setattr__(result, "registration", registration)
    object.__setattr__(
        result,
        "_seal",
        _register_acquisition_currentness_command_seal(
            registration._input_id,
            registration,
        ),
    )
    return result


def _register_acquisition_currentness_command_is_authentic(
    value: object,
) -> TypeGuard[_RegisterAcquisitionCurrentness]:
    if type(value) is not _RegisterAcquisitionCurrentness:
        return False
    try:
        input_id = value.input_id
        registration = value.registration
        seal = value._seal
    except AttributeError:
        return False
    return bool(
        type(input_id) is AuthorityInputId
        and _acquisition_currentness_registration_is_authentic(registration)
        and input_id == registration._input_id
        and type(seal) is bytes
        and len(seal) == 32
        and seal
        == _register_acquisition_currentness_command_seal(input_id, registration)
    )


def _register_canonical_fact_currentness_command_seal(
    input_id: AuthorityInputId,
    registration: _CanonicalFactCurrentnessRegistration,
) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-authority/canonical-fact-registration-command/v1",
        input_id.value.encode("utf-8"),
        registration.commitment,
    )


def _new_register_canonical_fact_currentness(
    registration: _CanonicalFactCurrentnessRegistration,
) -> RegisterAcquisitionCurrentness:
    """Wrap one sealed canonical-fact registration for ordinary replay handling."""

    if not (
        _canonical_fact_currentness_registration_is_authentic(registration)
        and registration._entry.source_kind
        is _AcquisitionCurrentnessSourceKind.CANONICAL_FACT
    ):
        raise TypeError("canonical fact registration must be exact and sealed")
    result = object.__new__(RegisterAcquisitionCurrentness)
    object.__setattr__(result, "input_id", registration._input_id)
    object.__setattr__(result, "registration", registration)
    object.__setattr__(
        result,
        "_seal",
        _register_canonical_fact_currentness_command_seal(
            registration._input_id,
            registration,
        ),
    )
    return result


def _register_canonical_fact_currentness_command_is_authentic(
    value: object,
) -> TypeGuard[RegisterAcquisitionCurrentness]:
    if type(value) is not RegisterAcquisitionCurrentness:
        return False
    try:
        input_id = value.input_id
        registration = value.registration
        seal = value._seal
    except AttributeError:
        return False
    return bool(
        type(input_id) is AuthorityInputId
        and _canonical_fact_currentness_registration_is_authentic(registration)
        and registration._entry.source_kind
        is _AcquisitionCurrentnessSourceKind.CANONICAL_FACT
        and input_id == registration._input_id
        and type(seal) is bytes
        and len(seal) == 32
        and seal
        == _register_canonical_fact_currentness_command_seal(input_id, registration)
    )


def _register_protection_rebase_currentness_command_seal(
    input_id: AuthorityInputId,
    registration: _ProtectionRebaseCurrentnessRegistration,
) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-authority/protection-rebase-registration-command/v1",
        input_id.value.encode("utf-8"),
        registration.commitment,
    )


def _new_register_protection_rebase_currentness(
    registration: _ProtectionRebaseCurrentnessRegistration,
) -> RegisterAcquisitionCurrentness:
    """Wrap one sealed semantic rebase without a new public command type."""

    if not (
        _protection_rebase_currentness_registration_is_authentic(registration)
        and registration._entry.source_kind
        is _AcquisitionCurrentnessSourceKind.PROTECTION_REBASE
    ):
        raise TypeError("protection rebase registration must be exact and sealed")
    result = object.__new__(RegisterAcquisitionCurrentness)
    object.__setattr__(result, "input_id", registration._input_id)
    object.__setattr__(result, "registration", registration)
    object.__setattr__(
        result,
        "_seal",
        _register_protection_rebase_currentness_command_seal(
            registration._input_id,
            registration,
        ),
    )
    return result


def _register_protection_rebase_currentness_command_is_authentic(
    value: object,
) -> bool:
    if type(value) is not RegisterAcquisitionCurrentness:
        return False
    try:
        input_id = value.input_id
        registration = value.registration
        seal = value._seal
    except AttributeError:
        return False
    return bool(
        type(input_id) is AuthorityInputId
        and _protection_rebase_currentness_registration_is_authentic(registration)
        and registration._entry.source_kind
        is _AcquisitionCurrentnessSourceKind.PROTECTION_REBASE
        and input_id == registration._input_id
        and type(seal) is bytes
        and len(seal) == 32
        and seal
        == _register_protection_rebase_currentness_command_seal(
            input_id,
            registration,
        )
    )


def _mint_acquisition_bootstrap_registration_command(
    *,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    controller_head: bytes,
    refresh: AcquisitionContextRefresh,
    bootstrap: AcquisitionVenueProjection,
    admission: AcquisitionAdmissionProjection,
) -> _RegisterAcquisitionCurrentness:
    """Return the sole owner-derived ordinal-zero registration command."""

    registration = _mint_acquisition_currentness_registration(
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        session_id=session_id,
        generation_id=generation_id,
        acquisition_mandate_id=acquisition_mandate_id,
        protection_mandate_id=protection_mandate_id,
        binding_commitment=binding_commitment,
        emergency_recovery_compatibility_commitment=(
            emergency_recovery_compatibility_commitment
        ),
        controller_head=controller_head,
        successor_ordinal=0,
        protection_commitment=None,
        refresh=refresh,
        bootstrap=bootstrap,
        admission=admission,
    )
    if type(registration) is not _AcquisitionCurrentnessRegistration:
        raise RuntimeError("bootstrap mint returned a non-bootstrap registration")
    return _new_register_acquisition_currentness(registration)


def _mint_acquisition_successor_registration_command(
    *,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    refresh: AcquisitionContextRefresh,
    bootstrap: AcquisitionVenueProjection,
    admission: AcquisitionAdmissionProjection,
) -> _RegisterAcquisitionCurrentness:
    """Return one owner-derived serial-successor registration command."""

    if successor_ordinal <= 0:
        raise ValueError("successor registration requires a positive ordinal")
    registration = _mint_acquisition_currentness_registration(
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        session_id=session_id,
        generation_id=generation_id,
        acquisition_mandate_id=acquisition_mandate_id,
        protection_mandate_id=protection_mandate_id,
        binding_commitment=binding_commitment,
        emergency_recovery_compatibility_commitment=(
            emergency_recovery_compatibility_commitment
        ),
        controller_head=controller_head,
        successor_ordinal=successor_ordinal,
        protection_commitment=None,
        refresh=refresh,
        bootstrap=bootstrap,
        admission=admission,
    )
    if type(registration) is not _AcquisitionCurrentnessRegistration:
        raise RuntimeError("successor mint returned a non-bootstrap registration")
    return _new_register_acquisition_currentness(registration)


def _acquisition_authority_receipt_commitment(
    operation: AcquisitionAuthorityOperation,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    predecessor_controller_head: bytes,
    controller_head: bytes,
    predecessor_scope_execution_commitment: bytes,
    scope_execution_commitment: bytes,
    predecessor_venue_commitment: bytes,
    venue_commitment: bytes,
    predecessor_authority_commitment: bytes,
    authority_commitment: bytes,
    ordered_venue_transition_commitments: tuple[bytes, ...],
    permit_commitment: bytes,
) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-authority/receipt/v3",
        operation.value.encode("utf-8"),
        application_generation_id.value.encode("utf-8"),
        position_scope.broker.value.encode("utf-8"),
        position_scope.environment.value.encode("utf-8"),
        position_scope.account.value.encode("utf-8"),
        position_scope.symbol_id.value.encode("utf-8"),
        predecessor_controller_head,
        controller_head,
        predecessor_scope_execution_commitment,
        scope_execution_commitment,
        predecessor_venue_commitment,
        venue_commitment,
        predecessor_authority_commitment,
        authority_commitment,
        _commit_parts(
            b"execution-core/acquisition-authority/ordered-venue-proofs/v1",
            *ordered_venue_transition_commitments,
        ),
        permit_commitment,
    )


def _new_acquisition_authority_receipt(
    *,
    operation: AcquisitionAuthorityOperation,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    predecessor_controller_head: bytes,
    controller_head: bytes,
    predecessor_scope_execution_commitment: bytes,
    scope_execution_commitment: bytes,
    predecessor_venue_commitment: bytes,
    venue_commitment: bytes,
    predecessor_authority_commitment: bytes,
    authority_commitment: bytes,
    ordered_venue_transition_commitments: tuple[bytes, ...],
    permit_commitment: bytes,
) -> AcquisitionAuthorityReceipt:
    if (
        type(operation) is not AcquisitionAuthorityOperation
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(ordered_venue_transition_commitments) is not tuple
    ):
        raise TypeError("acquisition authority receipt requires exact owner inputs")
    if len(ordered_venue_transition_commitments) > 3 or any(
        type(commitment) is not bytes or len(commitment) != 32
        for commitment in ordered_venue_transition_commitments
    ):
        raise TypeError("acquisition authority receipt proof sequence is invalid")
    for digest in (
        predecessor_controller_head,
        controller_head,
        predecessor_scope_execution_commitment,
        scope_execution_commitment,
        predecessor_venue_commitment,
        venue_commitment,
        predecessor_authority_commitment,
        authority_commitment,
        permit_commitment,
    ):
        if type(digest) is not bytes or len(digest) != 32:
            raise TypeError("acquisition authority receipt requires exact commitments")
    commitment = _acquisition_authority_receipt_commitment(
        operation,
        application_generation_id,
        position_scope,
        predecessor_controller_head,
        controller_head,
        predecessor_scope_execution_commitment,
        scope_execution_commitment,
        predecessor_venue_commitment,
        venue_commitment,
        predecessor_authority_commitment,
        authority_commitment,
        ordered_venue_transition_commitments,
        permit_commitment,
    )
    result = object.__new__(AcquisitionAuthorityReceipt)
    object.__setattr__(result, "operation", operation)
    object.__setattr__(result, "application_generation_id", application_generation_id)
    object.__setattr__(result, "position_scope", position_scope)
    object.__setattr__(
        result,
        "predecessor_controller_head",
        predecessor_controller_head,
    )
    object.__setattr__(result, "controller_head", controller_head)
    object.__setattr__(
        result,
        "predecessor_scope_execution_commitment",
        predecessor_scope_execution_commitment,
    )
    object.__setattr__(
        result,
        "scope_execution_commitment",
        scope_execution_commitment,
    )
    object.__setattr__(
        result,
        "predecessor_venue_commitment",
        predecessor_venue_commitment,
    )
    object.__setattr__(result, "venue_commitment", venue_commitment)
    object.__setattr__(
        result,
        "predecessor_authority_commitment",
        predecessor_authority_commitment,
    )
    object.__setattr__(result, "authority_commitment", authority_commitment)
    object.__setattr__(
        result,
        "ordered_venue_transition_commitments",
        ordered_venue_transition_commitments,
    )
    object.__setattr__(result, "permit_commitment", permit_commitment)
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition-authority/receipt-seal/v3",
            commitment,
        ),
    )
    return result


@dataclass(frozen=True, slots=True)
class ExecutionAuthorityTransition:
    state: ExecutionAuthorityState
    disposition: AuthorityDisposition
    reason: AuthorityReason | None
    created_effect_ids: tuple[EffectId, ...]
    fresh_claim: _FreshEffectClaim | _FreshQueryClaim | None
    venue_transitions: tuple[VenueRecoveryTransition, ...]
    acquisition_receipt: AcquisitionAuthorityReceipt | None
    acquisition_claim_receipt: AcquisitionClaimReceipt | None


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
        _manual_flatten_by_scope=_PersistentKeyMap.empty(),
        _consumed_grant_ids=_PersistentKeyMap.empty(),
        _acquisition_currentness_by_scope=_PersistentKeyMap.empty(),
        _acquisition_descriptor_by_scope=_PersistentKeyMap.empty(),
        _acquisition_descriptor_by_effect=_PersistentKeyMap.empty(),
        _acquisition_active_by_scope=_PersistentKeyMap.empty(),
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
    acquisition_receipt: AcquisitionAuthorityReceipt | None = None,
    acquisition_claim_receipt: AcquisitionClaimReceipt | None = None,
) -> ExecutionAuthorityTransition:
    return ExecutionAuthorityTransition(
        state,
        disposition,
        reason,
        created,
        claim,
        venue_transitions,
        acquisition_receipt,
        acquisition_claim_receipt,
    )


def _record_input(
    state: ExecutionAuthorityState,
    item: _AuthorityCommand | _AcquisitionFactPreemption,
) -> ExecutionAuthorityState:
    return _state_with(
        state,
        _input_by_id=_inserted(state._input_by_id, _input_key(item.input_id), item),
    )


def _register_acquisition_currentness(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: _RegisterAcquisitionCurrentness,
) -> ExecutionAuthorityTransition:
    """Install one exact bootstrap entry after reproving every source boundary."""

    registration = cast(_AcquisitionCurrentnessRegistration, item.registration)
    if not (
        _register_acquisition_currentness_command_is_authentic(item)
        and _acquisition_currentness_registration_is_authentic(registration)
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    entry = registration._entry
    bootstrap = state.venue.project_acquisition_bootstrap(
        execution,
        entry.position_scope,
    )
    admission = project_acquisition_admission(
        state,
        execution,
        entry.position_scope,
    )
    admitted = (
        admission.permits_genesis(
            entry.application_generation_id,
            execution,
            entry.position_scope,
        )
        if entry.successor_ordinal == 0
        else admission.permits_successor(
            entry.application_generation_id,
            execution,
            entry.position_scope,
        )
    )
    if (
        entry.source_kind is not _AcquisitionCurrentnessSourceKind.BOOTSTRAP
        or item.input_id != registration._input_id
        or state.session_id != entry.session_id
        or bootstrap._seal != registration._bootstrap_target_commitment
        or admission._seal != registration._admission_target_commitment
        or not admitted
        or not bootstrap.matches_bootstrap(
            execution,
            state.venue,
            entry.position_scope,
        )
        or bootstrap.scope_execution_commitment != entry.scope_execution_commitment
        or bootstrap.venue_commitment != entry.venue_commitment
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    slot_key = _acquisition_scope_key(
        entry.application_generation_id,
        entry.position_scope,
    )
    retained = state._acquisition_currentness_by_scope.get(slot_key)
    predecessor_slot_commitment = _currentness_entry_commitment(retained)
    retained_descriptor = state._acquisition_descriptor_by_scope.get(slot_key)
    retained_active = state._acquisition_active_by_scope.get(slot_key)
    terminal_successor = False
    if (
        entry.successor_ordinal > 0
        and _acquisition_effect_descriptor_is_authentic(retained_descriptor)
        and _acquisition_active_effect_is_authentic(retained_active)
        and retained_active.effect_id == retained_descriptor.permit.effect_id
        and retained_active.descriptor_commitment == retained_descriptor.commitment
    ):
        view = _venue_authority_view(
            state.venue,
            execution,
            entry.position_scope,
            retained_active.effect_id,
        )
        terminal_successor = bool(
            execution.position.raw_quantity == 0
            and execution.integrity is PositionIntegrity.CONSISTENT
            and view.execution_binding_matches
            and view.account_reconciliation_clear
            and view.blocking_effect_count == 0
            and view.blocking_buy_effect_count == 0
            and view.known_cancellable_buy_leg_count == 0
            and view.known_cancel_pending_buy_leg_count == 0
            and view.waiting_buy_parent_count == 0
            and view.unknown_buy_effect_count == 0
        )
    genesis_slot = bool(
        entry.successor_ordinal == 0
        and retained is None
        and state._acquisition_descriptor_by_scope.get(slot_key) is None
        and state._acquisition_active_by_scope.get(slot_key) is None
        and state._manual_flatten_by_scope.get(slot_key) is None
    )
    successor_slot = bool(
        entry.successor_ordinal > 0
        and _acquisition_currentness_entry_is_authentic(retained)
        and retained.application_generation_id == entry.application_generation_id
        and retained.position_scope == entry.position_scope
        and retained.session_id == entry.session_id
        and retained.successor_ordinal + 1 == entry.successor_ordinal
        and retained.generation_id != entry.generation_id
        and retained.acquisition_mandate_id != entry.acquisition_mandate_id
        and retained.protection_mandate_id != entry.protection_mandate_id
        and retained.binding_commitment != entry.binding_commitment
        and retained.emergency_recovery_compatibility_commitment
        == entry.emergency_recovery_compatibility_commitment
        and retained.controller_head != entry.controller_head
        and (
            (
                retained.scope_execution_commitment == entry.scope_execution_commitment
                and retained.venue_commitment == entry.venue_commitment
            )
            or terminal_successor
        )
        and state._manual_flatten_by_scope.get(slot_key) is None
    )
    if (
        not (genesis_slot or successor_slot)
        or predecessor_slot_commitment is None
        or predecessor_slot_commitment != entry.predecessor_slot_commitment
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    predecessor_venue_context = state.venue.project_acquisition_context(
        execution,
        entry.position_scope,
    )
    predecessor_authority_context = project_acquisition_authority_context(
        state,
        execution,
        predecessor_venue_context,
    )
    if (
        not predecessor_venue_context.matches_current(
            state.venue,
            execution,
            entry.application_generation_id,
            entry.position_scope,
        )
        or not predecessor_authority_context.matches_current(
            state,
            execution,
            predecessor_venue_context,
        )
        or predecessor_venue_context.scope_execution_commitment
        != entry.scope_execution_commitment
        or predecessor_venue_context.commitment != entry.venue_commitment
        or predecessor_authority_context.authority_commitment
        != admission.authority_commitment
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    next_currentness = (
        _inserted(state._acquisition_currentness_by_scope, slot_key, entry)
        if genesis_slot
        else _replaced(state._acquisition_currentness_by_scope, slot_key, entry)
    )
    next_descriptors = state._acquisition_descriptor_by_scope
    next_active = state._acquisition_active_by_scope
    if successor_slot and (
        _acquisition_effect_descriptor_is_authentic(retained_descriptor)
        and _acquisition_active_effect_is_authentic(retained_active)
    ):
        inactive = _new_acquisition_inactive_slot(
            retained_active,
            retained_descriptor,
            entry.generation_id,
        )
        next_descriptors = _replaced(next_descriptors, slot_key, inactive)
        next_active = _replaced(next_active, slot_key, inactive)
    next_state = _state_with(
        state,
        _acquisition_currentness_by_scope=next_currentness,
        _acquisition_descriptor_by_scope=next_descriptors,
        _acquisition_active_by_scope=next_active,
    )
    next_state = _record_input(next_state, item)
    current_venue_context = next_state.venue.project_acquisition_context(
        execution,
        entry.position_scope,
    )
    current_authority_context = project_acquisition_authority_context(
        next_state,
        execution,
        current_venue_context,
    )
    if not current_venue_context.matches_current(
        next_state.venue,
        execution,
        entry.application_generation_id,
        entry.position_scope,
    ) or not current_authority_context.matches_current(
        next_state,
        execution,
        current_venue_context,
    ):
        raise RuntimeError("registered acquisition currentness failed postcondition")
    receipt = _new_acquisition_authority_receipt(
        operation=AcquisitionAuthorityOperation.REGISTER,
        application_generation_id=entry.application_generation_id,
        position_scope=entry.position_scope,
        predecessor_controller_head=(
            entry.controller_head
            if genesis_slot
            else cast(_AcquisitionCurrentnessEntry, retained).controller_head
        ),
        controller_head=entry.controller_head,
        predecessor_scope_execution_commitment=(
            predecessor_venue_context.scope_execution_commitment
        ),
        scope_execution_commitment=current_venue_context.scope_execution_commitment,
        predecessor_venue_commitment=predecessor_venue_context.commitment,
        venue_commitment=current_venue_context.commitment,
        predecessor_authority_commitment=(
            predecessor_authority_context.authority_commitment
        ),
        authority_commitment=current_authority_context.authority_commitment,
        ordered_venue_transition_commitments=(),
        permit_commitment=registration.commitment,
    )
    return _result(
        next_state,
        AuthorityDisposition.APPLIED,
        acquisition_receipt=receipt,
    )


def _register_canonical_fact_currentness(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: RegisterAcquisitionCurrentness,
) -> ExecutionAuthorityTransition:
    """Atomically rebase one current acquisition slot from a canonical fact."""

    registration = cast(_CanonicalFactCurrentnessRegistration, item.registration)
    if not (
        _register_canonical_fact_currentness_command_is_authentic(item)
        and _canonical_fact_currentness_registration_is_authentic(registration)
        and type(registration._predecessor_authority_context_commitment) is bytes
        and len(registration._predecessor_authority_context_commitment) == 32
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    entry = registration._entry
    projection = registration._fact_projection
    transition = registration._fact_transition
    predecessor_authority_context_commitment = (
        registration._predecessor_authority_context_commitment
    )
    if (
        entry.source_kind is not _AcquisitionCurrentnessSourceKind.CANONICAL_FACT
        or item.input_id != registration._input_id
        or execution is not transition.execution
        or state.session_id != entry.session_id
        or entry.protection_commitment is None
        or entry.application_generation_id != projection.application_generation_id
        or entry.position_scope != projection.position_scope
        or entry.scope_execution_commitment != projection.scope_execution_commitment
        or entry.venue_commitment != projection.venue_commitment
        or type(projection.predecessor_scope_execution_commitment) is not bytes
        or type(projection.predecessor_venue_commitment) is not bytes
        or not projection.matches_fact_transition(transition, entry.position_scope)
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    slot_key = _acquisition_scope_key(
        entry.application_generation_id,
        entry.position_scope,
    )
    retained = state._acquisition_currentness_by_scope.get(slot_key)
    if not (
        _acquisition_currentness_entry_is_authentic(retained)
        and retained.commitment == entry.predecessor_slot_commitment
        and retained.application_generation_id == entry.application_generation_id
        and retained.position_scope == entry.position_scope
        and retained.session_id == entry.session_id
        and retained.generation_id == entry.generation_id
        and retained.acquisition_mandate_id == entry.acquisition_mandate_id
        and retained.protection_mandate_id == entry.protection_mandate_id
        and retained.binding_commitment == entry.binding_commitment
        and retained.emergency_recovery_compatibility_commitment
        == entry.emergency_recovery_compatibility_commitment
        and retained.successor_ordinal == entry.successor_ordinal
        and retained.controller_head != entry.controller_head
        and _canonical_fact_predecessor_is_current(
            state,
            transition,
            projection,
            retained,
            predecessor_authority_context_commitment,
        )
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    next_state = _state_with(
        state,
        venue=transition.book,
        _acquisition_currentness_by_scope=_replaced(
            state._acquisition_currentness_by_scope,
            slot_key,
            entry,
        ),
    )
    next_state = _record_input(next_state, item)
    current_venue_context = next_state.venue.project_acquisition_context(
        execution,
        entry.position_scope,
    )
    current_authority_context = project_acquisition_authority_context(
        next_state,
        execution,
        current_venue_context,
    )
    transition_proof_commitment = transition._protection_proof_commitment
    if not (
        current_venue_context.matches_current(
            next_state.venue,
            execution,
            entry.application_generation_id,
            entry.position_scope,
        )
        and current_authority_context.matches_current(
            next_state,
            execution,
            current_venue_context,
        )
        and current_venue_context.scope_execution_commitment
        == entry.scope_execution_commitment
        and current_venue_context.commitment == entry.venue_commitment
        and type(transition_proof_commitment) is bytes
        and len(transition_proof_commitment) == 32
    ):
        raise RuntimeError("canonical fact registration failed postcondition")
    predecessor_scope_execution_commitment = _require_digest(
        "canonical fact predecessor scope commitment",
        projection.predecessor_scope_execution_commitment,
    )
    predecessor_venue_commitment = _require_digest(
        "canonical fact predecessor venue commitment",
        projection.predecessor_venue_commitment,
    )
    receipt = _new_acquisition_authority_receipt(
        operation=AcquisitionAuthorityOperation.REGISTER,
        application_generation_id=entry.application_generation_id,
        position_scope=entry.position_scope,
        predecessor_controller_head=retained.controller_head,
        controller_head=entry.controller_head,
        predecessor_scope_execution_commitment=(predecessor_scope_execution_commitment),
        scope_execution_commitment=current_venue_context.scope_execution_commitment,
        predecessor_venue_commitment=predecessor_venue_commitment,
        venue_commitment=current_venue_context.commitment,
        predecessor_authority_commitment=predecessor_authority_context_commitment,
        authority_commitment=current_authority_context.authority_commitment,
        ordered_venue_transition_commitments=(transition_proof_commitment,),
        permit_commitment=registration.commitment,
    )
    return _result(
        next_state,
        AuthorityDisposition.APPLIED,
        acquisition_receipt=receipt,
    )


def _register_protection_rebase_currentness(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: RegisterAcquisitionCurrentness,
) -> ExecutionAuthorityTransition:
    """Advance one current slot for an already-sealed semantic protection change."""

    registration = cast(_ProtectionRebaseCurrentnessRegistration, item.registration)
    if not (
        _register_protection_rebase_currentness_command_is_authentic(item)
        and _protection_rebase_currentness_registration_is_authentic(registration)
        and type(registration._predecessor_authority_context_commitment) is bytes
        and len(registration._predecessor_authority_context_commitment) == 32
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    entry = registration._entry
    projection = registration._projection
    predecessor_authority_context_commitment = (
        registration._predecessor_authority_context_commitment
    )
    current_venue_context = state.venue.project_acquisition_context(
        execution,
        entry.position_scope,
    )
    current_authority_context = project_acquisition_authority_context(
        state,
        execution,
        current_venue_context,
    )
    if (
        entry.source_kind is not _AcquisitionCurrentnessSourceKind.PROTECTION_REBASE
        or item.input_id != registration._input_id
        or state.session_id != entry.session_id
        or not current_venue_context.matches_current(
            state.venue,
            execution,
            entry.application_generation_id,
            entry.position_scope,
        )
        or not current_authority_context.matches_current(
            state,
            execution,
            current_venue_context,
        )
        or current_venue_context.scope_execution_commitment
        != entry.scope_execution_commitment
        or current_venue_context.commitment != entry.venue_commitment
        or current_authority_context.authority_commitment
        != predecessor_authority_context_commitment
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    slot_key = _acquisition_scope_key(
        entry.application_generation_id,
        entry.position_scope,
    )
    retained = state._acquisition_currentness_by_scope.get(slot_key)
    if not (
        _acquisition_currentness_entry_is_authentic(retained)
        and retained.commitment == entry.predecessor_slot_commitment
        and retained.application_generation_id == entry.application_generation_id
        and retained.position_scope == entry.position_scope
        and retained.session_id == entry.session_id
        and retained.generation_id == entry.generation_id
        and retained.acquisition_mandate_id == entry.acquisition_mandate_id
        and retained.protection_mandate_id == entry.protection_mandate_id
        and retained.binding_commitment == entry.binding_commitment
        and retained.emergency_recovery_compatibility_commitment
        == entry.emergency_recovery_compatibility_commitment
        and retained.successor_ordinal == entry.successor_ordinal
        and retained.controller_head != entry.controller_head
        and retained.protection_commitment is not None
        and retained.protection_commitment != entry.protection_commitment
        and retained.scope_execution_commitment == entry.scope_execution_commitment
        and retained.venue_commitment == entry.venue_commitment
        and _protection_rebase_projection_is_current(
            projection,
            retained,
            execution,
            current_venue_context,
        )
        and _acquisition_authority_commitment(
            state,
            entry.application_generation_id,
            entry.position_scope,
        )
        == predecessor_authority_context_commitment
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    next_state = _state_with(
        state,
        _acquisition_currentness_by_scope=_replaced(
            state._acquisition_currentness_by_scope,
            slot_key,
            entry,
        ),
    )
    next_state = _record_input(next_state, item)
    next_venue_context = next_state.venue.project_acquisition_context(
        execution,
        entry.position_scope,
    )
    next_authority_context = project_acquisition_authority_context(
        next_state,
        execution,
        next_venue_context,
    )
    if not (
        next_venue_context.matches_current(
            next_state.venue,
            execution,
            entry.application_generation_id,
            entry.position_scope,
        )
        and next_authority_context.matches_current(
            next_state,
            execution,
            next_venue_context,
        )
        and next_venue_context.scope_execution_commitment
        == entry.scope_execution_commitment
        and next_venue_context.commitment == entry.venue_commitment
        and next_authority_context.authority_commitment
        != predecessor_authority_context_commitment
    ):
        raise RuntimeError("protection rebase registration failed postcondition")
    receipt = _new_acquisition_authority_receipt(
        operation=AcquisitionAuthorityOperation.REGISTER,
        application_generation_id=entry.application_generation_id,
        position_scope=entry.position_scope,
        predecessor_controller_head=retained.controller_head,
        controller_head=entry.controller_head,
        predecessor_scope_execution_commitment=(retained.scope_execution_commitment),
        scope_execution_commitment=next_venue_context.scope_execution_commitment,
        predecessor_venue_commitment=retained.venue_commitment,
        venue_commitment=next_venue_context.commitment,
        predecessor_authority_commitment=predecessor_authority_context_commitment,
        authority_commitment=next_authority_context.authority_commitment,
        ordered_venue_transition_commitments=(),
        permit_commitment=registration.commitment,
    )
    return _result(
        next_state,
        AuthorityDisposition.APPLIED,
        acquisition_receipt=receipt,
    )


def _apply_acquisition_bootstrap_initialization(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    *,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    controller_head: bytes,
    refresh: AcquisitionContextRefresh,
    bootstrap: AcquisitionVenueProjection,
    admission: AcquisitionAdmissionProjection,
) -> ExecutionAuthorityTransition:
    """Apply the private R8 registration only as part of controller initialization.

    ``apply_execution_authority_input`` deliberately rejects the private command
    type below.  This narrow owner seam retains ordinary dispatcher replay and
    receipt semantics while preventing a public authority-input caller from
    installing bootstrap currentness without the acquisition composite.
    """

    state = _validate_authority_state(state)
    _require("execution", execution, ExecutionSnapshot)
    if (
        type(refresh) is not AcquisitionContextRefresh
        or type(bootstrap) is not AcquisitionVenueProjection
        or type(admission) is not AcquisitionAdmissionProjection
        or refresh.authority is not state
        or refresh.execution is not execution
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    try:
        command = _mint_acquisition_bootstrap_registration_command(
            application_generation_id=application_generation_id,
            position_scope=position_scope,
            session_id=session_id,
            generation_id=generation_id,
            acquisition_mandate_id=acquisition_mandate_id,
            protection_mandate_id=protection_mandate_id,
            binding_commitment=binding_commitment,
            emergency_recovery_compatibility_commitment=(
                emergency_recovery_compatibility_commitment
            ),
            controller_head=controller_head,
            refresh=refresh,
            bootstrap=bootstrap,
            admission=admission,
        )
    except (TypeError, ValueError):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    if not _register_acquisition_currentness_command_is_authentic(command):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    replay = _replay_or_conflict(state, command)
    if replay is not None:
        return replay
    return _register_acquisition_currentness(state, execution, command)


def _apply_acquisition_successor_registration(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    *,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    refresh: AcquisitionContextRefresh,
    bootstrap: AcquisitionVenueProjection,
    admission: AcquisitionAdmissionProjection,
) -> ExecutionAuthorityTransition:
    """Apply one private serial-successor currentness replacement."""

    state = _validate_authority_state(state)
    _require("execution", execution, ExecutionSnapshot)
    if (
        type(refresh) is not AcquisitionContextRefresh
        or type(bootstrap) is not AcquisitionVenueProjection
        or type(admission) is not AcquisitionAdmissionProjection
        or refresh.authority is not state
        or refresh.execution is not execution
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    try:
        command = _mint_acquisition_successor_registration_command(
            application_generation_id=application_generation_id,
            position_scope=position_scope,
            session_id=session_id,
            generation_id=generation_id,
            acquisition_mandate_id=acquisition_mandate_id,
            protection_mandate_id=protection_mandate_id,
            binding_commitment=binding_commitment,
            emergency_recovery_compatibility_commitment=(
                emergency_recovery_compatibility_commitment
            ),
            controller_head=controller_head,
            successor_ordinal=successor_ordinal,
            refresh=refresh,
            bootstrap=bootstrap,
            admission=admission,
        )
    except (TypeError, ValueError):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    if not _register_acquisition_currentness_command_is_authentic(command):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    replay = _replay_or_conflict(state, command)
    if replay is not None:
        return replay
    return _register_acquisition_currentness(state, execution, command)


def _r8_bootstrap_pair_is_current(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_context_commitment: bytes,
) -> bool:
    """Reprove one sealed R8 continuation from bounded current indexes only."""

    if (
        type(state) is not ExecutionAuthorityState
        or type(execution) is not ExecutionSnapshot
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
    ):
        return False
    for commitment in (
        scope_execution_commitment,
        venue_commitment,
        authority_context_commitment,
    ):
        if type(commitment) is not bytes or len(commitment) != 32:
            return False
    slot_key = _acquisition_scope_key(application_generation_id, position_scope)
    entry = state._acquisition_currentness_by_scope.get(slot_key)
    if not (
        _acquisition_currentness_entry_is_authentic(entry)
        and entry.source_kind is _AcquisitionCurrentnessSourceKind.BOOTSTRAP
    ):
        return False
    venue_context = state.venue.project_acquisition_context(execution, position_scope)
    authority_context = project_acquisition_authority_context(
        state,
        execution,
        venue_context,
    )
    view = _venue_authority_view(
        state.venue,
        execution,
        position_scope,
        None,
    )
    successor_flat = bool(
        entry.successor_ordinal > 0
        and execution.position.raw_quantity == 0
        and execution.integrity is PositionIntegrity.CONSISTENT
        and view.execution_binding_matches
        and view.account_reconciliation_clear
        and view.blocking_effect_count == 0
        and view.blocking_buy_effect_count == 0
        and view.known_cancellable_buy_leg_count == 0
        and view.known_cancel_pending_buy_leg_count == 0
        and view.waiting_buy_parent_count == 0
        and view.unknown_buy_effect_count == 0
    )
    return bool(
        venue_context.matches_current(
            state.venue,
            execution,
            application_generation_id,
            position_scope,
        )
        and authority_context.matches_current(state, execution, venue_context)
        and venue_context.scope_execution_commitment == scope_execution_commitment
        and venue_context.commitment == venue_commitment
        and authority_context.authority_commitment == authority_context_commitment
        and (view.bootstrap_bound_target_active or successor_flat)
    )


def _r8_bootstrap_refresh_is_eligible_for_first_effect(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    refresh: AcquisitionContextRefresh,
) -> bool:
    """Reprove the sealed R8 continuation without re-registering currentness.

    A bootstrap registration seals the first controller coordinates.  An
    unrelated-symbol registry advance may subsequently replace only the active
    bootstrap record's neutral target checkpoint.  This predicate admits that
    bounded continuation when, and only when, the ordinary refresh and the
    currently retained bootstrap record mutually authenticate.  It does not
    update a controller head, registration, mandate, or authority slot.
    """

    if (
        type(state) is not ExecutionAuthorityState
        or type(execution) is not ExecutionSnapshot
        or type(refresh) is not AcquisitionContextRefresh
        or refresh.disposition
        not in {
            AcquisitionContextRefreshDisposition.CURRENT,
            AcquisitionContextRefreshDisposition.REFRESHED,
        }
        or refresh.authority is not state
        or refresh.execution is not execution
        or refresh.venue_context is None
        or refresh.authority_context is None
        or not refresh.matches_current(
            state,
            refresh.application_generation_id,
            refresh.position_scope,
        )
    ):
        return False
    return _r8_bootstrap_pair_is_current(
        state,
        execution,
        refresh.application_generation_id,
        refresh.position_scope,
        refresh.venue_context.scope_execution_commitment,
        refresh.venue_context.commitment,
        refresh.authority_context.authority_commitment,
    )


def _mint_acquisition_effect_permit(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    *,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    predecessor_controller_head: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    protection_commitment: bytes | None,
    terms: AcquisitionEffectTerms,
    refresh: AcquisitionContextRefresh,
    input_id: AuthorityInputId,
) -> AcquisitionEffectPermit:
    """Mint one sealed first-BUY permit from the exact current controller slot.

    This is intentionally a narrow owner seam.  It neither accepts a raw venue
    request nor exposes a mutable registration coordinate: every external
    identity is derived below from the sealed retained slot and the supplied
    replay input.
    """

    exact = _validate_authority_state(state)
    _require("execution", execution, ExecutionSnapshot)
    if (
        type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(session_id) is not SessionId
        or not _acquisition_generation_id_is_canonical(generation_id)
        or type(acquisition_mandate_id) is not AcquisitionMandateId
        or type(protection_mandate_id) is not MandateId
        or type(successor_ordinal) is not int
        or successor_ordinal < 0
        or successor_ordinal > 2**64 - 1
        or type(terms) is not AcquisitionEffectTerms
        or type(refresh) is not AcquisitionContextRefresh
        or type(input_id) is not AuthorityInputId
        or not _optional_digest_is_exact(protection_commitment)
    ):
        raise TypeError("acquisition effect permit requires exact controller inputs")
    for digest in (
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        predecessor_controller_head,
        controller_head,
    ):
        _require_digest("acquisition effect permit commitment", digest)
    if (
        refresh.disposition
        not in {
            AcquisitionContextRefreshDisposition.CURRENT,
            AcquisitionContextRefreshDisposition.REFRESHED,
        }
        or refresh.authority is not exact
        or refresh.execution is not execution
        or refresh.venue_context is None
        or refresh.authority_context is None
        or not refresh.matches_current(exact, application_generation_id, position_scope)
        or exact.session_id != session_id
        or execution.position.scope != position_scope
    ):
        raise ValueError("acquisition effect permit source is not current")
    slot_key = _acquisition_scope_key(application_generation_id, position_scope)
    entry = exact._acquisition_currentness_by_scope.get(slot_key)
    if not _acquisition_currentness_entry_is_authentic(entry):
        raise ValueError("acquisition effect permit has no authentic currentness")
    descriptor_slot = exact._acquisition_descriptor_by_scope.get(slot_key)
    active_slot = exact._acquisition_active_by_scope.get(slot_key)
    slot_available = bool(
        (descriptor_slot is None and active_slot is None)
        or (
            _acquisition_inactive_slot_is_authentic(descriptor_slot)
            and descriptor_slot is active_slot
            and descriptor_slot.successor_generation_id == generation_id
        )
    )
    if (
        entry.source_kind is not _AcquisitionCurrentnessSourceKind.BOOTSTRAP
        or entry.application_generation_id != application_generation_id
        or entry.position_scope != position_scope
        or entry.session_id != session_id
        or entry.generation_id != generation_id
        or entry.acquisition_mandate_id != acquisition_mandate_id
        or entry.protection_mandate_id != protection_mandate_id
        or entry.binding_commitment != binding_commitment
        or entry.emergency_recovery_compatibility_commitment
        != emergency_recovery_compatibility_commitment
        or entry.controller_head != predecessor_controller_head
        or predecessor_controller_head == controller_head
        or entry.successor_ordinal != successor_ordinal
        or entry.protection_commitment != protection_commitment
        or not slot_available
        or exact._manual_flatten_by_scope.get(slot_key) is not None
        or not _r8_bootstrap_refresh_is_eligible_for_first_effect(
            exact,
            execution,
            refresh,
        )
    ):
        raise ValueError("acquisition effect permit currentness is not eligible")
    current_context = project_acquisition_authority_context(
        exact,
        execution,
        refresh.venue_context,
    )
    if (
        not refresh.venue_context.matches_current(
            exact.venue,
            execution,
            application_generation_id,
            position_scope,
        )
        or not current_context.matches_current(exact, execution, refresh.venue_context)
        or current_context.authority_commitment
        != refresh.authority_context.authority_commitment
    ):
        raise ValueError("acquisition effect permit context is not current")
    identity = _commit_parts(
        b"execution-core/acquisition-authority/first-effect-identity/v1",
        entry.commitment,
        input_id.value.encode("utf-8"),
        terms.commitment,
        controller_head,
        execution.commitment,
    )
    return _new_acquisition_effect_permit(
        input_id=input_id,
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        session_id=session_id,
        generation_id=generation_id,
        acquisition_mandate_id=acquisition_mandate_id,
        protection_mandate_id=protection_mandate_id,
        binding_commitment=binding_commitment,
        emergency_recovery_compatibility_commitment=(
            emergency_recovery_compatibility_commitment
        ),
        predecessor_controller_head=predecessor_controller_head,
        controller_head=controller_head,
        successor_ordinal=successor_ordinal,
        execution_snapshot_commitment=execution.commitment,
        scope_execution_commitment=refresh.venue_context.scope_execution_commitment,
        venue_commitment=refresh.venue_context.commitment,
        authority_context_commitment=current_context.authority_commitment,
        protection_commitment=protection_commitment,
        terms=terms,
        effect_id=EffectId(f"acquisition-effect:{identity.hex()}"),
        request_occurrence_id=RequestOccurrenceId(
            f"acquisition-request:{identity.hex()}"
        ),
        client_order_id=ClientOrderId(f"acquisition-client:{identity.hex()}"),
    )


def _mint_acquisition_claim_permit(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    *,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    protection_commitment: bytes | None,
    effect_id: EffectId,
    claim_occurrence_id: ClaimOccurrenceId,
    refresh: AcquisitionContextRefresh,
    input_id: AuthorityInputId,
) -> AcquisitionClaimPermit:
    """Mint one exact final-claim permit from the current acquisition slot."""

    exact = _validate_authority_state(state)
    _require("execution", execution, ExecutionSnapshot)
    if (
        type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(session_id) is not SessionId
        or not _acquisition_generation_id_is_canonical(generation_id)
        or type(acquisition_mandate_id) is not AcquisitionMandateId
        or type(protection_mandate_id) is not MandateId
        or type(successor_ordinal) is not int
        or successor_ordinal < 0
        or successor_ordinal > 2**64 - 1
        or type(effect_id) is not EffectId
        or type(claim_occurrence_id) is not ClaimOccurrenceId
        or type(refresh) is not AcquisitionContextRefresh
        or type(input_id) is not AuthorityInputId
        or not _optional_digest_is_exact(protection_commitment)
    ):
        raise TypeError("acquisition claim permit requires exact controller inputs")
    for digest in (
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        controller_head,
    ):
        _require_digest("acquisition claim permit commitment", digest)
    if (
        refresh.disposition
        not in {
            AcquisitionContextRefreshDisposition.CURRENT,
            AcquisitionContextRefreshDisposition.REFRESHED,
        }
        or refresh.authority is not exact
        or refresh.execution is not execution
        or refresh.venue_context is None
        or refresh.authority_context is None
        or not refresh.matches_current(exact, application_generation_id, position_scope)
        or exact.session_id != session_id
        or execution.position.scope != position_scope
        or execution.commitment != refresh.execution.commitment
    ):
        raise ValueError("acquisition claim permit source is not current")
    slot_key = _acquisition_scope_key(application_generation_id, position_scope)
    entry = exact._acquisition_currentness_by_scope.get(slot_key)
    descriptor = exact._acquisition_descriptor_by_scope.get(slot_key)
    active = exact._acquisition_active_by_scope.get(slot_key)
    if not (
        _acquisition_currentness_entry_is_authentic(entry)
        and _acquisition_effect_descriptor_is_authentic(descriptor)
        and _acquisition_active_effect_is_authentic(active)
    ):
        raise ValueError("acquisition claim permit has no authentic active coordinates")
    entry = cast(_AcquisitionCurrentnessEntry, entry)
    descriptor = cast(_AcquisitionEffectDescriptor, descriptor)
    active = cast(_AcquisitionActiveEffect, active)
    original_permit = descriptor.permit
    authorization = exact._effect_authority_by_id.get(_effect_key(effect_id))
    if (
        entry.source_kind is not _AcquisitionCurrentnessSourceKind.AUTHORITY_MUTATION
        or entry.application_generation_id != application_generation_id
        or entry.position_scope != position_scope
        or entry.session_id != session_id
        or entry.generation_id != generation_id
        or entry.acquisition_mandate_id != acquisition_mandate_id
        or entry.protection_mandate_id != protection_mandate_id
        or entry.binding_commitment != binding_commitment
        or entry.emergency_recovery_compatibility_commitment
        != emergency_recovery_compatibility_commitment
        or entry.controller_head != controller_head
        or entry.successor_ordinal != successor_ordinal
        or entry.protection_commitment != protection_commitment
        or entry.scope_execution_commitment
        != refresh.venue_context.scope_execution_commitment
        or entry.venue_commitment != refresh.venue_context.commitment
        or original_permit.application_generation_id != application_generation_id
        or original_permit.position_scope != position_scope
        or original_permit.session_id != session_id
        or original_permit.generation_id != generation_id
        or original_permit.acquisition_mandate_id != acquisition_mandate_id
        or original_permit.protection_mandate_id != protection_mandate_id
        or original_permit.binding_commitment != binding_commitment
        or original_permit.emergency_recovery_compatibility_commitment
        != emergency_recovery_compatibility_commitment
        or original_permit.controller_head != controller_head
        or original_permit.successor_ordinal != successor_ordinal
        or original_permit.protection_commitment != protection_commitment
        or original_permit.effect_id != effect_id
        or active.effect_id != effect_id
        or active.descriptor_commitment != descriptor.commitment
        or exact._acquisition_descriptor_by_effect.get(_effect_key(effect_id))
        is not descriptor
        or type(authorization) is not _EffectAuthorization
        or authorization.request != _specialized_acquisition_request(original_permit)
        or exact._manual_flatten_by_scope.get(slot_key) is not None
        or exact._claim_by_effect.get(_effect_key(effect_id)) is not None
        or exact._claim_by_occurrence.get(_claim_key(claim_occurrence_id)) is not None
    ):
        raise ValueError("acquisition claim permit currentness is not eligible")
    current_context = project_acquisition_authority_context(
        exact,
        execution,
        refresh.venue_context,
    )
    if (
        not refresh.venue_context.matches_current(
            exact.venue,
            execution,
            application_generation_id,
            position_scope,
        )
        or not current_context.matches_current(exact, execution, refresh.venue_context)
        or current_context.authority_commitment
        != refresh.authority_context.authority_commitment
    ):
        raise ValueError("acquisition claim permit context is not current")
    return _new_acquisition_claim_permit(
        input_id=input_id,
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        session_id=session_id,
        generation_id=generation_id,
        acquisition_mandate_id=acquisition_mandate_id,
        protection_mandate_id=protection_mandate_id,
        binding_commitment=binding_commitment,
        emergency_recovery_compatibility_commitment=(
            emergency_recovery_compatibility_commitment
        ),
        controller_head=controller_head,
        successor_ordinal=successor_ordinal,
        execution_snapshot_commitment=execution.commitment,
        scope_execution_commitment=refresh.venue_context.scope_execution_commitment,
        venue_commitment=refresh.venue_context.commitment,
        authority_context_commitment=current_context.authority_commitment,
        protection_commitment=protection_commitment,
        effect_id=effect_id,
        claim_occurrence_id=claim_occurrence_id,
        currentness_commitment=entry.commitment,
        descriptor_commitment=descriptor.commitment,
        active_commitment=active.commitment,
    )


def _mint_acquisition_exit_permit(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    *,
    purpose: str,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    predecessor_controller_head: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    protection_commitment: bytes,
    residual_quantity: Quantity,
    intent_commitment: bytes,
    refresh: AcquisitionContextRefresh,
    input_id: AuthorityInputId,
    protective_goal_coordinates: tuple[
        ExecutionSide,
        Quantity,
        SessionId,
        MandateId,
        bytes,
        bytes,
        bytes,
    ]
    | None = None,
) -> AcquisitionExitPermit:
    """Mint one exact purpose-bound preemption/exit capability."""

    exact = _validate_authority_state(state)
    _require("execution", execution, ExecutionSnapshot)
    try:
        exit_purpose = _AcquisitionExitPurpose(purpose)
    except (TypeError, ValueError) as error:
        raise TypeError("acquisition exit purpose is not exact") from error
    if (
        type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(session_id) is not SessionId
        or not _acquisition_generation_id_is_canonical(generation_id)
        or type(acquisition_mandate_id) is not AcquisitionMandateId
        or type(protection_mandate_id) is not MandateId
        or type(successor_ordinal) is not int
        or successor_ordinal < 0
        or successor_ordinal > 2**64 - 1
        or type(residual_quantity) is not Quantity
        or residual_quantity.value <= 0
        or type(refresh) is not AcquisitionContextRefresh
        or type(input_id) is not AuthorityInputId
        or (
            protective_goal_coordinates is not None
            and type(protective_goal_coordinates) is not tuple
        )
    ):
        raise TypeError("acquisition exit permit requires exact controller inputs")
    for digest in (
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        predecessor_controller_head,
        controller_head,
        protection_commitment,
        intent_commitment,
    ):
        _require_digest("acquisition exit permit commitment", digest)
    if (
        refresh.disposition is not AcquisitionContextRefreshDisposition.CURRENT
        or refresh.authority is not exact
        or refresh.execution is not execution
        or refresh.venue_context is None
        or refresh.authority_context is None
        or not refresh.matches_current(exact, application_generation_id, position_scope)
        or exact.session_id != session_id
        or execution.position.scope != position_scope
        or execution.position.raw_quantity != residual_quantity.value
    ):
        raise ValueError("acquisition exit permit source is not current")
    slot_key = _acquisition_scope_key(application_generation_id, position_scope)
    entry = exact._acquisition_currentness_by_scope.get(slot_key)
    descriptor = exact._acquisition_descriptor_by_scope.get(slot_key)
    active = exact._acquisition_active_by_scope.get(slot_key)
    if not (
        _acquisition_currentness_entry_is_authentic(entry)
        and _acquisition_effect_descriptor_is_authentic(descriptor)
        and _acquisition_active_effect_is_authentic(active)
    ):
        raise ValueError("acquisition exit permit has no exact active coordinates")
    entry = cast(_AcquisitionCurrentnessEntry, entry)
    descriptor = cast(_AcquisitionEffectDescriptor, descriptor)
    active = cast(_AcquisitionActiveEffect, active)
    if (
        entry.application_generation_id != application_generation_id
        or entry.position_scope != position_scope
        or entry.session_id != session_id
        or entry.generation_id != generation_id
        or entry.acquisition_mandate_id != acquisition_mandate_id
        or entry.protection_mandate_id != protection_mandate_id
        or entry.binding_commitment != binding_commitment
        or entry.emergency_recovery_compatibility_commitment
        != emergency_recovery_compatibility_commitment
        or entry.controller_head != predecessor_controller_head
        or predecessor_controller_head == controller_head
        or entry.successor_ordinal != successor_ordinal
        or descriptor.permit.generation_id != generation_id
        or active.descriptor_commitment != descriptor.commitment
        or exact._acquisition_descriptor_by_effect.get(_effect_key(active.effect_id))
        is not descriptor
        or exact._manual_flatten_by_scope.get(slot_key) is not None
    ):
        raise ValueError("acquisition exit permit currentness is not eligible")
    view = _venue_authority_view(
        exact.venue,
        execution,
        position_scope,
        active.effect_id,
    )
    protective_request = None
    if exit_purpose is _AcquisitionExitPurpose.PREEMPT_BUY_ONLY:
        if (
            protective_goal_coordinates is not None
            or entry.protection_commitment != protection_commitment
        ):
            raise ValueError("acquisition preemption cannot carry SELL coordinates")
        stand_downable = bool(
            view.execution_binding_matches
            and view.account_reconciliation_clear
            and view.blocking_buy_effect_count == 1
            and view.stand_downable_buy_count == 1
            and view.target_exemptible_count == 1
            and view.known_cancellable_buy_leg_count == 0
            and view.known_cancel_pending_buy_leg_count == 0
            and view.waiting_buy_parent_count == 0
            and view.unknown_buy_effect_count == 0
        )
        cancellable = bool(
            view.execution_binding_matches
            and view.account_reconciliation_clear
            and view.blocking_buy_effect_count == 1
            and view.stand_downable_buy_count == 0
            and view.target_exemptible_count == 0
            and view.known_cancellable_buy_leg_count == 1
            and view.known_cancel_pending_buy_leg_count == 0
            and view.waiting_buy_parent_count == 1
            and view.unknown_buy_effect_count == 0
        )
        if not (stand_downable or cancellable):
            raise ValueError("acquisition preemption is not safely local")
    else:
        if protective_goal_coordinates is None or len(protective_goal_coordinates) != 7:
            raise ValueError("protective SELL requires exact owner coordinates")
        (
            goal_side,
            goal_quantity,
            goal_session_id,
            goal_mandate_id,
            goal_execution_commitment,
            goal_protection_commitment,
            goal_commitment,
        ) = protective_goal_coordinates
        if (
            type(goal_side) is not ExecutionSide
            or goal_side is not ExecutionSide.SELL
            or type(goal_quantity) is not Quantity
            or goal_quantity != residual_quantity
            or type(goal_session_id) is not SessionId
            or goal_session_id != session_id
            or type(goal_mandate_id) is not MandateId
            or goal_mandate_id != protection_mandate_id
            or type(goal_execution_commitment) is not bytes
            or goal_execution_commitment != execution.commitment
            or type(goal_protection_commitment) is not bytes
            or len(goal_protection_commitment) != 32
            or type(goal_commitment) is not bytes
            or len(goal_commitment) != 32
            or view.blocking_effect_count != 0
            or view.blocking_buy_effect_count != 0
            or view.stand_downable_buy_count != 0
            or view.known_cancellable_buy_leg_count != 0
            or view.known_cancel_pending_buy_leg_count != 0
            or view.waiting_buy_parent_count != 0
            or view.unknown_buy_effect_count != 0
            or exact._claim_by_effect.get(_effect_key(active.effect_id)) is None
        ):
            raise ValueError("protective SELL source is not closed and current")
        identity = _commit_parts(
            b"execution-core/acquisition-authority/protection-exit-identity/v1",
            entry.commitment,
            input_id.value.encode("utf-8"),
            intent_commitment,
            controller_head,
            execution.commitment,
            goal_protection_commitment,
            goal_commitment,
        )
        protective_request = BrokerEffectRequest(
            effect_id=EffectId(f"acquisition-protection-exit:{identity.hex()}"),
            request_occurrence_id=RequestOccurrenceId(
                f"acquisition-protection-request:{identity.hex()}"
            ),
            mandate_id=goal_mandate_id,
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId(
                f"acquisition-protection-client:{identity.hex()}"
            ),
            symbol_id=position_scope.symbol_id,
            side=goal_side,
            quantity=goal_quantity,
            economic_scope=goal_commitment,
            target_leg_key=None,
        )
    current_context = project_acquisition_authority_context(
        exact,
        execution,
        refresh.venue_context,
    )
    if (
        not current_context.matches_current(exact, execution, refresh.venue_context)
        or current_context.authority_commitment
        != refresh.authority_context.authority_commitment
    ):
        raise ValueError("acquisition exit permit context is not current")
    return _new_acquisition_exit_permit(
        input_id=input_id,
        purpose=exit_purpose,
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        session_id=session_id,
        generation_id=generation_id,
        acquisition_mandate_id=acquisition_mandate_id,
        protection_mandate_id=protection_mandate_id,
        binding_commitment=binding_commitment,
        emergency_recovery_compatibility_commitment=(
            emergency_recovery_compatibility_commitment
        ),
        predecessor_controller_head=predecessor_controller_head,
        controller_head=controller_head,
        successor_ordinal=successor_ordinal,
        execution_snapshot_commitment=execution.commitment,
        scope_execution_commitment=refresh.venue_context.scope_execution_commitment,
        venue_commitment=refresh.venue_context.commitment,
        authority_context_commitment=current_context.authority_commitment,
        predecessor_protection_commitment=entry.protection_commitment,
        protection_commitment=protection_commitment,
        residual_quantity=residual_quantity,
        target_effect_id=active.effect_id,
        protective_request=protective_request,
        intent_commitment=intent_commitment,
    )


def _mint_acquisition_fact_preemption(
    state: ExecutionAuthorityState,
    *,
    fact_transition: VenueRecoveryTransition,
    fact_projection: AcquisitionVenueProjection,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    session_id: SessionId,
    generation_id: AcquisitionGenerationId,
    acquisition_mandate_id: AcquisitionMandateId,
    protection_mandate_id: MandateId,
    binding_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
    predecessor_controller_head: bytes,
    controller_head: bytes,
    successor_ordinal: int,
    protection_commitment: bytes,
    residual_quantity: Quantity,
    intent_commitment: bytes,
    predecessor_authority_context_commitment: bytes,
    input_id: AuthorityInputId,
) -> _AcquisitionFactPreemption | None:
    """Mint the sole ordered currentness source for fact-plus-BUY preemption."""

    exact = _validate_authority_state(state)
    if (
        type(fact_transition) is not VenueRecoveryTransition
        or type(fact_projection) is not AcquisitionVenueProjection
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(session_id) is not SessionId
        or not _acquisition_generation_id_is_canonical(generation_id)
        or type(acquisition_mandate_id) is not AcquisitionMandateId
        or type(protection_mandate_id) is not MandateId
        or type(successor_ordinal) is not int
        or successor_ordinal < 0
        or successor_ordinal > 2**64 - 1
        or type(residual_quantity) is not Quantity
        or residual_quantity.value <= 0
        or type(input_id) is not AuthorityInputId
    ):
        raise TypeError("fact preemption requires exact controller inputs")
    for digest in (
        binding_commitment,
        emergency_recovery_compatibility_commitment,
        predecessor_controller_head,
        controller_head,
        protection_commitment,
        intent_commitment,
        predecessor_authority_context_commitment,
    ):
        _require_digest("fact preemption commitment", digest)
    slot_key = _acquisition_scope_key(application_generation_id, position_scope)
    entry = exact._acquisition_currentness_by_scope.get(slot_key)
    descriptor = exact._acquisition_descriptor_by_scope.get(slot_key)
    active = exact._acquisition_active_by_scope.get(slot_key)
    relation = fact_projection.fact_relation()
    if not _acquisition_currentness_entry_is_authentic(entry) or relation is None:
        raise ValueError("fact preemption has no exact current coordinates")
    entry = cast(_AcquisitionCurrentnessEntry, entry)
    if (
        exact.session_id != session_id
        or fact_transition.execution.position.scope != position_scope
        or fact_transition.execution.position.raw_quantity != residual_quantity.value
        or fact_projection.predecessor_execution_snapshot_commitment is None
        or fact_projection.execution_snapshot_commitment
        != fact_transition.execution.commitment
        or entry.application_generation_id != application_generation_id
        or entry.position_scope != position_scope
        or entry.session_id != session_id
        or entry.generation_id != generation_id
        or entry.acquisition_mandate_id != acquisition_mandate_id
        or entry.protection_mandate_id != protection_mandate_id
        or entry.binding_commitment != binding_commitment
        or entry.emergency_recovery_compatibility_commitment
        != emergency_recovery_compatibility_commitment
        or entry.controller_head != predecessor_controller_head
        or predecessor_controller_head == controller_head
        or entry.successor_ordinal != successor_ordinal
        or exact._manual_flatten_by_scope.get(slot_key) is not None
        or not _canonical_fact_predecessor_is_current(
            exact,
            fact_transition,
            fact_projection,
            entry,
            predecessor_authority_context_commitment,
        )
    ):
        raise ValueError("fact preemption currentness is not eligible")
    if _acquisition_inactive_slot_is_authentic(descriptor):
        if not (
            active is descriptor
            and descriptor.successor_generation_id == generation_id
            and descriptor.predecessor_effect_id == relation.effect_id
        ):
            raise ValueError("fact preemption inactive slot is not exact")
        return None
    if not (
        _acquisition_effect_descriptor_is_authentic(descriptor)
        and _acquisition_active_effect_is_authentic(active)
    ):
        raise ValueError("fact preemption has no exact current BUY")
    descriptor = cast(_AcquisitionEffectDescriptor, descriptor)
    active = cast(_AcquisitionActiveEffect, active)
    if (
        active.effect_id != descriptor.permit.effect_id
        or active.descriptor_commitment != descriptor.commitment
        or descriptor.permit.generation_id != generation_id
        or relation.effect_id == active.effect_id
    ):
        raise ValueError("fact preemption current BUY is not exact")
    view = _venue_authority_view(
        fact_transition.book,
        fact_transition.execution,
        position_scope,
        active.effect_id,
    )
    stand_downable = bool(
        view.execution_binding_matches
        and view.account_reconciliation_clear
        and view.blocking_buy_effect_count == 1
        and view.stand_downable_buy_count == 1
        and view.target_exemptible_count == 1
        and view.known_cancellable_buy_leg_count == 0
        and view.known_cancel_pending_buy_leg_count == 0
        and view.waiting_buy_parent_count == 0
        and view.unknown_buy_effect_count == 0
    )
    cancellable = bool(
        view.execution_binding_matches
        and view.account_reconciliation_clear
        and view.blocking_buy_effect_count == 1
        and view.stand_downable_buy_count == 0
        and view.target_exemptible_count == 0
        and view.known_cancellable_buy_leg_count == 1
        and view.known_cancel_pending_buy_leg_count == 0
        and view.waiting_buy_parent_count == 1
        and view.unknown_buy_effect_count == 0
    )
    if not (
        fact_projection.predecessor_scope_execution_commitment
        == entry.scope_execution_commitment
        and fact_projection.predecessor_venue_commitment == entry.venue_commitment
        and (stand_downable or cancellable)
    ):
        raise ValueError("fact preemption is not safely local")
    permit = _new_acquisition_exit_permit(
        input_id=input_id,
        purpose=_AcquisitionExitPurpose.PREEMPT_BUY_ONLY,
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        session_id=session_id,
        generation_id=generation_id,
        acquisition_mandate_id=acquisition_mandate_id,
        protection_mandate_id=protection_mandate_id,
        binding_commitment=binding_commitment,
        emergency_recovery_compatibility_commitment=(
            emergency_recovery_compatibility_commitment
        ),
        predecessor_controller_head=predecessor_controller_head,
        controller_head=controller_head,
        successor_ordinal=successor_ordinal,
        execution_snapshot_commitment=fact_transition.execution.commitment,
        scope_execution_commitment=entry.scope_execution_commitment,
        venue_commitment=entry.venue_commitment,
        authority_context_commitment=predecessor_authority_context_commitment,
        predecessor_protection_commitment=entry.protection_commitment,
        protection_commitment=protection_commitment,
        residual_quantity=residual_quantity,
        target_effect_id=active.effect_id,
        protective_request=None,
        intent_commitment=intent_commitment,
    )
    return _new_acquisition_fact_preemption(
        input_id=input_id,
        permit=permit,
        fact_transition=fact_transition,
        fact_projection=fact_projection,
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
    return _venue_request_from_request(item.input_id, item.request)


def _venue_request_from_request(
    input_id: AuthorityInputId,
    request: BrokerEffectRequest,
) -> RequestedEffect:
    _require("input_id", input_id, AuthorityInputId)
    _require("request", request, BrokerEffectRequest)
    return RequestedEffect(
        input_id=_venue_input_id(input_id, "request"),
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
    state: ExecutionAuthorityState,
    item: _AuthorityCommand | _AcquisitionFactPreemption,
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
    request_scope = _position_scope(state, request.symbol_id)
    request_slot = _acquisition_scope_key(state.venue.scope.generation, request_scope)
    if (
        request.side is ExecutionSide.BUY
        and _acquisition_currentness_entry_is_authentic(
            state._acquisition_currentness_by_scope.get(request_slot)
        )
    ):
        # Once E2 owns a scope, every exposure-increasing BUY is reserved for
        # its sealed specialized route.  This is separate from the R8 record
        # guard below, which also protects the period before registration.
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    if request.kind is EffectKind.CANCEL and request.target_leg_key is not None:
        target_owner = state.venue.owner(request.target_leg_key)
        if target_owner is not None and _acquisition_effect_descriptor_is_authentic(
            state._acquisition_descriptor_by_effect.get(
                _effect_key(target_owner.effect_id)
            )
        ):
            # Once a sealed acquisition effect owns a leg, generic cancellation
            # would bypass the same specialized lifecycle that owns its claim.
            return _result(
                state,
                AuthorityDisposition.REFUSED,
                AuthorityReason.VENUE_UNCERTAIN,
            )
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
    if (
        request.kind is EffectKind.SUBMIT
        and request.side is ExecutionSide.BUY
        and _execution_scope_matches(state, execution, request.symbol_id)
        and _venue_authority_view(
            state.venue,
            execution,
            _position_scope(state, request.symbol_id),
            None,
        ).bootstrap_bound_target_active
    ):
        # R8 reserves this one pre-effect target pair for the specialized
        # acquisition route.  Generic BUY never consumes the active record.
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
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


def _specialized_acquisition_request(
    permit: AcquisitionEffectPermit,
) -> BrokerEffectRequest:
    """Derive the one venue request from an already-authenticated permit."""

    if not _acquisition_effect_permit_is_authentic(permit):
        raise TypeError("specialized acquisition request requires an authentic permit")
    return BrokerEffectRequest(
        effect_id=permit.effect_id,
        request_occurrence_id=permit.request_occurrence_id,
        # R3: broker-visible mandate identity is always the linked protection
        # mandate; the distinct acquisition identity remains sealed in permit,
        # descriptor, and direct lineage.
        mandate_id=permit.protection_mandate_id,
        kind=EffectKind.SUBMIT,
        client_order_id=permit.client_order_id,
        symbol_id=permit.position_scope.symbol_id,
        side=ExecutionSide.BUY,
        quantity=permit.terms.quantity,
        economic_scope=permit.terms.commitment,
        target_leg_key=None,
    )


def _specialized_acquisition_permit_is_current(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    permit: AcquisitionEffectPermit,
) -> bool:
    """Reprove every bounded pre-effect authority coordinate at mutation time."""

    if not _acquisition_effect_permit_is_authentic(permit):
        return False
    if (
        state.session_id != permit.session_id
        or execution.position.scope != permit.position_scope
        or execution.commitment != permit.execution_snapshot_commitment
        or state._manual_flatten_by_scope.get(
            _acquisition_scope_key(
                permit.application_generation_id,
                permit.position_scope,
            )
        )
        is not None
    ):
        return False
    slot_key = _acquisition_scope_key(
        permit.application_generation_id,
        permit.position_scope,
    )
    entry = state._acquisition_currentness_by_scope.get(slot_key)
    if not _acquisition_currentness_entry_is_authentic(entry):
        return False
    descriptor_slot = state._acquisition_descriptor_by_scope.get(slot_key)
    active_slot = state._acquisition_active_by_scope.get(slot_key)
    slot_available = bool(
        (descriptor_slot is None and active_slot is None)
        or (
            _acquisition_inactive_slot_is_authentic(descriptor_slot)
            and descriptor_slot is active_slot
            and descriptor_slot.successor_generation_id == permit.generation_id
        )
    )
    if (
        entry.source_kind is not _AcquisitionCurrentnessSourceKind.BOOTSTRAP
        or entry.application_generation_id != permit.application_generation_id
        or entry.position_scope != permit.position_scope
        or entry.session_id != permit.session_id
        or entry.generation_id != permit.generation_id
        or entry.acquisition_mandate_id != permit.acquisition_mandate_id
        or entry.protection_mandate_id != permit.protection_mandate_id
        or entry.binding_commitment != permit.binding_commitment
        or entry.emergency_recovery_compatibility_commitment
        != permit.emergency_recovery_compatibility_commitment
        or entry.controller_head != permit.predecessor_controller_head
        or entry.successor_ordinal != permit.successor_ordinal
        or entry.protection_commitment != permit.protection_commitment
        or not slot_available
        or state._acquisition_descriptor_by_effect.get(_effect_key(permit.effect_id))
        is not None
        or not _r8_bootstrap_pair_is_current(
            state,
            execution,
            permit.application_generation_id,
            permit.position_scope,
            permit.scope_execution_commitment,
            permit.venue_commitment,
            permit.authority_context_commitment,
        )
    ):
        return False
    venue_context = state.venue.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    authority_context = project_acquisition_authority_context(
        state,
        execution,
        venue_context,
    )
    return bool(
        venue_context.matches_current(
            state.venue,
            execution,
            permit.application_generation_id,
            permit.position_scope,
        )
        and authority_context.matches_current(state, execution, venue_context)
        and venue_context.scope_execution_commitment
        == permit.scope_execution_commitment
        and venue_context.commitment == permit.venue_commitment
        and authority_context.authority_commitment
        == permit.authority_context_commitment
        and _r8_bootstrap_pair_is_current(
            state,
            execution,
            permit.application_generation_id,
            permit.position_scope,
            permit.scope_execution_commitment,
            permit.venue_commitment,
            permit.authority_context_commitment,
        )
    )


def _create_acquisition_effect(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: CreateAcquisitionEffect,
) -> ExecutionAuthorityTransition:
    """Apply one sealed first-generation acquisition BUY as one composite step."""

    permit = item.permit
    if (
        not _acquisition_effect_permit_is_authentic(permit)
        or item.input_id != permit.input_id
        or not _specialized_acquisition_permit_is_current(state, execution, permit)
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    request = _specialized_acquisition_request(permit)
    if _authority_effect_identity_conflicts(
        state.venue,
        request.effect_id,
        request.request_occurrence_id,
        request.client_order_id,
    ):
        return _result(state, AuthorityDisposition.CONFLICT)
    ordinary_gate = _create_gate_reason(
        state,
        execution,
        CreateBrokerEffect(
            input_id=item.input_id,
            session_id=permit.session_id,
            request=request,
            manual_flatten_id=None,
            emergency_grant_id=None,
        ),
    )
    if ordinary_gate is not None:
        return _result(state, AuthorityDisposition.REFUSED, ordinary_gate)
    venue_reason = _venue_reason(
        state,
        execution,
        request.symbol_id,
        None,
        require_clear=True,
    )
    if venue_reason is not None:
        return _result(state, AuthorityDisposition.REFUSED, venue_reason)
    venue_transition = _authority_request_acquisition_effect(
        state.venue,
        execution,
        _venue_request_from_request(item.input_id, request),
    )
    if venue_transition.disposition is VenueRecoveryDisposition.CONFLICT:
        return _result(state, AuthorityDisposition.CONFLICT)
    if venue_transition.disposition is not VenueRecoveryDisposition.APPLIED:
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    predecessor_venue_context = state.venue.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    predecessor_authority_context = project_acquisition_authority_context(
        state,
        execution,
        predecessor_venue_context,
    )
    current_venue_context = venue_transition.book.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    if (
        not predecessor_venue_context.matches_current(
            state.venue,
            execution,
            permit.application_generation_id,
            permit.position_scope,
        )
        or not predecessor_authority_context.matches_current(
            state,
            execution,
            predecessor_venue_context,
        )
        or not current_venue_context.matches_current(
            venue_transition.book,
            execution,
            permit.application_generation_id,
            permit.position_scope,
        )
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    slot_key = _acquisition_scope_key(
        permit.application_generation_id,
        permit.position_scope,
    )
    previous_entry = state._acquisition_currentness_by_scope.get(slot_key)
    if not _acquisition_currentness_entry_is_authentic(previous_entry):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    next_entry = _new_acquisition_currentness_entry(
        source_kind=_AcquisitionCurrentnessSourceKind.AUTHORITY_MUTATION,
        application_generation_id=permit.application_generation_id,
        position_scope=permit.position_scope,
        session_id=permit.session_id,
        generation_id=permit.generation_id,
        acquisition_mandate_id=permit.acquisition_mandate_id,
        protection_mandate_id=permit.protection_mandate_id,
        binding_commitment=permit.binding_commitment,
        emergency_recovery_compatibility_commitment=(
            permit.emergency_recovery_compatibility_commitment
        ),
        controller_head=permit.controller_head,
        successor_ordinal=permit.successor_ordinal,
        scope_execution_commitment=current_venue_context.scope_execution_commitment,
        venue_commitment=current_venue_context.commitment,
        protection_commitment=permit.protection_commitment,
        predecessor_slot_commitment=previous_entry.commitment,
    )
    descriptor = _new_acquisition_effect_descriptor(permit)
    active = _new_acquisition_active_effect(descriptor)
    authorization = _EffectAuthorization(
        request=request,
        session_id=permit.session_id,
        manual_flatten_id=None,
        emergency_grant_id=None,
    )
    next_state = _state_with(
        state,
        venue=venue_transition.book,
        _effect_authority_by_id=_inserted(
            state._effect_authority_by_id,
            _effect_key(request.effect_id),
            authorization,
        ),
        _acquisition_currentness_by_scope=_replaced(
            state._acquisition_currentness_by_scope,
            slot_key,
            next_entry,
        ),
        _acquisition_descriptor_by_scope=(
            _inserted(
                state._acquisition_descriptor_by_scope,
                slot_key,
                descriptor,
            )
            if state._acquisition_descriptor_by_scope.get(slot_key) is None
            else _replaced(
                state._acquisition_descriptor_by_scope,
                slot_key,
                descriptor,
            )
        ),
        _acquisition_descriptor_by_effect=_inserted(
            state._acquisition_descriptor_by_effect,
            _effect_key(request.effect_id),
            descriptor,
        ),
        _acquisition_active_by_scope=(
            _inserted(
                state._acquisition_active_by_scope,
                slot_key,
                active,
            )
            if state._acquisition_active_by_scope.get(slot_key) is None
            else _replaced(
                state._acquisition_active_by_scope,
                slot_key,
                active,
            )
        ),
    )
    next_state = _record_input(next_state, item)
    post_venue_context = next_state.venue.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    post_authority_context = project_acquisition_authority_context(
        next_state,
        execution,
        post_venue_context,
    )
    if (
        not post_venue_context.matches_current(
            next_state.venue,
            execution,
            permit.application_generation_id,
            permit.position_scope,
        )
        or not post_authority_context.matches_current(
            next_state,
            execution,
            post_venue_context,
        )
        or post_venue_context.scope_execution_commitment
        != next_entry.scope_execution_commitment
        or post_venue_context.commitment != next_entry.venue_commitment
    ):
        raise RuntimeError("specialized acquisition creation failed postcondition")
    receipt = _new_acquisition_authority_receipt(
        operation=AcquisitionAuthorityOperation.CREATE,
        application_generation_id=permit.application_generation_id,
        position_scope=permit.position_scope,
        predecessor_controller_head=permit.predecessor_controller_head,
        controller_head=permit.controller_head,
        predecessor_scope_execution_commitment=(
            predecessor_venue_context.scope_execution_commitment
        ),
        scope_execution_commitment=post_venue_context.scope_execution_commitment,
        predecessor_venue_commitment=predecessor_venue_context.commitment,
        venue_commitment=post_venue_context.commitment,
        predecessor_authority_commitment=(
            predecessor_authority_context.authority_commitment
        ),
        authority_commitment=post_authority_context.authority_commitment,
        ordered_venue_transition_commitments=(
            venue_transition._protection_proof_commitment,
        ),
        permit_commitment=permit.commitment,
    )
    return _result(
        next_state,
        AuthorityDisposition.APPLIED,
        created=(request.effect_id,),
        venue_transitions=(venue_transition,),
        acquisition_receipt=receipt,
    )


def _specialized_acquisition_claim_permit_is_current(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    permit: AcquisitionClaimPermit,
) -> bool:
    """Reprove one exact post-create acquisition claim at mutation time."""

    if not _acquisition_claim_permit_is_authentic(permit):
        return False
    if (
        state.session_id != permit.session_id
        or execution.position.scope != permit.position_scope
        or execution.commitment != permit.execution_snapshot_commitment
    ):
        return False
    slot_key = _acquisition_scope_key(
        permit.application_generation_id,
        permit.position_scope,
    )
    entry = state._acquisition_currentness_by_scope.get(slot_key)
    descriptor = state._acquisition_descriptor_by_scope.get(slot_key)
    active = state._acquisition_active_by_scope.get(slot_key)
    if not (
        _acquisition_currentness_entry_is_authentic(entry)
        and _acquisition_effect_descriptor_is_authentic(descriptor)
        and _acquisition_active_effect_is_authentic(active)
    ):
        return False
    entry = cast(_AcquisitionCurrentnessEntry, entry)
    descriptor = cast(_AcquisitionEffectDescriptor, descriptor)
    active = cast(_AcquisitionActiveEffect, active)
    original_permit = descriptor.permit
    authorization = state._effect_authority_by_id.get(_effect_key(permit.effect_id))
    if (
        entry.source_kind is not _AcquisitionCurrentnessSourceKind.AUTHORITY_MUTATION
        or entry.application_generation_id != permit.application_generation_id
        or entry.position_scope != permit.position_scope
        or entry.session_id != permit.session_id
        or entry.generation_id != permit.generation_id
        or entry.acquisition_mandate_id != permit.acquisition_mandate_id
        or entry.protection_mandate_id != permit.protection_mandate_id
        or entry.binding_commitment != permit.binding_commitment
        or entry.emergency_recovery_compatibility_commitment
        != permit.emergency_recovery_compatibility_commitment
        or entry.controller_head != permit.controller_head
        or entry.successor_ordinal != permit.successor_ordinal
        or entry.protection_commitment != permit.protection_commitment
        or entry.scope_execution_commitment != permit.scope_execution_commitment
        or entry.venue_commitment != permit.venue_commitment
        or entry.commitment != permit.currentness_commitment
        or descriptor.commitment != permit.descriptor_commitment
        or active.commitment != permit.active_commitment
        or active.effect_id != permit.effect_id
        or active.descriptor_commitment != descriptor.commitment
        or state._acquisition_descriptor_by_effect.get(_effect_key(permit.effect_id))
        is not descriptor
        or state._manual_flatten_by_scope.get(slot_key) is not None
        or state._claim_by_effect.get(_effect_key(permit.effect_id)) is not None
        or state._claim_by_occurrence.get(_claim_key(permit.claim_occurrence_id))
        is not None
        or original_permit.application_generation_id != permit.application_generation_id
        or original_permit.position_scope != permit.position_scope
        or original_permit.session_id != permit.session_id
        or original_permit.generation_id != permit.generation_id
        or original_permit.acquisition_mandate_id != permit.acquisition_mandate_id
        or original_permit.protection_mandate_id != permit.protection_mandate_id
        or original_permit.binding_commitment != permit.binding_commitment
        or original_permit.emergency_recovery_compatibility_commitment
        != permit.emergency_recovery_compatibility_commitment
        or original_permit.controller_head != permit.controller_head
        or original_permit.successor_ordinal != permit.successor_ordinal
        or original_permit.protection_commitment != permit.protection_commitment
        or original_permit.effect_id != permit.effect_id
        or type(authorization) is not _EffectAuthorization
        or authorization.request != _specialized_acquisition_request(original_permit)
    ):
        return False
    venue_context = state.venue.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    authority_context = project_acquisition_authority_context(
        state,
        execution,
        venue_context,
    )
    return bool(
        venue_context.matches_current(
            state.venue,
            execution,
            permit.application_generation_id,
            permit.position_scope,
        )
        and authority_context.matches_current(state, execution, venue_context)
        and venue_context.scope_execution_commitment
        == permit.scope_execution_commitment
        and venue_context.commitment == permit.venue_commitment
        and authority_context.authority_commitment
        == permit.authority_context_commitment
    )


def _claim_acquisition_effect(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: ClaimAcquisitionEffect,
) -> ExecutionAuthorityTransition:
    """Claim one sealed acquisition BUY without exposing a generic claim."""

    permit = item.permit
    if (
        not _acquisition_claim_permit_is_authentic(permit)
        or item.input_id != permit.input_id
        or item.effect_id != permit.effect_id
        or item.claim_occurrence_id != permit.claim_occurrence_id
        or not _specialized_acquisition_claim_permit_is_current(
            state,
            execution,
            permit,
        )
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    slot_key = _acquisition_scope_key(
        permit.application_generation_id,
        permit.position_scope,
    )
    previous_entry = state._acquisition_currentness_by_scope.get(slot_key)
    descriptor = state._acquisition_descriptor_by_scope.get(slot_key)
    if not (
        _acquisition_currentness_entry_is_authentic(previous_entry)
        and _acquisition_effect_descriptor_is_authentic(descriptor)
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    previous_entry = cast(_AcquisitionCurrentnessEntry, previous_entry)
    descriptor = cast(_AcquisitionEffectDescriptor, descriptor)
    authorization = state._effect_authority_by_id.get(_effect_key(item.effect_id))
    if type(authorization) is not _EffectAuthorization:
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.EFFECT_UNKNOWN,
        )
    reason = _claim_gate_reason(state, execution, authorization)
    if reason is not None:
        return _result(state, AuthorityDisposition.REFUSED, reason)
    request = authorization.request
    reason = _venue_reason(
        state,
        execution,
        request.symbol_id,
        item.effect_id,
        require_clear=True,
    )
    if reason is not None:
        return _result(state, AuthorityDisposition.REFUSED, reason)
    predecessor_venue_context = state.venue.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    predecessor_authority_context = project_acquisition_authority_context(
        state,
        execution,
        predecessor_venue_context,
    )
    venue_transition = _authority_claim_effect(
        state.venue,
        execution,
        RecordDispatchClaim(
            input_id=_venue_input_id(item.input_id, "acquisition-claim"),
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
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    current_venue_context = venue_transition.book.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    if not (
        predecessor_venue_context.matches_current(
            state.venue,
            execution,
            permit.application_generation_id,
            permit.position_scope,
        )
        and predecessor_authority_context.matches_current(
            state,
            execution,
            predecessor_venue_context,
        )
        and current_venue_context.matches_current(
            venue_transition.book,
            execution,
            permit.application_generation_id,
            permit.position_scope,
        )
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    next_entry = _new_acquisition_currentness_entry(
        source_kind=_AcquisitionCurrentnessSourceKind.AUTHORITY_MUTATION,
        application_generation_id=permit.application_generation_id,
        position_scope=permit.position_scope,
        session_id=permit.session_id,
        generation_id=permit.generation_id,
        acquisition_mandate_id=permit.acquisition_mandate_id,
        protection_mandate_id=permit.protection_mandate_id,
        binding_commitment=permit.binding_commitment,
        emergency_recovery_compatibility_commitment=(
            permit.emergency_recovery_compatibility_commitment
        ),
        controller_head=permit.controller_head,
        successor_ordinal=permit.successor_ordinal,
        scope_execution_commitment=current_venue_context.scope_execution_commitment,
        venue_commitment=current_venue_context.commitment,
        protection_commitment=permit.protection_commitment,
        predecessor_slot_commitment=previous_entry.commitment,
    )
    next_state = _state_with(
        state,
        venue=venue_transition.book,
        budget=RequestBudget(
            remaining=state.budget.remaining - 1,
            safety_reserve=state.budget.safety_reserve,
        ),
        _claim_by_effect=_inserted(
            state._claim_by_effect,
            _effect_key(item.effect_id),
            item,
        ),
        _claim_by_occurrence=_inserted(
            state._claim_by_occurrence,
            _claim_key(item.claim_occurrence_id),
            item,
        ),
        _acquisition_currentness_by_scope=_replaced(
            state._acquisition_currentness_by_scope,
            slot_key,
            next_entry,
        ),
    )
    next_state = _record_input(next_state, item)
    post_venue_context = next_state.venue.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    post_authority_context = project_acquisition_authority_context(
        next_state,
        execution,
        post_venue_context,
    )
    if not (
        post_venue_context.matches_current(
            next_state.venue,
            execution,
            permit.application_generation_id,
            permit.position_scope,
        )
        and post_authority_context.matches_current(
            next_state,
            execution,
            post_venue_context,
        )
        and post_venue_context.scope_execution_commitment
        == next_entry.scope_execution_commitment
        and post_venue_context.commitment == next_entry.venue_commitment
    ):
        raise RuntimeError("specialized acquisition claim failed postcondition")
    receipt = _new_acquisition_authority_receipt(
        operation=AcquisitionAuthorityOperation.CLAIM,
        application_generation_id=permit.application_generation_id,
        position_scope=permit.position_scope,
        predecessor_controller_head=permit.controller_head,
        controller_head=permit.controller_head,
        predecessor_scope_execution_commitment=(
            predecessor_venue_context.scope_execution_commitment
        ),
        scope_execution_commitment=post_venue_context.scope_execution_commitment,
        predecessor_venue_commitment=predecessor_venue_context.commitment,
        venue_commitment=post_venue_context.commitment,
        predecessor_authority_commitment=(
            predecessor_authority_context.authority_commitment
        ),
        authority_commitment=post_authority_context.authority_commitment,
        ordered_venue_transition_commitments=(
            venue_transition._protection_proof_commitment,
        ),
        permit_commitment=permit.commitment,
    )
    claim_receipt = _new_acquisition_claim_receipt(
        input_id=item.input_id,
        effect_id=item.effect_id,
        claim_occurrence_id=item.claim_occurrence_id,
        controller_head=permit.controller_head,
        scope_execution_commitment=post_venue_context.scope_execution_commitment,
        venue_commitment=post_venue_context.commitment,
        authority_context_commitment=post_authority_context.authority_commitment,
        permit_commitment=permit.commitment,
    )
    return _result(
        next_state,
        AuthorityDisposition.APPLIED,
        venue_transitions=(venue_transition,),
        acquisition_receipt=receipt,
        acquisition_claim_receipt=claim_receipt,
    )


def _begin_acquisition_preemption(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: BeginAcquisitionPreemption,
) -> ExecutionAuthorityTransition:
    """Atomically stand down one exact never-dispatched acquisition BUY."""

    permit = item.permit
    if (
        not _acquisition_exit_permit_is_authentic(permit)
        or item.input_id != permit.input_id
        or permit.purpose is not _AcquisitionExitPurpose.PREEMPT_BUY_ONLY
        or permit.target_effect_id is None
        or state.session_id != permit.session_id
        or execution.position.scope != permit.position_scope
        or execution.commitment != permit.execution_snapshot_commitment
        or execution.position.raw_quantity != permit.residual_quantity.value
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    slot_key = _acquisition_scope_key(
        permit.application_generation_id,
        permit.position_scope,
    )
    retained = state._acquisition_currentness_by_scope.get(slot_key)
    descriptor = state._acquisition_descriptor_by_scope.get(slot_key)
    active = state._acquisition_active_by_scope.get(slot_key)
    if not (
        _acquisition_currentness_entry_is_authentic(retained)
        and _acquisition_effect_descriptor_is_authentic(descriptor)
        and _acquisition_active_effect_is_authentic(active)
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    retained = cast(_AcquisitionCurrentnessEntry, retained)
    descriptor = cast(_AcquisitionEffectDescriptor, descriptor)
    active = cast(_AcquisitionActiveEffect, active)
    if (
        retained.application_generation_id != permit.application_generation_id
        or retained.position_scope != permit.position_scope
        or retained.session_id != permit.session_id
        or retained.generation_id != permit.generation_id
        or retained.acquisition_mandate_id != permit.acquisition_mandate_id
        or retained.protection_mandate_id != permit.protection_mandate_id
        or retained.binding_commitment != permit.binding_commitment
        or retained.emergency_recovery_compatibility_commitment
        != permit.emergency_recovery_compatibility_commitment
        or retained.controller_head != permit.predecessor_controller_head
        or retained.successor_ordinal != permit.successor_ordinal
        or retained.protection_commitment != permit.protection_commitment
        or active.effect_id != permit.target_effect_id
        or active.descriptor_commitment != descriptor.commitment
        or descriptor.permit.generation_id != permit.generation_id
        or state._acquisition_descriptor_by_effect.get(
            _effect_key(permit.target_effect_id)
        )
        is not descriptor
        or state._manual_flatten_by_scope.get(slot_key) is not None
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    predecessor_venue_context = state.venue.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    predecessor_authority_context = project_acquisition_authority_context(
        state,
        execution,
        predecessor_venue_context,
    )
    if not (
        predecessor_venue_context.matches_current(
            state.venue,
            execution,
            permit.application_generation_id,
            permit.position_scope,
        )
        and predecessor_authority_context.matches_current(
            state,
            execution,
            predecessor_venue_context,
        )
        and predecessor_venue_context.scope_execution_commitment
        == permit.scope_execution_commitment
        and predecessor_venue_context.commitment == permit.venue_commitment
        and predecessor_authority_context.authority_commitment
        == permit.authority_context_commitment
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    preempted = _authority_begin_symbol_flatten(
        state.venue,
        execution,
        permit.position_scope,
        permit.protection_mandate_id,
        f"acquisition-preempt:{item.input_id.value}",
    )
    if preempted is None:
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    next_venue, created_cancel_ids, transitions = preempted
    if len(created_cancel_ids) > 1:
        raise RuntimeError("acquisition preemption exceeded the one-cancel cap")
    effect_authority = state._effect_authority_by_id
    for effect_id in created_cancel_ids:
        effect = next_venue._current_effect(effect_id)
        if effect is None or effect.scope.kind is not EffectKind.CANCEL:
            raise RuntimeError("acquisition preemption omitted its exact cancel effect")
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
            _EffectAuthorization(request, permit.session_id, None, None),
        )
    next_venue_context = next_venue.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    next_entry = _new_acquisition_currentness_entry(
        source_kind=_AcquisitionCurrentnessSourceKind.AUTHORITY_MUTATION,
        application_generation_id=permit.application_generation_id,
        position_scope=permit.position_scope,
        session_id=permit.session_id,
        generation_id=permit.generation_id,
        acquisition_mandate_id=permit.acquisition_mandate_id,
        protection_mandate_id=permit.protection_mandate_id,
        binding_commitment=permit.binding_commitment,
        emergency_recovery_compatibility_commitment=(
            permit.emergency_recovery_compatibility_commitment
        ),
        controller_head=permit.controller_head,
        successor_ordinal=permit.successor_ordinal,
        scope_execution_commitment=next_venue_context.scope_execution_commitment,
        venue_commitment=next_venue_context.commitment,
        protection_commitment=permit.protection_commitment,
        predecessor_slot_commitment=retained.commitment,
    )
    next_state = _state_with(
        state,
        venue=next_venue,
        _effect_authority_by_id=effect_authority,
        _acquisition_currentness_by_scope=_replaced(
            state._acquisition_currentness_by_scope,
            slot_key,
            next_entry,
        ),
    )
    next_state = _record_input(next_state, item)
    post_venue_context = next_state.venue.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    post_authority_context = project_acquisition_authority_context(
        next_state,
        execution,
        post_venue_context,
    )
    if not (
        post_venue_context.matches_current(
            next_state.venue,
            execution,
            permit.application_generation_id,
            permit.position_scope,
        )
        and post_authority_context.matches_current(
            next_state,
            execution,
            post_venue_context,
        )
        and len(created_cancel_ids) <= 1
    ):
        raise RuntimeError("acquisition preemption failed postcondition")
    receipt = _new_acquisition_authority_receipt(
        operation=AcquisitionAuthorityOperation.PREEMPT,
        application_generation_id=permit.application_generation_id,
        position_scope=permit.position_scope,
        predecessor_controller_head=permit.predecessor_controller_head,
        controller_head=permit.controller_head,
        predecessor_scope_execution_commitment=(
            predecessor_venue_context.scope_execution_commitment
        ),
        scope_execution_commitment=post_venue_context.scope_execution_commitment,
        predecessor_venue_commitment=predecessor_venue_context.commitment,
        venue_commitment=post_venue_context.commitment,
        predecessor_authority_commitment=(
            predecessor_authority_context.authority_commitment
        ),
        authority_commitment=post_authority_context.authority_commitment,
        ordered_venue_transition_commitments=tuple(
            transition._protection_proof_commitment for transition in transitions
        ),
        permit_commitment=permit.commitment,
    )
    return _result(
        next_state,
        AuthorityDisposition.APPLIED,
        created=created_cancel_ids,
        venue_transitions=transitions,
        acquisition_receipt=receipt,
    )


def _create_acquisition_protection_exit(
    state: ExecutionAuthorityState,
    execution: ExecutionSnapshot,
    item: CreateAcquisitionProtectionExit,
) -> ExecutionAuthorityTransition:
    """Create one exact protective SELL after final BUY closure revalidation."""

    permit = item.permit
    if (
        not _acquisition_exit_permit_is_authentic(permit)
        or item.input_id != permit.input_id
        or permit.purpose is not _AcquisitionExitPurpose.CREATE_PROTECTION_EXIT_ONLY
        or permit.target_effect_id is None
        or permit.protective_request is None
        or state.session_id != permit.session_id
        or execution.position.scope != permit.position_scope
        or execution.commitment != permit.execution_snapshot_commitment
        or execution.position.raw_quantity != permit.residual_quantity.value
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    request = permit.protective_request
    if (
        request.kind is not EffectKind.SUBMIT
        or request.side is not ExecutionSide.SELL
        or request.symbol_id != permit.position_scope.symbol_id
        or request.mandate_id != permit.protection_mandate_id
        or request.quantity != permit.residual_quantity
        or request.target_leg_key is not None
        or len(request.economic_scope) != 32
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    slot_key = _acquisition_scope_key(
        permit.application_generation_id,
        permit.position_scope,
    )
    retained = state._acquisition_currentness_by_scope.get(slot_key)
    descriptor = state._acquisition_descriptor_by_scope.get(slot_key)
    active = state._acquisition_active_by_scope.get(slot_key)
    if not (
        _acquisition_currentness_entry_is_authentic(retained)
        and _acquisition_effect_descriptor_is_authentic(descriptor)
        and _acquisition_active_effect_is_authentic(active)
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    retained = cast(_AcquisitionCurrentnessEntry, retained)
    descriptor = cast(_AcquisitionEffectDescriptor, descriptor)
    active = cast(_AcquisitionActiveEffect, active)
    if (
        retained.application_generation_id != permit.application_generation_id
        or retained.position_scope != permit.position_scope
        or retained.session_id != permit.session_id
        or retained.generation_id != permit.generation_id
        or retained.acquisition_mandate_id != permit.acquisition_mandate_id
        or retained.protection_mandate_id != permit.protection_mandate_id
        or retained.binding_commitment != permit.binding_commitment
        or retained.emergency_recovery_compatibility_commitment
        != permit.emergency_recovery_compatibility_commitment
        or retained.controller_head != permit.predecessor_controller_head
        or retained.successor_ordinal != permit.successor_ordinal
        or retained.protection_commitment != permit.predecessor_protection_commitment
        or active.effect_id != permit.target_effect_id
        or active.descriptor_commitment != descriptor.commitment
        or descriptor.permit.generation_id != permit.generation_id
        or state._acquisition_descriptor_by_effect.get(
            _effect_key(permit.target_effect_id)
        )
        is not descriptor
        or state._claim_by_effect.get(_effect_key(permit.target_effect_id)) is None
        or state._manual_flatten_by_scope.get(slot_key) is not None
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    predecessor_venue_context = state.venue.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    predecessor_authority_context = project_acquisition_authority_context(
        state,
        execution,
        predecessor_venue_context,
    )
    view = _venue_authority_view(
        state.venue,
        execution,
        permit.position_scope,
        active.effect_id,
    )
    if not (
        predecessor_venue_context.matches_current(
            state.venue,
            execution,
            permit.application_generation_id,
            permit.position_scope,
        )
        and predecessor_authority_context.matches_current(
            state,
            execution,
            predecessor_venue_context,
        )
        and predecessor_venue_context.scope_execution_commitment
        == permit.scope_execution_commitment
        and predecessor_venue_context.commitment == permit.venue_commitment
        and predecessor_authority_context.authority_commitment
        == permit.authority_context_commitment
        and view.execution_binding_matches
        and view.account_reconciliation_clear
        and view.blocking_effect_count == 0
        and view.blocking_buy_effect_count == 0
        and view.stand_downable_buy_count == 0
        and view.known_cancellable_buy_leg_count == 0
        and view.known_cancel_pending_buy_leg_count == 0
        and view.waiting_buy_parent_count == 0
        and view.unknown_buy_effect_count == 0
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    envelope = CreateBrokerEffect(
        input_id=item.input_id,
        session_id=permit.session_id,
        request=request,
        manual_flatten_id=None,
        emergency_grant_id=None,
    )
    gate_reason = _create_gate_reason(state, execution, envelope)
    if gate_reason is not None:
        return _result(state, AuthorityDisposition.REFUSED, gate_reason)
    venue_reason = _venue_reason(
        state,
        execution,
        request.symbol_id,
        None,
        require_clear=True,
    )
    if venue_reason is not None:
        return _result(state, AuthorityDisposition.REFUSED, venue_reason)
    if _authority_effect_identity_conflicts(
        state.venue,
        request.effect_id,
        request.request_occurrence_id,
        request.client_order_id,
    ):
        return _result(state, AuthorityDisposition.CONFLICT)
    venue_transition = _authority_request_effect(
        state.venue,
        execution,
        _venue_request_from_request(item.input_id, request),
    )
    if venue_transition.disposition is VenueRecoveryDisposition.CONFLICT:
        return _result(state, AuthorityDisposition.CONFLICT)
    if venue_transition.disposition is not VenueRecoveryDisposition.APPLIED:
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    next_venue_context = venue_transition.book.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    next_entry = _new_acquisition_currentness_entry(
        source_kind=_AcquisitionCurrentnessSourceKind.AUTHORITY_MUTATION,
        application_generation_id=permit.application_generation_id,
        position_scope=permit.position_scope,
        session_id=permit.session_id,
        generation_id=permit.generation_id,
        acquisition_mandate_id=permit.acquisition_mandate_id,
        protection_mandate_id=permit.protection_mandate_id,
        binding_commitment=permit.binding_commitment,
        emergency_recovery_compatibility_commitment=(
            permit.emergency_recovery_compatibility_commitment
        ),
        controller_head=permit.controller_head,
        successor_ordinal=permit.successor_ordinal,
        scope_execution_commitment=next_venue_context.scope_execution_commitment,
        venue_commitment=next_venue_context.commitment,
        protection_commitment=permit.protection_commitment,
        predecessor_slot_commitment=retained.commitment,
    )
    authorization = _EffectAuthorization(
        request=request,
        session_id=permit.session_id,
        manual_flatten_id=None,
        emergency_grant_id=None,
    )
    next_state = _state_with(
        state,
        venue=venue_transition.book,
        _effect_authority_by_id=_inserted(
            state._effect_authority_by_id,
            _effect_key(request.effect_id),
            authorization,
        ),
        _acquisition_currentness_by_scope=_replaced(
            state._acquisition_currentness_by_scope,
            slot_key,
            next_entry,
        ),
    )
    next_state = _record_input(next_state, item)
    post_venue_context = next_state.venue.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    post_authority_context = project_acquisition_authority_context(
        next_state,
        execution,
        post_venue_context,
    )
    if not (
        post_venue_context.matches_current(
            next_state.venue,
            execution,
            permit.application_generation_id,
            permit.position_scope,
        )
        and post_authority_context.matches_current(
            next_state,
            execution,
            post_venue_context,
        )
    ):
        raise RuntimeError("acquisition protection exit failed postcondition")
    receipt = _new_acquisition_authority_receipt(
        operation=AcquisitionAuthorityOperation.PROTECTION_EXIT,
        application_generation_id=permit.application_generation_id,
        position_scope=permit.position_scope,
        predecessor_controller_head=permit.predecessor_controller_head,
        controller_head=permit.controller_head,
        predecessor_scope_execution_commitment=(
            predecessor_venue_context.scope_execution_commitment
        ),
        scope_execution_commitment=post_venue_context.scope_execution_commitment,
        predecessor_venue_commitment=predecessor_venue_context.commitment,
        venue_commitment=post_venue_context.commitment,
        predecessor_authority_commitment=(
            predecessor_authority_context.authority_commitment
        ),
        authority_commitment=post_authority_context.authority_commitment,
        ordered_venue_transition_commitments=(
            venue_transition._protection_proof_commitment,
        ),
        permit_commitment=permit.commitment,
    )
    return _result(
        next_state,
        AuthorityDisposition.APPLIED,
        created=(request.effect_id,),
        venue_transitions=(venue_transition,),
        acquisition_receipt=receipt,
    )


def _apply_acquisition_fact_preemption(
    state: ExecutionAuthorityState,
    item: _AcquisitionFactPreemption,
) -> ExecutionAuthorityTransition:
    """Adopt one retired fact and stand down its current BUY in one mutation."""

    state = _validate_authority_state(state)
    if not _acquisition_fact_preemption_is_authentic(item):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    replay = _replay_or_conflict(state, item)
    if replay is not None:
        return replay
    permit = item.permit
    transition = item._fact_transition
    projection = item._fact_projection
    execution = transition.execution
    relation = projection.fact_relation()
    if (
        not _acquisition_exit_permit_is_authentic(permit)
        or item.input_id != permit.input_id
        or permit.purpose is not _AcquisitionExitPurpose.PREEMPT_BUY_ONLY
        or permit.target_effect_id is None
        or relation is None
        or relation.effect_id == permit.target_effect_id
        or permit.execution_snapshot_commitment != execution.commitment
        or execution.position.scope != permit.position_scope
        or execution.position.raw_quantity != permit.residual_quantity.value
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    slot_key = _acquisition_scope_key(
        permit.application_generation_id,
        permit.position_scope,
    )
    retained = state._acquisition_currentness_by_scope.get(slot_key)
    descriptor = state._acquisition_descriptor_by_scope.get(slot_key)
    active = state._acquisition_active_by_scope.get(slot_key)
    if not (
        _acquisition_currentness_entry_is_authentic(retained)
        and _acquisition_effect_descriptor_is_authentic(descriptor)
        and _acquisition_active_effect_is_authentic(active)
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    retained = cast(_AcquisitionCurrentnessEntry, retained)
    descriptor = cast(_AcquisitionEffectDescriptor, descriptor)
    active = cast(_AcquisitionActiveEffect, active)
    if (
        retained.application_generation_id != permit.application_generation_id
        or retained.position_scope != permit.position_scope
        or retained.session_id != permit.session_id
        or retained.generation_id != permit.generation_id
        or retained.acquisition_mandate_id != permit.acquisition_mandate_id
        or retained.protection_mandate_id != permit.protection_mandate_id
        or retained.binding_commitment != permit.binding_commitment
        or retained.emergency_recovery_compatibility_commitment
        != permit.emergency_recovery_compatibility_commitment
        or retained.controller_head != permit.predecessor_controller_head
        or retained.successor_ordinal != permit.successor_ordinal
        or active.effect_id != permit.target_effect_id
        or active.descriptor_commitment != descriptor.commitment
        or descriptor.permit.generation_id != permit.generation_id
        or state._acquisition_descriptor_by_effect.get(
            _effect_key(permit.target_effect_id)
        )
        is not descriptor
        or state._manual_flatten_by_scope.get(slot_key) is not None
        or not _canonical_fact_predecessor_is_current(
            state,
            transition,
            projection,
            retained,
            permit.authority_context_commitment,
        )
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    if not (
        projection.predecessor_scope_execution_commitment
        == permit.scope_execution_commitment
        and projection.predecessor_venue_commitment == permit.venue_commitment
    ):
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    preempted = _authority_begin_symbol_flatten(
        transition.book,
        execution,
        permit.position_scope,
        permit.protection_mandate_id,
        f"acquisition-fact-preempt:{item.input_id.value}",
    )
    if preempted is None:
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    next_venue, created_cancel_ids, transitions = preempted
    if len(created_cancel_ids) > 1:
        raise RuntimeError("fact preemption exceeded the one-cancel cap")
    effect_authority = state._effect_authority_by_id
    for effect_id in created_cancel_ids:
        effect = next_venue._current_effect(effect_id)
        if effect is None or effect.scope.kind is not EffectKind.CANCEL:
            raise RuntimeError("fact preemption omitted its exact cancel effect")
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
            _EffectAuthorization(request, permit.session_id, None, None),
        )
    next_venue_context = next_venue.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    next_entry = _new_acquisition_currentness_entry(
        source_kind=_AcquisitionCurrentnessSourceKind.AUTHORITY_MUTATION,
        application_generation_id=permit.application_generation_id,
        position_scope=permit.position_scope,
        session_id=permit.session_id,
        generation_id=permit.generation_id,
        acquisition_mandate_id=permit.acquisition_mandate_id,
        protection_mandate_id=permit.protection_mandate_id,
        binding_commitment=permit.binding_commitment,
        emergency_recovery_compatibility_commitment=(
            permit.emergency_recovery_compatibility_commitment
        ),
        controller_head=permit.controller_head,
        successor_ordinal=permit.successor_ordinal,
        scope_execution_commitment=next_venue_context.scope_execution_commitment,
        venue_commitment=next_venue_context.commitment,
        protection_commitment=permit.protection_commitment,
        predecessor_slot_commitment=retained.commitment,
    )
    next_state = _state_with(
        state,
        venue=next_venue,
        _effect_authority_by_id=effect_authority,
        _acquisition_currentness_by_scope=_replaced(
            state._acquisition_currentness_by_scope,
            slot_key,
            next_entry,
        ),
    )
    next_state = _record_input(next_state, item)
    post_venue_context = next_state.venue.project_acquisition_context(
        execution,
        permit.position_scope,
    )
    post_authority_context = project_acquisition_authority_context(
        next_state,
        execution,
        post_venue_context,
    )
    if not (
        post_venue_context.matches_current(
            next_state.venue,
            execution,
            permit.application_generation_id,
            permit.position_scope,
        )
        and post_authority_context.matches_current(
            next_state,
            execution,
            post_venue_context,
        )
    ):
        raise RuntimeError("fact preemption failed its currentness postcondition")
    receipt = _new_acquisition_authority_receipt(
        operation=AcquisitionAuthorityOperation.PREEMPT,
        application_generation_id=permit.application_generation_id,
        position_scope=permit.position_scope,
        predecessor_controller_head=permit.predecessor_controller_head,
        controller_head=permit.controller_head,
        predecessor_scope_execution_commitment=(
            projection.predecessor_scope_execution_commitment
        ),
        scope_execution_commitment=post_venue_context.scope_execution_commitment,
        predecessor_venue_commitment=projection.predecessor_venue_commitment,
        venue_commitment=post_venue_context.commitment,
        predecessor_authority_commitment=permit.authority_context_commitment,
        authority_commitment=post_authority_context.authority_commitment,
        ordered_venue_transition_commitments=(
            transition._protection_proof_commitment,
            *(
                venue_transition._protection_proof_commitment
                for venue_transition in transitions
            ),
        ),
        permit_commitment=permit.commitment,
    )
    return _result(
        next_state,
        AuthorityDisposition.APPLIED,
        created=created_cancel_ids,
        venue_transitions=transitions,
        acquisition_receipt=receipt,
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
    if _acquisition_effect_descriptor_is_authentic(
        state._acquisition_descriptor_by_effect.get(_effect_key(item.effect_id))
    ):
        # R2 reserves final claim for the matching sealed acquisition route.
        # A generic claim must never consume the newly created BUY authority.
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
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
    position_scope = _position_scope(state, item.symbol_id)
    scope_key = _acquisition_scope_key(state.venue.scope.generation, position_scope)
    if state._manual_flatten_by_scope.get(scope_key) is not None:
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
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
        position_scope,
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
        _manual_flatten_by_scope=_inserted(
            state._manual_flatten_by_scope,
            scope_key,
            item.flatten_id,
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
    CreateAcquisitionEffect,
    ClaimAcquisitionEffect,
    BeginAcquisitionPreemption,
    CreateAcquisitionProtectionExit,
    ClaimEffect,
    _RegisterAcquisitionCurrentness,
    RegisterAcquisitionCurrentness,
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
    if type(command) is _RegisterAcquisitionCurrentness:
        # The R8 registration command is an implementation detail of
        # initialize_acquisition_controller.  It cannot be replayed, compared,
        # or dispatched through the public authority-input surface.
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    replay = _replay_or_conflict(state, command)
    if replay is not None:
        return replay
    if type(command) is RegisterAcquisitionCurrentness:
        if _register_canonical_fact_currentness_command_is_authentic(command):
            return _register_canonical_fact_currentness(state, execution, command)
        if _register_protection_rebase_currentness_command_is_authentic(command):
            return _register_protection_rebase_currentness(state, execution, command)
        return _result(
            state,
            AuthorityDisposition.REFUSED,
            AuthorityReason.VENUE_UNCERTAIN,
        )
    if type(item) is CreateBrokerEffect:
        return _create_effect(state, execution, item)
    if type(item) is CreateAcquisitionEffect:
        return _create_acquisition_effect(state, execution, item)
    if type(item) is ClaimAcquisitionEffect:
        return _claim_acquisition_effect(state, execution, item)
    if type(item) is BeginAcquisitionPreemption:
        return _begin_acquisition_preemption(state, execution, item)
    if type(item) is CreateAcquisitionProtectionExit:
        return _create_acquisition_protection_exit(state, execution, item)
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
    "AcquisitionAdmissionKind",
    "AcquisitionAdmissionProjection",
    "AcquisitionAuthorityOperation",
    "AcquisitionAuthorityContext",
    "AcquisitionAuthorityReceipt",
    "AcquisitionClaimPermit",
    "AcquisitionClaimReceipt",
    "AcquisitionContextRefresh",
    "AcquisitionContextRefreshDisposition",
    "AcquisitionEffectTerms",
    "AcquisitionEffectPermit",
    "AcquisitionEffectView",
    "AcquisitionExitPermit",
    "AcquisitionOrderType",
    "AuthorityDisposition",
    "AuthorityInputId",
    "AuthorityQueryKind",
    "AuthorityReason",
    "BeginManualFlatten",
    "BeginAcquisitionPreemption",
    "BrokerEffectRequest",
    "ClaimBrokerQuery",
    "ClaimAcquisitionEffect",
    "ClaimEffect",
    "CreateBrokerEffect",
    "CreateAcquisitionEffect",
    "CreateAcquisitionProtectionExit",
    "EmergencyGrantId",
    "EngageKill",
    "EnginePhase",
    "ExecutionAuthorityState",
    "ExecutionAuthorityTransition",
    "ManualFlattenId",
    "QueryClaimId",
    "RequestBudget",
    "RegisterAcquisitionCurrentness",
    "SessionId",
    "SupervisorFence",
    "TradingMode",
    "apply_execution_authority_input",
    "initial_execution_authority_state",
    "project_acquisition_admission",
    "project_acquisition_authority_context",
    "project_acquisition_effect",
    "refresh_acquisition_context",
]
