"""Pure broker-neutral position-protection semantic center."""

from __future__ import annotations as _annotations

from dataclasses import dataclass as _dataclass
from enum import Enum as _Enum
from fractions import Fraction as _Fraction

from .fills import (
    ExecutionSide as _ExecutionSide,
    PositionScope as _PositionScope,
    _commit_parts,
    _encode_fraction,
    _encode_int,
    _encode_position_scope,
    _encode_reported_price,
    _encode_text,
)
from .identity import (
    MandateId as _MandateId,
    MarketDataSourceId as _MarketDataSourceId,
    MarketOccurrenceId as _MarketOccurrenceId,
    SessionId as _SessionId,
)
from .position import (
    BasisAuthority as _BasisAuthority,
    ExecutionSnapshot as _ExecutionSnapshot,
    PositionIntegrity as _PositionIntegrity,
)
from .values import (
    PriceScale as _PriceScale,
    PriceUnits as _PriceUnits,
    Quantity as _Quantity,
    ReportedPrice as _ReportedPrice,
    TickMetadata as _TickMetadata,
)
from .venue import (
    VenueExecutionBinding as _VenueExecutionBinding,
    VenueRecoveryTransition as _VenueRecoveryTransition,
    _ProtectionCursor,
    _ProtectionTransitionProof,
    _SymbolAuthoritySummary,
    _extract_protection_transition,
)


class MarketKind(_Enum):
    BEST_BID = "BEST_BID"
    TRADE = "TRADE"


class ProtectionPolicy(_Enum):
    FLOOR_ONLY = "FLOOR_ONLY"
    TRAIL_ACTIVE = "TRAIL_ACTIVE"
    EXIT_NORMAL = "EXIT_NORMAL"
    HARD_BAIL = "HARD_BAIL"
    FLAT = "FLAT"


class ProtectionUrgency(_Enum):
    NORMAL = "NORMAL"
    EMERGENCY = "EMERGENCY"


class ProtectionDisposition(_Enum):
    APPLIED = "APPLIED"
    EXACT_REPLAY = "EXACT_REPLAY"
    STALE = "STALE"
    REFUSED = "REFUSED"


class ProtectionAlert(_Enum):
    LATE_POSITIVE_AFTER_FLAT = "LATE_POSITIVE_AFTER_FLAT"


@_dataclass(frozen=True, slots=True)
class EvidencePolicy:
    source_id: _MarketDataSourceId
    max_age: int
    corroboration_window: int
    max_step_fraction: _Fraction

    def __post_init__(self) -> None:
        if type(self.source_id) is not _MarketDataSourceId:
            raise TypeError("source_id must be MarketDataSourceId")
        if type(self.max_age) is not int:
            raise TypeError("max_age must be an exact integer")
        if self.max_age <= 0:
            raise ValueError("max_age must be positive")
        if type(self.corroboration_window) is not int:
            raise TypeError("corroboration_window must be an exact integer")
        if self.corroboration_window <= 0:
            raise ValueError("corroboration_window must be positive")
        if type(self.max_step_fraction) is not _Fraction:
            raise TypeError("max_step_fraction must be Fraction")
        if self.max_step_fraction <= 0 or self.max_step_fraction > 1:
            raise ValueError("max_step_fraction must be in (0, 1]")


@_dataclass(frozen=True, slots=True)
class ExecutionGuard:
    guard_id: str
    policy_commitment: bytes

    def __post_init__(self) -> None:
        if type(self.guard_id) is not str:
            raise TypeError("guard_id must be a string")
        if not self.guard_id.strip():
            raise ValueError("guard_id must be nonblank")
        if type(self.policy_commitment) is not bytes:
            raise TypeError("policy_commitment must be bytes")
        if len(self.policy_commitment) != 32:
            raise ValueError("policy_commitment must contain exactly 32 bytes")


