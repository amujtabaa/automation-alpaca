"""Deterministic RED examples for the reset execution-fact semantic center.

The arithmetic oracle in this module is deliberately test-owned.  It is derived
from the accepted ordered long-only equations and uses :class:`Fraction`; it
does not import the incumbent projector or mirror the production reducer.
"""

from __future__ import annotations

import ast
import inspect
import sys
from dataclasses import FrozenInstanceError, dataclass, replace
from decimal import Decimal
from fractions import Fraction
from textwrap import dedent
from types import FrameType
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
    PositionScope,
    RootHead,
    SeenFact,
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
POSITION_SCOPE = PositionScope(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    symbol_id=SYMBOL,
)
OTHER_POSITION_SCOPE = PositionScope(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    symbol_id=OTHER_SYMBOL,
)
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
    def flat(cls, scope: PositionScope = POSITION_SCOPE) -> _Kernel:
        snapshot = ExecutionSnapshot.flat(scope)
        return cls(
            position=snapshot.position,
            integrity=snapshot.integrity,
            root_heads=snapshot.root_heads,
            seen_facts=snapshot.seen_facts,
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


def _coherently_bound_human_kernel() -> _Kernel:
    """Build a test-only human root that reaches authority-specific guards."""

    scope = _scope(order_id=BUY_ORDER, side=ExecutionSide.BUY)
    fill = _fill(
        "human-fill",
        "human-root",
        side=ExecutionSide.BUY,
        quantity=2,
        units=100,
        scope=scope,
    )
    broker_kernel, _ = _Kernel.flat().apply(fill)
    broker_head = broker_kernel.root_heads.get(fill.root_key)
    assert broker_head is not None
    head = replace(
        broker_head,
        authority=ExecutionAuthority.HUMAN_ATTESTED,
    )
    roots = RootHeadIndex(entries=(head,), position_scope=POSITION_SCOPE)
    snapshot = position_module._bind_components(
        replace(broker_kernel.position, _binding=None),
        PositionIntegrity.CONSISTENT,
        roots,
        SeenFactIndex(
            entries=(
                SeenFact(
                    fact=fill,
                    classification=FirstObservationClassification.APPLIED_AVAILABLE,
                ),
            )
        ),
    )
    return _Kernel(
        position=snapshot.position,
        integrity=snapshot.integrity,
        root_heads=snapshot.root_heads,
        seen_facts=snapshot.seen_facts,
    )


def _unbound_hydration_parts(
    kernel: _Kernel,
) -> tuple[PositionState, RootHeadIndex, SeenFactIndex]:
    """Materialize persisted-style parts without trusting a prior binding."""

    return (
        replace(kernel.position, _binding=None),
        RootHeadIndex(
            entries=kernel.root_heads.entries,
            position_scope=kernel.position.scope,
        ),
        SeenFactIndex(entries=kernel.seen_facts.entries),
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


@dataclass(frozen=True)
class _LongLot:
    """One test-owned average-cost lot after proportional retention."""

    quantity: Fraction
    notional: Fraction


def _oracle_fold(
    effective_heads: tuple[tuple[ExecutionSide, int, Fraction], ...],
) -> tuple[int, Fraction]:
    """Price a signed tape through a conceptual long-lot ledger.

    BUY facts create only the portion newly carried as a long lot. SELL facts
    retain the same fraction of every open lot as remains long. The oracle's
    basis is therefore the sum of retained lot notionals, rather than a copy of
    the reducer's scalar basis branches.
    """

    raw_quantity = 0
    long_lots: list[_LongLot] = []
    for side, absolute_quantity, price in effective_heads:
        if side is ExecutionSide.BUY:
            newly_long = max(raw_quantity + absolute_quantity, 0) - max(raw_quantity, 0)
            if newly_long:
                long_lots.append(
                    _LongLot(
                        quantity=Fraction(newly_long),
                        notional=Fraction(newly_long) * price,
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
        raw_quantity += (
            absolute_quantity if side is ExecutionSide.BUY else -absolute_quantity
        )
        assert sum((lot.quantity for lot in long_lots), Fraction(0)) == max(
            raw_quantity, 0
        )
    return raw_quantity, sum(
        (lot.notional for lot in long_lots),
        Fraction(0),
    )


def _assert_zero_economic_delta(
    before: _Kernel,
    transition: ExecutionTransition,
) -> None:
    assert (
        replace(
            transition.position,
            integrity_floor=before.position.integrity_floor,
        )
        == before.position
    )
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
    monkeypatch.setattr(position_module, "_fold_ordered_heads", fail_if_called)
    monkeypatch.setattr(RootHeadIndex, "entries", property(fail_if_called))
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


def test_rejected_first_observation_still_reserves_root_fill_key() -> None:
    rejected_scope = _scope(
        order_id=BUY_ORDER,
        side=ExecutionSide.BUY,
        symbol_id=OTHER_SYMBOL,
    )
    rejected = _fill(
        "rejected",
        "reserved-root",
        side=ExecutionSide.BUY,
        quantity=3,
        units=100,
        scope=rejected_scope,
    )
    first = _assert_reconciliation_no_economics(_Kernel.flat(), rejected)
    assert first.seen_facts.contains_root(rejected.root_key)
    assert SeenFactIndex(entries=first.seen_facts.entries).contains_root(
        rejected.root_key
    )
    reuse = _fill(
        "reuse",
        "reserved-root",
        side=ExecutionSide.BUY,
        quantity=4,
        units=101,
    )

    after = _assert_reconciliation_no_economics(first, reuse)

    assert after.position.root_count == 0
    assert after.root_heads.count == 0
    assert after.seen_facts.count == 2
    assert after.seen_facts.contains_root(rejected.root_key)


@pytest.mark.parametrize("revision_kind", ["correction", "bust"])
def test_rejected_revision_reserves_root_against_later_fill(
    revision_kind: str,
) -> None:
    if revision_kind == "correction":
        rejected: BrokerFact = _correct(
            "rejected-revision",
            "reserved-root",
            "missing-predecessor",
            side=ExecutionSide.BUY,
            quantity=3,
            units=100,
        )
    else:
        rejected = _bust(
            "rejected-revision",
            "reserved-root",
            "missing-predecessor",
            side=ExecutionSide.BUY,
        )
    first = _assert_reconciliation_no_economics(_Kernel.flat(), rejected)
    reuse = _fill(
        "reuse",
        "reserved-root",
        side=ExecutionSide.BUY,
        quantity=4,
        units=101,
    )

    after = _assert_reconciliation_no_economics(first, reuse)

    assert after.position.raw_quantity == 0
    assert after.root_heads.count == 0
    assert after.seen_facts.count == 2


def test_seen_fact_commitment_covers_observed_root_reservations() -> None:
    rejected = _fill(
        "rejected",
        "reserved-root",
        side=ExecutionSide.BUY,
        quantity=3,
        units=100,
        scope=_scope(
            order_id=BUY_ORDER,
            side=ExecutionSide.BUY,
            symbol_id=OTHER_SYMBOL,
        ),
    )
    reserved = SeenFactIndex.empty().add(
        SeenFact(
            fact=rejected,
            classification=FirstObservationClassification.RECONCILIATION_REQUIRED,
        )
    )
    unreserved = SeenFactIndex._from_parts(
        by_key=reserved._by_key,
        order=reserved._order,
        observed_roots=type(reserved._observed_roots).empty(),
        overfill_scopes=reserved._overfill_scopes,
        account_scope=reserved.account_scope,
    )

    assert unreserved.entries == reserved.entries
    assert not unreserved.contains_root(rejected.root_key)
    assert unreserved != reserved
    assert unreserved.commitment != reserved.commitment
    assert not reserved.contains_root(
        _root_key(
            "reserved-root",
            account=AccountId("different-account"),
        )
    )


def test_seen_registry_value_identity_carries_account_owner() -> None:
    owned = SeenFactIndex.empty(POSITION_SCOPE)
    same_account_other_symbol = SeenFactIndex.empty(OTHER_POSITION_SCOPE)
    other_account = SeenFactIndex.empty(
        replace(POSITION_SCOPE, account=AccountId("other-account"))
    )
    unowned = SeenFactIndex.empty()

    assert owned == same_account_other_symbol
    assert owned.commitment == same_account_other_symbol.commitment
    assert owned != other_account
    assert owned != unowned
    assert owned.commitment != other_account.commitment
    assert owned.commitment != unowned.commitment


def test_seen_registry_rejects_mixed_or_forged_evaluation_scope() -> None:
    fact = _fill(
        "scope-fact",
        "scope-root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=100,
    )
    with pytest.raises(ValueError, match="applied first observation"):
        SeenFact(
            fact=fact,
            classification=FirstObservationClassification.APPLIED_AVAILABLE,
            position_scope=OTHER_POSITION_SCOPE,
        )
    foreign_evaluation_scope = replace(
        POSITION_SCOPE,
        account=AccountId("foreign-evaluation-account"),
    )
    rejected_foreign_evaluation = SeenFact(
        fact=fact,
        classification=FirstObservationClassification.RECONCILIATION_REQUIRED,
        position_scope=foreign_evaluation_scope,
    )

    with pytest.raises(ValueError, match="cannot mix evaluation accounts"):
        SeenFactIndex.empty(POSITION_SCOPE).add(rejected_foreign_evaluation)


def test_seen_registry_commitment_carries_overfill_summary() -> None:
    overfill = _fill(
        "overfill",
        "sell-root",
        side=ExecutionSide.SELL,
        quantity=3,
        units=100,
    )
    quarantined, _ = _apply_all(overfill)
    authentic = quarantined.seen_facts
    assert authentic.has_overfill_observation(POSITION_SCOPE)
    forged = SeenFactIndex._from_parts(
        by_key=authentic._by_key,
        order=authentic._order,
        observed_roots=authentic._observed_roots,
        overfill_scopes=type(authentic._overfill_scopes).empty(),
        account_scope=authentic.account_scope,
    )
    position, roots, _ = _unbound_hydration_parts(quarantined)

    assert forged.entries == authentic.entries
    assert forged != authentic
    assert forged.commitment != authentic.commitment
    with pytest.raises(ValueError, match="seen-fact replay did not close exactly"):
        ExecutionSnapshot.bind_verified(
            position,
            quarantined.integrity,
            roots,
            forged,
        )


def test_seen_fact_commits_reconciliation_evaluation_scope() -> None:
    misrouted = _fill(
        "misrouted",
        "misrouted-root",
        side=ExecutionSide.BUY,
        quantity=3,
        units=100,
        scope=_scope(
            order_id=OrderId("other-order"),
            side=ExecutionSide.BUY,
            symbol_id=OTHER_SYMBOL,
        ),
    )
    rejected = _assert_reconciliation_no_economics(_Kernel.flat(), misrouted)
    observation = rejected.seen_facts.get(misrouted.key)
    assert observation is not None
    assert observation.position_scope == POSITION_SCOPE
    forged_observation = replace(
        observation,
        position_scope=OTHER_POSITION_SCOPE,
    )
    forged_seen = SeenFactIndex(
        entries=(forged_observation,),
        position_scope=POSITION_SCOPE,
    )
    position, roots, _ = _unbound_hydration_parts(rejected)

    assert forged_observation.commitment != observation.commitment
    with pytest.raises(ValueError, match="classification is not reproducible"):
        ExecutionSnapshot.bind_verified(
            position,
            rejected.integrity,
            roots,
            forged_seen,
        )


def test_bind_verified_rejects_unclosed_observed_root_reservations() -> None:
    rejected = _fill(
        "rejected",
        "reserved-root",
        side=ExecutionSide.BUY,
        quantity=3,
        units=100,
        scope=_scope(
            order_id=BUY_ORDER,
            side=ExecutionSide.BUY,
            symbol_id=OTHER_SYMBOL,
        ),
    )
    expected = _assert_reconciliation_no_economics(_Kernel.flat(), rejected)
    position, roots, seen = _unbound_hydration_parts(expected)
    unreserved = SeenFactIndex._from_parts(
        by_key=seen._by_key,
        order=seen._order,
        observed_roots=type(seen._observed_roots).empty(),
        overfill_scopes=seen._overfill_scopes,
        account_scope=seen.account_scope,
    )

    with pytest.raises(ValueError, match="seen-fact replay did not close exactly"):
        ExecutionSnapshot.bind_verified(
            position,
            expected.integrity,
            roots,
            unreserved,
        )


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
    kernel = _coherently_bound_human_kernel()

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
    with pytest.raises((FrozenInstanceError, TypeError)):
        setattr(first.root_heads, "entries", ())
    with pytest.raises((FrozenInstanceError, TypeError)):
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
    inconsistent = PositionState.from_materialized(
        scope=kernel.position.scope,
        raw_quantity=kernel.position.raw_quantity,
        basis_authority=kernel.position.basis_authority,
        cost_basis=kernel.position.cost_basis,
        root_fill_sequence=kernel.position.root_fill_sequence,
        effective_head_ids=(SourceEventId("not-the-head"),),
        basis_price_metadata=kernel.position.basis_price_metadata,
        tail_fold_input=kernel.position.tail_fold_input,
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


def test_applied_revision_preserves_prior_combined_integrity() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    kernel, _ = _apply_all(fill)
    changed_replay = replace(fill, price=_price(101))
    kernel, conflict = kernel.apply(changed_replay)
    assert conflict.disposition is TransitionDisposition.FACT_CONFLICT
    root_reuse = _fill(
        "root-reuse",
        "root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=102,
    )
    kernel = _assert_reconciliation_no_economics(kernel, root_reuse)
    expected = (
        PositionIntegrity.EXECUTION_FACT_CONFLICT
        | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    assert kernel.integrity == expected
    correction = _correct(
        "correction",
        "root",
        "fill",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
    )

    after, transition = kernel.apply(correction)

    assert transition.disposition is TransitionDisposition.APPLIED
    assert after.integrity == expected


@pytest.mark.parametrize(
    "revision_factory",
    [
        lambda: _correct(
            "revision",
            "human-root",
            "human-fill",
            side=ExecutionSide.BUY,
            quantity=1,
            units=101,
        ),
        lambda: _bust(
            "revision",
            "human-root",
            "human-fill",
            side=ExecutionSide.BUY,
        ),
    ],
    ids=["correct", "bust"],
)
def test_each_revision_kind_rejects_human_authority(
    revision_factory: Callable[[], BrokerFact],
) -> None:
    _assert_reconciliation_no_economics(
        _coherently_bound_human_kernel(),
        revision_factory(),
    )


def test_aligned_priced_bust_then_different_scale_fill_stays_pending() -> None:
    """Zero-quantity bust metadata still binds slow/fast compatibility."""

    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    bust = _bust(
        "bust",
        "root",
        "fill",
        side=ExecutionSide.BUY,
        reported_price=_price(100),
    )
    cent_scale = PriceScale(Decimal("0.01"))
    cent_price = _price(
        10_000,
        scale=cent_scale,
        tick=TickMetadata(tick_units=PriceUnits(1), scale=cent_scale),
    )
    replacement_root = _fill(
        "replacement-fill",
        "replacement-root",
        side=ExecutionSide.BUY,
        quantity=3,
        units=10_000,
        price=cent_price,
    )
    before, _ = _apply_all(fill, bust)

    after, transition = before.apply(replacement_root)
    candidate = derive_ordered_basis_candidate(after.position, after.root_heads)

    assert transition.disposition is TransitionDisposition.APPLIED
    assert transition.quantity_delta == 3
    assert transition.basis_delta is None
    assert transition.original_classification is (
        FirstObservationClassification.APPLIED_BASIS_PENDING
    )
    assert after.position.raw_quantity == 3
    assert after.position.basis_authority is (
        BasisAuthority.BASIS_RECONCILIATION_PENDING
    )
    assert after.position.cost_basis is None
    assert candidate.raw_quantity == after.position.raw_quantity
    assert candidate.status is BasisCandidateStatus.INCOMPATIBLE_PRICE_METADATA
    assert candidate.cost_basis is None


@pytest.mark.parametrize("scope_dimension", ["broker", "environment", "account"])
def test_same_symbol_root_fill_from_different_position_scope_reconciles(
    scope_dimension: str,
) -> None:
    first = _fill("first", "root-1", side=ExecutionSide.BUY, quantity=2, units=100)
    before, _ = _apply_all(first)
    broker = BROKER
    environment = ENVIRONMENT
    account = ACCOUNT
    if scope_dimension == "broker":
        broker = BrokerId("other-broker")
    elif scope_dimension == "environment":
        environment = EnvironmentId("other-environment")
    else:
        account = AccountId("other-account")
    mixed_scope = _scope(
        order_id=OrderId(f"mixed-{scope_dimension}-order"),
        side=ExecutionSide.BUY,
        broker=broker,
        environment=environment,
        account=account,
    )
    mixed = _fill(
        f"mixed-{scope_dimension}",
        "root-2",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
        scope=mixed_scope,
        key=_key(
            f"mixed-{scope_dimension}",
            broker=broker,
            environment=environment,
            account=account,
        ),
    )

    _assert_reconciliation_no_economics(before, mixed)


def test_revision_requires_current_predecessor_in_seen_fact_index() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=5, units=100)
    applied, _ = _apply_all(fill)
    missing_predecessor = replace(applied, seen_facts=SeenFactIndex.empty())
    correction = _correct(
        "correct",
        "root",
        "fill",
        side=ExecutionSide.BUY,
        quantity=4,
        units=101,
    )

    _assert_reconciliation_no_economics(missing_predecessor, correction)


@pytest.mark.parametrize(
    "mismatch",
    [
        "missing-root-head",
        "missing-position-root",
        "mismatched-head-id",
        "flat-with-applied-seen-fact",
    ],
)
def test_fast_apply_rejects_exact_snapshot_component_mismatch(mismatch: str) -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    applied, _ = _apply_all(fill)
    if mismatch == "missing-root-head":
        corrupt = replace(applied, root_heads=RootHeadIndex.empty())
    elif mismatch == "missing-position-root":
        corrupt = replace(applied, position=PositionState.flat(POSITION_SCOPE))
    elif mismatch == "mismatched-head-id":
        corrupt = replace(
            applied,
            position=PositionState.from_materialized(
                scope=applied.position.scope,
                raw_quantity=applied.position.raw_quantity,
                basis_authority=applied.position.basis_authority,
                cost_basis=applied.position.cost_basis,
                root_fill_sequence=applied.position.root_fill_sequence,
                effective_head_ids=(SourceEventId("stale-head"),),
                basis_price_metadata=applied.position.basis_price_metadata,
                tail_fold_input=applied.position.tail_fold_input,
            ),
        )
    else:
        corrupt = replace(
            applied,
            position=PositionState.flat(POSITION_SCOPE),
            root_heads=RootHeadIndex.empty(),
        )
    incoming = _fill(
        f"incoming-{mismatch}",
        f"incoming-root-{mismatch}",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
    )

    _assert_reconciliation_no_economics(corrupt, incoming)


def test_incoherent_snapshot_preserves_position_integrity_floor() -> None:
    overfill = _fill(
        "overfill",
        "sell-root",
        side=ExecutionSide.SELL,
        quantity=3,
        units=100,
    )
    quarantined, _ = _apply_all(overfill)
    assert quarantined.position.integrity_floor & (
        PositionIntegrity.OVERFILL_QUARANTINE
    )
    mixed = replace(
        quarantined,
        position=replace(quarantined.position, _binding=None),
        integrity=PositionIntegrity.CONSISTENT,
        root_heads=RootHeadIndex.empty(POSITION_SCOPE),
        seen_facts=SeenFactIndex.empty(),
    )
    incoming = _fill(
        "incoming",
        "incoming-root",
        side=ExecutionSide.BUY,
        quantity=5,
        units=101,
    )

    after, transition = mixed.apply(incoming)

    _assert_zero_economic_delta(mixed, transition)
    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert after.integrity & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    assert after.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert after.position.integrity_floor & (
        PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    assert after.position.integrity_floor & PositionIntegrity.OVERFILL_QUARANTINE


@pytest.mark.parametrize("binding_source", ["position", "root_heads", "seen_facts"])
def test_incoherent_snapshot_recovers_integrity_from_each_component_binding(
    binding_source: str,
) -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=3, units=100)
    applied, _ = _apply_all(fill)
    conflicted, conflict = applied.apply(replace(fill, price=_price(101)))
    assert conflict.disposition is TransitionDisposition.FACT_CONFLICT
    mixed = _Kernel(
        position=replace(
            conflicted.position,
            integrity_floor=PositionIntegrity.CONSISTENT,
            _binding=(
                conflicted.position.binding if binding_source == "position" else None
            ),
        ),
        integrity=PositionIntegrity.CONSISTENT,
        root_heads=(
            conflicted.root_heads
            if binding_source == "root_heads"
            else RootHeadIndex(
                entries=conflicted.root_heads.entries,
                position_scope=POSITION_SCOPE,
            )
        ),
        seen_facts=(
            conflicted.seen_facts
            if binding_source == "seen_facts"
            else SeenFactIndex(entries=conflicted.seen_facts.entries)
        ),
    )
    incoming = _fill(
        "incoming",
        "incoming-root",
        side=ExecutionSide.BUY,
        quantity=5,
        units=101,
    )

    after, transition = mixed.apply(incoming)

    _assert_zero_economic_delta(mixed, transition)
    assert after.integrity & PositionIntegrity.EXECUTION_FACT_CONFLICT
    assert after.position.integrity_floor & PositionIntegrity.EXECUTION_FACT_CONFLICT


@pytest.mark.parametrize("negative_component", ["position", "root_heads"])
def test_incoherent_negative_component_conservatively_latches_overfill(
    negative_component: str,
) -> None:
    overfill = _fill(
        "overfill",
        "sell-root",
        side=ExecutionSide.SELL,
        quantity=3,
        units=100,
    )
    quarantined, _ = _apply_all(overfill)
    position = PositionState.from_materialized(
        scope=POSITION_SCOPE,
        raw_quantity=-3 if negative_component == "position" else 0,
        basis_authority=BasisAuthority.AVAILABLE,
        cost_basis=_basis(0),
        root_fill_sequence=(),
        effective_head_ids=(),
        basis_price_metadata=None,
        tail_fold_input=None,
        integrity_floor=PositionIntegrity.CONSISTENT,
    )
    root_heads = (
        RootHeadIndex.empty(POSITION_SCOPE)
        if negative_component == "position"
        else RootHeadIndex(
            entries=quarantined.root_heads.entries,
            position_scope=POSITION_SCOPE,
        )
    )
    incoming = _fill(
        f"incoming-{negative_component}",
        f"incoming-root-{negative_component}",
        side=ExecutionSide.BUY,
        quantity=5,
        units=101,
    )

    transition = apply_broker_execution_fact(
        position,
        PositionIntegrity.CONSISTENT,
        root_heads,
        SeenFactIndex.empty(),
        incoming,
    )

    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert transition.position.raw_quantity == position.raw_quantity
    assert transition.quantity_delta == 0
    assert transition.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert transition.position.integrity_floor & (PositionIntegrity.OVERFILL_QUARANTINE)


def test_incoherent_snapshot_recovers_overfill_from_unbound_seen_history() -> None:
    overfill = _fill(
        "overfill",
        "sell-root",
        side=ExecutionSide.SELL,
        quantity=3,
        units=100,
    )
    cover = _fill(
        "cover",
        "buy-root",
        side=ExecutionSide.BUY,
        quantity=5,
        units=101,
    )
    recovered, _ = _apply_all(overfill, cover)
    assert recovered.position.raw_quantity == 2
    mixed = _Kernel(
        position=replace(
            recovered.position,
            integrity_floor=PositionIntegrity.CONSISTENT,
            _binding=None,
        ),
        integrity=PositionIntegrity.CONSISTENT,
        root_heads=RootHeadIndex(
            entries=recovered.root_heads.entries,
            position_scope=POSITION_SCOPE,
        ),
        seen_facts=SeenFactIndex(entries=recovered.seen_facts.entries),
    )
    incoming = _fill(
        "incoming-seen-history",
        "incoming-seen-root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=102,
    )

    after, transition = mixed.apply(incoming)

    _assert_zero_economic_delta(mixed, transition)
    assert after.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert after.position.integrity_floor & PositionIntegrity.OVERFILL_QUARANTINE


def test_incoherent_snapshot_recovers_pending_overfill_from_seen_history() -> None:
    buy = _fill("buy", "buy-root", side=ExecutionSide.BUY, quantity=10, units=100)
    sell = _fill("sell", "sell-root", side=ExecutionSide.SELL, quantity=8, units=90)
    bust = _bust("bust", "buy-root", "buy", side=ExecutionSide.BUY)
    cover = _fill("cover", "cover-root", side=ExecutionSide.BUY, quantity=10, units=125)
    recovered, transitions = _apply_all(buy, sell, bust, cover)
    assert transitions[-2].original_classification is (
        FirstObservationClassification.APPLIED_PENDING_OVERFILL
    )
    unbound_seen = SeenFactIndex(entries=recovered.seen_facts.entries)
    assert unbound_seen.has_overfill_observation(POSITION_SCOPE)
    mixed = _Kernel(
        position=replace(
            recovered.position,
            integrity_floor=PositionIntegrity.CONSISTENT,
            _binding=None,
        ),
        integrity=PositionIntegrity.CONSISTENT,
        root_heads=RootHeadIndex(
            entries=recovered.root_heads.entries,
            position_scope=POSITION_SCOPE,
        ),
        seen_facts=unbound_seen,
    )
    incoming = _fill(
        "incoming-pending-overfill",
        "incoming-pending-overfill-root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=126,
    )

    after, transition = mixed.apply(incoming)

    _assert_zero_economic_delta(mixed, transition)
    assert after.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert after.position.integrity_floor & PositionIntegrity.OVERFILL_QUARANTINE


def test_incoherent_account_history_does_not_leak_overfill_between_symbols() -> None:
    overfill = _fill(
        "aapl-overfill",
        "aapl-sell-root",
        side=ExecutionSide.SELL,
        quantity=3,
        units=100,
    )
    quarantined, _ = _apply_all(overfill)
    account_seen = SeenFactIndex(
        entries=quarantined.seen_facts.entries,
        position_scope=OTHER_POSITION_SCOPE,
    )
    assert account_seen.has_overfill_observation(POSITION_SCOPE)
    assert not account_seen.has_overfill_observation(OTHER_POSITION_SCOPE)
    mixed = _Kernel(
        position=PositionState.flat(OTHER_POSITION_SCOPE),
        integrity=PositionIntegrity.CONSISTENT,
        root_heads=RootHeadIndex.empty(OTHER_POSITION_SCOPE),
        seen_facts=account_seen,
    )
    incoming = _fill(
        "msft-incoming",
        "msft-incoming-root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
        scope=_scope(
            order_id=OrderId("msft-buy-order"),
            side=ExecutionSide.BUY,
            symbol_id=OTHER_SYMBOL,
        ),
    )

    after, transition = mixed.apply(incoming)

    _assert_zero_economic_delta(mixed, transition)
    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert not after.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert not after.position.integrity_floor & (PositionIntegrity.OVERFILL_QUARANTINE)


@pytest.mark.parametrize(
    "foreign_scope",
    [
        OTHER_POSITION_SCOPE,
        replace(POSITION_SCOPE, account=AccountId("foreign-root-account")),
    ],
    ids=["other-symbol", "foreign-account"],
)
def test_incoherent_foreign_root_index_does_not_leak_overfill(
    foreign_scope: PositionScope,
) -> None:
    foreign_fact = _fill(
        "foreign-root-overfill",
        "foreign-root-overfill",
        side=ExecutionSide.SELL,
        quantity=2,
        units=100,
        scope=_scope(
            order_id=OrderId("foreign-root-order"),
            side=ExecutionSide.SELL,
            account=foreign_scope.account,
            symbol_id=foreign_scope.symbol_id,
        ),
        key=_key("foreign-root-overfill", account=foreign_scope.account),
    )
    foreign, _ = _Kernel.flat(foreign_scope).apply(foreign_fact)
    assert foreign.root_heads.signed_quantity == -2
    assert foreign.root_heads.binding is not None
    incoming = _fill(
        "local-after-foreign-root",
        "local-after-foreign-root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
    )

    transition = apply_broker_execution_fact(
        PositionState.flat(POSITION_SCOPE),
        PositionIntegrity.CONSISTENT,
        foreign.root_heads,
        SeenFactIndex.empty(POSITION_SCOPE),
        incoming,
    )

    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert transition.quantity_delta == 0
    assert not transition.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert not transition.position.integrity_floor & (
        PositionIntegrity.OVERFILL_QUARANTINE
    )


def test_incoherent_other_symbol_seen_binding_does_not_leak_overfill() -> None:
    other_overfill = _fill(
        "other-symbol-overfill",
        "other-symbol-overfill-root",
        side=ExecutionSide.SELL,
        quantity=2,
        units=100,
        scope=_scope(
            order_id=OrderId("other-symbol-sell"),
            side=ExecutionSide.SELL,
            symbol_id=OTHER_SYMBOL,
        ),
    )
    other, _ = _Kernel.flat(OTHER_POSITION_SCOPE).apply(other_overfill)
    assert other.seen_facts.binding is not None
    assert other.seen_facts.binding.position_scope == OTHER_POSITION_SCOPE
    assert not other.seen_facts.has_overfill_observation(POSITION_SCOPE)
    incoming = _fill(
        "local-after-other-seen",
        "local-after-other-seen-root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
    )

    transition = apply_broker_execution_fact(
        PositionState.flat(POSITION_SCOPE),
        PositionIntegrity.CONSISTENT,
        RootHeadIndex.empty(POSITION_SCOPE),
        other.seen_facts,
        incoming,
    )

    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert transition.quantity_delta == 0
    assert not transition.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert not transition.position.integrity_floor & (
        PositionIntegrity.OVERFILL_QUARANTINE
    )


@pytest.mark.parametrize("binding_source", ["position", "root_heads"])
def test_incoherent_component_binding_scope_mismatch_does_not_leak_overfill(
    binding_source: str,
) -> None:
    other_overfill = _fill(
        "other-binding-overfill",
        "other-binding-overfill-root",
        side=ExecutionSide.SELL,
        quantity=2,
        units=100,
        scope=_scope(
            order_id=OrderId("other-binding-sell"),
            side=ExecutionSide.SELL,
            symbol_id=OTHER_SYMBOL,
        ),
    )
    other, _ = _Kernel.flat(OTHER_POSITION_SCOPE).apply(other_overfill)
    foreign_binding = other.position.binding
    assert foreign_binding is not None
    assert foreign_binding.position_scope == OTHER_POSITION_SCOPE
    position = PositionState.flat(POSITION_SCOPE)
    root_heads = RootHeadIndex.empty(POSITION_SCOPE)
    if binding_source == "position":
        position = position._with_binding(foreign_binding)
    else:
        root_heads = root_heads._with_binding(foreign_binding)
    incoming = _fill(
        f"local-after-{binding_source}-binding",
        f"local-after-{binding_source}-binding-root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
    )

    transition = apply_broker_execution_fact(
        position,
        PositionIntegrity.CONSISTENT,
        root_heads,
        SeenFactIndex.empty(POSITION_SCOPE),
        incoming,
    )

    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert transition.quantity_delta == 0
    assert not transition.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert not transition.position.integrity_floor & (
        PositionIntegrity.OVERFILL_QUARANTINE
    )


def test_incoherent_foreign_account_registry_reconciles_without_exception() -> None:
    foreign_scope = replace(
        POSITION_SCOPE,
        account=AccountId("foreign-account"),
    )
    foreign_fact = _fill(
        "foreign-fill",
        "foreign-root",
        side=ExecutionSide.SELL,
        quantity=2,
        units=100,
        scope=_scope(
            order_id=OrderId("foreign-order"),
            side=ExecutionSide.SELL,
            account=foreign_scope.account,
        ),
        key=_key("foreign-fill", account=foreign_scope.account),
    )
    foreign, _ = _Kernel.flat(foreign_scope).apply(foreign_fact)
    assert foreign.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    mixed = _Kernel(
        position=PositionState.flat(POSITION_SCOPE),
        integrity=PositionIntegrity.CONSISTENT,
        root_heads=RootHeadIndex.empty(POSITION_SCOPE),
        seen_facts=foreign.seen_facts,
    )
    incoming = _fill(
        "local-incoming",
        "local-root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
    )

    after, transition = mixed.apply(incoming)

    _assert_zero_economic_delta(mixed, transition)
    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert after.seen_facts is foreign.seen_facts
    assert after.integrity == PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED


def test_incoherent_changed_replay_latches_fact_conflict() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    applied, _ = _apply_all(fill)
    corrupt = replace(
        applied,
        root_heads=RootHeadIndex.empty(POSITION_SCOPE),
    )
    changed_replay = replace(fill, price=_price(101))

    after, transition = corrupt.apply(changed_replay)

    _assert_zero_economic_delta(corrupt, transition)
    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert transition.original_classification is (
        FirstObservationClassification.APPLIED_AVAILABLE
    )
    assert after.integrity & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    assert after.integrity & PositionIntegrity.EXECUTION_FACT_CONFLICT
    assert after.position.integrity_floor & (
        PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    assert after.position.integrity_floor & PositionIntegrity.EXECUTION_FACT_CONFLICT

    deliberately_cleared = replace(
        after,
        integrity=PositionIntegrity.CONSISTENT,
    )
    next_fact = _fill(
        "next",
        "next-root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=102,
    )
    recovered, next_transition = deliberately_cleared.apply(next_fact)

    _assert_zero_economic_delta(deliberately_cleared, next_transition)
    assert recovered.integrity & PositionIntegrity.EXECUTION_FACT_CONFLICT
    assert recovered.integrity & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED


def test_incoherent_exact_replay_does_not_invent_fact_conflict() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    applied, _ = _apply_all(fill)
    corrupt = replace(
        applied,
        root_heads=RootHeadIndex.empty(POSITION_SCOPE),
    )

    after, transition = corrupt.apply(fill)

    _assert_zero_economic_delta(corrupt, transition)
    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert after.integrity & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    assert not after.integrity & PositionIntegrity.EXECUTION_FACT_CONFLICT


def test_exact_replay_rejects_flat_snapshot_with_applied_seen_fact() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    applied, _ = _apply_all(fill)
    corrupt = replace(
        applied,
        position=PositionState.flat(POSITION_SCOPE),
        root_heads=RootHeadIndex.empty(),
    )

    after, transition = corrupt.apply(fill)

    _assert_zero_economic_delta(corrupt, transition)
    assert after.seen_facts == corrupt.seen_facts
    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert transition.original_classification is (
        FirstObservationClassification.APPLIED_AVAILABLE
    )
    assert after.integrity & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED


def test_integrity_reset_mismatch_reconciles_without_economics() -> None:
    overfill = _fill(
        "overfill",
        "sell-root",
        side=ExecutionSide.SELL,
        quantity=3,
        units=100,
    )
    quarantined, _ = _apply_all(overfill)
    assert quarantined.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    reset = replace(quarantined, integrity=PositionIntegrity.CONSISTENT)
    cover = _fill(
        "cover",
        "cover-root",
        side=ExecutionSide.BUY,
        quantity=5,
        units=101,
    )

    after = _assert_reconciliation_no_economics(reset, cover)
    assert after.integrity & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED


def test_bind_verified_rejects_applied_seen_fact_without_root_economics() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    orphan_seen = SeenFactIndex(
        entries=(
            SeenFact(
                fact=fill,
                classification=FirstObservationClassification.APPLIED_AVAILABLE,
            ),
        )
    )

    with pytest.raises(ValueError):
        ExecutionSnapshot.bind_verified(
            PositionState.flat(POSITION_SCOPE),
            PositionIntegrity.CONSISTENT,
            RootHeadIndex.empty(POSITION_SCOPE),
            orphan_seen,
        )


def test_bind_verified_rejects_extra_applied_seen_fact_outside_current_roots() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    applied, _ = _apply_all(fill)
    orphan = _fill(
        "orphan",
        "orphan-root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
    )
    position, roots, seen = _unbound_hydration_parts(applied)
    forged_seen = SeenFactIndex(
        entries=seen.entries
        + (
            SeenFact(
                fact=orphan,
                classification=FirstObservationClassification.APPLIED_AVAILABLE,
            ),
        )
    )

    with pytest.raises(ValueError):
        ExecutionSnapshot.bind_verified(
            position,
            applied.integrity,
            roots,
            forged_seen,
        )


@pytest.mark.parametrize("ancestor_state", ["missing", "reconciliation"])
def test_bind_verified_rejects_current_revision_without_applied_ancestor_chain(
    ancestor_state: str,
) -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=3, units=100)
    correction = _correct(
        "correction",
        "root",
        "fill",
        side=ExecutionSide.BUY,
        quantity=2,
        units=101,
    )
    applied, _ = _apply_all(fill, correction)
    position, roots, seen = _unbound_hydration_parts(applied)
    fill_observation, correction_observation = seen.entries
    observations = (correction_observation,)
    if ancestor_state == "reconciliation":
        observations = (
            replace(
                fill_observation,
                classification=FirstObservationClassification.RECONCILIATION_REQUIRED,
            ),
            correction_observation,
        )

    with pytest.raises(ValueError):
        ExecutionSnapshot.bind_verified(
            position,
            applied.integrity,
            roots,
            SeenFactIndex(entries=observations),
        )


def test_bind_verified_rejects_overfill_fact_reclassified_available() -> None:
    overfill = _fill(
        "overfill",
        "sell-root",
        side=ExecutionSide.SELL,
        quantity=3,
        units=100,
    )
    applied, _ = _apply_all(overfill)
    position, roots, seen = _unbound_hydration_parts(applied)
    observation = seen.entries[0]
    forged_seen = SeenFactIndex(
        entries=(
            replace(
                observation,
                classification=FirstObservationClassification.APPLIED_AVAILABLE,
            ),
        )
    )

    with pytest.raises(ValueError):
        ExecutionSnapshot.bind_verified(
            position,
            applied.integrity,
            roots,
            forged_seen,
        )


def test_bind_verified_rejects_available_fact_reclassified_basis_pending() -> None:
    fill = _fill(
        "available",
        "available-root",
        side=ExecutionSide.BUY,
        quantity=3,
        units=100,
    )
    applied, _ = _apply_all(fill)
    position, roots, seen = _unbound_hydration_parts(applied)
    observation = seen.entries[0]
    forged_seen = SeenFactIndex(
        entries=(
            replace(
                observation,
                classification=FirstObservationClassification.APPLIED_BASIS_PENDING,
            ),
        )
    )

    with pytest.raises(ValueError, match="classification is not reproducible"):
        ExecutionSnapshot.bind_verified(
            position,
            applied.integrity,
            roots,
            forged_seen,
        )


def test_bind_verified_rejects_historical_overfill_integrity_reset() -> None:
    sell = _fill(
        "sell",
        "sell-root",
        side=ExecutionSide.SELL,
        quantity=3,
        units=100,
    )
    cover = _fill(
        "cover",
        "cover-root",
        side=ExecutionSide.BUY,
        quantity=5,
        units=101,
    )
    recovered, _ = _apply_all(sell, cover)
    assert recovered.position.raw_quantity == 2
    assert recovered.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    _, roots, seen = _unbound_hydration_parts(recovered)
    position = PositionState.from_materialized(
        scope=recovered.position.scope,
        raw_quantity=recovered.position.raw_quantity,
        basis_authority=recovered.position.basis_authority,
        cost_basis=recovered.position.cost_basis,
        root_fill_sequence=recovered.position.root_fill_sequence,
        effective_head_ids=recovered.position.effective_head_ids,
        basis_price_metadata=recovered.position.basis_price_metadata,
        tail_fold_input=recovered.position.tail_fold_input,
    )

    with pytest.raises(ValueError):
        ExecutionSnapshot.bind_verified(
            position,
            PositionIntegrity.CONSISTENT,
            roots,
            seen,
        )


def test_bind_verified_rejects_committed_conflict_integrity_reset() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    applied, _ = _apply_all(fill)
    changed_replay = replace(fill, price=_price(101))
    conflicted, transition = applied.apply(changed_replay)
    assert transition.disposition is TransitionDisposition.FACT_CONFLICT
    assert conflicted.integrity & PositionIntegrity.EXECUTION_FACT_CONFLICT
    position, roots, seen = _unbound_hydration_parts(conflicted)

    with pytest.raises(ValueError):
        ExecutionSnapshot.bind_verified(
            position,
            PositionIntegrity.CONSISTENT,
            roots,
            seen,
        )


def test_position_commitment_carries_unreconstructable_integrity_floor() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    applied, _ = _apply_all(fill)
    changed_replay = replace(fill, price=_price(101))
    conflicted, transition = applied.apply(changed_replay)
    assert transition.disposition is TransitionDisposition.FACT_CONFLICT

    assert conflicted.position.commitment != applied.position.commitment


def test_position_value_identity_carries_integrity_floor() -> None:
    clean = PositionState.flat(POSITION_SCOPE)
    quarantined = replace(
        clean,
        integrity_floor=PositionIntegrity.OVERFILL_QUARANTINE,
    )

    assert clean != quarantined
    assert clean.commitment != quarantined.commitment


def test_empty_root_index_value_identity_carries_exact_scope() -> None:
    scoped = RootHeadIndex.empty(POSITION_SCOPE)
    other_scoped = RootHeadIndex.empty(OTHER_POSITION_SCOPE)
    unscoped = RootHeadIndex.empty()

    assert scoped != other_scoped
    assert scoped != unscoped
    assert scoped.commitment != other_scoped.commitment
    assert scoped.commitment != unscoped.commitment


def test_root_index_value_identity_carries_signed_quantity() -> None:
    fill = _fill(
        "root-value",
        "root-value",
        side=ExecutionSide.BUY,
        quantity=2,
        units=100,
    )
    applied, _ = _apply_all(fill)
    authentic = applied.root_heads
    forged = RootHeadIndex._from_parts(
        by_root=authentic._by_root,
        root_sequence=authentic._root_sequence,
        head_sequence=authentic._head_sequence,
        position_scope=authentic.position_scope,
        signed_quantity=authentic.signed_quantity + 1,
    )

    assert authentic.entries == forged.entries
    assert authentic != forged
    assert authentic.commitment != forged.commitment


def test_bind_verified_rejects_reconciliation_integrity_reset() -> None:
    invalid = _correct(
        "orphan-correction",
        "missing-root",
        "missing-predecessor",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
    )
    reconciled, transition = _Kernel.flat().apply(invalid)
    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    _, roots, seen = _unbound_hydration_parts(reconciled)

    with pytest.raises(ValueError):
        ExecutionSnapshot.bind_verified(
            PositionState.flat(POSITION_SCOPE),
            PositionIntegrity.CONSISTENT,
            roots,
            seen,
        )


def test_bind_verified_rejects_forged_tail_prefix_economics() -> None:
    first = _fill("first", "first-root", side=ExecutionSide.BUY, quantity=10, units=100)
    tail = _fill("tail", "tail-root", side=ExecutionSide.BUY, quantity=10, units=100)
    applied, _ = _apply_all(first, tail)
    authentic_tail_input = applied.position.tail_fold_input
    authentic_tail_head = applied.root_heads.get(tail.root_key)
    first_head = applied.root_heads.get(first.root_key)
    assert authentic_tail_input is not None
    assert authentic_tail_head is not None
    assert first_head is not None
    forged_tail_input = replace(authentic_tail_input, cost_basis=_basis(5_000))
    forged_tail_head = replace(
        authentic_tail_head,
        prefix_proof_commitment=forged_tail_input.commitment,
    )
    forged_roots = RootHeadIndex(
        entries=(first_head, forged_tail_head),
        position_scope=POSITION_SCOPE,
    )
    forged_position = PositionState.from_materialized(
        scope=POSITION_SCOPE,
        raw_quantity=applied.position.raw_quantity,
        basis_authority=applied.position.basis_authority,
        cost_basis=applied.position.cost_basis,
        root_fill_sequence=applied.position.root_fill_sequence,
        effective_head_ids=applied.position.effective_head_ids,
        basis_price_metadata=applied.position.basis_price_metadata,
        tail_fold_input=forged_tail_input,
    )

    with pytest.raises(ValueError):
        ExecutionSnapshot.bind_verified(
            forged_position,
            applied.integrity,
            forged_roots,
            applied.seen_facts,
        )


def test_bind_verified_rejects_forged_tail_prefix_sequence_commitment() -> None:
    first = _fill("first", "first-root", side=ExecutionSide.BUY, quantity=10, units=100)
    tail = _fill("tail", "tail-root", side=ExecutionSide.BUY, quantity=10, units=100)
    applied, _ = _apply_all(first, tail)
    authentic_tail_input = applied.position.tail_fold_input
    authentic_tail_head = applied.root_heads.get(tail.root_key)
    first_head = applied.root_heads.get(first.root_key)
    assert authentic_tail_input is not None
    assert authentic_tail_head is not None
    assert first_head is not None
    forged_tail_input = replace(
        authentic_tail_input,
        prefix_heads_commitment=b"forged-prefix-commitment",
    )
    forged_tail_head = replace(
        authentic_tail_head,
        prefix_heads_commitment=forged_tail_input.prefix_heads_commitment,
        prefix_proof_commitment=forged_tail_input.commitment,
    )
    forged_roots = RootHeadIndex(
        entries=(first_head, forged_tail_head),
        position_scope=POSITION_SCOPE,
    )
    forged_position = PositionState.from_materialized(
        scope=POSITION_SCOPE,
        raw_quantity=applied.position.raw_quantity,
        basis_authority=applied.position.basis_authority,
        cost_basis=applied.position.cost_basis,
        root_fill_sequence=applied.position.root_fill_sequence,
        effective_head_ids=applied.position.effective_head_ids,
        basis_price_metadata=applied.position.basis_price_metadata,
        tail_fold_input=forged_tail_input,
    )

    with pytest.raises(ValueError):
        ExecutionSnapshot.bind_verified(
            forged_position,
            applied.integrity,
            forged_roots,
            SeenFactIndex(entries=applied.seen_facts.entries),
        )


def test_bind_verified_rejects_root_head_semantics_not_in_seen_replay() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    applied, _ = _apply_all(fill)
    position, _, seen = _unbound_hydration_parts(applied)
    head = applied.root_heads.get(fill.root_key)
    assert head is not None
    forged_head = replace(head, price=_price(101))

    with pytest.raises(ValueError, match="root heads do not match"):
        ExecutionSnapshot.bind_verified(
            position,
            applied.integrity,
            RootHeadIndex(entries=(forged_head,), position_scope=POSITION_SCOPE),
            seen,
        )


@pytest.mark.parametrize(
    "proof_field",
    ["prefix_heads_commitment", "prefix_proof_commitment"],
)
def test_bind_verified_rejects_tail_head_proof_not_in_seen_replay(
    proof_field: str,
) -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    applied, _ = _apply_all(fill)
    position, _, seen = _unbound_hydration_parts(applied)
    head = applied.root_heads.get(fill.root_key)
    assert head is not None
    forged_head = replace(head, **{proof_field: b"forged-tail-proof"})

    with pytest.raises(ValueError, match="exact replayed proof"):
        ExecutionSnapshot.bind_verified(
            position,
            applied.integrity,
            RootHeadIndex(entries=(forged_head,), position_scope=POSITION_SCOPE),
            seen,
        )


def test_bind_verified_rejects_retained_head_proof_without_position_proof() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    applied, _ = _apply_all(fill)
    authentic_head = applied.root_heads.get(fill.root_key)
    assert authentic_head is not None
    assert authentic_head.prefix_heads_commitment
    assert authentic_head.prefix_proof_commitment
    proofless_position = PositionState.from_materialized(
        scope=POSITION_SCOPE,
        raw_quantity=applied.position.raw_quantity,
        basis_authority=applied.position.basis_authority,
        cost_basis=applied.position.cost_basis,
        root_fill_sequence=applied.position.root_fill_sequence,
        effective_head_ids=applied.position.effective_head_ids,
        basis_price_metadata=applied.position.basis_price_metadata,
        tail_fold_input=None,
    )

    with pytest.raises(ValueError, match="tail proof must be fully absent"):
        ExecutionSnapshot.bind_verified(
            proofless_position,
            applied.integrity,
            RootHeadIndex(
                entries=applied.root_heads.entries,
                position_scope=POSITION_SCOPE,
            ),
            SeenFactIndex(entries=applied.seen_facts.entries),
        )


def test_bind_verified_rejects_inexact_basis_price_metadata() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    applied, _ = _apply_all(fill)
    compatible_but_inexact_metadata = _price(101)
    forged_position = PositionState.from_materialized(
        scope=POSITION_SCOPE,
        raw_quantity=applied.position.raw_quantity,
        basis_authority=applied.position.basis_authority,
        cost_basis=applied.position.cost_basis,
        root_fill_sequence=applied.position.root_fill_sequence,
        effective_head_ids=applied.position.effective_head_ids,
        basis_price_metadata=compatible_but_inexact_metadata,
        tail_fold_input=applied.position.tail_fold_input,
    )

    with pytest.raises(ValueError):
        ExecutionSnapshot.bind_verified(
            forged_position,
            applied.integrity,
            applied.root_heads,
            applied.seen_facts,
        )


def test_bind_verified_rejects_erased_priced_bust_metadata() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    bust = _bust(
        "bust",
        "root",
        "fill",
        side=ExecutionSide.BUY,
        reported_price=_price(100),
    )
    busted, _ = _apply_all(fill, bust)
    forged_position = PositionState.from_materialized(
        scope=POSITION_SCOPE,
        raw_quantity=busted.position.raw_quantity,
        basis_authority=busted.position.basis_authority,
        cost_basis=busted.position.cost_basis,
        root_fill_sequence=busted.position.root_fill_sequence,
        effective_head_ids=busted.position.effective_head_ids,
        basis_price_metadata=None,
        tail_fold_input=busted.position.tail_fold_input,
    )

    with pytest.raises(ValueError):
        ExecutionSnapshot.bind_verified(
            forged_position,
            busted.integrity,
            RootHeadIndex(
                entries=busted.root_heads.entries,
                position_scope=POSITION_SCOPE,
            ),
            SeenFactIndex(entries=busted.seen_facts.entries),
        )


def test_bind_verified_accepts_priced_bust_and_preserves_compatibility() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    bust = _bust(
        "bust",
        "root",
        "fill",
        side=ExecutionSide.BUY,
        reported_price=_price(100),
    )
    busted, _ = _apply_all(fill, bust)
    position, roots, seen = _unbound_hydration_parts(busted)

    hydrated = ExecutionSnapshot.bind_verified(
        position,
        busted.integrity,
        roots,
        seen,
    )
    priced_bust_head = hydrated.root_heads.get(fill.root_key)
    assert priced_bust_head is not None
    assert priced_bust_head.kind is FactKind.TRADE_BUST
    assert priced_bust_head.price == _price(100)
    assert hydrated.position.basis_price_metadata == _price(100)
    followup = _fill(
        "followup",
        "followup-root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
    )

    transition = apply_broker_execution_fact(
        hydrated.position,
        hydrated.integrity,
        hydrated.root_heads,
        hydrated.seen_facts,
        followup,
    )

    assert transition.disposition is TransitionDisposition.APPLIED
    assert transition.original_classification is (
        FirstObservationClassification.APPLIED_AVAILABLE
    )
    assert transition.position.basis_authority is BasisAuthority.AVAILABLE
    assert transition.position.cost_basis == _basis(101)
    assert transition.position.basis_price_metadata == _price(100)


def test_position_commitment_covers_exact_tail_fold_input() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    applied, _ = _apply_all(fill)
    authentic = applied.position.tail_fold_input
    assert authentic is not None
    forged = replace(authentic, price_metadata=_price(99))

    assert replace(applied.position, tail_fold_input=forged).commitment != (
        applied.position.commitment
    )
    assert replace(applied.position, tail_fold_input=None).commitment != (
        applied.position.commitment
    )


def test_bind_verified_rejects_human_attested_root() -> None:
    human = _coherently_bound_human_kernel()
    position, roots, seen = _unbound_hydration_parts(human)

    with pytest.raises(ValueError):
        ExecutionSnapshot.bind_verified(
            position,
            human.integrity,
            roots,
            seen,
        )


def test_bind_verified_allows_missing_tail_proof_then_revision_becomes_pending() -> (
    None
):
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=10, units=100)
    applied, _ = _apply_all(fill)
    head = applied.root_heads.get(fill.root_key)
    assert head is not None
    proofless_head = replace(
        head,
        prefix_heads_commitment=b"",
        prefix_proof_commitment=b"",
    )
    proofless_position = PositionState.from_materialized(
        scope=POSITION_SCOPE,
        raw_quantity=applied.position.raw_quantity,
        basis_authority=applied.position.basis_authority,
        cost_basis=applied.position.cost_basis,
        root_fill_sequence=applied.position.root_fill_sequence,
        effective_head_ids=applied.position.effective_head_ids,
        basis_price_metadata=applied.position.basis_price_metadata,
        tail_fold_input=None,
    )
    snapshot = ExecutionSnapshot.bind_verified(
        proofless_position,
        applied.integrity,
        RootHeadIndex(entries=(proofless_head,), position_scope=POSITION_SCOPE),
        SeenFactIndex(entries=applied.seen_facts.entries),
    )
    correction = _correct(
        "correction",
        "root",
        "fill",
        side=ExecutionSide.BUY,
        quantity=7,
        units=101,
    )

    transition = apply_broker_execution_fact(
        snapshot.position,
        snapshot.integrity,
        snapshot.root_heads,
        snapshot.seen_facts,
        correction,
    )

    assert transition.disposition is TransitionDisposition.APPLIED
    assert transition.quantity_delta == -3
    assert transition.position.raw_quantity == 7
    assert transition.position.effective_head_ids == (SourceEventId("correction"),)
    assert transition.position.basis_authority is (
        BasisAuthority.BASIS_RECONCILIATION_PENDING
    )
    assert transition.position.cost_basis is None


def test_pending_root_clears_tail_proof_and_hydrates() -> None:
    incompatible = _fill(
        "incompatible",
        "root",
        side=ExecutionSide.BUY,
        quantity=3,
        units=203,
        price=_price(203, tick=TickMetadata(tick_units=PriceUnits(2), scale=SCALE)),
    )
    pending, _ = _apply_all(incompatible)
    head = pending.root_heads.get(incompatible.root_key)
    assert head is not None
    assert pending.position.tail_fold_input is None
    assert head.prefix_heads_commitment == b""
    assert head.prefix_proof_commitment == b""
    position, roots, seen = _unbound_hydration_parts(pending)

    hydrated = ExecutionSnapshot.bind_verified(
        position,
        pending.integrity,
        roots,
        seen,
    )

    assert hydrated.position.basis_authority is (
        BasisAuthority.BASIS_RECONCILIATION_PENDING
    )


def test_pending_tail_revision_clears_active_proof_and_hydrates() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=10, units=100)
    correction = _correct(
        "correction",
        "root",
        "fill",
        side=ExecutionSide.BUY,
        quantity=7,
        units=203,
        price=_price(203, tick=TickMetadata(tick_units=PriceUnits(2), scale=SCALE)),
    )
    pending, _ = _apply_all(fill, correction)
    head = pending.root_heads.get(fill.root_key)
    assert head is not None
    assert pending.position.tail_fold_input is None
    assert head.prefix_heads_commitment == b""
    assert head.prefix_proof_commitment == b""
    position, roots, seen = _unbound_hydration_parts(pending)

    hydrated = ExecutionSnapshot.bind_verified(
        position,
        pending.integrity,
        roots,
        seen,
    )

    assert hydrated.position.raw_quantity == 7
    assert hydrated.position.basis_authority is (
        BasisAuthority.BASIS_RECONCILIATION_PENDING
    )


def test_non_tail_revision_clears_current_tail_proof_and_hydrates() -> None:
    buy = _fill("buy", "buy-root", side=ExecutionSide.BUY, quantity=10, units=100)
    sell = _fill("sell", "sell-root", side=ExecutionSide.SELL, quantity=5, units=120)
    correction = _correct(
        "correction",
        "buy-root",
        "buy",
        side=ExecutionSide.BUY,
        quantity=7,
        units=101,
    )
    before, _ = _apply_all(buy, sell)
    original_non_tail = before.root_heads.get(buy.root_key)
    assert original_non_tail is not None
    pending, transition = before.apply(correction)
    assert transition.disposition is TransitionDisposition.APPLIED
    revised_non_tail = pending.root_heads.get(buy.root_key)
    assert revised_non_tail is not None
    assert (
        revised_non_tail.prefix_heads_commitment
        == original_non_tail.prefix_heads_commitment
    )
    assert (
        revised_non_tail.prefix_proof_commitment
        == original_non_tail.prefix_proof_commitment
    )
    current_tail = pending.root_heads.get(sell.root_key)
    assert current_tail is not None
    assert pending.position.tail_fold_input is None
    assert current_tail.prefix_heads_commitment == b""
    assert current_tail.prefix_proof_commitment == b""
    position, roots, seen = _unbound_hydration_parts(pending)

    hydrated = ExecutionSnapshot.bind_verified(
        position,
        pending.integrity,
        roots,
        seen,
    )

    assert hydrated.position.raw_quantity == 2
    assert hydrated.position.basis_authority is (
        BasisAuthority.BASIS_RECONCILIATION_PENDING
    )


@pytest.mark.parametrize("replacement", [b"forged-proof", b""])
def test_bind_verified_rejects_changed_historical_non_tail_proof(
    replacement: bytes,
) -> None:
    buy = _fill("buy", "buy-root", side=ExecutionSide.BUY, quantity=10, units=100)
    second_buy = _fill(
        "second-buy",
        "second-buy-root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=110,
    )
    sell = _fill("sell", "sell-root", side=ExecutionSide.SELL, quantity=5, units=120)
    correction = _correct(
        "correction",
        "buy-root",
        "buy",
        side=ExecutionSide.BUY,
        quantity=7,
        units=101,
    )
    pending, _ = _apply_all(buy, second_buy, sell, correction)
    position, roots, seen = _unbound_hydration_parts(pending)
    historical, retained_historical, current_tail = roots.entries
    assert historical.prefix_heads_commitment
    assert historical.prefix_proof_commitment
    assert retained_historical.prefix_heads_commitment
    assert retained_historical.prefix_proof_commitment
    assert current_tail.prefix_heads_commitment == b""
    assert current_tail.prefix_proof_commitment == b""
    changed_historical = replace(
        historical,
        prefix_heads_commitment=replacement,
        prefix_proof_commitment=replacement,
    )

    with pytest.raises(ValueError, match="historical root proof"):
        ExecutionSnapshot.bind_verified(
            position,
            pending.integrity,
            RootHeadIndex(
                entries=(changed_historical, retained_historical, current_tail),
                position_scope=POSITION_SCOPE,
            ),
            seen,
        )


def test_bind_verified_accepts_fully_absent_multi_head_proof_cache() -> None:
    first = _fill("first", "first-root", side=ExecutionSide.BUY, quantity=3, units=100)
    middle = _fill(
        "middle",
        "middle-root",
        side=ExecutionSide.BUY,
        quantity=2,
        units=110,
    )
    tail = _fill("tail", "tail-root", side=ExecutionSide.SELL, quantity=1, units=120)
    applied, _ = _apply_all(first, middle, tail)
    proofless_position = PositionState.from_materialized(
        scope=POSITION_SCOPE,
        raw_quantity=applied.position.raw_quantity,
        basis_authority=applied.position.basis_authority,
        cost_basis=applied.position.cost_basis,
        root_fill_sequence=applied.position.root_fill_sequence,
        effective_head_ids=applied.position.effective_head_ids,
        basis_price_metadata=applied.position.basis_price_metadata,
        tail_fold_input=None,
        integrity_floor=applied.position.integrity_floor,
    )
    proofless_roots = RootHeadIndex(
        entries=tuple(
            replace(
                head,
                prefix_heads_commitment=b"",
                prefix_proof_commitment=b"",
            )
            for head in applied.root_heads.entries
        ),
        position_scope=POSITION_SCOPE,
    )

    hydrated = ExecutionSnapshot.bind_verified(
        proofless_position,
        applied.integrity,
        proofless_roots,
        SeenFactIndex(entries=applied.seen_facts.entries),
    )

    assert hydrated.position.basis_authority is BasisAuthority.AVAILABLE
    assert hydrated.position.tail_fold_input is None
    assert all(
        not head.prefix_heads_commitment and not head.prefix_proof_commitment
        for head in hydrated.root_heads.entries
    )
    correction = _correct(
        "correction",
        "first-root",
        "first",
        side=ExecutionSide.BUY,
        quantity=4,
        units=101,
    )
    pending, transition = _Kernel(
        position=hydrated.position,
        integrity=hydrated.integrity,
        root_heads=hydrated.root_heads,
        seen_facts=hydrated.seen_facts,
    ).apply(correction)
    assert transition.disposition is TransitionDisposition.APPLIED
    assert pending.position.basis_authority is (
        BasisAuthority.BASIS_RECONCILIATION_PENDING
    )


def test_account_registry_rejects_cross_symbol_source_event_collision() -> None:
    shared_key = _key("shared-event")
    first_fill = _fill(
        "shared-event",
        "first-root",
        side=ExecutionSide.BUY,
        quantity=2,
        units=100,
        key=shared_key,
    )
    first, _ = _Kernel.flat().apply(first_fill)
    other_snapshot = ExecutionSnapshot.bind_verified(
        PositionState.flat(OTHER_POSITION_SCOPE),
        PositionIntegrity.CONSISTENT,
        RootHeadIndex.empty(OTHER_POSITION_SCOPE),
        first.seen_facts,
    )
    changed_fill = _fill(
        "shared-event",
        "other-root",
        side=ExecutionSide.BUY,
        quantity=3,
        units=101,
        scope=_scope(
            order_id=OrderId("other-buy-order"),
            side=ExecutionSide.BUY,
            symbol_id=OTHER_SYMBOL,
        ),
        key=shared_key,
    )

    other, transition = _Kernel(
        position=other_snapshot.position,
        integrity=other_snapshot.integrity,
        root_heads=other_snapshot.root_heads,
        seen_facts=other_snapshot.seen_facts,
    ).apply(changed_fill)

    assert transition.disposition is TransitionDisposition.FACT_CONFLICT
    assert transition.quantity_delta == 0
    assert other.position.raw_quantity == 0
    assert other.root_heads.count == 0
    assert other.integrity & PositionIntegrity.EXECUTION_FACT_CONFLICT
    assert other.integrity & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    assert other.seen_facts.count == 1
    observation = other.seen_facts.get(first_fill.key)
    assert observation is not None
    assert observation.fact == first_fill
    assert first.position.raw_quantity == 2
    rebound_first = ExecutionSnapshot.bind_verified(
        replace(first.position, _binding=None),
        first.integrity,
        RootHeadIndex(
            entries=first.root_heads.entries,
            position_scope=POSITION_SCOPE,
        ),
        other.seen_facts,
    )
    assert rebound_first.position.raw_quantity == 2
    assert rebound_first.seen_facts.count == 1


def test_account_registry_rejects_cross_symbol_exact_replay_misroute() -> None:
    first_fill = _fill(
        "aapl-event",
        "aapl-root",
        side=ExecutionSide.BUY,
        quantity=2,
        units=100,
    )
    first, _ = _Kernel.flat().apply(first_fill)
    other_snapshot = ExecutionSnapshot.bind_verified(
        PositionState.flat(OTHER_POSITION_SCOPE),
        PositionIntegrity.CONSISTENT,
        RootHeadIndex.empty(OTHER_POSITION_SCOPE),
        first.seen_facts,
    )
    other_before = _Kernel(
        position=other_snapshot.position,
        integrity=other_snapshot.integrity,
        root_heads=other_snapshot.root_heads,
        seen_facts=other_snapshot.seen_facts,
    )

    other, transition = other_before.apply(first_fill)

    _assert_zero_economic_delta(other_before, transition)
    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert transition.original_classification is (
        FirstObservationClassification.APPLIED_AVAILABLE
    )
    assert other.integrity & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    assert other.position.raw_quantity == 0
    assert other.root_heads.count == 0
    assert other.seen_facts.count == 1


def test_rejected_misroute_cannot_apply_when_later_routed_to_fact_symbol() -> None:
    other_fill = _fill(
        "msft-event",
        "msft-root",
        side=ExecutionSide.BUY,
        quantity=2,
        units=100,
        scope=_scope(
            order_id=OrderId("msft-order"),
            side=ExecutionSide.BUY,
            symbol_id=OTHER_SYMBOL,
        ),
    )
    rejected, first_transition = _Kernel.flat().apply(other_fill)
    assert first_transition.disposition is (
        TransitionDisposition.RECONCILIATION_REQUIRED
    )
    observation = rejected.seen_facts.get(other_fill.key)
    assert observation is not None
    assert observation.position_scope == POSITION_SCOPE
    other_snapshot = ExecutionSnapshot.bind_verified(
        PositionState.flat(OTHER_POSITION_SCOPE),
        PositionIntegrity.CONSISTENT,
        RootHeadIndex.empty(OTHER_POSITION_SCOPE),
        rejected.seen_facts,
    )
    other_before = _Kernel(
        position=other_snapshot.position,
        integrity=other_snapshot.integrity,
        root_heads=other_snapshot.root_heads,
        seen_facts=other_snapshot.seen_facts,
    )

    other, transition = other_before.apply(other_fill)

    _assert_zero_economic_delta(other_before, transition)
    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert transition.original_classification is (
        FirstObservationClassification.RECONCILIATION_REQUIRED
    )
    assert other.integrity & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    assert other.position.raw_quantity == 0
    assert other.root_heads.count == 0
    assert other.seen_facts.count == 1


def test_account_registry_rejects_cross_symbol_root_fill_collision() -> None:
    first_fill = _fill(
        "first-event",
        "shared-root",
        side=ExecutionSide.BUY,
        quantity=2,
        units=100,
    )
    first, _ = _Kernel.flat().apply(first_fill)
    other_snapshot = ExecutionSnapshot.bind_verified(
        PositionState.flat(OTHER_POSITION_SCOPE),
        PositionIntegrity.CONSISTENT,
        RootHeadIndex.empty(OTHER_POSITION_SCOPE),
        first.seen_facts,
    )
    reused_root = _fill(
        "other-event",
        "shared-root",
        side=ExecutionSide.BUY,
        quantity=3,
        units=101,
        scope=_scope(
            order_id=OrderId("other-buy-order"),
            side=ExecutionSide.BUY,
            symbol_id=OTHER_SYMBOL,
        ),
    )

    other, transition = _Kernel(
        position=other_snapshot.position,
        integrity=other_snapshot.integrity,
        root_heads=other_snapshot.root_heads,
        seen_facts=other_snapshot.seen_facts,
    ).apply(reused_root)

    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert transition.quantity_delta == 0
    assert other.position.raw_quantity == 0
    assert other.root_heads.count == 0
    assert other.integrity & (PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED)
    assert other.seen_facts.count == 2
    observation = other.seen_facts.get(reused_root.key)
    assert observation is not None
    assert observation.classification is (
        FirstObservationClassification.RECONCILIATION_REQUIRED
    )
    assert other.seen_facts.contains_root(first_fill.root_key)
    assert first.position.raw_quantity == 2
    rebound_first = ExecutionSnapshot.bind_verified(
        replace(first.position, _binding=None),
        first.integrity,
        RootHeadIndex(
            entries=first.root_heads.entries,
            position_scope=POSITION_SCOPE,
        ),
        other.seen_facts,
    )
    assert rebound_first.position.raw_quantity == 2
    assert rebound_first.seen_facts.count == 2


def test_bind_verified_accepts_complete_revision_chain() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=3, units=100)
    correction = _correct(
        "correction",
        "root",
        "fill",
        side=ExecutionSide.BUY,
        quantity=2,
        units=101,
    )
    bust = _bust(
        "bust",
        "root",
        "correction",
        side=ExecutionSide.BUY,
    )
    expected, _ = _apply_all(fill, correction, bust)
    position, roots, seen = _unbound_hydration_parts(expected)

    hydrated = ExecutionSnapshot.bind_verified(
        position,
        expected.integrity,
        roots,
        seen,
    )

    assert hydrated.position.raw_quantity == 0
    assert hydrated.position.cost_basis == _basis(0)
    assert hydrated.root_heads == expected.root_heads
    assert hydrated.seen_facts == expected.seen_facts


def test_bind_verified_accepts_rejected_observation_with_required_integrity() -> None:
    invalid = _correct(
        "orphan-correction",
        "missing-root",
        "missing-predecessor",
        side=ExecutionSide.BUY,
        quantity=1,
        units=101,
    )
    expected, _ = _Kernel.flat().apply(invalid)
    position, roots, seen = _unbound_hydration_parts(expected)

    hydrated = ExecutionSnapshot.bind_verified(
        position,
        expected.integrity,
        roots,
        seen,
    )

    assert hydrated.position.raw_quantity == 0
    assert hydrated.root_heads.count == 0
    assert hydrated.integrity & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED


def test_bind_verified_accepts_conservative_integrity_superset() -> None:
    sell = _fill(
        "sell",
        "sell-root",
        side=ExecutionSide.SELL,
        quantity=3,
        units=100,
    )
    cover = _fill(
        "cover",
        "cover-root",
        side=ExecutionSide.BUY,
        quantity=5,
        units=101,
    )
    recovered, _ = _apply_all(sell, cover)
    position, roots, seen = _unbound_hydration_parts(recovered)
    conservative = (
        PositionIntegrity.OVERFILL_QUARANTINE
        | PositionIntegrity.EXECUTION_FACT_CONFLICT
    )

    hydrated = ExecutionSnapshot.bind_verified(
        position,
        conservative,
        roots,
        seen,
    )

    assert hydrated.integrity == conservative


def test_forged_tail_fold_input_cannot_authorize_revision_basis() -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=10, units=100)
    applied, _ = _apply_all(fill)
    forged_position = replace(
        applied.position,
        tail_fold_input=FoldInput(
            raw_quantity=50,
            cost_basis=_basis(5_000),
            price_metadata=_price(100),
        ),
    )
    forged = replace(applied, position=forged_position)
    correction = _correct(
        "correct",
        "root",
        "fill",
        side=ExecutionSide.BUY,
        quantity=7,
        units=101,
    )

    after, transition = forged.apply(correction)

    _assert_zero_economic_delta(forged, transition)
    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert after.integrity & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED


@pytest.mark.parametrize("retained_cache", ["metadata", "tail-fold-input"])
def test_pending_position_rejects_retained_basis_cache(retained_cache: str) -> None:
    fill = _fill("fill", "root", side=ExecutionSide.BUY, quantity=1, units=100)
    applied, _ = _apply_all(fill)
    metadata = _price(100) if retained_cache == "metadata" else None
    tail_input = (
        FoldInput(
            raw_quantity=0,
            cost_basis=_basis(0),
            price_metadata=None,
        )
        if retained_cache == "tail-fold-input"
        else None
    )

    with pytest.raises(ValueError):
        replace(
            applied.position,
            basis_authority=BasisAuthority.BASIS_RECONCILIATION_PENDING,
            cost_basis=None,
            basis_price_metadata=metadata,
            tail_fold_input=tail_input,
        )


def test_slow_candidate_rejects_human_attested_root() -> None:
    kernel = _coherently_bound_human_kernel()

    candidate = derive_ordered_basis_candidate(kernel.position, kernel.root_heads)

    assert candidate.status is BasisCandidateStatus.SNAPSHOT_INCONSISTENT
    assert candidate.cost_basis is None


def _history_kernel(root_count: int) -> tuple[_Kernel, BrokerFillFact]:
    price = _price(100)
    root_keys: list[RootFillKey] = []
    head_ids: list[SourceEventId] = []
    heads: list[RootHead] = []
    seen: list[SeenFact] = []
    for index in range(root_count):
        event = f"history-event-{index}"
        root = f"history-root-{index}"
        scope = _scope(
            order_id=OrderId(f"history-order-{index}"),
            side=ExecutionSide.BUY,
        )
        fact = _fill(
            event,
            root,
            side=ExecutionSide.BUY,
            quantity=1,
            units=100,
            scope=scope,
            key=_key(event),
        )
        root_keys.append(fact.root_key)
        head_ids.append(fact.key.source_event_id)
        heads.append(
            RootHead(
                root_key=fact.root_key,
                original_sequence=index,
                scope=fact.scope,
                authority=fact.authority,
                current_source_event_id=fact.key.source_event_id,
                kind=fact.kind,
                quantity=fact.quantity,
                price=fact.price,
            )
        )
        seen.append(
            SeenFact(
                fact=fact,
                classification=FirstObservationClassification.APPLIED_AVAILABLE,
            )
        )
    unbound_position = PositionState.from_materialized(
        scope=POSITION_SCOPE,
        raw_quantity=root_count,
        basis_authority=BasisAuthority.AVAILABLE,
        cost_basis=_basis(root_count * 100),
        root_fill_sequence=tuple(root_keys),
        effective_head_ids=tuple(head_ids),
        basis_price_metadata=price,
        tail_fold_input=None,
    )
    snapshot = ExecutionSnapshot.bind_verified(
        unbound_position,
        PositionIntegrity.CONSISTENT,
        RootHeadIndex(entries=tuple(heads), position_scope=POSITION_SCOPE),
        SeenFactIndex(entries=tuple(seen)),
    )
    kernel = _Kernel(
        position=snapshot.position,
        integrity=snapshot.integrity,
        root_heads=snapshot.root_heads,
        seen_facts=snapshot.seen_facts,
    )
    incoming = _fill(
        "incoming-event",
        "incoming-root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=100,
        order_id=OrderId("incoming-order"),
    )
    return kernel, incoming


def _fast_apply_line_events(kernel: _Kernel, fact: BrokerFact) -> int:
    traced_files = {
        inspect.getsourcefile(apply_broker_execution_fact),
        inspect.getsourcefile(RootHeadIndex),
    }
    line_events = 0

    def count_lines(frame: FrameType, event: str, _arg: object) -> object:
        nonlocal line_events
        if event == "line" and frame.f_code.co_filename in traced_files:
            line_events += 1
        return count_lines

    previous_trace = sys.gettrace()
    sys.settrace(count_lines)
    try:
        _, transition = kernel.apply(fact)
    finally:
        sys.settrace(previous_trace)
    assert transition.disposition is TransitionDisposition.APPLIED
    return line_events


def test_fast_apply_line_events_are_independent_of_history_length() -> None:
    small, small_fact = _history_kernel(16)
    large, large_fact = _history_kernel(2_048)

    small_events = _fast_apply_line_events(small, small_fact)
    large_events = _fast_apply_line_events(large, large_fact)

    # Sparse radix nodes may require a few more bounded label comparisons as
    # their fan-out approaches the fixed byte alphabet. The 500-event headroom
    # is constant (not proportional to history) and still decisively kills the
    # former tuple scans/copies, whose 2,048-root path exceeded 53,000 events.
    assert large_events <= small_events + 500, (
        "one fast application scaled with historical roots/facts: "
        f"16 roots={small_events} line events, 2048 roots={large_events}"
    )


def test_fast_non_tail_revision_line_events_are_independent_of_history_length() -> None:
    small, _ = _history_kernel(16)
    large, _ = _history_kernel(2_048)
    revision = _correct(
        "history-correction",
        "history-root-0",
        "history-event-0",
        side=ExecutionSide.BUY,
        quantity=2,
        units=101,
        order_id=OrderId("history-order-0"),
    )

    small_events = _fast_apply_line_events(small, revision)
    large_events = _fast_apply_line_events(large, revision)

    # Sparse radix fan-out adds bounded binary-search work as the fixed byte
    # alphabet fills. This constant headroom still kills any ordered fold or
    # full-history materialization in the non-tail fast path.
    assert large_events <= small_events + 2_000, (
        "one non-tail revision scaled with ordered history: "
        f"16 roots={small_events} line events, 2048 roots={large_events}"
    )


def _loads_entries(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Attribute)
        and isinstance(child.ctx, ast.Load)
        and child.attr == "entries"
        for child in ast.walk(node)
    )


