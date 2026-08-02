"""Immutable broker execution facts and their exact lineage indexes.

This module normalizes only the canonical fill family.  It deliberately owns no
position arithmetic and performs no I/O: the reducer in :mod:`.position` consumes
these values as explicit inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from hashlib import sha256
from typing import Callable, Generic, TypeAlias, TypeVar, cast

from .identity import (
    AccountId,
    ActorId,
    BrokerId,
    ClaimOccurrenceId,
    EvidenceReference,
    EnvironmentId,
    ExecutionFactKey,
    OrderId,
    RootFillId,
    RootFillKey,
    SourceEventId,
    SymbolId,
    RequestOccurrenceId,
    VenueLegKey,
)
from .values import Quantity, ReportedPrice


_ValueT = TypeVar("_ValueT")
_AccountScope: TypeAlias = tuple[BrokerId, EnvironmentId, AccountId]


def _pack_parts(domain: bytes, *parts: bytes) -> bytes:
    """Return versioned, length-prefixed canonical bytes without hashing."""

    packed = len(domain).to_bytes(4, "big") + domain
    for part in parts:
        packed += len(part).to_bytes(8, "big") + part
    return packed


def _commit_parts(domain: bytes, *parts: bytes) -> bytes:
    """Return a deterministic domain-separated commitment to exact byte parts."""

    return sha256(_pack_parts(domain, *parts)).digest()


def _encode_int(value: int) -> bytes:
    if type(value) is not int:
        raise TypeError("canonical integer must be an exact integer")
    magnitude = abs(value)
    encoded = magnitude.to_bytes(max(1, (magnitude.bit_length() + 7) // 8), "big")
    return (
        (b"\x01" if value < 0 else b"\x00") + len(encoded).to_bytes(4, "big") + encoded
    )


def _encode_text(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(8, "big") + encoded


def _encode_fraction(value: Fraction) -> bytes:
    if not isinstance(value, Fraction):
        raise TypeError("canonical rational must be Fraction")
    return _commit_parts(
        b"execution-core/fraction/v1",
        _encode_int(value.numerator),
        _encode_int(value.denominator),
    )


def _encode_reported_price(value: ReportedPrice | None) -> bytes:
    if value is None:
        return _commit_parts(b"execution-core/reported-price/none/v1")
    if not isinstance(value, ReportedPrice):
        raise TypeError("canonical reported price must be ReportedPrice or None")
    return _commit_parts(
        b"execution-core/reported-price/v1",
        _encode_int(value.units.value),
        _encode_fraction(Fraction(value.scale.value)),
        _encode_int(value.tick.tick_units.value),
        _encode_fraction(Fraction(value.tick.scale.value)),
    )


class ExecutionSide(Enum):
    """Signed economic direction of a canonical execution fact."""

    BUY = "BUY"
    SELL = "SELL"


class FactKind(Enum):
    """The complete economic fact family admitted by the reset kernel."""

    FILL = "FILL"
    TRADE_CORRECT = "TRADE_CORRECT"
    TRADE_BUST = "TRADE_BUST"


class ExecutionAuthority(Enum):
    """Provenance of an effective root head."""

    BROKER_AUTHORITATIVE = "BROKER_AUTHORITATIVE"
    HUMAN_ATTESTED = "HUMAN_ATTESTED"


class FirstObservationClassification(Enum):
    """Stable replay classification recorded with a first-seen source event."""

    APPLIED_AVAILABLE = "APPLIED_AVAILABLE"
    APPLIED_BASIS_PENDING = "APPLIED_BASIS_PENDING"
    APPLIED_OVERFILL_QUARANTINE = "APPLIED_OVERFILL_QUARANTINE"
    APPLIED_PENDING_OVERFILL = "APPLIED_PENDING_OVERFILL"
    CORROBORATED_ZERO_ECONOMIC = "CORROBORATED_ZERO_ECONOMIC"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


@dataclass(frozen=True, slots=True)
class PositionScope:
    """Exact venue/account/symbol owner of one position kernel snapshot."""

    broker: BrokerId
    environment: EnvironmentId
    account: AccountId
    symbol_id: SymbolId

    def __post_init__(self) -> None:
        _require_type("broker", self.broker, BrokerId)
        _require_type("environment", self.environment, EnvironmentId)
        _require_type("account", self.account, AccountId)
        _require_type("symbol_id", self.symbol_id, SymbolId)


@dataclass(frozen=True, slots=True)
class ExecutionScope:
    """Complete venue/account/order/symbol/side scope for one execution fact."""

    broker: BrokerId
    environment: EnvironmentId
    account: AccountId
    order_id: OrderId
    symbol_id: SymbolId
    side: ExecutionSide

    def __post_init__(self) -> None:
        _require_type("broker", self.broker, BrokerId)
        _require_type("environment", self.environment, EnvironmentId)
        _require_type("account", self.account, AccountId)
        _require_type("order_id", self.order_id, OrderId)
        _require_type("symbol_id", self.symbol_id, SymbolId)
        _require_type("side", self.side, ExecutionSide)

    @property
    def position_scope(self) -> PositionScope:
        return PositionScope(
            broker=self.broker,
            environment=self.environment,
            account=self.account,
            symbol_id=self.symbol_id,
        )


def _require_type(name: str, value: object, expected: type[object]) -> None:
    if not isinstance(value, expected):
        raise TypeError(f"{name} must be {expected.__name__}")


def _encode_position_scope(scope: PositionScope) -> bytes:
    _require_type("scope", scope, PositionScope)
    return _pack_parts(
        b"execution-core/position-scope/v1",
        _encode_text(scope.broker.value),
        _encode_text(scope.environment.value),
        _encode_text(scope.account.value),
        _encode_text(scope.symbol_id.value),
    )


def _encode_execution_scope(scope: ExecutionScope) -> bytes:
    _require_type("scope", scope, ExecutionScope)
    return _pack_parts(
        b"execution-core/execution-scope/v1",
        _encode_position_scope(scope.position_scope),
        _encode_text(scope.order_id.value),
        _encode_text(scope.side.value),
    )


def _account_scope_from_position(scope: PositionScope) -> _AccountScope:
    _require_type("scope", scope, PositionScope)
    return (scope.broker, scope.environment, scope.account)


def _encode_account_scope(scope: _AccountScope | None) -> bytes:
    if scope is None:
        return _commit_parts(b"execution-core/account-scope/none/v1")
    broker, environment, account = scope
    return _pack_parts(
        b"execution-core/account-scope/v1",
        _encode_text(broker.value),
        _encode_text(environment.value),
        _encode_text(account.value),
    )


def _encode_root_fill_key(key: RootFillKey) -> bytes:
    _require_type("root_key", key, RootFillKey)
    return _pack_parts(
        b"execution-core/root-fill-key/v1",
        _encode_text(key.broker.value),
        _encode_text(key.environment.value),
        _encode_text(key.account.value),
        _encode_text(key.root_fill_id.value),
    )


def _encode_execution_fact_key(key: ExecutionFactKey) -> bytes:
    _require_type("key", key, ExecutionFactKey)
    return _pack_parts(
        b"execution-core/execution-fact-key/v1",
        _encode_text(key.broker.value),
        _encode_text(key.environment.value),
        _encode_text(key.account.value),
        _encode_text(key.source_event_id.value),
    )


def _encode_source_event_id(event_id: SourceEventId) -> bytes:
    _require_type("source_event_id", event_id, SourceEventId)
    return _pack_parts(
        b"execution-core/source-event-id/v1",
        _encode_text(event_id.value),
    )


def _commit_root_fill_key(key: RootFillKey) -> bytes:
    return _commit_parts(
        b"execution-core/root-fill-key-commitment/v1", _encode_root_fill_key(key)
    )


def _commit_source_event_id(event_id: SourceEventId) -> bytes:
    return _commit_parts(
        b"execution-core/source-event-id-commitment/v1",
        _encode_source_event_id(event_id),
    )


def _validate_fact_identity(
    key: ExecutionFactKey,
    scope: ExecutionScope,
    root_fill_id: RootFillId,
) -> None:
    _require_type("key", key, ExecutionFactKey)
    _require_type("scope", scope, ExecutionScope)
    _require_type("root_fill_id", root_fill_id, RootFillId)
    if (
        key.broker != scope.broker
        or key.environment != scope.environment
        or key.account != scope.account
    ):
        raise ValueError(
            "execution fact key and scope must have identical broker, "
            "environment, and account"
        )


def _validate_positive_economics(
    quantity: Quantity,
    price: ReportedPrice,
    *,
    quantity_name: str,
    price_name: str,
) -> None:
    _require_type(quantity_name, quantity, Quantity)
    _require_type(price_name, price, ReportedPrice)
    if quantity.value <= 0:
        raise ValueError(f"{quantity_name} must be positive")
    if price.exact_value <= 0:
        raise ValueError(f"{price_name} must be positive")


def _validate_predecessor(
    key: ExecutionFactKey,
    predecessor_source_event_id: SourceEventId,
) -> None:
    _require_type(
        "predecessor_source_event_id",
        predecessor_source_event_id,
        SourceEventId,
    )
    if predecessor_source_event_id == key.source_event_id:
        raise ValueError("a revision cannot name itself as its predecessor")


@dataclass(frozen=True, slots=True)
class _RadixNode(Generic[_ValueT]):
    value: _ValueT | None
    has_value: bool
    value_commitment: bytes
    children: tuple[tuple[int, _RadixNode[_ValueT]], ...]
    children_commitment: bytes
    commitment: bytes


def _radix_edge_commitment(label: int, child_commitment: bytes) -> bytes:
    return _commit_parts(
        b"execution-core/radix-child/v1",
        bytes((label,)),
        child_commitment,
    )


def _xor_commitments(left: bytes, right: bytes) -> bytes:
    return bytes(left_byte ^ right_byte for left_byte, right_byte in zip(left, right))


def _make_radix_node(
    *,
    value: _ValueT | None = None,
    has_value: bool = False,
    value_commitment: bytes = b"",
    children: tuple[tuple[int, _RadixNode[_ValueT]], ...] = (),
    children_commitment: bytes | None = None,
) -> _RadixNode[_ValueT]:
    if children_commitment is None:
        children_commitment = bytes(32)
        for label, child in children:
            children_commitment = _xor_commitments(
                children_commitment,
                _radix_edge_commitment(label, child.commitment),
            )
    commitment = _commit_parts(
        b"execution-core/radix-node/v1",
        b"\x01" if has_value else b"\x00",
        value_commitment if has_value else b"",
        children_commitment,
    )
    return _RadixNode(
        value=value,
        has_value=has_value,
        value_commitment=value_commitment,
        children=children,
        children_commitment=children_commitment,
        commitment=commitment,
    )


def _child_at(
    children: tuple[tuple[int, _RadixNode[_ValueT]], ...],
    label: int,
) -> tuple[int, _RadixNode[_ValueT] | None]:
    low = 0
    high = len(children)
    while low < high:
        middle = (low + high) // 2
        current = children[middle][0]
        if current < label:
            low = middle + 1
        else:
            high = middle
    if low < len(children) and children[low][0] == label:
        return low, children[low][1]
    return low, None


def _set_child(
    parent: _RadixNode[_ValueT],
    label: int,
    child: _RadixNode[_ValueT],
) -> tuple[tuple[tuple[int, _RadixNode[_ValueT]], ...], bytes]:
    children = parent.children
    index, current = _child_at(children, label)
    commitment = parent.children_commitment
    next_edge = _radix_edge_commitment(label, child.commitment)
    if current is None:
        return (
            children[:index] + ((label, child),) + children[index:],
            _xor_commitments(commitment, next_edge),
        )
    current_edge = _radix_edge_commitment(label, current.commitment)
    return (
        children[:index] + ((label, child),) + children[index + 1 :],
        _xor_commitments(_xor_commitments(commitment, current_edge), next_edge),
    )


@dataclass(frozen=True, slots=True)
class _PersistentKeyMap(Generic[_ValueT]):
    """Immutable full-key radix map with history-independent path work."""

    _root: _RadixNode[_ValueT]
    size: int

    @classmethod
    def empty(cls) -> _PersistentKeyMap[_ValueT]:
        return cls(_root=_make_radix_node(), size=0)

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/persistent-map/v1",
            _encode_int(self.size),
            self._root.commitment,
        )

    def get(self, key: bytes) -> _ValueT | None:
        if not isinstance(key, bytes) or not key:
            raise ValueError("persistent-map key must be nonempty bytes")
        node = self._root
        for label in key:
            _, child = _child_at(node.children, label)
            if child is None:
                return None
            node = child
        if not node.has_value:
            return None
        return cast(_ValueT, node.value)

    def _set(
        self,
        key: bytes,
        value: _ValueT,
        value_commitment: bytes,
        *,
        require_existing: bool,
    ) -> _PersistentKeyMap[_ValueT]:
        existing = self.get(key)
        if require_existing and existing is None:
            raise KeyError(key)
        if not require_existing and existing is not None:
            raise ValueError("persistent-map key already exists")

        node = self._root
        parents: list[tuple[_RadixNode[_ValueT], int]] = []
        for label in key:
            parents.append((node, label))
            _, child = _child_at(node.children, label)
            node = child if child is not None else _make_radix_node()

        rebuilt = _make_radix_node(
            value=value,
            has_value=True,
            value_commitment=value_commitment,
            children=node.children,
            children_commitment=node.children_commitment,
        )
        for parent, label in reversed(parents):
            children, children_commitment = _set_child(parent, label, rebuilt)
            rebuilt = _make_radix_node(
                value=parent.value,
                has_value=parent.has_value,
                value_commitment=parent.value_commitment,
                children=children,
                children_commitment=children_commitment,
            )
        return _PersistentKeyMap(
            _root=rebuilt,
            size=self.size if require_existing else self.size + 1,
        )

    def insert_new(
        self,
        key: bytes,
        value: _ValueT,
        value_commitment: bytes,
    ) -> _PersistentKeyMap[_ValueT]:
        return self._set(
            key,
            value,
            value_commitment,
            require_existing=False,
        )

    def replace_existing(
        self,
        key: bytes,
        value: _ValueT,
        value_commitment: bytes,
    ) -> _PersistentKeyMap[_ValueT]:
        return self._set(
            key,
            value,
            value_commitment,
            require_existing=True,
        )


@dataclass(frozen=True, slots=True)
class _PersistentSequence(Generic[_ValueT]):
    """Immutable sequence backed by an eight-level unsigned-index radix."""

    _values: _PersistentKeyMap[_ValueT]
    length: int

    @classmethod
    def empty(cls) -> _PersistentSequence[_ValueT]:
        return cls(_values=_PersistentKeyMap.empty(), length=0)

    @classmethod
    def from_values(
        cls,
        values: tuple[_ValueT, ...],
        value_committer: Callable[[_ValueT], bytes],
    ) -> _PersistentSequence[_ValueT]:
        sequence = cls.empty()
        for value in values:
            sequence = sequence.append(value, value_committer(value))
        return sequence

    @staticmethod
    def _key(index: int) -> bytes:
        if type(index) is not int:
            raise TypeError("sequence index must be an exact integer")
        if index < 0 or index >= 2**64:
            raise IndexError("sequence index is outside unsigned 64-bit range")
        return index.to_bytes(8, "big")

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/persistent-sequence/v1",
            _encode_int(self.length),
            self._values.commitment,
        )

    def get(self, index: int) -> _ValueT:
        if index < 0 or index >= self.length:
            raise IndexError(index)
        value = self._values.get(self._key(index))
        if value is None:
            raise RuntimeError("persistent sequence is internally sparse")
        return value

    def append(
        self,
        value: _ValueT,
        value_commitment: bytes,
    ) -> _PersistentSequence[_ValueT]:
        if self.length >= 2**64:
            raise OverflowError("persistent sequence exhausted unsigned index space")
        return _PersistentSequence(
            _values=self._values.insert_new(
                self._key(self.length),
                value,
                value_commitment,
            ),
            length=self.length + 1,
        )

    def set(
        self,
        index: int,
        value: _ValueT,
        value_commitment: bytes,
    ) -> _PersistentSequence[_ValueT]:
        if index < 0 or index >= self.length:
            raise IndexError(index)
        return _PersistentSequence(
            _values=self._values.replace_existing(
                self._key(index),
                value,
                value_commitment,
            ),
            length=self.length,
        )

    def to_tuple(self) -> tuple[_ValueT, ...]:
        """Materialize only for explicit slow, audit, and reporting paths."""

        return tuple(self.get(index) for index in range(self.length))


@dataclass(frozen=True, slots=True)
class _SnapshotBinding:
    """Shared immutable high-water binding for all kernel snapshot components."""

    position_scope: PositionScope
    position_commitment: bytes
    root_heads_commitment: bytes
    seen_facts_commitment: bytes
    integrity_bits: int
    account_reconciliation_required: bool
    reconciliation_transition_count: int
    reconciliation_transition_head: bytes
    snapshot_commitment: bytes


@dataclass(frozen=True, slots=True)
class BrokerFillFact:
    """A broker-authoritative positive root execution."""

    key: ExecutionFactKey
    scope: ExecutionScope
    root_fill_id: RootFillId
    quantity: Quantity
    price: ReportedPrice

    def __post_init__(self) -> None:
        _validate_fact_identity(self.key, self.scope, self.root_fill_id)
        _validate_positive_economics(
            self.quantity,
            self.price,
            quantity_name="quantity",
            price_name="price",
        )

    @property
    def kind(self) -> FactKind:
        return FactKind.FILL

    @property
    def authority(self) -> ExecutionAuthority:
        return ExecutionAuthority.BROKER_AUTHORITATIVE

    @property
    def root_key(self) -> RootFillKey:
        return RootFillKey(
            broker=self.key.broker,
            environment=self.key.environment,
            account=self.key.account,
            root_fill_id=self.root_fill_id,
        )


@dataclass(frozen=True, slots=True)
class HumanAttestedFillFact:
    """Capacity-gated operator evidence for one exact venue-leg interval.

    Construction proves payload shape only.  Venue ownership, immutable order
    capacity, current cumulative coverage, and long-only position authority are
    revalidated by the venue-recovery reducer before this fact may reach the
    canonical root-fill primitive.
    """

    key: ExecutionFactKey
    scope: ExecutionScope
    root_fill_id: RootFillId
    leg_key: VenueLegKey
    request_occurrence_id: RequestOccurrenceId
    claim_occurrence_id: ClaimOccurrenceId
    quantity: Quantity
    prior_cumulative_quantity: Quantity
    resulting_cumulative_quantity: Quantity
    price: ReportedPrice
    actor: ActorId
    reason: str
    evidence_reference: EvidenceReference

    def __post_init__(self) -> None:
        _validate_fact_identity(self.key, self.scope, self.root_fill_id)
        _require_type("leg_key", self.leg_key, VenueLegKey)
        _require_type(
            "request_occurrence_id",
            self.request_occurrence_id,
            RequestOccurrenceId,
        )
        _require_type(
            "claim_occurrence_id",
            self.claim_occurrence_id,
            ClaimOccurrenceId,
        )
        _validate_positive_economics(
            self.quantity,
            self.price,
            quantity_name="quantity",
            price_name="price",
        )
        _require_type(
            "prior_cumulative_quantity",
            self.prior_cumulative_quantity,
            Quantity,
        )
        _require_type(
            "resulting_cumulative_quantity",
            self.resulting_cumulative_quantity,
            Quantity,
        )
        _require_type("actor", self.actor, ActorId)
        _require_type("evidence_reference", self.evidence_reference, EvidenceReference)
        if type(self.reason) is not str:
            raise TypeError("reason must be a string")
        if not self.reason.strip():
            raise ValueError("reason must be nonblank")

    @property
    def kind(self) -> FactKind:
        return FactKind.FILL

    @property
    def authority(self) -> ExecutionAuthority:
        return ExecutionAuthority.HUMAN_ATTESTED

    @property
    def root_key(self) -> RootFillKey:
        return RootFillKey(
            broker=self.key.broker,
            environment=self.key.environment,
            account=self.key.account,
            root_fill_id=self.root_fill_id,
        )


@dataclass(frozen=True, slots=True)
class BrokerTradeCorrectFact:
    """A broker-authoritative replacement of one root's current head."""

    key: ExecutionFactKey
    scope: ExecutionScope
    root_fill_id: RootFillId
    predecessor_source_event_id: SourceEventId
    revised_quantity: Quantity
    revised_price: ReportedPrice

    def __post_init__(self) -> None:
        _validate_fact_identity(self.key, self.scope, self.root_fill_id)
        _validate_predecessor(self.key, self.predecessor_source_event_id)
        _validate_positive_economics(
            self.revised_quantity,
            self.revised_price,
            quantity_name="revised_quantity",
            price_name="revised_price",
        )

    @property
    def kind(self) -> FactKind:
        return FactKind.TRADE_CORRECT

    @property
    def authority(self) -> ExecutionAuthority:
        return ExecutionAuthority.BROKER_AUTHORITATIVE

    @property
    def root_key(self) -> RootFillKey:
        return RootFillKey(
            broker=self.key.broker,
            environment=self.key.environment,
            account=self.key.account,
            root_fill_id=self.root_fill_id,
        )


