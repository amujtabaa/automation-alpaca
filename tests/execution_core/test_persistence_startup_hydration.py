from __future__ import annotations

from copy import copy
from dataclasses import replace

import pytest

from app.execution_core import acquisition
from app.execution_core import authority
from app.execution_core import fills
from app.execution_core import identity
from app.execution_core import position
from app.execution_core import protection
from app.execution_core import values
from app.execution_core import venue
from app.execution_core.persistence import checkpoint_codec
from app.execution_core.persistence import records
import test_persistence_runtime_checkpoint_pure as checkpoint_fixtures
from tests.execution_core import test_acquisition as acquisition_fixtures
from tests.execution_core import test_authority as authority_fixtures
from tests.execution_core import test_protection as protection_fixtures


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


def _active_acquisition_projection_inputs() -> tuple[
    records.RuntimeCheckpointSelectionProof,
    venue.VenueRecoveryBook,
    object,
    tuple[checkpoint_codec._RuntimeCheckpointScopeOwners, ...],
]:
    book, authority_state = checkpoint_fixtures._empty_owners()
    position_scope = checkpoint_fixtures._DORMANT_POSITION_SCOPE
    execution = position.ExecutionSnapshot.flat(position_scope)
    book = venue._m2_restore_compact_venue_book(
        scope=book.scope,
        account_authority_epoch=0,
        unresolved_account_execution_reconciliation_count=0,
        execution_registry_count=execution.seen_facts.count,
        execution_registry_commitment=execution.seen_facts.commitment,
        registry_transition_head_commitment=execution.reconciliation_transition_head,
        authority_epochs=(),
        effects=(),
        claims=(),
        owners=(),
        acquisition_correlations=(),
        closure_heads=(),
        economic_high_waters=(),
        human_coverages=(),
        broker_coverages=(),
        coverage_provenances=(),
        reconciliations=(),
        execution_reconciliations=(),
        bootstrap_targets=(),
        execution_snapshots=(execution,),
        protection_cursors=(),
    )
    authority_state = copy(authority_state)
    object.__setattr__(authority_state, "venue", book)
    venue_context = book.project_acquisition_context(execution, position_scope)
    session_id = identity.SessionId("compact-active-session")
    stream_generation = identity.MarketStreamGenerationId("cd" * 32)
    protection_mandate = protection_fixtures._mandate(
        protection,
        position_scope=position_scope,
        session_id=session_id,
        stream_generation=stream_generation,
    )
    mandate = acquisition_fixtures._approved_acquisition_mandate(
        position_scope=position_scope,
        session_id=session_id,
        protection_mandate=protection_mandate,
        label="compact-active",
    )
    assert type(mandate) is acquisition.AcquisitionMandate
    genesis = acquisition._acquisition_controller_genesis_head(
        checkpoint_fixtures._APPLICATION,
        position_scope,
    )
    compatibility = (
        mandate.protection_mandate.emergency_recovery_compatibility.commitment
    )
    generation_id = acquisition._derive_acquisition_generation_id(
        application_generation_id=checkpoint_fixtures._APPLICATION,
        position_scope=position_scope,
        successor_ordinal=0,
        dual_mandate_binding_commitment=mandate.binding.commitment,
        predecessor_or_genesis_head_commitment=genesis,
        emergency_recovery_compatibility_commitment=compatibility,
    )
    binding = acquisition._new_generation_binding_view(
        generation_id=generation_id,
        application_generation_id=checkpoint_fixtures._APPLICATION,
        position_scope=position_scope,
        successor_ordinal=0,
        dual_mandate_binding_commitment=mandate.binding.commitment,
        predecessor_or_genesis_head_commitment=genesis,
        emergency_recovery_compatibility_commitment=compatibility,
    )
    generation = acquisition._new_generation_record_view(
        binding=binding,
        economics_head_commitment=acquisition._initial_generation_economics_head(
            binding
        ),
        serving_class=acquisition.GenerationServingClass.LIVE,
        closure_summary_commitment=acquisition._initial_generation_closure_summary(
            binding
        ),
    )
    controller = acquisition._new_symbol_acquisition_controller(
        application_generation_id=checkpoint_fixtures._APPLICATION,
        position_scope=position_scope,
        controller_head=genesis,
        successor_ordinal=0,
        live_generation_id=generation_id,
        recovery_class=acquisition.AcquisitionRecoveryClass.NORMAL,
        scope_execution_commitment=venue_context.scope_execution_commitment,
        venue_commitment=venue_context.commitment,
        authority_context_commitment=bytes.fromhex("a1" * 32),
        protection_commitment=None,
        binding_commitment=mandate.binding.commitment,
        compatibility_commitment=compatibility,
    )
    acquisition_state = acquisition._m2_restore_compact_acquisition_controller(
        controller=controller,
        mandate=mandate,
        generation_records=(generation,),
        stream_routes=((stream_generation, generation_id),),
        lineage_routes=(),
    )
    selection = records._RuntimeCheckpointSelectionSet(
        scopes=(
            records.ScopeRecord(
                1,
                checkpoint_fixtures._APPLICATION,
                checkpoint_fixtures._EXECUTION_PROFILE,
                position_scope.symbol_id,
            ),
        ),
        controllers=(
            records.SymbolControllerRecord(
                1,
                checkpoint_fixtures._APPLICATION,
                checkpoint_fixtures._EXECUTION_PROFILE,
                generation_id,
                0,
                "ACTIVE",
                0,
                1,
                compatibility.hex(),
            ),
        ),
        protection_authorities=(
            records.ProtectionAuthorityRecord(
                1,
                "DORMANT",
                None,
                None,
                None,
                None,
                None,
                None,
                0,
                "aa" * 32,
                1,
            ),
        ),
        live_generations=(
            records.AcquisitionGenerationRecord(
                generation_id,
                1,
                "LIVE",
                0,
                None,
                mandate.binding.commitment.hex(),
                compatibility.hex(),
            ),
        ),
        live_generation_current=(
            records.AcquisitionGenerationCurrentRecord(
                generation_id,
                1,
                0,
                0,
                0,
            ),
        ),
        unresolved_generations=(),
        unresolved_generation_current=(),
        effects=(),
        owners=(),
        claims=(),
        acceptance_sets=(),
        evidence=(),
        closure_heads=(),
        root_routes=(),
        roots=(),
        fact_heads=(),
        current_facts=(),
        streams=(
            records.MarketStreamAuthorityRecord(
                stream_generation,
                1,
                checkpoint_fixtures._APPLICATION,
                generation_id,
                mandate.binding.commitment.hex(),
                checkpoint_fixtures._MARKET_PROFILE,
                session_id,
                mandate.protection_mandate.evidence_policy.sequence_mode.value,
            ),
        ),
        cursors=(),
        owner_effect_absences=(),
        claim_effect_absences=(),
        acceptance_effect_absences=(),
        evidence_acceptance_absences=(),
        closure_owner_absences=(),
        route_owner_absences=(),
        fact_head_root_absences=(),
        current_fact_root_absences=(),
        stream_generation_absences=(),
        cursor_stream_absences=(),
        query_row_counts=(1,) * 13,
    )
    proof = checkpoint_fixtures._selection_proof(selection=selection)
    owners = (
        checkpoint_codec._RuntimeCheckpointScopeOwners(
            1,
            acquisition_state,
            execution,
            None,
        ),
    )
    return proof, book, authority_state, owners


