"""Pure broker-neutral position-protection semantic center."""

from __future__ import annotations as _annotations

from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from enum import Enum as _Enum
from fractions import Fraction as _Fraction
from hashlib import sha256 as _sha256

from .fills import (
    ExecutionSide as _ExecutionSide,
    PositionScope as _PositionScope,
    _commit_parts,
    _encode_fraction,
    _encode_int,
    _encode_position_scope,
    _encode_reported_price,
    _encode_text,
    _pack_parts,
)
from .identity import (
    MandateId as _MandateId,
    MarketDataSourceId as _MarketDataSourceId,
    MarketOccurrenceId as _MarketOccurrenceId,
    MarketStreamGenerationId as _MarketStreamGenerationId,
    SessionId as _SessionId,
    _market_identity_is_canonical,
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


class MarketSequenceMode(_Enum):
    SEQUENCED = "SEQUENCED"
    SOURCE_TIME = "SOURCE_TIME"


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
    MARKET_BASELINE_REQUIRED = "MARKET_BASELINE_REQUIRED"
    MARKET_COORDINATE_EXHAUSTED = "MARKET_COORDINATE_EXHAUSTED"


@_dataclass(frozen=True, slots=True)
class EvidencePolicy:
    source_id: _MarketDataSourceId
    stream_generation: _MarketStreamGenerationId
    sequence_mode: MarketSequenceMode
    max_age: int
    corroboration_window: int
    max_step_fraction: _Fraction

    def __post_init__(self) -> None:
        if type(self.source_id) is not _MarketDataSourceId:
            raise TypeError("source_id must be MarketDataSourceId")
        if type(self.stream_generation) is not _MarketStreamGenerationId:
            raise TypeError("stream_generation must be MarketStreamGenerationId")
        if type(self.sequence_mode) is not MarketSequenceMode:
            raise TypeError("sequence_mode must be MarketSequenceMode")
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
    occurrence_id: _MarketOccurrenceId = _field(init=False)
    source_id: _MarketDataSourceId
    stream_generation: _MarketStreamGenerationId
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
        if type(self.source_id) is not _MarketDataSourceId:
            raise TypeError("source_id must be MarketDataSourceId")
        if type(self.stream_generation) is not _MarketStreamGenerationId:
            raise TypeError("stream_generation must be MarketStreamGenerationId")
        if type(self.position_scope) is not _PositionScope:
            raise TypeError("position_scope must be PositionScope")
        if type(self.session_id) is not _SessionId:
            raise TypeError("session_id must be SessionId")
        if type(self.market_epoch) is not int:
            raise TypeError("market_epoch must be an exact integer")
        if self.market_epoch < 0 or self.market_epoch > 18446744073709551615:
            raise ValueError("market_epoch must be an unsigned 64-bit integer")
        if self.source_sequence is not None:
            if type(self.source_sequence) is not int:
                raise TypeError("source_sequence must be an exact integer or None")
            if self.source_sequence < 0 or self.source_sequence > 18446744073709551615:
                raise ValueError("source_sequence must be an unsigned 64-bit integer")
        if type(self.source_time) is not int:
            raise TypeError("source_time must be an exact integer")
        if self.source_time < 0 or self.source_time > 18446744073709551615:
            raise ValueError("source_time must be an unsigned 64-bit integer")
        if type(self.evaluation_time) is not int:
            raise TypeError("evaluation_time must be an exact integer")
        if self.evaluation_time < 0 or self.evaluation_time > 18446744073709551615:
            raise ValueError("evaluation_time must be an unsigned 64-bit integer")
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
        preimage = _market_occurrence_preimage(
            source_id=self.source_id.value,
            position_scope=self.position_scope,
            session_id=self.session_id.value,
            stream_generation=self.stream_generation._bytes,
            market_epoch=self.market_epoch,
            source_sequence=self.source_sequence,
            source_time=self.source_time,
            kind=self.kind.value,
            best_bid=self.best_bid,
            best_ask=self.best_ask,
            trade_price=self.trade_price,
            atr_distance=self.atr_distance,
            structure_trail=self.structure_trail,
            halted=self.halted,
        )
        object.__setattr__(
            self,
            "occurrence_id",
            _MarketOccurrenceId(_sha256(preimage).hexdigest()),
        )

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
    _market_occurrence_epoch: int | None
    _market_committed_epoch: int | None
    _market_expected_epoch: int | None
    _market_source_sequence: int | None
    _market_source_time: int | None
    _market_evaluation_time: int | None
    _market_occurrence_identity: _MarketOccurrenceId | None
    _market_halted: bool
    _market_baseline_required: bool
    _market_exhausted: bool
    _market_last_primary: _ReportedPrice | None
    _hard_bid_identity: _MarketOccurrenceId | None
    _hard_bid_source_time: int | None
    _trade_identity: _MarketOccurrenceId | None
    _trade_source_time: int | None
    _trail_bid_identity: _MarketOccurrenceId | None
    _trail_bid_source_time: int | None
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
    _execution_fact_count: int
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
    _market_occurrence_epoch: int | None,
    _market_committed_epoch: int | None,
    _market_expected_epoch: int | None,
    _market_source_sequence: int | None,
    _market_source_time: int | None,
    _market_evaluation_time: int | None,
    _market_occurrence_identity: _MarketOccurrenceId | None,
    _market_halted: bool,
    _market_baseline_required: bool,
    _market_exhausted: bool,
    _market_last_primary: _ReportedPrice | None,
    _hard_bid_identity: _MarketOccurrenceId | None,
    _hard_bid_source_time: int | None,
    _trade_identity: _MarketOccurrenceId | None,
    _trade_source_time: int | None,
    _trail_bid_identity: _MarketOccurrenceId | None,
    _trail_bid_source_time: int | None,
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
    object.__setattr__(result, "_market_occurrence_epoch", _market_occurrence_epoch)
    object.__setattr__(result, "_market_committed_epoch", _market_committed_epoch)
    object.__setattr__(result, "_market_expected_epoch", _market_expected_epoch)
    object.__setattr__(result, "_market_source_sequence", _market_source_sequence)
    object.__setattr__(result, "_market_source_time", _market_source_time)
    object.__setattr__(result, "_market_evaluation_time", _market_evaluation_time)
    object.__setattr__(
        result,
        "_market_occurrence_identity",
        _market_occurrence_identity,
    )
    object.__setattr__(result, "_market_halted", _market_halted)
    object.__setattr__(result, "_market_baseline_required", _market_baseline_required)
    object.__setattr__(result, "_market_exhausted", _market_exhausted)
    object.__setattr__(result, "_market_last_primary", _market_last_primary)
    object.__setattr__(result, "_hard_bid_identity", _hard_bid_identity)
    object.__setattr__(result, "_hard_bid_source_time", _hard_bid_source_time)
    object.__setattr__(result, "_trade_identity", _trade_identity)
    object.__setattr__(result, "_trade_source_time", _trade_source_time)
    object.__setattr__(result, "_trail_bid_identity", _trail_bid_identity)
    object.__setattr__(result, "_trail_bid_source_time", _trail_bid_source_time)
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
    _execution_fact_count: int,
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
    object.__setattr__(result, "_execution_fact_count", _execution_fact_count)
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
        _encode_text(mandate.evidence_policy.stream_generation.value),
        _encode_text(mandate.evidence_policy.sequence_mode.value),
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
    execution_fact_count: int,
    basis_available: bool,
    cost_basis: _Fraction,
    basis_metadata_available: bool,
    basis_price: _ReportedPrice,
    integrity: _PositionIntegrity,
) -> bytes:
    return _commit_parts(
        b"execution-core/protection-venue-projection/v2",
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
        _encode_int(execution_fact_count),
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
        projection._execution_fact_count,
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


def _u64_bytes(value: int) -> bytes:
    if type(value) is not int:
        raise TypeError("coordinate must be an exact integer")
    if value < 0 or value > 18446744073709551615:
        raise ValueError("coordinate must be an unsigned 64-bit integer")
    return int.to_bytes(value, 8, "big")


def _optional_u64(value: int | None) -> bytes:
    if value is None:
        return b"\x00" + b"\x00" * 8
    return b"\x01" + _u64_bytes(value)


def _optional_32(value: bytes | None) -> bytes:
    if value is None:
        return b"\x00" + b"\x00" * 32
    if type(value) is not bytes:
        raise TypeError("optional commitment must be bytes or None")
    return b"\x01" + value


def _market_occurrence_preimage(
    source_id: str,
    position_scope: _PositionScope,
    session_id: str,
    stream_generation: bytes,
    market_epoch: int,
    source_sequence: int | None,
    source_time: int,
    kind: str,
    best_bid: _ReportedPrice | None,
    best_ask: _ReportedPrice | None,
    trade_price: _ReportedPrice | None,
    atr_distance: _ReportedPrice | None,
    structure_trail: _ReportedPrice | None,
    halted: bool,
) -> bytes:
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    if type(position_scope) is not _PositionScope:
        raise TypeError("position_scope must be PositionScope")
    if type(session_id) is not str:
        raise TypeError("session_id must be a string")
    if type(stream_generation) is not bytes:
        raise TypeError("stream_generation must be bytes")
    if source_sequence is not None and type(source_sequence) is not int:
        raise TypeError("source_sequence must be an exact integer or None")
    if type(kind) is not str:
        raise TypeError("kind must be a string")
    if type(halted) is not bool:
        raise TypeError("halted must be bool")
    sequence_present = source_sequence is not None
    return _pack_parts(
        b"execution-core/market-occurrence/v1",
        _encode_text(source_id),
        _encode_position_scope(position_scope),
        _encode_text(session_id),
        stream_generation,
        _u64_bytes(market_epoch),
        b"\x01" if sequence_present else b"\x00",
        _u64_bytes(source_sequence) if source_sequence is not None else b"\x00" * 8,
        _u64_bytes(source_time),
        _encode_text(kind),
        _encode_reported_price(best_bid),
        _encode_reported_price(best_ask),
        _encode_reported_price(trade_price),
        _encode_reported_price(atr_distance),
        _encode_reported_price(structure_trail),
        b"\x01" if halted else b"\x00",
    )


def _protection_market_cursor_preimage(
    stream_generation: bytes,
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
    if type(stream_generation) is not bytes:
        raise TypeError("stream_generation must be bytes")
    if type(sequence_mode) is not int:
        raise TypeError("sequence_mode must be an exact integer")
    if sequence_mode != 0 and sequence_mode != 1:
        raise ValueError("sequence_mode must be 0 or 1")
    if type(halted) is not bool:
        raise TypeError("halted must be bool")
    if type(baseline_required) is not bool:
        raise TypeError("baseline_required must be bool")
    if type(exhausted) is not bool:
        raise TypeError("exhausted must be bool")
    if (occurrence_epoch is None) != (occurrence_identity is None):
        raise ValueError("occurrence epoch and identity presence must match")
    if (hard_bid_identity is None) != (hard_bid_source_time is None):
        raise ValueError("hard-bid identity and source-time presence must match")
    if (trade_identity is None) != (trade_source_time is None):
        raise ValueError("trade identity and source-time presence must match")
    if (trail_bid_identity is None) != (trail_bid_source_time is None):
        raise ValueError("trail-bid identity and source-time presence must match")
    return _pack_parts(
        b"execution-core/protection-market-cursor/v1",
        stream_generation,
        b"\x00" if sequence_mode == 0 else b"\x01",
        _optional_u64(occurrence_epoch),
        _optional_u64(committed_epoch),
        _optional_u64(expected_epoch),
        _optional_u64(source_sequence),
        _optional_u64(source_time),
        _optional_u64(evaluation_time),
        _optional_32(occurrence_identity),
        b"\x01" if halted else b"\x00",
        b"\x01" if baseline_required else b"\x00",
        b"\x01" if exhausted else b"\x00",
        _optional_32(last_primary_commitment),
        _optional_32(hard_bid_identity),
        _optional_u64(hard_bid_source_time),
        _optional_32(trade_identity),
        _optional_u64(trade_source_time),
        _optional_32(trail_bid_identity),
        _optional_u64(trail_bid_source_time),
    )


def _next_market_epoch(committed_epoch: int) -> int | None:
    _u64_bytes(committed_epoch)
    if committed_epoch == 18446744073709551615:
        return None
    return committed_epoch + 1


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
    stream_generation: bytes,
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
    last_primary: _ReportedPrice | None,
    hard_bid_identity: bytes | None,
    hard_bid_source_time: int | None,
    trade_identity: bytes | None,
    trade_source_time: int | None,
    trail_bid_identity: bytes | None,
    trail_bid_source_time: int | None,
    exit_provenance: bytes,
) -> bytes:
    return _commit_parts(
        b"execution-core/position-protection-state/v4",
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
        _sha256(
            _protection_market_cursor_preimage(
                stream_generation=stream_generation,
                sequence_mode=sequence_mode,
                occurrence_epoch=occurrence_epoch,
                committed_epoch=committed_epoch,
                expected_epoch=expected_epoch,
                source_sequence=source_sequence,
                source_time=source_time,
                evaluation_time=evaluation_time,
                occurrence_identity=occurrence_identity,
                halted=halted,
                baseline_required=baseline_required,
                exhausted=exhausted,
                last_primary_commitment=(
                    None
                    if last_primary is None
                    else _encode_reported_price(last_primary)
                ),
                hard_bid_identity=hard_bid_identity,
                hard_bid_source_time=hard_bid_source_time,
                trade_identity=trade_identity,
                trade_source_time=trade_source_time,
                trail_bid_identity=trail_bid_identity,
                trail_bid_source_time=trail_bid_source_time,
            )
        ).digest(),
        exit_provenance,
    )


def _identity_bytes(value: _MarketOccurrenceId | None) -> bytes | None:
    if value is None:
        return None
    if type(value) is not _MarketOccurrenceId:
        raise TypeError("market identity must be MarketOccurrenceId or None")
    return value._bytes


def _market_occurrence_identity_is_authentic(
    value: _MarketOccurrenceId | None,
) -> bool:
    if value is None:
        return True
    return type(value) is _MarketOccurrenceId and _market_identity_is_canonical(value)


def _market_generation_is_authentic(value: _MarketStreamGenerationId) -> bool:
    return type(value) is _MarketStreamGenerationId and _market_identity_is_canonical(
        value
    )


def _state_is_authentic(state: PositionProtectionState) -> bool:
    if type(state) is not PositionProtectionState:
        return False
    if type(state.commitment) is not bytes:
        return False
    if not _market_generation_is_authentic(
        state.mandate.evidence_policy.stream_generation
    ):
        return False
    if not _market_occurrence_identity_is_authentic(state._market_occurrence_identity):
        return False
    if not _market_occurrence_identity_is_authentic(state._hard_bid_identity):
        return False
    if not _market_occurrence_identity_is_authentic(state._trade_identity):
        return False
    if not _market_occurrence_identity_is_authentic(state._trail_bid_identity):
        return False
    if (state._market_occurrence_epoch is None) != (
        state._market_occurrence_identity is None
    ):
        return False
    if (state._hard_bid_identity is None) != (state._hard_bid_source_time is None):
        return False
    if (state._trade_identity is None) != (state._trade_source_time is None):
        return False
    if (state._trail_bid_identity is None) != (state._trail_bid_source_time is None):
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
        state.mandate.evidence_policy.stream_generation._bytes,
        0
        if state.mandate.evidence_policy.sequence_mode is MarketSequenceMode.SEQUENCED
        else 1,
        state._market_occurrence_epoch,
        state._market_committed_epoch,
        state._market_expected_epoch,
        state._market_source_sequence,
        state._market_source_time,
        state._market_evaluation_time,
        _identity_bytes(state._market_occurrence_identity),
        state._market_halted,
        state._market_baseline_required,
        state._market_exhausted,
        state._market_last_primary,
        _identity_bytes(state._hard_bid_identity),
        state._hard_bid_source_time,
        _identity_bytes(state._trade_identity),
        state._trade_source_time,
        _identity_bytes(state._trail_bid_identity),
        state._trail_bid_source_time,
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


def _pre_exposure_origin() -> bytes:
    return _commit_parts(b"execution-core/protection-pre-exposure/v1")


def _flat_origin() -> bytes:
    return _commit_parts(b"execution-core/protection-flat-origin/v1")


def _formula_loss_origin() -> bytes:
    return _commit_parts(b"execution-core/protection-formula-loss-origin/v1")


def _late_positive_origin() -> bytes:
    return _commit_parts(b"execution-core/protection-late-positive-origin/v1")


def _real_exit(provenance: bytes) -> bool:
    return (
        provenance != _exit_genesis()
        and provenance != _pre_exposure_origin()
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
    market_occurrence_epoch: int | None,
    market_committed_epoch: int | None,
    market_expected_epoch: int | None,
    market_source_sequence: int | None,
    market_source_time: int | None,
    market_evaluation_time: int | None,
    market_occurrence_identity: _MarketOccurrenceId | None,
    market_halted: bool,
    market_baseline_required: bool,
    market_exhausted: bool,
    market_last_primary: _ReportedPrice | None,
    hard_bid_identity: _MarketOccurrenceId | None,
    hard_bid_source_time: int | None,
    trade_identity: _MarketOccurrenceId | None,
    trade_source_time: int | None,
    trail_bid_identity: _MarketOccurrenceId | None,
    trail_bid_source_time: int | None,
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
        mandate.evidence_policy.stream_generation._bytes,
        0
        if mandate.evidence_policy.sequence_mode is MarketSequenceMode.SEQUENCED
        else 1,
        market_occurrence_epoch,
        market_committed_epoch,
        market_expected_epoch,
        market_source_sequence,
        market_source_time,
        market_evaluation_time,
        _identity_bytes(market_occurrence_identity),
        market_halted,
        market_baseline_required,
        market_exhausted,
        market_last_primary,
        _identity_bytes(hard_bid_identity),
        hard_bid_source_time,
        _identity_bytes(trade_identity),
        trade_source_time,
        _identity_bytes(trail_bid_identity),
        trail_bid_source_time,
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
        market_occurrence_epoch,
        market_committed_epoch,
        market_expected_epoch,
        market_source_sequence,
        market_source_time,
        market_evaluation_time,
        market_occurrence_identity,
        market_halted,
        market_baseline_required,
        market_exhausted,
        market_last_primary,
        hard_bid_identity,
        hard_bid_source_time,
        trade_identity,
        trade_source_time,
        trail_bid_identity,
        trail_bid_source_time,
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
    pre_exposure_zero = (
        raw_quantity == 0
        and projection._execution_fact_count == 0
        and (
            prior is None
            or (
                prior.raw_quantity == 0
                and prior._exit_provenance == _pre_exposure_origin()
            )
        )
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
    market_expected_epoch: int | None
    if prior is None:
        market_occurrence_epoch = None
        market_committed_epoch = None
        market_expected_epoch = 0
        market_source_sequence = None
        market_source_time = None
        market_evaluation_time = None
        market_occurrence_identity = None
        market_halted = False
        market_baseline_required = True
        market_exhausted = False
    else:
        market_occurrence_epoch = prior._market_occurrence_epoch
        market_committed_epoch = prior._market_committed_epoch
        market_expected_epoch = prior._market_expected_epoch
        market_source_sequence = prior._market_source_sequence
        market_source_time = prior._market_source_time
        market_evaluation_time = prior._market_evaluation_time
        market_occurrence_identity = prior._market_occurrence_identity
        market_halted = prior._market_halted
        market_baseline_required = prior._market_baseline_required
        market_exhausted = prior._market_exhausted
    reset_all = (
        prior is None
        or not formula_available
        or flat_ready
        or late_positive
        or (prior is not None and not prior.formula_available)
    )
    if reset_all:
        market_last_primary = None
        hard_bid_identity = None
        hard_bid_source_time = None
        trade_identity = None
        trade_source_time = None
        trail_bid_identity = None
        trail_bid_source_time = None
    else:
        if prior is None:
            raise TypeError("retained prior state is required")
        market_last_primary = prior._market_last_primary
        hard_bid_identity = prior._hard_bid_identity
        hard_bid_source_time = prior._hard_bid_source_time
        trade_identity = prior._trade_identity
        trade_source_time = prior._trade_source_time
        trail_bid_identity = prior._trail_bid_identity
        trail_bid_source_time = prior._trail_bid_source_time
    trigger_changed = (
        prior is not None
        and prior.armed_hard_bail_trigger != hard_bail
        and not reset_all
    )
    if trigger_changed:
        hard_bid_identity = None
        hard_bid_source_time = None
        trade_identity = None
        trade_source_time = None
    if pre_exposure_zero:
        exit_provenance = _pre_exposure_origin()
    elif flat_ready:
        exit_provenance = _flat_origin()
    elif raw_quantity == 0 and prior is not None:
        exit_provenance = prior._exit_provenance
    elif late_positive:
        exit_provenance = _late_positive_origin()
    elif not formula_available:
        exit_provenance = _formula_loss_origin()
    elif prior is None or prior._exit_provenance == _pre_exposure_origin():
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
        market_occurrence_epoch,
        market_committed_epoch,
        market_expected_epoch,
        market_source_sequence,
        market_source_time,
        market_evaluation_time,
        market_occurrence_identity,
        market_halted,
        market_baseline_required,
        market_exhausted,
        market_last_primary,
        hard_bid_identity,
        hard_bid_source_time,
        trade_identity,
        trade_source_time,
        trail_bid_identity,
        trail_bid_source_time,
        exit_provenance,
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


def _step_is_eligible(
    state: PositionProtectionState,
    primary: _ReportedPrice,
) -> bool:
    retained = state._market_last_primary
    if retained is None:
        return True
    difference = (
        primary.exact_value - retained.exact_value
        if primary.exact_value >= retained.exact_value
        else retained.exact_value - primary.exact_value
    )
    return difference <= (
        retained.exact_value * state.mandate.evidence_policy.max_step_fraction
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
        or state._market_halted
        or state._market_baseline_required
        or state._market_exhausted
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


def _market_projection_is_current(
    state: PositionProtectionState,
    projection: ProtectionVenueProjection,
) -> bool:
    return (
        _projection_is_authentic(projection)
        and projection._position_scope == state.mandate.position_scope
        and projection._mandate_commitment == _commit_mandate(state.mandate)
        and state._cursor_ordinal == projection.cursor_ordinal
        and state._cursor_head == projection.cursor_head
        and state.execution_commitment == projection.execution_commitment
    )


def _market_state(
    state: PositionProtectionState,
    policy: ProtectionPolicy,
    high_watermark: _ReportedPrice | None,
    trail: _ReportedPrice | None,
    occurrence_epoch: int | None,
    committed_epoch: int | None,
    expected_epoch: int | None,
    source_sequence: int | None,
    source_time: int | None,
    evaluation_time: int | None,
    occurrence_identity: _MarketOccurrenceId | None,
    halted: bool,
    baseline_required: bool,
    exhausted: bool,
    last_primary: _ReportedPrice | None,
    hard_bid_identity: _MarketOccurrenceId | None,
    hard_bid_source_time: int | None,
    trade_identity: _MarketOccurrenceId | None,
    trade_source_time: int | None,
    trail_bid_identity: _MarketOccurrenceId | None,
    trail_bid_source_time: int | None,
    exit_provenance: bytes,
) -> PositionProtectionState:
    return _rebuild_state(
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
        occurrence_epoch,
        committed_epoch,
        expected_epoch,
        source_sequence,
        source_time,
        evaluation_time,
        occurrence_identity,
        halted,
        baseline_required,
        exhausted,
        last_primary,
        hard_bid_identity,
        hard_bid_source_time,
        trade_identity,
        trade_source_time,
        trail_bid_identity,
        trail_bid_source_time,
        exit_provenance,
    )


def _reserve_market_occurrence(
    state: PositionProtectionState,
    occurrence: MarketOccurrence,
    source_time: int,
    evaluation_time: int,
) -> PositionProtectionState:
    return _market_state(
        state,
        state.policy,
        state.high_watermark,
        state.trail,
        occurrence.market_epoch,
        state._market_committed_epoch,
        state._market_expected_epoch,
        occurrence.source_sequence,
        source_time,
        evaluation_time,
        occurrence.occurrence_id,
        state._market_halted,
        state._market_baseline_required,
        state._market_exhausted,
        state._market_last_primary,
        state._hard_bid_identity,
        state._hard_bid_source_time,
        state._trade_identity,
        state._trade_source_time,
        state._trail_bid_identity,
        state._trail_bid_source_time,
        state._exit_provenance,
    )


def _restrict_market_state(
    state: PositionProtectionState,
    committed_epoch: int | None,
    expected_epoch: int | None,
    halted: bool,
    baseline_required: bool,
    exhausted: bool,
) -> PositionProtectionState:
    return _market_state(
        state,
        state.policy,
        state.high_watermark,
        state.trail,
        state._market_occurrence_epoch,
        committed_epoch,
        expected_epoch,
        state._market_source_sequence,
        state._market_source_time,
        state._market_evaluation_time,
        state._market_occurrence_identity,
        halted,
        baseline_required,
        exhausted,
        state._market_last_primary,
        None,
        None,
        None,
        None,
        None,
        None,
        state._exit_provenance,
    )


def _exhaust_market_state(
    state: PositionProtectionState,
    committed_epoch: int | None,
    halted: bool,
) -> PositionProtectionState:
    return _restrict_market_state(
        state,
        committed_epoch,
        None,
        halted,
        True,
        True,
    )


def _enter_market_baseline(
    state: PositionProtectionState,
    halted: bool,
) -> PositionProtectionState:
    if state._market_exhausted:
        return state
    if state._market_baseline_required:
        return _restrict_market_state(
            state,
            state._market_committed_epoch,
            state._market_expected_epoch,
            halted,
            True,
            False,
        )
    committed_epoch = state._market_committed_epoch
    if committed_epoch is None:
        return _restrict_market_state(
            state,
            None,
            0,
            halted,
            True,
            False,
        )
    expected_epoch = _next_market_epoch(committed_epoch)
    if expected_epoch is None:
        return _exhaust_market_state(state, committed_epoch, halted)
    return _restrict_market_state(
        state,
        committed_epoch,
        expected_epoch,
        halted,
        True,
        False,
    )


def _current_market_coordinate_matches(
    state: PositionProtectionState,
    occurrence: MarketOccurrence,
) -> bool:
    if (
        state._market_occurrence_identity is None
        or state._market_occurrence_epoch != occurrence.market_epoch
    ):
        return False
    if state.mandate.evidence_policy.sequence_mode is MarketSequenceMode.SEQUENCED:
        return state._market_source_sequence == occurrence.source_sequence
    return state._market_source_time == occurrence.source_time


def _market_occurrence_is_authentic(occurrence: MarketOccurrence) -> bool:
    if not _market_generation_is_authentic(occurrence.stream_generation):
        return False
    if not _market_occurrence_identity_is_authentic(occurrence.occurrence_id):
        return False
    return (
        occurrence.occurrence_id._bytes
        == _sha256(
            _market_occurrence_preimage(
                source_id=occurrence.source_id.value,
                position_scope=occurrence.position_scope,
                session_id=occurrence.session_id.value,
                stream_generation=occurrence.stream_generation._bytes,
                market_epoch=occurrence.market_epoch,
                source_sequence=occurrence.source_sequence,
                source_time=occurrence.source_time,
                kind=occurrence.kind.value,
                best_bid=occurrence.best_bid,
                best_ask=occurrence.best_ask,
                trade_price=occurrence.trade_price,
                atr_distance=occurrence.atr_distance,
                structure_trail=occurrence.structure_trail,
                halted=occurrence.halted,
            )
        ).digest()
    )


def _market_route_matches(
    state: PositionProtectionState,
    occurrence: MarketOccurrence,
) -> bool:
    if not _market_occurrence_is_authentic(occurrence):
        return False
    if (
        occurrence.position_scope != state.mandate.position_scope
        or occurrence.source_id != state.mandate.evidence_policy.source_id
        or occurrence.stream_generation
        != state.mandate.evidence_policy.stream_generation
        or occurrence.session_id != state.mandate.session_id
    ):
        return False
    if state.mandate.evidence_policy.sequence_mode is MarketSequenceMode.SEQUENCED:
        return occurrence.source_sequence is not None
    return occurrence.source_sequence is None


def _market_primary(
    state: PositionProtectionState,
    occurrence: MarketOccurrence,
) -> _ReportedPrice | None:
    if occurrence.kind is MarketKind.BEST_BID:
        if (
            type(occurrence.best_bid) is not _ReportedPrice
            or type(occurrence.best_ask) is not _ReportedPrice
            or not _market_price_matches(occurrence.best_bid, state.mandate.tick)
            or not _market_price_matches(occurrence.best_ask, state.mandate.tick)
            or occurrence.best_bid.exact_value > occurrence.best_ask.exact_value
        ):
            return None
        return occurrence.best_bid
    if type(occurrence.trade_price) is not _ReportedPrice or not _market_price_matches(
        occurrence.trade_price, state.mandate.tick
    ):
        return None
    return occurrence.trade_price


def _tightened_trail(
    state: PositionProtectionState,
    occurrence: MarketOccurrence,
    high_watermark: _ReportedPrice,
) -> _ReportedPrice:
    candidate = _upward_price(
        high_watermark.exact_value * (1 - state.mandate.percent_trail_fraction),
        state.mandate.tick,
    )
    if (
        type(occurrence.atr_distance) is _ReportedPrice
        and _market_price_matches(occurrence.atr_distance, state.mandate.tick)
        and high_watermark.exact_value
        > occurrence.atr_distance.exact_value * state.mandate.atr_multiple
    ):
        atr_candidate = _upward_price(
            high_watermark.exact_value
            - occurrence.atr_distance.exact_value * state.mandate.atr_multiple,
            state.mandate.tick,
        )
        if atr_candidate.exact_value > candidate.exact_value:
            candidate = atr_candidate
    if (
        type(occurrence.structure_trail) is _ReportedPrice
        and _market_price_matches(occurrence.structure_trail, state.mandate.tick)
        and occurrence.structure_trail.exact_value <= high_watermark.exact_value
        and occurrence.structure_trail.exact_value > candidate.exact_value
    ):
        candidate = occurrence.structure_trail
    if state.trail is not None and state.trail.exact_value > candidate.exact_value:
        return state.trail
    return candidate


def _state_after_market_baseline(
    state: PositionProtectionState,
    occurrence: MarketOccurrence,
    primary: _ReportedPrice,
) -> PositionProtectionState:
    policy = state.policy
    high_watermark = state.high_watermark
    trail = state.trail
    if (
        policy is ProtectionPolicy.FLOOR_ONLY
        and state.activation_price is not None
        and primary.exact_value >= state.activation_price.exact_value
    ):
        policy = ProtectionPolicy.TRAIL_ACTIVE
        high_watermark = primary
    if policy is ProtectionPolicy.TRAIL_ACTIVE or high_watermark is not None:
        if high_watermark is None or primary.exact_value > high_watermark.exact_value:
            high_watermark = primary
        if high_watermark is not None:
            trail = _tightened_trail(state, occurrence, high_watermark)
    return _market_state(
        state,
        policy,
        high_watermark,
        trail,
        occurrence.market_epoch,
        occurrence.market_epoch,
        None,
        state._market_source_sequence,
        state._market_source_time,
        state._market_evaluation_time,
        occurrence.occurrence_id,
        False,
        False,
        False,
        primary,
        None,
        None,
        None,
        None,
        None,
        None,
        state._exit_provenance,
    )


def _state_after_eligible_market(
    state: PositionProtectionState,
    occurrence: MarketOccurrence,
    primary: _ReportedPrice,
) -> PositionProtectionState:
    identity = occurrence.occurrence_id
    policy = state.policy
    high_watermark = state.high_watermark
    trail = state.trail
    hard_bid_identity = state._hard_bid_identity
    hard_bid_source_time = state._hard_bid_source_time
    trade_identity = state._trade_identity
    trade_source_time = state._trade_source_time
    trail_bid_identity = state._trail_bid_identity
    trail_bid_source_time = state._trail_bid_source_time
    exit_provenance = state._exit_provenance
    hard_triggered = False
    counterpart_identity = None
    trigger = state.armed_hard_bail_trigger
    below_hard = trigger is not None and primary.exact_value <= trigger.exact_value

    if occurrence.kind is MarketKind.TRADE:
        if below_hard:
            if (
                hard_bid_identity is not None
                and hard_bid_source_time is not None
                and hard_bid_identity != identity
                and occurrence.source_time - hard_bid_source_time
                <= state.mandate.evidence_policy.corroboration_window
            ):
                hard_triggered = True
                counterpart_identity = hard_bid_identity
            trade_identity = identity
            trade_source_time = occurrence.source_time
        else:
            trade_identity = None
            trade_source_time = None
        hard_bid_identity = None
        hard_bid_source_time = None
        trail_bid_identity = None
        trail_bid_source_time = None
    else:
        if below_hard:
            if (
                trade_identity is not None
                and trade_source_time is not None
                and trade_identity != identity
                and occurrence.source_time - trade_source_time
                <= state.mandate.evidence_policy.corroboration_window
            ):
                hard_triggered = True
                counterpart_identity = trade_identity
            elif hard_bid_identity is not None and hard_bid_identity != identity:
                hard_triggered = True
                counterpart_identity = hard_bid_identity
            hard_bid_identity = identity
            hard_bid_source_time = occurrence.source_time
        else:
            hard_bid_identity = None
            hard_bid_source_time = None
            trade_identity = None
            trade_source_time = None

    if hard_triggered:
        policy = ProtectionPolicy.HARD_BAIL
        if counterpart_identity is None:
            raise TypeError("hard-bail counterpart identity is required")
        if not _real_exit(exit_provenance):
            exit_provenance = _commit_parts(
                b"execution-core/protection-hard-exit/v1",
                counterpart_identity._bytes,
                identity._bytes,
            )
        trail_bid_identity = None
        trail_bid_source_time = None
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
            if high_watermark is None:
                raise TypeError("active high watermark is required")
            previous_trail = trail
            trail = _tightened_trail(state, occurrence, high_watermark)
            if previous_trail is None or trail.exact_value > previous_trail.exact_value:
                trail_bid_identity = None
                trail_bid_source_time = None
            if primary.exact_value <= trail.exact_value:
                if trail_bid_identity is not None and trail_bid_identity != identity:
                    policy = ProtectionPolicy.EXIT_NORMAL
                    exit_provenance = _commit_parts(
                        b"execution-core/protection-normal-exit/v1",
                        trail_bid_identity._bytes,
                        identity._bytes,
                    )
                trail_bid_identity = identity
                trail_bid_source_time = occurrence.source_time
            else:
                trail_bid_identity = None
                trail_bid_source_time = None

    return _market_state(
        state,
        policy,
        high_watermark,
        trail,
        occurrence.market_epoch,
        state._market_committed_epoch,
        state._market_expected_epoch,
        state._market_source_sequence,
        state._market_source_time,
        state._market_evaluation_time,
        identity,
        False,
        False,
        False,
        primary,
        hard_bid_identity,
        hard_bid_source_time,
        trade_identity,
        trade_source_time,
        trail_bid_identity,
        trail_bid_source_time,
        exit_provenance,
    )


def _stale_or_refused_exhausted_market(
    state: PositionProtectionState,
    occurrence: MarketOccurrence,
) -> ProtectionDisposition:
    retained_epoch = state._market_occurrence_epoch
    if retained_epoch is not None and occurrence.market_epoch < retained_epoch:
        return ProtectionDisposition.STALE
    if retained_epoch == occurrence.market_epoch:
        if state.mandate.evidence_policy.sequence_mode is MarketSequenceMode.SEQUENCED:
            if (
                state._market_source_sequence is not None
                and occurrence.source_sequence is not None
                and occurrence.source_sequence < state._market_source_sequence
            ):
                return ProtectionDisposition.STALE
        elif (
            state._market_source_time is not None
            and occurrence.source_time < state._market_source_time
        ):
            return ProtectionDisposition.STALE
    return ProtectionDisposition.REFUSED


def _reduce_market_occurrence(
    state: PositionProtectionState,
    projection: ProtectionVenueProjection,
    occurrence: MarketOccurrence,
) -> ProtectionTransition:
    if not _market_projection_is_current(state, projection):
        return ProtectionTransition(
            state,
            ProtectionDisposition.REFUSED,
            None,
            None,
        )
    if not _market_route_matches(state, occurrence):
        return ProtectionTransition(
            state,
            ProtectionDisposition.REFUSED,
            None,
            None,
        )

    current_coordinate = _current_market_coordinate_matches(state, occurrence)
    if current_coordinate:
        if state._market_occurrence_identity == occurrence.occurrence_id:
            return ProtectionTransition(
                state,
                ProtectionDisposition.EXACT_REPLAY,
                None,
                None,
            )
        if state._market_baseline_required:
            return ProtectionTransition(
                state,
                ProtectionDisposition.REFUSED,
                None,
                None,
            )
        conflicted = _enter_market_baseline(state, state._market_halted)
        conflict_alert = (
            ProtectionAlert.MARKET_COORDINATE_EXHAUSTED
            if conflicted._market_exhausted
            else ProtectionAlert.MARKET_BASELINE_REQUIRED
        )
        return ProtectionTransition(
            conflicted,
            ProtectionDisposition.APPLIED,
            None,
            conflict_alert,
        )

    if state._market_exhausted:
        return ProtectionTransition(
            state,
            _stale_or_refused_exhausted_market(state, occurrence),
            None,
            None,
        )

    admitted_epoch = (
        state._market_expected_epoch
        if state._market_baseline_required
        else state._market_committed_epoch
    )
    if admitted_epoch is None:
        return ProtectionTransition(
            state,
            ProtectionDisposition.REFUSED,
            None,
            None,
        )
    if occurrence.market_epoch < admitted_epoch:
        return ProtectionTransition(
            state,
            ProtectionDisposition.STALE,
            None,
            None,
        )
    if occurrence.market_epoch > admitted_epoch:
        return ProtectionTransition(
            state,
            ProtectionDisposition.REFUSED,
            None,
            None,
        )

    sequenced = (
        state.mandate.evidence_policy.sequence_mode is MarketSequenceMode.SEQUENCED
    )
    if sequenced:
        if occurrence.source_sequence is None:
            return ProtectionTransition(
                state,
                ProtectionDisposition.REFUSED,
                None,
                None,
            )
        if (
            state._market_source_sequence is not None
            and occurrence.source_sequence <= state._market_source_sequence
        ):
            return ProtectionTransition(
                state,
                ProtectionDisposition.STALE,
                None,
                None,
            )
        strict_coordinate = occurrence.source_sequence
    else:
        if (
            state._market_source_time is not None
            and occurrence.source_time <= state._market_source_time
        ):
            return ProtectionTransition(
                state,
                ProtectionDisposition.STALE,
                None,
                None,
            )
        strict_coordinate = occurrence.source_time

    source_time_regressed = (
        sequenced
        and state._market_source_time is not None
        and occurrence.source_time < state._market_source_time
    )
    evaluation_time_regressed = (
        state._market_evaluation_time is not None
        and occurrence.evaluation_time < state._market_evaluation_time
    )
    retained_source_time = (
        state._market_source_time if source_time_regressed else occurrence.source_time
    )
    if retained_source_time is None:
        raise TypeError("retained source time is required")
    retained_evaluation_time = (
        state._market_evaluation_time
        if evaluation_time_regressed
        else occurrence.evaluation_time
    )
    if retained_evaluation_time is None:
        raise TypeError("retained evaluation time is required")
    reserved = _reserve_market_occurrence(
        state,
        occurrence,
        retained_source_time,
        retained_evaluation_time,
    )

    committing_epoch_maximum = (
        state._market_baseline_required
        and occurrence.market_epoch == 18446744073709551615
    )
    if strict_coordinate == 18446744073709551615 or committing_epoch_maximum:
        committed_epoch = (
            occurrence.market_epoch
            if committing_epoch_maximum
            else state._market_committed_epoch
        )
        exhausted = _exhaust_market_state(
            reserved,
            committed_epoch,
            reserved._market_halted,
        )
        return ProtectionTransition(
            exhausted,
            ProtectionDisposition.APPLIED,
            None,
            ProtectionAlert.MARKET_COORDINATE_EXHAUSTED,
        )

    if source_time_regressed:
        restricted = _enter_market_baseline(reserved, reserved._market_halted)
        restriction_alert = (
            ProtectionAlert.MARKET_COORDINATE_EXHAUSTED
            if restricted._market_exhausted
            else (
                ProtectionAlert.MARKET_BASELINE_REQUIRED
                if not state._market_baseline_required
                else None
            )
        )
        return ProtectionTransition(
            restricted,
            ProtectionDisposition.APPLIED,
            None,
            restriction_alert,
        )

    if occurrence.halted:
        halted_state = _enter_market_baseline(reserved, True)
        halt_alert = (
            ProtectionAlert.MARKET_COORDINATE_EXHAUSTED
            if halted_state._market_exhausted
            else (
                ProtectionAlert.MARKET_BASELINE_REQUIRED
                if not state._market_baseline_required
                else None
            )
        )
        return ProtectionTransition(
            halted_state,
            ProtectionDisposition.APPLIED,
            None,
            halt_alert,
        )

    primary = _market_primary(state, occurrence)
    context_is_eligible = (
        primary is not None
        and not evaluation_time_regressed
        and occurrence.source_time <= occurrence.evaluation_time
        and occurrence.evaluation_time - occurrence.source_time
        <= state.mandate.evidence_policy.max_age
        and state.formula_available
        and state.policy is not ProtectionPolicy.FLAT
        and state.raw_quantity > 0
        and state.raw_quantity <= state.mandate.maximum_quantity.value
    )
    if (
        context_is_eligible
        and not state._market_baseline_required
        and primary is not None
        and not _step_is_eligible(state, primary)
    ):
        context_is_eligible = False
    if (
        not context_is_eligible
        or primary is None
        or (
            state._market_baseline_required
            and occurrence.kind is not MarketKind.BEST_BID
        )
    ):
        inert = _restrict_market_state(
            reserved,
            reserved._market_committed_epoch,
            reserved._market_expected_epoch,
            reserved._market_halted,
            reserved._market_baseline_required,
            False,
        )
        return ProtectionTransition(
            inert,
            ProtectionDisposition.APPLIED,
            None,
            None,
        )

    if state._market_baseline_required:
        baseline = _state_after_market_baseline(reserved, occurrence, primary)
        return ProtectionTransition(
            baseline,
            ProtectionDisposition.APPLIED,
            None,
            None,
        )

    applied = _state_after_eligible_market(reserved, occurrence, primary)
    return ProtectionTransition(
        applied,
        ProtectionDisposition.APPLIED,
        _goal_for_state(applied, projection),
        None,
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
        proof.execution_checkpoint.registry_count,
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
        proof.execution_checkpoint.registry_count,
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
) -> ProtectionTransition:
    if type(state) is not PositionProtectionState:
        raise TypeError("state must be PositionProtectionState")
    if type(projection) is not ProtectionVenueProjection:
        raise TypeError("projection must be ProtectionVenueProjection")
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
    return ProtectionTransition(
        next_state,
        ProtectionDisposition.APPLIED,
        _goal_for_state(next_state, projection),
        alert,
    )


def reduce_position_protection_market(
    state: PositionProtectionState,
    projection: ProtectionVenueProjection,
    occurrence: MarketOccurrence,
) -> ProtectionTransition:
    if type(state) is not PositionProtectionState:
        raise TypeError("state must be PositionProtectionState")
    if type(projection) is not ProtectionVenueProjection:
        raise TypeError("projection must be ProtectionVenueProjection")
    if type(occurrence) is not MarketOccurrence:
        raise TypeError("occurrence must be MarketOccurrence")
    if not _state_is_authentic(state):
        return ProtectionTransition(state, ProtectionDisposition.REFUSED, None, None)
    return _reduce_market_occurrence(state, projection, occurrence)


def invalidate_position_protection_market(
    state: PositionProtectionState,
    projection: ProtectionVenueProjection,
) -> ProtectionTransition:
    if type(state) is not PositionProtectionState:
        raise TypeError("state must be PositionProtectionState")
    if type(projection) is not ProtectionVenueProjection:
        raise TypeError("projection must be ProtectionVenueProjection")
    if not _state_is_authentic(state):
        return ProtectionTransition(state, ProtectionDisposition.REFUSED, None, None)
    if not _market_projection_is_current(state, projection):
        return ProtectionTransition(state, ProtectionDisposition.REFUSED, None, None)
    if state._market_baseline_required or state._market_exhausted:
        return ProtectionTransition(
            state,
            ProtectionDisposition.EXACT_REPLAY,
            None,
            None,
        )
    invalidated = _enter_market_baseline(state, state._market_halted)
    invalidation_alert = (
        ProtectionAlert.MARKET_COORDINATE_EXHAUSTED
        if invalidated._market_exhausted
        else ProtectionAlert.MARKET_BASELINE_REQUIRED
    )
    return ProtectionTransition(
        invalidated,
        ProtectionDisposition.APPLIED,
        None,
        invalidation_alert,
    )


__all__ = (
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
)