@dataclass(frozen=True, slots=True)
class BrokerTradeBustFact:
    """A broker-authoritative replacement whose root economics become zero."""

    key: ExecutionFactKey
    scope: ExecutionScope
    root_fill_id: RootFillId
    predecessor_source_event_id: SourceEventId
    reported_price: ReportedPrice | None = None

    def __post_init__(self) -> None:
        _validate_fact_identity(self.key, self.scope, self.root_fill_id)
        _validate_predecessor(self.key, self.predecessor_source_event_id)
        if self.reported_price is not None:
            _require_type("reported_price", self.reported_price, ReportedPrice)
            if self.reported_price.exact_value <= 0:
                raise ValueError("reported_price must be positive when present")

    @property
    def kind(self) -> FactKind:
        return FactKind.TRADE_BUST

    @property
    def authority(self) -> ExecutionAuthority:
        return ExecutionAuthority.BROKER_AUTHORITATIVE

    @property
    def root_key(self) -> RootFillKey:
        return RootFillKey(
            broker=self.key.broker,
            environment=self.key.environment,
            account=self.key.account,
            root_fill_id=self.root_fill_id,
        )


BrokerExecutionFact: TypeAlias = (
    BrokerFillFact | BrokerTradeCorrectFact | BrokerTradeBustFact
)
CanonicalExecutionFact: TypeAlias = BrokerExecutionFact | HumanAttestedFillFact
CanonicalRootFillFact: TypeAlias = BrokerFillFact | HumanAttestedFillFact


