"""Pure fill-family position and long-basis transition semantics.

The reducer in this module consumes only explicit immutable inputs.  It does no
I/O and deliberately keeps the ordered slow fold separate from the fast
transition used to accept broker execution truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum, Flag, auto
from fractions import Fraction
from typing import cast

from .fills import (
    BrokerExecutionFact,
    BrokerFillFact,
    BrokerTradeBustFact,
    BrokerTradeCorrectFact,
    CanonicalExecutionFact,
    CanonicalRootFillFact,
    ExecutionAuthority,
    ExecutionSide,
    FirstObservationClassification,
    HumanAttestedFillFact,
    PositionScope,
    RootHead,
    RootHeadIndex,
    SeenFact,
    SeenFactIndex,
    _PersistentKeyMapWitness,
    _PersistentSequence,
    _SnapshotBinding,
    _commit_parts,
    _commit_root_fill_key,
    _commit_source_event_id,
    _encode_execution_fact,
    _encode_execution_fact_key,
    _encode_fraction,
    _encode_int,
    _encode_position_scope,
    _encode_reported_price,
    _encode_root_fill_key,
    _require_exact_reported_price,
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


_RECONCILIATION_GENESIS_HEAD = _commit_parts(
    b"execution-core/account-reconciliation-genesis/v1"
)


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
        if type(self.cost_basis) is not ExactBasis:
            raise TypeError("cost_basis must be ExactBasis")
        _require_exact_basis("cost_basis", self.cost_basis)
        if self.price_metadata is not None:
            try:
                _require_exact_reported_price("price_metadata", self.price_metadata)
            except TypeError as error:
                raise TypeError(
                    "price_metadata must be ReportedPrice or None (exact type required)"
                ) from error
        if self.raw_quantity <= 0 and self.cost_basis.value != 0:
            raise ValueError("a non-positive fold quantity cannot carry long basis")
        if (
            self.position_scope is not None
            and type(self.position_scope) is not PositionScope
        ):
            raise TypeError("position_scope must be PositionScope or None")
        if (
            self.tail_root_key is not None
            and type(self.tail_root_key) is not RootFillKey
        ):
            raise TypeError("tail_root_key must be RootFillKey or None")
        _require_signed_integer("prefix_count", self.prefix_count)
        if type(self.prefix_heads_commitment) is not bytes:
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
    integrity_floor: PositionIntegrity = PositionIntegrity.CONSISTENT
    _binding: _SnapshotBinding | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if type(self._scope) is not PositionScope:
            raise TypeError("_scope must be PositionScope")
        _require_signed_integer("raw_quantity", self.raw_quantity)
        if type(self.basis_authority) is not BasisAuthority:
            raise TypeError("basis_authority must be BasisAuthority")
        if type(self._root_fill_sequence) is not _PersistentSequence:
            raise TypeError("_root_fill_sequence must be persistent")
        if type(self._effective_head_ids) is not _PersistentSequence:
            raise TypeError("_effective_head_ids must be persistent")
        if self._root_fill_sequence.length != self._effective_head_ids.length:
            raise ValueError("root sequence and effective heads must remain aligned")
        if self.basis_price_metadata is not None:
            try:
                _require_exact_reported_price(
                    "basis_price_metadata",
                    self.basis_price_metadata,
                )
            except TypeError as error:
                raise TypeError(
                    "basis_price_metadata must be ReportedPrice or None "
                    "(exact type required)"
                ) from error
        if (
            self.tail_fold_input is not None
            and type(self.tail_fold_input) is not FoldInput
        ):
            raise TypeError("tail_fold_input must be FoldInput or None")
        if type(self.integrity_floor) is not PositionIntegrity:
            raise TypeError("integrity_floor must be PositionIntegrity")
        if self._binding is not None and type(self._binding) is not _SnapshotBinding:
            raise TypeError("_binding must be the exact _SnapshotBinding type or None")
        if self.basis_authority is BasisAuthority.AVAILABLE:
            if type(self.cost_basis) is not ExactBasis:
                raise ValueError("available basis requires an exact cost basis")
            _require_exact_basis("cost_basis", self.cost_basis)
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

        if type(root_fill_sequence) is not tuple:
            raise TypeError("root_fill_sequence must be a tuple")
        if type(effective_head_ids) is not tuple:
            raise TypeError("effective_head_ids must be a tuple")
        if not all(type(key) is RootFillKey for key in root_fill_sequence):
            raise TypeError("root_fill_sequence entries must be RootFillKey")
        if not all(type(event_id) is SourceEventId for event_id in effective_head_ids):
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

        if type(scope) is not PositionScope:
            raise TypeError(
                "scope must be the exact PositionScope type; "
                "scope must be PositionScope; position scope must be exact; "
                "position.scope must be PositionScope"
            )
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
        if type(binding) is not _SnapshotBinding:
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
class ExecutionReconciliationCursor:
    """Independently retained account-reconciliation restart high-water."""

    transition_count: int
    transition_head: bytes
    account_reconciliation_required: bool
    snapshot_commitment: bytes

    def __post_init__(self) -> None:
        if type(self.transition_count) is not int or self.transition_count < 0:
            raise ValueError("transition_count must be a non-negative exact integer")
        for name in ("transition_head", "snapshot_commitment"):
            value = getattr(self, name)
            if type(value) is not bytes or len(value) != 32:
                raise ValueError(f"{name} must contain exactly 32 bytes")
        if type(self.account_reconciliation_required) is not bool:
            raise TypeError("account_reconciliation_required must be bool")


@dataclass(frozen=True, slots=True)
class ExecutionSnapshot:
    """One coherently bound immutable execution-kernel high-water."""

    position: PositionState
    integrity: PositionIntegrity
    root_heads: RootHeadIndex
    seen_facts: SeenFactIndex

    def __post_init__(self) -> None:
        _require_execution_components(
            self.position,
            self.integrity,
            self.root_heads,
            self.seen_facts,
        )
        if not _snapshot_is_coherent(
            self.position,
            self.integrity,
            self.root_heads,
            self.seen_facts,
        ):
            raise ValueError("execution snapshot components are not coherently bound")

    @property
    def commitment(self) -> bytes:
        """Return the immutable aggregate high-water commitment."""

        binding = self.position.binding
        if binding is None:
            raise RuntimeError("coherent execution snapshot has no binding")
        return binding.snapshot_commitment

    @property
    def account_reconciliation_required(self) -> bool:
        """Return the sticky account-wide venue-attribution restriction."""

        binding = self.position.binding
        if binding is None:
            raise RuntimeError("coherent execution snapshot has no binding")
        return binding.account_reconciliation_required

    @property
    def reconciliation_transition_count(self) -> int:
        """Return the externally bound ordered reconciliation cursor count."""

        binding = self.position.binding
        if binding is None:
            raise RuntimeError("coherent execution snapshot has no binding")
        return binding.reconciliation_transition_count

    @property
    def reconciliation_transition_head(self) -> bytes:
        """Return the externally bound ordered reconciliation cursor head."""

        binding = self.position.binding
        if binding is None:
            raise RuntimeError("coherent execution snapshot has no binding")
        return binding.reconciliation_transition_head

    @property
    def reconciliation_cursor(self) -> ExecutionReconciliationCursor:
        """Return the exact restart cursor to retain independently of the book."""

        return ExecutionReconciliationCursor(
            transition_count=self.reconciliation_transition_count,
            transition_head=self.reconciliation_transition_head,
            account_reconciliation_required=(self.account_reconciliation_required),
            snapshot_commitment=self.commitment,
        )

    @classmethod
    def flat(cls, scope: PositionScope) -> ExecutionSnapshot:
        """Create the only admitted empty snapshot for exact position scope."""

        if type(scope) is not PositionScope:
            raise TypeError("scope must be the exact PositionScope type")
        return _bind_components(
            PositionState.flat(scope),
            PositionIntegrity.CONSISTENT,
            RootHeadIndex.empty(scope),
            SeenFactIndex.empty(scope),
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

        _require_execution_components(position, integrity, root_heads, seen_facts)
        seen_facts = seen_facts._for_position_scope(position.scope)
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


@dataclass(frozen=True, slots=True, init=False)
class _M2ExecutionState:
    """Bounded execution state retained independently of history-shaped indexes."""

    scope: PositionScope
    raw_quantity: int
    basis_authority: BasisAuthority
    cost_basis: ExactBasis | None
    basis_price_metadata: ReportedPrice | None
    tail_fold_input: FoldInput | None
    integrity_floor: PositionIntegrity
    integrity: PositionIntegrity
    account_reconciliation_required: bool
    reconciliation_transition_count: int
    reconciliation_transition_head: bytes
    root_count: int
    root_order_commitment: bytes
    head_ids_commitment: bytes
    root_heads_commitment: bytes
    seen_facts_commitment: bytes
    root_head_map_commitment: bytes
    seen_fact_map_commitment: bytes
    root_claim_map_commitment: bytes
    commitment: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("_M2ExecutionState is owner-constructed")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("_M2ExecutionState cannot be subclassed")


@dataclass(frozen=True, slots=True, init=False)
class _M2ExecutionObservationProof:
    """One aggregate-bound direct-current proof for a broker execution input."""

    state_commitment: bytes
    root_heads_commitment: bytes
    seen_facts_commitment: bytes
    root_head_map_commitment: bytes
    seen_fact_map_commitment: bytes
    root_claim_map_commitment: bytes
    fact: BrokerExecutionFact
    prior_observation: SeenFact | None
    root_head: RootHead | None
    predecessor_observation: SeenFact | None
    root_claimed: bool
    prior_observation_witness: _PersistentKeyMapWitness
    root_head_witness: _PersistentKeyMapWitness
    predecessor_observation_witness: _PersistentKeyMapWitness | None
    root_claim_witness: _PersistentKeyMapWitness
    commitment: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("_M2ExecutionObservationProof is owner-constructed")

    @classmethod
    def from_snapshot(
        cls,
        state: _M2ExecutionState,
        snapshot: ExecutionSnapshot,
        fact: BrokerExecutionFact,
    ) -> _M2ExecutionObservationProof:
        """Mint one proof only from a coherent snapshot's exact keyed slice."""

        if cls is not _M2ExecutionObservationProof:
            raise TypeError("_M2ExecutionObservationProof rejects subclass instances")
        if type(state) is not _M2ExecutionState or not _m2_execution_state_is_authentic(
            state
        ):
            raise ValueError("state must be an authentic _M2ExecutionState")
        if type(snapshot) is not ExecutionSnapshot:
            raise TypeError("snapshot must be ExecutionSnapshot")
        if type(fact) not in {
            BrokerFillFact,
            BrokerTradeCorrectFact,
            BrokerTradeBustFact,
        }:
            raise TypeError("fact must be an exact broker execution fact")
        projected = _m2_execution_state_from_snapshot(snapshot)
        if projected != state:
            raise ValueError("state is not the exact coherent snapshot projection")
        prior_observation = snapshot.seen_facts.get(fact.key)
        root_head = snapshot.root_heads.get(fact.root_key)
        prior_observation_witness = snapshot.seen_facts._fact_witness(fact.key)
        root_head_witness = snapshot.root_heads._current_head_witness(fact.root_key)
        predecessor_observation = None
        predecessor_observation_witness = None
        if type(fact) in {BrokerTradeCorrectFact, BrokerTradeBustFact}:
            revision_fact = cast(BrokerTradeCorrectFact | BrokerTradeBustFact, fact)
            predecessor_key = ExecutionFactKey(
                broker=revision_fact.key.broker,
                environment=revision_fact.key.environment,
                account=revision_fact.key.account,
                source_event_id=revision_fact.predecessor_source_event_id,
            )
            predecessor_observation = snapshot.seen_facts.get(predecessor_key)
            predecessor_observation_witness = snapshot.seen_facts._fact_witness(
                predecessor_key
            )
        root_claimed = snapshot.seen_facts.contains_root(fact.root_key)
        root_claim_witness = snapshot.seen_facts._root_claim_witness(fact.root_key)
        commitment = _m2_execution_observation_proof_commitment(
            state_commitment=state.commitment,
            root_heads_commitment=state.root_heads_commitment,
            seen_facts_commitment=state.seen_facts_commitment,
            root_head_map_commitment=state.root_head_map_commitment,
            seen_fact_map_commitment=state.seen_fact_map_commitment,
            root_claim_map_commitment=state.root_claim_map_commitment,
            fact=fact,
            prior_observation=prior_observation,
            root_head=root_head,
            predecessor_observation=predecessor_observation,
            root_claimed=root_claimed,
            prior_observation_witness=prior_observation_witness,
            root_head_witness=root_head_witness,
            predecessor_observation_witness=predecessor_observation_witness,
            root_claim_witness=root_claim_witness,
        )
        result = object.__new__(_M2ExecutionObservationProof)
        object.__setattr__(result, "state_commitment", state.commitment)
        object.__setattr__(result, "root_heads_commitment", state.root_heads_commitment)
        object.__setattr__(result, "seen_facts_commitment", state.seen_facts_commitment)
        object.__setattr__(
            result, "root_head_map_commitment", state.root_head_map_commitment
        )
        object.__setattr__(
            result, "seen_fact_map_commitment", state.seen_fact_map_commitment
        )
        object.__setattr__(
            result, "root_claim_map_commitment", state.root_claim_map_commitment
        )
        object.__setattr__(result, "fact", fact)
        object.__setattr__(result, "prior_observation", prior_observation)
        object.__setattr__(result, "root_head", root_head)
        object.__setattr__(result, "predecessor_observation", predecessor_observation)
        object.__setattr__(result, "root_claimed", root_claimed)
        object.__setattr__(
            result, "prior_observation_witness", prior_observation_witness
        )
        object.__setattr__(result, "root_head_witness", root_head_witness)
        object.__setattr__(
            result,
            "predecessor_observation_witness",
            predecessor_observation_witness,
        )
        object.__setattr__(result, "root_claim_witness", root_claim_witness)
        object.__setattr__(result, "commitment", commitment)
        return result

    @classmethod
    def _is_authentic(cls, proof: object) -> bool:
        """Return whether a sealed proof remains its exact direct-current slice."""

        if cls is not _M2ExecutionObservationProof or type(proof) is not cls:
            return False
        candidate = cast(_M2ExecutionObservationProof, proof)
        if any(
            type(value) is not bytes or len(value) != 32
            for value in (
                candidate.state_commitment,
                candidate.root_heads_commitment,
                candidate.seen_facts_commitment,
                candidate.root_head_map_commitment,
                candidate.seen_fact_map_commitment,
                candidate.root_claim_map_commitment,
                candidate.commitment,
            )
        ):
            return False
        if type(candidate.fact) not in {
            BrokerFillFact,
            BrokerTradeCorrectFact,
            BrokerTradeBustFact,
        }:
            return False
        if (
            candidate.prior_observation is not None
            and type(candidate.prior_observation) is not SeenFact
        ):
            return False
        if (
            candidate.root_head is not None
            and type(candidate.root_head) is not RootHead
        ):
            return False
        if (
            candidate.predecessor_observation is not None
            and type(candidate.predecessor_observation) is not SeenFact
        ):
            return False
        if type(candidate.root_claimed) is not bool:
            return False
        if (
            type(candidate.prior_observation_witness) is not _PersistentKeyMapWitness
            or type(candidate.root_head_witness) is not _PersistentKeyMapWitness
            or type(candidate.root_claim_witness) is not _PersistentKeyMapWitness
            or (
                candidate.predecessor_observation_witness is not None
                and type(candidate.predecessor_observation_witness)
                is not _PersistentKeyMapWitness
            )
        ):
            return False
        try:
            expected = _m2_execution_observation_proof_commitment(
                state_commitment=candidate.state_commitment,
                root_heads_commitment=candidate.root_heads_commitment,
                seen_facts_commitment=candidate.seen_facts_commitment,
                root_head_map_commitment=candidate.root_head_map_commitment,
                seen_fact_map_commitment=candidate.seen_fact_map_commitment,
                root_claim_map_commitment=candidate.root_claim_map_commitment,
                fact=candidate.fact,
                prior_observation=candidate.prior_observation,
                root_head=candidate.root_head,
                predecessor_observation=candidate.predecessor_observation,
                root_claimed=candidate.root_claimed,
                prior_observation_witness=candidate.prior_observation_witness,
                root_head_witness=candidate.root_head_witness,
                predecessor_observation_witness=candidate.predecessor_observation_witness,
                root_claim_witness=candidate.root_claim_witness,
            )
        except (TypeError, ValueError):
            return False
        return candidate.commitment == expected

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("_M2ExecutionObservationProof cannot be subclassed")


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


