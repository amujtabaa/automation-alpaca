"""RED-first bounded direct-proof contracts for the M2 execution owner seam."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
import re
from types import SimpleNamespace

import pytest

import app.execution_core.fills as fills_module
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
from app.execution_core.persistence import checkpoint_codec
from app.execution_core.position import ExecutionSnapshot, apply_broker_execution_fact
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


def _copied_m2_execution_state_shape(state: object) -> SimpleNamespace:
    """Model a caller-shaped record with every visible execution-state member."""

    return SimpleNamespace(
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
        commitment=state.commitment,
    )


def _resign_m2_execution_proof(
    proof: position_module._M2ExecutionObservationProof,
) -> None:
    """Model an adversary who can recompute a proof's outer self-seal."""

    object.__setattr__(
        proof,
        "commitment",
        position_module._m2_execution_observation_proof_commitment(
            state_commitment=proof.state_commitment,
            root_heads_commitment=proof.root_heads_commitment,
            seen_facts_commitment=proof.seen_facts_commitment,
            root_head_map_commitment=proof.root_head_map_commitment,
            seen_fact_map_commitment=proof.seen_fact_map_commitment,
            root_claim_map_commitment=proof.root_claim_map_commitment,
            fact=proof.fact,
            prior_observation=proof.prior_observation,
            root_head=proof.root_head,
            predecessor_observation=proof.predecessor_observation,
            root_claimed=proof.root_claimed,
            prior_observation_witness=proof.prior_observation_witness,
            root_head_witness=proof.root_head_witness,
            predecessor_observation_witness=proof.predecessor_observation_witness,
            root_claim_witness=proof.root_claim_witness,
        ),
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
            state.root_head_map_commitment,
            state.seen_fact_map_commitment,
            state.root_claim_map_commitment,
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


def test_m2_execution_checkpoint_component_round_trips_canonically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _snapshot_after(
        _fill("codec-fill-1", "codec-root-1"),
        _fill("codec-fill-2", "codec-root-2"),
    )
    state = position_module._m2_execution_state_from_snapshot(snapshot)
    proof = _proof(snapshot, _fill("codec-probe", "codec-probe-root"))
    assert state.cost_basis is not None
    assert state.basis_price_metadata is not None
    assert state.tail_fold_input is not None

    encoded = checkpoint_codec._encode_m2_execution_state_component(state)
    decoded = checkpoint_codec._decode_m2_execution_state_component(encoded, proof)

    assert decoded == state
    assert position_module._m2_execution_state_is_authentic(decoded)
    assert checkpoint_codec._encode_m2_execution_state_component(decoded) == encoded
    assert encoded == [
        "m2.position.execution-state/v1",
        checkpoint_codec._operations._encode_m2_position_scope(state.scope),
        state.raw_quantity,
        ["m2.position.BasisAuthority", state.basis_authority.value],
        [
            "m2.scalar.Fraction/v1",
            state.cost_basis.value.numerator,
            state.cost_basis.value.denominator,
        ],
        checkpoint_codec._encode_m2_optional_m1_value(state.basis_price_metadata),
        checkpoint_codec._encode_m2_tail_fold_input(state.tail_fold_input),
        ["m2.position.PositionIntegrity", state.integrity_floor.value],
        ["m2.position.PositionIntegrity", state.integrity.value],
        state.account_reconciliation_required,
        state.reconciliation_transition_count,
        state.reconciliation_transition_head.hex(),
        state.root_count,
        state.root_order_commitment.hex(),
        state.head_ids_commitment.hex(),
        state.root_heads_commitment.hex(),
        state.seen_facts_commitment.hex(),
        state.root_head_map_commitment.hex(),
        state.seen_fact_map_commitment.hex(),
        state.root_claim_map_commitment.hex(),
        state.commitment.hex(),
    ]

    tampered_commitment = [*encoded]
    tampered_commitment[-1] = "00" * 32
    with pytest.raises(ValueError, match="execution state is not authentic"):
        checkpoint_codec._decode_m2_execution_state_component(
            tampered_commitment, proof
        )

    # A decoded component is not usable without a proof tied to these exact
    # retained aggregate commitments.
    other_snapshot = _snapshot_after(_fill("other-state-fill", "other-state-root"))
    other_proof = _proof(other_snapshot, _fill("other-state-probe", "other-probe"))
    with pytest.raises(
        ValueError,
        match="^direct proof state commitment does not match state$",
    ):
        checkpoint_codec._decode_m2_execution_state_component(encoded, other_proof)

    # These are valid field shapes with the original state commitment retained.
    # They kill commitment regressions that omit either semantic member.
    alternate_tail_state = position_module._m2_execution_state_from_snapshot(
        _snapshot_after(
            _fill("alternate-tail-fill-1", "alternate-tail-root-1"),
            _fill("alternate-tail-fill-2", "alternate-tail-root-2", units=101),
        )
    )
    assert alternate_tail_state.tail_fold_input is not None
    commitment_member_mutants = (
        (2, state.raw_quantity + 1),
        (
            6,
            checkpoint_codec._encode_m2_tail_fold_input(
                alternate_tail_state.tail_fold_input
            ),
        ),
    )
    for member_index, replacement in commitment_member_mutants:
        malformed = [*encoded]
        malformed[member_index] = replacement
        with pytest.raises(
            ValueError,
            match="^direct proof state commitment does not match state$",
        ):
            checkpoint_codec._decode_m2_execution_state_component(malformed, proof)

    # Distinguishable, locally valid flag values make the two fixed enum slots
    # observable even though ordinary snapshot states currently share them.
    integrity_order_mutant = [*encoded]
    integrity_order_mutant[7] = [
        "m2.position.PositionIntegrity",
        position_module.PositionIntegrity.EXECUTION_FACT_CONFLICT.value,
    ]
    integrity_order_mutant[8] = [
        "m2.position.PositionIntegrity",
        (
            position_module.PositionIntegrity.EXECUTION_FACT_CONFLICT
            | position_module.PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
        ).value,
    ]
    with pytest.raises(
        ValueError,
        match="^direct proof state commitment does not match state$",
    ):
        checkpoint_codec._decode_m2_execution_state_component(
            integrity_order_mutant,
            proof,
        )

    flat_snapshot = _snapshot_after()
    flat_state = position_module._m2_execution_state_from_snapshot(flat_snapshot)
    flat_encoded = checkpoint_codec._encode_m2_execution_state_component(flat_state)
    assert flat_encoded[5:7] == [None, None]
    assert (
        checkpoint_codec._decode_m2_execution_state_component(
            flat_encoded,
            _proof(flat_snapshot, _fill("flat-codec-probe", "flat-codec-root")),
        )
        == flat_state
    )

    pending_snapshot = _snapshot_after(
        _fill("pending-codec-fill-1", "pending-codec-root-1"),
        _fill(
            "pending-codec-fill-2",
            "pending-codec-root-2",
            price=_incompatible_price(102),
        ),
    )
    pending_state = position_module._m2_execution_state_from_snapshot(pending_snapshot)
    pending_encoded = checkpoint_codec._encode_m2_execution_state_component(
        pending_state
    )
    assert pending_encoded[4:7] == [None, None, None]
    assert (
        checkpoint_codec._decode_m2_execution_state_component(
            pending_encoded,
            _proof(
                pending_snapshot, _fill("pending-codec-probe", "pending-codec-root")
            ),
        )
        == pending_state
    )

    with pytest.raises(
        TypeError,
        match="^state must be exact _M2ExecutionState$",
    ):
        checkpoint_codec._encode_m2_execution_state_component(
            _copied_m2_execution_state_shape(state)
        )
    mutated_state = position_module._m2_execution_state_from_snapshot(snapshot)
    object.__setattr__(mutated_state, "raw_quantity", mutated_state.raw_quantity + 1)
    with pytest.raises(ValueError, match="^execution state is not authentic$"):
        checkpoint_codec._encode_m2_execution_state_component(mutated_state)

    wrong_m1_value = checkpoint_codec._operations._encode_m2_m1_atom(Quantity(1))
    malformed_members = (
        (
            0,
            "wrong-execution-state-tag",
            ValueError,
            "aggregate must have exact tag m2.position.execution-state/v1",
        ),
        (
            1,
            [],
            ValueError,
            "m1.fills.PositionScope/v1 aggregate has the wrong member count",
        ),
        (2, True, TypeError, "execution state raw quantity must be an exact integer"),
        (
            3,
            ["wrong-basis-authority-tag", encoded[3][1]],
            ValueError,
            "basis authority tag is not admitted",
        ),
        (
            4,
            [],
            ValueError,
            "m2.scalar.Fraction/v1 aggregate has the wrong member count",
        ),
        (
            5,
            wrong_m1_value,
            ValueError,
            "execution state basis price metadata must decode to ReportedPrice",
        ),
        (
            6,
            [],
            ValueError,
            "m2.position.tail-fold-input/v1 aggregate has the wrong member count",
        ),
        (
            7,
            ["wrong-integrity-tag", encoded[7][1]],
            ValueError,
            "position integrity tag is not admitted",
        ),
        (
            8,
            ["wrong-integrity-tag", encoded[8][1]],
            ValueError,
            "position integrity tag is not admitted",
        ),
        (9, 0, TypeError, "execution state reconciliation required must be exact bool"),
        (
            10,
            True,
            TypeError,
            "execution state reconciliation transition count must be an exact integer",
        ),
        (
            11,
            0,
            TypeError,
            "execution state reconciliation transition head must be exact text",
        ),
        (12, True, TypeError, "execution state root count must be an exact integer"),
        (13, 0, TypeError, "execution state root order commitment must be exact text"),
        (14, 0, TypeError, "execution state head ids commitment must be exact text"),
        (15, 0, TypeError, "execution state root heads commitment must be exact text"),
        (16, 0, TypeError, "execution state seen facts commitment must be exact text"),
        (
            17,
            0,
            TypeError,
            "execution state root head map commitment must be exact text",
        ),
        (
            18,
            0,
            TypeError,
            "execution state seen fact map commitment must be exact text",
        ),
        (
            19,
            0,
            TypeError,
            "execution state root claim map commitment must be exact text",
        ),
        (20, 0, TypeError, "execution state commitment must be exact text"),
    )
    assert {member_index for member_index, *_ in malformed_members} == set(
        range(len(encoded))
    )
    for member_index, replacement, error_type, message in malformed_members:
        malformed = [*encoded]
        malformed[member_index] = replacement
        with pytest.raises(error_type, match=rf"\A{re.escape(message)}\Z"):
            checkpoint_codec._decode_m2_execution_state_component(malformed, proof)

    invalid_enum_members = (
        (
            3,
            ["m2.position.BasisAuthority", "NOT_ADMITTED"],
            "basis authority value is not admitted",
        ),
        (
            7,
            ["m2.position.PositionIntegrity", 8],
            "position integrity value is not admitted",
        ),
    )
    for member_index, replacement, message in invalid_enum_members:
        malformed = [*encoded]
        malformed[member_index] = replacement
        with pytest.raises(ValueError, match=rf"\A{re.escape(message)}\Z"):
            checkpoint_codec._decode_m2_execution_state_component(malformed, proof)

    structural_mutants = (
        (
            encoded[:-1],
            "m2.position.execution-state/v1 aggregate has the wrong member count",
        ),
        (
            [*encoded, "unexpected-member"],
            "m2.position.execution-state/v1 aggregate has the wrong member count",
        ),
        (
            [encoded[0], encoded[2], encoded[1], *encoded[3:]],
            "m1.fills.PositionScope/v1 aggregate has the wrong member count",
        ),
    )
    for malformed, message in structural_mutants:
        with pytest.raises(ValueError, match=rf"\A{re.escape(message)}\Z"):
            checkpoint_codec._decode_m2_execution_state_component(malformed, proof)

    original_encode = checkpoint_codec._encode_m2_execution_state_component

    def _noncanonical_execution_encode(value: object) -> list[object]:
        return [*original_encode(value), "unexpected-member"]

    monkeypatch.setattr(
        checkpoint_codec,
        "_encode_m2_execution_state_component",
        _noncanonical_execution_encode,
    )
    with pytest.raises(
        ValueError,
        match="^execution state component is not canonical$",
    ):
        checkpoint_codec._decode_m2_execution_state_component(encoded, proof)


def test_m2_tail_fold_checkpoint_component_round_trips_canonically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = position_module._m2_execution_state_from_snapshot(
        _snapshot_after(
            _fill("codec-tail-fill-1", "codec-tail-root-1"),
            _fill("codec-tail-fill-2", "codec-tail-root-2"),
        )
    )
    tail = state.tail_fold_input
    assert tail is not None

    encoded = checkpoint_codec._encode_m2_tail_fold_input(tail)
    decoded = checkpoint_codec._decode_m2_tail_fold_input(encoded)

    assert decoded == tail
    assert checkpoint_codec._encode_m2_tail_fold_input(decoded) == encoded
    assert encoded == [
        "m2.position.tail-fold-input/v1",
        tail.raw_quantity,
        checkpoint_codec._operations._encode_m2_fraction(tail.cost_basis.value),
        checkpoint_codec._encode_m2_optional_m1_value(tail.price_metadata),
        checkpoint_codec._operations._encode_m2_position_scope(tail.position_scope),
        checkpoint_codec._encode_m2_optional_m1_value(tail.tail_root_key),
        tail.prefix_count,
        tail.prefix_heads_commitment.hex(),
    ]

    null_tail = position_module.FoldInput(
        raw_quantity=0,
        cost_basis=ExactBasis(Fraction(0)),
        price_metadata=None,
    )
    with pytest.raises(
        ValueError,
        match="^tail fold input must carry a bound predecessor proof$",
    ):
        checkpoint_codec._encode_m2_tail_fold_input(null_tail)

    with pytest.raises(TypeError, match="^tail fold input must be exact FoldInput$"):
        checkpoint_codec._encode_m2_tail_fold_input(
            SimpleNamespace(
                raw_quantity=tail.raw_quantity,
                cost_basis=tail.cost_basis,
                price_metadata=tail.price_metadata,
                position_scope=tail.position_scope,
                tail_root_key=tail.tail_root_key,
                prefix_count=tail.prefix_count,
                prefix_heads_commitment=tail.prefix_heads_commitment,
            )
        )

    wrong_m1_value = checkpoint_codec._operations._encode_m2_m1_atom(Quantity(1))
    malformed_members = (
        (
            0,
            "wrong-tail-fold-tag",
            ValueError,
            "aggregate must have exact tag m2.position.tail-fold-input/v1",
        ),
        (1, True, TypeError, "tail fold raw quantity must be an exact integer"),
        (
            2,
            [],
            ValueError,
            "m2.scalar.Fraction/v1 aggregate has the wrong member count",
        ),
        (
            3,
            wrong_m1_value,
            ValueError,
            "tail fold price metadata must decode to ReportedPrice",
        ),
        (
            4,
            [],
            ValueError,
            "m1.fills.PositionScope/v1 aggregate has the wrong member count",
        ),
        (
            5,
            wrong_m1_value,
            ValueError,
            "tail fold root key must decode to RootFillKey",
        ),
        (6, True, TypeError, "tail fold prefix count must be an exact integer"),
        (7, 0, TypeError, "tail fold prefix commitment must be exact text"),
    )
    assert {member_index for member_index, *_ in malformed_members} == set(
        range(len(encoded))
    )
    for member_index, replacement, error_type, message in malformed_members:
        malformed = [*encoded]
        malformed[member_index] = replacement
        with pytest.raises(error_type, match=rf"\A{re.escape(message)}\Z"):
            checkpoint_codec._decode_m2_tail_fold_input(malformed)

    original_encode = checkpoint_codec._encode_m2_tail_fold_input

    def _noncanonical_tail_encode(value: object) -> list[object]:
        return [*original_encode(value), "unexpected-member"]

    monkeypatch.setattr(
        checkpoint_codec,
        "_encode_m2_tail_fold_input",
        _noncanonical_tail_encode,
    )
    with pytest.raises(
        ValueError,
        match="^tail fold input is not canonical$",
    ):
        checkpoint_codec._decode_m2_tail_fold_input(encoded)


def test_persistent_map_witness_covers_both_prefix_nonmembership_cases() -> None:
    long_only = fills_module._PersistentKeyMap.empty().insert_new(
        b"prefix/descendant",
        "descendant",
        b"a" * 32,
    )
    absent_prefix = long_only._witness_for(b"prefix")

    assert absent_prefix._matches(long_only.commitment, b"prefix", None)

    with_prefix = long_only.insert_new(b"prefix", "prefix", b"b" * 32)
    present_prefix = with_prefix._witness_for(b"prefix")

    assert present_prefix._matches(with_prefix.commitment, b"prefix", b"b" * 32)
    assert not present_prefix._matches(with_prefix.commitment, b"prefix", None)

    multi_child = (
        fills_module._PersistentKeyMap.empty()
        .insert_new(b"aa", "first", b"c" * 32)
        .insert_new(b"ba", "second", b"d" * 32)
    )
    ordered_witness = multi_child._witness_for(b"aa")
    root = ordered_witness.nodes[0]
    assert len(root.children) == 2

    reordered_witness = replace(
        ordered_witness,
        nodes=(
            replace(root, children=tuple(reversed(root.children))),
            *ordered_witness.nodes[1:],
        ),
    )
    duplicated_child_witness = replace(
        ordered_witness,
        nodes=(
            replace(
                root,
                children=(root.children[0], root.children[0], *root.children),
            ),
            *ordered_witness.nodes[1:],
        ),
    )

    assert not reordered_witness._matches(multi_child.commitment, b"aa", b"c" * 32)
    assert not duplicated_child_witness._matches(
        multi_child.commitment,
        b"aa",
        b"c" * 32,
    )


def test_m2_execution_direct_proof_rejects_a_resigned_wrong_key_witness() -> None:
    first = _fill("fill-1", "root-1")
    second = _fill("fill-2", "root-2")
    snapshot = _snapshot_after(first, second)
    state = position_module._m2_execution_state_from_snapshot(snapshot)
    proof = _proof(snapshot, _correct("correct-1", "root-1", "fill-1"))
    object.__setattr__(
        proof,
        "root_head_witness",
        snapshot.root_heads._current_head_witness(second.root_key),
    )
    _resign_m2_execution_proof(proof)

    assert position_module._M2ExecutionObservationProof._is_authentic(proof)
    with pytest.raises(ValueError, match="root membership"):
        position_module._m2_execution_state_from_direct_proof(state, proof)


def test_m2_execution_direct_proof_rejects_resigned_wrong_key_witnesses() -> None:
    first = _fill("fill-1", "root-1")
    second = _fill("fill-2", "root-2")
    snapshot = _snapshot_after(first, second)
    state = position_module._m2_execution_state_from_snapshot(snapshot)
    candidate = _correct("correct-1", "root-1", "fill-1")
    mutations = (
        (
            "prior_observation_witness",
            snapshot.seen_facts._fact_witness(second.key),
            "prior membership",
        ),
        (
            "predecessor_observation_witness",
            snapshot.seen_facts._fact_witness(second.key),
            "predecessor membership",
        ),
        (
            "root_claim_witness",
            snapshot.seen_facts._root_claim_witness(second.root_key),
            "root claim membership",
        ),
    )

    for field_name, wrong_witness, failure in mutations:
        proof = _proof(snapshot, candidate)
        assert type(proof) is position_module._M2ExecutionObservationProof
        object.__setattr__(proof, field_name, wrong_witness)
        _resign_m2_execution_proof(proof)

        assert position_module._M2ExecutionObservationProof._is_authentic(proof)
        with pytest.raises(ValueError, match=failure):
            position_module._m2_execution_state_from_direct_proof(state, proof)


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