def _active_claimed_projection_inputs() -> tuple[
    records.RuntimeCheckpointSelectionProof,
    venue.VenueRecoveryBook,
    object,
    tuple[checkpoint_codec._RuntimeCheckpointScopeOwners, ...],
]:
    """Build one genuine active owner set with a claimed unresolved effect."""

    base_proof, base_book, base_authority, base_owners = (
        _active_acquisition_projection_inputs()
    )
    source_acquisition = base_owners[0].acquisition
    assert source_acquisition is not None
    execution = base_owners[0].execution
    effect_id = identity.EffectId("effect-1")
    authority_state = checkpoint_fixtures._with_extra_authorization(
        base_authority,
        effect_id.value,
        claimed=True,
    )
    authorization = authority_state._effect_authority_by_id.get(
        authority._effect_key(effect_id)
    )
    claim = authority_state._claim_by_effect.get(authority._effect_key(effect_id))
    assert authorization is not None and claim is not None
    request = authorization.request
    effect_scope = venue.VenueEffectScope(
        base_book.scope.generation,
        base_book.scope.broker,
        base_book.scope.environment,
        base_book.scope.account,
        request.effect_id,
        request.request_occurrence_id,
        request.mandate_id,
        request.kind,
        request.client_order_id,
        request.symbol_id,
        request.side,
        request.quantity,
        request.economic_scope,
        request.target_leg_key,
    )
    book = venue._m2_restore_compact_venue_book(
        scope=base_book.scope,
        account_authority_epoch=0,
        unresolved_account_execution_reconciliation_count=0,
        execution_registry_count=execution.seen_facts.count,
        execution_registry_commitment=execution.seen_facts.commitment,
        registry_transition_head_commitment=execution.reconciliation_transition_head,
        authority_epochs=(),
        effects=(
            (
                venue._EffectCurrent(
                    venue.BrokerEffect(
                        effect_scope,
                        venue.BrokerEffectState.DISPATCH_CLAIMED,
                        venue.AcceptanceSetState.OPEN,
                        claim.claim_occurrence_id,
                        None,
                        (),
                    )
                ),
                (),
            ),
        ),
        claims=(venue.DispatchClaim(effect_scope, claim.claim_occurrence_id),),
        owners=(),
        acquisition_correlations=(),
        closure_heads=(),
        economic_high_waters=(),
        human_coverages=(),
        broker_coverages=(),
        coverage_provenances=(),
        reconciliations=(),
        execution_reconciliations=(),
        bootstrap_targets=(),
        execution_snapshots=(execution,),
        protection_cursors=(),
    )
    authority_state = copy(authority_state)
    object.__setattr__(authority_state, "venue", book)
    venue_context = book.project_acquisition_context(
        execution,
        source_acquisition.position_scope,
    )
    authority_context = authority.project_acquisition_authority_context(
        authority_state,
        execution,
        venue_context,
    )
    source_controller = source_acquisition._controller
    generation_id = source_controller.live_generation_id
    assert generation_id is not None
    generation = source_acquisition.registry.record(generation_id)
    assert generation is not None
    controller = acquisition._new_symbol_acquisition_controller(
        application_generation_id=source_controller.application_generation_id,
        position_scope=source_controller.position_scope,
        controller_head=source_controller.controller_head,
        successor_ordinal=source_controller.successor_ordinal,
        live_generation_id=generation_id,
        recovery_class=source_controller.recovery_class,
        scope_execution_commitment=venue_context.scope_execution_commitment,
        venue_commitment=venue_context.commitment,
        authority_context_commitment=authority_context.authority_commitment,
        protection_commitment=None,
        binding_commitment=source_controller._binding_commitment,
        compatibility_commitment=source_controller._compatibility_commitment,
    )
    acquisition_state = acquisition._m2_restore_compact_acquisition_controller(
        controller=controller,
        mandate=source_acquisition._mandate,
        generation_records=(generation,),
        stream_routes=(
            (
                source_acquisition._mandate.protection_mandate.evidence_policy.stream_generation,
                generation_id,
            ),
        ),
        lineage_routes=(
            (
                acquisition.GenerationRouteKind.REQUEST,
                identity.RequestOccurrenceId("req-effect-1"),
                generation_id,
            ),
            (
                acquisition.GenerationRouteKind.EFFECT,
                effect_id,
                generation_id,
            ),
        ),
    )

    selected_generation = base_proof._selection.live_generations[0]
    selected_controller = replace(
        base_proof._selection.controllers[0],
        aggregate_quantity=execution.position.raw_quantity,
    )
    effect_selection = checkpoint_fixtures._venue_claim_selection()
    selected_effect = replace(
        effect_selection.effects[0],
        application_generation_id=base_proof.request.application_generation_id,
        execution_profile_id=base_proof.request.execution_profile_id,
        acquisition_generation_id=selected_generation.acquisition_generation_id,
        generation_mandate_commitment_sha256=(
            selected_generation.mandate_commitment_sha256
        ),
        expected_controller_head_ordinal=(selected_controller.currentness_head_ordinal),
        expected_protection_version_ordinal=(
            base_proof._selection.protection_authorities[0].version_ordinal
        ),
        authority_class=(
            base_proof._selection.protection_authorities[0].authority_class
        ),
    )
    selected_claim = replace(
        effect_selection.claims[0],
        effect_id=selected_effect.effect_id,
        execution_profile_id=selected_effect.execution_profile_id,
    )
    selection = replace(
        base_proof._selection,
        controllers=(selected_controller,),
        effects=(selected_effect,),
        claims=(selected_claim,),
    )
    proof = checkpoint_fixtures._selection_proof(selection=selection)
    owners = (
        checkpoint_codec._RuntimeCheckpointScopeOwners(
            1,
            acquisition_state,
            execution,
            None,
        ),
    )
    return proof, book, authority_state, owners