def _require_exact_basis(name: str, value: object) -> None:
    if type(value) is not ExactBasis:
        raise TypeError(f"{name} must be the exact ExactBasis type")
    basis = cast(ExactBasis, value)
    if type(basis.value) is not Fraction:
        raise TypeError(f"{name}.value must be the exact Fraction type")


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


def _m2_execution_state_commitment(
    *,
    scope: PositionScope,
    raw_quantity: int,
    basis_authority: BasisAuthority,
    cost_basis: ExactBasis | None,
    basis_price_metadata: ReportedPrice | None,
    tail_fold_input: FoldInput | None,
    integrity_floor: PositionIntegrity,
    integrity: PositionIntegrity,
    account_reconciliation_required: bool,
    reconciliation_transition_count: int,
    reconciliation_transition_head: bytes,
    root_count: int,
    root_order_commitment: bytes,
    head_ids_commitment: bytes,
    root_heads_commitment: bytes,
    seen_facts_commitment: bytes,
    root_head_map_commitment: bytes,
    seen_fact_map_commitment: bytes,
    root_claim_map_commitment: bytes,
) -> bytes:
    """Commit only the exact bounded execution members retained by M2."""

    return _commit_parts(
        b"execution-core/m2-execution-state/v1",
        _encode_position_scope(scope),
        _encode_int(raw_quantity),
        basis_authority.value.encode("ascii"),
        _encode_fraction(cost_basis.value) if cost_basis is not None else b"",
        _encode_reported_price(basis_price_metadata),
        (
            _commit_parts(
                b"execution-core/m2-execution-tail/present/v1",
                tail_fold_input.commitment,
            )
            if tail_fold_input is not None
            else _commit_parts(b"execution-core/m2-execution-tail/absent/v1")
        ),
        _encode_int(integrity_floor.value),
        _encode_int(integrity.value),
        _encode_int(int(account_reconciliation_required)),
        _encode_int(reconciliation_transition_count),
        reconciliation_transition_head,
        _encode_int(root_count),
        root_order_commitment,
        head_ids_commitment,
        root_heads_commitment,
        seen_facts_commitment,
        root_head_map_commitment,
        seen_fact_map_commitment,
        root_claim_map_commitment,
    )


