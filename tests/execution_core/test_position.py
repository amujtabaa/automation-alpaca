"""RED-first bounded direct-proof contracts for the M2 execution owner seam."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import inspect

import pytest

import app.execution_core.position as position_module
from app.execution_core.fills import (
    BrokerFillFact,
    BrokerTradeCorrectFact,
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
    SourceEventId,
    SymbolId,
)
from app.execution_core.position import ExecutionSnapshot, apply_broker_execution_fact
from app.execution_core.values import (
    PriceScale,
    PriceUnits,
    Quantity,
    ReportedPrice,
    TickMetadata,
)


_BROKER = BrokerId("alpaca")
_ENVIRONMENT = EnvironmentId("paper")
_ACCOUNT = AccountId("m2-execution-owner")
_SYMBOL = SymbolId("AAPL")
_POSITION_SCOPE = PositionScope(
    broker=_BROKER,
    environment=_ENVIRONMENT,
    account=_ACCOUNT,
    symbol_id=_SYMBOL,
)
_SCALE = PriceScale(Decimal("1"))
_TICK = TickMetadata(tick_units=PriceUnits(1), scale=_SCALE)


def _key(source_event_id: str) -> ExecutionFactKey:
    return ExecutionFactKey(
        broker=_BROKER,
        environment=_ENVIRONMENT,
        account=_ACCOUNT,
        source_event_id=SourceEventId(source_event_id),
    )


def _scope(*, side: ExecutionSide = ExecutionSide.BUY) -> ExecutionScope:
    return ExecutionScope(
        broker=_BROKER,
        environment=_ENVIRONMENT,
        account=_ACCOUNT,
        order_id=OrderId("m2-execution-owner-order"),
        symbol_id=_SYMBOL,
        side=side,
    )


def _price(units: int) -> ReportedPrice:
    return ReportedPrice(
        units=PriceUnits(units),
        scale=_SCALE,
        tick=_TICK,
    )


def _fill(
    source_event_id: str,
    root_fill_id: str,
    *,
    side: ExecutionSide = ExecutionSide.BUY,
    quantity: int = 2,
    units: int = 100,
) -> BrokerFillFact:
    return BrokerFillFact(
        key=_key(source_event_id),
        scope=_scope(side=side),
        root_fill_id=RootFillId(root_fill_id),
        quantity=Quantity(quantity),
        price=_price(units),
    )


def _correct(
    source_event_id: str,
    root_fill_id: str,
    predecessor_source_event_id: str,
    *,
    quantity: int = 3,
    units: int = 101,
) -> BrokerTradeCorrectFact:
    return BrokerTradeCorrectFact(
        key=_key(source_event_id),
        scope=_scope(),
        root_fill_id=RootFillId(root_fill_id),
        predecessor_source_event_id=SourceEventId(predecessor_source_event_id),
        revised_quantity=Quantity(quantity),
        revised_price=_price(units),
    )


def _snapshot_after(
    *facts: BrokerFillFact | BrokerTradeCorrectFact,
) -> ExecutionSnapshot:
    snapshot = ExecutionSnapshot.flat(_POSITION_SCOPE)
    for fact in facts:
        transition = apply_broker_execution_fact(
            snapshot.position,
            snapshot.integrity,
            snapshot.root_heads,
            snapshot.seen_facts,
            fact,
        )
        snapshot = position_module._bind_components(
            transition.position,
            transition.integrity,
            transition.root_heads,
            transition.seen_facts,
        )
    return snapshot


def _proof(
    snapshot: ExecutionSnapshot,
    fact: BrokerFillFact | BrokerTradeCorrectFact,
) -> object:
    state = position_module._m2_execution_state_from_snapshot(snapshot)
    predecessor = None
    if type(fact) is BrokerTradeCorrectFact:
        predecessor = snapshot.seen_facts.get(
            _key(fact.predecessor_source_event_id.value)
        )
    return position_module._M2ExecutionObservationProof(
        state_commitment=state.commitment,
        fact=fact,
        prior_observation=snapshot.seen_facts.get(fact.key),
        root_head=snapshot.root_heads.get(fact.root_key),
        predecessor_observation=predecessor,
        root_claimed=snapshot.seen_facts.contains_root(fact.root_key),
    )


@pytest.mark.parametrize(
    ("prior_facts", "candidate"),
    (
        ((), _fill("fill-1", "root-1")),
        (
            (),
            _fill(
                "sell-1",
                "sell-root-1",
                side=ExecutionSide.SELL,
            ),
        ),
        ((_fill("fill-1", "root-1"),), _fill("fill-1", "root-1")),
        (
            (_fill("fill-1", "root-1"),),
            _fill("fill-1", "root-1", units=101),
        ),
        (
            (_fill("fill-1", "root-1"),),
            _correct("correct-1", "root-1", "fill-1"),
        ),
        (
            (_fill("fill-1", "root-1"),),
            _correct("correct-1", "root-1", "not-the-current-head"),
        ),
    ),
)
def test_m2_execution_direct_kernel_matches_the_retained_public_reducer(
    prior_facts: tuple[BrokerFillFact, ...],
    candidate: BrokerFillFact | BrokerTradeCorrectFact,
) -> None:
    snapshot = _snapshot_after(*prior_facts)
    state = position_module._m2_execution_state_from_snapshot(snapshot)
    proof = _proof(snapshot, candidate)

    assert position_module._m2_execution_state_from_direct_proof(state, proof) == state
    expected = position_module._m2_apply_broker_execution_fact(state, proof)
    actual = apply_broker_execution_fact(
        snapshot.position,
        snapshot.integrity,
        snapshot.root_heads,
        snapshot.seen_facts,
        candidate,
    )
    assert expected == (actual.disposition, actual.original_classification)


def test_m2_execution_state_is_bounded_and_rejects_cross_state_proof() -> None:
    snapshot = _snapshot_after(_fill("fill-1", "root-1"))
    state = position_module._m2_execution_state_from_snapshot(snapshot)
    candidate = _correct("correct-1", "root-1", "fill-1")
    proof = _proof(snapshot, candidate)

    assert not hasattr(state, "root_heads")
    assert not hasattr(state, "seen_facts")
    reconstructed = position_module._m2_execution_state_from_direct_proof(
        (
            state.scope,
            state.raw_quantity,
            state.basis_authority,
            state.cost_basis,
            state.basis_price_metadata,
            state.tail_fold_input,
            state.integrity_floor,
            state.integrity,
            state.account_reconciliation_required,
            state.reconciliation_transition_count,
            state.reconciliation_transition_head,
            state.root_count,
            state.root_order_commitment,
            state.head_ids_commitment,
        ),
        proof,
    )
    assert reconstructed == state
    with pytest.raises(ValueError, match="state commitment"):
        position_module._m2_execution_state_from_direct_proof(
            state,
            replace(proof, state_commitment=b"x" * 32),
        )


def test_public_broker_execution_reducer_delegates_to_the_m2_owner_kernel() -> None:
    source = inspect.getsource(position_module.apply_broker_execution_fact)
    assert "_m2_apply_broker_execution_fact" in source
