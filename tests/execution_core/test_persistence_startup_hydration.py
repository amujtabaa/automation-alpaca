from __future__ import annotations

import pytest

from app.execution_core import identity
from app.execution_core import position
from app.execution_core.persistence import checkpoint_codec
from app.execution_core.persistence import records
import test_persistence_runtime_checkpoint_pure as checkpoint_fixtures


def _loaded_checkpoint(
    inputs: tuple[object, object, object, object],
) -> tuple[
    checkpoint_codec.RuntimeCheckpointEnvelope,
    records.RuntimeCheckpointSelectionProof,
]:
    proof, book, authority, owners = inputs
    projected = checkpoint_codec._project_runtime_checkpoint(
        proof,  # type: ignore[arg-type]
        book,  # type: ignore[arg-type]
        authority,  # type: ignore[arg-type]
        owners,  # type: ignore[arg-type]
    )
    loaded = checkpoint_codec._decode_runtime_checkpoint(
        checkpoint_codec.encode_runtime_checkpoint(projected),
        bytes.fromhex("12" * 32),
    )
    expected = records.KernelCheckpointRecord(
        projected.application_generation_id,
        projected.currentness_head_ordinal,
        projected.payload_sha256,
        projected.checkpoint_version_ordinal,
    )
    request = records.RuntimeCheckpointSelectionRequest(
        projected.application_generation_id,
        projected.execution_profile_id,
        projected.market_source_profile_id,
        expected,
    )
    successor_proof = records._issue_runtime_checkpoint_selection_proof(
        request,
        proof.application_generation,
        proof.execution_profile,
        proof.market_source_profile,
        expected,
        expected.currentness_head_ordinal,
        expected.checkpoint_version_ordinal + 1,
        proof._selection,
    )
    return loaded, successor_proof


def _loaded_dormant_checkpoint() -> tuple[
    checkpoint_codec.RuntimeCheckpointEnvelope,
    records.RuntimeCheckpointSelectionProof,
]:
    return _loaded_checkpoint(checkpoint_fixtures._dormant_projection_inputs())


def test_compact_hydration_requires_loaded_checkpoint_and_fresh_successor_proof() -> (
    None
):
    loaded, proof = _loaded_dormant_checkpoint()

    restored = checkpoint_codec._restore_compact_runtime_checkpoint(loaded, proof)

    assert restored.source_checkpoint is loaded
    assert restored.selection_proof is proof
    assert restored.scope_owners[0].acquisition is None
    assert restored.scope_owners[0].protection is None
    projected = checkpoint_codec._project_runtime_checkpoint(
        proof,
        restored.venue,
        restored.authority,
        restored.scope_owners,
    )
    assert projected.venue.canonical_bytes == loaded.venue.canonical_bytes
    assert projected.authority.canonical_bytes == loaded.authority.canonical_bytes
    assert tuple(item.execution.canonical_bytes for item in projected.scopes) == tuple(
        item.execution.canonical_bytes for item in loaded.scopes
    )


def test_compact_hydration_rejects_projected_stale_or_spliced_inputs() -> None:
    loaded, proof = _loaded_dormant_checkpoint()
    original, book, authority, owners = checkpoint_fixtures._dormant_projection_inputs()
    projected = checkpoint_codec._project_runtime_checkpoint(
        original,
        book,
        authority,
        owners,
    )

    with pytest.raises(ValueError, match="loaded"):
        checkpoint_codec._restore_compact_runtime_checkpoint(projected, proof)
    with pytest.raises(ValueError, match="predecessor"):
        checkpoint_codec._restore_compact_runtime_checkpoint(loaded, original)

    forged = object.__new__(records.RuntimeCheckpointSelectionProof)
    for name in proof.__slots__:
        if name != "__weakref__":
            object.__setattr__(forged, name, getattr(proof, name))
    with pytest.raises(ValueError, match="proof"):
        checkpoint_codec._restore_compact_runtime_checkpoint(loaded, forged)


def test_compact_hydration_restores_payload_owned_manual_authority() -> None:
    loaded, proof = _loaded_checkpoint(checkpoint_fixtures._manual_projection_inputs())

    restored = checkpoint_codec._restore_compact_runtime_checkpoint(loaded, proof)

    projected = checkpoint_codec._project_runtime_checkpoint(
        proof,
        restored.venue,
        restored.authority,
        restored.scope_owners,
    )
    assert projected.authority.canonical_bytes == loaded.authority.canonical_bytes