def _encode_execution_fact(fact: CanonicalExecutionFact) -> bytes:
    if isinstance(fact, BrokerFillFact):
        return _commit_parts(
            b"execution-core/broker-fill-fact/v1",
            _encode_execution_fact_key(fact.key),
            _encode_execution_scope(fact.scope),
            _encode_root_fill_key(fact.root_key),
            _encode_int(fact.quantity.value),
            _encode_reported_price(fact.price),
        )
    if isinstance(fact, HumanAttestedFillFact):
        return _commit_parts(
            b"execution-core/human-attested-fill-fact/v1",
            _encode_execution_fact_key(fact.key),
            _encode_execution_scope(fact.scope),
            _encode_root_fill_key(fact.root_key),
            _encode_text(fact.leg_key.broker.value),
            _encode_text(fact.leg_key.environment.value),
            _encode_text(fact.leg_key.account.value),
            _encode_text(fact.leg_key.order_id.value),
            _encode_text(fact.request_occurrence_id.value),
            _encode_text(fact.claim_occurrence_id.value),
            _encode_int(fact.quantity.value),
            _encode_int(fact.prior_cumulative_quantity.value),
            _encode_int(fact.resulting_cumulative_quantity.value),
            _encode_reported_price(fact.price),
            _encode_text(fact.actor.value),
            _encode_text(fact.reason),
            _encode_text(fact.evidence_reference.value),
        )
    if isinstance(fact, BrokerTradeCorrectFact):
        return _commit_parts(
            b"execution-core/broker-correct-fact/v1",
            _encode_execution_fact_key(fact.key),
            _encode_execution_scope(fact.scope),
            _encode_root_fill_key(fact.root_key),
            _encode_source_event_id(fact.predecessor_source_event_id),
            _encode_int(fact.revised_quantity.value),
            _encode_reported_price(fact.revised_price),
        )
    if isinstance(fact, BrokerTradeBustFact):
        return _commit_parts(
            b"execution-core/broker-bust-fact/v1",
            _encode_execution_fact_key(fact.key),
            _encode_execution_scope(fact.scope),
            _encode_root_fill_key(fact.root_key),
            _encode_source_event_id(fact.predecessor_source_event_id),
            _encode_reported_price(fact.reported_price),
        )
    raise TypeError(
        "fact must be a canonical broker execution fact or HumanAttestedFillFact"
    )