def test_compact_hydration_restores_one_active_claimed_effect() -> None:
    proof, book, authority_state, owners = _active_claimed_projection_inputs()
    projected = checkpoint_codec._project_runtime_checkpoint(
        proof,
        book,
        authority_state,  # type: ignore[arg-type]
        owners,
    )
    loaded = checkpoint_codec._decode_runtime_checkpoint(
        checkpoint_codec.encode_runtime_checkpoint(projected),
        bytes.fromhex("31" * 32),
    )
    head = records.KernelCheckpointRecord(
        projected.application_generation_id,
        projected.currentness_head_ordinal,
        projected.payload_sha256,
        projected.checkpoint_version_ordinal,
    )
    successor = records._issue_runtime_checkpoint_selection_proof(
        records.RuntimeCheckpointSelectionRequest(
            projected.application_generation_id,
            projected.execution_profile_id,
            projected.market_source_profile_id,
            head,
        ),
        proof.application_generation,
        proof.execution_profile,
        proof.market_source_profile,
        head,
        head.currentness_head_ordinal,
        head.checkpoint_version_ordinal + 1,
        proof._selection,
    )

    restored = checkpoint_codec._restore_compact_runtime_checkpoint(
        loaded,
        successor,
    )

    assert restored.scope_owners[0].acquisition is not None
    assert restored.scope_owners[0].execution.position.raw_quantity == 0
    effect = restored.venue._current_effect(identity.EffectId("effect-1"))
    assert effect is not None
    assert effect.state is venue.BrokerEffectState.DISPATCH_CLAIMED
    assert effect.claim_occurrence_id == identity.ClaimOccurrenceId(
        "occurrence-effect-1"
    )


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


