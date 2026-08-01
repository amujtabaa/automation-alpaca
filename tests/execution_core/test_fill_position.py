"""Deterministic RED examples for the reset execution-fact semantic center.

The arithmetic oracle in this module is deliberately test-owned.  It is derived
from the accepted ordered long-only equations and uses :class:`Fraction`; it
does not import the incumbent projector or mirror the production reducer.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, replace
from decimal import Decimal
from fractions import Fraction
from typing import Callable, Union

import pytest

import app.execution_core.position as position_module
from app.execution_core.fills import (
    BrokerFillFact,
    BrokerTradeBustFact,
    BrokerTradeCorrectFact,
    ExecutionAuthority,
    ExecutionScope,
    ExecutionSide,
    FactKind,
    RootHead,
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
    ExecutionTransition,
    FirstObservationClassification,
    FoldInput,
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


BrokerFact = Union[BrokerFillFact, BrokerTradeCorrectFact, BrokerTradeBustFact]

BROKER = BrokerId("alpaca")
ENVIRONMENT = EnvironmentId("paper")
ACCOUNT = AccountId("account-001")
SYMBOL = SymbolId("AAPL")
OTHER_SYMBOL = SymbolId("MSFT")
BUY_ORDER = OrderId("buy-order")
SELL_ORDER = OrderId("sell-order")
SCALE = PriceScale(Decimal("1"))
TICK = TickMetadata(tick_units=PriceUnits(1), scale=SCALE)


def _price(
    units: int,
    *,
    scale: PriceScale = SCALE,
    tick: TickMetadata = TICK,
) -> ReportedPrice:
    return ReportedPrice(units=PriceUnits(units), scale=scale, tick=tick)


def _scope(
    *,
    order_id: OrderId,
    side: ExecutionSide,
    broker: BrokerId = BROKER,
    environment: EnvironmentId = ENVIRONMENT,
    account: AccountId = ACCOUNT,
    symbol_id: SymbolId = SYMBOL,
) -> ExecutionScope:
    return ExecutionScope(
        broker=broker,
        environment=environment,
        account=account,
        order_id=order_id,
        symbol_id=symbol_id,
        side=side,
    )


def _key(
    event: str,
    *,
    broker: BrokerId = BROKER,
    environment: EnvironmentId = ENVIRONMENT,
    account: AccountId = ACCOUNT,
) -> ExecutionFactKey:
    return ExecutionFactKey(
        broker=broker,
        environment=environment,
        account=account,
        source_event_id=SourceEventId(event),
    )


def _root_key(
    root: str,
    *,
    broker: BrokerId = BROKER,
    environment: EnvironmentId = ENVIRONMENT,
    account: AccountId = ACCOUNT,
) -> RootFillKey:
    return RootFillKey(
        broker=broker,
        environment=environment,
        account=account,
        root_fill_id=RootFillId(root),
    )


def _fill(
    event: str,
    root: str,
    *,
    side: ExecutionSide,
    quantity: int,
    units: int,
    order_id: OrderId | None = None,
    price: ReportedPrice | None = None,
    scope: ExecutionScope | None = None,
    key: ExecutionFactKey | None = None,
) -> BrokerFillFact:
    resolved_order = order_id or (
        BUY_ORDER if side is ExecutionSide.BUY else SELL_ORDER
    )
    return BrokerFillFact(
        key=key or _key(event),
        scope=scope or _scope(order_id=resolved_order, side=side),
        root_fill_id=RootFillId(root),
        quantity=Quantity(quantity),
        price=price or _price(units),
    )


def _correct(
    event: str,
    root: str,
    predecessor: str,
    *,
    side: ExecutionSide,
    quantity: int,
    units: int,
    order_id: OrderId | None = None,
    price: ReportedPrice | None = None,
    scope: ExecutionScope | None = None,
    key: ExecutionFactKey | None = None,
) -> BrokerTradeCorrectFact:
    resolved_order = order_id or (
        BUY_ORDER if side is ExecutionSide.BUY else SELL_ORDER
    )
    return BrokerTradeCorrectFact(
        key=key or _key(event),
        scope=scope or _scope(order_id=resolved_order, side=side),
        root_fill_id=RootFillId(root),
        predecessor_source_event_id=SourceEventId(predecessor),
        revised_quantity=Quantity(quantity),
        revised_price=price or _price(units),
    )


def _bust(
    event: str,
    root: str,
    predecessor: str,
    *,
    side: ExecutionSide,
    order_id: OrderId | None = None,
    reported_price: ReportedPrice | None = None,
    scope: ExecutionScope | None = None,
    key: ExecutionFactKey | None = None,
) -> BrokerTradeBustFact:
    resolved_order = order_id or (
        BUY_ORDER if side is ExecutionSide.BUY else SELL_ORDER
    )
    return BrokerTradeBustFact(
        key=key or _key(event),
        scope=scope or _scope(order_id=resolved_order, side=side),
        root_fill_id=RootFillId(root),
        predecessor_source_event_id=SourceEventId(predecessor),
        reported_price=reported_price,
    )


@dataclass(frozen=True)
class _Kernel:
    position: PositionState
    integrity: PositionIntegrity
    root_heads: RootHeadIndex
    seen_facts: SeenFactIndex

    @classmethod
    def flat(cls) -> _Kernel:
        return cls(
            position=PositionState.flat(SYMBOL),
            integrity=PositionIntegrity.CONSISTENT,
            root_heads=RootHeadIndex.empty(),
            seen_facts=SeenFactIndex.empty(),
        )

    def apply(self, fact: BrokerFact) -> tuple[_Kernel, ExecutionTransition]:
        transition = apply_broker_execution_fact(
            self.position,
            self.integrity,
            self.root_heads,
            self.seen_facts,
            fact,
        )
        return (
            _Kernel(
                position=transition.position,
                integrity=transition.integrity,
                root_heads=transition.root_heads,
                seen_facts=transition.seen_facts,
            ),
            transition,
        )


def _apply_all(*facts: BrokerFact) -> tuple[_Kernel, list[ExecutionTransition]]:
    kernel = _Kernel.flat()
    transitions: list[ExecutionTransition] = []
    for fact in facts:
        kernel, transition = kernel.apply(fact)
        transitions.append(transition)
    return kernel, transitions


def _basis(value: int | Fraction) -> ExactBasis:
    return ExactBasis(Fraction(value))


def _oracle_fold(
    effective_heads: tuple[tuple[ExecutionSide, int, Fraction], ...],
) -> tuple[int, Fraction]:
    """Fold an independently supplied effective-head sequence with exact math."""

    quantity = 0
    basis = Fraction(0)
    for side, absolute_quantity, price in effective_heads:
        if side is ExecutionSide.BUY:
            next_quantity = quantity + absolute_quantity
            basis = (
                basis + absolute_quantity * price
                if quantity >= 0
                else max(next_quantity, 0) * price
            )
        else:
            next_quantity = quantity - absolute_quantity
            basis = (
                basis * Fraction(next_quantity, quantity)
                if quantity > 0 and next_quantity > 0
                else Fraction(0)
            )
        quantity = next_quantity
    return quantity, basis


def _assert_zero_economic_delta(
    before: _Kernel,
    transition: ExecutionTransition,
) -> None:
    assert transition.position == before.position
    assert transition.root_heads == before.root_heads
    assert transition.quantity_delta == 0
    assert transition.basis_delta == Fraction(0)


def _assert_reconciliation_no_economics(
    before: _Kernel,
    fact: BrokerFact,
) -> _Kernel:
    after, transition = before.apply(fact)
    _assert_zero_economic_delta(before, transition)
    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert (
        transition.original_classification
        is FirstObservationClassification.RECONCILIATION_REQUIRED
    )
    assert after.integrity & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    assert after.seen_facts != before.seen_facts
    return after


def test_first_buy_partial_sell_and_flat_use_exact_long_only_basis() -> None:
    buy = _fill("buy-1", "buy-root", side=ExecutionSide.BUY, quantity=10, units=100)
    sell_four = _fill(
        "sell-1", "sell-root-1", side=ExecutionSide.SELL, quantity=4, units=120
    )
    sell_six = _fill(
        "sell-2", "sell-root-2", side=ExecutionSide.SELL, quantity=6, units=80
    )

    kernel, buy_transition = _Kernel.flat().apply(buy)
    assert buy_transition.disposition is TransitionDisposition.APPLIED
    assert (
        buy_transition.original_classification
        is FirstObservationClassification.APPLIED_AVAILABLE
    )
    assert buy_transition.quantity_delta == 10
    assert buy_transition.basis_delta == Fraction(1000)
    assert kernel.position.raw_quantity == 10
    assert kernel.position.cost_basis == _basis(1000)
    assert kernel.position.average_price == Fraction(100)
    assert kernel.position.basis_authority is BasisAuthority.AVAILABLE
    assert kernel.position.authorized_residual_sell == Quantity(10)

    kernel, partial_transition = kernel.apply(sell_four)
    assert partial_transition.quantity_delta == -4
    assert partial_transition.basis_delta == Fraction(-400)
    assert kernel.position.raw_quantity == 6
    assert kernel.position.cost_basis == _basis(600)
    assert kernel.position.average_price == Fraction(100)
    assert kernel.position.authorized_residual_sell == Quantity(6)

    kernel, flat_transition = kernel.apply(sell_six)
    assert flat_transition.quantity_delta == -6
    assert flat_transition.basis_delta == Fraction(-600)
    assert kernel.position.raw_quantity == 0
    assert kernel.position.cost_basis == _basis(0)
    assert kernel.position.average_price is None
    assert kernel.position.authorized_residual_sell == Quantity(0)
    assert kernel.position.root_fill_sequence == (
        _root_key("buy-root"),
        _root_key("sell-root-1"),
        _root_key("sell-root-2"),
    )
    assert kernel.position.effective_head_ids == (
        SourceEventId("buy-1"),
        SourceEventId("sell-1"),
        SourceEventId("sell-2"),
    )


def test_exact_duplicate_is_noop_and_reports_original_classification() -> None:
    fact = _fill(
        "duplicate", "duplicate-root", side=ExecutionSide.BUY, quantity=3, units=25
    )
    after_first, first = _Kernel.flat().apply(fact)
    after_replay, replay = after_first.apply(fact)

    _assert_zero_economic_delta(after_first, replay)
    assert after_replay == after_first
    assert replay.disposition is TransitionDisposition.EXACT_REPLAY
    assert replay.original_classification is first.original_classification
    assert (
        replay.original_classification
        is FirstObservationClassification.APPLIED_AVAILABLE
    )
    assert after_replay.position.raw_quantity == 3
    assert after_replay.position.cost_basis == _basis(75)


def _revision_payload_mutation(
    field: str,
    original: BrokerTradeCorrectFact,
) -> BrokerFact:
    if field == "fact kind":
        return BrokerTradeBustFact(
            key=original.key,
            scope=original.scope,
            root_fill_id=original.root_fill_id,
            predecessor_source_event_id=original.predecessor_source_event_id,
        )
    if field == "predecessor":
        return replace(
            original, predecessor_source_event_id=SourceEventId("different-predecessor")
        )
    if field == "root":
        return replace(original, root_fill_id=RootFillId("different-root"))
    if field == "side":
        return replace(
            original,
            scope=replace(original.scope, side=ExecutionSide.SELL),
        )
    if field == "quantity":
        return replace(original, revised_quantity=Quantity(6))
    if field == "price":
        return replace(original, revised_price=_price(102))
    if field == "order scope":
        return replace(
            original,
            scope=replace(original.scope, order_id=OrderId("different-order")),
        )
    raise AssertionError(f"unhandled test mutation: {field}")


@pytest.mark.parametrize(
    "changed_field",
    ["fact kind", "predecessor", "root", "side", "quantity", "price", "order scope"],
)
def test_changed_same_key_conflicts_before_any_second_delta(changed_field: str) -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=10, units=100)
    correction = _correct(
        "correct", "root", "fill", side=ExecutionSide.BUY, quantity=7, units=101
    )
    kernel, _ = _apply_all(fill, correction)
    first_fact = kernel.seen_facts.get(correction.key)
    changed = _revision_payload_mutation(changed_field, correction)

    after, conflict = kernel.apply(changed)

    _assert_zero_economic_delta(kernel, conflict)
    assert conflict.disposition is TransitionDisposition.FACT_CONFLICT
    assert (
        conflict.original_classification
        is FirstObservationClassification.APPLIED_AVAILABLE
    )
    assert after.integrity & PositionIntegrity.EXECUTION_FACT_CONFLICT
    assert after.seen_facts.get(correction.key) == first_fact
    assert after.position.raw_quantity == 7
    assert after.position.cost_basis == _basis(707)


def test_rejected_first_observation_is_retained_across_replays() -> None:
    rejected = _correct(
        "arrived-too-soon",
        "missing-root",
        "missing-predecessor",
        side=ExecutionSide.BUY,
        quantity=7,
        units=101,
    )
    after_rejection = _assert_reconciliation_no_economics(_Kernel.flat(), rejected)

    after_exact, exact = after_rejection.apply(rejected)
    _assert_zero_economic_delta(after_rejection, exact)
    assert exact.disposition is TransitionDisposition.EXACT_REPLAY
    assert (
        exact.original_classification
        is FirstObservationClassification.RECONCILIATION_REQUIRED
    )
    assert after_exact == after_rejection

    changed = replace(rejected, revised_quantity=Quantity(8))
    after_changed, conflict = after_exact.apply(changed)
    _assert_zero_economic_delta(after_exact, conflict)
    assert conflict.disposition is TransitionDisposition.FACT_CONFLICT
    assert (
        conflict.original_classification
        is FirstObservationClassification.RECONCILIATION_REQUIRED
    )
    assert after_changed.integrity & PositionIntegrity.EXECUTION_FACT_CONFLICT
    assert after_changed.integrity & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    assert after_changed.seen_facts.get(rejected.key) == after_rejection.seen_facts.get(
        rejected.key
    )


def test_buy_ten_then_tail_bust_yields_exact_zero_quantity_and_basis() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=10, units=100)
    bust = _bust("bust", "root", "fill", side=ExecutionSide.BUY)
    kernel, transitions = _apply_all(fill, bust)

    assert transitions[-1].quantity_delta == -10
    assert transitions[-1].basis_delta == Fraction(-1000)
    assert transitions[-1].disposition is TransitionDisposition.APPLIED
    assert kernel.position.raw_quantity == 0
    assert kernel.position.cost_basis == _basis(0)
    assert kernel.position.basis_authority is BasisAuthority.AVAILABLE
    assert kernel.position.root_fill_sequence == (_root_key("root"),)
    assert kernel.position.effective_head_ids == (SourceEventId("bust"),)


def test_buy_ten_then_tail_correction_to_seven_at_101_yields_707() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=10, units=100)
    correction = _correct(
        "correct", "root", "fill", side=ExecutionSide.BUY, quantity=7, units=101
    )
    kernel, transitions = _apply_all(fill, correction)

    assert transitions[-1].quantity_delta == -3
    assert transitions[-1].basis_delta == Fraction(-293)
    assert (
        transitions[-1].original_classification
        is FirstObservationClassification.APPLIED_AVAILABLE
    )
    assert kernel.position.raw_quantity == 7
    assert kernel.position.cost_basis == _basis(707)
    assert kernel.position.average_price == Fraction(101)
    assert kernel.position.effective_head_ids == (SourceEventId("correct"),)


def test_non_tail_correction_commits_two_pending_and_slow_candidate_202_not_207() -> (
    None
):
    buy = _fill("buy", "buy-root", side=ExecutionSide.BUY, quantity=10, units=100)
    sell = _fill("sell", "sell-root", side=ExecutionSide.SELL, quantity=5, units=120)
    correction = _correct(
        "correct",
        "buy-root",
        "buy",
        side=ExecutionSide.BUY,
        quantity=7,
        units=101,
    )
    before, _ = _apply_all(buy, sell)
    after, transition = before.apply(correction)

    assert transition.disposition is TransitionDisposition.APPLIED
    assert (
        transition.original_classification
        is FirstObservationClassification.APPLIED_BASIS_PENDING
    )
    assert transition.quantity_delta == -3
    assert transition.basis_delta is None
    assert after.position.raw_quantity == 2
    assert after.position.basis_authority is BasisAuthority.BASIS_RECONCILIATION_PENDING
    assert after.position.cost_basis is None
    assert not hasattr(after.position, "basis_candidate")
    assert not hasattr(transition, "basis_candidate")
    assert after.position.root_fill_sequence == (
        _root_key("buy-root"),
        _root_key("sell-root"),
    )
    assert after.position.effective_head_ids == (
        SourceEventId("correct"),
        SourceEventId("sell"),
    )

    candidate = derive_ordered_basis_candidate(after.position, after.root_heads)
    assert candidate.status is BasisCandidateStatus.DERIVED
    assert candidate.raw_quantity == 2
    assert candidate.cost_basis == _basis(202)
    assert candidate.cost_basis != _basis(207)
    assert candidate.root_fill_sequence == after.position.root_fill_sequence
    assert candidate.effective_head_ids == after.position.effective_head_ids
    assert _oracle_fold(
        (
            (ExecutionSide.BUY, 7, Fraction(101)),
            (ExecutionSide.SELL, 5, Fraction(120)),
        )
    ) == (candidate.raw_quantity, candidate.cost_basis.value)


def test_fast_non_tail_revision_never_calls_slow_derivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buy = _fill("buy", "buy-root", side=ExecutionSide.BUY, quantity=10, units=100)
    sell = _fill("sell", "sell-root", side=ExecutionSide.SELL, quantity=5, units=120)
    correction = _correct(
        "correct",
        "buy-root",
        "buy",
        side=ExecutionSide.BUY,
        quantity=7,
        units=101,
    )
    before, _ = _apply_all(buy, sell)

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the fast non-tail path invoked the slow ordered fold")

    monkeypatch.setattr(
        position_module,
        "derive_ordered_basis_candidate",
        fail_if_called,
    )
    after, transition = before.apply(correction)

    assert transition.quantity_delta == -3
    assert transition.basis_delta is None
    assert after.position.raw_quantity == 2
    assert after.position.basis_authority is BasisAuthority.BASIS_RECONCILIATION_PENDING


def test_bust_of_earlier_buy_applies_negative_truth_and_permanent_quarantine() -> None:
    buy = _fill("buy", "buy-root", side=ExecutionSide.BUY, quantity=10, units=100)
    sell = _fill("sell", "sell-root", side=ExecutionSide.SELL, quantity=8, units=90)
    bust = _bust("bust", "buy-root", "buy", side=ExecutionSide.BUY)
    kernel, transitions = _apply_all(buy, sell, bust)

    assert transitions[-1].quantity_delta == -10
    assert transitions[-1].basis_delta is None
    assert (
        transitions[-1].original_classification
        is FirstObservationClassification.APPLIED_PENDING_OVERFILL
    )
    assert kernel.position.raw_quantity == -8
    assert kernel.position.cost_basis is None
    assert kernel.position.authorized_residual_sell == Quantity(0)
    assert kernel.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert kernel.position.effective_head_ids == (
        SourceEventId("bust"),
        SourceEventId("sell"),
    )

    covering = _fill(
        "cover", "cover-root", side=ExecutionSide.BUY, quantity=10, units=125
    )
    covered, _ = kernel.apply(covering)
    assert covered.position.raw_quantity == 2
    assert covered.position.authorized_residual_sell == Quantity(2)
    assert covered.integrity & PositionIntegrity.OVERFILL_QUARANTINE


def test_direct_sell_overfill_is_exact_not_clamped_rejected_or_flattened() -> None:
    overfill = _fill(
        "sell-overfill",
        "sell-root",
        side=ExecutionSide.SELL,
        quantity=3,
        units=100,
    )
    kernel, transition = _Kernel.flat().apply(overfill)

    assert transition.disposition is TransitionDisposition.APPLIED
    assert transition.quantity_delta == -3
    assert transition.basis_delta == Fraction(0)
    assert (
        transition.original_classification
        is FirstObservationClassification.APPLIED_OVERFILL_QUARANTINE
    )
    assert kernel.position.raw_quantity == -3
    assert kernel.position.cost_basis == _basis(0)
    assert kernel.position.average_price is None
    assert kernel.position.authorized_residual_sell == Quantity(0)
    assert kernel.integrity & PositionIntegrity.OVERFILL_QUARANTINE


def test_covering_buy_establishes_only_long_remainder_basis_and_keeps_latch() -> None:
    sell = _fill("sell", "sell-root", side=ExecutionSide.SELL, quantity=8, units=90)
    cover = _fill("cover", "buy-root", side=ExecutionSide.BUY, quantity=10, units=125)
    kernel, _ = _apply_all(sell, cover)

    assert kernel.position.raw_quantity == 2
    assert kernel.position.cost_basis == _basis(250)
    assert kernel.position.average_price == Fraction(125)
    assert kernel.position.authorized_residual_sell == Quantity(2)
    assert kernel.integrity & PositionIntegrity.OVERFILL_QUARANTINE


def test_buy_that_only_partly_covers_short_keeps_zero_long_basis_and_latch() -> None:
    sell = _fill("sell", "sell-root", side=ExecutionSide.SELL, quantity=8, units=90)
    cover = _fill("cover", "buy-root", side=ExecutionSide.BUY, quantity=5, units=125)
    kernel, _ = _apply_all(sell, cover)

    assert kernel.position.raw_quantity == -3
    assert kernel.position.cost_basis == _basis(0)
    assert kernel.position.authorized_residual_sell == Quantity(0)
    assert kernel.integrity & PositionIntegrity.OVERFILL_QUARANTINE


def test_missing_predecessor_is_reconciliation_with_zero_economics() -> None:
    root = _fill("fill", "root", side=ExecutionSide.BUY, quantity=10, units=100)
    kernel, _ = _apply_all(root)
    missing = _correct(
        "missing",
        "root",
        "unknown",
        side=ExecutionSide.BUY,
        quantity=7,
        units=101,
    )
    _assert_reconciliation_no_economics(kernel, missing)


def test_stale_predecessor_after_deep_chain_is_rejected() -> None:
    root = _fill("fill", "root", side=ExecutionSide.BUY, quantity=10, units=100)
    first = _correct(
        "correct-1", "root", "fill", side=ExecutionSide.BUY, quantity=9, units=101
    )
    second = _correct(
        "correct-2",
        "root",
        "correct-1",
        side=ExecutionSide.BUY,
        quantity=8,
        units=102,
    )
    kernel, _ = _apply_all(root, first, second)
    stale = _bust("stale", "root", "correct-1", side=ExecutionSide.BUY)
    _assert_reconciliation_no_economics(kernel, stale)


def test_branched_revision_from_already_replaced_predecessor_is_rejected() -> None:
    root = _fill("fill", "root", side=ExecutionSide.BUY, quantity=10, units=100)
    winning_child = _correct(
        "winner", "root", "fill", side=ExecutionSide.BUY, quantity=9, units=101
    )
    kernel, _ = _apply_all(root, winning_child)
    branch = _correct(
        "branch", "root", "fill", side=ExecutionSide.BUY, quantity=8, units=102
    )
    _assert_reconciliation_no_economics(kernel, branch)


def test_out_of_order_revision_remains_rejected_after_predecessor_arrives() -> None:
    root = _fill("fill", "root", side=ExecutionSide.BUY, quantity=10, units=100)
    predecessor = _correct(
        "correct-1", "root", "fill", side=ExecutionSide.BUY, quantity=9, units=101
    )
    arrived_early = _correct(
        "correct-2",
        "root",
        "correct-1",
        side=ExecutionSide.BUY,
        quantity=8,
        units=102,
    )
    kernel, _ = _apply_all(root)
    rejected = _assert_reconciliation_no_economics(kernel, arrived_early)
    after_predecessor, applied = rejected.apply(predecessor)
    assert applied.disposition is TransitionDisposition.APPLIED

    replayed, replay = after_predecessor.apply(arrived_early)
    _assert_zero_economic_delta(after_predecessor, replay)
    assert replay.disposition is TransitionDisposition.EXACT_REPLAY
    assert (
        replay.original_classification
        is FirstObservationClassification.RECONCILIATION_REQUIRED
    )
    assert replayed.position.raw_quantity == 9


def test_revision_naming_another_root_is_rejected() -> None:
    first = _fill("first", "root-1", side=ExecutionSide.BUY, quantity=5, units=100)
    second = _fill("second", "root-2", side=ExecutionSide.BUY, quantity=5, units=110)
    kernel, _ = _apply_all(first, second)
    root_conflict = _correct(
        "wrong-root",
        "root-2",
        "first",
        side=ExecutionSide.BUY,
        quantity=3,
        units=105,
        order_id=BUY_ORDER,
    )
    _assert_reconciliation_no_economics(kernel, root_conflict)


def _scope_conflict(
    conflict: str,
    base_scope: ExecutionScope,
) -> tuple[ExecutionFactKey, ExecutionScope]:
    if conflict == "broker":
        broker = BrokerId("other-broker")
        return _key("scope-broker", broker=broker), replace(base_scope, broker=broker)
    if conflict == "environment":
        environment = EnvironmentId("other-environment")
        return _key("scope-environment", environment=environment), replace(
            base_scope, environment=environment
        )
    if conflict == "account":
        account = AccountId("other-account")
        return _key("scope-account", account=account), replace(
            base_scope, account=account
        )
    if conflict == "order":
        return _key("scope-order"), replace(base_scope, order_id=OrderId("other-order"))
    if conflict == "symbol":
        return _key("scope-symbol"), replace(base_scope, symbol_id=OTHER_SYMBOL)
    if conflict == "side":
        return _key("scope-side"), replace(base_scope, side=ExecutionSide.SELL)
    raise AssertionError(f"unhandled scope conflict: {conflict}")


@pytest.mark.parametrize(
    "conflict",
    ["broker", "environment", "account", "order", "symbol", "side"],
)
def test_every_complete_scope_conflict_is_reconciliation(conflict: str) -> None:
    root = _fill("fill", "root", side=ExecutionSide.BUY, quantity=10, units=100)
    kernel, _ = _apply_all(root)
    key, scope = _scope_conflict(conflict, root.scope)
    revision = _correct(
        f"scope-{conflict}",
        "root",
        "fill",
        side=scope.side,
        quantity=7,
        units=101,
        scope=scope,
        key=key,
    )
    _assert_reconciliation_no_economics(kernel, revision)


def test_fresh_source_event_reusing_root_fill_key_is_rejected() -> None:
    root = _fill("first", "root", side=ExecutionSide.BUY, quantity=3, units=100)
    collision = _fill("second", "root", side=ExecutionSide.BUY, quantity=4, units=101)
    kernel, _ = _apply_all(root)

    after = _assert_reconciliation_no_economics(kernel, collision)
    assert after.position.root_fill_sequence == (_root_key("root"),)
    assert after.position.effective_head_ids == (SourceEventId("first"),)


def test_revision_substitutes_head_at_original_sequence_without_append() -> None:
    first = _fill("first", "root-1", side=ExecutionSide.BUY, quantity=10, units=100)
    second = _fill("second", "root-2", side=ExecutionSide.SELL, quantity=5, units=120)
    revision = _correct(
        "revision",
        "root-1",
        "first",
        side=ExecutionSide.BUY,
        quantity=7,
        units=101,
    )
    kernel, _ = _apply_all(first, second, revision)

    assert kernel.position.root_fill_sequence == (
        _root_key("root-1"),
        _root_key("root-2"),
    )
    assert kernel.position.effective_head_ids == (
        SourceEventId("revision"),
        SourceEventId("second"),
    )
    assert len(kernel.root_heads.entries) == 2
    assert kernel.position.raw_quantity == 2


def test_deep_tail_revision_chain_replaces_once_per_head() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=10, units=100)
    correction_one = _correct(
        "correct-1", "root", "fill", side=ExecutionSide.BUY, quantity=8, units=110
    )
    correction_two = _correct(
        "correct-2",
        "root",
        "correct-1",
        side=ExecutionSide.BUY,
        quantity=6,
        units=120,
    )
    bust = _bust("bust", "root", "correct-2", side=ExecutionSide.BUY)
    kernel, transitions = _apply_all(fill, correction_one, correction_two, bust)

    assert [transition.quantity_delta for transition in transitions] == [10, -2, -2, -6]
    assert [transition.basis_delta for transition in transitions] == [
        Fraction(1000),
        Fraction(-120),
        Fraction(-160),
        Fraction(-720),
    ]
    assert kernel.position.raw_quantity == 0
    assert kernel.position.cost_basis == _basis(0)
    assert kernel.position.root_fill_sequence == (_root_key("root"),)
    assert kernel.position.effective_head_ids == (SourceEventId("bust"),)
    assert len(kernel.root_heads.entries) == 1


@pytest.mark.parametrize(
    "incompatible_price",
    [
        ReportedPrice(
            units=PriceUnits(101),
            scale=SCALE,
            tick=TickMetadata(tick_units=PriceUnits(2), scale=SCALE),
        ),
        ReportedPrice(
            units=PriceUnits(101),
            scale=PriceScale(Decimal("0.01")),
            tick=TickMetadata(
                tick_units=PriceUnits(1),
                scale=PriceScale(Decimal("0.1")),
            ),
        ),
    ],
)
def test_incompatible_first_fill_applies_quantity_truth_but_withholds_basis(
    incompatible_price: ReportedPrice,
) -> None:
    fact = _fill(
        "incompatible",
        "root",
        side=ExecutionSide.BUY,
        quantity=3,
        units=101,
        price=incompatible_price,
    )
    kernel, transition = _Kernel.flat().apply(fact)

    assert transition.disposition is TransitionDisposition.APPLIED
    assert transition.quantity_delta == 3
    assert transition.basis_delta is None
    assert (
        transition.original_classification
        is FirstObservationClassification.APPLIED_BASIS_PENDING
    )
    assert kernel.position.raw_quantity == 3
    assert kernel.position.cost_basis is None
    assert (
        kernel.position.basis_authority is BasisAuthority.BASIS_RECONCILIATION_PENDING
    )
    assert kernel.root_heads.get(_root_key("root")) is not None

    candidate = derive_ordered_basis_candidate(kernel.position, kernel.root_heads)
    assert candidate.status is BasisCandidateStatus.INCOMPATIBLE_PRICE_METADATA
    assert candidate.cost_basis is None


def test_incompatible_tail_correction_advances_head_and_quantity_pending() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=10, units=100)
    incompatible = ReportedPrice(
        units=PriceUnits(7),
        scale=PriceScale(Decimal("0.1")),
        tick=TickMetadata(
            tick_units=PriceUnits(1),
            scale=PriceScale(Decimal("0.01")),
        ),
    )
    correction = _correct(
        "correct",
        "root",
        "fill",
        side=ExecutionSide.BUY,
        quantity=7,
        units=7,
        price=incompatible,
    )
    kernel, transitions = _apply_all(fill, correction)

    assert transitions[-1].quantity_delta == -3
    assert transitions[-1].basis_delta is None
    assert kernel.position.raw_quantity == 7
    assert kernel.position.cost_basis is None
    assert (
        kernel.position.basis_authority is BasisAuthority.BASIS_RECONCILIATION_PENDING
    )
    assert kernel.position.effective_head_ids == (SourceEventId("correct"),)
    assert kernel.root_heads.get(
        _root_key("root")
    ).current_source_event_id == SourceEventId("correct")


def test_human_attested_root_cannot_be_corrected_or_busted() -> None:
    root_key = _root_key("human-root")
    event_id = SourceEventId("human-fill")
    price = _price(100)
    human_head = RootHead(
        root_key=root_key,
        original_sequence=0,
        scope=_scope(order_id=BUY_ORDER, side=ExecutionSide.BUY),
        authority=ExecutionAuthority.HUMAN_ATTESTED,
        current_source_event_id=event_id,
        kind=FactKind.FILL,
        quantity=Quantity(2),
        price=price,
    )
    position = PositionState(
        symbol_id=SYMBOL,
        raw_quantity=2,
        basis_authority=BasisAuthority.AVAILABLE,
        cost_basis=_basis(200),
        root_fill_sequence=(root_key,),
        effective_head_ids=(event_id,),
        basis_price_metadata=price,
        tail_fold_input=FoldInput(
            raw_quantity=0,
            cost_basis=_basis(0),
            price_metadata=None,
        ),
    )
    kernel = _Kernel(
        position=position,
        integrity=PositionIntegrity.CONSISTENT,
        root_heads=RootHeadIndex.empty().append(human_head),
        seen_facts=SeenFactIndex.empty(),
    )

    correction = _correct(
        "broker-correction",
        "human-root",
        "human-fill",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
    )
    after_correction = _assert_reconciliation_no_economics(kernel, correction)
    bust = _bust(
        "broker-bust",
        "human-root",
        "human-fill",
        side=ExecutionSide.BUY,
    )
    _assert_reconciliation_no_economics(after_correction, bust)


@dataclass(frozen=True)
class _HumanAttestedEconomicInput:
    authority: ExecutionAuthority = ExecutionAuthority.HUMAN_ATTESTED


def test_nonbroker_or_non_fill_family_input_is_structurally_rejected() -> None:
    kernel = _Kernel.flat()
    invalid = _HumanAttestedEconomicInput()

    with pytest.raises(TypeError):
        apply_broker_execution_fact(
            kernel.position,
            kernel.integrity,
            kernel.root_heads,
            kernel.seen_facts,
            invalid,  # type: ignore[arg-type]
        )

    assert kernel == _Kernel.flat()


def test_conflict_reconciliation_and_overfill_flags_are_combined_and_monotonic() -> (
    None
):
    overfill = _fill(
        "sell", "sell-root", side=ExecutionSide.SELL, quantity=3, units=100
    )
    kernel, _ = _apply_all(overfill)
    assert kernel.integrity == PositionIntegrity.OVERFILL_QUARANTINE

    changed_same_key = replace(overfill, quantity=Quantity(4))
    kernel, conflict = kernel.apply(changed_same_key)
    assert conflict.disposition is TransitionDisposition.FACT_CONFLICT
    assert kernel.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert kernel.integrity & PositionIntegrity.EXECUTION_FACT_CONFLICT

    missing = _correct(
        "missing",
        "unknown-root",
        "unknown-predecessor",
        side=ExecutionSide.BUY,
        quantity=1,
        units=100,
    )
    kernel = _assert_reconciliation_no_economics(kernel, missing)
    expected = (
        PositionIntegrity.OVERFILL_QUARANTINE
        | PositionIntegrity.EXECUTION_FACT_CONFLICT
        | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    assert kernel.integrity == expected

    cover = _fill("cover", "buy-root", side=ExecutionSide.BUY, quantity=5, units=125)
    kernel, _ = kernel.apply(cover)
    assert kernel.position.raw_quantity == 2
    assert kernel.integrity == expected


def test_transition_is_deterministic_and_does_not_mutate_any_input() -> None:
    kernel = _Kernel.flat()
    fact = _fill("fill", "root", side=ExecutionSide.BUY, quantity=3, units=100)
    original_position = kernel.position
    original_integrity = kernel.integrity
    original_heads = kernel.root_heads
    original_seen = kernel.seen_facts

    first = apply_broker_execution_fact(
        original_position,
        original_integrity,
        original_heads,
        original_seen,
        fact,
    )
    second = apply_broker_execution_fact(
        original_position,
        original_integrity,
        original_heads,
        original_seen,
        fact,
    )

    assert first == second
    assert kernel == _Kernel.flat()
    assert fact.quantity == Quantity(3)
    with pytest.raises(FrozenInstanceError):
        setattr(fact, "quantity", Quantity(999))
    with pytest.raises(FrozenInstanceError):
        setattr(first.position, "raw_quantity", 999)
    with pytest.raises(FrozenInstanceError):
        setattr(first.root_heads, "entries", ())
    with pytest.raises(FrozenInstanceError):
        setattr(first.seen_facts, "entries", ())


@pytest.mark.parametrize(
    ("facts", "effective_heads"),
    [
        (
            (
                _fill("b1", "r1", side=ExecutionSide.BUY, quantity=10, units=100),
                _fill("s1", "r2", side=ExecutionSide.SELL, quantity=4, units=90),
                _fill("b2", "r3", side=ExecutionSide.BUY, quantity=2, units=130),
            ),
            (
                (ExecutionSide.BUY, 10, Fraction(100)),
                (ExecutionSide.SELL, 4, Fraction(90)),
                (ExecutionSide.BUY, 2, Fraction(130)),
            ),
        ),
        (
            (
                _fill("b3", "r4", side=ExecutionSide.BUY, quantity=10, units=100),
                _fill("s2", "r5", side=ExecutionSide.SELL, quantity=5, units=120),
                _correct(
                    "c3",
                    "r4",
                    "b3",
                    side=ExecutionSide.BUY,
                    quantity=7,
                    units=101,
                ),
            ),
            (
                (ExecutionSide.BUY, 7, Fraction(101)),
                (ExecutionSide.SELL, 5, Fraction(120)),
            ),
        ),
        (
            (
                _fill("s3", "r6", side=ExecutionSide.SELL, quantity=8, units=90),
                _fill("b4", "r7", side=ExecutionSide.BUY, quantity=10, units=125),
            ),
            (
                (ExecutionSide.SELL, 8, Fraction(90)),
                (ExecutionSide.BUY, 10, Fraction(125)),
            ),
        ),
    ],
)
def test_fraction_oracle_agrees_with_separate_ordered_candidate(
    facts: tuple[BrokerFact, ...],
    effective_heads: tuple[tuple[ExecutionSide, int, Fraction], ...],
) -> None:
    kernel, _ = _apply_all(*facts)
    expected_quantity, expected_basis = _oracle_fold(effective_heads)
    candidate = derive_ordered_basis_candidate(kernel.position, kernel.root_heads)

    assert candidate.status is BasisCandidateStatus.DERIVED
    assert candidate.raw_quantity == expected_quantity
    assert candidate.cost_basis == ExactBasis(expected_basis)
    assert candidate.root_fill_sequence == kernel.position.root_fill_sequence
    assert candidate.effective_head_ids == kernel.position.effective_head_ids
    assert kernel.position.raw_quantity == expected_quantity
    if kernel.position.basis_authority is BasisAuthority.AVAILABLE:
        assert kernel.position.cost_basis == ExactBasis(expected_basis)
    else:
        assert kernel.position.cost_basis is None


def test_candidate_rejects_inconsistent_snapshot_instead_of_guessing() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=3, units=100)
    kernel, _ = _apply_all(fill)
    inconsistent = replace(
        kernel.position,
        effective_head_ids=(SourceEventId("not-the-head"),),
    )

    candidate = derive_ordered_basis_candidate(inconsistent, kernel.root_heads)

    assert candidate.status is BasisCandidateStatus.SNAPSHOT_INCONSISTENT
    assert candidate.cost_basis is None


def test_bust_optional_reported_metadata_can_make_basis_pending_without_blocking_truth() -> (
    None
):
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=3, units=100)
    incompatible = ReportedPrice(
        units=PriceUnits(3),
        scale=SCALE,
        tick=TickMetadata(tick_units=PriceUnits(2), scale=SCALE),
    )
    bust = _bust(
        "bust",
        "root",
        "fill",
        side=ExecutionSide.BUY,
        reported_price=incompatible,
    )
    kernel, transitions = _apply_all(fill, bust)

    assert transitions[-1].quantity_delta == -3
    assert transitions[-1].basis_delta is None
    assert kernel.position.raw_quantity == 0
    assert kernel.position.cost_basis is None
    assert (
        kernel.position.basis_authority is BasisAuthority.BASIS_RECONCILIATION_PENDING
    )


def test_revision_rejection_preserves_prior_combined_integrity() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    kernel, _ = _apply_all(fill)
    seeded = replace(
        kernel,
        integrity=(
            PositionIntegrity.EXECUTION_FACT_CONFLICT
            | PositionIntegrity.OVERFILL_QUARANTINE
        ),
    )
    invalid = _correct(
        "invalid",
        "root",
        "missing",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
    )

    after = _assert_reconciliation_no_economics(seeded, invalid)

    assert after.integrity == (
        PositionIntegrity.EXECUTION_FACT_CONFLICT
        | PositionIntegrity.OVERFILL_QUARANTINE
        | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )


@pytest.mark.parametrize(
    "revision_factory",
    [
        lambda: _correct(
            "revision",
            "root",
            "human-fill",
            side=ExecutionSide.BUY,
            quantity=1,
            units=101,
        ),
        lambda: _bust("revision", "root", "human-fill", side=ExecutionSide.BUY),
    ],
    ids=["correct", "bust"],
)
def test_each_revision_kind_rejects_human_authority(
    revision_factory: Callable[[], BrokerFact],
) -> None:
    root_key = _root_key("root")
    head_id = SourceEventId("human-fill")
    price = _price(100)
    root_head = RootHead(
        root_key=root_key,
        original_sequence=0,
        scope=_scope(order_id=BUY_ORDER, side=ExecutionSide.BUY),
        authority=ExecutionAuthority.HUMAN_ATTESTED,
        current_source_event_id=head_id,
        kind=FactKind.FILL,
        quantity=Quantity(2),
        price=price,
    )
    kernel = _Kernel(
        position=PositionState(
            symbol_id=SYMBOL,
            raw_quantity=2,
            basis_authority=BasisAuthority.AVAILABLE,
            cost_basis=_basis(200),
            root_fill_sequence=(root_key,),
            effective_head_ids=(head_id,),
            basis_price_metadata=price,
            tail_fold_input=FoldInput(
                raw_quantity=0,
                cost_basis=_basis(0),
                price_metadata=None,
            ),
        ),
        integrity=PositionIntegrity.CONSISTENT,
        root_heads=RootHeadIndex.empty().append(root_head),
        seen_facts=SeenFactIndex.empty(),
    )

    _assert_reconciliation_no_economics(kernel, revision_factory())