@pytest.mark.parametrize(
    ("owner", "method_name"),
    [
        (RootHeadIndex, "append"),
        (RootHeadIndex, "replace"),
        (SeenFactIndex, "add"),
    ],
    ids=["root-append", "root-replace", "seen-add"],
)
def test_fast_index_updates_do_not_materialize_entry_history(
    owner: type[RootHeadIndex] | type[SeenFactIndex],
    method_name: str,
) -> None:
    tree = ast.parse(dedent(inspect.getsource(getattr(owner, method_name))))
    materializers = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Add)
            and _loads_entries(node)
        )
        or (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Slice)
            and _loads_entries(node)
        )
        or (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"list", "tuple"}
            and _loads_entries(node)
        )
    ]

    assert not materializers, (
        f"{owner.__name__}.{method_name} copies or slices complete entry history"
    )


def test_root_head_rejects_malformed_economics_and_proof_fields() -> None:
    kernel, _ = _apply_all(
        _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    )
    head = kernel.root_heads.entries[0]
    invalid_changes: tuple[tuple[dict[str, object], type[Exception], str], ...] = (
        ({"original_sequence": True}, TypeError, "must be an integer"),
        ({"original_sequence": -1}, ValueError, "must be non-negative"),
        (
            {
                "scope": replace(
                    head.scope,
                    account=AccountId("different-account"),
                )
            },
            ValueError,
            "identical venue scope",
        ),
        ({"price": _price(0)}, ValueError, "price must be positive"),
        (
            {"kind": FactKind.TRADE_BUST},
            ValueError,
            "bust root head must have structural zero quantity",
        ),
        (
            {"quantity": Quantity(0)},
            ValueError,
            "fill/correction root heads require positive economics",
        ),
        (
            {"prefix_heads_commitment": "not-bytes"},
            TypeError,
            "prefix_heads_commitment must be bytes",
        ),
        (
            {"prefix_proof_commitment": "not-bytes"},
            TypeError,
            "prefix_proof_commitment must be bytes",
        ),
    )

    for changes, expected_error, message in invalid_changes:
        with pytest.raises(expected_error, match=message):
            replace(head, **changes)


