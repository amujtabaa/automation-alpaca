"""RED-first bounded direct-proof contracts for the M2 execution owner seam."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from fractions import Fraction

import pytest

import app.execution_core.position as position_module
from app.execution_core.fills import (
    BrokerFillFact,
    BrokerTradeBustFact,
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


def _incompatible_price(units: int) -> ReportedPrice:
    return ReportedPrice(
        units=PriceUnits(units),
        scale=_SCALE,
        tick=TickMetadata(tick_units=PriceUnits(2), scale=_SCALE),
    )


def _fill(
    source_event_id: str,
    root_fill_id: str,
    *,
    side: ExecutionSide = ExecutionSide.BUY,
    quantity: int = 2,
    units: int = 100,
    price: ReportedPrice | None = None,
) -> BrokerFillFact:
    return BrokerFillFact(
        key=_key(source_event_id),
        scope=_scope(side=side),
        root_fill_id=RootFillId(root_fill_id),
        quantity=Quantity(quantity),
        price=_price(units) if price is None else price,
    )


def _correct(
    source_event_id: str,
    root_fill_id: str,
    predecessor_source_event_id: str,
    *,
    side: ExecutionSide = ExecutionSide.BUY,
    quantity: int = 3,
    units: int = 101,
) -> BrokerTradeCorrectFact:
    return BrokerTradeCorrectFact(
        key=_key(source_event_id),
        scope=_scope(side=side),
        root_fill_id=RootFillId(root_fill_id),
        predecessor_source_event_id=SourceEventId(predecessor_source_event_id),
        revised_quantity=Quantity(quantity),
        revised_price=_price(units),
    )


def _bust(
    source_event_id: str,
    root_fill_id: str,
    predecessor_source_event_id: str,
    *,
    side: ExecutionSide = ExecutionSide.BUY,
) -> BrokerTradeBustFact:
    return BrokerTradeBustFact(
        key=_key(source_event_id),
        scope=_scope(side=side),
        root_fill_id=RootFillId(root_fill_id),
        predecessor_source_event_id=SourceEventId(predecessor_source_event_id),
        reported_price=_price(99),
    )


def _snapshot_after(
    *facts: BrokerFillFact | BrokerTradeCorrectFact | BrokerTradeBustFact,
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
    fact: BrokerFillFact | BrokerTradeCorrectFact | BrokerTradeBustFact,
) -> object:
    state = position_module._m2_execution_state_from_snapshot(snapshot)
    return position_module._M2ExecutionObservationProof.from_snapshot(
        state,
        snapshot,
        fact,
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
        (
            (_fill("fill-1", "root-1"),),
            _bust("bust-1", "root-1", "fill-1"),
        ),
        (
            (_fill("sell-1", "sell-root-1", side=ExecutionSide.SELL),),
            _correct(
                "sell-correct-1",
                "sell-root-1",
                "sell-1",
                side=ExecutionSide.SELL,
            ),
        ),
        (
            (_fill("fill-1", "root-1"),),
            _fill(
                "fill-2",
                "root-2",
                price=_incompatible_price(102),
            ),
        ),
    ),
)
def test_m2_execution_direct_kernel_matches_the_retained_public_reducer(
    prior_facts: tuple[BrokerFillFact, ...],
    candidate: BrokerFillFact | BrokerTradeCorrectFact | BrokerTradeBustFact,
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
            state.root_heads_commitment,
            state.seen_facts_commitment,
        ),
        proof,
    )
    assert reconstructed == state
    object.__setattr__(proof, "state_commitment", b"x" * 32)
    with pytest.raises(ValueError, match="not authentic"):
        position_module._m2_execution_state_from_direct_proof(
            state,
            proof,
        )


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    (
        ("root_head", None),
        (
            "prior_observation",
            _snapshot_after(_fill("other-1", "other-root-1")).seen_facts.get(
                _key("other-1")
            ),
        ),
        ("root_heads_commitment", b"x" * 32),
        ("seen_facts_commitment", b"y" * 32),
    ),
)
def test_m2_execution_direct_proof_rejects_substituted_or_absent_current_rows(
    field_name: str,
    replacement: object,
) -> None:
    snapshot = _snapshot_after(_fill("fill-1", "root-1"))
    state = position_module._m2_execution_state_from_snapshot(snapshot)
    proof = _proof(snapshot, _correct("correct-1", "root-1", "fill-1"))

    object.__setattr__(proof, field_name, replacement)

    with pytest.raises(ValueError, match="not authentic"):
        position_module._m2_execution_state_from_direct_proof(state, proof)


def test_m2_execution_direct_proof_rejects_a_cross_state_revision_slice() -> None:
    source_snapshot = _snapshot_after(_fill("fill-1", "root-1"))
    source_state = position_module._m2_execution_state_from_snapshot(source_snapshot)
    proof = _proof(source_snapshot, _correct("correct-1", "root-1", "fill-1"))
    other_snapshot = _snapshot_after(_fill("fill-2", "root-2"))
    other_state = position_module._m2_execution_state_from_snapshot(other_snapshot)

    assert source_state.scope == other_state.scope
    with pytest.raises(ValueError, match="state commitment"):
        position_module._m2_execution_state_from_direct_proof(other_state, proof)


def test_public_broker_execution_reducer_consumes_the_m2_owner_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = ExecutionSnapshot.flat(_POSITION_SCOPE)
    candidate = _fill("fill-1", "root-1")
    sentinel = (
        position_module.TransitionDisposition.RECONCILIATION_REQUIRED,
        position_module.FirstObservationClassification.RECONCILIATION_REQUIRED,
    )
    monkeypatch.setattr(
        position_module,
        "_m2_apply_broker_execution_fact",
        lambda _state, _proof: sentinel,
    )

    transition = apply_broker_execution_fact(
        snapshot.position,
        snapshot.integrity,
        snapshot.root_heads,
        snapshot.seen_facts,
        candidate,
    )

    assert (transition.disposition, transition.original_classification) == sentinel


def test_m2_execution_fold_mismatch_keeps_direct_and_public_paths_in_lockstep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _snapshot_after(_fill("fill-1", "root-1"))
    candidate = _fill("fill-2", "root-2")
    state = position_module._m2_execution_state_from_snapshot(snapshot)
    proof = _proof(snapshot, candidate)
    original_fold = position_module._fold_one

    def _mismatched_fold(
        raw_quantity: int,
        cost_basis: Fraction,
        side: ExecutionSide,
        absolute_quantity: int,
        price: ReportedPrice | None,
    ) -> tuple[int, Fraction]:
        quantity, basis = original_fold(
            raw_quantity,
            cost_basis,
            side,
            absolute_quantity,
            price,
        )
        return quantity + 1, basis

    monkeypatch.setattr(position_module, "_fold_one", _mismatched_fold)
    expected = position_module._m2_apply_broker_execution_fact(state, proof)
    actual = apply_broker_execution_fact(
        snapshot.position,
        snapshot.integrity,
        snapshot.root_heads,
        snapshot.seen_facts,
        candidate,
    )

    assert expected == (actual.disposition, actual.original_classification)


def test_incoherent_snapshot_bypasses_the_m2_owner_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = ExecutionSnapshot.flat(_POSITION_SCOPE)
    unbound_position = replace(snapshot.position, _binding=None)
    monkeypatch.setattr(
        position_module,
        "_m2_apply_broker_execution_fact",
        lambda _state, _proof: (_ for _ in ()).throw(
            AssertionError("unexpected M2 call")
        ),
    )

    transition = apply_broker_execution_fact(
        unbound_position,
        snapshot.integrity,
        snapshot.root_heads,
        snapshot.seen_facts,
        _fill("fill-1", "root-1"),
    )

    assert (
        transition.disposition
        is position_module.TransitionDisposition.RECONCILIATION_REQUIRED
    )