@dataclass(frozen=True, slots=True)
class RootHead:
    """Current effective economics for one immutable root sequence entry."""

    root_key: RootFillKey
    original_sequence: int
    scope: ExecutionScope
    authority: ExecutionAuthority
    current_source_event_id: SourceEventId
    kind: FactKind
    quantity: Quantity
    price: ReportedPrice | None
    prefix_heads_commitment: bytes = b""
    prefix_proof_commitment: bytes = b""

    def __post_init__(self) -> None:
        _require_type("root_key", self.root_key, RootFillKey)
        if isinstance(self.original_sequence, bool) or not isinstance(
            self.original_sequence, int
        ):
            raise TypeError("original_sequence must be an integer")
        if self.original_sequence < 0:
            raise ValueError("original_sequence must be non-negative")
        _require_type("scope", self.scope, ExecutionScope)
        _require_type("authority", self.authority, ExecutionAuthority)
        _require_type(
            "current_source_event_id",
            self.current_source_event_id,
            SourceEventId,
        )
        _require_type("kind", self.kind, FactKind)
        _require_type("quantity", self.quantity, Quantity)
        if (
            self.root_key.broker != self.scope.broker
            or self.root_key.environment != self.scope.environment
            or self.root_key.account != self.scope.account
        ):
            raise ValueError("root head key and scope must have identical venue scope")
        if self.price is not None:
            _require_type("price", self.price, ReportedPrice)
            if self.price.exact_value <= 0:
                raise ValueError("root-head price must be positive when present")
        if self.kind is FactKind.TRADE_BUST:
            if self.quantity.value != 0:
                raise ValueError("a bust root head must have structural zero quantity")
        elif self.quantity.value <= 0 or self.price is None:
            raise ValueError("fill/correction root heads require positive economics")
        if not isinstance(self.prefix_heads_commitment, bytes):
            raise TypeError("prefix_heads_commitment must be bytes")
        if not isinstance(self.prefix_proof_commitment, bytes):
            raise TypeError("prefix_proof_commitment must be bytes")

    @property
    def signed_quantity(self) -> int:
        if self.scope.side is ExecutionSide.BUY:
            return self.quantity.value
        return -self.quantity.value

    @property
    def commitment(self) -> bytes:
        return _commit_root_head(self)