def test_root_head_index_rejects_invalid_append_and_replace_operations() -> None:
    kernel, _ = _apply_all(
        _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    )
    head = kernel.root_heads.entries[0]

    with pytest.raises(TypeError, match="entries must be a tuple"):
        RootHeadIndex([head])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="key already exists"):
        kernel.root_heads.append(head)
    with pytest.raises(ValueError, match="current root count"):
        RootHeadIndex.empty(POSITION_SCOPE).append(replace(head, original_sequence=1))
    with pytest.raises(ValueError, match="share exact position scope"):
        RootHeadIndex.empty(POSITION_SCOPE).append(
            replace(
                head,
                scope=replace(head.scope, symbol_id=OTHER_SYMBOL),
            )
        )
    with pytest.raises(KeyError):
        kernel.root_heads.replace(
            replace(head, root_key=_root_key("unregistered-root"))
        )
    with pytest.raises(ValueError, match="original root sequence"):
        kernel.root_heads.replace(replace(head, original_sequence=1))
    with pytest.raises(ValueError, match="complete root scope"):
        kernel.root_heads.replace(
            replace(head, scope=replace(head.scope, order_id=OrderId("other-order")))
        )
    with pytest.raises(ValueError, match="root authority"):
        kernel.root_heads.replace(
            replace(head, authority=ExecutionAuthority.HUMAN_ATTESTED)
        )