def test_compact_authority_restores_selected_effect_authorization_and_claim() -> None:
    state, effect_ids = checkpoint_fixtures._authority_state_with_effects()
    selection = checkpoint_fixtures._venue_claim_selection()
    venue_wire, venue_commitment, _ = checkpoint_codec._encode_runtime_checkpoint_venue(
        state.venue, selection
    )
    authority_wire, _, _ = checkpoint_codec._encode_runtime_checkpoint_authority(
        state,
        venue_commitment,
        checkpoint_fixtures._APPLICATION,
        (checkpoint_fixtures._DORMANT_POSITION_SCOPE,),
        effect_ids,
    )

    restored = checkpoint_codec._decode_compact_authority_checkpoint(
        authority_wire,
        venue=state.venue,
        venue_commitment=venue_commitment,
        application_generation_id=checkpoint_fixtures._APPLICATION,
        selected_position_scopes=(checkpoint_fixtures._DORMANT_POSITION_SCOPE,),
        selected_effect_ids=effect_ids,
    )

    reencoded, _, _ = checkpoint_codec._encode_runtime_checkpoint_authority(
        restored,
        checkpoint_codec._checkpoint_row_commitment(
            b"execution-core/m2-venue/state/v1", venue_wire[:-1]
        ),
        checkpoint_fixtures._APPLICATION,
        (checkpoint_fixtures._DORMANT_POSITION_SCOPE,),
        effect_ids,
    )
    assert reencoded == authority_wire


@pytest.mark.parametrize("inactive", (False, True))
def test_compact_authority_restores_acquisition_slot_variants(inactive: bool) -> None:
    state, effect_ids = checkpoint_fixtures._authority_state_with_effects()
    state = checkpoint_fixtures._state_with_acquisition_slot(
        state,
        inactive=inactive,
    )
    selection = checkpoint_fixtures._venue_claim_selection()
    _, venue_commitment, _ = checkpoint_codec._encode_runtime_checkpoint_venue(
        state.venue,
        selection,
    )
    authority_wire, _, _ = checkpoint_codec._encode_runtime_checkpoint_authority(
        state,
        venue_commitment,
        checkpoint_fixtures._APPLICATION,
        (checkpoint_fixtures._DORMANT_POSITION_SCOPE,),
        effect_ids,
    )

    restored = checkpoint_codec._decode_compact_authority_checkpoint(
        authority_wire,
        venue=state.venue,
        venue_commitment=venue_commitment,
        application_generation_id=checkpoint_fixtures._APPLICATION,
        selected_position_scopes=(checkpoint_fixtures._DORMANT_POSITION_SCOPE,),
        selected_effect_ids=effect_ids,
    )

    reencoded, _, _ = checkpoint_codec._encode_runtime_checkpoint_authority(
        restored,
        venue_commitment,
        checkpoint_fixtures._APPLICATION,
        (checkpoint_fixtures._DORMANT_POSITION_SCOPE,),
        effect_ids,
    )
    assert reencoded == authority_wire


def _selected_execution_rows() -> tuple[
    position._M2ExecutionState,
    tuple[records.RootFillRecord, ...],
    tuple[records.ExecutionFactHeadRecord, ...],
    tuple[records.ExecutionFactRecord, ...],
]:
    source = checkpoint_fixtures._advanced_execution(
        identity.SymbolId("AAPL"),
        9,
        "compact-hydration",
    )
    state = position._m2_execution_state_from_snapshot(source)
    head = source.root_heads.entries[0]
    fact = source.seen_facts.entries[0].fact
    root = records.RootFillRecord(
        1,
        1,
        checkpoint_fixtures._APPLICATION,
        checkpoint_fixtures._EXECUTION_PROFILE,
        identity.AcquisitionGenerationId("ab" * 32),
        fact.root_fill_id,
        1,
        fact.kind.value,
        fact.authority.value,
        fact.scope.side.value,
        head.quantity,
        head.price,
        1,
    )
    current = records.ExecutionFactRecord(
        1,
        1,
        checkpoint_fixtures._APPLICATION,
        checkpoint_fixtures._EXECUTION_PROFILE,
        1,
        fact.key.source_event_id,
        fact.scope.order_id,
        fact.scope.side.value,
        fact.kind.value,
        fact.authority.value,
        head.quantity,
        head.price,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        1,
    )
    return state, (root,), (records.ExecutionFactHeadRecord(1, 1, 1),), (current,)


def test_compact_execution_restores_current_roots_without_seen_history() -> None:
    state, roots, heads, facts = _selected_execution_rows()

    restored = checkpoint_codec._restore_compact_execution_from_selected_rows(
        state,
        scope_id=1,
        roots=roots,
        fact_heads=heads,
        current_facts=facts,
    )

    assert restored.position.raw_quantity == state.raw_quantity
    assert restored.position.cost_basis == state.cost_basis
    assert restored.root_heads.count == state.root_count
    assert restored.root_heads.entries[0].current_source_event_id == (
        facts[0].source_event_id
    )
    assert restored.seen_facts.count == 0

    with pytest.raises(ValueError, match="incomplete"):
        checkpoint_codec._restore_compact_execution_from_selected_rows(
            state,
            scope_id=1,
            roots=roots,
            fact_heads=heads,
            current_facts=(),
        )