def test_compact_hydration_authenticates_and_rebinds_active_acquisition() -> None:
    proof, _book, _authority, owners = _active_acquisition_projection_inputs()
    source = owners[0].acquisition
    assert source is not None
    wire, _ = checkpoint_codec._encode_runtime_checkpoint_acquisition(
        source,
        proof._selection,
        1,
    )

    restored = checkpoint_codec._decode_source_acquisition_checkpoint(
        wire,
        selection_proof=proof,
        scope_id=1,
    )
    rebound = acquisition._m2_rebind_compact_acquisition_controller(
        restored,
        scope_execution_commitment=bytes.fromhex("b1" * 32),
        venue_commitment=bytes.fromhex("b2" * 32),
        protection_commitment=bytes.fromhex("b3" * 32),
    )

    assert acquisition._controller_state_is_authentic(restored)
    assert restored._controller.live_generation_id == (
        proof._selection.live_generations[0].acquisition_generation_id
    )
    assert rebound.registry is restored.registry
    assert rebound.lineage is restored.lineage
    assert rebound.scope_execution_commitment == bytes.fromhex("b1" * 32)
    assert rebound.venue_commitment == bytes.fromhex("b2" * 32)
    assert rebound.protection_commitment == bytes.fromhex("b3" * 32)


def test_compact_hydration_authenticates_and_rebinds_active_protection() -> None:
    transition = protection_fixtures._owned_fill_transition(
        label="compact-active-protection"
    )
    mandate, _projection, state = protection_fixtures._start(
        protection,
        transition,
        establish_baseline=False,
    )
    source_execution = transition.execution
    source_execution_state = position._m2_execution_state_from_snapshot(
        source_execution
    )
    compact_execution = position._m2_restore_compact_execution_snapshot(
        source_execution_state,
        source_execution.root_heads,
        position.SeenFactIndex.empty(source_execution.position.scope),
    )
    generation_id = identity.AcquisitionGenerationId("ab" * 32)
    mandate_commitment = protection._commit_mandate(mandate).hex()
    compatibility = mandate.emergency_recovery_compatibility.commitment.hex()
    controller_head = state._cursor_ordinal
    selection = records._RuntimeCheckpointSelectionSet(
        scopes=(
            records.ScopeRecord(
                1,
                checkpoint_fixtures._APPLICATION,
                checkpoint_fixtures._EXECUTION_PROFILE,
                state.mandate.position_scope.symbol_id,
            ),
        ),
        controllers=(
            records.SymbolControllerRecord(
                1,
                checkpoint_fixtures._APPLICATION,
                checkpoint_fixtures._EXECUTION_PROFILE,
                generation_id,
                state.raw_quantity,
                "ACTIVE",
                controller_head,
                1,
                compatibility,
            ),
        ),
        protection_authorities=(
            records.ProtectionAuthorityRecord(
                1,
                "NORMAL",
                mandate.evidence_policy.stream_generation,
                generation_id,
                mandate_commitment,
                checkpoint_fixtures._MARKET_PROFILE,
                mandate.session_id,
                mandate.evidence_policy.sequence_mode.value,
                controller_head,
                state.commitment.hex(),
                1,
            ),
        ),
        live_generations=(
            records.AcquisitionGenerationRecord(
                generation_id,
                1,
                "LIVE",
                0,
                None,
                mandate_commitment,
                compatibility,
            ),
        ),
        live_generation_current=(
            records.AcquisitionGenerationCurrentRecord(
                generation_id,
                1,
                0,
                0,
                1,
            ),
        ),
        unresolved_generations=(),
        unresolved_generation_current=(),
        effects=(),
        owners=(),
        claims=(),
        acceptance_sets=(),
        evidence=(),
        closure_heads=(),
        root_routes=(),
        roots=(),
        fact_heads=(),
        current_facts=(),
        streams=(
            records.MarketStreamAuthorityRecord(
                mandate.evidence_policy.stream_generation,
                1,
                checkpoint_fixtures._APPLICATION,
                generation_id,
                mandate_commitment,
                checkpoint_fixtures._MARKET_PROFILE,
                mandate.session_id,
                mandate.evidence_policy.sequence_mode.value,
            ),
        ),
        cursors=(),
        owner_effect_absences=(),
        claim_effect_absences=(),
        acceptance_effect_absences=(),
        evidence_acceptance_absences=(),
        closure_owner_absences=(),
        route_owner_absences=(),
        fact_head_root_absences=(),
        current_fact_root_absences=(),
        stream_generation_absences=(),
        cursor_stream_absences=(),
        query_row_counts=(1,) * 13,
    )
    proof = checkpoint_fixtures._selection_proof(selection=selection)
    checkpoint = protection_fixtures._m2_checkpoint_from_state(protection, state)
    wire = checkpoint_codec._encode_m2_protection_checkpoint_component(checkpoint)

    restored = checkpoint_codec._decode_source_protection_checkpoint(
        wire,
        selection_proof=proof,
        scope_id=1,
        position_scope=state.mandate.position_scope,
        compact_execution=compact_execution,
    )

    assert protection._state_is_authentic(restored)
    assert restored.raw_quantity == state.raw_quantity
    assert restored.execution_commitment == compact_execution.commitment
    assert restored.execution_commitment != state.execution_commitment
    assert restored._market_baseline_required == state._market_baseline_required


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