def test_seen_registry_rejects_invalid_entries_and_claims_an_unowned_account() -> None:
    kernel, _ = _apply_all(
        _fill("fill", "root", side=ExecutionSide.BUY, quantity=2, units=100)
    )
    observation = kernel.seen_facts.entries[0]

    with pytest.raises(TypeError, match="canonical broker execution fact"):
        SeenFact(  # type: ignore[arg-type]
            object(),
            FirstObservationClassification.APPLIED_AVAILABLE,
        )
    with pytest.raises(TypeError, match="entries must be a tuple"):
        SeenFactIndex([observation])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="event key already exists"):
        kernel.seen_facts.add(observation)

    claimed = ExecutionSnapshot.bind_verified(
        PositionState.flat(POSITION_SCOPE),
        PositionIntegrity.CONSISTENT,
        RootHeadIndex.empty(POSITION_SCOPE),
        SeenFactIndex(),
    )
    assert claimed.seen_facts.belongs_to(POSITION_SCOPE)

    foreign_scope = replace(
        POSITION_SCOPE,
        account=AccountId("different-account"),
    )
    with pytest.raises(ValueError, match="different account"):
        ExecutionSnapshot.bind_verified(
            PositionState.flat(POSITION_SCOPE),
            PositionIntegrity.CONSISTENT,
            RootHeadIndex.empty(POSITION_SCOPE),
            SeenFactIndex.empty(foreign_scope),
        )