def _commit_root_head(head: RootHead) -> bytes:
    _require_type("head", head, RootHead)
    return _commit_parts(
        b"execution-core/root-head/v1",
        _encode_root_fill_key(head.root_key),
        _encode_int(head.original_sequence),
        _encode_execution_scope(head.scope),
        _encode_text(head.authority.value),
        _encode_source_event_id(head.current_source_event_id),
        _encode_text(head.kind.value),
        _encode_int(head.quantity.value),
        _encode_reported_price(head.price),
        head.prefix_heads_commitment,
        head.prefix_proof_commitment,
    )


@dataclass(frozen=True, slots=True, init=False, eq=False)
class RootHeadIndex:
    """Persistent root index; tuple materialization is an explicit slow view."""

    _by_root: _PersistentKeyMap[RootHead]
    _root_sequence: _PersistentSequence[RootFillKey]
    _head_sequence: _PersistentSequence[SourceEventId]
    _broker_scope_counts: _PersistentKeyMap[int]
    position_scope: PositionScope | None
    signed_quantity: int
    _binding: _SnapshotBinding | None

    def __init__(
        self,
        entries: tuple[RootHead, ...] = (),
        *,
        position_scope: PositionScope | None = None,
    ) -> None:
        if not isinstance(entries, tuple):
            raise TypeError("entries must be a tuple")
        current = type(self).empty(position_scope)
        for head in entries:
            current = current.append(head)
        object.__setattr__(self, "_by_root", current._by_root)
        object.__setattr__(self, "_root_sequence", current._root_sequence)
        object.__setattr__(self, "_head_sequence", current._head_sequence)
        object.__setattr__(
            self,
            "_broker_scope_counts",
            current._broker_scope_counts,
        )
        object.__setattr__(self, "position_scope", current.position_scope)
        object.__setattr__(self, "signed_quantity", current.signed_quantity)
        object.__setattr__(self, "_binding", None)

    @classmethod
    def _from_parts(
        cls,
        *,
        by_root: _PersistentKeyMap[RootHead],
        root_sequence: _PersistentSequence[RootFillKey],
        head_sequence: _PersistentSequence[SourceEventId],
        broker_scope_counts: _PersistentKeyMap[int] | None = None,
        position_scope: PositionScope | None,
        signed_quantity: int,
        binding: _SnapshotBinding | None = None,
    ) -> RootHeadIndex:
        result = object.__new__(cls)
        object.__setattr__(result, "_by_root", by_root)
        object.__setattr__(result, "_root_sequence", root_sequence)
        object.__setattr__(result, "_head_sequence", head_sequence)
        object.__setattr__(
            result,
            "_broker_scope_counts",
            (
                broker_scope_counts
                if broker_scope_counts is not None
                else _PersistentKeyMap.empty()
            ),
        )
        object.__setattr__(result, "position_scope", position_scope)
        object.__setattr__(result, "signed_quantity", signed_quantity)
        object.__setattr__(result, "_binding", binding)
        return result

    @classmethod
    def empty(
        cls,
        position_scope: PositionScope | None = None,
    ) -> RootHeadIndex:
        if position_scope is not None:
            _require_type("position_scope", position_scope, PositionScope)
        return cls._from_parts(
            by_root=_PersistentKeyMap.empty(),
            root_sequence=_PersistentSequence.empty(),
            head_sequence=_PersistentSequence.empty(),
            broker_scope_counts=_PersistentKeyMap.empty(),
            position_scope=position_scope,
            signed_quantity=0,
        )

    @property
    def count(self) -> int:
        return self._root_sequence.length

    @property
    def root_order_commitment(self) -> bytes:
        return self._root_sequence.commitment

    @property
    def head_ids_commitment(self) -> bytes:
        return self._head_sequence.commitment

    @property
    def commitment(self) -> bytes:
        scope = (
            _encode_position_scope(self.position_scope)
            if self.position_scope is not None
            else b""
        )
        return _commit_parts(
            b"execution-core/root-head-index/v2",
            scope,
            _encode_int(self.signed_quantity),
            self._by_root.commitment,
            self._root_sequence.commitment,
            self._head_sequence.commitment,
            self._broker_scope_counts.commitment,
        )

    @property
    def binding(self) -> _SnapshotBinding | None:
        return self._binding

    @property
    def entries(self) -> tuple[RootHead, ...]:
        """Materialize root order only for explicit slow/audit consumers."""

        materialized: list[RootHead] = []
        for index in range(self.count):
            root_key = self._root_sequence.get(index)
            head = self.get(root_key)
            if head is None:
                raise RuntimeError("root index order references a missing head")
            materialized.append(head)
        return tuple(materialized)

    def get(self, root_key: RootFillKey) -> RootHead | None:
        _require_type("root_key", root_key, RootFillKey)
        return self._by_root.get(_encode_root_fill_key(root_key))

    def broker_root_count(self, scope: ExecutionScope) -> int:
        """Return the indexed broker-authoritative root count for exact scope."""

        _require_type("scope", scope, ExecutionScope)
        count = self._broker_scope_counts.get(_encode_execution_scope(scope))
        return 0 if count is None else count

    def append(self, head: RootHead) -> RootHeadIndex:
        _require_type("head", head, RootHead)
        if self.get(head.root_key) is not None:
            raise ValueError("a root head with this key already exists")
        if head.original_sequence != self.count:
            raise ValueError("new root head sequence must equal the current root count")
        head_scope = head.scope.position_scope
        if self.position_scope is not None and head_scope != self.position_scope:
            raise ValueError("all root heads must share exact position scope")
        broker_scope_counts = self._broker_scope_counts
        if head.authority is ExecutionAuthority.BROKER_AUTHORITATIVE:
            encoded_scope = _encode_execution_scope(head.scope)
            current_count = broker_scope_counts.get(encoded_scope)
            next_count = 1 if current_count is None else current_count + 1
            count_commitment = _commit_parts(
                b"execution-core/broker-scope-root-count/v1",
                encoded_scope,
                _encode_int(next_count),
            )
            broker_scope_counts = (
                broker_scope_counts.insert_new(
                    encoded_scope,
                    next_count,
                    count_commitment,
                )
                if current_count is None
                else broker_scope_counts.replace_existing(
                    encoded_scope,
                    next_count,
                    count_commitment,
                )
            )
        return type(self)._from_parts(
            by_root=self._by_root.insert_new(
                _encode_root_fill_key(head.root_key),
                head,
                head.commitment,
            ),
            root_sequence=self._root_sequence.append(
                head.root_key,
                _commit_root_fill_key(head.root_key),
            ),
            head_sequence=self._head_sequence.append(
                head.current_source_event_id,
                _commit_source_event_id(head.current_source_event_id),
            ),
            broker_scope_counts=broker_scope_counts,
            position_scope=self.position_scope or head_scope,
            signed_quantity=self.signed_quantity + head.signed_quantity,
        )

    def replace(self, head: RootHead) -> RootHeadIndex:
        _require_type("head", head, RootHead)
        current = self.get(head.root_key)
        if current is None:
            raise KeyError(head.root_key)
        if head.original_sequence != current.original_sequence:
            raise ValueError("a replacement cannot change original root sequence")
        if head.scope != current.scope:
            raise ValueError("a replacement cannot change complete root scope")
        if head.authority is not current.authority:
            raise ValueError("a replacement cannot change root authority")
        return type(self)._from_parts(
            by_root=self._by_root.replace_existing(
                _encode_root_fill_key(head.root_key),
                head,
                head.commitment,
            ),
            root_sequence=self._root_sequence,
            head_sequence=self._head_sequence.set(
                head.original_sequence,
                head.current_source_event_id,
                _commit_source_event_id(head.current_source_event_id),
            ),
            broker_scope_counts=self._broker_scope_counts,
            position_scope=self.position_scope,
            signed_quantity=(
                self.signed_quantity - current.signed_quantity + head.signed_quantity
            ),
        )

    def _with_binding(self, binding: _SnapshotBinding) -> RootHeadIndex:
        _require_type("binding", binding, _SnapshotBinding)
        return type(self)._from_parts(
            by_root=self._by_root,
            root_sequence=self._root_sequence,
            head_sequence=self._head_sequence,
            broker_scope_counts=self._broker_scope_counts,
            position_scope=self.position_scope,
            signed_quantity=self.signed_quantity,
            binding=binding,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RootHeadIndex):
            return NotImplemented
        return (
            self.position_scope == other.position_scope
            and self.signed_quantity == other.signed_quantity
            and self.entries == other.entries
        )