def _m2_execution_observation_proof_commitment(
    *,
    state_commitment: bytes,
    root_heads_commitment: bytes,
    seen_facts_commitment: bytes,
    root_head_map_commitment: bytes,
    seen_fact_map_commitment: bytes,
    root_claim_map_commitment: bytes,
    fact: BrokerExecutionFact,
    prior_observation: SeenFact | None,
    root_head: RootHead | None,
    predecessor_observation: SeenFact | None,
    root_claimed: bool,
    prior_observation_witness: _PersistentKeyMapWitness,
    root_head_witness: _PersistentKeyMapWitness,
    predecessor_observation_witness: _PersistentKeyMapWitness | None,
    root_claim_witness: _PersistentKeyMapWitness,
) -> bytes:
    """Commit exactly one aggregate-bound direct execution proof slice."""

    return _commit_parts(
        b"execution-core/m2-execution-observation-proof/v1",
        state_commitment,
        root_heads_commitment,
        seen_facts_commitment,
        root_head_map_commitment,
        seen_fact_map_commitment,
        root_claim_map_commitment,
        _encode_execution_fact(fact),
        (
            prior_observation.commitment
            if prior_observation is not None
            else _commit_parts(b"execution-core/m2-observation/absent/v1")
        ),
        (
            root_head.commitment
            if root_head is not None
            else _commit_parts(b"execution-core/m2-root-head/absent/v1")
        ),
        (
            predecessor_observation.commitment
            if predecessor_observation is not None
            else _commit_parts(b"execution-core/m2-predecessor/absent/v1")
        ),
        b"\x01" if root_claimed else b"\x00",
        prior_observation_witness.commitment,
        root_head_witness.commitment,
        (
            predecessor_observation_witness.commitment
            if predecessor_observation_witness is not None
            else _commit_parts(b"execution-core/m2-predecessor-witness/absent/v1")
        ),
        root_claim_witness.commitment,
    )


def _new_m2_execution_state(
    *,
    scope: PositionScope,
    raw_quantity: int,
    basis_authority: BasisAuthority,
    cost_basis: ExactBasis | None,
    basis_price_metadata: ReportedPrice | None,
    tail_fold_input: FoldInput | None,
    integrity_floor: PositionIntegrity,
    integrity: PositionIntegrity,
    account_reconciliation_required: bool,
    reconciliation_transition_count: int,
    reconciliation_transition_head: bytes,
    root_count: int,
    root_order_commitment: bytes,
    head_ids_commitment: bytes,
    root_heads_commitment: bytes,
    seen_facts_commitment: bytes,
    root_head_map_commitment: bytes,
    seen_fact_map_commitment: bytes,
    root_claim_map_commitment: bytes,
) -> _M2ExecutionState:
    """Construct one sealed bounded execution state through its owning checks."""

    if type(scope) is not PositionScope:
        raise TypeError("scope must be PositionScope")
    _require_signed_integer("raw_quantity", raw_quantity)
    if type(basis_authority) is not BasisAuthority:
        raise TypeError("basis_authority must be BasisAuthority")
    if cost_basis is not None:
        _require_exact_basis("cost_basis", cost_basis)
    if basis_price_metadata is not None:
        _require_exact_reported_price("basis_price_metadata", basis_price_metadata)
    if tail_fold_input is not None and type(tail_fold_input) is not FoldInput:
        raise TypeError("tail_fold_input must be FoldInput or None")
    if type(integrity_floor) is not PositionIntegrity:
        raise TypeError("integrity_floor must be PositionIntegrity")
    if type(integrity) is not PositionIntegrity:
        raise TypeError("integrity must be PositionIntegrity")
    if integrity_floor & integrity != integrity_floor:
        raise ValueError("integrity cannot clear the position integrity floor")
    if type(account_reconciliation_required) is not bool:
        raise TypeError("account_reconciliation_required must be bool")
    if (
        type(reconciliation_transition_count) is not int
        or reconciliation_transition_count < 0
    ):
        raise ValueError("reconciliation_transition_count must be non-negative")
    if (
        type(reconciliation_transition_head) is not bytes
        or len(reconciliation_transition_head) != 32
    ):
        raise ValueError("reconciliation_transition_head must contain exactly 32 bytes")
    if type(root_count) is not int or root_count < 0:
        raise ValueError("root_count must be a non-negative exact integer")
    for name, value in (
        ("root_order_commitment", root_order_commitment),
        ("head_ids_commitment", head_ids_commitment),
        ("root_heads_commitment", root_heads_commitment),
        ("seen_facts_commitment", seen_facts_commitment),
        ("root_head_map_commitment", root_head_map_commitment),
        ("seen_fact_map_commitment", seen_fact_map_commitment),
        ("root_claim_map_commitment", root_claim_map_commitment),
    ):
        if type(value) is not bytes or len(value) != 32:
            raise ValueError(f"{name} must contain exactly 32 bytes")
    if basis_authority is BasisAuthority.AVAILABLE:
        if type(cost_basis) is not ExactBasis:
            raise ValueError("available basis requires an exact cost basis")
        if raw_quantity <= 0 and cost_basis.value != 0:
            raise ValueError("a non-positive position cannot carry long basis")
    elif (
        cost_basis is not None
        or basis_price_metadata is not None
        or tail_fold_input is not None
    ):
        raise ValueError("pending basis cannot retain basis-derived cache")
    commitment = _m2_execution_state_commitment(
        scope=scope,
        raw_quantity=raw_quantity,
        basis_authority=basis_authority,
        cost_basis=cost_basis,
        basis_price_metadata=basis_price_metadata,
        tail_fold_input=tail_fold_input,
        integrity_floor=integrity_floor,
        integrity=integrity,
        account_reconciliation_required=account_reconciliation_required,
        reconciliation_transition_count=reconciliation_transition_count,
        reconciliation_transition_head=reconciliation_transition_head,
        root_count=root_count,
        root_order_commitment=root_order_commitment,
        head_ids_commitment=head_ids_commitment,
        root_heads_commitment=root_heads_commitment,
        seen_facts_commitment=seen_facts_commitment,
        root_head_map_commitment=root_head_map_commitment,
        seen_fact_map_commitment=seen_fact_map_commitment,
        root_claim_map_commitment=root_claim_map_commitment,
    )
    result = object.__new__(_M2ExecutionState)
    object.__setattr__(result, "scope", scope)
    object.__setattr__(result, "raw_quantity", raw_quantity)
    object.__setattr__(result, "basis_authority", basis_authority)
    object.__setattr__(result, "cost_basis", cost_basis)
    object.__setattr__(result, "basis_price_metadata", basis_price_metadata)
    object.__setattr__(result, "tail_fold_input", tail_fold_input)
    object.__setattr__(result, "integrity_floor", integrity_floor)
    object.__setattr__(result, "integrity", integrity)
    object.__setattr__(
        result,
        "account_reconciliation_required",
        account_reconciliation_required,
    )
    object.__setattr__(
        result,
        "reconciliation_transition_count",
        reconciliation_transition_count,
    )
    object.__setattr__(
        result,
        "reconciliation_transition_head",
        reconciliation_transition_head,
    )
    object.__setattr__(result, "root_count", root_count)
    object.__setattr__(result, "root_order_commitment", root_order_commitment)
    object.__setattr__(result, "head_ids_commitment", head_ids_commitment)
    object.__setattr__(result, "root_heads_commitment", root_heads_commitment)
    object.__setattr__(result, "seen_facts_commitment", seen_facts_commitment)
    object.__setattr__(result, "root_head_map_commitment", root_head_map_commitment)
    object.__setattr__(result, "seen_fact_map_commitment", seen_fact_map_commitment)
    object.__setattr__(result, "root_claim_map_commitment", root_claim_map_commitment)
    object.__setattr__(result, "commitment", commitment)
    return result