def test_revision_facts_expose_broker_authority() -> None:
    correction = _correct(
        "correct",
        "root",
        "fill",
        side=ExecutionSide.BUY,
        quantity=2,
        units=101,
    )
    bust = _bust(
        "bust",
        "root",
        "fill",
        side=ExecutionSide.BUY,
    )

    assert correction.authority is ExecutionAuthority.BROKER_AUTHORITATIVE
    assert bust.authority is ExecutionAuthority.BROKER_AUTHORITATIVE


def test_fold_input_rejects_malformed_state_and_partial_tail_proof() -> None:
    valid = FoldInput(
        raw_quantity=1,
        cost_basis=_basis(100),
        price_metadata=_price(100),
    )
    invalid_changes: tuple[tuple[dict[str, object], type[Exception], str], ...] = (
        ({"raw_quantity": True}, TypeError, "must be an exact integer"),
        ({"cost_basis": Fraction(100)}, TypeError, "must be ExactBasis"),
        (
            {"price_metadata": object()},
            TypeError,
            "must be ReportedPrice or None",
        ),
        (
            {"raw_quantity": 0},
            ValueError,
            "non-positive fold quantity cannot carry long basis",
        ),
        (
            {"position_scope": object()},
            TypeError,
            "must be PositionScope or None",
        ),
        (
            {"tail_root_key": object()},
            TypeError,
            "must be RootFillKey or None",
        ),
        (
            {"prefix_heads_commitment": "not-bytes"},
            TypeError,
            "prefix_heads_commitment must be bytes",
        ),
        (
            {"position_scope": POSITION_SCOPE},
            ValueError,
            "proof fields must be present together",
        ),
    )

    for changes, expected_error, message in invalid_changes:
        with pytest.raises(expected_error, match=message):
            replace(valid, **changes)