@dataclass(frozen=True, slots=True)
class SeenFact:
    """First immutable payload and its stable exact-replay classification."""

    fact: CanonicalExecutionFact
    classification: FirstObservationClassification
    position_scope: PositionScope | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.fact,
            (
                BrokerFillFact,
                HumanAttestedFillFact,
                BrokerTradeCorrectFact,
                BrokerTradeBustFact,
            ),
        ):
            raise TypeError(
                "fact must be a canonical broker execution fact "
                "or HumanAttestedFillFact"
            )
        _require_type(
            "classification",
            self.classification,
            FirstObservationClassification,
        )
        if self.position_scope is None:
            object.__setattr__(self, "position_scope", self.fact.scope.position_scope)
        else:
            _require_type("position_scope", self.position_scope, PositionScope)
        if (
            self.classification
            is not FirstObservationClassification.RECONCILIATION_REQUIRED
            and self.position_scope != self.fact.scope.position_scope
        ):
            raise ValueError(
                "an applied first observation must use the fact's position scope"
            )
        if (
            self.classification
            is FirstObservationClassification.CORROBORATED_ZERO_ECONOMIC
            and not isinstance(self.fact, BrokerFillFact)
        ):
            raise ValueError("zero-economic corroboration requires a BrokerFillFact")

    @property
    def commitment(self) -> bytes:
        return _commit_seen_fact(self)