@_dataclass(frozen=True, slots=True)
class ProtectionMandate:
    mandate_id: _MandateId
    position_scope: _PositionScope
    session_id: _SessionId
    configuration_version: str
    loss_fraction: _Fraction
    approved_gain: _Fraction
    percent_trail_fraction: _Fraction
    atr_multiple: _Fraction
    tick: _TickMetadata
    normal_guard: ExecutionGuard
    emergency_guard: ExecutionGuard
    evidence_policy: EvidencePolicy
    maximum_quantity: _Quantity
    maximum_goal_rate: int
    deadline: int

    def __post_init__(self) -> None:
        if type(self.mandate_id) is not _MandateId:
            raise TypeError("mandate_id must be MandateId")
        if type(self.position_scope) is not _PositionScope:
            raise TypeError("position_scope must be PositionScope")
        if type(self.session_id) is not _SessionId:
            raise TypeError("session_id must be SessionId")
        if type(self.configuration_version) is not str:
            raise TypeError("configuration_version must be a string")
        if not self.configuration_version.strip():
            raise ValueError("configuration_version must be nonblank")
        if type(self.loss_fraction) is not _Fraction:
            raise TypeError("loss_fraction must be Fraction")
        if self.loss_fraction <= 0 or self.loss_fraction >= 1:
            raise ValueError("loss_fraction must be in (0, 1)")
        if type(self.approved_gain) is not _Fraction:
            raise TypeError("approved_gain must be Fraction")
        if self.approved_gain <= 0:
            raise ValueError("approved_gain must be positive")
        if type(self.percent_trail_fraction) is not _Fraction:
            raise TypeError("percent_trail_fraction must be Fraction")
        if self.percent_trail_fraction <= 0 or self.percent_trail_fraction >= 1:
            raise ValueError("percent_trail_fraction must be in (0, 1)")
        if type(self.atr_multiple) is not _Fraction:
            raise TypeError("atr_multiple must be Fraction")
        if self.atr_multiple <= 0:
            raise ValueError("atr_multiple must be positive")
        if type(self.tick) is not _TickMetadata:
            raise TypeError("tick must be TickMetadata")
        if type(self.tick.tick_units) is not _PriceUnits:
            raise TypeError("tick units must be PriceUnits")
        if type(self.tick.tick_units.value) is not int:
            raise TypeError("tick units value must be an exact integer")
        if self.tick.tick_units.value <= 0:
            raise ValueError("tick units must be positive")
        if type(self.tick.scale) is not _PriceScale:
            raise TypeError("tick scale must be PriceScale")
        if type(self.normal_guard) is not ExecutionGuard:
            raise TypeError("normal_guard must be ExecutionGuard")
        if type(self.emergency_guard) is not ExecutionGuard:
            raise TypeError("emergency_guard must be ExecutionGuard")
        if type(self.evidence_policy) is not EvidencePolicy:
            raise TypeError("evidence_policy must be EvidencePolicy")
        if type(self.maximum_quantity) is not _Quantity:
            raise TypeError("maximum_quantity must be Quantity")
        if type(self.maximum_quantity.value) is not int:
            raise TypeError("maximum_quantity value must be an exact integer")
        if self.maximum_quantity.value <= 0:
            raise ValueError("maximum_quantity must be positive")
        if type(self.maximum_goal_rate) is not int:
            raise TypeError("maximum_goal_rate must be an exact integer")
        if self.maximum_goal_rate <= 0:
            raise ValueError("maximum_goal_rate must be positive")
        if type(self.deadline) is not int:
            raise TypeError("deadline must be an exact integer")
        if self.deadline < 0:
            raise ValueError("deadline must be non-negative")

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("ProtectionMandate cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class MarketOccurrence:
    occurrence_id: _MarketOccurrenceId
    source_id: _MarketDataSourceId
    position_scope: _PositionScope
    session_id: _SessionId
    market_epoch: int
    source_sequence: int | None
    source_time: int
    evaluation_time: int
    kind: MarketKind
    best_bid: _ReportedPrice | None
    best_ask: _ReportedPrice | None
    trade_price: _ReportedPrice | None
    atr_distance: _ReportedPrice | None
    structure_trail: _ReportedPrice | None
    halted: bool

    def __post_init__(self) -> None:
        if type(self.occurrence_id) is not _MarketOccurrenceId:
            raise TypeError("occurrence_id must be MarketOccurrenceId")
        if type(self.source_id) is not _MarketDataSourceId:
            raise TypeError("source_id must be MarketDataSourceId")
        if type(self.position_scope) is not _PositionScope:
            raise TypeError("position_scope must be PositionScope")
        if type(self.session_id) is not _SessionId:
            raise TypeError("session_id must be SessionId")
        if type(self.market_epoch) is not int:
            raise TypeError("market_epoch must be an exact integer")
        if self.market_epoch < 0:
            raise ValueError("market_epoch must be non-negative")
        if self.source_sequence is not None:
            if type(self.source_sequence) is not int:
                raise TypeError("source_sequence must be an exact integer or None")
            if self.source_sequence < 0:
                raise ValueError("source_sequence must be non-negative")
        if type(self.source_time) is not int:
            raise TypeError("source_time must be an exact integer")
        if self.source_time < 0:
            raise ValueError("source_time must be non-negative")
        if type(self.evaluation_time) is not int:
            raise TypeError("evaluation_time must be an exact integer")
        if self.evaluation_time < 0:
            raise ValueError("evaluation_time must be non-negative")
        if type(self.kind) is not MarketKind:
            raise TypeError("kind must be MarketKind")
        if self.best_bid is not None and type(self.best_bid) is not _ReportedPrice:
            raise TypeError("best_bid must be ReportedPrice or None")
        if self.best_ask is not None and type(self.best_ask) is not _ReportedPrice:
            raise TypeError("best_ask must be ReportedPrice or None")
        if (
            self.trade_price is not None
            and type(self.trade_price) is not _ReportedPrice
        ):
            raise TypeError("trade_price must be ReportedPrice or None")
        if (
            self.atr_distance is not None
            and type(self.atr_distance) is not _ReportedPrice
        ):
            raise TypeError("atr_distance must be ReportedPrice or None")
        if (
            self.structure_trail is not None
            and type(self.structure_trail) is not _ReportedPrice
        ):
            raise TypeError("structure_trail must be ReportedPrice or None")
        if type(self.halted) is not bool:
            raise TypeError("halted must be bool")
        if self.kind is MarketKind.BEST_BID:
            if self.best_bid is None or self.best_ask is None:
                raise ValueError("BEST_BID requires bid and ask")
            if self.trade_price is not None:
                raise ValueError("BEST_BID cannot retain a trade price")
        else:
            if self.trade_price is None:
                raise ValueError("TRADE requires a trade price")
            if self.best_bid is not None or self.best_ask is not None:
                raise ValueError("TRADE cannot retain bid or ask")
            if self.atr_distance is not None or self.structure_trail is not None:
                raise ValueError("TRADE cannot retain trailing components")

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("MarketOccurrence cannot be subclassed")


@_dataclass(frozen=True, slots=True, init=False)
class PositionProtectionState:
    policy: ProtectionPolicy
    mandate: ProtectionMandate
    raw_quantity: int
    execution_commitment: bytes
    formula_available: bool
    armed_hard_bail_trigger: _ReportedPrice | None
    activation_price: _ReportedPrice | None
    high_watermark: _ReportedPrice | None
    trail: _ReportedPrice | None
    waiting_buy_resolution: bool
    commitment: bytes
    _cursor_ordinal: int
    _cursor_head: bytes
    _stream_epoch: int
    _stream_sequence: int
    _stream_source_time: int
    _stream_evaluation_time: int
    _stream_halted: bool
    _last_occurrence_id: bytes
    _last_occurrence_payload: bytes
    _last_primary_present: bool
    _last_primary_units: int
    _hard_bid_count: int
    _hard_bid_sequence: int
    _hard_bid_source_time: int
    _hard_bid_identity: bytes
    _trade_present: bool
    _trade_source_time: int
    _trade_identity: bytes
    _trade_units: int
    _trail_bid_count: int
    _trail_bid_sequence: int
    _trail_bid_source_time: int
    _trail_bid_identity: bytes
    _exit_provenance: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("PositionProtectionState is opaque")

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("PositionProtectionState cannot be subclassed")


@_dataclass(frozen=True, slots=True, init=False)
class ProtectionVenueProjection:
    predecessor_cursor_ordinal: int
    predecessor_cursor_head: bytes
    cursor_ordinal: int
    cursor_head: bytes
    predecessor_execution_commitment: bytes
    execution_commitment: bytes
    predecessor_blocking_effect_count: int
    predecessor_blocking_buy_effect_count: int
    blocking_effect_count: int
    blocking_buy_effect_count: int
    predecessor_execution_binding_matches: bool
    execution_binding_matches: bool
    predecessor_account_reconciliation_clear: bool
    account_reconciliation_clear: bool
    _position_scope: _PositionScope
    _mandate_commitment: bytes
    _raw_quantity: int
    _basis_available: bool
    _cost_basis: _Fraction
    _basis_metadata_available: bool
    _basis_price: _ReportedPrice
    _integrity: _PositionIntegrity
    _seal: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ProtectionVenueProjection is opaque")

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("ProtectionVenueProjection cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class ExecutionGoal:
    side: _ExecutionSide
    residual: _Quantity
    urgency: ProtectionUrgency
    guard: ExecutionGuard
    deadline: int
    session_id: _SessionId
    mandate_id: _MandateId
    maximum_goal_rate: int
    execution_commitment: bytes
    protection_commitment: bytes

    def __post_init__(self) -> None:
        if type(self.side) is not _ExecutionSide:
            raise TypeError("side must be ExecutionSide")
        if self.side is not _ExecutionSide.SELL:
            raise ValueError("protection goals must be SELL")
        if type(self.residual) is not _Quantity:
            raise TypeError("residual must be Quantity")
        if type(self.residual.value) is not int:
            raise TypeError("residual value must be an exact integer")
        if self.residual.value <= 0:
            raise ValueError("residual must be positive")
        if type(self.urgency) is not ProtectionUrgency:
            raise TypeError("urgency must be ProtectionUrgency")
        if type(self.guard) is not ExecutionGuard:
            raise TypeError("guard must be ExecutionGuard")
        if type(self.deadline) is not int:
            raise TypeError("deadline must be an exact integer")
        if self.deadline < 0:
            raise ValueError("deadline must be non-negative")
        if type(self.session_id) is not _SessionId:
            raise TypeError("session_id must be SessionId")
        if type(self.mandate_id) is not _MandateId:
            raise TypeError("mandate_id must be MandateId")
        if type(self.maximum_goal_rate) is not int:
            raise TypeError("maximum_goal_rate must be an exact integer")
        if self.maximum_goal_rate <= 0:
            raise ValueError("maximum_goal_rate must be positive")
        if type(self.execution_commitment) is not bytes:
            raise TypeError("execution_commitment must be bytes")
        if len(self.execution_commitment) != 32:
            raise ValueError("execution_commitment must contain exactly 32 bytes")
        if type(self.protection_commitment) is not bytes:
            raise TypeError("protection_commitment must be bytes")
        if len(self.protection_commitment) != 32:
            raise ValueError("protection_commitment must contain exactly 32 bytes")


@_dataclass(frozen=True, slots=True)
class ProtectionTransition:
    state: PositionProtectionState
    disposition: ProtectionDisposition
    goal: ExecutionGoal | None
    critical_alert: ProtectionAlert | None

    def __post_init__(self) -> None:
        if type(self.state) is not PositionProtectionState:
            raise TypeError("state must be PositionProtectionState")
        if type(self.disposition) is not ProtectionDisposition:
            raise TypeError("disposition must be ProtectionDisposition")
        if self.goal is not None and type(self.goal) is not ExecutionGoal:
            raise TypeError("goal must be ExecutionGoal or None")
        if (
            self.critical_alert is not None
            and type(self.critical_alert) is not ProtectionAlert
        ):
            raise TypeError("critical_alert must be ProtectionAlert or None")


def _new_position_protection_state(
    policy: ProtectionPolicy,
    mandate: ProtectionMandate,
    raw_quantity: int,
    execution_commitment: bytes,
    formula_available: bool,
    armed_hard_bail_trigger: _ReportedPrice | None,
    activation_price: _ReportedPrice | None,
    high_watermark: _ReportedPrice | None,
    trail: _ReportedPrice | None,
    waiting_buy_resolution: bool,
    commitment: bytes,
    _cursor_ordinal: int,
    _cursor_head: bytes,
    _stream_epoch: int,
    _stream_sequence: int,
    _stream_source_time: int,
    _stream_evaluation_time: int,
    _stream_halted: bool,
    _last_occurrence_id: bytes,
    _last_occurrence_payload: bytes,
    _last_primary_present: bool,
    _last_primary_units: int,
    _hard_bid_count: int,
    _hard_bid_sequence: int,
    _hard_bid_source_time: int,
    _hard_bid_identity: bytes,
    _trade_present: bool,
    _trade_source_time: int,
    _trade_identity: bytes,
    _trade_units: int,
    _trail_bid_count: int,
    _trail_bid_sequence: int,
    _trail_bid_source_time: int,
    _trail_bid_identity: bytes,
    _exit_provenance: bytes,
) -> PositionProtectionState:
    result = object.__new__(PositionProtectionState)
    object.__setattr__(result, "policy", policy)
    object.__setattr__(result, "mandate", mandate)
    object.__setattr__(result, "raw_quantity", raw_quantity)
    object.__setattr__(result, "execution_commitment", execution_commitment)
    object.__setattr__(result, "formula_available", formula_available)
    object.__setattr__(result, "armed_hard_bail_trigger", armed_hard_bail_trigger)
    object.__setattr__(result, "activation_price", activation_price)
    object.__setattr__(result, "high_watermark", high_watermark)
    object.__setattr__(result, "trail", trail)
    object.__setattr__(result, "waiting_buy_resolution", waiting_buy_resolution)
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(result, "_cursor_ordinal", _cursor_ordinal)
    object.__setattr__(result, "_cursor_head", _cursor_head)
    object.__setattr__(result, "_stream_epoch", _stream_epoch)
    object.__setattr__(result, "_stream_sequence", _stream_sequence)
    object.__setattr__(result, "_stream_source_time", _stream_source_time)
    object.__setattr__(result, "_stream_evaluation_time", _stream_evaluation_time)
    object.__setattr__(result, "_stream_halted", _stream_halted)
    object.__setattr__(result, "_last_occurrence_id", _last_occurrence_id)
    object.__setattr__(result, "_last_occurrence_payload", _last_occurrence_payload)
    object.__setattr__(result, "_last_primary_present", _last_primary_present)
    object.__setattr__(result, "_last_primary_units", _last_primary_units)
    object.__setattr__(result, "_hard_bid_count", _hard_bid_count)
    object.__setattr__(result, "_hard_bid_sequence", _hard_bid_sequence)
    object.__setattr__(result, "_hard_bid_source_time", _hard_bid_source_time)
    object.__setattr__(result, "_hard_bid_identity", _hard_bid_identity)
    object.__setattr__(result, "_trade_present", _trade_present)
    object.__setattr__(result, "_trade_source_time", _trade_source_time)
    object.__setattr__(result, "_trade_identity", _trade_identity)
    object.__setattr__(result, "_trade_units", _trade_units)
    object.__setattr__(result, "_trail_bid_count", _trail_bid_count)
    object.__setattr__(result, "_trail_bid_sequence", _trail_bid_sequence)
    object.__setattr__(result, "_trail_bid_source_time", _trail_bid_source_time)
    object.__setattr__(result, "_trail_bid_identity", _trail_bid_identity)
    object.__setattr__(result, "_exit_provenance", _exit_provenance)
    return result


def _new_protection_venue_projection(
    predecessor_cursor_ordinal: int,
    predecessor_cursor_head: bytes,
    cursor_ordinal: int,
    cursor_head: bytes,
    predecessor_execution_commitment: bytes,
    execution_commitment: bytes,
    predecessor_blocking_effect_count: int,
    predecessor_blocking_buy_effect_count: int,
    blocking_effect_count: int,
    blocking_buy_effect_count: int,
    predecessor_execution_binding_matches: bool,
    execution_binding_matches: bool,
    predecessor_account_reconciliation_clear: bool,
    account_reconciliation_clear: bool,
    _position_scope: _PositionScope,
    _mandate_commitment: bytes,
    _raw_quantity: int,
    _basis_available: bool,
    _cost_basis: _Fraction,
    _basis_metadata_available: bool,
    _basis_price: _ReportedPrice,
    _integrity: _PositionIntegrity,
    _seal: bytes,
) -> ProtectionVenueProjection:
    result = object.__new__(ProtectionVenueProjection)
    object.__setattr__(result, "predecessor_cursor_ordinal", predecessor_cursor_ordinal)
    object.__setattr__(result, "predecessor_cursor_head", predecessor_cursor_head)
    object.__setattr__(result, "cursor_ordinal", cursor_ordinal)
    object.__setattr__(result, "cursor_head", cursor_head)
    object.__setattr__(
        result,
        "predecessor_execution_commitment",
        predecessor_execution_commitment,
    )
    object.__setattr__(result, "execution_commitment", execution_commitment)
    object.__setattr__(
        result,
        "predecessor_blocking_effect_count",
        predecessor_blocking_effect_count,
    )
    object.__setattr__(
        result,
        "predecessor_blocking_buy_effect_count",
        predecessor_blocking_buy_effect_count,
    )
    object.__setattr__(result, "blocking_effect_count", blocking_effect_count)
    object.__setattr__(result, "blocking_buy_effect_count", blocking_buy_effect_count)
    object.__setattr__(
        result,
        "predecessor_execution_binding_matches",
        predecessor_execution_binding_matches,
    )
    object.__setattr__(result, "execution_binding_matches", execution_binding_matches)
    object.__setattr__(
        result,
        "predecessor_account_reconciliation_clear",
        predecessor_account_reconciliation_clear,
    )
    object.__setattr__(
        result,
        "account_reconciliation_clear",
        account_reconciliation_clear,
    )
    object.__setattr__(result, "_position_scope", _position_scope)
    object.__setattr__(result, "_mandate_commitment", _mandate_commitment)
    object.__setattr__(result, "_raw_quantity", _raw_quantity)
    object.__setattr__(result, "_basis_available", _basis_available)
    object.__setattr__(result, "_cost_basis", _cost_basis)
    object.__setattr__(result, "_basis_metadata_available", _basis_metadata_available)
    object.__setattr__(result, "_basis_price", _basis_price)
    object.__setattr__(result, "_integrity", _integrity)
    object.__setattr__(result, "_seal", _seal)
    return result


def _commit_mandate(mandate: ProtectionMandate) -> bytes:
    return _commit_parts(
        b"execution-core/protection-mandate/v1",
        _encode_text(mandate.mandate_id.value),
        _encode_position_scope(mandate.position_scope),
        _encode_text(mandate.session_id.value),
        _encode_text(mandate.configuration_version),
        _encode_fraction(mandate.loss_fraction),
        _encode_fraction(mandate.approved_gain),
        _encode_fraction(mandate.percent_trail_fraction),
        _encode_fraction(mandate.atr_multiple),
        _encode_int(mandate.tick.tick_units.value),
        _encode_fraction(_Fraction(mandate.tick.scale.value)),
        _encode_text(mandate.normal_guard.guard_id),
        mandate.normal_guard.policy_commitment,
        _encode_text(mandate.emergency_guard.guard_id),
        mandate.emergency_guard.policy_commitment,
        _encode_text(mandate.evidence_policy.source_id.value),
        _encode_int(mandate.evidence_policy.max_age),
        _encode_int(mandate.evidence_policy.corroboration_window),
        _encode_fraction(mandate.evidence_policy.max_step_fraction),
        _encode_int(mandate.maximum_quantity.value),
        _encode_int(mandate.maximum_goal_rate),
        _encode_int(mandate.deadline),
    )


def _projection_commitment(
    predecessor_cursor_ordinal: int,
    predecessor_cursor_head: bytes,
    cursor_ordinal: int,
    cursor_head: bytes,
    predecessor_execution_commitment: bytes,
    execution_commitment: bytes,
    predecessor_blocking_effect_count: int,
    predecessor_blocking_buy_effect_count: int,
    blocking_effect_count: int,
    blocking_buy_effect_count: int,
    predecessor_execution_binding_matches: bool,
    execution_binding_matches: bool,
    predecessor_account_reconciliation_clear: bool,
    account_reconciliation_clear: bool,
    position_scope: _PositionScope,
    mandate_commitment: bytes,
    raw_quantity: int,
    basis_available: bool,
    cost_basis: _Fraction,
    basis_metadata_available: bool,
    basis_price: _ReportedPrice,
    integrity: _PositionIntegrity,
) -> bytes:
    return _commit_parts(
        b"execution-core/protection-venue-projection/v1",
        _encode_int(predecessor_cursor_ordinal),
        predecessor_cursor_head,
        _encode_int(cursor_ordinal),
        cursor_head,
        predecessor_execution_commitment,
        execution_commitment,
        _encode_int(predecessor_blocking_effect_count),
        _encode_int(predecessor_blocking_buy_effect_count),
        _encode_int(blocking_effect_count),
        _encode_int(blocking_buy_effect_count),
        _encode_int(1 if predecessor_execution_binding_matches else 0),
        _encode_int(1 if execution_binding_matches else 0),
        _encode_int(1 if predecessor_account_reconciliation_clear else 0),
        _encode_int(1 if account_reconciliation_clear else 0),
        _encode_position_scope(position_scope),
        mandate_commitment,
        _encode_int(raw_quantity),
        _encode_int(1 if basis_available else 0),
        _encode_fraction(cost_basis),
        _encode_int(1 if basis_metadata_available else 0),
        _encode_reported_price(basis_price),
        _encode_int(integrity.value),
    )


def _projection_is_authentic(projection: ProtectionVenueProjection) -> bool:
    if type(projection._seal) is not bytes:
        return False
    return projection._seal == _projection_commitment(
        projection.predecessor_cursor_ordinal,
        projection.predecessor_cursor_head,
        projection.cursor_ordinal,
        projection.cursor_head,
        projection.predecessor_execution_commitment,
        projection.execution_commitment,
        projection.predecessor_blocking_effect_count,
        projection.predecessor_blocking_buy_effect_count,
        projection.blocking_effect_count,
        projection.blocking_buy_effect_count,
        projection.predecessor_execution_binding_matches,
        projection.execution_binding_matches,
        projection.predecessor_account_reconciliation_clear,
        projection.account_reconciliation_clear,
        projection._position_scope,
        projection._mandate_commitment,
        projection._raw_quantity,
        projection._basis_available,
        projection._cost_basis,
        projection._basis_metadata_available,
        projection._basis_price,
        projection._integrity,
    )


def _execution_matches_checkpoint(
    execution: _ExecutionSnapshot,
    proof: _ProtectionTransitionProof,
) -> bool:
    checkpoint = proof.execution_checkpoint
    return (
        type(execution) is _ExecutionSnapshot
        and checkpoint.position_scope == execution.position.scope
        and checkpoint.registry_count == execution.seen_facts.count
        and checkpoint.registry_commitment == execution.seen_facts.commitment
        and checkpoint.position_commitment == execution.position.commitment
        and checkpoint.root_heads_commitment == execution.root_heads.commitment
        and checkpoint.integrity_bits == execution.integrity.value
        and checkpoint.account_reconciliation_required
        == execution.account_reconciliation_required
        and checkpoint.reconciliation_transition_count
        == execution.reconciliation_transition_count
        and checkpoint.reconciliation_transition_head
        == execution.reconciliation_transition_head
    )


def _state_commitment(
    policy: ProtectionPolicy,
    mandate: ProtectionMandate,
    raw_quantity: int,
    execution_commitment: bytes,
    formula_available: bool,
    armed_hard_bail_trigger: _ReportedPrice | None,
    activation_price: _ReportedPrice | None,
    high_watermark: _ReportedPrice | None,
    trail: _ReportedPrice | None,
    waiting_buy_resolution: bool,
    cursor_ordinal: int,
    cursor_head: bytes,
    stream_epoch: int,
    stream_sequence: int,
    stream_source_time: int,
    stream_evaluation_time: int,
    stream_halted: bool,
    last_occurrence_id: bytes,
    last_occurrence_payload: bytes,
    last_primary_present: bool,
    last_primary_units: int,
    hard_bid_count: int,
    hard_bid_sequence: int,
    hard_bid_source_time: int,
    hard_bid_identity: bytes,
    trade_present: bool,
    trade_source_time: int,
    trade_identity: bytes,
    trade_units: int,
    trail_bid_count: int,
    trail_bid_sequence: int,
    trail_bid_source_time: int,
    trail_bid_identity: bytes,
    exit_provenance: bytes,
) -> bytes:
    return _commit_parts(
        b"execution-core/position-protection-state/v2",
        _encode_text(policy.value),
        _commit_mandate(mandate),
        _encode_int(raw_quantity),
        execution_commitment,
        _encode_int(1 if formula_available else 0),
        _encode_reported_price(armed_hard_bail_trigger),
        _encode_reported_price(activation_price),
        _encode_reported_price(high_watermark),
        _encode_reported_price(trail),
        _encode_int(1 if waiting_buy_resolution else 0),
        _encode_int(cursor_ordinal),
        cursor_head,
        _encode_int(stream_epoch),
        _encode_int(stream_sequence),
        _encode_int(stream_source_time),
        _encode_int(stream_evaluation_time),
        _encode_int(1 if stream_halted else 0),
        last_occurrence_id,
        last_occurrence_payload,
        _encode_int(1 if last_primary_present else 0),
        _encode_int(last_primary_units),
        _encode_int(hard_bid_count),
        _encode_int(hard_bid_sequence),
        _encode_int(hard_bid_source_time),
        hard_bid_identity,
        _encode_int(1 if trade_present else 0),
        _encode_int(trade_source_time),
        trade_identity,
        _encode_int(trade_units),
        _encode_int(trail_bid_count),
        _encode_int(trail_bid_sequence),
        _encode_int(trail_bid_source_time),
        trail_bid_identity,
        exit_provenance,
    )


def _state_is_authentic(state: PositionProtectionState) -> bool:
    if type(state.commitment) is not bytes:
        return False
    return state.commitment == _state_commitment(
        state.policy,
        state.mandate,
        state.raw_quantity,
        state.execution_commitment,
        state.formula_available,
        state.armed_hard_bail_trigger,
        state.activation_price,
        state.high_watermark,
        state.trail,
        state.waiting_buy_resolution,
        state._cursor_ordinal,
        state._cursor_head,
        state._stream_epoch,
        state._stream_sequence,
        state._stream_source_time,
        state._stream_evaluation_time,
        state._stream_halted,
        state._last_occurrence_id,
        state._last_occurrence_payload,
        state._last_primary_present,
        state._last_primary_units,
        state._hard_bid_count,
        state._hard_bid_sequence,
        state._hard_bid_source_time,
        state._hard_bid_identity,
        state._trade_present,
        state._trade_source_time,
        state._trade_identity,
        state._trade_units,
        state._trail_bid_count,
        state._trail_bid_sequence,
        state._trail_bid_source_time,
        state._trail_bid_identity,
        state._exit_provenance,
    )


def _upward_price(value: _Fraction, tick: _TickMetadata) -> _ReportedPrice:
    raw_units = value / _Fraction(tick.scale.value)
    integral_units = (
        raw_units.numerator + raw_units.denominator - 1
    ) // raw_units.denominator
    aligned_units = (
        (integral_units + tick.tick_units.value - 1) // tick.tick_units.value
    ) * tick.tick_units.value
    return _ReportedPrice(
        _PriceUnits(aligned_units),
        tick.scale,
        tick,
    )


def _basis_metadata_matches(
    price: _ReportedPrice,
    tick: _TickMetadata,
) -> bool:
    return (
        type(price.units) is _PriceUnits
        and type(price.scale) is _PriceScale
        and type(price.tick) is _TickMetadata
        and type(price.tick.tick_units) is _PriceUnits
        and type(price.tick.scale) is _PriceScale
        and price.scale == tick.scale
        and price.tick.scale == tick.scale
        and tick.tick_units.value % price.tick.tick_units.value == 0
        and price.units.value % price.tick.tick_units.value == 0
    )


def _market_genesis() -> bytes:
    return _commit_parts(b"execution-core/protection-market-genesis/v1")


def _exit_genesis() -> bytes:
    return _commit_parts(b"execution-core/protection-exit-genesis/v1")


def _flat_origin() -> bytes:
    return _commit_parts(b"execution-core/protection-flat-origin/v1")


def _formula_loss_origin() -> bytes:
    return _commit_parts(b"execution-core/protection-formula-loss-origin/v1")


def _late_positive_origin() -> bytes:
    return _commit_parts(b"execution-core/protection-late-positive-origin/v1")


def _real_exit(provenance: bytes) -> bool:
    return (
        provenance != _exit_genesis()
        and provenance != _flat_origin()
        and provenance != _formula_loss_origin()
        and provenance != _late_positive_origin()
    )


def _rebuild_state(
    policy: ProtectionPolicy,
    mandate: ProtectionMandate,
    raw_quantity: int,
    execution_commitment: bytes,
    formula_available: bool,
    armed_hard_bail_trigger: _ReportedPrice | None,
    activation_price: _ReportedPrice | None,
    high_watermark: _ReportedPrice | None,
    trail: _ReportedPrice | None,
    waiting_buy_resolution: bool,
    cursor_ordinal: int,
    cursor_head: bytes,
    stream_epoch: int,
    stream_sequence: int,
    stream_source_time: int,
    stream_evaluation_time: int,
    stream_halted: bool,
    last_occurrence_id: bytes,
    last_occurrence_payload: bytes,
    last_primary_present: bool,
    last_primary_units: int,
    hard_bid_count: int,
    hard_bid_sequence: int,
    hard_bid_source_time: int,
    hard_bid_identity: bytes,
    trade_present: bool,
    trade_source_time: int,
    trade_identity: bytes,
    trade_units: int,
    trail_bid_count: int,
    trail_bid_sequence: int,
    trail_bid_source_time: int,
    trail_bid_identity: bytes,
    exit_provenance: bytes,
) -> PositionProtectionState:
    commitment = _state_commitment(
        policy,
        mandate,
        raw_quantity,
        execution_commitment,
        formula_available,
        armed_hard_bail_trigger,
        activation_price,
        high_watermark,
        trail,
        waiting_buy_resolution,
        cursor_ordinal,
        cursor_head,
        stream_epoch,
        stream_sequence,
        stream_source_time,
        stream_evaluation_time,
        stream_halted,
        last_occurrence_id,
        last_occurrence_payload,
        last_primary_present,
        last_primary_units,
        hard_bid_count,
        hard_bid_sequence,
        hard_bid_source_time,
        hard_bid_identity,
        trade_present,
        trade_source_time,
        trade_identity,
        trade_units,
        trail_bid_count,
        trail_bid_sequence,
        trail_bid_source_time,
        trail_bid_identity,
        exit_provenance,
    )
    return _new_position_protection_state(
        policy,
        mandate,
        raw_quantity,
        execution_commitment,
        formula_available,
        armed_hard_bail_trigger,
        activation_price,
        high_watermark,
        trail,
        waiting_buy_resolution,
        commitment,
        cursor_ordinal,
        cursor_head,
        stream_epoch,
        stream_sequence,
        stream_source_time,
        stream_evaluation_time,
        stream_halted,
        last_occurrence_id,
        last_occurrence_payload,
        last_primary_present,
        last_primary_units,
        hard_bid_count,
        hard_bid_sequence,
        hard_bid_source_time,
        hard_bid_identity,
        trade_present,
        trade_source_time,
        trade_identity,
        trade_units,
        trail_bid_count,
        trail_bid_sequence,
        trail_bid_source_time,
        trail_bid_identity,
        exit_provenance,
    )


def _new_state_from_projection(
    mandate: ProtectionMandate,
    projection: ProtectionVenueProjection,
    prior: PositionProtectionState | None,
) -> PositionProtectionState:
    raw_quantity = projection._raw_quantity
    average_available = (
        raw_quantity > 0
        and projection._basis_available
        and projection._cost_basis > 0
        and projection._basis_metadata_available
        and _basis_metadata_matches(projection._basis_price, mandate.tick)
        and projection._integrity is _PositionIntegrity.CONSISTENT
        and projection.execution_binding_matches
        and projection.account_reconciliation_clear
    )
    average = (
        projection._cost_basis / raw_quantity if average_available else _Fraction(0)
    )
    activation_price = (
        _upward_price(average * (1 + mandate.approved_gain), mandate.tick)
        if average_available
        else None
    )
    candidate = (
        _upward_price(average * (1 - mandate.loss_fraction), mandate.tick)
        if average_available
        else None
    )
    formula_available = (
        average_available and candidate is not None and candidate.exact_value < average
    )
    hard_bail = candidate if formula_available else None
    if (
        prior is not None
        and prior.armed_hard_bail_trigger is not None
        and (
            hard_bail is None
            or prior.armed_hard_bail_trigger.exact_value > hard_bail.exact_value
        )
    ):
        hard_bail = prior.armed_hard_bail_trigger
    late_positive = (
        prior is not None
        and prior._exit_provenance == _flat_origin()
        and raw_quantity > 0
    )
    flat_ready = (
        raw_quantity == 0
        and projection.execution_binding_matches
        and projection.account_reconciliation_clear
        and projection.blocking_effect_count == 0
    )
    if flat_ready:
        policy = ProtectionPolicy.FLAT
    elif raw_quantity <= 0:
        policy = ProtectionPolicy.HARD_BAIL
    elif late_positive:
        policy = ProtectionPolicy.HARD_BAIL
    elif prior is not None and (
        prior._exit_provenance == _formula_loss_origin()
        or prior._exit_provenance == _late_positive_origin()
    ):
        policy = ProtectionPolicy.HARD_BAIL
    elif not formula_available:
        policy = ProtectionPolicy.HARD_BAIL
    elif raw_quantity > mandate.maximum_quantity.value:
        policy = ProtectionPolicy.HARD_BAIL
    elif (
        prior is not None
        and prior.raw_quantity > 0
        and prior.policy is ProtectionPolicy.TRAIL_ACTIVE
    ):
        policy = ProtectionPolicy.TRAIL_ACTIVE
    elif (
        prior is not None
        and prior.raw_quantity > 0
        and prior.policy is ProtectionPolicy.EXIT_NORMAL
    ):
        policy = ProtectionPolicy.EXIT_NORMAL
    elif (
        prior is not None
        and prior.raw_quantity > 0
        and prior.policy is ProtectionPolicy.HARD_BAIL
    ):
        policy = ProtectionPolicy.HARD_BAIL
    else:
        policy = ProtectionPolicy.FLOOR_ONLY
    high_watermark = None if prior is None else prior.high_watermark
    trail = None if prior is None else prior.trail
    if flat_ready or late_positive:
        high_watermark = None
        trail = None
    waiting = projection.blocking_buy_effect_count > 0
    genesis = _market_genesis()
    reset_all = (
        prior is None
        or not formula_available
        or flat_ready
        or late_positive
        or (prior is not None and not prior.formula_available)
    )
    if reset_all:
        stream_epoch = -1
        stream_sequence = -1
        stream_source_time = -1
        stream_evaluation_time = -1
        stream_halted = False
        last_occurrence_id = genesis
        last_occurrence_payload = genesis
        last_primary_present = False
        last_primary_units = 0
        hard_bid_count = 0
        hard_bid_sequence = -1
        hard_bid_source_time = -1
        hard_bid_identity = genesis
        trade_present = False
        trade_source_time = -1
        trade_identity = genesis
        trade_units = 0
        trail_bid_count = 0
        trail_bid_sequence = -1
        trail_bid_source_time = -1
        trail_bid_identity = genesis
    else:
        if prior is None:
            raise TypeError("retained prior state is required")
        stream_epoch = prior._stream_epoch
        stream_sequence = prior._stream_sequence
        stream_source_time = prior._stream_source_time
        stream_evaluation_time = prior._stream_evaluation_time
        stream_halted = prior._stream_halted
        last_occurrence_id = prior._last_occurrence_id
        last_occurrence_payload = prior._last_occurrence_payload
        last_primary_present = prior._last_primary_present
        last_primary_units = prior._last_primary_units
        hard_bid_count = prior._hard_bid_count
        hard_bid_sequence = prior._hard_bid_sequence
        hard_bid_source_time = prior._hard_bid_source_time
        hard_bid_identity = prior._hard_bid_identity
        trade_present = prior._trade_present
        trade_source_time = prior._trade_source_time
        trade_identity = prior._trade_identity
        trade_units = prior._trade_units
        trail_bid_count = prior._trail_bid_count
        trail_bid_sequence = prior._trail_bid_sequence
        trail_bid_source_time = prior._trail_bid_source_time
        trail_bid_identity = prior._trail_bid_identity
    trigger_changed = (
        prior is not None
        and prior.armed_hard_bail_trigger != hard_bail
        and not reset_all
    )
    if trigger_changed:
        hard_bid_count = 0
        hard_bid_sequence = -1
        hard_bid_source_time = -1
        hard_bid_identity = genesis
        trade_present = False
        trade_source_time = -1
        trade_identity = genesis
        trade_units = 0
    if flat_ready:
        exit_provenance = _flat_origin()
    elif raw_quantity == 0 and prior is not None:
        exit_provenance = prior._exit_provenance
    elif late_positive:
        exit_provenance = _late_positive_origin()
    elif not formula_available:
        exit_provenance = _formula_loss_origin()
    elif prior is None:
        exit_provenance = _exit_genesis()
    else:
        exit_provenance = prior._exit_provenance
    return _rebuild_state(
        policy,
        mandate,
        raw_quantity,
        projection.execution_commitment,
        formula_available,
        hard_bail,
        activation_price,
        high_watermark,
        trail,
        waiting,
        projection.cursor_ordinal,
        projection.cursor_head,
        stream_epoch,
        stream_sequence,
        stream_source_time,
        stream_evaluation_time,
        stream_halted,
        last_occurrence_id,
        last_occurrence_payload,
        last_primary_present,
        last_primary_units,
        hard_bid_count,
        hard_bid_sequence,
        hard_bid_source_time,
        hard_bid_identity,
        trade_present,
        trade_source_time,
        trade_identity,
        trade_units,
        trail_bid_count,
        trail_bid_sequence,
        trail_bid_source_time,
        trail_bid_identity,
        exit_provenance,
    )


def _occurrence_identity(occurrence: MarketOccurrence) -> bytes:
    return _commit_parts(
        b"execution-core/protection-market-occurrence-identity/v1",
        _encode_text(occurrence.occurrence_id.value),
    )


def _occurrence_payload(occurrence: MarketOccurrence) -> bytes:
    return _commit_parts(
        b"execution-core/protection-market-occurrence-payload/v1",
        _encode_text(occurrence.source_id.value),
        _encode_position_scope(occurrence.position_scope),
        _encode_text(occurrence.session_id.value),
        _encode_int(occurrence.market_epoch),
        _encode_int(
            occurrence.source_sequence if occurrence.source_sequence is not None else -1
        ),
        _encode_int(occurrence.source_time),
        _encode_text(occurrence.kind.value),
        _encode_reported_price(occurrence.best_bid),
        _encode_reported_price(occurrence.best_ask),
        _encode_reported_price(occurrence.trade_price),
        _encode_reported_price(occurrence.atr_distance),
        _encode_reported_price(occurrence.structure_trail),
        _encode_int(1 if occurrence.halted else 0),
    )


def _market_price_matches(
    price: _ReportedPrice,
    tick: _TickMetadata,
) -> bool:
    return (
        type(price.units) is _PriceUnits
        and type(price.scale) is _PriceScale
        and type(price.tick) is _TickMetadata
        and type(price.tick.tick_units) is _PriceUnits
        and type(price.tick.scale) is _PriceScale
        and price.units.value > 0
        and price.tick.tick_units.value > 0
        and price.scale == tick.scale
        and price.tick.scale == tick.scale
        and tick.tick_units.value % price.tick.tick_units.value == 0
        and price.units.value % tick.tick_units.value == 0
    )


def _mandate_price(units: int, tick: _TickMetadata) -> _ReportedPrice:
    return _ReportedPrice(_PriceUnits(units), tick.scale, tick)


def _step_is_eligible(
    state: PositionProtectionState,
    units: int,
) -> bool:
    if not state._last_primary_present:
        return True
    difference = (
        units - state._last_primary_units
        if units >= state._last_primary_units
        else state._last_primary_units - units
    )
    return _Fraction(difference) <= (
        _Fraction(state._last_primary_units)
        * state.mandate.evidence_policy.max_step_fraction
    )


def _goal_for_state(
    state: PositionProtectionState,
    projection: ProtectionVenueProjection,
) -> ExecutionGoal | None:
    exit_policy = (
        state.policy is ProtectionPolicy.EXIT_NORMAL
        or state.policy is ProtectionPolicy.HARD_BAIL
    )
    if (
        not exit_policy
        or not _real_exit(state._exit_provenance)
        or not state.formula_available
        or state.raw_quantity <= 0
        or state.raw_quantity > state.mandate.maximum_quantity.value
        or state.waiting_buy_resolution
        or projection.blocking_effect_count != 0
        or not projection.execution_binding_matches
        or not projection.account_reconciliation_clear
        or state.execution_commitment != projection.execution_commitment
    ):
        return None
    urgency = (
        ProtectionUrgency.NORMAL
        if state.policy is ProtectionPolicy.EXIT_NORMAL
        else ProtectionUrgency.EMERGENCY
    )
    guard = (
        state.mandate.normal_guard
        if state.policy is ProtectionPolicy.EXIT_NORMAL
        else state.mandate.emergency_guard
    )
    return ExecutionGoal(
        _ExecutionSide.SELL,
        _Quantity(state.raw_quantity),
        urgency,
        guard,
        state.mandate.deadline,
        state.mandate.session_id,
        state.mandate.mandate_id,
        state.mandate.maximum_goal_rate,
        state.execution_commitment,
        state.commitment,
    )


def _market_inert_transition(
    state: PositionProtectionState,
    projection: ProtectionVenueProjection,
    advanced: bool,
    alert: ProtectionAlert | None,
) -> ProtectionTransition:
    disposition = (
        ProtectionDisposition.APPLIED
        if advanced
        else ProtectionDisposition.EXACT_REPLAY
    )
    goal = _goal_for_state(state, projection) if advanced else None
    return ProtectionTransition(state, disposition, goal, alert)


def _state_after_market_halt(
    state: PositionProtectionState,
    occurrence: MarketOccurrence,
    identity: bytes,
    payload: bytes,
) -> PositionProtectionState:
    genesis = _market_genesis()
    stream_sequence = (
        occurrence.source_sequence
        if occurrence.source_sequence is not None
        else (
            -1
            if occurrence.market_epoch > state._stream_epoch
            else state._stream_sequence
        )
    )
    return _rebuild_state(
        state.policy,
        state.mandate,
        state.raw_quantity,
        state.execution_commitment,
        state.formula_available,
        state.armed_hard_bail_trigger,
        state.activation_price,
        state.high_watermark,
        state.trail,
        state.waiting_buy_resolution,
        state._cursor_ordinal,
        state._cursor_head,
        occurrence.market_epoch,
        stream_sequence,
        occurrence.source_time,
        occurrence.evaluation_time,
        True,
        identity,
        payload,
        False,
        0,
        0,
        -1,
        -1,
        genesis,
        False,
        -1,
        genesis,
        0,
        0,
        -1,
        -1,
        genesis,
        state._exit_provenance,
    )


def _reduce_market_occurrence(
    state: PositionProtectionState,
    projection: ProtectionVenueProjection,
    occurrence: MarketOccurrence,
    advanced: bool,
    alert: ProtectionAlert | None,
) -> ProtectionTransition:
    identity = _occurrence_identity(occurrence)
    payload = _occurrence_payload(occurrence)
    if identity == state._last_occurrence_id:
        if advanced:
            return _market_inert_transition(state, projection, True, alert)
        if payload == state._last_occurrence_payload:
            return ProtectionTransition(
                state,
                ProtectionDisposition.EXACT_REPLAY,
                None,
                alert,
            )
        return ProtectionTransition(
            state,
            ProtectionDisposition.REFUSED,
            None,
            alert,
        )
    if (
        not state.formula_available
        or state.policy is ProtectionPolicy.FLAT
        or occurrence.position_scope != state.mandate.position_scope
        or occurrence.source_id != state.mandate.evidence_policy.source_id
        or occurrence.session_id != state.mandate.session_id
        or occurrence.source_time > occurrence.evaluation_time
        or occurrence.evaluation_time - occurrence.source_time
        > state.mandate.evidence_policy.max_age
        or occurrence.market_epoch < state._stream_epoch
    ):
        return _market_inert_transition(state, projection, advanced, alert)
    new_epoch = occurrence.market_epoch > state._stream_epoch
    if not new_epoch and (
        occurrence.source_time < state._stream_source_time
        or occurrence.evaluation_time < state._stream_evaluation_time
        or (
            occurrence.source_sequence is not None
            and state._stream_sequence >= 0
            and occurrence.source_sequence <= state._stream_sequence
        )
    ):
        return _market_inert_transition(state, projection, advanced, alert)
    if state._stream_halted and not new_epoch:
        return _market_inert_transition(state, projection, advanced, alert)
    if occurrence.halted:
        next_state = _state_after_market_halt(state, occurrence, identity, payload)
        return ProtectionTransition(
            next_state,
            ProtectionDisposition.APPLIED,
            _goal_for_state(next_state, projection),
            alert,
        )
    if occurrence.kind is MarketKind.BEST_BID:
        if (
            type(occurrence.best_bid) is not _ReportedPrice
            or type(occurrence.best_ask) is not _ReportedPrice
            or not _market_price_matches(occurrence.best_bid, state.mandate.tick)
            or not _market_price_matches(occurrence.best_ask, state.mandate.tick)
            or occurrence.best_bid.exact_value > occurrence.best_ask.exact_value
        ):
            return _market_inert_transition(state, projection, advanced, alert)
        primary = occurrence.best_bid
    else:
        if type(
            occurrence.trade_price
        ) is not _ReportedPrice or not _market_price_matches(
            occurrence.trade_price, state.mandate.tick
        ):
            return _market_inert_transition(state, projection, advanced, alert)
        primary = occurrence.trade_price
    if not new_epoch and not _step_is_eligible(state, primary.units.value):
        return _market_inert_transition(state, projection, advanced, alert)

    genesis = _market_genesis()
    stream_sequence = (
        occurrence.source_sequence
        if occurrence.source_sequence is not None
        else (-1 if new_epoch else state._stream_sequence)
    )
    last_primary_present = False if new_epoch else state._last_primary_present
    last_primary_units = 0 if new_epoch else state._last_primary_units
    hard_bid_count = 0 if new_epoch else state._hard_bid_count
    hard_bid_sequence = -1 if new_epoch else state._hard_bid_sequence
    hard_bid_source_time = -1 if new_epoch else state._hard_bid_source_time
    hard_bid_identity = genesis if new_epoch else state._hard_bid_identity
    trade_present = False if new_epoch else state._trade_present
    trade_source_time = -1 if new_epoch else state._trade_source_time
    trade_identity = genesis if new_epoch else state._trade_identity
    trade_units = 0 if new_epoch else state._trade_units
    trail_bid_count = 0 if new_epoch else state._trail_bid_count
    trail_bid_sequence = -1 if new_epoch else state._trail_bid_sequence
    trail_bid_source_time = -1 if new_epoch else state._trail_bid_source_time
    trail_bid_identity = genesis if new_epoch else state._trail_bid_identity
    policy = state.policy
    high_watermark = state.high_watermark
    trail = state.trail
    exit_provenance = state._exit_provenance
    hard_triggered = False
    hard_counterpart_identity = genesis
    trigger = state.armed_hard_bail_trigger
    below_hard = trigger is not None and primary.exact_value <= trigger.exact_value
    last_primary_present = True
    last_primary_units = primary.units.value
    if occurrence.kind is MarketKind.TRADE:
        if below_hard:
            hard_triggered = (
                hard_bid_count > 0
                and hard_bid_identity != identity
                and occurrence.source_time - hard_bid_source_time
                <= state.mandate.evidence_policy.corroboration_window
            )
            if hard_triggered:
                hard_counterpart_identity = hard_bid_identity
            trade_present = True
            trade_source_time = occurrence.source_time
            trade_identity = identity
            trade_units = primary.units.value
        else:
            trade_present = False
            trade_source_time = -1
            trade_identity = genesis
            trade_units = 0
        hard_bid_count = 0
        hard_bid_sequence = -1
        hard_bid_source_time = -1
        hard_bid_identity = genesis
        trail_bid_count = 0
        trail_bid_sequence = -1
        trail_bid_source_time = -1
        trail_bid_identity = genesis
    else:
        if below_hard:
            prior_hard_bid_identity = hard_bid_identity
            hard_triggered = (
                trade_present
                and trade_identity != identity
                and occurrence.source_time - trade_source_time
                <= state.mandate.evidence_policy.corroboration_window
            )
            if hard_triggered:
                hard_counterpart_identity = trade_identity
            hard_bid_count = (
                hard_bid_count + 1
                if hard_bid_count > 0 and hard_bid_identity != identity
                else 1
            )
            hard_bid_sequence = stream_sequence
            hard_bid_source_time = occurrence.source_time
            hard_bid_identity = identity
            if hard_bid_count >= 2:
                hard_triggered = True
                hard_counterpart_identity = prior_hard_bid_identity
        else:
            hard_bid_count = 0
            hard_bid_sequence = -1
            hard_bid_source_time = -1
            hard_bid_identity = genesis
            trade_present = False
            trade_source_time = -1
            trade_identity = genesis
            trade_units = 0
    if hard_triggered:
        policy = ProtectionPolicy.HARD_BAIL
        exit_provenance = _commit_parts(
            b"execution-core/protection-hard-exit/v1",
            hard_counterpart_identity,
            identity,
        )
        trail_bid_count = 0
        trail_bid_sequence = -1
        trail_bid_source_time = -1
        trail_bid_identity = genesis
    elif occurrence.kind is MarketKind.BEST_BID:
        if (
            policy is ProtectionPolicy.FLOOR_ONLY
            and state.activation_price is not None
            and primary.exact_value >= state.activation_price.exact_value
        ):
            policy = ProtectionPolicy.TRAIL_ACTIVE
            high_watermark = primary
        if policy is ProtectionPolicy.TRAIL_ACTIVE:
            if (
                high_watermark is None
                or primary.exact_value > high_watermark.exact_value
            ):
                high_watermark = primary
            percent_candidate = _upward_price(
                high_watermark.exact_value * (1 - state.mandate.percent_trail_fraction),
                state.mandate.tick,
            )
            trail_candidate = percent_candidate
            if (
                type(occurrence.atr_distance) is _ReportedPrice
                and _market_price_matches(
                    occurrence.atr_distance,
                    state.mandate.tick,
                )
                and high_watermark.exact_value
                > occurrence.atr_distance.exact_value * state.mandate.atr_multiple
            ):
                atr_candidate = _upward_price(
                    high_watermark.exact_value
                    - occurrence.atr_distance.exact_value * state.mandate.atr_multiple,
                    state.mandate.tick,
                )
                if atr_candidate.exact_value > trail_candidate.exact_value:
                    trail_candidate = atr_candidate
            if (
                type(occurrence.structure_trail) is _ReportedPrice
                and _market_price_matches(
                    occurrence.structure_trail,
                    state.mandate.tick,
                )
                and occurrence.structure_trail.exact_value <= high_watermark.exact_value
                and occurrence.structure_trail.exact_value > trail_candidate.exact_value
            ):
                trail_candidate = occurrence.structure_trail
            trail_changed = trail is None or (
                trail_candidate.exact_value > trail.exact_value
            )
            if trail_changed:
                trail = trail_candidate
                trail_bid_count = 0
                trail_bid_sequence = -1
                trail_bid_source_time = -1
                trail_bid_identity = genesis
            if trail is None:
                raise TypeError("active trail is required")
            if primary.exact_value <= trail.exact_value:
                prior_trail_identity = trail_bid_identity
                trail_bid_count = (
                    trail_bid_count + 1
                    if trail_bid_count > 0 and trail_bid_identity != identity
                    else 1
                )
                trail_bid_sequence = stream_sequence
                trail_bid_source_time = occurrence.source_time
                trail_bid_identity = identity
                if trail_bid_count >= 2:
                    policy = ProtectionPolicy.EXIT_NORMAL
                    exit_provenance = _commit_parts(
                        b"execution-core/protection-normal-exit/v1",
                        prior_trail_identity,
                        identity,
                    )
            else:
                trail_bid_count = 0
                trail_bid_sequence = -1
                trail_bid_source_time = -1
                trail_bid_identity = genesis

    next_state = _rebuild_state(
        policy,
        state.mandate,
        state.raw_quantity,
        state.execution_commitment,
        state.formula_available,
        state.armed_hard_bail_trigger,
        state.activation_price,
        high_watermark,
        trail,
        state.waiting_buy_resolution,
        state._cursor_ordinal,
        state._cursor_head,
        occurrence.market_epoch,
        stream_sequence,
        occurrence.source_time,
        occurrence.evaluation_time,
        False,
        identity,
        payload,
        last_primary_present,
        last_primary_units,
        hard_bid_count,
        hard_bid_sequence,
        hard_bid_source_time,
        hard_bid_identity,
        trade_present,
        trade_source_time,
        trade_identity,
        trade_units,
        trail_bid_count,
        trail_bid_sequence,
        trail_bid_source_time,
        trail_bid_identity,
        exit_provenance,
    )
    return ProtectionTransition(
        next_state,
        ProtectionDisposition.APPLIED,
        _goal_for_state(next_state, projection),
        alert,
    )


def project_protection_venue(
    transition: _VenueRecoveryTransition,
    mandate: ProtectionMandate,
) -> ProtectionVenueProjection:
    if type(transition) is not _VenueRecoveryTransition:
        raise TypeError("transition must be VenueRecoveryTransition")
    if type(mandate) is not ProtectionMandate:
        raise TypeError("mandate must be ProtectionMandate")
    proof = transition._protection_proof
    if type(proof) is not _ProtectionTransitionProof:
        raise TypeError("transition protection proof is not exact")
    proof_commitment = transition._protection_proof_commitment
    if type(proof_commitment) is not bytes:
        raise ValueError("transition protection proof commitment is not exact")
    if proof.commitment != proof_commitment:
        raise ValueError("transition protection proof commitment differs")
    if not proof.lineage_is_authentic:
        raise ValueError("transition protection proof lineage is not authentic")
    if type(proof.predecessor_cursor) is not _ProtectionCursor:
        raise ValueError("predecessor protection cursor is not exact")
    if type(proof.cursor) is not _ProtectionCursor:
        raise ValueError("protection cursor is not exact")
    if type(proof.predecessor_summary) is not _SymbolAuthoritySummary:
        raise ValueError("predecessor authority summary is not exact")
    if type(proof.summary) is not _SymbolAuthoritySummary:
        raise ValueError("authority summary is not exact")
    if (
        proof.predecessor_binding is not None
        and type(proof.predecessor_binding) is not _VenueExecutionBinding
    ):
        raise ValueError("predecessor execution binding is not exact")
    if proof.binding is not None and type(proof.binding) is not _VenueExecutionBinding:
        raise ValueError("execution binding is not exact")
    if proof.position_scope != mandate.position_scope:
        raise ValueError("transition and mandate position scopes differ")
    if proof.cursor.mandate_id != mandate.mandate_id:
        raise ValueError("transition and mandate identities differ")
    if proof.disposition is not transition.disposition:
        raise ValueError("transition disposition is not proof-bound")
    if proof.quantity_delta != transition.quantity_delta:
        raise ValueError("transition quantity delta is not proof-bound")
    if proof.book_scope != transition.book.scope:
        raise ValueError("transition book scope is not proof-bound")
    if proof.book_commitment != transition.book._protection_commitment:
        raise ValueError("transition book envelope is not proof-bound")
    if proof.execution_commitment != transition.execution.commitment:
        raise ValueError("transition execution is not proof-bound")
    if not _execution_matches_checkpoint(transition.execution, proof):
        raise ValueError("transition execution checkpoint is not proof-bound")
    if _extract_protection_transition(transition) != (
        proof.summary,
        proof.binding,
        proof.cursor,
    ):
        raise ValueError("transition book is not proof-bound")
    position = transition.execution.position
    raw_quantity = position.raw_quantity
    basis_available = position.basis_authority is _BasisAuthority.AVAILABLE
    cost_basis = (
        position.cost_basis.value if position.cost_basis is not None else _Fraction(0)
    )
    if type(position.basis_price_metadata) is _ReportedPrice:
        basis_metadata_available = True
        basis_price = position.basis_price_metadata
    else:
        basis_metadata_available = False
        basis_price = _ReportedPrice(
            _PriceUnits(0),
            mandate.tick.scale,
            mandate.tick,
        )
    mandate_commitment = _commit_mandate(mandate)
    seal = _projection_commitment(
        proof.predecessor_cursor.ordinal,
        proof.predecessor_cursor.head,
        proof.cursor.ordinal,
        proof.cursor.head,
        proof.predecessor_execution_commitment,
        proof.execution_commitment,
        proof.predecessor_summary.blocking_effect_count,
        proof.predecessor_summary.blocking_buy_effect_count,
        proof.summary.blocking_effect_count,
        proof.summary.blocking_buy_effect_count,
        proof.predecessor_execution_binding_matches,
        proof.execution_binding_matches,
        proof.predecessor_account_reconciliation_clear,
        proof.account_reconciliation_clear,
        proof.position_scope,
        mandate_commitment,
        raw_quantity,
        basis_available,
        cost_basis,
        basis_metadata_available,
        basis_price,
        transition.execution.integrity,
    )
    return _new_protection_venue_projection(
        proof.predecessor_cursor.ordinal,
        proof.predecessor_cursor.head,
        proof.cursor.ordinal,
        proof.cursor.head,
        proof.predecessor_execution_commitment,
        proof.execution_commitment,
        proof.predecessor_summary.blocking_effect_count,
        proof.predecessor_summary.blocking_buy_effect_count,
        proof.summary.blocking_effect_count,
        proof.summary.blocking_buy_effect_count,
        proof.predecessor_execution_binding_matches,
        proof.execution_binding_matches,
        proof.predecessor_account_reconciliation_clear,
        proof.account_reconciliation_clear,
        proof.position_scope,
        mandate_commitment,
        raw_quantity,
        basis_available,
        cost_basis,
        basis_metadata_available,
        basis_price,
        transition.execution.integrity,
        seal,
    )


def initialize_position_protection(
    mandate: ProtectionMandate,
    projection: ProtectionVenueProjection,
) -> PositionProtectionState:
    if type(mandate) is not ProtectionMandate:
        raise TypeError("mandate must be ProtectionMandate")
    if type(projection) is not ProtectionVenueProjection:
        raise TypeError("projection must be ProtectionVenueProjection")
    if not _projection_is_authentic(projection):
        raise ValueError("projection is not authentic")
    if projection._position_scope != mandate.position_scope:
        raise ValueError("projection and mandate position scopes differ")
    if projection._mandate_commitment != _commit_mandate(mandate):
        raise ValueError("projection and mandate authority differ")
    return _new_state_from_projection(
        mandate,
        projection,
        None,
    )


def reduce_position_protection(
    state: PositionProtectionState,
    projection: ProtectionVenueProjection,
    occurrence: MarketOccurrence | None,
) -> ProtectionTransition:
    if type(state) is not PositionProtectionState:
        raise TypeError("state must be PositionProtectionState")
    if type(projection) is not ProtectionVenueProjection:
        raise TypeError("projection must be ProtectionVenueProjection")
    if occurrence is not None and type(occurrence) is not MarketOccurrence:
        raise TypeError("occurrence must be MarketOccurrence or None")
    if not _state_is_authentic(state):
        return ProtectionTransition(state, ProtectionDisposition.REFUSED, None, None)
    if not _projection_is_authentic(projection):
        return ProtectionTransition(state, ProtectionDisposition.REFUSED, None, None)
    if projection._position_scope != state.mandate.position_scope:
        return ProtectionTransition(state, ProtectionDisposition.REFUSED, None, None)
    if projection._mandate_commitment != _commit_mandate(state.mandate):
        return ProtectionTransition(state, ProtectionDisposition.REFUSED, None, None)
    if (
        state._cursor_ordinal == projection.cursor_ordinal
        and state._cursor_head == projection.cursor_head
    ):
        if occurrence is not None:
            return _reduce_market_occurrence(
                state,
                projection,
                occurrence,
                False,
                None,
            )
        return ProtectionTransition(
            state,
            ProtectionDisposition.EXACT_REPLAY,
            None,
            None,
        )
    if (
        state._cursor_ordinal != projection.predecessor_cursor_ordinal
        or state._cursor_head != projection.predecessor_cursor_head
        or state.execution_commitment != projection.predecessor_execution_commitment
    ):
        return ProtectionTransition(state, ProtectionDisposition.STALE, None, None)
    next_state = _new_state_from_projection(
        state.mandate,
        projection,
        state,
    )
    alert = (
        ProtectionAlert.LATE_POSITIVE_AFTER_FLAT
        if state._exit_provenance == _flat_origin() and next_state.raw_quantity > 0
        else None
    )
    if occurrence is not None:
        return _reduce_market_occurrence(
            next_state,
            projection,
            occurrence,
            True,
            alert,
        )
    return ProtectionTransition(
        next_state,
        ProtectionDisposition.APPLIED,
        _goal_for_state(next_state, projection),
        alert,
    )


__all__ = (
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
)