def test_materialized_position_rejects_malformed_hydration_state() -> None:
    root_key = _root_key("root")
    base: dict[str, object] = {
        "scope": POSITION_SCOPE,
        "raw_quantity": 0,
        "basis_authority": BasisAuthority.AVAILABLE,
        "cost_basis": _basis(0),
        "root_fill_sequence": (),
        "effective_head_ids": (),
        "basis_price_metadata": None,
        "tail_fold_input": None,
        "integrity_floor": PositionIntegrity.CONSISTENT,
    }
    invalid_changes: tuple[tuple[dict[str, object], type[Exception], str], ...] = (
        ({"root_fill_sequence": []}, TypeError, "must be a tuple"),
        ({"effective_head_ids": []}, TypeError, "must be a tuple"),
        (
            {"root_fill_sequence": (object(),)},
            TypeError,
            "entries must be RootFillKey",
        ),
        (
            {"effective_head_ids": (object(),)},
            TypeError,
            "entries must be SourceEventId",
        ),
        (
            {"root_fill_sequence": (root_key, root_key)},
            ValueError,
            "cannot contain duplicate roots",
        ),
        ({"scope": object()}, TypeError, "_scope must be PositionScope"),
        ({"raw_quantity": True}, TypeError, "must be an exact integer"),
        (
            {"basis_authority": object()},
            TypeError,
            "basis_authority must be BasisAuthority",
        ),
        (
            {"root_fill_sequence": (root_key,)},
            ValueError,
            "root sequence and effective heads must remain aligned",
        ),
        (
            {"basis_price_metadata": object()},
            TypeError,
            "basis_price_metadata must be ReportedPrice or None",
        ),
        (
            {"tail_fold_input": object()},
            TypeError,
            "tail_fold_input must be FoldInput or None",
        ),
        (
            {"integrity_floor": object()},
            TypeError,
            "integrity_floor must be PositionIntegrity",
        ),
        (
            {"cost_basis": None},
            ValueError,
            "available basis requires an exact cost basis",
        ),
        (
            {"cost_basis": _basis(1)},
            ValueError,
            "non-positive position cannot carry long basis",
        ),
        (
            {
                "basis_authority": BasisAuthority.BASIS_RECONCILIATION_PENDING,
            },
            ValueError,
            "pending basis cannot retain any basis-derived cache",
        ),
    )

    for changes, expected_error, message in invalid_changes:
        candidate = dict(base)
        candidate.update(changes)
        with pytest.raises(expected_error, match=message):
            PositionState.from_materialized(**candidate)  # type: ignore[arg-type]