def _m2_execution_state_is_authentic(state: object) -> bool:
    """Return whether an opaque M2 execution state re-derives exactly."""

    if type(state) is not _M2ExecutionState:
        return False
    try:
        expected = _m2_execution_state_commitment(
            scope=state.scope,
            raw_quantity=state.raw_quantity,
            basis_authority=state.basis_authority,
            cost_basis=state.cost_basis,
            basis_price_metadata=state.basis_price_metadata,
            tail_fold_input=state.tail_fold_input,
            integrity_floor=state.integrity_floor,
            integrity=state.integrity,
            account_reconciliation_required=state.account_reconciliation_required,
            reconciliation_transition_count=state.reconciliation_transition_count,
            reconciliation_transition_head=state.reconciliation_transition_head,
            root_count=state.root_count,
            root_order_commitment=state.root_order_commitment,
            head_ids_commitment=state.head_ids_commitment,
            root_heads_commitment=state.root_heads_commitment,
            seen_facts_commitment=state.seen_facts_commitment,
            root_head_map_commitment=state.root_head_map_commitment,
            seen_fact_map_commitment=state.seen_fact_map_commitment,
            root_claim_map_commitment=state.root_claim_map_commitment,
        )
        rebuilt = _new_m2_execution_state(
            scope=state.scope,
            raw_quantity=state.raw_quantity,
            basis_authority=state.basis_authority,
            cost_basis=state.cost_basis,
            basis_price_metadata=state.basis_price_metadata,
            tail_fold_input=state.tail_fold_input,
            integrity_floor=state.integrity_floor,
            integrity=state.integrity,
            account_reconciliation_required=state.account_reconciliation_required,
            reconciliation_transition_count=state.reconciliation_transition_count,
            reconciliation_transition_head=state.reconciliation_transition_head,
            root_count=state.root_count,
            root_order_commitment=state.root_order_commitment,
            head_ids_commitment=state.head_ids_commitment,
            root_heads_commitment=state.root_heads_commitment,
            seen_facts_commitment=state.seen_facts_commitment,
            root_head_map_commitment=state.root_head_map_commitment,
            seen_fact_map_commitment=state.seen_fact_map_commitment,
            root_claim_map_commitment=state.root_claim_map_commitment,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return state.commitment == expected == rebuilt.commitment


def _m2_execution_state_from_snapshot(snapshot: ExecutionSnapshot) -> _M2ExecutionState:
    """Project one coherent in-memory snapshot to its bounded M2 state."""

    if type(snapshot) is not ExecutionSnapshot:
        raise TypeError("snapshot must be ExecutionSnapshot")
    if not _snapshot_is_coherent(
        snapshot.position,
        snapshot.integrity,
        snapshot.root_heads,
        snapshot.seen_facts,
    ):
        raise ValueError("snapshot must be coherently bound")
    binding = snapshot.position.binding
    if binding is None:
        raise ValueError("coherent snapshot has no binding")
    return _new_m2_execution_state(
        scope=snapshot.position.scope,
        raw_quantity=snapshot.position.raw_quantity,
        basis_authority=snapshot.position.basis_authority,
        cost_basis=snapshot.position.cost_basis,
        basis_price_metadata=snapshot.position.basis_price_metadata,
        tail_fold_input=snapshot.position.tail_fold_input,
        integrity_floor=snapshot.position.integrity_floor,
        integrity=snapshot.integrity,
        account_reconciliation_required=binding.account_reconciliation_required,
        reconciliation_transition_count=binding.reconciliation_transition_count,
        reconciliation_transition_head=binding.reconciliation_transition_head,
        root_count=snapshot.root_heads.count,
        root_order_commitment=snapshot.root_heads.root_order_commitment,
        head_ids_commitment=snapshot.root_heads.head_ids_commitment,
        root_heads_commitment=snapshot.root_heads.commitment,
        seen_facts_commitment=snapshot.seen_facts.commitment,
        root_head_map_commitment=snapshot.root_heads._by_root.commitment,
        seen_fact_map_commitment=snapshot.seen_facts._by_key.commitment,
        root_claim_map_commitment=snapshot.seen_facts._observed_roots.commitment,
    )


def _m2_execution_state_from_checkpoint_fields(
    fields: tuple[object, ...],
) -> _M2ExecutionState:
    """Decode one inert checkpoint state without minting serving authority."""

    if type(fields) is not tuple or len(fields) != 19:
        raise ValueError("checkpoint execution state has an invalid field count")
    (
        scope,
        raw_quantity,
        basis_authority,
        cost_basis,
        basis_price_metadata,
        tail_fold_input,
        integrity_floor,
        integrity,
        account_reconciliation_required,
        reconciliation_transition_count,
        reconciliation_transition_head,
        root_count,
        root_order_commitment,
        head_ids_commitment,
        root_heads_commitment,
        seen_facts_commitment,
        root_head_map_commitment,
        seen_fact_map_commitment,
        root_claim_map_commitment,
    ) = fields
    return _new_m2_execution_state(
        scope=cast(PositionScope, scope),
        raw_quantity=cast(int, raw_quantity),
        basis_authority=cast(BasisAuthority, basis_authority),
        cost_basis=cast(ExactBasis | None, cost_basis),
        basis_price_metadata=cast(ReportedPrice | None, basis_price_metadata),
        tail_fold_input=cast(FoldInput | None, tail_fold_input),
        integrity_floor=cast(PositionIntegrity, integrity_floor),
        integrity=cast(PositionIntegrity, integrity),
        account_reconciliation_required=cast(bool, account_reconciliation_required),
        reconciliation_transition_count=cast(int, reconciliation_transition_count),
        reconciliation_transition_head=cast(bytes, reconciliation_transition_head),
        root_count=cast(int, root_count),
        root_order_commitment=cast(bytes, root_order_commitment),
        head_ids_commitment=cast(bytes, head_ids_commitment),
        root_heads_commitment=cast(bytes, root_heads_commitment),
        seen_facts_commitment=cast(bytes, seen_facts_commitment),
        root_head_map_commitment=cast(bytes, root_head_map_commitment),
        seen_fact_map_commitment=cast(bytes, seen_fact_map_commitment),
        root_claim_map_commitment=cast(bytes, root_claim_map_commitment),
    )


def _m2_restore_compact_execution_snapshot(
    state: _M2ExecutionState,
    root_heads: RootHeadIndex,
    current_facts: SeenFactIndex,
) -> ExecutionSnapshot:
    """Cut an inert bounded state over complete current roots into a compact owner."""

    if not _m2_execution_state_is_authentic(state):
        raise ValueError("execution checkpoint state is not authentic")
    if type(root_heads) is not RootHeadIndex:
        raise TypeError("root_heads must be exact RootHeadIndex")
    if type(current_facts) is not SeenFactIndex:
        raise TypeError("current_facts must be exact SeenFactIndex")
    if (
        root_heads.position_scope != state.scope
        or root_heads.count != state.root_count
        or root_heads.signed_quantity != state.raw_quantity
    ):
        raise ValueError("current root proof does not reproduce execution economics")
    if state.tail_fold_input is not None:
        tail = state.tail_fold_input
        if (
            not tail.is_bound
            or tail.position_scope != state.scope
            or tail.prefix_count != state.root_count - 1
            or state.root_count < 1
            or root_heads._root_sequence.get(state.root_count - 1) != tail.tail_root_key
        ):
            raise ValueError(
                "current root proof does not reproduce the tail basis proof"
            )
    position = PositionState.from_materialized(
        scope=state.scope,
        raw_quantity=state.raw_quantity,
        basis_authority=state.basis_authority,
        cost_basis=state.cost_basis,
        root_fill_sequence=root_heads._root_sequence.to_tuple(),
        effective_head_ids=root_heads._head_sequence.to_tuple(),
        basis_price_metadata=state.basis_price_metadata,
        tail_fold_input=state.tail_fold_input,
        integrity_floor=state.integrity_floor,
    )
    return _bind_components(
        position,
        state.integrity,
        root_heads,
        current_facts,
        account_reconciliation_required=state.account_reconciliation_required,
        reconciliation_transition_count=state.reconciliation_transition_count,
        reconciliation_transition_head=state.reconciliation_transition_head,
    )


def _m2_execution_state_from_direct_proof(
    state_or_fields: _M2ExecutionState | tuple[object, ...],
    proof: _M2ExecutionObservationProof,
) -> _M2ExecutionState:
    """Construct/authenticate bounded state from exact direct-current fields."""

    if type(proof) is not _M2ExecutionObservationProof:
        raise TypeError("proof must be exact _M2ExecutionObservationProof")
    if type(state_or_fields) is _M2ExecutionState:
        state = state_or_fields
    elif type(state_or_fields) is tuple:
        if len(state_or_fields) != 19:
            raise ValueError("direct execution state has an invalid field count")
        (
            scope,
            raw_quantity,
            basis_authority,
            cost_basis,
            basis_price_metadata,
            tail_fold_input,
            integrity_floor,
            integrity,
            account_reconciliation_required,
            reconciliation_transition_count,
            reconciliation_transition_head,
            root_count,
            root_order_commitment,
            head_ids_commitment,
            root_heads_commitment,
            seen_facts_commitment,
            root_head_map_commitment,
            seen_fact_map_commitment,
            root_claim_map_commitment,
        ) = state_or_fields
        state = _new_m2_execution_state(
            scope=cast(PositionScope, scope),
            raw_quantity=cast(int, raw_quantity),
            basis_authority=cast(BasisAuthority, basis_authority),
            cost_basis=cast(ExactBasis | None, cost_basis),
            basis_price_metadata=cast(ReportedPrice | None, basis_price_metadata),
            tail_fold_input=cast(FoldInput | None, tail_fold_input),
            integrity_floor=cast(PositionIntegrity, integrity_floor),
            integrity=cast(PositionIntegrity, integrity),
            account_reconciliation_required=cast(bool, account_reconciliation_required),
            reconciliation_transition_count=cast(int, reconciliation_transition_count),
            reconciliation_transition_head=cast(bytes, reconciliation_transition_head),
            root_count=cast(int, root_count),
            root_order_commitment=cast(bytes, root_order_commitment),
            head_ids_commitment=cast(bytes, head_ids_commitment),
            root_heads_commitment=cast(bytes, root_heads_commitment),
            seen_facts_commitment=cast(bytes, seen_facts_commitment),
            root_head_map_commitment=cast(bytes, root_head_map_commitment),
            seen_fact_map_commitment=cast(bytes, seen_fact_map_commitment),
            root_claim_map_commitment=cast(bytes, root_claim_map_commitment),
        )
    else:
        raise TypeError("state_or_fields must be exact _M2ExecutionState or tuple")
    if not _m2_execution_state_is_authentic(state):
        raise ValueError("execution state is not authentic")
    if not _M2ExecutionObservationProof._is_authentic(proof):
        raise ValueError("direct proof is not authentic")
    if proof.state_commitment != state.commitment:
        raise ValueError("direct proof state commitment does not match state")
    if (
        proof.root_heads_commitment != state.root_heads_commitment
        or proof.seen_facts_commitment != state.seen_facts_commitment
        or proof.root_head_map_commitment != state.root_head_map_commitment
        or proof.seen_fact_map_commitment != state.seen_fact_map_commitment
        or proof.root_claim_map_commitment != state.root_claim_map_commitment
    ):
        raise ValueError("direct proof aggregate commitments do not match state")
    if (
        proof.prior_observation is not None
        and proof.prior_observation.fact.key != proof.fact.key
    ):
        raise ValueError("direct proof prior observation does not match fact identity")
    if not proof.prior_observation_witness._matches(
        state.seen_fact_map_commitment,
        _encode_execution_fact_key(proof.fact.key),
        (
            proof.prior_observation.commitment
            if proof.prior_observation is not None
            else None
        ),
    ):
        raise ValueError("direct proof prior membership does not match state")
    if proof.root_head is not None:
        if (
            proof.root_head.root_key != proof.fact.root_key
            or proof.root_head.scope.position_scope != state.scope
        ):
            raise ValueError("direct proof root head is outside the exact state")
    if not proof.root_head_witness._matches(
        state.root_head_map_commitment,
        _encode_root_fill_key(proof.fact.root_key),
        proof.root_head.commitment if proof.root_head is not None else None,
    ):
        raise ValueError("direct proof root membership does not match state")
    if proof.predecessor_observation is not None:
        if type(proof.fact) not in {BrokerTradeCorrectFact, BrokerTradeBustFact}:
            raise ValueError("only a revision may carry a predecessor observation")
        revision_fact = cast(BrokerTradeCorrectFact | BrokerTradeBustFact, proof.fact)
        if (
            proof.predecessor_observation.fact.key.source_event_id
            != revision_fact.predecessor_source_event_id
        ):
            raise ValueError("direct proof predecessor does not match revision")
    if type(proof.fact) in {BrokerTradeCorrectFact, BrokerTradeBustFact}:
        revision_fact = cast(BrokerTradeCorrectFact | BrokerTradeBustFact, proof.fact)
        predecessor_key = ExecutionFactKey(
            broker=revision_fact.key.broker,
            environment=revision_fact.key.environment,
            account=revision_fact.key.account,
            source_event_id=revision_fact.predecessor_source_event_id,
        )
        if proof.predecessor_observation_witness is None or not (
            proof.predecessor_observation_witness._matches(
                state.seen_fact_map_commitment,
                _encode_execution_fact_key(predecessor_key),
                (
                    proof.predecessor_observation.commitment
                    if proof.predecessor_observation is not None
                    else None
                ),
            )
        ):
            raise ValueError("direct proof predecessor membership does not match state")
    elif proof.predecessor_observation_witness is not None:
        raise ValueError("only a revision may carry a predecessor witness")
    if not proof.root_claim_witness._matches(
        state.root_claim_map_commitment,
        _encode_root_fill_key(proof.fact.root_key),
        _commit_root_fill_key(proof.fact.root_key) if proof.root_claimed else None,
    ):
        raise ValueError("direct proof root claim membership does not match state")
    return state


def _m2_tail_proof_is_valid(
    state: _M2ExecutionState,
    head: RootHead,
) -> bool:
    """Validate the bounded tail proof against one direct current root row."""

    fold_input = state.tail_fold_input
    return bool(
        fold_input is not None
        and fold_input.is_bound
        and state.root_count > 0
        and head.original_sequence == state.root_count - 1
        and fold_input.position_scope == state.scope
        and fold_input.tail_root_key == head.root_key
        and fold_input.prefix_count == head.original_sequence
        and fold_input.prefix_heads_commitment == head.prefix_heads_commitment
        and fold_input.commitment == head.prefix_proof_commitment
        and fold_input.raw_quantity == state.raw_quantity - head.signed_quantity
    )


def _m2_apply_broker_execution_fact(
    state: _M2ExecutionState,
    proof: _M2ExecutionObservationProof,
) -> tuple[TransitionDisposition, FirstObservationClassification]:
    """Classify broker economics from bounded state plus exact direct proof."""

    state = _m2_execution_state_from_direct_proof(state, proof)
    fact = proof.fact
    prior = proof.prior_observation
    if prior is not None:
        if prior.position_scope != state.scope:
            if prior.fact != fact:
                return (
                    TransitionDisposition.FACT_CONFLICT,
                    prior.classification,
                )
            return (
                TransitionDisposition.RECONCILIATION_REQUIRED,
                prior.classification,
            )
        if prior.fact == fact:
            return TransitionDisposition.EXACT_REPLAY, prior.classification
        return TransitionDisposition.FACT_CONFLICT, prior.classification

    if type(fact) is BrokerFillFact:
        if (
            fact.scope.position_scope != state.scope
            or proof.root_head is not None
            or proof.root_claimed
        ):
            return (
                TransitionDisposition.RECONCILIATION_REQUIRED,
                FirstObservationClassification.RECONCILIATION_REQUIRED,
            )
        quantity_delta = (
            fact.quantity.value
            if fact.scope.side is ExecutionSide.BUY
            else -fact.quantity.value
        )
        next_raw_quantity = state.raw_quantity + quantity_delta
        pending = True
        if (
            state.basis_authority is BasisAuthority.AVAILABLE
            and state.cost_basis is not None
            and _metadata_accepts(state.basis_price_metadata, fact.price)
        ):
            folded_quantity, _ = _fold_one(
                state.raw_quantity,
                state.cost_basis.value,
                fact.scope.side,
                fact.quantity.value,
                fact.price,
            )
            pending = folded_quantity != next_raw_quantity
        return (
            TransitionDisposition.APPLIED,
            _classification(pending=pending, raw_quantity=next_raw_quantity),
        )

    head = proof.root_head
    predecessor = proof.predecessor_observation
    revision_fact = cast(BrokerTradeCorrectFact | BrokerTradeBustFact, fact)
    if (
        revision_fact.scope.position_scope != state.scope
        or head is None
        or head.authority is not ExecutionAuthority.BROKER_AUTHORITATIVE
        or head.scope != revision_fact.scope
        or head.current_source_event_id != revision_fact.predecessor_source_event_id
        or predecessor is None
        or predecessor.classification
        is FirstObservationClassification.RECONCILIATION_REQUIRED
        or not _observation_matches_head(predecessor, head)
    ):
        return (
            TransitionDisposition.RECONCILIATION_REQUIRED,
            FirstObservationClassification.RECONCILIATION_REQUIRED,
        )
    revised_quantity, revised_price = _revision_economics(revision_fact)
    signed_change = revised_quantity.value - head.quantity.value
    if head.scope.side is ExecutionSide.SELL:
        signed_change = -signed_change
    next_raw_quantity = state.raw_quantity + signed_change
    pending = True
    if (
        state.basis_authority is BasisAuthority.AVAILABLE
        and state.cost_basis is not None
        and _m2_tail_proof_is_valid(state, head)
        and _metadata_accepts(
            state.tail_fold_input.price_metadata
            if state.tail_fold_input is not None
            else None,
            revised_price,
        )
    ):
        assert state.tail_fold_input is not None
        folded_quantity, _ = _fold_one(
            state.tail_fold_input.raw_quantity,
            state.tail_fold_input.cost_basis.value,
            head.scope.side,
            revised_quantity.value,
            revised_price,
        )
        pending = folded_quantity != next_raw_quantity
    return (
        TransitionDisposition.APPLIED,
        _classification(pending=pending, raw_quantity=next_raw_quantity),
    )


def _snapshot_parts_share_binding(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    *,
    require_integrity: bool,
) -> bool:
    if (
        type(position) is not PositionState
        or type(integrity) is not PositionIntegrity
        or type(root_heads) is not RootHeadIndex
        or type(seen_facts) is not SeenFactIndex
        or type(position.scope) is not PositionScope
        or (
            root_heads.position_scope is not None
            and type(root_heads.position_scope) is not PositionScope
        )
    ):
        return False
    binding = position.binding
    if (
        type(binding) is not _SnapshotBinding
        or root_heads.binding is not binding
        or seen_facts.binding is not binding
    ):
        return False
    if (
        type(binding.position_scope) is not PositionScope
        or binding.position_scope != position.scope
        or binding.position_commitment != position.commitment
        or binding.root_heads_commitment != root_heads.commitment
        or binding.seen_facts_commitment != seen_facts.commitment
        or root_heads.position_scope != position.scope
        or not seen_facts.belongs_to(position.scope)
        or type(binding.account_reconciliation_required) is not bool
        or type(binding.reconciliation_transition_count) is not int
        or binding.reconciliation_transition_count < 0
        or type(binding.reconciliation_transition_head) is not bytes
        or len(binding.reconciliation_transition_head) != 32
        or position.raw_quantity != root_heads.signed_quantity
        or position.root_count != root_heads.count
        or position._root_fill_sequence is not root_heads._root_sequence
        or position._effective_head_ids is not root_heads._head_sequence
        or binding.snapshot_commitment
        != _commit_parts(
            b"execution-core/kernel-snapshot/v2",
            _encode_position_scope(position.scope),
            position.commitment,
            root_heads.commitment,
            seen_facts.commitment,
            _encode_int(binding.integrity_bits),
            _encode_int(int(binding.account_reconciliation_required)),
            _encode_int(binding.reconciliation_transition_count),
            binding.reconciliation_transition_head,
        )
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


def _inherited_account_reconciliation_required(
    position: PositionState,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
) -> bool:
    """Preserve a sticky account restriction from any trusted bound component."""

    return any(
        binding.account_reconciliation_required
        for binding in (
            position.binding,
            root_heads.binding,
            seen_facts.binding,
        )
        if binding is not None
    )


def _inherited_reconciliation_cursors(
    position: PositionState,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
) -> set[tuple[int, bytes]]:
    return {
        (
            binding.reconciliation_transition_count,
            binding.reconciliation_transition_head,
        )
        for binding in (
            position.binding,
            root_heads.binding,
            seen_facts.binding,
        )
        if binding is not None
    }


def _bind_components(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    *,
    account_reconciliation_required: bool | None = None,
    reconciliation_transition_count: int | None = None,
    reconciliation_transition_head: bytes | None = None,
) -> ExecutionSnapshot:
    _require_execution_components(position, integrity, root_heads, seen_facts)
    if (
        account_reconciliation_required is not None
        and type(account_reconciliation_required) is not bool
    ):
        raise TypeError("account_reconciliation_required must be bool or None")
    inherited_account_reconciliation = _inherited_account_reconciliation_required(
        position,
        root_heads,
        seen_facts,
    )
    account_reconciliation_required = bool(
        inherited_account_reconciliation or account_reconciliation_required
    )
    if (reconciliation_transition_count is None) != (
        reconciliation_transition_head is None
    ):
        raise ValueError("reconciliation cursor fields must be supplied together")
    inherited_cursors = _inherited_reconciliation_cursors(
        position,
        root_heads,
        seen_facts,
    )
    if reconciliation_transition_count is None:
        if len(inherited_cursors) > 1:
            raise ValueError(
                "execution components carry divergent reconciliation cursors"
            )
        if inherited_cursors:
            (
                reconciliation_transition_count,
                reconciliation_transition_head,
            ) = next(iter(inherited_cursors))
        else:
            reconciliation_transition_count = 0
            reconciliation_transition_head = _RECONCILIATION_GENESIS_HEAD
    if (
        type(reconciliation_transition_count) is not int
        or reconciliation_transition_count < 0
    ):
        raise ValueError(
            "reconciliation_transition_count must be a non-negative exact integer"
        )
    if (
        type(reconciliation_transition_head) is not bytes
        or len(reconciliation_transition_head) != 32
    ):
        raise ValueError("reconciliation_transition_head must contain exactly 32 bytes")
    for inherited_count, inherited_head in inherited_cursors:
        if reconciliation_transition_count < inherited_count or (
            reconciliation_transition_count == inherited_count
            and reconciliation_transition_head != inherited_head
        ):
            raise ValueError("reconciliation cursor cannot roll back or fork")
    seen_facts = seen_facts._for_position_scope(position.scope)
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
        b"execution-core/kernel-snapshot/v2",
        _encode_position_scope(position.scope),
        position.commitment,
        root_heads.commitment,
        seen_facts.commitment,
        _encode_int(integrity.value),
        _encode_int(int(account_reconciliation_required)),
        _encode_int(reconciliation_transition_count),
        reconciliation_transition_head,
    )
    binding = _SnapshotBinding(
        position_scope=position.scope,
        position_commitment=position.commitment,
        root_heads_commitment=root_heads.commitment,
        seen_facts_commitment=seen_facts.commitment,
        integrity_bits=integrity.value,
        account_reconciliation_required=account_reconciliation_required,
        reconciliation_transition_count=reconciliation_transition_count,
        reconciliation_transition_head=reconciliation_transition_head,
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


def _project_execution_registry(
    target: ExecutionSnapshot,
    source: ExecutionSnapshot,
    *,
    reconciliation_transition_count: int,
    reconciliation_transition_head: bytes,
) -> ExecutionSnapshot:
    """Project a proven account-registry extension onto unchanged symbol state."""

    if type(target) is not ExecutionSnapshot:
        raise TypeError("target must be the exact ExecutionSnapshot type")
    if type(source) is not ExecutionSnapshot:
        raise TypeError("source must be the exact ExecutionSnapshot type")
    _require_execution_components(
        target.position,
        target.integrity,
        target.root_heads,
        target.seen_facts,
    )
    _require_execution_components(
        source.position,
        source.integrity,
        source.root_heads,
        source.seen_facts,
    )
    target_scope = target.position.scope
    source_scope = source.position.scope
    if (
        target_scope.broker != source_scope.broker
        or target_scope.environment != source_scope.environment
        or target_scope.account != source_scope.account
    ):
        raise ValueError("execution registries belong to different accounts")
    if not source.seen_facts.has_prefix(
        target.seen_facts.count,
        target.seen_facts.commitment,
    ):
        raise ValueError("source registry is not a monotonic target extension")
    return _bind_components(
        target.position,
        target.integrity,
        target.root_heads,
        source.seen_facts,
        account_reconciliation_required=(
            target.account_reconciliation_required
            or source.account_reconciliation_required
        ),
        reconciliation_transition_count=reconciliation_transition_count,
        reconciliation_transition_head=reconciliation_transition_head,
    )


def _latch_execution_integrity(
    execution: ExecutionSnapshot,
    evidence: PositionIntegrity,
) -> ExecutionSnapshot:
    """Return the same exact economics with additional sticky integrity evidence."""

    if type(execution) is not ExecutionSnapshot:
        raise TypeError("execution must be the exact ExecutionSnapshot type")
    if type(evidence) is not PositionIntegrity:
        raise TypeError("evidence must be the exact PositionIntegrity type")
    return _bind_components(
        execution.position,
        execution.integrity | evidence,
        execution.root_heads,
        execution.seen_facts,
    )


def _latch_account_execution_reconciliation(
    execution: ExecutionSnapshot,
) -> ExecutionSnapshot:
    """Latch account-wide unattributed canonical truth into an exact snapshot."""

    if type(execution) is not ExecutionSnapshot:
        raise TypeError("execution must be the exact ExecutionSnapshot type")
    if execution.account_reconciliation_required:
        return execution
    return _bind_components(
        execution.position,
        execution.integrity,
        execution.root_heads,
        execution.seen_facts,
        account_reconciliation_required=True,
    )


def _bind_execution_reconciliation_cursor(
    execution: ExecutionSnapshot,
    *,
    transition_count: int,
    transition_head: bytes,
    account_reconciliation_required: bool,
) -> ExecutionSnapshot:
    """Advance one exact snapshot to a venue-verified account cursor."""

    if type(execution) is not ExecutionSnapshot:
        raise TypeError("execution must be the exact ExecutionSnapshot type")
    return _bind_components(
        execution.position,
        execution.integrity,
        execution.root_heads,
        execution.seen_facts,
        account_reconciliation_required=account_reconciliation_required,
        reconciliation_transition_count=transition_count,
        reconciliation_transition_head=transition_head,
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
    if type(fact) in {BrokerFillFact, HumanAttestedFillFact}:
        root_fact = cast(CanonicalRootFillFact, fact)
        return root_fact.quantity == head.quantity and root_fact.price == head.price
    if type(fact) is BrokerTradeCorrectFact:
        correction = cast(BrokerTradeCorrectFact, fact)
        return (
            correction.revised_quantity == head.quantity
            and correction.revised_price == head.price
        )
    bust = cast(BrokerTradeBustFact, fact)
    return head.quantity.value == 0 and bust.reported_price == head.price


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
    fact: CanonicalExecutionFact,
) -> ExecutionTransition:
    classification = FirstObservationClassification.RECONCILIATION_REQUIRED
    next_integrity = integrity | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    next_seen = seen_facts.add(
        SeenFact(
            fact=fact,
            classification=classification,
            position_scope=position.scope,
        )
    )
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
    fact: CanonicalExecutionFact,
) -> ExecutionTransition:
    observation = seen_facts.get(fact.key)
    original_classification = (
        observation.classification
        if observation is not None
        else FirstObservationClassification.RECONCILIATION_REQUIRED
    )
    next_seen = seen_facts
    registry_matches_position = (
        seen_facts.account_scope is None or seen_facts.belongs_to(position.scope)
    )
    if observation is None and registry_matches_position:
        next_seen = seen_facts.add(
            SeenFact(
                fact=fact,
                classification=FirstObservationClassification.RECONCILIATION_REQUIRED,
                position_scope=position.scope,
            )
        )
    trusted_integrity = integrity | position.integrity_floor
    root_matches_position = root_heads.position_scope == position.scope
    trusted_bindings = []
    position_binding = position.binding
    if (
        position_binding is not None
        and position_binding.position_scope == position.scope
    ):
        trusted_bindings.append(position_binding)
    root_binding = root_heads.binding
    if (
        root_matches_position
        and root_binding is not None
        and root_binding.position_scope == position.scope
    ):
        trusted_bindings.append(root_binding)
    if registry_matches_position:
        seen_binding = seen_facts.binding
        if seen_binding is not None and seen_binding.position_scope == position.scope:
            trusted_bindings.append(seen_binding)
    for binding in trusted_bindings:
        trusted_integrity |= PositionIntegrity(binding.integrity_bits)
    if position.raw_quantity < 0 or (
        root_matches_position and root_heads.signed_quantity < 0
    ):
        trusted_integrity |= PositionIntegrity.OVERFILL_QUARANTINE
    if seen_facts.has_overfill_observation(position.scope):
        trusted_integrity |= PositionIntegrity.OVERFILL_QUARANTINE
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
    fact: CanonicalRootFillFact,
) -> ExecutionTransition:
    prior_binding = position.binding
    if prior_binding is None:
        raise RuntimeError("coherent root-fill transition requires a bound snapshot")
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
    next_seen = seen_facts.add(
        SeenFact(
            fact=fact,
            classification=classification,
            position_scope=position.scope,
        )
    )
    snapshot = _bind_components(
        next_position,
        next_integrity,
        next_roots,
        next_seen,
        account_reconciliation_required=(prior_binding.account_reconciliation_required),
        reconciliation_transition_count=(prior_binding.reconciliation_transition_count),
        reconciliation_transition_head=(prior_binding.reconciliation_transition_head),
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
    if type(fact) is BrokerTradeCorrectFact:
        correction = cast(BrokerTradeCorrectFact, fact)
        return correction.revised_quantity, correction.revised_price
    bust = cast(BrokerTradeBustFact, fact)
    return Quantity(0), bust.reported_price


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
    prior_binding = position.binding
    if prior_binding is None:
        raise RuntimeError("coherent revision transition requires a bound snapshot")
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
        prefix_heads_commitment=head.prefix_heads_commitment,
        prefix_proof_commitment=head.prefix_proof_commitment,
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
    next_seen = seen_facts.add(
        SeenFact(
            fact=fact,
            classification=classification,
            position_scope=position.scope,
        )
    )
    snapshot = _bind_components(
        next_position,
        next_integrity,
        next_roots,
        next_seen,
        account_reconciliation_required=(prior_binding.account_reconciliation_required),
        reconciliation_transition_count=(prior_binding.reconciliation_transition_count),
        reconciliation_transition_head=(prior_binding.reconciliation_transition_head),
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


def _require_execution_components(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
) -> None:
    if type(position) is not PositionState:
        raise TypeError("position must be PositionState (exact type required)")
    if type(integrity) is not PositionIntegrity:
        raise TypeError("integrity must be PositionIntegrity (exact type required)")
    if type(root_heads) is not RootHeadIndex:
        raise TypeError("root_heads must be RootHeadIndex (exact type required)")
    if type(seen_facts) is not SeenFactIndex:
        raise TypeError("seen_facts must be SeenFactIndex (exact type required)")
    if type(position.scope) is not PositionScope:
        raise TypeError("position scope must be the exact PositionScope type")
    if (
        root_heads.position_scope is not None
        and type(root_heads.position_scope) is not PositionScope
    ):
        raise TypeError("root-head scope must be the exact PositionScope type")


def _apply_canonical_execution_fact(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    fact: CanonicalExecutionFact,
    *,
    m2_classification: tuple[
        TransitionDisposition,
        FirstObservationClassification,
    ]
    | None = None,
) -> ExecutionTransition:
    if not _snapshot_is_coherent(position, integrity, root_heads, seen_facts):
        return _incoherent_snapshot_transition(
            position,
            integrity,
            root_heads,
            seen_facts,
            fact,
        )

    if m2_classification is not None:
        if (
            type(m2_classification) is not tuple
            or len(m2_classification) != 2
            or type(m2_classification[0]) is not TransitionDisposition
            or type(m2_classification[1]) is not FirstObservationClassification
        ):
            raise TypeError("m2_classification must be one exact disposition pair")
        disposition, original_classification = m2_classification
        first_observation = seen_facts.get(fact.key)
        if first_observation is not None:
            next_integrity = integrity
            if first_observation.position_scope != position.scope:
                next_integrity |= PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
            if disposition is TransitionDisposition.FACT_CONFLICT:
                next_integrity |= PositionIntegrity.EXECUTION_FACT_CONFLICT
            if disposition is TransitionDisposition.APPLIED:
                raise RuntimeError("M2 classification cannot apply an existing fact")
            return _unchanged_transition(
                position,
                next_integrity,
                root_heads,
                seen_facts,
                disposition=disposition,
                original_classification=original_classification,
            )
        if disposition is TransitionDisposition.RECONCILIATION_REQUIRED:
            return _reconciliation_transition(
                position,
                integrity,
                root_heads,
                seen_facts,
                fact,
            )
        if disposition is not TransitionDisposition.APPLIED:
            raise RuntimeError(
                "M2 classification requires a retained first observation"
            )
        transition = (
            _apply_root_fill(
                position,
                integrity,
                root_heads,
                seen_facts,
                cast(CanonicalRootFillFact, fact),
            )
            if type(fact) is BrokerFillFact
            else _apply_revision(
                position,
                integrity,
                root_heads,
                seen_facts,
                cast(BrokerTradeCorrectFact | BrokerTradeBustFact, fact),
            )
        )
        if (
            transition.disposition is not disposition
            or transition.original_classification is not original_classification
        ):
            raise RuntimeError("M2 execution classification disagrees with transition")
        return transition

    first_observation = seen_facts.get(fact.key)
    if first_observation is not None:
        if first_observation.position_scope != position.scope:
            next_integrity = (
                integrity | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
            )
            disposition = TransitionDisposition.RECONCILIATION_REQUIRED
            if first_observation.fact != fact:
                next_integrity |= PositionIntegrity.EXECUTION_FACT_CONFLICT
                disposition = TransitionDisposition.FACT_CONFLICT
            return _unchanged_transition(
                position,
                next_integrity,
                root_heads,
                seen_facts,
                disposition=disposition,
                original_classification=first_observation.classification,
            )
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

    if type(fact) in {BrokerFillFact, HumanAttestedFillFact}:
        return _apply_root_fill(
            position,
            integrity,
            root_heads,
            seen_facts,
            cast(CanonicalRootFillFact, fact),
        )
    return _apply_revision(
        position,
        integrity,
        root_heads,
        seen_facts,
        cast(BrokerTradeCorrectFact | BrokerTradeBustFact, fact),
    )


def apply_broker_execution_fact(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    fact: BrokerExecutionFact,
) -> ExecutionTransition:
    """Apply one canonical broker fact without I/O or an ordered history fold."""

    _require_execution_components(position, integrity, root_heads, seen_facts)
    if type(fact) not in {
        BrokerFillFact,
        BrokerTradeCorrectFact,
        BrokerTradeBustFact,
    }:
        raise TypeError("fact must be an exact canonical broker execution fact")
    if not _snapshot_is_coherent(position, integrity, root_heads, seen_facts):
        return _incoherent_snapshot_transition(
            position,
            integrity,
            root_heads,
            seen_facts,
            fact,
        )
    snapshot = ExecutionSnapshot(
        position=position,
        integrity=integrity,
        root_heads=root_heads,
        seen_facts=seen_facts,
    )
    state = _m2_execution_state_from_snapshot(snapshot)
    proof = _M2ExecutionObservationProof.from_snapshot(state, snapshot, fact)
    m2_classification = _m2_apply_broker_execution_fact(state, proof)
    return _apply_canonical_execution_fact(
        position,
        integrity,
        root_heads,
        seen_facts,
        fact,
        m2_classification=m2_classification,
    )


def _apply_human_attested_fill_fact(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    fact: HumanAttestedFillFact,
) -> ExecutionTransition:
    """Apply one already venue-authorized human root through the canonical fold."""

    _require_execution_components(position, integrity, root_heads, seen_facts)
    if type(fact) is not HumanAttestedFillFact:
        raise TypeError("fact must be the exact HumanAttestedFillFact type")
    return _apply_canonical_execution_fact(
        position,
        integrity,
        root_heads,
        seen_facts,
        fact,
    )


def _record_execution_reconciliation(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    fact: BrokerFillFact,
) -> ExecutionTransition:
    """Record broker evidence that recovery proved unsafe to apply economically."""

    _require_execution_components(position, integrity, root_heads, seen_facts)
    if type(fact) is not BrokerFillFact:
        raise TypeError("fact must be the exact BrokerFillFact type")
    if not _snapshot_is_coherent(position, integrity, root_heads, seen_facts):
        return _incoherent_snapshot_transition(
            position,
            integrity,
            root_heads,
            seen_facts,
            fact,
        )

    first_observation = seen_facts.get(fact.key)
    if first_observation is None:
        return _reconciliation_transition(
            position,
            integrity,
            root_heads,
            seen_facts,
            fact,
        )
    if first_observation.fact != fact:
        return _unchanged_transition(
            position,
            integrity
            | PositionIntegrity.EXECUTION_FACT_CONFLICT
            | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED,
            root_heads,
            seen_facts,
            disposition=TransitionDisposition.FACT_CONFLICT,
            original_classification=first_observation.classification,
        )
    return _unchanged_transition(
        position,
        integrity | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED,
        root_heads,
        seen_facts,
        disposition=TransitionDisposition.RECONCILIATION_REQUIRED,
        original_classification=first_observation.classification,
    )


def _record_broker_corroboration(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    fact: BrokerFillFact,
) -> ExecutionTransition:
    """Reserve exact broker evidence already covered by another economic root.

    The reservation makes a later public broker application of the same fact an
    exact replay without manufacturing a second position delta or a
    reconciliation latch.
    """

    _require_execution_components(position, integrity, root_heads, seen_facts)
    if type(fact) is not BrokerFillFact:
        raise TypeError("fact must be the exact BrokerFillFact type")
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

    if seen_facts.contains_root(fact.root_key):
        return _record_execution_reconciliation(
            position,
            integrity,
            root_heads,
            seen_facts,
            fact,
        )

    classification = FirstObservationClassification.CORROBORATED_ZERO_ECONOMIC
    next_seen = seen_facts.add(
        SeenFact(
            fact=fact,
            classification=classification,
            position_scope=position.scope,
        )
    )
    snapshot = _bind_components(position, integrity, root_heads, next_seen)
    return ExecutionTransition(
        position=snapshot.position,
        integrity=snapshot.integrity,
        root_heads=snapshot.root_heads,
        seen_facts=snapshot.seen_facts,
        quantity_delta=0,
        basis_delta=Fraction(0),
        disposition=TransitionDisposition.APPLIED,
        original_classification=classification,
    )


def _replay_hydration_snapshot(
    scope: PositionScope,
    seen_facts: SeenFactIndex,
) -> ExecutionSnapshot:
    """Re-derive one symbol from the account-wide observation high-water."""

    account_seen = SeenFactIndex.empty(scope)
    symbol_snapshots: dict[PositionScope, ExecutionSnapshot] = {}
    for observation in seen_facts.entries:
        observation_scope = observation.position_scope
        if observation_scope is None:
            raise ValueError("seen fact has no evaluation position scope")
        replayed = symbol_snapshots.get(observation_scope)
        if replayed is None:
            replayed = ExecutionSnapshot.flat(observation_scope)
        replayed = _bind_components(
            replayed.position,
            replayed.integrity,
            replayed.root_heads,
            account_seen,
        )
        if type(observation.fact) not in {
            BrokerFillFact,
            BrokerTradeCorrectFact,
            BrokerTradeBustFact,
        }:
            raise ValueError("public hydration admits broker-authoritative facts only")
        if (
            observation.classification
            is FirstObservationClassification.CORROBORATED_ZERO_ECONOMIC
        ):
            raise ValueError(
                "public hydration does not admit zero-economic corroboration"
            )
        broker_fact = cast(BrokerExecutionFact, observation.fact)
        transition = apply_broker_execution_fact(
            replayed.position,
            replayed.integrity,
            replayed.root_heads,
            replayed.seen_facts,
            broker_fact,
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
        account_seen = transition.seen_facts
        symbol_snapshots[observation_scope] = ExecutionSnapshot(
            position=transition.position,
            integrity=transition.integrity,
            root_heads=transition.root_heads,
            seen_facts=transition.seen_facts,
        )
    replayed = symbol_snapshots.get(scope)
    if replayed is None:
        replayed = ExecutionSnapshot.flat(scope)
    replayed = _bind_components(
        replayed.position,
        replayed.integrity,
        replayed.root_heads,
        account_seen,
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
    historical_proof_mismatch = any(
        (
            supplied.prefix_heads_commitment,
            supplied.prefix_proof_commitment,
        )
        != (
            expected.prefix_heads_commitment,
            expected.prefix_proof_commitment,
        )
        for supplied, expected in zip(supplied_heads[:-1], replayed_heads[:-1])
    )
    supplied_proofs_fully_absent = all(
        not head.prefix_heads_commitment and not head.prefix_proof_commitment
        for head in supplied_heads
    )
    if historical_proof_mismatch and not supplied_proofs_fully_absent:
        raise ValueError("historical root proof does not match chronological replay")

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

    if type(position_snapshot) is not PositionState:
        raise TypeError("position_snapshot must be PositionState")
    if type(root_heads) is not RootHeadIndex:
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
