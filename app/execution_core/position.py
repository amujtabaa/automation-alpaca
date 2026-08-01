"""Pure fill-family position and long-basis transition semantics.

The reducer in this module consumes only explicit immutable inputs.  It does no
I/O and deliberately keeps the ordered slow fold separate from the fast
transition used to accept broker execution truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum, Flag, auto
from fractions import Fraction

from .fills import (
    BrokerExecutionFact,
    BrokerFillFact,
    BrokerTradeBustFact,
    BrokerTradeCorrectFact,
    ExecutionAuthority,
    ExecutionSide,
    FirstObservationClassification,
    PositionScope,
    RootHead,
    RootHeadIndex,
    SeenFact,
    SeenFactIndex,
    _PersistentSequence,
    _SnapshotBinding,
    _commit_parts,
    _commit_root_fill_key,
    _commit_source_event_id,
    _encode_fraction,
    _encode_int,
    _encode_position_scope,
    _encode_reported_price,
    _encode_root_fill_key,
)
from .identity import ExecutionFactKey, RootFillKey, SourceEventId, SymbolId
from .values import ExactBasis, Quantity, ReportedPrice


class BasisAuthority(Enum):
    """Whether the stored long basis may currently drive decisions."""

    AVAILABLE = "AVAILABLE"
    BASIS_RECONCILIATION_PENDING = "BASIS_RECONCILIATION_PENDING"


class PositionIntegrity(Flag):
    """Monotonic, composable integrity restrictions for one position."""

    CONSISTENT = 0
    EXECUTION_FACT_CONFLICT = auto()
    EXECUTION_RECONCILIATION_REQUIRED = auto()
    OVERFILL_QUARANTINE = auto()


class TransitionDisposition(Enum):
    """Immediate classification of one fact-application attempt."""

    APPLIED = "APPLIED"
    EXACT_REPLAY = "EXACT_REPLAY"
    FACT_CONFLICT = "FACT_CONFLICT"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class BasisCandidateStatus(Enum):
    """Result of the separately invoked immutable-snapshot ordered fold."""

    DERIVED = "DERIVED"
    INCOMPATIBLE_PRICE_METADATA = "INCOMPATIBLE_PRICE_METADATA"
    SNAPSHOT_INCONSISTENT = "SNAPSHOT_INCONSISTENT"


@dataclass(frozen=True, slots=True)
class FoldInput:
    """Exact state and immutable proof immediately before the tail root."""

    raw_quantity: int
    cost_basis: ExactBasis
    price_metadata: ReportedPrice | None
    position_scope: PositionScope | None = None
    tail_root_key: RootFillKey | None = None
    prefix_count: int = -1
    prefix_heads_commitment: bytes = b""

    def __post_init__(self) -> None:
        _require_signed_integer("raw_quantity", self.raw_quantity)
        if not isinstance(self.cost_basis, ExactBasis):
            raise TypeError("cost_basis must be ExactBasis")
        if self.price_metadata is not None and not isinstance(
            self.price_metadata, ReportedPrice
        ):
            raise TypeError("price_metadata must be ReportedPrice or None")
        if self.raw_quantity <= 0 and self.cost_basis.value != 0:
            raise ValueError("a non-positive fold quantity cannot carry long basis")
        if self.position_scope is not None and not isinstance(
            self.position_scope, PositionScope
        ):
            raise TypeError("position_scope must be PositionScope or None")
        if self.tail_root_key is not None and not isinstance(
            self.tail_root_key, RootFillKey
        ):
            raise TypeError("tail_root_key must be RootFillKey or None")
        _require_signed_integer("prefix_count", self.prefix_count)
        if not isinstance(self.prefix_heads_commitment, bytes):
            raise TypeError("prefix_heads_commitment must be bytes")
        proof_parts = (
            self.position_scope is not None,
            self.tail_root_key is not None,
            self.prefix_count >= 0,
            bool(self.prefix_heads_commitment),
        )
        if any(proof_parts) and not all(proof_parts):
            raise ValueError("tail fold proof fields must be present together")

    @property
    def is_bound(self) -> bool:
        return (
            self.position_scope is not None
            and self.tail_root_key is not None
            and self.prefix_count >= 0
            and bool(self.prefix_heads_commitment)
        )

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/tail-fold-input/v1",
            _encode_int(self.raw_quantity),
            _encode_fraction(self.cost_basis.value),
            _encode_reported_price(self.price_metadata),
            (
                _encode_position_scope(self.position_scope)
                if self.position_scope is not None
                else b""
            ),
            (
                _encode_root_fill_key(self.tail_root_key)
                if self.tail_root_key is not None
                else b""
            ),
            _encode_int(self.prefix_count),
            self.prefix_heads_commitment,
        )


@dataclass(frozen=True, slots=True)
class PositionState:
    """Immutable position state bound to exact scope and persistent head order."""

    _scope: PositionScope
    raw_quantity: int
    basis_authority: BasisAuthority
    cost_basis: ExactBasis | None
    _root_fill_sequence: _PersistentSequence[RootFillKey]
    _effective_head_ids: _PersistentSequence[SourceEventId]
    basis_price_metadata: ReportedPrice | None
    tail_fold_input: FoldInput | None
    integrity_floor: PositionIntegrity = field(
        default=PositionIntegrity.CONSISTENT,
        compare=False,
    )
    _binding: _SnapshotBinding | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self._scope, PositionScope):
            raise TypeError("_scope must be PositionScope")
        _require_signed_integer("raw_quantity", self.raw_quantity)
        if not isinstance(self.basis_authority, BasisAuthority):
            raise TypeError("basis_authority must be BasisAuthority")
        if not isinstance(self._root_fill_sequence, _PersistentSequence):
            raise TypeError("_root_fill_sequence must be persistent")
        if not isinstance(self._effective_head_ids, _PersistentSequence):
            raise TypeError("_effective_head_ids must be persistent")
        if self._root_fill_sequence.length != self._effective_head_ids.length:
            raise ValueError("root sequence and effective heads must remain aligned")
        if self.basis_price_metadata is not None and not isinstance(
            self.basis_price_metadata, ReportedPrice
        ):
            raise TypeError("basis_price_metadata must be ReportedPrice or None")
        if self.tail_fold_input is not None and not isinstance(
            self.tail_fold_input, FoldInput
        ):
            raise TypeError("tail_fold_input must be FoldInput or None")
        if not isinstance(self.integrity_floor, PositionIntegrity):
            raise TypeError("integrity_floor must be PositionIntegrity")
        if self.basis_authority is BasisAuthority.AVAILABLE:
            if not isinstance(self.cost_basis, ExactBasis):
                raise ValueError("available basis requires an exact cost basis")
            if self.raw_quantity <= 0 and self.cost_basis.value != 0:
                raise ValueError("a non-positive position cannot carry long basis")
        elif (
            self.cost_basis is not None
            or self.basis_price_metadata is not None
            or self.tail_fold_input is not None
        ):
            raise ValueError("pending basis cannot retain any basis-derived cache")

    @classmethod
    def from_materialized(
        cls,
        *,
        scope: PositionScope,
        raw_quantity: int,
        basis_authority: BasisAuthority,
        cost_basis: ExactBasis | None,
        root_fill_sequence: tuple[RootFillKey, ...],
        effective_head_ids: tuple[SourceEventId, ...],
        basis_price_metadata: ReportedPrice | None,
        tail_fold_input: FoldInput | None,
        integrity_floor: PositionIntegrity = PositionIntegrity.CONSISTENT,
    ) -> PositionState:
        """Build an unbound snapshot for explicit validation/hydration only."""

        if not isinstance(root_fill_sequence, tuple):
            raise TypeError("root_fill_sequence must be a tuple")
        if not isinstance(effective_head_ids, tuple):
            raise TypeError("effective_head_ids must be a tuple")
        if not all(isinstance(key, RootFillKey) for key in root_fill_sequence):
            raise TypeError("root_fill_sequence entries must be RootFillKey")
        if not all(
            isinstance(event_id, SourceEventId) for event_id in effective_head_ids
        ):
            raise TypeError("effective_head_ids entries must be SourceEventId")
        if len(set(root_fill_sequence)) != len(root_fill_sequence):
            raise ValueError("root_fill_sequence cannot contain duplicate roots")
        return cls(
            _scope=scope,
            raw_quantity=raw_quantity,
            basis_authority=basis_authority,
            cost_basis=cost_basis,
            _root_fill_sequence=_PersistentSequence.from_values(
                root_fill_sequence,
                _commit_root_fill_key,
            ),
            _effective_head_ids=_PersistentSequence.from_values(
                effective_head_ids,
                _commit_source_event_id,
            ),
            basis_price_metadata=basis_price_metadata,
            tail_fold_input=tail_fold_input,
            integrity_floor=integrity_floor,
        )

    @classmethod
    def flat(cls, scope: PositionScope) -> PositionState:
        """Construct the unique empty, basis-available state for exact scope."""

        if not isinstance(scope, PositionScope):
            raise TypeError("scope must be PositionScope")
        zero_basis = ExactBasis(Fraction(0))
        return cls(
            _scope=scope,
            raw_quantity=0,
            basis_authority=BasisAuthority.AVAILABLE,
            cost_basis=zero_basis,
            _root_fill_sequence=_PersistentSequence.empty(),
            _effective_head_ids=_PersistentSequence.empty(),
            basis_price_metadata=None,
            tail_fold_input=None,
        )

    @property
    def scope(self) -> PositionScope:
        return self._scope

    @property
    def symbol_id(self) -> SymbolId:
        return self._scope.symbol_id

    @property
    def root_count(self) -> int:
        return self._root_fill_sequence.length

    @property
    def root_fill_sequence(self) -> tuple[RootFillKey, ...]:
        """Materialize root order only for reporting and slow verification."""

        return self._root_fill_sequence.to_tuple()

    @property
    def effective_head_ids(self) -> tuple[SourceEventId, ...]:
        """Materialize current head IDs only for reporting and slow verification."""

        return self._effective_head_ids.to_tuple()

    @property
    def commitment(self) -> bytes:
        basis = self.cost_basis.value if self.cost_basis is not None else None
        tail_commitment = (
            _commit_parts(b"execution-core/position-tail/absent/v1")
            if self.tail_fold_input is None
            else _commit_parts(
                b"execution-core/position-tail/present/v1",
                self.tail_fold_input.commitment,
            )
        )
        return _commit_parts(
            b"execution-core/position-state/v2",
            _encode_position_scope(self.scope),
            _encode_int(self.raw_quantity),
            self.basis_authority.value.encode("ascii"),
            _encode_fraction(basis) if basis is not None else b"",
            self._root_fill_sequence.commitment,
            self._effective_head_ids.commitment,
            _encode_reported_price(self.basis_price_metadata),
            tail_commitment,
            _encode_int(self.integrity_floor.value),
        )

    @property
    def binding(self) -> _SnapshotBinding | None:
        return self._binding

    def _with_binding(self, binding: _SnapshotBinding) -> PositionState:
        if not isinstance(binding, _SnapshotBinding):
            raise TypeError("binding must be _SnapshotBinding")
        return replace(self, _binding=binding)

    @property
    def average_price(self) -> Fraction | None:
        """Return exact long average price only while basis is authoritative."""

        if (
            self.basis_authority is not BasisAuthority.AVAILABLE
            or self.cost_basis is None
            or self.raw_quantity <= 0
        ):
            return None
        return self.cost_basis.value / self.raw_quantity

    @property
    def authorized_residual_sell(self) -> Quantity:
        """Return the authority cap without hiding a negative raw position."""

        return Quantity(max(self.raw_quantity, 0))


@dataclass(frozen=True, slots=True)
class ExecutionSnapshot:
    """One coherently bound immutable execution-kernel high-water."""

    position: PositionState
    integrity: PositionIntegrity
    root_heads: RootHeadIndex
    seen_facts: SeenFactIndex

    def __post_init__(self) -> None:
        if not _snapshot_is_coherent(
            self.position,
            self.integrity,
            self.root_heads,
            self.seen_facts,
        ):
            raise ValueError("execution snapshot components are not coherently bound")

    @classmethod
    def flat(cls, scope: PositionScope) -> ExecutionSnapshot:
        """Create the only admitted empty snapshot for exact position scope."""

        return _bind_components(
            PositionState.flat(scope),
            PositionIntegrity.CONSISTENT,
            RootHeadIndex.empty(scope),
            SeenFactIndex.empty(),
        )

    @classmethod
    def bind_verified(
        cls,
        position: PositionState,
        integrity: PositionIntegrity,
        root_heads: RootHeadIndex,
        seen_facts: SeenFactIndex,
    ) -> ExecutionSnapshot:
        """Fully validate and bind a materialized hydration/audit snapshot."""

        if not isinstance(position, PositionState):
            raise TypeError("position must be PositionState")
        if not isinstance(integrity, PositionIntegrity):
            raise TypeError("integrity must be PositionIntegrity")
        if not isinstance(root_heads, RootHeadIndex):
            raise TypeError("root_heads must be RootHeadIndex")
        if not isinstance(seen_facts, SeenFactIndex):
            raise TypeError("seen_facts must be SeenFactIndex")
        if root_heads.position_scope != position.scope:
            raise ValueError("root index and position must share exact scope")
        if root_heads.signed_quantity != position.raw_quantity:
            raise ValueError("root economics and position quantity disagree")
        if position.root_fill_sequence != root_heads._root_sequence.to_tuple():
            raise ValueError("position root order and root index disagree")
        if position.effective_head_ids != root_heads._head_sequence.to_tuple():
            raise ValueError("position head IDs and root index disagree")
        for head in root_heads.entries:
            if head.scope.position_scope != position.scope:
                raise ValueError("root head is outside exact position scope")
            if head.authority is not ExecutionAuthority.BROKER_AUTHORITATIVE:
                raise ValueError(
                    "public hydration admits broker-authoritative roots only"
                )

        replayed = _replay_hydration_snapshot(position.scope, seen_facts)
        _require_hydration_match(position, root_heads, replayed)
        required_integrity = replayed.integrity | position.integrity_floor
        if integrity & required_integrity != required_integrity:
            raise ValueError("supplied integrity clears historical evidence")
        rebound_position = replace(
            position,
            _root_fill_sequence=root_heads._root_sequence,
            _effective_head_ids=root_heads._head_sequence,
            _binding=None,
        )
        return _bind_components(
            rebound_position,
            integrity,
            root_heads,
            seen_facts,
        )


@dataclass(frozen=True, slots=True)
class ExecutionTransition:
    """Complete deterministic output of one fast fact application."""

    position: PositionState
    integrity: PositionIntegrity
    root_heads: RootHeadIndex
    seen_facts: SeenFactIndex
    quantity_delta: int
    basis_delta: Fraction | None
    disposition: TransitionDisposition
    original_classification: FirstObservationClassification


@dataclass(frozen=True, slots=True)
class BasisCandidate:
    """Uncommitted result of an explicit immutable-snapshot ordered fold."""

    status: BasisCandidateStatus
    raw_quantity: int
    cost_basis: ExactBasis | None
    root_fill_sequence: tuple[RootFillKey, ...]
    effective_head_ids: tuple[SourceEventId, ...]


def _require_signed_integer(name: str, value: object) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact integer")


def _fold_one(
    raw_quantity: int,
    cost_basis: Fraction,
    side: ExecutionSide,
    absolute_quantity: int,
    price: ReportedPrice | None,
) -> tuple[int, Fraction]:
    """Apply one effective root with the accepted exact long-only equations."""

    if side is ExecutionSide.BUY:
        next_quantity = raw_quantity + absolute_quantity
        if raw_quantity >= 0:
            if absolute_quantity:
                if price is None:
                    raise ValueError("positive BUY economics require a price")
                cost_basis += absolute_quantity * price.exact_value
        elif next_quantity > 0:
            if price is None:
                raise ValueError("a covering BUY requires a price")
            cost_basis = next_quantity * price.exact_value
        else:
            cost_basis = Fraction(0)
    else:
        next_quantity = raw_quantity - absolute_quantity
        if raw_quantity > 0 and next_quantity > 0:
            cost_basis *= Fraction(next_quantity, raw_quantity)
        else:
            cost_basis = Fraction(0)
    return next_quantity, cost_basis


def _metadata_accepts(
    reference: ReportedPrice | None,
    reported: ReportedPrice | None,
) -> bool:
    if reported is None:
        return True
    if not reported.is_aligned:
        return False
    return reference is None or reference.is_compatible_with(reported)


def _next_metadata(
    reference: ReportedPrice | None,
    reported: ReportedPrice | None,
    _absolute_quantity: int,
) -> ReportedPrice | None:
    if reference is not None:
        return reference
    return reported


def _snapshot_parts_share_binding(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    *,
    require_integrity: bool,
) -> bool:
    binding = position.binding
    if (
        binding is None
        or root_heads.binding is not binding
        or seen_facts.binding is not binding
    ):
        return False
    if (
        binding.position_scope != position.scope
        or binding.position_commitment != position.commitment
        or binding.root_heads_commitment != root_heads.commitment
        or binding.seen_facts_commitment != seen_facts.commitment
        or root_heads.position_scope != position.scope
        or position.raw_quantity != root_heads.signed_quantity
        or position.root_count != root_heads.count
        or position._root_fill_sequence is not root_heads._root_sequence
        or position._effective_head_ids is not root_heads._head_sequence
    ):
        return False
    return not require_integrity or binding.integrity_bits == integrity.value


def _snapshot_is_coherent(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
) -> bool:
    return _snapshot_parts_share_binding(
        position,
        integrity,
        root_heads,
        seen_facts,
        require_integrity=True,
    )


def _bind_components(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
) -> ExecutionSnapshot:
    if not isinstance(integrity, PositionIntegrity):
        raise TypeError("integrity must be PositionIntegrity")
    if position.integrity_floor & integrity != position.integrity_floor:
        raise ValueError("integrity cannot clear the committed position floor")
    if root_heads.position_scope != position.scope:
        raise ValueError("cannot bind root index outside position scope")
    if (
        position._root_fill_sequence is not root_heads._root_sequence
        or position._effective_head_ids is not root_heads._head_sequence
    ):
        if (
            position._root_fill_sequence.commitment != root_heads.root_order_commitment
            or position._effective_head_ids.commitment != root_heads.head_ids_commitment
        ):
            raise ValueError("cannot bind divergent position/root sequences")
        position = replace(
            position,
            _root_fill_sequence=root_heads._root_sequence,
            _effective_head_ids=root_heads._head_sequence,
            _binding=None,
        )
    if (
        position.raw_quantity != root_heads.signed_quantity
        or position.root_count != root_heads.count
    ):
        raise ValueError("cannot bind structurally divergent position/root state")
    position = replace(
        position,
        integrity_floor=position.integrity_floor | integrity,
        _binding=None,
    )
    snapshot_commitment = _commit_parts(
        b"execution-core/kernel-snapshot/v1",
        _encode_position_scope(position.scope),
        position.commitment,
        root_heads.commitment,
        seen_facts.commitment,
        _encode_int(integrity.value),
    )
    binding = _SnapshotBinding(
        position_scope=position.scope,
        position_commitment=position.commitment,
        root_heads_commitment=root_heads.commitment,
        seen_facts_commitment=seen_facts.commitment,
        integrity_bits=integrity.value,
        snapshot_commitment=snapshot_commitment,
    )
    bound_position = position._with_binding(binding)
    bound_roots = root_heads._with_binding(binding)
    bound_seen = seen_facts._with_binding(binding)
    return ExecutionSnapshot(
        position=bound_position,
        integrity=integrity,
        root_heads=bound_roots,
        seen_facts=bound_seen,
    )


def _observation_matches_head(observation: SeenFact, head: RootHead) -> bool:
    fact = observation.fact
    if (
        fact.root_key != head.root_key
        or fact.scope != head.scope
        or fact.key.source_event_id != head.current_source_event_id
        or fact.kind is not head.kind
    ):
        return False
    if isinstance(fact, BrokerFillFact):
        return fact.quantity == head.quantity and fact.price == head.price
    if isinstance(fact, BrokerTradeCorrectFact):
        return (
            fact.revised_quantity == head.quantity and fact.revised_price == head.price
        )
    return head.quantity.value == 0 and fact.reported_price == head.price


def _fold_ordered_heads(
    root_heads: RootHeadIndex,
) -> tuple[int, ExactBasis] | None:
    raw_quantity = 0
    cost_basis = Fraction(0)
    reference_metadata: ReportedPrice | None = None
    for head in root_heads.entries:
        if head.authority is not ExecutionAuthority.BROKER_AUTHORITATIVE:
            return None
        if not _metadata_accepts(reference_metadata, head.price):
            return None
        reference_metadata = _next_metadata(
            reference_metadata,
            head.price,
            head.quantity.value,
        )
        raw_quantity, cost_basis = _fold_one(
            raw_quantity,
            cost_basis,
            head.scope.side,
            head.quantity.value,
            head.price,
        )
    return raw_quantity, ExactBasis(cost_basis)


def _classification(
    *,
    pending: bool,
    raw_quantity: int,
) -> FirstObservationClassification:
    if pending and raw_quantity < 0:
        return FirstObservationClassification.APPLIED_PENDING_OVERFILL
    if pending:
        return FirstObservationClassification.APPLIED_BASIS_PENDING
    if raw_quantity < 0:
        return FirstObservationClassification.APPLIED_OVERFILL_QUARANTINE
    return FirstObservationClassification.APPLIED_AVAILABLE


def _unchanged_transition(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    *,
    disposition: TransitionDisposition,
    original_classification: FirstObservationClassification,
) -> ExecutionTransition:
    if not _snapshot_is_coherent(position, integrity, root_heads, seen_facts) and (
        _snapshot_parts_share_binding(
            position,
            integrity,
            root_heads,
            seen_facts,
            require_integrity=False,
        )
    ):
        rebound = _bind_components(position, integrity, root_heads, seen_facts)
        position = rebound.position
        root_heads = rebound.root_heads
        seen_facts = rebound.seen_facts
    return ExecutionTransition(
        position=position,
        integrity=integrity,
        root_heads=root_heads,
        seen_facts=seen_facts,
        quantity_delta=0,
        basis_delta=Fraction(0),
        disposition=disposition,
        original_classification=original_classification,
    )


def _reconciliation_transition(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    fact: BrokerExecutionFact,
) -> ExecutionTransition:
    classification = FirstObservationClassification.RECONCILIATION_REQUIRED
    next_integrity = integrity | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    next_seen = seen_facts.add(SeenFact(fact=fact, classification=classification))
    snapshot = _bind_components(position, next_integrity, root_heads, next_seen)
    return ExecutionTransition(
        position=snapshot.position,
        integrity=snapshot.integrity,
        root_heads=snapshot.root_heads,
        seen_facts=snapshot.seen_facts,
        quantity_delta=0,
        basis_delta=Fraction(0),
        disposition=TransitionDisposition.RECONCILIATION_REQUIRED,
        original_classification=classification,
    )


def _incoherent_snapshot_transition(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    fact: BrokerExecutionFact,
) -> ExecutionTransition:
    observation = seen_facts.get(fact.key)
    original_classification = (
        observation.classification
        if observation is not None
        else FirstObservationClassification.RECONCILIATION_REQUIRED
    )
    next_seen = seen_facts
    if observation is None:
        next_seen = seen_facts.add(
            SeenFact(
                fact=fact,
                classification=FirstObservationClassification.RECONCILIATION_REQUIRED,
            )
        )
    trusted_integrity = integrity | position.integrity_floor
    for binding in (
        position.binding,
        root_heads.binding,
        seen_facts.binding,
    ):
        if binding is not None:
            trusted_integrity |= PositionIntegrity(binding.integrity_bits)
    if observation is not None and observation.fact != fact:
        trusted_integrity |= PositionIntegrity.EXECUTION_FACT_CONFLICT
    next_integrity = (
        trusted_integrity | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    next_position = replace(
        position,
        integrity_floor=position.integrity_floor | next_integrity,
        _binding=None,
    )
    return ExecutionTransition(
        position=next_position,
        integrity=next_integrity,
        root_heads=root_heads,
        seen_facts=next_seen,
        quantity_delta=0,
        basis_delta=Fraction(0),
        disposition=TransitionDisposition.RECONCILIATION_REQUIRED,
        original_classification=original_classification,
    )


def _basis_delta(
    old_basis: ExactBasis | None,
    new_basis: ExactBasis | None,
) -> Fraction | None:
    if old_basis is None or new_basis is None:
        return None
    return new_basis.value - old_basis.value


def _apply_root_fill(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    fact: BrokerFillFact,
) -> ExecutionTransition:
    if (
        fact.scope.position_scope != position.scope
        or root_heads.get(fact.root_key) is not None
        or seen_facts.contains_root(fact.root_key)
    ):
        return _reconciliation_transition(
            position, integrity, root_heads, seen_facts, fact
        )

    quantity_delta = (
        fact.quantity.value
        if fact.scope.side is ExecutionSide.BUY
        else -fact.quantity.value
    )
    next_raw_quantity = position.raw_quantity + quantity_delta
    can_update_basis = (
        position.basis_authority is BasisAuthority.AVAILABLE
        and position.cost_basis is not None
        and _metadata_accepts(position.basis_price_metadata, fact.price)
    )
    next_basis: ExactBasis | None = None
    next_metadata: ReportedPrice | None = None
    next_tail_input: FoldInput | None = None
    prefix_heads_commitment = _commit_parts(
        b"execution-core/tail-prefix-heads/v1",
        position._root_fill_sequence.commitment,
        position._effective_head_ids.commitment,
    )
    if can_update_basis:
        assert position.cost_basis is not None
        folded_quantity, folded_basis = _fold_one(
            position.raw_quantity,
            position.cost_basis.value,
            fact.scope.side,
            fact.quantity.value,
            fact.price,
        )
        if folded_quantity == next_raw_quantity:
            next_basis = ExactBasis(folded_basis)
            next_metadata = _next_metadata(
                position.basis_price_metadata,
                fact.price,
                fact.quantity.value,
            )
            next_tail_input = FoldInput(
                raw_quantity=position.raw_quantity,
                cost_basis=position.cost_basis,
                price_metadata=position.basis_price_metadata,
                position_scope=position.scope,
                tail_root_key=fact.root_key,
                prefix_count=position.root_count,
                prefix_heads_commitment=prefix_heads_commitment,
            )

    pending = next_basis is None
    next_head = RootHead(
        root_key=fact.root_key,
        original_sequence=position.root_count,
        scope=fact.scope,
        authority=fact.authority,
        current_source_event_id=fact.key.source_event_id,
        kind=fact.kind,
        quantity=fact.quantity,
        price=fact.price,
        prefix_heads_commitment=(
            prefix_heads_commitment if next_tail_input is not None else b""
        ),
        prefix_proof_commitment=(
            next_tail_input.commitment if next_tail_input is not None else b""
        ),
    )
    next_roots = root_heads.append(next_head)
    next_position = PositionState(
        _scope=position.scope,
        raw_quantity=next_raw_quantity,
        basis_authority=(
            BasisAuthority.BASIS_RECONCILIATION_PENDING
            if pending
            else BasisAuthority.AVAILABLE
        ),
        cost_basis=next_basis,
        _root_fill_sequence=next_roots._root_sequence,
        _effective_head_ids=next_roots._head_sequence,
        basis_price_metadata=next_metadata,
        tail_fold_input=next_tail_input,
    )
    classification = _classification(
        pending=pending,
        raw_quantity=next_raw_quantity,
    )
    next_integrity = integrity
    if next_raw_quantity < 0:
        next_integrity |= PositionIntegrity.OVERFILL_QUARANTINE
    next_seen = seen_facts.add(SeenFact(fact=fact, classification=classification))
    snapshot = _bind_components(
        next_position,
        next_integrity,
        next_roots,
        next_seen,
    )
    return ExecutionTransition(
        position=snapshot.position,
        integrity=snapshot.integrity,
        root_heads=snapshot.root_heads,
        seen_facts=snapshot.seen_facts,
        quantity_delta=quantity_delta,
        basis_delta=_basis_delta(position.cost_basis, next_basis),
        disposition=TransitionDisposition.APPLIED,
        original_classification=classification,
    )


def _revision_economics(
    fact: BrokerTradeCorrectFact | BrokerTradeBustFact,
) -> tuple[Quantity, ReportedPrice | None]:
    if isinstance(fact, BrokerTradeCorrectFact):
        return fact.revised_quantity, fact.revised_price
    return Quantity(0), fact.reported_price


def _current_predecessor_is_proven(
    seen_facts: SeenFactIndex,
    head: RootHead,
    fact: BrokerTradeCorrectFact | BrokerTradeBustFact,
) -> bool:
    predecessor_key = ExecutionFactKey(
        broker=fact.key.broker,
        environment=fact.key.environment,
        account=fact.key.account,
        source_event_id=fact.predecessor_source_event_id,
    )
    observation = seen_facts.get(predecessor_key)
    return (
        observation is not None
        and observation.classification
        is not FirstObservationClassification.RECONCILIATION_REQUIRED
        and _observation_matches_head(observation, head)
    )


def _tail_proof_is_valid(position: PositionState, head: RootHead) -> bool:
    fold_input = position.tail_fold_input
    if fold_input is None or not fold_input.is_bound:
        return False
    if position.root_count == 0:
        return False
    return (
        fold_input.position_scope == position.scope
        and fold_input.tail_root_key == head.root_key
        and fold_input.prefix_count == head.original_sequence
        and fold_input.prefix_heads_commitment == head.prefix_heads_commitment
        and fold_input.commitment == head.prefix_proof_commitment
        and fold_input.raw_quantity == position.raw_quantity - head.signed_quantity
        and position._root_fill_sequence.get(position.root_count - 1) == head.root_key
        and position._effective_head_ids.get(position.root_count - 1)
        == head.current_source_event_id
    )


def _apply_revision(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    fact: BrokerTradeCorrectFact | BrokerTradeBustFact,
) -> ExecutionTransition:
    head = root_heads.get(fact.root_key)
    if (
        fact.scope.position_scope != position.scope
        or head is None
        or head.authority is not ExecutionAuthority.BROKER_AUTHORITATIVE
        or head.scope != fact.scope
        or head.current_source_event_id != fact.predecessor_source_event_id
        or not _current_predecessor_is_proven(seen_facts, head, fact)
    ):
        return _reconciliation_transition(
            position, integrity, root_heads, seen_facts, fact
        )

    revised_quantity, revised_price = _revision_economics(fact)
    signed_change = revised_quantity.value - head.quantity.value
    if head.scope.side is ExecutionSide.SELL:
        signed_change = -signed_change
    next_raw_quantity = position.raw_quantity + signed_change
    is_tail = head.original_sequence == position.root_count - 1
    can_update_basis = (
        is_tail
        and position.basis_authority is BasisAuthority.AVAILABLE
        and position.cost_basis is not None
        and _tail_proof_is_valid(position, head)
        and _metadata_accepts(
            # The exact prefix metadata, not the current tail's metadata, controls
            # whether this replacement can be folded immediately.
            position.tail_fold_input.price_metadata
            if position.tail_fold_input is not None
            else None,
            revised_price,
        )
    )
    next_basis: ExactBasis | None = None
    next_metadata: ReportedPrice | None = None
    next_tail_input: FoldInput | None = None
    if can_update_basis:
        assert position.tail_fold_input is not None
        folded_quantity, folded_basis = _fold_one(
            position.tail_fold_input.raw_quantity,
            position.tail_fold_input.cost_basis.value,
            head.scope.side,
            revised_quantity.value,
            revised_price,
        )
        if folded_quantity == next_raw_quantity:
            next_basis = ExactBasis(folded_basis)
            next_metadata = _next_metadata(
                position.tail_fold_input.price_metadata,
                revised_price,
                revised_quantity.value,
            )
            next_tail_input = position.tail_fold_input

    pending = next_basis is None
    next_head = RootHead(
        root_key=head.root_key,
        original_sequence=head.original_sequence,
        scope=head.scope,
        authority=head.authority,
        current_source_event_id=fact.key.source_event_id,
        kind=fact.kind,
        quantity=revised_quantity,
        price=revised_price,
        prefix_heads_commitment=(
            head.prefix_heads_commitment
            if not is_tail or next_tail_input is not None
            else b""
        ),
        prefix_proof_commitment=(
            head.prefix_proof_commitment
            if not is_tail or next_tail_input is not None
            else b""
        ),
    )
    next_roots = root_heads.replace(next_head)
    if pending and position.root_count:
        tail_root_key = position._root_fill_sequence.get(position.root_count - 1)
        tail_head = next_roots.get(tail_root_key)
        if tail_head is None:
            raise RuntimeError("position tail root is missing from root index")
        if tail_head.prefix_heads_commitment or tail_head.prefix_proof_commitment:
            next_roots = next_roots.replace(
                replace(
                    tail_head,
                    prefix_heads_commitment=b"",
                    prefix_proof_commitment=b"",
                )
            )
    next_position = PositionState(
        _scope=position.scope,
        raw_quantity=next_raw_quantity,
        basis_authority=(
            BasisAuthority.BASIS_RECONCILIATION_PENDING
            if pending
            else BasisAuthority.AVAILABLE
        ),
        cost_basis=next_basis,
        _root_fill_sequence=next_roots._root_sequence,
        _effective_head_ids=next_roots._head_sequence,
        basis_price_metadata=next_metadata,
        tail_fold_input=next_tail_input,
    )
    classification = _classification(
        pending=pending,
        raw_quantity=next_raw_quantity,
    )
    next_integrity = integrity
    if next_raw_quantity < 0:
        next_integrity |= PositionIntegrity.OVERFILL_QUARANTINE
    next_seen = seen_facts.add(SeenFact(fact=fact, classification=classification))
    snapshot = _bind_components(
        next_position,
        next_integrity,
        next_roots,
        next_seen,
    )
    return ExecutionTransition(
        position=snapshot.position,
        integrity=snapshot.integrity,
        root_heads=snapshot.root_heads,
        seen_facts=snapshot.seen_facts,
        quantity_delta=signed_change,
        basis_delta=_basis_delta(position.cost_basis, next_basis),
        disposition=TransitionDisposition.APPLIED,
        original_classification=classification,
    )


def apply_broker_execution_fact(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    fact: BrokerExecutionFact,
) -> ExecutionTransition:
    """Apply one canonical broker fact without I/O or an ordered history fold."""

    if not isinstance(position, PositionState):
        raise TypeError("position must be PositionState")
    if not isinstance(integrity, PositionIntegrity):
        raise TypeError("integrity must be PositionIntegrity")
    if not isinstance(root_heads, RootHeadIndex):
        raise TypeError("root_heads must be RootHeadIndex")
    if not isinstance(seen_facts, SeenFactIndex):
        raise TypeError("seen_facts must be SeenFactIndex")
    if not isinstance(
        fact,
        (BrokerFillFact, BrokerTradeCorrectFact, BrokerTradeBustFact),
    ):
        raise TypeError("fact must be a canonical broker execution fact")

    if not _snapshot_is_coherent(position, integrity, root_heads, seen_facts):
        return _incoherent_snapshot_transition(
            position,
            integrity,
            root_heads,
            seen_facts,
            fact,
        )

    first_observation = seen_facts.get(fact.key)
    if first_observation is not None:
        if first_observation.fact == fact:
            return _unchanged_transition(
                position,
                integrity,
                root_heads,
                seen_facts,
                disposition=TransitionDisposition.EXACT_REPLAY,
                original_classification=first_observation.classification,
            )
        return _unchanged_transition(
            position,
            integrity | PositionIntegrity.EXECUTION_FACT_CONFLICT,
            root_heads,
            seen_facts,
            disposition=TransitionDisposition.FACT_CONFLICT,
            original_classification=first_observation.classification,
        )

    if isinstance(fact, BrokerFillFact):
        return _apply_root_fill(position, integrity, root_heads, seen_facts, fact)
    return _apply_revision(position, integrity, root_heads, seen_facts, fact)


def _replay_hydration_snapshot(
    scope: PositionScope,
    seen_facts: SeenFactIndex,
) -> ExecutionSnapshot:
    """Re-derive one materialized high-water from first observations only."""

    replayed = ExecutionSnapshot.flat(scope)
    for observation in seen_facts.entries:
        transition = apply_broker_execution_fact(
            replayed.position,
            replayed.integrity,
            replayed.root_heads,
            replayed.seen_facts,
            observation.fact,
        )
        expected_disposition = (
            TransitionDisposition.RECONCILIATION_REQUIRED
            if observation.classification
            is FirstObservationClassification.RECONCILIATION_REQUIRED
            else TransitionDisposition.APPLIED
        )
        if (
            transition.disposition is not expected_disposition
            or transition.original_classification is not observation.classification
        ):
            raise ValueError("seen-fact classification is not reproducible")
        replayed = ExecutionSnapshot(
            position=transition.position,
            integrity=transition.integrity,
            root_heads=transition.root_heads,
            seen_facts=transition.seen_facts,
        )
    if (
        replayed.seen_facts.entries != seen_facts.entries
        or replayed.seen_facts.commitment != seen_facts.commitment
    ):
        raise ValueError("seen-fact replay did not close exactly")
    return replayed


def _root_head_semantics(head: RootHead) -> tuple[object, ...]:
    """Return authoritative head values, excluding optional tail-cache proofs."""

    return (
        head.root_key,
        head.original_sequence,
        head.scope,
        head.authority,
        head.current_source_event_id,
        head.kind,
        head.quantity,
        head.price,
    )


def _require_hydration_match(
    position: PositionState,
    root_heads: RootHeadIndex,
    replayed: ExecutionSnapshot,
) -> None:
    """Require exact replay closure while allowing a fully absent tail cache."""

    replayed_position = replayed.position
    if (
        position.scope != replayed_position.scope
        or position.raw_quantity != replayed_position.raw_quantity
        or position.basis_authority is not replayed_position.basis_authority
        or position.cost_basis != replayed_position.cost_basis
        or position.root_fill_sequence != replayed_position.root_fill_sequence
        or position.effective_head_ids != replayed_position.effective_head_ids
        or position.basis_price_metadata != replayed_position.basis_price_metadata
    ):
        raise ValueError("position economics do not match chronological replay")

    supplied_heads = root_heads.entries
    replayed_heads = replayed.root_heads.entries
    if len(supplied_heads) != len(replayed_heads) or any(
        _root_head_semantics(supplied) != _root_head_semantics(expected)
        for supplied, expected in zip(supplied_heads, replayed_heads)
    ):
        raise ValueError("root heads do not match chronological replay")

    tail_input = position.tail_fold_input
    if tail_input is None:
        if supplied_heads:
            supplied_tail = supplied_heads[-1]
            if (
                supplied_tail.prefix_heads_commitment
                or supplied_tail.prefix_proof_commitment
            ):
                raise ValueError("tail proof must be fully absent")
        return
    expected_tail_input = replayed_position.tail_fold_input
    if (
        position.root_count == 0
        or not tail_input.is_bound
        or expected_tail_input is None
        or tail_input != expected_tail_input
    ):
        raise ValueError("tail fold input is not the exact replayed prefix")
    supplied_tail = supplied_heads[-1]
    replayed_tail = replayed_heads[-1]
    if (
        supplied_tail.prefix_heads_commitment != replayed_tail.prefix_heads_commitment
        or supplied_tail.prefix_proof_commitment
        != replayed_tail.prefix_proof_commitment
        or supplied_tail.prefix_proof_commitment != tail_input.commitment
    ):
        raise ValueError("tail root does not carry the exact replayed proof")


def derive_ordered_basis_candidate(
    position_snapshot: PositionState,
    root_heads: RootHeadIndex,
) -> BasisCandidate:
    """Derive an uncommitted exact basis from a bound immutable root snapshot."""

    if not isinstance(position_snapshot, PositionState):
        raise TypeError("position_snapshot must be PositionState")
    if not isinstance(root_heads, RootHeadIndex):
        raise TypeError("root_heads must be RootHeadIndex")

    sequence = position_snapshot.root_fill_sequence
    head_ids = position_snapshot.effective_head_ids
    binding = position_snapshot.binding
    if (
        binding is None
        or root_heads.binding is not binding
        or binding.position_scope != position_snapshot.scope
        or binding.position_commitment != position_snapshot.commitment
        or binding.root_heads_commitment != root_heads.commitment
        or root_heads.position_scope != position_snapshot.scope
        or root_heads.signed_quantity != position_snapshot.raw_quantity
        or position_snapshot._root_fill_sequence is not root_heads._root_sequence
        or position_snapshot._effective_head_ids is not root_heads._head_sequence
    ):
        return BasisCandidate(
            status=BasisCandidateStatus.SNAPSHOT_INCONSISTENT,
            raw_quantity=position_snapshot.raw_quantity,
            cost_basis=None,
            root_fill_sequence=sequence,
            effective_head_ids=head_ids,
        )

    raw_quantity = 0
    cost_basis = Fraction(0)
    reference_metadata: ReportedPrice | None = None
    metadata_compatible = True
    for head in root_heads.entries:
        if head.authority is not ExecutionAuthority.BROKER_AUTHORITATIVE:
            return BasisCandidate(
                status=BasisCandidateStatus.SNAPSHOT_INCONSISTENT,
                raw_quantity=position_snapshot.raw_quantity,
                cost_basis=None,
                root_fill_sequence=sequence,
                effective_head_ids=head_ids,
            )
        if head.quantity.value > 0 and head.price is None:
            return BasisCandidate(
                status=BasisCandidateStatus.SNAPSHOT_INCONSISTENT,
                raw_quantity=position_snapshot.raw_quantity,
                cost_basis=None,
                root_fill_sequence=sequence,
                effective_head_ids=head_ids,
            )
        if not _metadata_accepts(reference_metadata, head.price):
            metadata_compatible = False
        else:
            reference_metadata = _next_metadata(
                reference_metadata,
                head.price,
                head.quantity.value,
            )
        raw_quantity, cost_basis = _fold_one(
            raw_quantity,
            cost_basis,
            head.scope.side,
            head.quantity.value,
            head.price,
        )

    if raw_quantity != position_snapshot.raw_quantity:
        return BasisCandidate(
            status=BasisCandidateStatus.SNAPSHOT_INCONSISTENT,
            raw_quantity=raw_quantity,
            cost_basis=None,
            root_fill_sequence=sequence,
            effective_head_ids=head_ids,
        )
    if not metadata_compatible:
        return BasisCandidate(
            status=BasisCandidateStatus.INCOMPATIBLE_PRICE_METADATA,
            raw_quantity=raw_quantity,
            cost_basis=None,
            root_fill_sequence=sequence,
            effective_head_ids=head_ids,
        )
    exact_basis = ExactBasis(cost_basis)
    if (
        position_snapshot.basis_authority is BasisAuthority.AVAILABLE
        and position_snapshot.cost_basis != exact_basis
    ):
        return BasisCandidate(
            status=BasisCandidateStatus.SNAPSHOT_INCONSISTENT,
            raw_quantity=raw_quantity,
            cost_basis=None,
            root_fill_sequence=sequence,
            effective_head_ids=head_ids,
        )
    return BasisCandidate(
        status=BasisCandidateStatus.DERIVED,
        raw_quantity=raw_quantity,
        cost_basis=exact_basis,
        root_fill_sequence=sequence,
        effective_head_ids=head_ids,
    )