def test_execution_kernel_public_entrypoints_reject_untyped_components() -> None:
    snapshot = ExecutionSnapshot.flat(POSITION_SCOPE)
    fact = _fill(
        "fill",
        "root",
        side=ExecutionSide.BUY,
        quantity=1,
        units=100,
    )

    with pytest.raises(TypeError, match="scope must be PositionScope"):
        PositionState.flat(object())  # type: ignore[arg-type]

    bind_arguments: dict[str, object] = {
        "position": snapshot.position,
        "integrity": snapshot.integrity,
        "root_heads": snapshot.root_heads,
        "seen_facts": snapshot.seen_facts,
    }
    for field_name, message in (
        ("position", "position must be PositionState"),
        ("integrity", "integrity must be PositionIntegrity"),
        ("root_heads", "root_heads must be RootHeadIndex"),
        ("seen_facts", "seen_facts must be SeenFactIndex"),
    ):
        invalid = dict(bind_arguments)
        invalid[field_name] = object()
        with pytest.raises(TypeError, match=message):
            ExecutionSnapshot.bind_verified(**invalid)  # type: ignore[arg-type]

    apply_arguments: dict[str, object] = {
        **bind_arguments,
        "fact": fact,
    }
    for field_name, message in (
        ("position", "position must be PositionState"),
        ("integrity", "integrity must be PositionIntegrity"),
        ("root_heads", "root_heads must be RootHeadIndex"),
        ("seen_facts", "seen_facts must be SeenFactIndex"),
    ):
        invalid = dict(apply_arguments)
        invalid[field_name] = object()
        with pytest.raises(TypeError, match=message):
            apply_broker_execution_fact(**invalid)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="position_snapshot must be PositionState"):
        derive_ordered_basis_candidate(  # type: ignore[arg-type]
            object(),
            snapshot.root_heads,
        )
    with pytest.raises(TypeError, match="root_heads must be RootHeadIndex"):
        derive_ordered_basis_candidate(  # type: ignore[arg-type]
            snapshot.position,
            object(),
        )