def test_compact_venue_restores_selected_effect_claim_execution_and_cursor() -> None:
    state, _ = checkpoint_fixtures._authority_state_with_effects()
    selection = checkpoint_fixtures._venue_claim_selection()
    venue_wire, _, _ = checkpoint_codec._encode_runtime_checkpoint_venue(
        state.venue,
        selection,
    )
    position_scope = checkpoint_fixtures._DORMANT_POSITION_SCOPE
    execution = state.venue._execution_snapshot_by_scope.get(
        venue._position_scope_index_key(position_scope)
    )
    assert execution is not None
    execution_state = position._m2_execution_state_from_snapshot(execution)

    restored = checkpoint_codec._decode_compact_venue_checkpoint(
        venue_wire,
        selection=selection,
        application_generation_id=checkpoint_fixtures._APPLICATION,
        compact_execution_by_scope={position_scope: execution},
        source_execution_state_by_scope={position_scope: execution_state},
    )

    reencoded, _, _ = checkpoint_codec._encode_runtime_checkpoint_venue(
        restored,
        selection,
    )
    assert reencoded == venue_wire
    with pytest.raises(ValueError, match="execution scope"):
        checkpoint_codec._decode_compact_venue_checkpoint(
            venue_wire,
            selection=selection,
            application_generation_id=checkpoint_fixtures._APPLICATION,
            compact_execution_by_scope={},
            source_execution_state_by_scope={position_scope: execution_state},
        )


