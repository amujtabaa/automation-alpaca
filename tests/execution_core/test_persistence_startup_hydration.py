from __future__ import annotations

import pytest

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
