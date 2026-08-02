"""Stateful, metamorphic, and mutation-capable tests for reset kernel M1A.

The oracle in this module intentionally knows nothing about the reducer's branch
structure.  It substitutes each effective root at its original sequence and
folds exact rational economics using the accepted long-only average-cost rule.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from fractions import Fraction

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule
import pytest

import app.execution_core.position as position_module
from app.execution_core.fills import (
    BrokerFillFact,
    BrokerTradeBustFact,
    BrokerTradeCorrectFact,
    ExecutionAuthority,
    ExecutionScope,
    ExecutionSide,
    PositionScope,
)
from app.execution_core.identity import (
    AccountId,
    BrokerId,
    EnvironmentId,
    ExecutionFactKey,
    OrderId,
    RootFillId,
    RootFillKey,
    SourceEventId,
    SymbolId,
)
from app.execution_core.position import (
    BasisAuthority,
    BasisCandidateStatus,
    ExecutionSnapshot,
    FirstObservationClassification,
    PositionIntegrity,
    PositionState,
    RootHeadIndex,
    SeenFactIndex,
    TransitionDisposition,
    apply_broker_execution_fact,
    derive_ordered_basis_candidate,
)
from app.execution_core.values import (
    ExactBasis,
    PriceScale,
    PriceUnits,
    Quantity,
    ReportedPrice,
    TickMetadata,
)


_BROKER = BrokerId("alpaca")
_ENVIRONMENT = EnvironmentId("paper")
_ACCOUNT = AccountId("paper-account")
_SYMBOL = SymbolId("AAPL")
_POSITION_SCOPE = PositionScope(
    broker=_BROKER,
    environment=_ENVIRONMENT,
    account=_ACCOUNT,
    symbol_id=_SYMBOL,
)


ExecutionFact = BrokerFillFact | BrokerTradeCorrectFact | BrokerTradeBustFact


@dataclass(frozen=True)
class _ModelRoot:
    key: RootFillKey
    root_fill_id: RootFillId
    scope: ExecutionScope
    current_source_event_id: SourceEventId
    history: tuple[SourceEventId, ...]
    quantity: int
    price: ReportedPrice | None


def _price(units: int, *, tick_units: int = 1, scale: str = "1") -> ReportedPrice:
    exact_scale = PriceScale(Decimal(scale))
    return ReportedPrice(
        units=PriceUnits(units),
        scale=exact_scale,
        tick=TickMetadata(
            tick_units=PriceUnits(tick_units),
            scale=exact_scale,
        ),
    )


def _scope(side: ExecutionSide, order_number: int) -> ExecutionScope:
    return ExecutionScope(
        broker=_BROKER,
        environment=_ENVIRONMENT,
        account=_ACCOUNT,
        order_id=OrderId(f"order-{order_number}"),
        symbol_id=_SYMBOL,
        side=side,
    )


def _fact_key(number: int) -> ExecutionFactKey:
    return ExecutionFactKey(
        broker=_BROKER,
        environment=_ENVIRONMENT,
        account=_ACCOUNT,
        source_event_id=SourceEventId(f"event-{number}"),
    )


def _root_key(root_fill_id: RootFillId) -> RootFillKey:
    return RootFillKey(
        broker=_BROKER,
        environment=_ENVIRONMENT,
        account=_ACCOUNT,
        root_fill_id=root_fill_id,
    )


def _signed(side: ExecutionSide, quantity: int) -> int:
    return quantity if side is ExecutionSide.BUY else -quantity


def _flat_snapshot() -> ExecutionSnapshot:
    return ExecutionSnapshot.flat(_POSITION_SCOPE)


def _fractional_price(price: ReportedPrice) -> Fraction:
    return Fraction(price.units.value) * Fraction(price.scale.value)


def _metadata_are_compatible(roots: list[_ModelRoot]) -> bool:
    prices = [root.price for root in roots if root.price is not None]
    if not prices:
        return True
    reference = prices[0]
    reference_tick = reference.tick.tick_units.value
    reference_scale = reference.scale.value
    for price in prices:
        if price.units.value % price.tick.tick_units.value:
            return False
        if price.tick.scale.value != price.scale.value:
            return False
        if price.scale.value != reference_scale:
            return False
        if price.tick.tick_units.value != reference_tick:
            return False
    return True


@dataclass(frozen=True)
class _LongLot:
    """One test-owned average-cost lot after proportional retention."""

    quantity: Fraction
    notional: Fraction


def _ordered_fold(roots: list[_ModelRoot]) -> tuple[int, Fraction]:
    """Fold effective roots through a conceptual exact long-lot ledger."""

    raw_quantity = 0
    long_lots: list[_LongLot] = []
    for root in roots:
        absolute_quantity = root.quantity
        if root.scope.side is ExecutionSide.BUY:
            newly_long = max(raw_quantity + absolute_quantity, 0) - max(raw_quantity, 0)
            if newly_long:
                assert root.price is not None
                long_lots.append(
                    _LongLot(
                        quantity=Fraction(newly_long),
                        notional=(Fraction(newly_long) * _fractional_price(root.price)),
                    )
                )
        else:
            long_before = max(raw_quantity, 0)
            long_after = max(raw_quantity - absolute_quantity, 0)
            if long_before:
                retained = Fraction(long_after, long_before)
                long_lots = [
                    _LongLot(
                        quantity=lot.quantity * retained,
                        notional=lot.notional * retained,
                    )
                    for lot in long_lots
                ]
        raw_quantity += _signed(root.scope.side, absolute_quantity)
        assert sum((lot.quantity for lot in long_lots), Fraction(0)) == max(
            raw_quantity, 0
        )
    return raw_quantity, sum(
        (lot.notional for lot in long_lots),
        Fraction(0),
    )


def _changed_payload(fact: ExecutionFact) -> ExecutionFact:
    if isinstance(fact, BrokerFillFact):
        return replace(fact, quantity=Quantity(fact.quantity.value + 1))
    if isinstance(fact, BrokerTradeCorrectFact):
        return replace(
            fact,
            revised_quantity=Quantity(fact.revised_quantity.value + 1),
        )
    changed_price = (
        _price(103)
        if fact.reported_price is None
        else _price(fact.reported_price.units.value + 1)
    )
    return replace(fact, reported_price=changed_price)


def _apply(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    fact: ExecutionFact,
):
    """Call twice from identical inputs: every complete transition is deterministic."""

    before = _input_semantic_fingerprint(
        position,
        integrity,
        root_heads,
        seen_facts,
        fact,
    )
    first = apply_broker_execution_fact(
        position, integrity, root_heads, seen_facts, fact
    )
    second = apply_broker_execution_fact(
        position, integrity, root_heads, seen_facts, fact
    )
    assert first == second
    assert before == _input_semantic_fingerprint(
        position,
        integrity,
        root_heads,
        seen_facts,
        fact,
    ), "the reducer mutated an input or immutable predecessor"
    return first


def _input_semantic_fingerprint(
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    fact: ExecutionFact,
) -> tuple[object, ...]:
    """Re-derive test-only input semantics without rendering private radix trees."""

    return (
        position.commitment,
        tuple(repr(root_key) for root_key in position.root_fill_sequence),
        tuple(repr(head_id) for head_id in position.effective_head_ids),
        repr(position.binding),
        integrity,
        root_heads.commitment,
        tuple(repr(head) for head in root_heads.entries),
        repr(root_heads.binding),
        seen_facts.commitment,
        tuple(repr(observation) for observation in seen_facts.entries),
        repr(seen_facts.binding),
        repr(fact),
    )


@pytest.mark.parametrize(
    "target",
    ("root-head", "seen-fact"),
)
def test_apply_guard_detects_retained_leaf_mutation(monkeypatch, target: str) -> None:
    snapshot = _flat_snapshot()
    seed = BrokerFillFact(
        key=_fact_key(1),
        scope=_scope(ExecutionSide.BUY, 1),
        root_fill_id=RootFillId("guard-seed"),
        quantity=Quantity(3),
        price=_price(100),
    )
    seeded = apply_broker_execution_fact(
        snapshot.position,
        snapshot.integrity,
        snapshot.root_heads,
        snapshot.seen_facts,
        seed,
    )
    next_fact = BrokerFillFact(
        key=_fact_key(2),
        scope=_scope(ExecutionSide.BUY, 2),
        root_fill_id=RootFillId("guard-next"),
        quantity=Quantity(1),
        price=_price(101),
    )
    original = apply_broker_execution_fact
    call_count = 0

    def mutate_after_second_call(
        position: PositionState,
        integrity: PositionIntegrity,
        root_heads: RootHeadIndex,
        seen_facts: SeenFactIndex,
        fact: ExecutionFact,
    ):
        nonlocal call_count
        transition = original(position, integrity, root_heads, seen_facts, fact)
        call_count += 1
        if call_count == 2:
            if target == "root-head":
                object.__setattr__(root_heads.entries[0], "quantity", Quantity(10))
            else:
                object.__setattr__(seen_facts.entries[0].fact, "quantity", Quantity(10))
        return transition

    monkeypatch.setitem(
        _apply.__globals__,
        "apply_broker_execution_fact",
        mutate_after_second_call,
    )
    with pytest.raises(AssertionError, match="mutated an input"):
        _apply(
            seeded.position,
            seeded.integrity,
            seeded.root_heads,
            seeded.seen_facts,
            next_fact,
        )


def test_input_semantic_fingerprint_reads_position_sequence_leaves() -> None:
    snapshot = _flat_snapshot()
    position = PositionState.from_materialized(
        scope=_POSITION_SCOPE,
        raw_quantity=0,
        basis_authority=BasisAuthority.AVAILABLE,
        cost_basis=ExactBasis(Fraction(0)),
        root_fill_sequence=(_root_key(RootFillId("position-leaf")),),
        effective_head_ids=(SourceEventId("position-head"),),
        basis_price_metadata=None,
        tail_fold_input=None,
    )
    fact = BrokerFillFact(
        key=_fact_key(1),
        scope=_scope(ExecutionSide.BUY, 1),
        root_fill_id=RootFillId("fingerprint-fact"),
        quantity=Quantity(1),
        price=_price(100),
    )
    before_commitment = position.commitment
    before = _input_semantic_fingerprint(
        position,
        snapshot.integrity,
        snapshot.root_heads,
        snapshot.seen_facts,
        fact,
    )

    object.__setattr__(
        position.root_fill_sequence[0],
        "root_fill_id",
        RootFillId("mutated-position-leaf"),
    )

    assert position.commitment == before_commitment
    assert before != _input_semantic_fingerprint(
        position,
        snapshot.integrity,
        snapshot.root_heads,
        snapshot.seen_facts,
        fact,
    )


class FillPositionMachine(RuleBasedStateMachine):
    """Generate root/revision/duplicate/failure histories against an exact model."""

    def __init__(self) -> None:
        super().__init__()
        snapshot = ExecutionSnapshot.flat(_POSITION_SCOPE)
        self.position = snapshot.position
        self.integrity = snapshot.integrity
        self.root_heads = snapshot.root_heads
        self.seen_facts = snapshot.seen_facts
        self.roots: list[_ModelRoot] = []
        self.seen: dict[
            ExecutionFactKey,
            tuple[ExecutionFact, FirstObservationClassification],
        ] = {}
        self.pending = False
        self._next_event = 0
        self._next_root = 0
        self._next_order = 0

    def _event_key(self) -> ExecutionFactKey:
        self._next_event += 1
        return _fact_key(self._next_event)

    def _root_id(self) -> RootFillId:
        self._next_root += 1
        return RootFillId(f"root-{self._next_root}")

    def _new_scope(self, side: ExecutionSide) -> ExecutionScope:
        self._next_order += 1
        return _scope(side, self._next_order)

    def _commit_first(
        self,
        fact: ExecutionFact,
        *,
        expected_disposition: TransitionDisposition,
        expected_delta: int,
        integrity_to_add: PositionIntegrity = PositionIntegrity.CONSISTENT,
    ):
        old_integrity = self.integrity
        transition = _apply(
            self.position,
            self.integrity,
            self.root_heads,
            self.seen_facts,
            fact,
        )
        assert transition.disposition is expected_disposition
        assert transition.quantity_delta == expected_delta
        assert transition.integrity == old_integrity | integrity_to_add
        assert transition.integrity | old_integrity == transition.integrity
        assert fact.key not in self.seen
        observed = transition.seen_facts.get(fact.key)
        assert observed is not None
        assert observed.fact == fact
        assert observed.classification is transition.original_classification
        self.seen[fact.key] = (fact, observed.classification)
        self.position = transition.position
        self.integrity = transition.integrity
        self.root_heads = transition.root_heads
        self.seen_facts = transition.seen_facts
        return transition

    def _commit_valid(self, fact: ExecutionFact, *, expected_delta: int):
        old_quantity = self.position.raw_quantity
        transition = _apply(
            self.position,
            self.integrity,
            self.root_heads,
            self.seen_facts,
            fact,
        )
        assert transition.disposition is TransitionDisposition.APPLIED
        assert transition.quantity_delta == expected_delta
        assert transition.position.raw_quantity == old_quantity + expected_delta
        expected_integrity = self.integrity
        if transition.position.raw_quantity < 0:
            expected_integrity |= PositionIntegrity.OVERFILL_QUARANTINE
        assert transition.integrity == expected_integrity
        assert transition.integrity | self.integrity == transition.integrity
        observed = transition.seen_facts.get(fact.key)
        assert observed is not None
        assert observed.fact == fact
        self.seen[fact.key] = (fact, observed.classification)
        self.position = transition.position
        self.integrity = transition.integrity
        self.root_heads = transition.root_heads
        self.seen_facts = transition.seen_facts
        return transition

    @rule(
        side=st.sampled_from((ExecutionSide.BUY, ExecutionSide.SELL)),
        quantity=st.integers(min_value=1, max_value=15),
        units=st.integers(min_value=80, max_value=140),
        incompatible=st.booleans(),
    )
    def append_broker_root(
        self,
        side: ExecutionSide,
        quantity: int,
        units: int,
        incompatible: bool,
    ) -> None:
        scope = self._new_scope(side)
        root_fill_id = self._root_id()
        fact = BrokerFillFact(
            key=self._event_key(),
            scope=scope,
            root_fill_id=root_fill_id,
            quantity=Quantity(quantity),
            price=(
                _price(units * 2 + 1, tick_units=2) if incompatible else _price(units)
            ),
        )
        transition = self._commit_valid(fact, expected_delta=_signed(side, quantity))
        self.roots.append(
            _ModelRoot(
                key=_root_key(root_fill_id),
                root_fill_id=root_fill_id,
                scope=scope,
                current_source_event_id=fact.key.source_event_id,
                history=(fact.key.source_event_id,),
                quantity=quantity,
                price=fact.price,
            )
        )
        self.pending = self.pending or not _metadata_are_compatible(self.roots)
        if self.pending:
            assert transition.position.basis_authority is (
                BasisAuthority.BASIS_RECONCILIATION_PENDING
            )

    @precondition(lambda self: bool(self.roots))
    @rule(
        data=st.data(),
        quantity=st.integers(min_value=1, max_value=15),
        units=st.integers(min_value=80, max_value=140),
        incompatible=st.booleans(),
    )
    def replace_current_head(
        self, data, quantity: int, units: int, incompatible: bool
    ) -> None:
        index = data.draw(st.integers(min_value=0, max_value=len(self.roots) - 1))
        old = self.roots[index]
        price = _price(units * 2 + 1, tick_units=2) if incompatible else _price(units)
        fact = BrokerTradeCorrectFact(
            key=self._event_key(),
            scope=old.scope,
            root_fill_id=old.root_fill_id,
            predecessor_source_event_id=old.current_source_event_id,
            revised_quantity=Quantity(quantity),
            revised_price=price,
        )
        expected_delta = _signed(old.scope.side, quantity - old.quantity)
        transition = self._commit_valid(fact, expected_delta=expected_delta)
        self.roots[index] = replace(
            old,
            current_source_event_id=fact.key.source_event_id,
            history=old.history + (fact.key.source_event_id,),
            quantity=quantity,
            price=price,
        )
        self.pending = (
            self.pending
            or index != len(self.roots) - 1
            or not _metadata_are_compatible(self.roots)
        )
        if self.pending:
            assert transition.position.basis_authority is (
                BasisAuthority.BASIS_RECONCILIATION_PENDING
            )

    @precondition(lambda self: bool(self.roots))
    @rule(data=st.data(), explicit_incompatible_price=st.booleans())
    def bust_current_head(self, data, explicit_incompatible_price: bool) -> None:
        index = data.draw(st.integers(min_value=0, max_value=len(self.roots) - 1))
        old = self.roots[index]
        reported_price = (
            _price(203, tick_units=2) if explicit_incompatible_price else None
        )
        fact = BrokerTradeBustFact(
            key=self._event_key(),
            scope=old.scope,
            root_fill_id=old.root_fill_id,
            predecessor_source_event_id=old.current_source_event_id,
            reported_price=reported_price,
        )
        transition = self._commit_valid(
            fact, expected_delta=_signed(old.scope.side, -old.quantity)
        )
        self.roots[index] = replace(
            old,
            current_source_event_id=fact.key.source_event_id,
            history=old.history + (fact.key.source_event_id,),
            quantity=0,
            price=reported_price,
        )
        self.pending = (
            self.pending
            or index != len(self.roots) - 1
            or not _metadata_are_compatible(self.roots)
        )
        if self.pending:
            assert transition.position.basis_authority is (
                BasisAuthority.BASIS_RECONCILIATION_PENDING
            )

    @precondition(lambda self: bool(self.seen))
    @rule(data=st.data())
    def replay_exact_first_observation(self, data) -> None:
        key = data.draw(st.sampled_from(tuple(self.seen)))
        fact, classification = self.seen[key]
        before = (self.position, self.integrity, self.root_heads, self.seen_facts)
        transition = _apply(*before, fact)
        assert transition.disposition is TransitionDisposition.EXACT_REPLAY
        assert transition.original_classification is classification
        assert transition.quantity_delta == 0
        assert transition.basis_delta in (Fraction(0), None)
        assert (
            transition.position,
            transition.integrity,
            transition.root_heads,
            transition.seen_facts,
        ) == before

    @precondition(lambda self: bool(self.seen))
    @rule(data=st.data())
    def replay_changed_payload(self, data) -> None:
        key = data.draw(st.sampled_from(tuple(self.seen)))
        first_fact, classification = self.seen[key]
        changed = _changed_payload(first_fact)
        before_position = self.position
        before_heads = self.root_heads
        before_seen = self.seen_facts
        transition = _apply(
            self.position,
            self.integrity,
            self.root_heads,
            self.seen_facts,
            changed,
        )
        assert transition.disposition is TransitionDisposition.FACT_CONFLICT
        assert transition.original_classification is classification
        assert transition.quantity_delta == 0
        assert (
            replace(
                transition.position,
                integrity_floor=before_position.integrity_floor,
            )
            == before_position
        )
        assert transition.root_heads == before_heads
        assert transition.seen_facts == before_seen
        assert transition.integrity == (
            self.integrity | PositionIntegrity.EXECUTION_FACT_CONFLICT
        )
        self.position = transition.position
        self.integrity = transition.integrity
        self.root_heads = transition.root_heads
        self.seen_facts = transition.seen_facts

    @precondition(lambda self: bool(self.roots))
    @rule(data=st.data(), mode=st.sampled_from(("missing", "out_of_order", "scope")))
    def reject_unresolved_revision(self, data, mode: str) -> None:
        root = data.draw(st.sampled_from(tuple(self.roots)))
        root_fill_id = root.root_fill_id
        predecessor = root.current_source_event_id
        scope = root.scope
        if mode == "missing":
            root_fill_id = self._root_id()
        elif mode == "out_of_order":
            predecessor = SourceEventId(f"future-{self._next_event + 1000}")
        else:
            scope = replace(scope, order_id=OrderId("wrong-order"))
        fact = BrokerTradeCorrectFact(
            key=self._event_key(),
            scope=scope,
            root_fill_id=root_fill_id,
            predecessor_source_event_id=predecessor,
            revised_quantity=Quantity(root.quantity + 1),
            revised_price=_price(111),
        )
        transition = self._commit_first(
            fact,
            expected_disposition=TransitionDisposition.RECONCILIATION_REQUIRED,
            expected_delta=0,
            integrity_to_add=PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED,
        )
        assert transition.original_classification is (
            FirstObservationClassification.RECONCILIATION_REQUIRED
        )

    @precondition(lambda self: len(self.roots) >= 2)
    @rule(data=st.data())
    def reject_wrong_root_or_branched_predecessor(self, data) -> None:
        left_index = data.draw(st.integers(min_value=0, max_value=len(self.roots) - 1))
        right_index = (left_index + 1) % len(self.roots)
        left = self.roots[left_index]
        right = self.roots[right_index]
        fact = BrokerTradeBustFact(
            key=self._event_key(),
            scope=left.scope,
            root_fill_id=left.root_fill_id,
            predecessor_source_event_id=right.current_source_event_id,
        )
        transition = self._commit_first(
            fact,
            expected_disposition=TransitionDisposition.RECONCILIATION_REQUIRED,
            expected_delta=0,
            integrity_to_add=PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED,
        )
        assert transition.position == self.position

    @precondition(lambda self: any(len(root.history) >= 2 for root in self.roots))
    @rule(data=st.data())
    def reject_stale_non_head_predecessor(self, data) -> None:
        candidates = [root for root in self.roots if len(root.history) >= 2]
        root = data.draw(st.sampled_from(candidates))
        fact = BrokerTradeCorrectFact(
            key=self._event_key(),
            scope=root.scope,
            root_fill_id=root.root_fill_id,
            predecessor_source_event_id=root.history[-2],
            revised_quantity=Quantity(max(root.quantity, 1)),
            revised_price=_price(109),
        )
        transition = self._commit_first(
            fact,
            expected_disposition=TransitionDisposition.RECONCILIATION_REQUIRED,
            expected_delta=0,
            integrity_to_add=PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED,
        )
        assert transition.position == self.position

    @precondition(lambda self: bool(self.roots))
    @rule(data=st.data())
    def reject_fresh_event_reusing_root_key(self, data) -> None:
        root = data.draw(st.sampled_from(tuple(self.roots)))
        fact = BrokerFillFact(
            key=self._event_key(),
            scope=root.scope,
            root_fill_id=root.root_fill_id,
            quantity=Quantity(max(root.quantity, 1)),
            price=_price(107),
        )
        transition = self._commit_first(
            fact,
            expected_disposition=TransitionDisposition.RECONCILIATION_REQUIRED,
            expected_delta=0,
            integrity_to_add=PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED,
        )
        assert transition.position == self.position

    @invariant()
    def effective_heads_quantity_and_basis_match_independent_fold(self) -> None:
        expected_quantity, expected_basis = _ordered_fold(self.roots)
        assert self.position.raw_quantity == expected_quantity
        assert self.position.root_fill_sequence == tuple(
            root.key for root in self.roots
        )
        assert self.position.effective_head_ids == tuple(
            root.current_source_event_id for root in self.roots
        )
        assert self.position.authorized_residual_sell == Quantity(
            max(expected_quantity, 0)
        )
        for root in self.roots:
            head = self.root_heads.get(root.key)
            assert head is not None
            assert head.current_source_event_id == root.current_source_event_id
            assert head.quantity == Quantity(root.quantity)

        candidate = derive_ordered_basis_candidate(self.position, self.root_heads)
        assert candidate.raw_quantity == expected_quantity
        assert candidate.root_fill_sequence == self.position.root_fill_sequence
        assert candidate.effective_head_ids == self.position.effective_head_ids
        if _metadata_are_compatible(self.roots):
            assert candidate.status is BasisCandidateStatus.DERIVED
            assert candidate.cost_basis == ExactBasis(expected_basis)
        else:
            assert candidate.status is BasisCandidateStatus.INCOMPATIBLE_PRICE_METADATA
            assert candidate.cost_basis is None

        if self.pending:
            assert self.position.basis_authority is (
                BasisAuthority.BASIS_RECONCILIATION_PENDING
            )
            assert self.position.cost_basis is None
        else:
            assert self.position.basis_authority is BasisAuthority.AVAILABLE
            assert self.position.cost_basis == ExactBasis(expected_basis)
        assert not hasattr(self.position, "basis_candidate")
        assert not hasattr(self.position, "candidate_basis")

    @invariant()
    def integrity_and_seen_first_observations_are_permanent(self) -> None:
        if self.position.raw_quantity < 0:
            assert self.integrity & PositionIntegrity.OVERFILL_QUARANTINE
        for key, (fact, classification) in self.seen.items():
            observed = self.seen_facts.get(key)
            assert observed is not None
            assert observed.fact == fact
            assert observed.classification is classification
            assert self.seen_facts.contains_root(fact.root_key)


TestFillPositionStateful = FillPositionMachine.TestCase
TestFillPositionStateful.settings = settings(
    max_examples=75,
    stateful_step_count=40,
    deadline=None,
)


def test_property_duplicate_does_not_count_clamp_reject_or_clear_integrity() -> None:
    snapshot = _flat_snapshot()
    position = snapshot.position
    integrity = snapshot.integrity
    roots = snapshot.root_heads
    seen = snapshot.seen_facts
    sell = BrokerFillFact(
        key=_fact_key(1),
        scope=_scope(ExecutionSide.SELL, 1),
        root_fill_id=RootFillId("sell-overfill"),
        quantity=Quantity(3),
        price=_price(100),
    )

    first = _apply(position, integrity, roots, seen, sell)
    assert first.position.raw_quantity == -3
    assert first.quantity_delta == -3
    assert first.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert first.original_classification is (
        FirstObservationClassification.APPLIED_OVERFILL_QUARANTINE
    )

    replay = _apply(
        first.position, first.integrity, first.root_heads, first.seen_facts, sell
    )
    assert replay.disposition is TransitionDisposition.EXACT_REPLAY
    assert replay.quantity_delta == 0
    assert replay.position == first.position
    assert replay.root_heads == first.root_heads
    assert replay.integrity == first.integrity
    assert len(replay.position.root_fill_sequence) == 1


def test_property_rejected_root_key_remains_reserved() -> None:
    snapshot = _flat_snapshot()
    rejected = BrokerFillFact(
        key=_fact_key(1),
        scope=replace(
            _scope(ExecutionSide.BUY, 1),
            symbol_id=SymbolId("MSFT"),
        ),
        root_fill_id=RootFillId("reserved-root"),
        quantity=Quantity(3),
        price=_price(100),
    )
    first = _apply(
        snapshot.position,
        snapshot.integrity,
        snapshot.root_heads,
        snapshot.seen_facts,
        rejected,
    )
    assert first.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert first.seen_facts.contains_root(rejected.root_key)
    reuse = BrokerFillFact(
        key=_fact_key(2),
        scope=_scope(ExecutionSide.BUY, 2),
        root_fill_id=rejected.root_fill_id,
        quantity=Quantity(5),
        price=_price(101),
    )

    second = _apply(
        first.position,
        first.integrity,
        first.root_heads,
        first.seen_facts,
        reuse,
    )

    assert second.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert second.quantity_delta == 0
    assert second.position.raw_quantity == 0
    assert second.root_heads.count == 0
    assert second.seen_facts.count == 2


def test_property_incompatible_authoritative_fact_applies_and_withholds_basis() -> None:
    fill = BrokerFillFact(
        key=_fact_key(1),
        scope=_scope(ExecutionSide.BUY, 1),
        root_fill_id=RootFillId("unaligned-root"),
        quantity=Quantity(4),
        price=_price(203, tick_units=2),
    )
    snapshot = _flat_snapshot()
    transition = _apply(
        snapshot.position,
        snapshot.integrity,
        snapshot.root_heads,
        snapshot.seen_facts,
        fill,
    )
    assert transition.disposition is TransitionDisposition.APPLIED
    assert transition.quantity_delta == 4
    assert transition.position.raw_quantity == 4
    assert transition.position.basis_authority is (
        BasisAuthority.BASIS_RECONCILIATION_PENDING
    )
    assert transition.position.cost_basis is None


def test_property_revision_induced_negative_is_exact_and_permanently_quarantined() -> (
    None
):
    snapshot = _flat_snapshot()
    state = snapshot.position
    integrity = snapshot.integrity
    heads = snapshot.root_heads
    seen = snapshot.seen_facts
    buy = BrokerFillFact(
        key=_fact_key(1),
        scope=_scope(ExecutionSide.BUY, 1),
        root_fill_id=RootFillId("buy-root"),
        quantity=Quantity(10),
        price=_price(100),
    )
    first = _apply(state, integrity, heads, seen, buy)
    sell = BrokerFillFact(
        key=_fact_key(2),
        scope=_scope(ExecutionSide.SELL, 2),
        root_fill_id=RootFillId("sell-root"),
        quantity=Quantity(8),
        price=_price(100),
    )
    second = _apply(
        first.position, first.integrity, first.root_heads, first.seen_facts, sell
    )
    bust = BrokerTradeBustFact(
        key=_fact_key(3),
        scope=buy.scope,
        root_fill_id=buy.root_fill_id,
        predecessor_source_event_id=buy.key.source_event_id,
    )
    revised = _apply(
        second.position,
        second.integrity,
        second.root_heads,
        second.seen_facts,
        bust,
    )
    assert revised.quantity_delta == -10
    assert revised.position.raw_quantity == -8
    assert revised.position.authorized_residual_sell == Quantity(0)
    assert revised.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert revised.position.basis_authority is (
        BasisAuthority.BASIS_RECONCILIATION_PENDING
    )
    assert revised.position.cost_basis is None

    covering_buy = BrokerFillFact(
        key=_fact_key(4),
        scope=_scope(ExecutionSide.BUY, 3),
        root_fill_id=RootFillId("cover-root"),
        quantity=Quantity(20),
        price=_price(99),
    )
    covered = _apply(
        revised.position,
        revised.integrity,
        revised.root_heads,
        revised.seen_facts,
        covering_buy,
    )
    assert covered.position.raw_quantity == 12
    assert covered.integrity & PositionIntegrity.OVERFILL_QUARANTINE


def test_property_fast_non_tail_revision_never_invokes_or_exposes_slow_candidate(
    monkeypatch,
) -> None:
    snapshot = _flat_snapshot()
    first = _apply(
        snapshot.position,
        snapshot.integrity,
        snapshot.root_heads,
        snapshot.seen_facts,
        BrokerFillFact(
            key=_fact_key(1),
            scope=_scope(ExecutionSide.BUY, 1),
            root_fill_id=RootFillId("buy-root"),
            quantity=Quantity(10),
            price=_price(100),
        ),
    )
    buy_head = first.root_heads.get(_root_key(RootFillId("buy-root")))
    assert buy_head is not None
    second = _apply(
        first.position,
        first.integrity,
        first.root_heads,
        first.seen_facts,
        BrokerFillFact(
            key=_fact_key(2),
            scope=_scope(ExecutionSide.SELL, 2),
            root_fill_id=RootFillId("sell-root"),
            quantity=Quantity(5),
            price=_price(100),
        ),
    )
    correction = BrokerTradeCorrectFact(
        key=_fact_key(3),
        scope=buy_head.scope,
        root_fill_id=RootFillId("buy-root"),
        predecessor_source_event_id=buy_head.current_source_event_id,
        revised_quantity=Quantity(7),
        revised_price=_price(101),
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("fast non-tail transition called slow ordered fold")

    with monkeypatch.context() as patcher:
        patcher.setattr(
            "app.execution_core.position.derive_ordered_basis_candidate",
            fail_if_called,
        )
        patcher.setattr(
            "app.execution_core.position._fold_ordered_heads",
            fail_if_called,
        )
        revised = _apply(
            second.position,
            second.integrity,
            second.root_heads,
            second.seen_facts,
            correction,
        )

    assert revised.position.raw_quantity == 2
    assert revised.quantity_delta == -3
    assert revised.position.basis_authority is (
        BasisAuthority.BASIS_RECONCILIATION_PENDING
    )
    assert revised.position.cost_basis is None
    assert not hasattr(revised.position, "basis_candidate")
    candidate = derive_ordered_basis_candidate(revised.position, revised.root_heads)
    assert candidate.status is BasisCandidateStatus.DERIVED
    assert candidate.raw_quantity == 2
    assert candidate.cost_basis == ExactBasis(Fraction(202))


def test_property_human_attested_root_cannot_be_corrected_or_busted() -> None:
    fill = BrokerFillFact(
        key=_fact_key(1),
        scope=_scope(ExecutionSide.BUY, 1),
        root_fill_id=RootFillId("human-root"),
        quantity=Quantity(5),
        price=_price(100),
    )
    snapshot = _flat_snapshot()
    broker_state = _apply(
        snapshot.position,
        snapshot.integrity,
        snapshot.root_heads,
        snapshot.seen_facts,
        fill,
    )
    key = _root_key(fill.root_fill_id)
    broker_head = broker_state.root_heads.get(key)
    assert broker_head is not None
    human_heads = RootHeadIndex(
        entries=(replace(broker_head, authority=ExecutionAuthority.HUMAN_ATTESTED),),
        position_scope=_POSITION_SCOPE,
    )
    human_snapshot = position_module._bind_components(
        replace(broker_state.position, _binding=None),
        broker_state.integrity,
        human_heads,
        SeenFactIndex(entries=broker_state.seen_facts.entries),
    )
    correction = BrokerTradeCorrectFact(
        key=_fact_key(2),
        scope=fill.scope,
        root_fill_id=fill.root_fill_id,
        predecessor_source_event_id=fill.key.source_event_id,
        revised_quantity=Quantity(7),
        revised_price=_price(101),
    )
    bust = BrokerTradeBustFact(
        key=_fact_key(3),
        scope=fill.scope,
        root_fill_id=fill.root_fill_id,
        predecessor_source_event_id=fill.key.source_event_id,
    )
    for revision in (correction, bust):
        transition = _apply(
            human_snapshot.position,
            human_snapshot.integrity,
            human_snapshot.root_heads,
            human_snapshot.seen_facts,
            revision,
        )
        assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
        assert transition.quantity_delta == 0
        assert (
            replace(
                transition.position,
                integrity_floor=human_snapshot.position.integrity_floor,
            )
            == human_snapshot.position
        )
        assert transition.integrity & (
            PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
        )