def test_compact_venue_restores_active_bootstrap_with_idempotent_cutover() -> None:
    position_scope = checkpoint_fixtures._FIXTURE_POSITION_SCOPE
    source_execution = position.ExecutionSnapshot.flat(position_scope)
    bootstrapped = venue._authority_bootstrap_unbound_target_pair_for_scope(
        venue.VenueRecoveryBook.empty(checkpoint_fixtures._FIXTURE_VENUE_SCOPE),
        source_execution,
        position_scope,
    )
    assert bootstrapped is not None
    book, execution, _ = bootstrapped
    selection = checkpoint_fixtures._dormant_selection()
    venue_wire, _, _ = checkpoint_codec._encode_runtime_checkpoint_venue(
        book,
        selection,
    )
    execution_state = position._m2_execution_state_from_snapshot(execution)

    restored = checkpoint_codec._decode_compact_venue_checkpoint(
        venue_wire,
        selection=selection,
        application_generation_id=checkpoint_fixtures._APPLICATION,
        compact_execution_by_scope={position_scope: execution},
        source_execution_state_by_scope={position_scope: execution_state},
    )

    assert restored._bootstrap_bound_target_pair_matches(execution, position_scope)
    record = restored._bootstrap_bound_target_record(position_scope)
    assert record is not None
    assert (
        record._neutral_checkpoint_proof.source_kind
        is venue._ProtectionTransitionSourceKind.COMPACT_RESTORE
    )
    normalized_wire, _, _ = checkpoint_codec._encode_runtime_checkpoint_venue(
        restored,
        selection,
    )
    replay = checkpoint_codec._decode_compact_venue_checkpoint(
        normalized_wire,
        selection=selection,
        application_generation_id=checkpoint_fixtures._APPLICATION,
        compact_execution_by_scope={position_scope: execution},
        source_execution_state_by_scope={position_scope: execution_state},
    )
    replay_wire, _, _ = checkpoint_codec._encode_runtime_checkpoint_venue(
        replay,
        selection,
    )
    assert replay_wire == normalized_wire


def test_compact_bootstrap_rebinds_an_omitted_registry_history() -> None:
    target_scope = authority_fixtures.EXECUTION.position.scope
    source_scope = fills.PositionScope(
        authority_fixtures.BROKER,
        authority_fixtures.ENVIRONMENT,
        authority_fixtures.ACCOUNT,
        authority_fixtures.OTHER_SYMBOL,
    )
    source_book, source_execution = authority_fixtures._apply_closed_sell_fill(
        venue.VenueRecoveryBook.empty(authority_fixtures.VENUE_SCOPE),
        position.ExecutionSnapshot.flat(source_scope),
        label="compact-bootstrap-source-history",
        leg_key=identity.VenueLegKey(
            authority_fixtures.BROKER,
            authority_fixtures.ENVIRONMENT,
            authority_fixtures.ACCOUNT,
            identity.OrderId("compact-bootstrap-source-leg"),
        ),
        symbol_id=authority_fixtures.OTHER_SYMBOL,
    )
    bootstrapped = venue._authority_bootstrap_unbound_target_pair_for_scope(
        source_book,
        source_execution,
        target_scope,
    )
    assert bootstrapped is not None
    source_book, source_target, _ = bootstrapped
    source_record = source_book._bootstrap_bound_target_record(target_scope)
    source_cursor = source_book._protection_cursor_by_scope.get(
        venue._position_scope_index_key(target_scope)
    )
    assert source_record is not None and source_cursor is not None
    source_state = position._m2_execution_state_from_snapshot(source_target)
    compact_target = position._m2_restore_compact_execution_snapshot(
        source_state,
        source_target.root_heads,
        fills.SeenFactIndex.empty(target_scope),
    )
    assert compact_target.commitment != source_target.commitment

    restored = venue._m2_restore_compact_venue_book(
        scope=source_book.scope,
        account_authority_epoch=0,
        unresolved_account_execution_reconciliation_count=0,
        execution_registry_count=compact_target.seen_facts.count,
        execution_registry_commitment=compact_target.seen_facts.commitment,
        registry_transition_head_commitment=None,
        authority_epochs=(),
        effects=(),
        claims=(),
        owners=(),
        acquisition_correlations=(),
        closure_heads=(),
        economic_high_waters=(),
        human_coverages=(),
        broker_coverages=(),
        coverage_provenances=(),
        reconciliations=(),
        execution_reconciliations=(),
        bootstrap_targets=(source_record,),
        execution_snapshots=(compact_target,),
        protection_cursors=((target_scope, source_cursor),),
    )

    compact_record = restored._bootstrap_bound_target_record(target_scope)
    assert compact_record is not None
    assert compact_record.target_execution_commitment == compact_target.commitment
    assert (
        compact_record._neutral_checkpoint_proof.predecessor_execution_commitment
        == source_target.commitment
    )
    assert restored._bootstrap_bound_target_pair_matches(compact_target, target_scope)


@pytest.mark.parametrize(
    "record",
    (
        checkpoint_fixtures._fixture_resolved_registry_outcome("resolved-input"),
        checkpoint_fixtures._fixture_unresolved_registry_outcome("unresolved-input"),
    ),
)
def test_compact_execution_reconciliation_round_trips_exact_union(
    record: object,
) -> None:
    row = (
        checkpoint_codec._encode_runtime_checkpoint_venue_execution_reconciliation_row(
            record
        )
    )

    restored = checkpoint_codec._decode_compact_venue_execution_reconciliation_row(row)

    assert restored == record