def _commit_seen_fact(observation: SeenFact) -> bytes:
    _require_type("observation", observation, SeenFact)
    return _commit_parts(
        b"execution-core/seen-fact/v2",
        _encode_execution_fact(observation.fact),
        _encode_text(observation.classification.value),
        _encode_position_scope(cast(PositionScope, observation.position_scope)),
    )


@dataclass(frozen=True, slots=True, init=False, eq=False)
class SeenFactIndex:
    """Persistent account registry of exact first observations and root claims."""

    _by_key: _PersistentKeyMap[SeenFact]
    _order: _PersistentSequence[ExecutionFactKey]
    _observed_roots: _PersistentKeyMap[RootFillKey]
    _overfill_scopes: _PersistentKeyMap[PositionScope]
    _prefix_commitments: _PersistentKeyMap[bytes]
    _tail_position_scope: PositionScope | None
    _tail_position_scope_start: int
    _account_scope: _AccountScope | None
    _binding: _SnapshotBinding | None

    def __init__(
        self,
        entries: tuple[SeenFact, ...] = (),
        *,
        position_scope: PositionScope | None = None,
    ) -> None:
        if not isinstance(entries, tuple):
            raise TypeError("entries must be a tuple")
        current = type(self).empty(position_scope)
        for observation in entries:
            current = current.add(observation)
        object.__setattr__(self, "_by_key", current._by_key)
        object.__setattr__(self, "_order", current._order)
        object.__setattr__(self, "_observed_roots", current._observed_roots)
        object.__setattr__(self, "_overfill_scopes", current._overfill_scopes)
        object.__setattr__(
            self,
            "_prefix_commitments",
            current._prefix_commitments,
        )
        object.__setattr__(
            self,
            "_tail_position_scope",
            current._tail_position_scope,
        )
        object.__setattr__(
            self,
            "_tail_position_scope_start",
            current._tail_position_scope_start,
        )
        object.__setattr__(self, "_account_scope", current._account_scope)
        object.__setattr__(self, "_binding", None)

    @classmethod
    def _from_parts(
        cls,
        *,
        by_key: _PersistentKeyMap[SeenFact],
        order: _PersistentSequence[ExecutionFactKey],
        observed_roots: _PersistentKeyMap[RootFillKey],
        overfill_scopes: _PersistentKeyMap[PositionScope],
        prefix_commitments: _PersistentKeyMap[bytes] | None = None,
        account_scope: _AccountScope | None,
        tail_position_scope: PositionScope | None = None,
        tail_position_scope_start: int = 0,
        binding: _SnapshotBinding | None = None,
    ) -> SeenFactIndex:
        result = object.__new__(cls)
        object.__setattr__(result, "_by_key", by_key)
        object.__setattr__(result, "_order", order)
        object.__setattr__(result, "_observed_roots", observed_roots)
        object.__setattr__(result, "_overfill_scopes", overfill_scopes)
        object.__setattr__(
            result,
            "_prefix_commitments",
            (
                prefix_commitments
                if prefix_commitments is not None
                else _PersistentKeyMap.empty()
            ),
        )
        object.__setattr__(result, "_account_scope", account_scope)
        object.__setattr__(result, "_tail_position_scope", tail_position_scope)
        object.__setattr__(
            result,
            "_tail_position_scope_start",
            tail_position_scope_start,
        )
        object.__setattr__(result, "_binding", binding)
        return result

    @classmethod
    def empty(cls, position_scope: PositionScope | None = None) -> SeenFactIndex:
        if position_scope is not None:
            _require_type("position_scope", position_scope, PositionScope)
        return cls._from_parts(
            by_key=_PersistentKeyMap.empty(),
            order=_PersistentSequence.empty(),
            observed_roots=_PersistentKeyMap.empty(),
            overfill_scopes=_PersistentKeyMap.empty(),
            prefix_commitments=_PersistentKeyMap.empty(),
            account_scope=(
                _account_scope_from_position(position_scope)
                if position_scope is not None
                else None
            ),
        )

    @property
    def count(self) -> int:
        return self._order.length

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/seen-fact-index/v5",
            _encode_account_scope(self._account_scope),
            self._by_key.commitment,
            self._order.commitment,
            self._observed_roots.commitment,
            self._overfill_scopes.commitment,
            self._prefix_commitments.commitment,
            (
                _encode_position_scope(self._tail_position_scope)
                if self._tail_position_scope is not None
                else _commit_parts(b"execution-core/tail-position-scope/none/v1")
            ),
            _encode_int(self._tail_position_scope_start),
        )

    @property
    def account_scope(self) -> _AccountScope | None:
        return self._account_scope

    def has_overfill_observation(self, position_scope: PositionScope) -> bool:
        _require_type("position_scope", position_scope, PositionScope)
        return (
            self._overfill_scopes.get(_encode_position_scope(position_scope))
            is not None
        )

    def belongs_to(self, position_scope: PositionScope) -> bool:
        _require_type("position_scope", position_scope, PositionScope)
        return self._account_scope == _account_scope_from_position(position_scope)

    def has_prefix(self, count: int, commitment: bytes) -> bool:
        """Verify an exact prior registry commitment without history materialization."""

        if type(count) is not int or count < 0:
            raise ValueError("count must be a non-negative exact integer")
        if type(commitment) is not bytes or len(commitment) != 32:
            raise ValueError("commitment must contain exactly 32 bytes")
        if count > self.count:
            return False
        if count == self.count:
            return self.commitment == commitment
        retained = self._prefix_commitments.get(count.to_bytes(8, "big"))
        return retained == commitment

    def suffix_belongs_to(
        self,
        count: int,
        position_scope: PositionScope,
    ) -> bool:
        """Prove a registry suffix has one evaluation scope in constant work."""

        if type(count) is not int or count < 0:
            raise ValueError("count must be a non-negative exact integer")
        _require_type("position_scope", position_scope, PositionScope)
        if count > self.count:
            return False
        if count == self.count:
            return True
        return (
            self._tail_position_scope == position_scope
            and self._tail_position_scope_start <= count
        )

    def _for_position_scope(self, position_scope: PositionScope) -> SeenFactIndex:
        _require_type("position_scope", position_scope, PositionScope)
        account_scope = _account_scope_from_position(position_scope)
        if self._account_scope is not None and self._account_scope != account_scope:
            raise ValueError("seen-fact registry belongs to a different account")
        if self._account_scope == account_scope:
            return self
        return type(self)._from_parts(
            by_key=self._by_key,
            order=self._order,
            observed_roots=self._observed_roots,
            overfill_scopes=self._overfill_scopes,
            prefix_commitments=self._prefix_commitments,
            account_scope=account_scope,
            tail_position_scope=self._tail_position_scope,
            tail_position_scope_start=self._tail_position_scope_start,
        )

    @property
    def binding(self) -> _SnapshotBinding | None:
        return self._binding

    @property
    def entries(self) -> tuple[SeenFact, ...]:
        """Materialize arrival order only for explicit slow/audit consumers."""

        materialized: list[SeenFact] = []
        for index in range(self.count):
            key = self._order.get(index)
            observation = self.get(key)
            if observation is None:
                raise RuntimeError("seen-fact order references a missing observation")
            materialized.append(observation)
        return tuple(materialized)

    def get(self, key: ExecutionFactKey) -> SeenFact | None:
        _require_type("key", key, ExecutionFactKey)
        return self._by_key.get(_encode_execution_fact_key(key))

    def observation_at(self, index: int) -> SeenFact:
        """Return one ordered observation without materializing registry history."""

        if type(index) is not int:
            raise TypeError("index must be an exact integer")
        if index < 0 or index >= self.count:
            raise IndexError(index)
        key = self._order.get(index)
        observation = self.get(key)
        if observation is None:
            raise RuntimeError("seen-fact order references a missing observation")
        return observation

    def contains_root(self, root_key: RootFillKey) -> bool:
        """Return whether any first observation reserved this exact root key."""

        _require_type("root_key", root_key, RootFillKey)
        return self._observed_roots.get(_encode_root_fill_key(root_key)) is not None

    def add(self, observation: SeenFact) -> SeenFactIndex:
        _require_type("observation", observation, SeenFact)
        if self.get(observation.fact.key) is not None:
            raise ValueError("a first observation for this event key already exists")
        observation_account_scope = _account_scope_from_position(
            cast(PositionScope, observation.position_scope)
        )
        if (
            self._account_scope is not None
            and self._account_scope != observation_account_scope
        ):
            raise ValueError("seen-fact registry cannot mix evaluation accounts")
        current = self._for_position_scope(
            cast(PositionScope, observation.position_scope)
        )
        root_key = observation.fact.root_key
        encoded_root = _encode_root_fill_key(root_key)
        observed_roots = current._observed_roots
        if observed_roots.get(encoded_root) is None:
            observed_roots = observed_roots.insert_new(
                encoded_root,
                root_key,
                _commit_root_fill_key(root_key),
            )
        overfill_scopes = current._overfill_scopes
        if observation.classification in {
            FirstObservationClassification.APPLIED_OVERFILL_QUARANTINE,
            FirstObservationClassification.APPLIED_PENDING_OVERFILL,
        }:
            position_scope = cast(PositionScope, observation.position_scope)
            encoded_position_scope = _encode_position_scope(position_scope)
            if overfill_scopes.get(encoded_position_scope) is None:
                overfill_scopes = overfill_scopes.insert_new(
                    encoded_position_scope,
                    position_scope,
                    _commit_parts(
                        b"execution-core/overfill-position-scope/v1",
                        encoded_position_scope,
                    ),
                )
        prefix_key = current.count.to_bytes(8, "big")
        prefix_commitments = current._prefix_commitments
        if prefix_commitments.get(prefix_key) is None:
            prefix_commitments = prefix_commitments.insert_new(
                prefix_key,
                current.commitment,
                _commit_parts(
                    b"execution-core/seen-fact-prefix/v1",
                    prefix_key,
                    current.commitment,
                ),
            )
        return type(self)._from_parts(
            by_key=current._by_key.insert_new(
                _encode_execution_fact_key(observation.fact.key),
                observation,
                observation.commitment,
            ),
            order=current._order.append(
                observation.fact.key,
                _commit_parts(
                    b"execution-core/execution-fact-key-commitment/v1",
                    _encode_execution_fact_key(observation.fact.key),
                ),
            ),
            observed_roots=observed_roots,
            overfill_scopes=overfill_scopes,
            prefix_commitments=prefix_commitments,
            account_scope=current._account_scope or observation_account_scope,
            tail_position_scope=cast(PositionScope, observation.position_scope),
            tail_position_scope_start=(
                current._tail_position_scope_start
                if current._tail_position_scope == observation.position_scope
                else current.count
            ),
        )

    def _with_binding(self, binding: _SnapshotBinding) -> SeenFactIndex:
        _require_type("binding", binding, _SnapshotBinding)
        return type(self)._from_parts(
            by_key=self._by_key,
            order=self._order,
            observed_roots=self._observed_roots,
            overfill_scopes=self._overfill_scopes,
            prefix_commitments=self._prefix_commitments,
            account_scope=self._account_scope,
            tail_position_scope=self._tail_position_scope,
            tail_position_scope_start=self._tail_position_scope_start,
            binding=binding,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SeenFactIndex):
            return NotImplemented
        return (
            self.entries == other.entries
            and self._observed_roots == other._observed_roots
            and self._overfill_scopes == other._overfill_scopes
            and self._tail_position_scope == other._tail_position_scope
            and self._tail_position_scope_start == other._tail_position_scope_start
            and self._account_scope == other._account_scope
        )