def test_compact_consumed_bootstrap_round_trips_exact_effect_binding() -> None:
    position_scope = checkpoint_fixtures._FIXTURE_POSITION_SCOPE
    bootstrapped = venue._authority_bootstrap_unbound_target_pair_for_scope(
        venue.VenueRecoveryBook.empty(checkpoint_fixtures._FIXTURE_VENUE_SCOPE),
        position.ExecutionSnapshot.flat(position_scope),
        position_scope,
    )
    assert bootstrapped is not None
    book, _, _ = bootstrapped
    active = book._bootstrap_bound_target_record(position_scope)
    assert active is not None
    effect = venue.BrokerEffect(
        venue.VenueEffectScope(
            checkpoint_fixtures._APPLICATION,
            position_scope.broker,
            position_scope.environment,
            position_scope.account,
            identity.EffectId("compact-bootstrap-effect"),
            identity.RequestOccurrenceId("compact-bootstrap-occurrence"),
            identity.MandateId("compact-bootstrap-mandate"),
            venue.EffectKind.SUBMIT,
            identity.ClientOrderId("compact-bootstrap-client"),
            position_scope.symbol_id,
            checkpoint_fixtures.ExecutionSide.BUY,
            values.Quantity(1),
            b"compact-bootstrap-economic-scope",
        )
    )
    request_input_id = identity.VenueInputId("compact-bootstrap-request")
    consumed = venue._new_consumed_bootstrap_bound_target_record(
        active_record=active,
        effect=effect,
        request_input_id=request_input_id,
    )
    row, _ = checkpoint_codec._encode_runtime_checkpoint_venue_bootstrap_target(
        consumed
    )

    restored = checkpoint_codec._decode_compact_venue_bootstrap_target(
        row,
        effects_by_id={effect.effect_id: effect},
    )

    reencoded, _ = checkpoint_codec._encode_runtime_checkpoint_venue_bootstrap_target(
        restored
    )
    assert reencoded == row


def test_compact_venue_restores_owner_closure_and_economic_high_water() -> None:
    state, _ = checkpoint_fixtures._authority_state_with_effects()
    position_scope = checkpoint_fixtures._DORMANT_POSITION_SCOPE
    execution = state.venue._execution_snapshot_by_scope.get(
        venue._position_scope_index_key(position_scope)
    )
    assert execution is not None
    effect = state.venue._effect_by_id.get(
        venue._effect_index_key(identity.EffectId("effect-1"))
    )
    assert effect is not None
    leg_key = identity.VenueLegKey(
        identity.BrokerId("paper"),
        identity.EnvironmentId("paper"),
        identity.AccountId("account"),
        identity.OrderId("owner-order-1"),
    )
    book = checkpoint_fixtures._book_with_owner_leg(
        state.venue,
        leg_key,
        effect.effect.scope,
        with_attempt=False,
    )
    closure = venue.VenueTerminalClosure(
        leg_key,
        identity.ClosureId("closure-current"),
        3,
        None,
        venue.VenueAttemptState.WORKING,
        values.Quantity(2),
        values.Quantity(2),
        identity.EvidenceReference("closure-evidence"),
        venue.VenueClosureKind.BROKER_TERMINAL,
        identity.VenueInputId("closure-input"),
    )
    book_with_closure = copy(book)
    object.__setattr__(
        book_with_closure,
        "_closure_head_by_leg",
        book._closure_head_by_leg.insert_new(
            venue._leg_index_key(leg_key),
            closure,
            venue._closure_commitment(closure),
        ),
    )
    book_with_current = checkpoint_fixtures._book_with_int_index(
        book_with_closure,
        "_economic_high_water_by_leg",
        venue._leg_index_key(leg_key),
        2,
        b"execution-core/venue-economic-high-water/v1",
    )
    selection = checkpoint_fixtures._closure_selection(
        checkpoint_fixtures._owner_selection(
            checkpoint_fixtures._venue_claim_selection(),
            "owner-order-1",
        ),
        closure,
    )
    venue_wire, _, _ = checkpoint_codec._encode_runtime_checkpoint_venue(
        book_with_current,
        selection,
    )
    execution_state = position._m2_execution_state_from_snapshot(execution)

    restored = checkpoint_codec._decode_compact_venue_checkpoint(
        venue_wire,
        selection=selection,
        application_generation_id=checkpoint_fixtures._APPLICATION,
        compact_execution_by_scope={position_scope: execution},
        source_execution_state_by_scope={position_scope: execution_state},
    )

    reencoded, _, _ = checkpoint_codec._encode_runtime_checkpoint_venue(
        restored,
        selection,
    )
    assert reencoded == venue_wire
    assert restored.owner(leg_key) is not None
    assert restored.closure_head(leg_key) == closure


@pytest.mark.parametrize("human", (False, True))
def test_compact_venue_restores_current_coverage(human: bool) -> None:
    state, _ = checkpoint_fixtures._authority_state_with_effects()
    position_scope = checkpoint_fixtures._DORMANT_POSITION_SCOPE
    execution = state.venue._execution_snapshot_by_scope.get(
        venue._position_scope_index_key(position_scope)
    )
    assert execution is not None
    effect = state.venue._effect_by_id.get(
        venue._effect_index_key(identity.EffectId("effect-1"))
    )
    assert effect is not None
    book = checkpoint_fixtures._book_with_owner_leg(
        state.venue,
        checkpoint_fixtures._FIXTURE_LEG_KEY,
        effect.effect.scope,
    )
    if human:
        book = checkpoint_fixtures._book_with_human_coverage(book)
    else:
        book = checkpoint_fixtures._book_with_broker_coverage(book)
    selection = checkpoint_fixtures._route_selection(
        checkpoint_fixtures._root_selection(
            checkpoint_fixtures._venue_claim_selection(),
            "root-1",
        )
    )
    venue_wire, _, _ = checkpoint_codec._encode_runtime_checkpoint_venue(
        book,
        selection,
    )
    execution_state = position._m2_execution_state_from_snapshot(execution)

    restored = checkpoint_codec._decode_compact_venue_checkpoint(
        venue_wire,
        selection=selection,
        application_generation_id=checkpoint_fixtures._APPLICATION,
        compact_execution_by_scope={position_scope: execution},
        source_execution_state_by_scope={position_scope: execution_state},
    )

    reencoded, _, _ = checkpoint_codec._encode_runtime_checkpoint_venue(
        restored,
        selection,
    )
    assert reencoded == venue_wire
    if human:
        assert len(restored.human_coverages) == 1
    else:
        assert len(restored.broker_coverages) == 1


def test_compact_venue_restores_referenced_unresolved_reconciliation() -> None:
    state, _ = checkpoint_fixtures._authority_state_with_effects()
    position_scope = checkpoint_fixtures._DORMANT_POSITION_SCOPE
    execution = state.venue._execution_snapshot_by_scope.get(
        venue._position_scope_index_key(position_scope)
    )
    assert execution is not None
    effect = state.venue._effect_by_id.get(
        venue._effect_index_key(identity.EffectId("effect-1"))
    )
    assert effect is not None
    book = checkpoint_fixtures._book_with_owner_leg(
        state.venue,
        checkpoint_fixtures._FIXTURE_LEG_KEY,
        effect.effect.scope,
    )
    book = checkpoint_fixtures._book_with_broker_coverage(book)
    reconciliation = checkpoint_fixtures._fixture_fill_reconciliation("input-1")
    book = checkpoint_fixtures._book_with_reconciliations(
        book,
        (("input-1", reconciliation),),
    )
    selection = checkpoint_fixtures._reconciliation_selection()
    venue_wire, _, _ = checkpoint_codec._encode_runtime_checkpoint_venue(
        book,
        selection,
    )
    execution_state = position._m2_execution_state_from_snapshot(execution)

    restored = checkpoint_codec._decode_compact_venue_checkpoint(
        venue_wire,
        selection=selection,
        application_generation_id=checkpoint_fixtures._APPLICATION,
        compact_execution_by_scope={position_scope: execution},
        source_execution_state_by_scope={position_scope: execution_state},
    )

    reencoded, _, _ = checkpoint_codec._encode_runtime_checkpoint_venue(
        restored,
        selection,
    )
    assert reencoded == venue_wire
    assert restored.reconciliations == (reconciliation,)


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


def _selected_execution_rows_from(
    source: position.ExecutionSnapshot,
) -> tuple[
    position._M2ExecutionState,
    tuple[records.RootFillRecord, ...],
    tuple[records.ExecutionFactHeadRecord, ...],
    tuple[records.ExecutionFactRecord, ...],
]:
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


def _selected_execution_rows() -> tuple[
    position._M2ExecutionState,
    tuple[records.RootFillRecord, ...],
    tuple[records.ExecutionFactHeadRecord, ...],
    tuple[records.ExecutionFactRecord, ...],
]:
    return _selected_execution_rows_from(
        checkpoint_fixtures._advanced_execution(
            identity.SymbolId("AAPL"),
            9,
            "compact-hydration",
        )
    )


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
