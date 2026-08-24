"""Pure R13 checkpoint carrier, wire, binding, and authenticity controls."""

from __future__ import annotations

import ast
from copy import copy
from copy import deepcopy
import hashlib
import inspect
import json
import struct
from typing import Any

import pytest

from decimal import Decimal

from app.execution_core import authority, identity, profiles, values, venue
from app.execution_core.fills import (
    BrokerFillFact,
    BrokerTradeCorrectFact,
    ExecutionFactKey,
    ExecutionScope,
    ExecutionSide,
    PositionScope,
)
from app.execution_core.position import ExecutionSnapshot, apply_broker_execution_fact
from app.execution_core.persistence import (
    checkpoint_codec,
    operations as _operations,
    records,
)


_EXECUTION_PROFILE = "11" * 32
_MARKET_PROFILE = "22" * 32
_LOAD_BINDING = bytes.fromhex("33" * 32)
_SELECTION_BINDING = bytes.fromhex("44" * 32)
_APPLICATION = identity.ApplicationGenerationId("checkpoint-app")
_DORMANT_POSITION_SCOPE = PositionScope(
    identity.BrokerId("paper"),
    identity.EnvironmentId("paper"),
    identity.AccountId("account"),
    identity.SymbolId("AAPL"),
)


def _canonical(value: list[object]) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _contract_k(domain: str, row: list[object]) -> str:
    """Independent literal K(domain,row) oracle for R19 known answers."""

    domain_bytes = domain.encode("ascii")
    row_bytes = _canonical(row)
    preimage = (
        struct.pack(">I", len(domain_bytes))
        + domain_bytes
        + struct.pack(">Q", len(row_bytes))
        + row_bytes
    )
    return hashlib.sha256(preimage).hexdigest()


def _dormant_wires(*, nonempty: bool) -> tuple[list[object], list[object]]:
    generation_rows: list[object] = []
    generation_current_rows: list[object] = []
    stream_rows: list[object] = []
    cursor_rows: list[object] = []
    lineage_rows: list[object] = []
    if nonempty:
        generation = ["1", "acquisition_generation_id", ["ab" * 32]]
        stream = ["1", "market_stream_generation_id", ["cd" * 32]]
        application = ["1", "application_generation_id", ["checkpoint-app"]]
        session = ["1", "session_id", ["retired-session"]]
        effect = ["1", "effect_id", ["retired-effect"]]
        generation_rows.append(
            [
                "m2.acquisition.DormantGeneration/v1",
                generation,
                1,
                "RETIRED",
                4,
                ["1", "acquisition_generation_id", ["ef" * 32]],
                "11" * 32,
                "22" * 32,
            ]
        )
        generation_current_rows.append(
            [
                "m2.acquisition.DormantGenerationCurrent/v1",
                generation,
                1,
                9,
                2,
                0,
            ]
        )
        stream_rows.append(
            [
                "m2.acquisition.DormantMarketStream/v1",
                stream,
                1,
                application,
                generation,
                "11" * 32,
                _MARKET_PROFILE,
                session,
                "FIXED_ORDINAL",
            ]
        )
        cursor_rows.append(
            [
                "m2.acquisition.DormantMarketCursor/v1",
                stream,
                1,
                application,
                generation,
                "11" * 32,
                _MARKET_PROFILE,
                session,
                "FIXED_ORDINAL",
                8,
                9,
            ]
        )
        lineage_without_commitment: list[object] = [
            "m2.acquisition.DormantLineageRoute/v1",
            ["m1.acquisition.GenerationRouteKind", "EFFECT"],
            effect,
            generation,
            ["m2.acquisition.LineageEffectSource/v1", effect],
            "33" * 32,
        ]
        lineage_rows.append(
            [
                *lineage_without_commitment,
                _contract_k(
                    "execution-core/m2-acquisition/dormant-lineage-route/v1",
                    lineage_without_commitment,
                ),
            ]
        )

    generations = [
        "m2.acquisition.DormantGenerations/v1",
        len(generation_rows),
        generation_rows,
    ]
    generation_currents = [
        "m2.acquisition.DormantGenerationCurrents/v1",
        len(generation_current_rows),
        generation_current_rows,
    ]
    streams = ["m2.acquisition.DormantMarketStreams/v1", len(stream_rows), stream_rows]
    cursors = ["m2.acquisition.DormantMarketCursors/v1", len(cursor_rows), cursor_rows]
    lineage = [
        "m2.acquisition.DormantLineageRoutes/v1",
        len(lineage_rows),
        lineage_rows,
    ]
    registry_row = [
        "m2.acquisition.DormantRegistry/v2",
        generations,
        generation_currents,
        streams,
        cursors,
    ]
    registry_commitment = _contract_k(
        "execution-core/m2-acquisition/dormant-registry/v2", registry_row
    )
    lineage_commitment = _contract_k(
        "execution-core/m2-acquisition/dormant-lineage/v2", lineage
    )
    acquisition_without_commitment: list[object] = [
        "m2.acquisition.Dormant/v2",
        ["1", "application_generation_id", ["checkpoint-app"]],
        [
            "m1.fills.PositionScope/v1",
            ["1", "broker_id", ["paper"]],
            ["1", "environment_id", ["paper"]],
            ["1", "account_id", ["account"]],
            ["1", "symbol_id", ["AAPL"]],
        ],
        1,
        0,
        "DORMANT",
        7,
        3,
        "ee" * 32,
        generations,
        generation_currents,
        streams,
        cursors,
        lineage,
        registry_commitment,
        lineage_commitment,
    ]
    acquisition = [
        *acquisition_without_commitment,
        _contract_k(
            "execution-core/m2-acquisition/dormant/v2",
            acquisition_without_commitment,
        ),
    ]
    protection_without_commitment: list[object] = [
        "m2.protection.Dormant/v1",
        1,
        "DORMANT",
        7,
        "aa" * 32,
        3,
    ]
    protection = [
        *protection_without_commitment,
        _contract_k(
            "execution-core/m2-protection/dormant/v1",
            protection_without_commitment,
        ),
    ]
    return acquisition, protection


def _outer_payload(*, scopes: list[object] | None = None) -> bytes:
    rows = [] if scopes is None else scopes
    return _canonical(
        [
            1,
            "m2.runtime-checkpoint/v1",
            ["1", "application_generation_id", ["checkpoint-app"]],
            _EXECUTION_PROFILE,
            _MARKET_PROFILE,
            7,
            3,
            ["m2.venue.State/v1", *([None] * 22)],
            ["m2.authority.Checkpoint/v1", *([None] * 13)],
            ["m2.runtime-checkpoint.scopes/v1", len(rows), rows],
        ]
    )


def _selection_proof(
    scopes: tuple[records.ScopeRecord, ...] = (),
    *,
    selection: records._RuntimeCheckpointSelectionSet | None = None,
) -> records.RuntimeCheckpointSelectionProof:
    if selection is None:
        selection = records._RuntimeCheckpointSelectionSet(
            scopes=scopes,
            controllers=(),
            protection_authorities=(),
            live_generations=(),
            live_generation_current=(),
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
            streams=(),
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
            query_row_counts=(0,) * 13,
        )
    request = records.RuntimeCheckpointSelectionRequest(
        _APPLICATION,
        _EXECUTION_PROFILE,
        _MARKET_PROFILE,
        None,
    )
    execution_profile = profiles.ExecutionConnectionProfile(
        connection_profile_id=_EXECUTION_PROFILE,
        application_generation=_APPLICATION.value,
        broker_provider="ALPACA",
        environment_class="PAPER",
        account_identity="55" * 32,
        trade_command_origin="https://trade.example.com",
        order_query_origin="https://query.example.com",
        order_event_origin="https://events.example.com",
        credential_handle_fingerprint="66" * 32,
        adapter_contract_version="1.0.0",
        capability_profile_sha256="77" * 32,
        deployment_identity="88" * 32,
    )
    market_profile = profiles.MarketDataSourceProfile(
        market_source_profile_id=_MARKET_PROFILE,
        provider="ALPACA",
        environment_or_feed="iex-feed",
        source_origin="https://feed.example.com",
        entitlement_class="IEX",
        normalization_contract_version="1.0.0",
        data_capability_profile_sha256="99" * 32,
    )
    return records._issue_runtime_checkpoint_selection_proof(
        request,
        records.ApplicationGenerationRecord(
            _APPLICATION, _EXECUTION_PROFILE, _MARKET_PROFILE, 1
        ),
        execution_profile,
        market_profile,
        None,
        0,
        1,
        selection,
    )


def _dormant_selection(
    *,
    controller_quantity: int = 0,
    controller_head: int = 7,
    protection_head: int | None = None,
    partial_protection: bool = False,
    active_generation: bool = False,
) -> records._RuntimeCheckpointSelectionSet:
    generation = identity.AcquisitionGenerationId("ab" * 32)
    scope = records.ScopeRecord(
        1, _APPLICATION, _EXECUTION_PROFILE, identity.SymbolId("AAPL")
    )
    controller = records.SymbolControllerRecord(
        1,
        _APPLICATION,
        _EXECUTION_PROFILE,
        generation if active_generation else None,
        controller_quantity,
        "DORMANT",
        controller_head,
        3,
        "ee" * 32,
    )
    protection = records.ProtectionAuthorityRecord(
        1,
        "DORMANT",
        identity.MarketStreamGenerationId("cd" * 32) if partial_protection else None,
        None,
        None,
        None,
        None,
        None,
        controller_head if protection_head is None else protection_head,
        "aa" * 32,
        3,
    )
    live_generations: tuple[records.AcquisitionGenerationRecord, ...] = ()
    live_current: tuple[records.AcquisitionGenerationCurrentRecord, ...] = ()
    if active_generation:
        live_generations = (
            records.AcquisitionGenerationRecord(
                generation, 1, "LIVE", 1, None, "11" * 32, "ee" * 32
            ),
        )
        live_current = (
            records.AcquisitionGenerationCurrentRecord(generation, 1, 0, 0, 0),
        )
    return records._RuntimeCheckpointSelectionSet(
        scopes=(scope,),
        controllers=(controller,),
        protection_authorities=(protection,),
        live_generations=live_generations,
        live_generation_current=live_current,
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
        streams=(),
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
        query_row_counts=(1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    )


def _dormant_projection_inputs(
    **selection_changes: object,
) -> tuple[
    records.RuntimeCheckpointSelectionProof,
    venue.VenueRecoveryBook,
    authority.ExecutionAuthorityState,
    tuple[checkpoint_codec._RuntimeCheckpointScopeOwners, ...],
]:
    selection = _dormant_selection(**selection_changes)  # type: ignore[arg-type]
    proof = _selection_proof(selection=selection)
    book, state = _empty_owners()
    execution = ExecutionSnapshot.flat(_DORMANT_POSITION_SCOPE)
    owners = (
        checkpoint_codec._RuntimeCheckpointScopeOwners(
            1,
            None,  # type: ignore[arg-type]
            execution,
            None,  # type: ignore[arg-type]
        ),
    )
    return proof, book, state, owners


def _empty_owners(
    account: str = "account",
) -> tuple[venue.VenueRecoveryBook, authority.ExecutionAuthorityState]:
    scope = venue.VenueScope(
        _APPLICATION,
        identity.BrokerId("paper"),
        identity.EnvironmentId("paper"),
        identity.AccountId(account),
    )
    state = authority.initial_execution_authority_state(scope)
    return state.venue, state


def _valid_empty_payload() -> bytes:
    proof = _selection_proof()
    book, state = _empty_owners()
    return checkpoint_codec.encode_runtime_checkpoint(
        checkpoint_codec._project_runtime_checkpoint(proof, book, state, ())
    )


def test_public_surface_is_exact_and_has_no_sqlite_import() -> None:
    assert checkpoint_codec.__all__ == (
        "InertRuntimeCheckpointComponent",
        "RuntimeCheckpointEnvelope",
        "RuntimeCheckpointScopeCandidate",
        "encode_runtime_checkpoint",
    )
    tree = ast.parse(inspect.getsource(checkpoint_codec))
    imported = {
        alias.name
        for statement in tree.body
        if isinstance(statement, ast.Import)
        for alias in statement.names
    }
    imported_from = {
        statement.module
        for statement in tree.body
        if isinstance(statement, ast.ImportFrom)
    }
    assert "sqlite3" not in imported
    assert "sqlite3" not in imported_from


@pytest.mark.parametrize(
    "carrier",
    (
        checkpoint_codec.InertRuntimeCheckpointComponent,
        checkpoint_codec.RuntimeCheckpointScopeCandidate,
        checkpoint_codec.RuntimeCheckpointEnvelope,
    ),
)
def test_public_inert_carriers_are_constructor_hidden_and_non_subclassable(
    carrier: type[object],
) -> None:
    with pytest.raises(TypeError):
        carrier()
    with pytest.raises(TypeError):
        type("Forged", (carrier,), {})


def test_loaded_decode_is_canonical_registered_and_round_trips_exact_bytes() -> None:
    payload = _valid_empty_payload()

    envelope = checkpoint_codec._decode_runtime_checkpoint(payload, _LOAD_BINDING)

    assert type(envelope) is checkpoint_codec.RuntimeCheckpointEnvelope
    assert envelope.application_generation_id == identity.ApplicationGenerationId(
        "checkpoint-app"
    )
    assert envelope.currentness_head_ordinal == 0
    assert envelope.checkpoint_version_ordinal == 1
    assert envelope._provenance == "LOADED"
    assert envelope._owner_preimage is None
    assert envelope.scopes == ()
    assert envelope.payload_sha256 == hashlib.sha256(payload).hexdigest()
    assert checkpoint_codec.RuntimeCheckpointEnvelope._is_authentic(envelope)
    assert checkpoint_codec.encode_runtime_checkpoint(envelope) is payload


def test_decode_refuses_noncanonical_bytes_wrong_shape_and_scope_order() -> None:
    canonical = _valid_empty_payload()
    spaced = canonical.replace(b",", b", ", 1)
    with pytest.raises(ValueError, match="canonical"):
        checkpoint_codec._decode_runtime_checkpoint(spaced, _LOAD_BINDING)

    wrong_outer = json.loads(canonical)
    wrong_outer.append(None)
    with pytest.raises(ValueError, match="outer envelope"):
        checkpoint_codec._decode_runtime_checkpoint(
            _canonical(wrong_outer), _LOAD_BINDING
        )

    malformed_scopes = json.loads(canonical)
    malformed_scopes[9] = [
        "m2.runtime-checkpoint.scopes/v1",
        2,
        [["m2.runtime-checkpoint.scope/v1"], ["m2.runtime-checkpoint.scope/v1"]],
    ]
    with pytest.raises(ValueError, match="scope row"):
        checkpoint_codec._decode_runtime_checkpoint(
            _canonical(malformed_scopes), _LOAD_BINDING
        )

    zero_version = json.loads(_outer_payload())
    zero_version[6] = 0
    with pytest.raises(ValueError, match="version ordinal must be positive"):
        checkpoint_codec._decode_runtime_checkpoint(
            _canonical(zero_version), _LOAD_BINDING
        )


def test_decode_refuses_profile_alias_bad_binding_and_cross_scope_splice() -> None:
    payload = json.loads(_valid_empty_payload())
    payload[3] = "AA" * 32
    with pytest.raises(ValueError, match="execution profile"):
        checkpoint_codec._decode_runtime_checkpoint(_canonical(payload), _LOAD_BINDING)

    with pytest.raises(ValueError, match="load proof binding"):
        checkpoint_codec._decode_runtime_checkpoint(_valid_empty_payload(), b"short")

    payload = json.loads(_valid_empty_payload())
    payload[7][7][0] = "m2.venue.UnknownRows/v1"
    with pytest.raises(ValueError, match="AuthorityEpochs"):
        checkpoint_codec._decode_runtime_checkpoint(_canonical(payload), _LOAD_BINDING)


def test_forgery_and_post_issuance_mutation_fail_fresh_authenticity() -> None:
    envelope = checkpoint_codec._decode_runtime_checkpoint(
        _valid_empty_payload(), _LOAD_BINDING
    )
    forged = object.__new__(checkpoint_codec.RuntimeCheckpointEnvelope)
    for name in (
        "application_generation_id",
        "execution_profile_id",
        "market_source_profile_id",
        "currentness_head_ordinal",
        "checkpoint_version_ordinal",
        "venue",
        "authority",
        "scopes",
        "canonical_payload_bytes",
        "payload_sha256",
        "_provenance",
        "_selection_binding",
        "_owner_preimage",
        "_binding",
    ):
        object.__setattr__(forged, name, getattr(envelope, name))
    assert not checkpoint_codec.RuntimeCheckpointEnvelope._is_authentic(forged)
    with pytest.raises(ValueError, match="not authentic"):
        checkpoint_codec.encode_runtime_checkpoint(forged)

    object.__setattr__(envelope, "currentness_head_ordinal", 8)
    assert not checkpoint_codec.RuntimeCheckpointEnvelope._is_authentic(envelope)


def test_projected_seam_binds_owner_preimage_and_loaded_bytes_stay_nonserving() -> None:
    canonical = _valid_empty_payload()
    payload = json.loads(canonical)
    envelope = checkpoint_codec._issue_projected_runtime_checkpoint(
        selection_proof_binding=_SELECTION_BINDING,
        application_generation_id=identity.ApplicationGenerationId("checkpoint-app"),
        execution_profile_id=_EXECUTION_PROFILE,
        market_source_profile_id=_MARKET_PROFILE,
        currentness_head_ordinal=0,
        checkpoint_version_ordinal=1,
        venue_wire=payload[7],
        authority_wire=payload[8],
        scope_wires=(),
        venue_owner_commitment=bytes.fromhex("55" * 32),
        authority_owner_commitment=bytes.fromhex("66" * 32),
        scope_owner_commitments=(),
    )

    assert envelope._provenance == "PROJECTED"
    assert envelope._owner_preimage is not None
    assert envelope._owner_preimage.selection_proof_binding == _SELECTION_BINDING
    assert checkpoint_codec.RuntimeCheckpointEnvelope._is_authentic(envelope)
    assert checkpoint_codec.encode_runtime_checkpoint(envelope) == canonical

    loaded = checkpoint_codec._decode_runtime_checkpoint(
        checkpoint_codec.encode_runtime_checkpoint(envelope), _LOAD_BINDING
    )
    assert loaded._provenance == "LOADED"
    assert loaded._owner_preimage is None
    assert loaded._binding != envelope._binding


def test_owner_preimage_mutation_and_scope_coordinate_splice_fail() -> None:
    payload = json.loads(_valid_empty_payload())
    envelope = checkpoint_codec._issue_projected_runtime_checkpoint(
        selection_proof_binding=_SELECTION_BINDING,
        application_generation_id=identity.ApplicationGenerationId("checkpoint-app"),
        execution_profile_id=_EXECUTION_PROFILE,
        market_source_profile_id=_MARKET_PROFILE,
        currentness_head_ordinal=0,
        checkpoint_version_ordinal=1,
        venue_wire=payload[7],
        authority_wire=payload[8],
        scope_wires=(),
        venue_owner_commitment=bytes.fromhex("55" * 32),
        authority_owner_commitment=bytes.fromhex("66" * 32),
        scope_owner_commitments=(),
    )
    preimage = envelope._owner_preimage
    assert preimage is not None
    object.__setattr__(preimage, "venue_owner_commitment", bytes.fromhex("77" * 32))
    assert not checkpoint_codec.RuntimeCheckpointEnvelope._is_authentic(envelope)

    with pytest.raises(ValueError, match="scope coordinates"):
        checkpoint_codec._issue_projected_runtime_checkpoint(
            selection_proof_binding=_SELECTION_BINDING,
            application_generation_id=identity.ApplicationGenerationId(
                "checkpoint-app"
            ),
            execution_profile_id=_EXECUTION_PROFILE,
            market_source_profile_id=_MARKET_PROFILE,
            currentness_head_ordinal=0,
            checkpoint_version_ordinal=1,
            venue_wire=payload[7],
            authority_wire=payload[8],
            scope_wires=(),
            venue_owner_commitment=bytes.fromhex("55" * 32),
            authority_owner_commitment=bytes.fromhex("66" * 32),
            scope_owner_commitments=((1, b"a" * 32, b"b" * 32, b"c" * 32),),
        )


def test_records_projector_seam_refuses_a_forged_contract_proof() -> None:
    forged: Any = object()
    with pytest.raises(TypeError, match="exact RuntimeCheckpointSelectionProof"):
        checkpoint_codec._project_runtime_checkpoint(forged, forged, forged, ())


def test_owner_projector_projects_valid_empty_selection_to_exact_canonical_wire() -> (
    None
):
    proof = _selection_proof()
    book, state = _empty_owners()

    envelope = checkpoint_codec._project_runtime_checkpoint(proof, book, state, ())
    payload = json.loads(checkpoint_codec.encode_runtime_checkpoint(envelope))

    assert envelope._provenance == "PROJECTED"
    assert payload[:7] == [
        1,
        "m2.runtime-checkpoint/v1",
        ["1", "application_generation_id", ["checkpoint-app"]],
        _EXECUTION_PROFILE,
        _MARKET_PROFILE,
        0,
        1,
    ]
    assert payload[7][0] == "m2.venue.State/v1"
    assert len(payload[7]) == 23
    assert payload[8][0] == "m2.authority.Checkpoint/v1"
    assert len(payload[8]) == 14
    assert payload[9] == ["m2.runtime-checkpoint.scopes/v1", 0, []]
    assert checkpoint_codec.RuntimeCheckpointEnvelope._is_authentic(envelope)


def test_owner_projector_refuses_missing_forged_and_unordered_scope_owners() -> None:
    selected = records.ScopeRecord(
        1, _APPLICATION, _EXECUTION_PROFILE, identity.SymbolId("AAPL")
    )
    proof = _selection_proof((selected,))
    book, state = _empty_owners()

    with pytest.raises(ValueError, match="do not match"):
        checkpoint_codec._project_runtime_checkpoint(proof, book, state, ())
    with pytest.raises(TypeError, match="exact _RuntimeCheckpointScopeOwners"):
        checkpoint_codec._project_runtime_checkpoint(
            proof,
            book,
            state,
            (object(),),  # type: ignore[arg-type]
        )

    forged = object.__new__(checkpoint_codec._RuntimeCheckpointScopeOwners)
    object.__setattr__(forged, "scope_id", 1)
    object.__setattr__(forged, "acquisition", object())
    object.__setattr__(forged, "execution", object())
    object.__setattr__(forged, "protection", object())
    with pytest.raises(TypeError, match="acquisition owner"):
        checkpoint_codec._project_runtime_checkpoint(proof, book, state, (forged,))


def test_owner_projector_refuses_spliced_authority_and_ignores_source_order() -> None:
    """R17 section 1: projection never reads _effect_order, so it cannot move bytes.

    This previously asserted that a nonempty source order was REFUSED. R17 deletes the
    source-order dependency outright - the selection proof is the sole membership and
    order witness - so the control is now the stronger positive one: unrelated source
    order must leave the projected payload byte-identical.
    """

    proof = _selection_proof()
    book, state = _empty_owners()
    other_book, other_state = _empty_owners("other-account")

    with pytest.raises(ValueError, match="selected venue owner"):
        checkpoint_codec._project_runtime_checkpoint(proof, book, other_state, ())

    clean_bytes = checkpoint_codec.encode_runtime_checkpoint(
        checkpoint_codec._project_runtime_checkpoint(proof, book, state, ())
    )
    sequence_type = type(book._effect_order)
    object.__setattr__(
        book,
        "_effect_order",
        sequence_type.from_values(
            (identity.EffectId("unselected-effect"),), lambda _value: b"x" * 32
        ),
    )
    noisy_bytes = checkpoint_codec.encode_runtime_checkpoint(
        checkpoint_codec._project_runtime_checkpoint(proof, book, state, ())
    )

    assert noisy_bytes == clean_bytes
    assert other_book.scope.account == identity.AccountId("other-account")


def test_owner_projector_binding_covers_proof_and_owner_commitments() -> None:
    first_proof = _selection_proof()
    second_proof = _selection_proof()
    first_book, first_state = _empty_owners("account-a")
    second_book, second_state = _empty_owners("account-b")

    first = checkpoint_codec._project_runtime_checkpoint(
        first_proof, first_book, first_state, ()
    )
    second = checkpoint_codec._project_runtime_checkpoint(
        second_proof, second_book, second_state, ()
    )

    assert first._owner_preimage is not None
    assert first._owner_preimage.selection_proof_binding == first_proof._binding
    # R20 section 1: owner provenance is the distinct source-owner commitment over the
    # venue row without its final member, never the history-shaped venue commitment.
    first_payload = json.loads(checkpoint_codec.encode_runtime_checkpoint(first))
    assert first._owner_preimage.venue_owner_commitment == bytes.fromhex(
        _contract_k("execution-core/m2-venue/source-owner/v1", first_payload[7][:-1])
    )
    assert first._owner_preimage.venue_owner_commitment != (
        first_book._protection_commitment
    )
    assert first._owner_preimage != second._owner_preimage
    assert first._binding != second._binding


@pytest.mark.parametrize(
    "nonempty,expected_acquisition_tail,expected_protection_commitment",
    (
        (
            False,
            (
                "a2f7601f08c166a94e98589c087205252aeb44978a03ef74895e4d1f9970f4db",
                "d9ef74722b0b16997850ed36ef467e5bfec7ea127a40d456639571db518ad54b",
                "3dc62b05989bc4eb51888760cd87d30f22e1ffa67e7a8bd3d2ae8581048dceba",
            ),
            "1ab343ac6edc9a7dfe9b0d27ea496ac966b5cb7523ec8fb816a9b88f30ffe9b2",
        ),
        (
            True,
            (
                "805ebef61eb3c37f1e9010e8caa030a6726363c278fac5923fc28e4d4faf1bf5",
                "7adf6f456fc23f6749d187d2936be0fa35ba356c3dc46d4b30c7f9c98622bdec",
                "69f658f70460184e3313581c4a7ad34de7d881fd78cd4bea887c06c395a6c63f",
            ),
            "1ab343ac6edc9a7dfe9b0d27ea496ac966b5cb7523ec8fb816a9b88f30ffe9b2",
        ),
    ),
)
def test_r19_dormant_empty_and_nonempty_literal_known_answers(
    nonempty: bool,
    expected_acquisition_tail: tuple[str, str, str],
    expected_protection_commitment: str,
) -> None:
    acquisition, protection = _dormant_wires(nonempty=nonempty)

    assert len(acquisition) == 17
    assert tuple(acquisition[-3:]) == expected_acquisition_tail
    assert len(protection) == 7
    assert protection[-1] == expected_protection_commitment
    checkpoint_codec._validate_runtime_checkpoint_acquisition_wire(acquisition)
    checkpoint_codec._validate_runtime_checkpoint_protection_wire(protection)


@pytest.mark.parametrize(
    "mutator",
    (
        lambda row: row[9].__setitem__(1, row[9][1] + 1),
        lambda row: row[10].__setitem__(0, "m2.acquisition.Wrong/v1"),
        lambda row: row[11].__setitem__(2, [*row[11][2], object()]),
        lambda row: row.__setitem__(slice(14, 16), [row[15], row[14]]),
        lambda row: row.__setitem__(14, row[15]),
        lambda row: row.__setitem__(16, row[14]),
    ),
)
def test_r19_dormant_acquisition_refuses_count_tag_order_omit_and_alias_mutants(
    mutator: Any,
) -> None:
    acquisition, _ = _dormant_wires(nonempty=True)
    mutant = deepcopy(acquisition)
    mutator(mutant)
    with pytest.raises((OverflowError, TypeError, ValueError)):
        checkpoint_codec._validate_runtime_checkpoint_acquisition_wire(mutant)


def test_r19_dormant_projection_uses_distinct_source_provenance_not_wire_self_hashes() -> (
    None
):
    proof, book, state, owners = _dormant_projection_inputs()

    envelope = checkpoint_codec._project_runtime_checkpoint(proof, book, state, owners)
    payload = json.loads(checkpoint_codec.encode_runtime_checkpoint(envelope))
    acquisition_wire = payload[9][2][0][3]
    protection_wire = payload[9][2][0][5]
    preimage = envelope._owner_preimage

    assert acquisition_wire[0] == "m2.acquisition.Dormant/v2"
    assert protection_wire[0] == "m2.protection.Dormant/v1"
    assert preimage is not None
    owner_row = preimage.scope_owner_commitments[0]
    assert owner_row[0] == 1
    assert owner_row[1] != bytes.fromhex(acquisition_wire[-1])
    assert owner_row[3] != bytes.fromhex(protection_wire[-1])
    assert owner_row[1] != owner_row[3]

    for acquisition_source, protection_source in (
        (bytes.fromhex(acquisition_wire[-1]), owner_row[3]),
        (owner_row[1], bytes.fromhex(protection_wire[-1])),
        (owner_row[3], owner_row[1]),
        (b"", owner_row[3]),
    ):
        forged = deepcopy(preimage)
        object.__setattr__(
            forged,
            "scope_owner_commitments",
            ((1, acquisition_source, owner_row[2], protection_source),),
        )
        object.__setattr__(envelope, "_owner_preimage", forged)
        assert not checkpoint_codec.RuntimeCheckpointEnvelope._is_authentic(envelope)
        object.__setattr__(envelope, "_owner_preimage", preimage)


@pytest.mark.parametrize(
    "selection_changes,message",
    (
        ({"controller_quantity": 1}, "quantity"),
        ({"protection_head": 8}, "head"),
        ({"partial_protection": True}, "partial"),
        ({"active_generation": True}, "acquisition owner"),
    ),
)
def test_r19_active_dormant_union_and_scope_relation_refusal_matrix(
    selection_changes: dict[str, object], message: str
) -> None:
    proof, book, state, owners = _dormant_projection_inputs(**selection_changes)
    with pytest.raises((TypeError, ValueError), match=message):
        checkpoint_codec._project_runtime_checkpoint(proof, book, state, owners)


def test_r19_dormant_source_projection_is_scope_and_proof_specific() -> None:
    proof, book, state, owners = _dormant_projection_inputs()
    first = checkpoint_codec._project_runtime_checkpoint(proof, book, state, owners)
    first_preimage = first._owner_preimage
    assert first_preimage is not None

    other_selection = _dormant_selection()
    other_scope = records.ScopeRecord(
        2, _APPLICATION, _EXECUTION_PROFILE, identity.SymbolId("MSFT")
    )
    other_controller = records.SymbolControllerRecord(
        2, _APPLICATION, _EXECUTION_PROFILE, None, 0, "DORMANT", 7, 3, "ee" * 32
    )
    other_protection = records.ProtectionAuthorityRecord(
        2, "DORMANT", None, None, None, None, None, None, 7, "aa" * 32, 3
    )
    object.__setattr__(
        other_selection,
        "scopes",
        (other_scope,),
    )
    object.__setattr__(other_selection, "controllers", (other_controller,))
    object.__setattr__(other_selection, "protection_authorities", (other_protection,))
    second_proof = _selection_proof(selection=other_selection)
    assert second_proof._binding != proof._binding

    owner_row = first_preimage.scope_owner_commitments[0]
    with pytest.raises(ValueError, match="scope coordinates"):
        checkpoint_codec._issue_projected_runtime_checkpoint(
            selection_proof_binding=second_proof._binding,
            application_generation_id=_APPLICATION,
            execution_profile_id=_EXECUTION_PROFILE,
            market_source_profile_id=_MARKET_PROFILE,
            currentness_head_ordinal=0,
            checkpoint_version_ordinal=1,
            venue_wire=json.loads(first.venue.canonical_bytes),
            authority_wire=json.loads(first.authority.canonical_bytes),
            scope_wires=(),
            venue_owner_commitment=first_preimage.venue_owner_commitment,
            authority_owner_commitment=first_preimage.authority_owner_commitment,
            scope_owner_commitments=((2, owner_row[1], owner_row[2], owner_row[3]),),
        )


def test_r20_venue_owner_provenance_is_distinct_source_owner_domain() -> None:
    proof = _selection_proof()
    book, state = _empty_owners()

    envelope = checkpoint_codec._project_runtime_checkpoint(proof, book, state, ())
    payload = json.loads(checkpoint_codec.encode_runtime_checkpoint(envelope))
    venue_row = payload[7]
    source_members = venue_row[:-1]
    preimage = envelope._owner_preimage

    expected_wire = _contract_k("execution-core/m2-venue/state/v1", source_members)
    expected_source_owner = _contract_k(
        "execution-core/m2-venue/source-owner/v1", source_members
    )

    assert expected_wire != expected_source_owner
    assert venue_row[-1] == expected_wire
    assert preimage is not None
    assert preimage.venue_owner_commitment == bytes.fromhex(expected_source_owner)
    assert preimage.venue_owner_commitment != bytes.fromhex(venue_row[-1])
    assert preimage.venue_owner_commitment != book._protection_commitment


def test_r20_authority_venue_ref_consumes_wire_commitment_only() -> None:
    proof = _selection_proof()
    book, state = _empty_owners()

    envelope = checkpoint_codec._project_runtime_checkpoint(proof, book, state, ())
    payload = json.loads(checkpoint_codec.encode_runtime_checkpoint(envelope))
    venue_ref = payload[8][7]
    preimage = envelope._owner_preimage

    assert venue_ref[0] == "m2.authority.VenueRef/v1"
    assert venue_ref[5] == payload[7][-1]
    assert preimage is not None
    assert venue_ref[5] != preimage.venue_owner_commitment.hex()


def test_r20_swapping_venue_wire_and_source_owner_commitments_fails() -> None:
    proof = _selection_proof()
    book, state = _empty_owners()

    envelope = checkpoint_codec._project_runtime_checkpoint(proof, book, state, ())
    payload = json.loads(checkpoint_codec.encode_runtime_checkpoint(envelope))
    preimage = envelope._owner_preimage
    assert preimage is not None

    for substitute in (
        bytes.fromhex(payload[7][-1]),
        preimage.authority_owner_commitment,
        book._protection_commitment,
        b"\x00" * 32,
    ):
        forged = deepcopy(preimage)
        object.__setattr__(forged, "venue_owner_commitment", substitute)
        object.__setattr__(envelope, "_owner_preimage", forged)
        assert not checkpoint_codec.RuntimeCheckpointEnvelope._is_authentic(envelope)
        object.__setattr__(envelope, "_owner_preimage", preimage)

    assert checkpoint_codec.RuntimeCheckpointEnvelope._is_authentic(envelope)


def test_r20_both_venue_commitments_differ_across_distinct_selected_accounts() -> None:
    first_proof = _selection_proof()
    second_proof = _selection_proof()
    first_book, first_state = _empty_owners("account-a")
    second_book, second_state = _empty_owners("account-b")

    first = checkpoint_codec._project_runtime_checkpoint(
        first_proof, first_book, first_state, ()
    )
    second = checkpoint_codec._project_runtime_checkpoint(
        second_proof, second_book, second_state, ()
    )
    first_payload = json.loads(checkpoint_codec.encode_runtime_checkpoint(first))
    second_payload = json.loads(checkpoint_codec.encode_runtime_checkpoint(second))

    assert first_payload[7][-1] != second_payload[7][-1]
    assert first._owner_preimage is not None
    assert second._owner_preimage is not None
    assert (
        first._owner_preimage.venue_owner_commitment
        != second._owner_preimage.venue_owner_commitment
    )


def _authority_state_with_manual_flattens(
    scope: venue.VenueScope,
    symbols: tuple[identity.SymbolId, ...],
    *,
    session: str = "manual-fixture-session",
) -> authority.ExecutionAuthorityState:
    """Build manual state through the real reducer, forging only environment proof."""

    state = copy(authority.initial_execution_authority_state(scope))
    for name, value in (
        ("phase", authority.EnginePhase.SERVING),
        ("mode", authority.TradingMode.REDUCING),
        ("supervisor_fence", authority.SupervisorFence.PAPER_MUTATION_ELIGIBLE),
        ("kill_engaged", False),
        ("session_id", authority.SessionId(session)),
        ("budget", authority.RequestBudget(remaining=8, safety_reserve=1)),
    ):
        object.__setattr__(state, name, value)

    for index, symbol in enumerate(symbols):
        execution = ExecutionSnapshot.flat(
            PositionScope(scope.broker, scope.environment, scope.account, symbol)
        )
        command = authority.BeginManualFlatten(
            authority.AuthorityInputId(f"manual-input-{index}"),
            authority.ManualFlattenId(f"manual-flatten-{symbol.value}"),
            authority.SessionId(session),
            symbol,
            identity.ActorId("fixture-operator"),
            "fixture manual flatten",
            identity.EvidenceReference(f"manual-evidence-{index}"),
            None,
        )
        transition = authority.apply_execution_authority_input(
            state, execution, command
        )
        assert transition.disposition is authority.AuthorityDisposition.APPLIED, (
            f"manual fixture refused: {transition.disposition} {transition.reason}"
        )
        state = transition.state
    return state


def _forge_stored_manual(
    state: authority.ExecutionAuthorityState,
    flatten_value: str,
    **command_changes: object,
) -> authority.ExecutionAuthorityState:
    """Return a state whose stored manual disagrees with the index that reaches it."""

    key = authority._manual_key(authority.ManualFlattenId(flatten_value))
    manual = state._manual_by_id.get(key)
    assert manual is not None
    forged_command = deepcopy(manual.command)
    for name, value in command_changes.items():
        object.__setattr__(forged_command, name, value)
    forged_manual = deepcopy(manual)
    object.__setattr__(forged_manual, "command", forged_command)
    forged_state = deepcopy(state)
    object.__setattr__(
        forged_state,
        "_manual_by_id",
        authority._replaced(state._manual_by_id, key, forged_manual),
    )
    return forged_state


def _manual_projection_inputs(
    symbols: tuple[identity.SymbolId, ...] = (identity.SymbolId("AAPL"),),
) -> tuple[
    records.RuntimeCheckpointSelectionProof,
    venue.VenueRecoveryBook,
    authority.ExecutionAuthorityState,
    tuple[checkpoint_codec._RuntimeCheckpointScopeOwners, ...],
]:
    """Reuse the dormant selection, but with reducer-built manual flatten state."""

    proof, _book, state, owners = _dormant_projection_inputs()
    manual_state = _authority_state_with_manual_flattens(state.venue.scope, symbols)
    return proof, manual_state.venue, manual_state, owners


def test_r20_manual_flatten_rows_project_exact_wire_from_selected_scope() -> None:
    proof, book, state, owners = _manual_projection_inputs()

    envelope = checkpoint_codec._project_runtime_checkpoint(proof, book, state, owners)
    payload = json.loads(checkpoint_codec.encode_runtime_checkpoint(envelope))
    manual_rows = payload[8][10]

    flatten_id = authority.ManualFlattenId("manual-flatten-AAPL")
    manual = state._manual_by_id.get(authority._manual_key(flatten_id))
    assert manual is not None

    assert manual_rows[0] == "m2.authority.ManualFlattens/v1"
    assert manual_rows[1] == 1
    assert len(manual_rows[2]) == 1
    row = manual_rows[2][0]
    assert row == [
        "m2.authority.ManualFlatten/v1",
        _operations._encode_m2_begin_manual_flatten(manual.command),
        ["m1.authority.FlattenPhase", "WAITING"],
        ["m2.authority.CancelEffects/v1", 0, []],
        None,
    ]
    assert len(row) == 5

    # Pin the nested command layout independently of the encoder under test.
    command_row = row[1]
    assert command_row[0] == "m1.authority.BeginManualFlatten/v1"
    assert len(command_row) == 9
    assert command_row[2] == ["1", "manual_flatten_id", ["manual-flatten-AAPL"]]
    assert command_row[4] == ["1", "symbol_id", ["AAPL"]]
    assert command_row[6] == "fixture manual flatten"
    assert command_row[8] is None
    assert checkpoint_codec.RuntimeCheckpointEnvelope._is_authentic(envelope)


def test_r20_manual_flatten_unreachable_from_selected_scopes_is_refused() -> None:
    """A manual on an unselected scope must fail closed, never be dropped silently."""

    proof, book, state, owners = _manual_projection_inputs(
        (identity.SymbolId("AAPL"), identity.SymbolId("MSFT"))
    )

    assert state._manual_by_id.size == 2
    with pytest.raises(ValueError, match="manual"):
        checkpoint_codec._project_runtime_checkpoint(proof, book, state, owners)


def test_r20_manual_cancel_effects_are_ordered_deduped_and_capped() -> None:
    _, _, state, _ = _manual_projection_inputs()
    manual = state._manual_by_id.get(
        authority._manual_key(authority.ManualFlattenId("manual-flatten-AAPL"))
    )
    assert manual is not None

    ordered = checkpoint_codec._encode_runtime_checkpoint_manual_row(
        _replace_manual(
            manual,
            cancel_effect_ids=(identity.EffectId("e-2"), identity.EffectId("e-1")),
        )
    )
    assert ordered[3] == [
        "m2.authority.CancelEffects/v1",
        2,
        [
            _operations._encode_m2_m1_atom(identity.EffectId("e-1")),
            _operations._encode_m2_m1_atom(identity.EffectId("e-2")),
        ],
    ]

    with pytest.raises(ValueError, match="duplicate"):
        checkpoint_codec._encode_runtime_checkpoint_manual_row(
            _replace_manual(
                manual,
                cancel_effect_ids=(identity.EffectId("e-1"), identity.EffectId("e-1")),
            )
        )
    at_cap = tuple(identity.EffectId(f"e-{index:06d}") for index in range(65_535))
    accepted = checkpoint_codec._encode_runtime_checkpoint_manual_row(
        _replace_manual(manual, cancel_effect_ids=at_cap)
    )
    assert accepted[3][1] == 65_535

    with pytest.raises(ValueError, match="bounded|cap"):
        checkpoint_codec._encode_runtime_checkpoint_manual_row(
            _replace_manual(
                manual,
                cancel_effect_ids=at_cap + (identity.EffectId("e-overflow"),),
            )
        )


def _replace_manual(manual: Any, **changes: object) -> Any:
    forged = deepcopy(manual)
    for name, value in changes.items():
        object.__setattr__(forged, name, value)
    return forged


def test_r20_manual_disagreeing_with_its_index_flatten_id_is_refused() -> None:
    """R20 s3: a stored manual must own the flatten ID that reached it."""

    proof, book, state, owners = _manual_projection_inputs()
    forged = _forge_stored_manual(
        state,
        "manual-flatten-AAPL",
        flatten_id=authority.ManualFlattenId("manual-flatten-FORGED"),
    )

    with pytest.raises(ValueError, match="flatten"):
        checkpoint_codec._project_runtime_checkpoint(
            proof, forged.venue, forged, owners
        )


def test_r20_manual_disagreeing_with_its_reached_scope_is_refused() -> None:
    """R20 s3: a manual reached through one scope may not name another symbol."""

    proof, book, state, owners = _manual_projection_inputs()
    forged = _forge_stored_manual(
        state, "manual-flatten-AAPL", symbol_id=identity.SymbolId("MSFT")
    )

    with pytest.raises(ValueError, match="scope|symbol"):
        checkpoint_codec._project_runtime_checkpoint(
            proof, forged.venue, forged, owners
        )


def test_r20_dangling_manual_slot_entry_is_refused() -> None:
    """R15 s4 cardinality is proved against BOTH authority manual maps, not one."""

    proof, book, state, owners = _manual_projection_inputs()
    unselected = PositionScope(
        book.scope.broker,
        book.scope.environment,
        book.scope.account,
        identity.SymbolId("MSFT"),
    )
    forged = deepcopy(state)
    object.__setattr__(
        forged,
        "_manual_flatten_by_scope",
        authority._inserted(
            state._manual_flatten_by_scope,
            authority._acquisition_scope_key(book.scope.generation, unselected),
            authority.ManualFlattenId("manual-flatten-AAPL"),
        ),
    )
    assert forged._manual_flatten_by_scope.size == 2
    assert forged._manual_by_id.size == 1

    with pytest.raises(ValueError, match="manual"):
        checkpoint_codec._project_runtime_checkpoint(
            proof, forged.venue, forged, owners
        )


def test_r20_manual_phase_must_be_an_exact_flatten_phase() -> None:
    """Every other manual row member is exact-type checked; phase must be too."""

    _, _, state, _ = _manual_projection_inputs()
    manual = state._manual_by_id.get(
        authority._manual_key(authority.ManualFlattenId("manual-flatten-AAPL"))
    )
    assert manual is not None
    forged = deepcopy(manual)
    object.__setattr__(forged, "phase", identity.SymbolId("NOT-A-PHASE"))

    with pytest.raises(TypeError, match="phase"):
        checkpoint_codec._encode_runtime_checkpoint_manual_row(forged)


def test_r20_authority_owner_provenance_is_distinct_source_owner_domain() -> None:
    """R15 s4 / R20 s4: authority wire and owner commitments are distinct domains."""

    proof, book, state, owners = _manual_projection_inputs()

    envelope = checkpoint_codec._project_runtime_checkpoint(proof, book, state, owners)
    payload = json.loads(checkpoint_codec.encode_runtime_checkpoint(envelope))
    source_members = payload[8][:-1]
    preimage = envelope._owner_preimage

    expected_wire = _contract_k(
        "execution-core/m2-authority/checkpoint/v1", source_members
    )
    expected_source_owner = _contract_k(
        "execution-core/m2-authority/source-owner/v1", source_members
    )

    assert expected_wire != expected_source_owner
    assert payload[8][-1] == expected_wire
    assert preimage is not None
    assert preimage.authority_owner_commitment == bytes.fromhex(expected_source_owner)
    assert preimage.authority_owner_commitment != bytes.fromhex(payload[8][-1])


def _claim_permit(
    *,
    protection_commitment: bytes | None = bytes.fromhex("bb" * 32),
    successor_ordinal: int = 3,
) -> authority.AcquisitionClaimPermit:
    """Mint one real permit through the authority constructor, not by hand."""

    return authority._new_acquisition_claim_permit(
        input_id=authority.AuthorityInputId("permit-input"),
        application_generation_id=_APPLICATION,
        position_scope=_DORMANT_POSITION_SCOPE,
        session_id=authority.SessionId("permit-session"),
        generation_id=identity.AcquisitionGenerationId("ab" * 32),
        acquisition_mandate_id=identity.AcquisitionMandateId("acq-mandate"),
        protection_mandate_id=identity.MandateId("prot-mandate"),
        binding_commitment=bytes.fromhex("11" * 32),
        emergency_recovery_compatibility_commitment=bytes.fromhex("22" * 32),
        controller_head=bytes.fromhex("33" * 32),
        successor_ordinal=successor_ordinal,
        execution_snapshot_commitment=bytes.fromhex("44" * 32),
        scope_execution_commitment=bytes.fromhex("55" * 32),
        venue_commitment=bytes.fromhex("66" * 32),
        authority_context_commitment=bytes.fromhex("77" * 32),
        protection_commitment=protection_commitment,
        effect_id=identity.EffectId("permit-effect"),
        claim_occurrence_id=identity.ClaimOccurrenceId("permit-occurrence"),
        currentness_commitment=bytes.fromhex("88" * 32),
        descriptor_commitment=bytes.fromhex("99" * 32),
        active_commitment=bytes.fromhex("aa" * 32),
    )


def test_r20_claim_permit_encodes_the_exact_21_semantic_members() -> None:
    permit = _claim_permit()
    row = checkpoint_codec._encode_runtime_checkpoint_claim_permit(permit)

    assert row == [
        "m2.authority.AcquisitionClaimPermit/v1",
        _operations._encode_m2_m1_atom(permit.input_id),
        _operations._encode_m2_m1_atom(_APPLICATION),
        _operations._encode_m2_position_scope(_DORMANT_POSITION_SCOPE),
        _operations._encode_m2_m1_atom(permit.session_id),
        _operations._encode_m2_m1_atom(permit.generation_id),
        _operations._encode_m2_m1_atom(permit.acquisition_mandate_id),
        _operations._encode_m2_m1_atom(permit.protection_mandate_id),
        "11" * 32,
        "22" * 32,
        "33" * 32,
        3,
        "44" * 32,
        "55" * 32,
        "66" * 32,
        "77" * 32,
        "bb" * 32,
        _operations._encode_m2_m1_atom(permit.effect_id),
        _operations._encode_m2_m1_atom(permit.claim_occurrence_id),
        "88" * 32,
        "99" * 32,
        "aa" * 32,
    ]
    assert len(row) == 22
    # derived members are re-derived on decode, never carried on the wire
    assert permit.commitment.hex() not in row
    assert permit._seal.hex() not in row
    # the whole row is admissible to the nested checkpoint validator
    checkpoint_codec._validate_checkpoint_nested_value(row)


def test_r20_claim_permit_optional_protection_commitment_is_null() -> None:
    row = checkpoint_codec._encode_runtime_checkpoint_claim_permit(
        _claim_permit(protection_commitment=None)
    )

    assert row[16] is None
    assert len(row) == 22
    checkpoint_codec._validate_checkpoint_nested_value(row)


def test_r20_claim_permit_refuses_forged_and_wrong_type_values() -> None:
    permit = _claim_permit()

    with pytest.raises(TypeError, match="permit"):
        checkpoint_codec._encode_runtime_checkpoint_claim_permit(
            _DORMANT_POSITION_SCOPE
        )

    for name, value in (
        ("effect_id", identity.EffectId("tampered-effect")),
        ("successor_ordinal", 9),
        ("active_commitment", bytes.fromhex("cc" * 32)),
    ):
        forged = deepcopy(permit)
        object.__setattr__(forged, name, value)
        with pytest.raises(ValueError, match="authentic"):
            checkpoint_codec._encode_runtime_checkpoint_claim_permit(forged)


_PRICE_SCALE = values.PriceScale(Decimal("0.01"))
_FIXTURE_PRICE = values.ReportedPrice(
    units=values.PriceUnits(100),
    scale=_PRICE_SCALE,
    tick=values.TickMetadata(tick_units=values.PriceUnits(1), scale=_PRICE_SCALE),
)


def _advanced_execution(
    symbol: identity.SymbolId, quantity: int, label: str
) -> ExecutionSnapshot:
    """Advance a real position through the fills reducer; no forging."""

    base = ExecutionSnapshot.flat(
        PositionScope(
            identity.BrokerId("paper"),
            identity.EnvironmentId("paper"),
            identity.AccountId("account"),
            symbol,
        )
    )
    fact = BrokerFillFact(
        key=ExecutionFactKey(
            broker=identity.BrokerId("paper"),
            environment=identity.EnvironmentId("paper"),
            account=identity.AccountId("account"),
            source_event_id=identity.SourceEventId(f"fixture-{label}-fill"),
        ),
        scope=ExecutionScope(
            broker=identity.BrokerId("paper"),
            environment=identity.EnvironmentId("paper"),
            account=identity.AccountId("account"),
            order_id=identity.OrderId(f"fixture-{label}-order"),
            symbol_id=symbol,
            side=ExecutionSide.BUY,
        ),
        root_fill_id=identity.RootFillId(f"fixture-{label}-root"),
        quantity=values.Quantity(quantity),
        price=_FIXTURE_PRICE,
    )
    transition = apply_broker_execution_fact(
        base.position, base.integrity, base.root_heads, base.seen_facts, fact
    )
    return ExecutionSnapshot(
        position=transition.position,
        integrity=transition.integrity,
        root_heads=transition.root_heads,
        seen_facts=transition.seen_facts,
    )


def _authority_state_with_effect(
    *,
    claimed: bool = True,
    symbol: identity.SymbolId = identity.SymbolId("AAPL"),
    effect_value: str = "effect-1",
) -> tuple[authority.ExecutionAuthorityState, identity.EffectId]:
    """Real reducer-built effect authorization; only environment proof is forged."""

    scope = venue.VenueScope(
        _APPLICATION,
        identity.BrokerId("paper"),
        identity.EnvironmentId("paper"),
        identity.AccountId("account"),
    )
    state = copy(authority.initial_execution_authority_state(scope))
    for name, value in (
        ("phase", authority.EnginePhase.SERVING),
        ("mode", authority.TradingMode.REDUCING),
        ("supervisor_fence", authority.SupervisorFence.PAPER_MUTATION_ELIGIBLE),
        ("kill_engaged", False),
        ("session_id", authority.SessionId("effect-session")),
        ("budget", authority.RequestBudget(remaining=8, safety_reserve=1)),
    ):
        object.__setattr__(state, name, value)

    execution = _advanced_execution(symbol, 5, effect_value)
    effect_id = identity.EffectId(effect_value)
    request = authority.BrokerEffectRequest(
        effect_id,
        identity.RequestOccurrenceId(f"req-{effect_value}"),
        identity.MandateId(f"mandate-{effect_value}"),
        venue.EffectKind.SUBMIT,
        identity.ClientOrderId(f"coid-{effect_value}"),
        symbol,
        ExecutionSide.SELL,
        values.Quantity(2),
        b"\x01" * 32,
        None,
    )
    created = authority.apply_execution_authority_input(
        state,
        execution,
        authority.CreateBrokerEffect(
            authority.AuthorityInputId(f"create-{effect_value}"),
            authority.SessionId("effect-session"),
            request,
            None,
            None,
        ),
    )
    assert created.disposition is authority.AuthorityDisposition.APPLIED, (
        f"effect fixture refused: {created.disposition} {created.reason}"
    )
    state = created.state
    if claimed:
        claimed_transition = authority.apply_execution_authority_input(
            state,
            execution,
            authority.ClaimEffect(
                authority.AuthorityInputId(f"claim-{effect_value}"),
                effect_id,
                identity.ClaimOccurrenceId(f"occurrence-{effect_value}"),
            ),
        )
        assert (
            claimed_transition.disposition is authority.AuthorityDisposition.APPLIED
        ), f"claim fixture refused: {claimed_transition.reason}"
        state = claimed_transition.state
    return state, effect_id


def test_r20_claim_row_encodes_the_exact_claim_effect_variant() -> None:
    state, effect_id = _authority_state_with_effect()
    claim = state._claim_by_effect.get(authority._effect_key(effect_id))
    assert claim is not None

    row = checkpoint_codec._encode_runtime_checkpoint_claim_row(claim)

    assert row == [
        "m2.authority.ClaimEffect/v1",
        _operations._encode_m2_m1_atom(claim.input_id),
        _operations._encode_m2_m1_atom(effect_id),
        _operations._encode_m2_m1_atom(claim.claim_occurrence_id),
    ]
    checkpoint_codec._validate_checkpoint_nested_value(row)


def test_r20_effect_authorization_row_nests_its_claim() -> None:
    state, effect_id = _authority_state_with_effect()
    authorization = state._effect_authority_by_id.get(authority._effect_key(effect_id))
    claim = state._claim_by_effect.get(authority._effect_key(effect_id))
    assert authorization is not None

    row = checkpoint_codec._encode_runtime_checkpoint_effect_authorization_row(
        authorization, claim
    )

    assert len(row) == 6
    assert row[0] == "m2.authority.EffectAuthorization/v1"
    assert row[1] == _operations._encode_m2_broker_effect_request(authorization.request)
    assert row[1][1] == _operations._encode_m2_m1_atom(effect_id)
    assert row[2] == _operations._encode_m2_m1_atom(authorization.session_id)
    assert row[3] is None
    assert row[4] is None
    assert row[5] == checkpoint_codec._encode_runtime_checkpoint_claim_row(claim)
    checkpoint_codec._validate_checkpoint_nested_value(row)


def test_r20_effect_authorization_row_without_a_claim_is_null() -> None:
    state, effect_id = _authority_state_with_effect(claimed=False)
    authorization = state._effect_authority_by_id.get(authority._effect_key(effect_id))
    assert authorization is not None
    assert state._claim_by_effect.get(authority._effect_key(effect_id)) is None

    row = checkpoint_codec._encode_runtime_checkpoint_effect_authorization_row(
        authorization, None
    )

    assert row[5] is None
    assert len(row) == 6
    checkpoint_codec._validate_checkpoint_nested_value(row)


def test_r20_effect_authorization_refuses_a_claim_naming_another_effect() -> None:
    """Contract: every claim must name the same effect as its authorization."""

    state, effect_id = _authority_state_with_effect()
    authorization = state._effect_authority_by_id.get(authority._effect_key(effect_id))
    claim = state._claim_by_effect.get(authority._effect_key(effect_id))
    assert authorization is not None and claim is not None

    forged = deepcopy(claim)
    object.__setattr__(forged, "effect_id", identity.EffectId("other-effect"))
    with pytest.raises(ValueError, match="effect"):
        checkpoint_codec._encode_runtime_checkpoint_effect_authorization_row(
            authorization, forged
        )


def _order_component_oracle(octet: int, value: object) -> bytes:
    """Independent contract-07 section 2.4 order_component, built from the text."""

    canonical = json.dumps(
        value, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")
    return bytes((octet,)) + struct.pack(">Q", len(canonical)) + canonical


def test_r20_collection_order_is_contract_order_component_not_python_strings() -> None:
    """Contract 2.4 forbids Python comparison; length-framing reorders these ids."""

    small = identity.EffectId("e-2")
    large = identity.EffectId("e-10")
    # Python string order and canonical order genuinely disagree for this pair.
    assert large.value < small.value
    assert _order_component_oracle(
        0x06, _operations._encode_m2_m1_atom(small)
    ) < _order_component_oracle(0x06, _operations._encode_m2_m1_atom(large))

    _, _, state, _ = _manual_projection_inputs()
    manual = state._manual_by_id.get(
        authority._manual_key(authority.ManualFlattenId("manual-flatten-AAPL"))
    )
    assert manual is not None

    row = checkpoint_codec._encode_runtime_checkpoint_manual_row(
        _replace_manual(manual, cancel_effect_ids=(large, small))
    )
    assert row[3][2] == [
        _operations._encode_m2_m1_atom(small),
        _operations._encode_m2_m1_atom(large),
    ]


def test_r20_unreachable_manual_id_is_omitted_not_refused() -> None:
    """R16 section 2: _manual_by_id is directly-reachable rows, not a current map.

    Older unreachable IDs are omitted; comparing a selected subset against this
    map's whole size is the cardinality mutant R16 requires to fail.
    """

    proof, book, state, owners = _manual_projection_inputs()
    stale = deepcopy(state)
    object.__setattr__(
        stale,
        "_manual_by_id",
        authority._inserted(
            state._manual_by_id,
            authority._manual_key(authority.ManualFlattenId("stale-flatten")),
            state._manual_by_id.get(
                authority._manual_key(authority.ManualFlattenId("manual-flatten-AAPL"))
            ),
        ),
    )
    assert stale._manual_by_id.size == 2
    assert stale._manual_flatten_by_scope.size == 1

    envelope = checkpoint_codec._project_runtime_checkpoint(
        proof, stale.venue, stale, owners
    )
    payload = json.loads(checkpoint_codec.encode_runtime_checkpoint(envelope))
    assert payload[8][10][1] == 1


def test_r20_noise_invariance_unreachable_manual_leaves_payload_bytes_identical() -> (
    None
):
    """R16 section 2's named control: unrelated history must not move the bytes."""

    proof, book, state, owners = _manual_projection_inputs()
    clean_bytes = checkpoint_codec.encode_runtime_checkpoint(
        checkpoint_codec._project_runtime_checkpoint(proof, book, state, owners)
    )

    noisy = deepcopy(state)
    object.__setattr__(
        noisy,
        "_manual_by_id",
        authority._inserted(
            state._manual_by_id,
            authority._manual_key(authority.ManualFlattenId("unrelated-closed")),
            state._manual_by_id.get(
                authority._manual_key(authority.ManualFlattenId("manual-flatten-AAPL"))
            ),
        ),
    )
    noisy_bytes = checkpoint_codec.encode_runtime_checkpoint(
        checkpoint_codec._project_runtime_checkpoint(proof, noisy.venue, noisy, owners)
    )

    assert noisy_bytes == clean_bytes


def test_r20_dangling_manual_slot_entry_is_still_refused() -> None:
    """The scope-index half of the rule stays exact: every present key is selected."""

    proof, book, state, owners = _manual_projection_inputs()
    unselected = PositionScope(
        book.scope.broker,
        book.scope.environment,
        book.scope.account,
        identity.SymbolId("MSFT"),
    )
    forged = deepcopy(state)
    object.__setattr__(
        forged,
        "_manual_flatten_by_scope",
        authority._inserted(
            state._manual_flatten_by_scope,
            authority._acquisition_scope_key(book.scope.generation, unselected),
            authority.ManualFlattenId("manual-flatten-AAPL"),
        ),
    )

    with pytest.raises(ValueError, match="manual"):
        checkpoint_codec._project_runtime_checkpoint(
            proof, forged.venue, forged, owners
        )


def _with_extra_authorization(
    state: authority.ExecutionAuthorityState,
    effect_value: str,
    *,
    claimed: bool = True,
) -> authority.ExecutionAuthorityState:
    """Add one more superset authorization without a second reducer effect.

    The reducer admits only one open effect per execution-bound scope, so a second
    CreateBrokerEffect is refused EXECUTION_BINDING_MISMATCH - correct venue behaviour.
    _EffectAuthorization and ClaimEffect are plain frozen dataclasses with no seal or
    commitment, so an inserted row is byte-identical to what the reducer would store;
    this only populates the permitted superset that the projection must ignore.
    """

    effect_id = identity.EffectId(effect_value)
    effect_key = authority._effect_key(effect_id)
    request = authority.BrokerEffectRequest(
        effect_id,
        identity.RequestOccurrenceId(f"req-{effect_value}"),
        identity.MandateId(f"mandate-{effect_value}"),
        venue.EffectKind.SUBMIT,
        identity.ClientOrderId(f"coid-{effect_value}"),
        identity.SymbolId("AAPL"),
        ExecutionSide.SELL,
        values.Quantity(2),
        b"\x01" * 32,
        None,
    )
    authorization = authority._EffectAuthorization(
        request, authority.SessionId("effect-session"), None, None
    )
    extended = copy(state)
    object.__setattr__(
        extended,
        "_effect_authority_by_id",
        authority._inserted(state._effect_authority_by_id, effect_key, authorization),
    )
    if claimed:
        occurrence = identity.ClaimOccurrenceId(f"occurrence-{effect_value}")
        claim = authority.ClaimEffect(
            authority.AuthorityInputId(f"claim-{effect_value}"), effect_id, occurrence
        )
        object.__setattr__(
            extended,
            "_claim_by_effect",
            authority._inserted(state._claim_by_effect, effect_key, claim),
        )
        object.__setattr__(
            extended,
            "_claim_by_occurrence",
            authority._inserted(
                state._claim_by_occurrence, authority._claim_key(occurrence), claim
            ),
        )
    return extended


def _authority_state_with_effects(
    effect_values: tuple[str, ...] = ("effect-1",),
    *,
    claimed: bool = True,
) -> tuple[authority.ExecutionAuthorityState, tuple[identity.EffectId, ...]]:
    """Reducer-built authority state carrying one authorization per effect value.

    Each effect gets its own symbol scope: a second open effect on the SAME scope is
    refused VENUE_UNCERTAIN by the real reducer, which is correct venue behaviour and
    not something the fixture should forge around.
    """

    scope = venue.VenueScope(
        _APPLICATION,
        identity.BrokerId("paper"),
        identity.EnvironmentId("paper"),
        identity.AccountId("account"),
    )
    state = copy(authority.initial_execution_authority_state(scope))
    for name, value in (
        ("phase", authority.EnginePhase.SERVING),
        ("mode", authority.TradingMode.REDUCING),
        ("supervisor_fence", authority.SupervisorFence.PAPER_MUTATION_ELIGIBLE),
        ("kill_engaged", False),
        ("session_id", authority.SessionId("effect-session")),
        ("budget", authority.RequestBudget(remaining=16, safety_reserve=1)),
    ):
        object.__setattr__(state, name, value)

    symbol = identity.SymbolId("AAPL")
    execution = _advanced_execution(symbol, 9, "effects")
    effect_ids: list[identity.EffectId] = []
    for value in effect_values[:1]:
        effect_id = identity.EffectId(value)
        request = authority.BrokerEffectRequest(
            effect_id,
            identity.RequestOccurrenceId(f"req-{value}"),
            identity.MandateId(f"mandate-{value}"),
            venue.EffectKind.SUBMIT,
            identity.ClientOrderId(f"coid-{value}"),
            symbol,
            ExecutionSide.SELL,
            values.Quantity(2),
            b"\x01" * 32,
            None,
        )
        created = authority.apply_execution_authority_input(
            state,
            execution,
            authority.CreateBrokerEffect(
                authority.AuthorityInputId(f"create-{value}"),
                authority.SessionId("effect-session"),
                request,
                None,
                None,
            ),
        )
        if created.disposition is not authority.AuthorityDisposition.APPLIED:
            raise AssertionError(
                f"effect fixture refused: {created.disposition.value} "
                f"{created.reason.value if created.reason else None}"
            )
        state = created.state
        if claimed:
            claim = authority.apply_execution_authority_input(
                state,
                execution,
                authority.ClaimEffect(
                    authority.AuthorityInputId(f"claim-{value}"),
                    effect_id,
                    identity.ClaimOccurrenceId(f"occurrence-{value}"),
                ),
            )
            if claim.disposition is not authority.AuthorityDisposition.APPLIED:
                raise AssertionError(
                    "claim fixture refused: "
                    f"{claim.reason.value if claim.reason else None}"
                )
            state = claim.state
        effect_ids.append(effect_id)
    for value in effect_values[1:]:
        state = _with_extra_authorization(state, value, claimed=claimed)
        effect_ids.append(identity.EffectId(value))
    return state, tuple(effect_ids)


def test_r20_effect_authorization_family_projects_selected_effects() -> None:
    state, effect_ids = _authority_state_with_effects()

    rows = checkpoint_codec._encode_runtime_checkpoint_effect_authorization_rows(
        state, effect_ids
    )

    assert rows[0] == "m2.authority.EffectAuthorizations/v1"
    assert rows[1] == 1
    row = rows[2][0]
    assert row[0] == "m2.authority.EffectAuthorization/v1"
    assert len(row) == 6
    assert row[1][1] == _operations._encode_m2_m1_atom(identity.EffectId("effect-1"))
    assert row[5][0] == "m2.authority.ClaimEffect/v1"
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.authority.EffectAuthorizations/v1"
    )


def test_r20_effect_authorization_family_omits_unselected_superset_rows() -> None:
    """R16 section 2: only rows reached by a selected effect are checkpointed.

    _effect_authority_by_id is a permitted authenticated superset, so unrelated
    authority history must leave the emitted bytes unchanged and must never be
    compared against the selection by whole-map size.
    """

    lean_state, lean_ids = _authority_state_with_effects(("effect-1",))
    lean_rows = checkpoint_codec._encode_runtime_checkpoint_effect_authorization_rows(
        lean_state, lean_ids
    )

    noisy_state, _ = _authority_state_with_effects(("effect-1", "effect-9"))
    assert noisy_state._effect_authority_by_id.size == 2
    noisy_rows = checkpoint_codec._encode_runtime_checkpoint_effect_authorization_rows(
        noisy_state, (identity.EffectId("effect-1"),)
    )

    assert noisy_rows == lean_rows


def test_r20_effect_authorization_orders_by_canonical_key_not_python_string() -> None:
    state, _ = _authority_state_with_effects(("effect-10", "effect-2"))

    rows = checkpoint_codec._encode_runtime_checkpoint_effect_authorization_rows(
        state, (identity.EffectId("effect-10"), identity.EffectId("effect-2"))
    )

    assert rows[1] == 2
    assert [row[1][1] for row in rows[2]] == [
        _operations._encode_m2_m1_atom(identity.EffectId("effect-2")),
        _operations._encode_m2_m1_atom(identity.EffectId("effect-10")),
    ]


def test_r20_effect_authorization_refuses_claim_occurrence_that_does_not_resolve() -> (
    None
):
    """Contract: a claim must name the same canonical occurrence as its authorization."""

    state, effect_ids = _authority_state_with_effects()
    effect_key = authority._effect_key(identity.EffectId("effect-1"))
    claim = state._claim_by_effect.get(effect_key)
    assert claim is not None

    forged = copy(state)
    other = deepcopy(claim)
    object.__setattr__(
        other, "claim_occurrence_id", identity.ClaimOccurrenceId("occurrence-other")
    )
    object.__setattr__(
        forged,
        "_claim_by_effect",
        authority._replaced(state._claim_by_effect, effect_key, other),
    )

    with pytest.raises(ValueError, match="occurrence"):
        checkpoint_codec._encode_runtime_checkpoint_effect_authorization_rows(
            forged, effect_ids
        )


def test_r20_effect_authorization_refuses_authorization_naming_another_effect() -> None:
    state, effect_ids = _authority_state_with_effects(claimed=False)
    effect_key = authority._effect_key(identity.EffectId("effect-1"))
    authorization = state._effect_authority_by_id.get(effect_key)
    assert authorization is not None

    forged_request = deepcopy(authorization.request)
    object.__setattr__(forged_request, "effect_id", identity.EffectId("other-effect"))
    forged_authorization = deepcopy(authorization)
    object.__setattr__(forged_authorization, "request", forged_request)
    forged = copy(state)
    object.__setattr__(
        forged,
        "_effect_authority_by_id",
        authority._replaced(
            state._effect_authority_by_id, effect_key, forged_authorization
        ),
    )

    with pytest.raises(ValueError, match="effect"):
        checkpoint_codec._encode_runtime_checkpoint_effect_authorization_rows(
            forged, effect_ids
        )


def _venue_effect_record(
    effect_id: identity.EffectId, ordinal: int
) -> records.VenueEffectRecord:
    """One repository-shaped selected effect row."""

    return records.VenueEffectRecord(
        ordinal,
        effect_id,
        1,
        _APPLICATION,
        _EXECUTION_PROFILE,
        identity.AcquisitionGenerationId("ab" * 32),
        "cd" * 32,
        7,
        3,
        "ACQUISITION",
        identity.RequestOccurrenceId(f"req-{effect_id.value}"),
        identity.MandateId(f"mandate-{effect_id.value}"),
        "SUBMIT",
        identity.ClientOrderId(f"coid-{effect_id.value}"),
        None,
        "SELL",
        values.Quantity(2),
        b"\x01" * 32,
        "OPEN",
        "OPEN",
        None,
        None,
        None,
        None,
        ordinal,
    )


def _venue_claim_selection(
    effect_values: tuple[str, ...] = ("effect-1",),
) -> records._RuntimeCheckpointSelectionSet:
    """Selection carrying one effect and its dispatch claim, in proof order."""

    effects = tuple(
        _venue_effect_record(identity.EffectId(value), index + 1)
        for index, value in enumerate(effect_values)
    )
    claims = tuple(
        records.DispatchClaimRecord(
            index + 1,
            index + 1,
            _EXECUTION_PROFILE,
            identity.ClaimOccurrenceId(f"occurrence-{value}"),
            index + 1,
        )
        for index, value in enumerate(effect_values)
    )
    base = _dormant_selection()
    forged = deepcopy(base)
    object.__setattr__(forged, "effects", effects)
    object.__setattr__(forged, "claims", claims)
    return forged


def test_r20_venue_claim_rows_project_in_proof_order() -> None:
    """R20 section 2: venue families keep R17 proof order, not a re-sort."""

    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_claim_rows(
        state.venue, selection
    )

    assert rows[0] == "m2.venue.Claims/v1"
    assert rows[1] == 1
    assert rows[2][0] == [
        "m2.venue.DispatchClaim/v1",
        _operations._encode_m2_m1_atom(identity.EffectId("effect-1")),
        _operations._encode_m2_m1_atom(
            identity.ClaimOccurrenceId("occurrence-effect-1")
        ),
    ]
    checkpoint_codec._validate_checkpoint_collection(rows, "m2.venue.Claims/v1")


def test_r20_venue_claim_refuses_record_disagreeing_with_its_owner() -> None:
    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()
    forged_claim = records.DispatchClaimRecord(
        1, 1, _EXECUTION_PROFILE, identity.ClaimOccurrenceId("occurrence-wrong"), 1
    )
    forged = deepcopy(selection)
    object.__setattr__(forged, "claims", (forged_claim,))

    with pytest.raises(ValueError, match="selected record"):
        checkpoint_codec._encode_runtime_checkpoint_venue_claim_rows(
            state.venue, forged
        )


def test_r20_venue_claim_refuses_claim_naming_an_unselected_effect() -> None:
    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()
    forged = deepcopy(selection)
    object.__setattr__(forged, "effects", ())

    with pytest.raises(ValueError, match="unselected effect"):
        checkpoint_codec._encode_runtime_checkpoint_venue_claim_rows(
            state.venue, forged
        )


def test_r20_venue_effect_rows_carry_dense_proof_order_checkpoint_ordinals() -> None:
    """R18 section 1: I(checkpoint_ordinal) is the dense 0..n-1 proof-order index."""

    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_effect_rows(
        state.venue, selection
    )

    assert rows[0] == "m2.venue.Effects/v1"
    assert rows[1] == 1
    row = rows[2][0]
    assert row[0] == "m2.venue.EffectCurrent/v1"
    assert len(row) == 10
    assert row[1] == 0
    scope_row = row[2]
    assert scope_row[0] == "m2.venue.EffectScope/v1"
    assert len(scope_row) == 15
    assert scope_row[5] == _operations._encode_m2_m1_atom(identity.EffectId("effect-1"))
    # the fixture claims the effect, so the current owner state is DISPATCH_CLAIMED
    assert row[3] == ["m1.venue.BrokerEffectState", "DISPATCH_CLAIMED"]
    assert row[7] == ["m2.venue.Contradictions/v1", 0, []]
    checkpoint_codec._validate_checkpoint_collection(rows, "m2.venue.Effects/v1")


def test_r20_venue_effect_rows_refuse_a_record_disagreeing_with_its_owner() -> None:
    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()
    forged = deepcopy(selection)
    record = selection.effects[0]
    other = deepcopy(record)
    object.__setattr__(other, "side", "BUY")
    object.__setattr__(forged, "effects", (other,))

    with pytest.raises(ValueError, match="selected record"):
        checkpoint_codec._encode_runtime_checkpoint_venue_effect_rows(
            state.venue, forged
        )


def test_r20_venue_effect_rows_refuse_an_unreachable_selected_effect() -> None:
    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()
    forged = deepcopy(selection)
    object.__setattr__(
        forged,
        "effects",
        (_venue_effect_record(identity.EffectId("effect-absent"), 1),),
    )
    object.__setattr__(forged, "claims", ())

    with pytest.raises(ValueError, match="no current owner"):
        checkpoint_codec._encode_runtime_checkpoint_venue_effect_rows(
            state.venue, forged
        )


def test_r20_venue_protection_cursor_rows_project_selected_scopes() -> None:
    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_protection_cursor_rows(
        state.venue, selection
    )

    assert rows[0] == "m2.venue.ProtectionCursors/v1"
    assert rows[1] == 1
    row = rows[2][0]
    assert row[0] == "m2.venue.ProtectionCursor/v1"
    assert len(row) == 7
    assert row[1] == _operations._encode_m2_position_scope(_DORMANT_POSITION_SCOPE)
    assert row[2] == 2
    assert row[4] == _operations._encode_m2_m1_atom(
        identity.MandateId("mandate-effect-1")
    )
    checkpoint = row[6]
    assert checkpoint[0] == "m2.venue.ExecutionCheckpoint/v1"
    assert len(checkpoint) == 10
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.venue.ProtectionCursors/v1"
    )


def test_r20_venue_protection_cursor_refuses_an_unselected_scope_entry() -> None:
    """Exact current selected-scope map: every present key must be a selected scope."""

    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()
    forged = deepcopy(selection)
    object.__setattr__(forged, "scopes", ())

    with pytest.raises(ValueError, match="selected scope"):
        checkpoint_codec._encode_runtime_checkpoint_venue_protection_cursor_rows(
            state.venue, forged
        )


def test_r20_venue_execution_scope_rows_project_selected_scopes() -> None:
    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_execution_scope_rows(
        state.venue, selection
    )

    assert rows[0] == "m2.venue.ExecutionScopes/v1"
    assert rows[1] == 1
    row = rows[2][0]
    assert row[0] == "m2.venue.ExecutionScopeCurrent/v1"
    assert len(row) == 3
    assert row[1][0] == "m2.position.execution-state/v1"
    assert row[2][0] == "m2.venue.ExecutionCheckpoint/v1"
    assert len(row[2]) == 10
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.venue.ExecutionScopes/v1"
    )


def test_r20_venue_execution_scope_refuses_an_unselected_scope_entry() -> None:
    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()
    forged = deepcopy(selection)
    object.__setattr__(forged, "scopes", ())

    with pytest.raises(ValueError, match="selected scope"):
        checkpoint_codec._encode_runtime_checkpoint_venue_execution_scope_rows(
            state.venue, forged
        )


def test_r20_composite_durable_atom_is_admitted_as_a_nested_value() -> None:
    """The validator must admit exactly what the frozen atom encoder can emit.

    _encode_m2_durable_atom accepts a field that is either text or a nested atom, so a
    composite atom such as a reported price is legitimate wire. The checkpoint
    validator previously required every field to be text, which refused any execution
    state carrying a price - that is, every non-flat position.
    """

    price = values.ReportedPrice(
        units=values.PriceUnits(100),
        scale=_PRICE_SCALE,
        tick=values.TickMetadata(tick_units=values.PriceUnits(1), scale=_PRICE_SCALE),
    )
    composite = _operations._encode_m2_m1_atom(price)

    assert composite[0] == "1"
    assert any(type(field) is list for field in composite[2])
    checkpoint_codec._validate_checkpoint_nested_value(composite)

    # a malformed nested field must still fail closed
    forged = deepcopy(composite)
    forged[2][0] = ["9", "not-an-atom", []]
    with pytest.raises(ValueError, match="durable atom"):
        checkpoint_codec._validate_checkpoint_nested_value(forged)

    forged_scalar = deepcopy(composite)
    forged_scalar[2][0] = 7
    with pytest.raises(ValueError, match="durable atom"):
        checkpoint_codec._validate_checkpoint_nested_value(forged_scalar)


def test_r20_tail_fold_input_registered_arity_matches_its_encoder() -> None:
    """The nested-row registry is tag-inclusive and must match the frozen encoder.

    _encode_m2_tail_fold_input emits the tag plus seven fields, and its decoder asserts
    seven fields, so the admitted nested-row length is eight. It was registered as
    seven, which refused every bound tail-fold proof - reachable only once a non-flat
    position reaches a checkpoint.
    """

    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()
    rows = checkpoint_codec._encode_runtime_checkpoint_venue_execution_scope_rows(
        state.venue, selection
    )
    execution_state = rows[2][0][1]
    tail_folds = [
        member
        for member in execution_state
        if type(member) is list
        and member
        and member[0] == "m2.position.tail-fold-input/v1"
    ]

    assert tail_folds, "fixture must produce a bound tail-fold proof"
    for tail_fold in tail_folds:
        assert (
            len(tail_fold)
            == checkpoint_codec._CHECKPOINT_FIXED_ROW_LENGTHS[
                "m2.position.tail-fold-input/v1"
            ]
        )
        checkpoint_codec._validate_checkpoint_nested_value(tail_fold)


def _book_with_int_index(
    book: venue.VenueRecoveryBook,
    field_name: str,
    key: bytes,
    value: int,
    domain: bytes,
) -> venue.VenueRecoveryBook:
    """Populate one int-valued venue index using the book's own commitment domain.

    These two maps are not reachable from the pure reducer path this suite can drive,
    so the entry is inserted directly under the exact domain venue.py uses. The value
    is a plain int with no seal, so the inserted row is identical to a reduced one.
    """

    retained = getattr(book, field_name)
    commitment = venue._commit_parts(domain, venue._encode_text(str(value)))
    forged = copy(book)
    object.__setattr__(forged, field_name, retained.insert_new(key, value, commitment))
    return forged


def test_r20_venue_authority_epoch_rows_project_selected_scopes() -> None:
    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()
    book = _book_with_int_index(
        state.venue,
        "_authority_epoch_by_scope",
        venue._position_scope_index_key(_DORMANT_POSITION_SCOPE),
        4,
        b"execution-core/venue-authority-epoch/v1",
    )

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_authority_epoch_rows(
        book, selection
    )

    assert rows[0] == "m2.venue.AuthorityEpochs/v1"
    assert rows[1] == 1
    assert rows[2][0] == [
        "m2.venue.AuthorityEpoch/v1",
        _operations._encode_m2_position_scope(_DORMANT_POSITION_SCOPE),
        4,
    ]
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.venue.AuthorityEpochs/v1"
    )


def test_r20_venue_authority_epoch_refuses_an_unselected_scope_entry() -> None:
    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()
    book = _book_with_int_index(
        state.venue,
        "_authority_epoch_by_scope",
        venue._position_scope_index_key(_DORMANT_POSITION_SCOPE),
        4,
        b"execution-core/venue-authority-epoch/v1",
    )
    forged = deepcopy(selection)
    object.__setattr__(forged, "scopes", ())

    with pytest.raises(ValueError, match="selected scope"):
        checkpoint_codec._encode_runtime_checkpoint_venue_authority_epoch_rows(
            book, forged
        )


def test_r20_venue_economic_high_water_rows_project_selected_owners() -> None:
    state, _ = _authority_state_with_effects()
    selection = _venue_claim_selection()
    leg_key = identity.VenueLegKey(
        identity.BrokerId("paper"),
        identity.EnvironmentId("paper"),
        identity.AccountId("account"),
        identity.OrderId("owner-order-1"),
    )
    book = _book_with_int_index(
        state.venue,
        "_economic_high_water_by_leg",
        venue._leg_index_key(leg_key),
        6,
        b"execution-core/venue-economic-high-water/v1",
    )
    owners = (
        records.VenueIdentityOwnerRecord(
            1,
            _EXECUTION_PROFILE,
            identity.OrderId("owner-order-1"),
            identity.VenueObservationId("observation-1"),
            1,
            None,
            identity.AcquisitionGenerationId("ab" * 32),
            False,
        ),
    )
    forged = deepcopy(selection)
    object.__setattr__(forged, "owners", owners)

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_high_water_rows(
        book, forged
    )

    assert rows[0] == "m2.venue.EconomicHighWaters/v1"
    assert rows[1] == 1
    assert rows[2][0] == [
        "m2.venue.EconomicHighWater/v1",
        _operations._encode_m2_m1_atom(leg_key),
        6,
    ]
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.venue.EconomicHighWaters/v1"
    )


def _book_with_owner_leg(
    book: venue.VenueRecoveryBook,
    leg_key: identity.VenueLegKey,
    effect_scope: venue.VenueEffectScope,
    *,
    with_attempt: bool = True,
) -> venue.VenueRecoveryBook:
    """Populate the owner and leg-current indexes for one leg."""

    owner = venue.VenueIdentityOwner(
        leg_key, effect_scope, identity.VenueObservationId("observation-1")
    )
    forged = copy(book)
    object.__setattr__(
        forged,
        "_owner_by_leg",
        book._owner_by_leg.insert_new(
            venue._leg_index_key(leg_key), owner, venue._owner_value_commitment(owner)
        ),
    )
    if with_attempt:
        attempt = venue.VenueAttempt(
            leg_key,
            venue.VenueAttemptState.WORKING,
            None,
            values.Quantity(2),
            identity.VenueObservationId("observation-1"),
        )
        current = venue._LegCurrent(attempt)
        object.__setattr__(
            forged,
            "_leg_current_by_leg",
            book._leg_current_by_leg.insert_new(
                venue._leg_index_key(leg_key), current, current.commitment
            ),
        )
    return forged


def _owner_selection(
    selection: records._RuntimeCheckpointSelectionSet, order_id: str
) -> records._RuntimeCheckpointSelectionSet:
    forged = deepcopy(selection)
    object.__setattr__(
        forged,
        "owners",
        (
            records.VenueIdentityOwnerRecord(
                1,
                _EXECUTION_PROFILE,
                identity.OrderId(order_id),
                identity.VenueObservationId("observation-1"),
                1,
                None,
                identity.AcquisitionGenerationId("ab" * 32),
                False,
            ),
        ),
    )
    return forged


def test_r20_venue_owner_attempt_rows_carry_dense_checkpoint_ordinals() -> None:
    state, _ = _authority_state_with_effects()
    effect_scope = state.venue._effect_by_id.get(
        venue._effect_index_key(identity.EffectId("effect-1"))
    ).effect.scope
    leg_key = identity.VenueLegKey(
        identity.BrokerId("paper"),
        identity.EnvironmentId("paper"),
        identity.AccountId("account"),
        identity.OrderId("owner-order-1"),
    )
    book = _book_with_owner_leg(state.venue, leg_key, effect_scope)
    selection = _owner_selection(_venue_claim_selection(), "owner-order-1")

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_owner_attempt_rows(
        book, selection
    )

    assert rows[0] == "m2.venue.OwnerAttempts/v1"
    assert rows[1] == 1
    row = rows[2][0]
    assert row[0] == "m2.venue.OwnerAttempt/v1"
    assert len(row) == 6
    assert row[1] == 0
    assert row[2] == _operations._encode_m2_m1_atom(leg_key)
    assert row[3] == _operations._encode_m2_m1_atom(identity.EffectId("effect-1"))
    assert row[5][0] == "m2.venue.Attempt/v1"
    assert len(row[5]) == 6
    checkpoint_codec._validate_checkpoint_collection(rows, "m2.venue.OwnerAttempts/v1")


def test_r20_venue_owner_attempt_null_attempt_and_unselected_leg() -> None:
    state, _ = _authority_state_with_effects()
    effect_scope = state.venue._effect_by_id.get(
        venue._effect_index_key(identity.EffectId("effect-1"))
    ).effect.scope
    leg_key = identity.VenueLegKey(
        identity.BrokerId("paper"),
        identity.EnvironmentId("paper"),
        identity.AccountId("account"),
        identity.OrderId("owner-order-1"),
    )
    book = _book_with_owner_leg(state.venue, leg_key, effect_scope, with_attempt=False)
    selection = _owner_selection(_venue_claim_selection(), "owner-order-1")

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_owner_attempt_rows(
        book, selection
    )
    assert rows[2][0][5] is None

    with pytest.raises(ValueError, match="selected owner"):
        checkpoint_codec._encode_runtime_checkpoint_venue_owner_attempt_rows(
            book, _venue_claim_selection()
        )


def _root_selection(
    selection: records._RuntimeCheckpointSelectionSet, root_fill_id: str
) -> records._RuntimeCheckpointSelectionSet:
    forged = deepcopy(selection)
    object.__setattr__(
        forged,
        "roots",
        (
            records.RootFillRecord(
                1,
                1,
                _APPLICATION,
                _EXECUTION_PROFILE,
                identity.AcquisitionGenerationId("ab" * 32),
                identity.RootFillId(root_fill_id),
                None,
                None,
                None,
                None,
                None,
                None,
                0,
            ),
        ),
    )
    return forged


def test_r20_venue_acquisition_correlation_rows_project_selected_roots() -> None:
    state, _ = _authority_state_with_effects()
    root_key = identity.RootFillKey(
        identity.BrokerId("paper"),
        identity.EnvironmentId("paper"),
        identity.AccountId("account"),
        identity.RootFillId("root-1"),
    )
    leg_key = identity.VenueLegKey(
        identity.BrokerId("paper"),
        identity.EnvironmentId("paper"),
        identity.AccountId("account"),
        identity.OrderId("owner-order-1"),
    )
    entry = venue._AcquisitionCorrelationEntry(
        _APPLICATION,
        _DORMANT_POSITION_SCOPE,
        identity.RequestOccurrenceId("req-effect-1"),
        identity.EffectId("effect-1"),
        leg_key,
        root_key,
    )
    book = copy(state.venue)
    object.__setattr__(
        book,
        "_acquisition_correlation_by_root",
        state.venue._acquisition_correlation_by_root.insert_new(
            venue._coverage_root_index_key(root_key), entry, entry.commitment
        ),
    )
    selection = _root_selection(_venue_claim_selection(), "root-1")

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_correlation_rows(
        book, selection
    )

    assert rows[0] == "m2.venue.AcquisitionCorrelations/v1"
    assert rows[1] == 1
    row = rows[2][0]
    assert row[0] == "m2.venue.AcquisitionCorrelation/v1"
    assert len(row) == 7
    assert row[2] == _operations._encode_m2_position_scope(_DORMANT_POSITION_SCOPE)
    assert row[6] == _operations._encode_m2_m1_atom(root_key)
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.venue.AcquisitionCorrelations/v1"
    )

    with pytest.raises(ValueError, match="selected root"):
        checkpoint_codec._encode_runtime_checkpoint_venue_correlation_rows(
            book, _venue_claim_selection()
        )


def test_r20_venue_coverage_provenance_rows_flatten_selected_roots() -> None:
    state, _ = _authority_state_with_effects()
    root_key = identity.RootFillKey(
        identity.BrokerId("paper"),
        identity.EnvironmentId("paper"),
        identity.AccountId("account"),
        identity.RootFillId("root-1"),
    )
    roots = (
        type(state.venue._effect_by_id)
        .empty()
        .insert_new(
            venue._coverage_root_index_key(root_key), b"\xaa" * 32, b"\xbb" * 32
        )
    )
    provenance = venue._CoverageProvenance(roots, b"\xcc" * 32)
    book = copy(state.venue)
    object.__setattr__(
        book,
        "_coverage_provenance_by_scope",
        state.venue._coverage_provenance_by_scope.insert_new(
            venue._position_scope_index_key(_DORMANT_POSITION_SCOPE),
            provenance,
            provenance.commitment,
        ),
    )
    selection = _root_selection(_venue_claim_selection(), "root-1")

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_coverage_provenance_rows(
        book, selection
    )

    assert rows[0] == "m2.venue.CoverageProvenances/v1"
    assert rows[1] == 1
    row = rows[2][0]
    assert row[0] == "m2.venue.CoverageProvenance/v1"
    assert len(row) == 4
    assert row[1] == _operations._encode_m2_position_scope(_DORMANT_POSITION_SCOPE)
    assert row[2] == [
        "m2.venue.CoveredRoots/v1",
        1,
        [
            [
                "m2.venue.CoveredRoot/v1",
                _operations._encode_m2_m1_atom(root_key),
                "aa" * 32,
            ]
        ],
    ]
    assert row[3] == "cc" * 32
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.venue.CoverageProvenances/v1"
    )

    with pytest.raises(ValueError, match="covered root"):
        checkpoint_codec._encode_runtime_checkpoint_venue_coverage_provenance_rows(
            book, _venue_claim_selection()
        )


_FIXTURE_LEG_KEY = identity.VenueLegKey(
    identity.BrokerId("paper"),
    identity.EnvironmentId("paper"),
    identity.AccountId("account"),
    identity.OrderId("owner-order-1"),
)
_FIXTURE_ROOT_KEY = identity.RootFillKey(
    identity.BrokerId("paper"),
    identity.EnvironmentId("paper"),
    identity.AccountId("account"),
    identity.RootFillId("root-1"),
)


def _fixture_broker_fill_fact(label: str) -> BrokerFillFact:
    return BrokerFillFact(
        key=ExecutionFactKey(
            broker=identity.BrokerId("paper"),
            environment=identity.EnvironmentId("paper"),
            account=identity.AccountId("account"),
            source_event_id=identity.SourceEventId(f"coverage-{label}"),
        ),
        scope=ExecutionScope(
            broker=identity.BrokerId("paper"),
            environment=identity.EnvironmentId("paper"),
            account=identity.AccountId("account"),
            order_id=identity.OrderId("owner-order-1"),
            symbol_id=identity.SymbolId("AAPL"),
            side=ExecutionSide.BUY,
        ),
        root_fill_id=identity.RootFillId("root-1"),
        quantity=values.Quantity(2),
        price=_FIXTURE_PRICE,
    )


def _book_with_broker_coverage(
    book: venue.VenueRecoveryBook,
) -> venue.VenueRecoveryBook:
    from app.execution_core import recovery as _recovery

    coverage = _recovery._BrokerCoverage(
        identity.EffectId("effect-1"),
        _FIXTURE_LEG_KEY,
        values.Quantity(0),
        values.Quantity(2),
        _fixture_broker_fill_fact("broker"),
        b"\xdd" * 32,
        identity.VenueInputId("input-1"),
        _fixture_broker_fill_fact("broker"),
        b"\xee" * 32,
        identity.VenueInputId("input-1"),
        True,
    )
    ledger_type = type(book._broker_coverage_ledger)
    forged = copy(book)
    object.__setattr__(
        forged,
        "_broker_coverage_ledger",
        ledger_type.from_values((coverage,), lambda _value: b"\x01" * 32),
    )
    object.__setattr__(
        forged,
        "_broker_coverage_by_root",
        book._broker_coverage_by_root.insert_new(
            venue._coverage_root_index_key(_FIXTURE_ROOT_KEY), 0, b"\x02" * 32
        ),
    )
    return forged


def test_r20_venue_broker_coverage_rows_dereference_the_ledger() -> None:
    state, _ = _authority_state_with_effects()
    book = _book_with_broker_coverage(state.venue)
    selection = _root_selection(_venue_claim_selection(), "root-1")

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_broker_coverage_rows(
        book, selection
    )

    assert rows[0] == "m2.venue.BrokerCoverages/v1"
    assert rows[1] == 1
    row = rows[2][0]
    assert row[0] == "m2.venue.BrokerCoverage/v1"
    assert len(row) == 12
    assert row[1] == _operations._encode_m2_m1_atom(identity.EffectId("effect-1"))
    assert row[5][0] == "m1.fills.BrokerFillFact/v1"
    assert row[6] == "dd" * 32
    assert row[11] is True
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.venue.BrokerCoverages/v1"
    )

    with pytest.raises(ValueError, match="selected root"):
        checkpoint_codec._encode_runtime_checkpoint_venue_broker_coverage_rows(
            book, _venue_claim_selection()
        )


def _book_with_human_coverage(
    book: venue.VenueRecoveryBook,
) -> venue.VenueRecoveryBook:
    from app.execution_core import recovery as _recovery
    from app.execution_core.fills import HumanAttestedFillFact

    fact = HumanAttestedFillFact(
        key=ExecutionFactKey(
            broker=identity.BrokerId("paper"),
            environment=identity.EnvironmentId("paper"),
            account=identity.AccountId("account"),
            source_event_id=identity.SourceEventId("human-1"),
        ),
        scope=ExecutionScope(
            broker=identity.BrokerId("paper"),
            environment=identity.EnvironmentId("paper"),
            account=identity.AccountId("account"),
            order_id=identity.OrderId("owner-order-1"),
            symbol_id=identity.SymbolId("AAPL"),
            side=ExecutionSide.BUY,
        ),
        root_fill_id=identity.RootFillId("root-1"),
        leg_key=_FIXTURE_LEG_KEY,
        request_occurrence_id=identity.RequestOccurrenceId("req-effect-1"),
        claim_occurrence_id=identity.ClaimOccurrenceId("occurrence-effect-1"),
        quantity=values.Quantity(2),
        prior_cumulative_quantity=values.Quantity(0),
        resulting_cumulative_quantity=values.Quantity(2),
        price=_FIXTURE_PRICE,
        actor=identity.ActorId("operator"),
        reason="fixture human coverage",
        evidence_reference=identity.EvidenceReference("evidence-1"),
    )
    coverage = _recovery.HumanCoverage(
        identity.EffectId("effect-1"),
        _FIXTURE_LEG_KEY,
        fact,
        identity.VenueInputId("input-1"),
    )
    ledger_type = type(book._human_coverage_ledger)
    forged = copy(book)
    object.__setattr__(
        forged,
        "_human_coverage_ledger",
        ledger_type.from_values((coverage,), lambda _value: b"\x03" * 32),
    )
    object.__setattr__(
        forged,
        "_human_coverage_by_root",
        book._human_coverage_by_root.insert_new(
            venue._coverage_root_index_key(_FIXTURE_ROOT_KEY), 0, b"\x04" * 32
        ),
    )
    return forged


def test_r20_venue_human_coverage_rows_dereference_the_ledger() -> None:
    state, _ = _authority_state_with_effects()
    book = _book_with_human_coverage(state.venue)
    selection = _root_selection(_venue_claim_selection(), "root-1")

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_human_coverage_rows(
        book, selection
    )

    assert rows[0] == "m2.venue.HumanCoverages/v1"
    assert rows[1] == 1
    row = rows[2][0]
    assert row[0] == "m2.venue.HumanCoverage/v1"
    assert len(row) == 9
    assert row[3][0] == "m1.fills.HumanAttestedFillFact/v1"
    assert row[5] is False
    assert row[6] is None and row[7] is None and row[8] is None
    checkpoint_codec._validate_checkpoint_collection(rows, "m2.venue.HumanCoverages/v1")

    with pytest.raises(ValueError, match="selected root"):
        checkpoint_codec._encode_runtime_checkpoint_venue_human_coverage_rows(
            book, _venue_claim_selection()
        )


def test_r20_venue_closure_head_rows_project_selected_legs() -> None:
    state, _ = _authority_state_with_effects()
    closure = venue.VenueTerminalClosure(
        _FIXTURE_LEG_KEY,
        identity.ClosureId("closure-1"),
        3,
        None,
        venue.VenueAttemptState.WORKING,
        values.Quantity(2),
        values.Quantity(2),
        identity.EvidenceReference("evidence-1"),
        venue.VenueClosureKind.BROKER_TERMINAL,
        identity.VenueInputId("input-1"),
    )
    book = copy(state.venue)
    object.__setattr__(
        book,
        "_closure_head_by_leg",
        state.venue._closure_head_by_leg.insert_new(
            venue._leg_index_key(_FIXTURE_LEG_KEY),
            closure,
            venue._closure_commitment(closure),
        ),
    )
    selection = _owner_selection(_venue_claim_selection(), "owner-order-1")

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_closure_head_rows(
        book, selection
    )

    assert rows[0] == "m2.venue.ClosureHeads/v1"
    assert rows[1] == 1
    row = rows[2][0]
    assert row[0] == "m2.venue.TerminalClosure/v1"
    assert len(row) == 17
    assert row[3] == 3
    assert row[4] is None
    assert row[5] == ["m1.venue.VenueAttemptState", "WORKING"]
    assert row[16] is None
    checkpoint_codec._validate_checkpoint_collection(rows, "m2.venue.ClosureHeads/v1")

    with pytest.raises(ValueError, match="selected owner"):
        checkpoint_codec._encode_runtime_checkpoint_venue_closure_head_rows(
            book, _venue_claim_selection()
        )


def _fixture_fill_reconciliation(input_value: str) -> object:
    from app.execution_core import recovery as _recovery

    return _recovery.ReconciliationRecord(
        identity.VenueInputId(input_value),
        identity.EffectId("effect-1"),
        _FIXTURE_LEG_KEY,
        values.Quantity(0),
        values.Quantity(2),
        _fixture_broker_fill_fact("recon"),
        b"\xab" * 32,
        "unsafe to apply",
    )


def _fixture_revision_reconciliation(input_value: str) -> object:
    from app.execution_core import recovery as _recovery

    return _recovery.RevisionReconciliationRecord(
        identity.VenueInputId(input_value),
        identity.EffectId("effect-1"),
        _FIXTURE_LEG_KEY,
        values.Quantity(2),
        values.Quantity(2),
        values.Quantity(3),
        BrokerTradeCorrectFact(
            key=ExecutionFactKey(
                broker=identity.BrokerId("paper"),
                environment=identity.EnvironmentId("paper"),
                account=identity.AccountId("account"),
                source_event_id=identity.SourceEventId("revision-1"),
            ),
            scope=ExecutionScope(
                broker=identity.BrokerId("paper"),
                environment=identity.EnvironmentId("paper"),
                account=identity.AccountId("account"),
                order_id=identity.OrderId("owner-order-1"),
                symbol_id=identity.SymbolId("AAPL"),
                side=ExecutionSide.BUY,
            ),
            root_fill_id=identity.RootFillId("root-1"),
            predecessor_source_event_id=identity.SourceEventId("coverage-broker"),
            revised_quantity=values.Quantity(3),
            revised_price=_FIXTURE_PRICE,
        ),
        b"\xac" * 32,
        False,
        "revision unresolved",
    )


def _book_with_reconciliations(
    book: venue.VenueRecoveryBook,
    records_by_input: tuple[tuple[str, object], ...],
) -> venue.VenueRecoveryBook:
    forged = copy(book)
    index = book._reconciliation_by_input
    for input_value, record in records_by_input:
        index = index.insert_new(
            venue._input_index_key(identity.VenueInputId(input_value)),
            record,
            b"\x03" * 32,
        )
    object.__setattr__(forged, "_reconciliation_by_input", index)
    return forged


def _reconciliation_selection() -> records._RuntimeCheckpointSelectionSet:
    return _root_selection(
        _owner_selection(_venue_claim_selection(), "owner-order-1"), "root-1"
    )


def test_r20_venue_reconciliation_rows_project_both_referenced_union_arms() -> None:
    state, _ = _authority_state_with_effects()
    book = _book_with_broker_coverage(state.venue)
    closure = venue.VenueTerminalClosure(
        _FIXTURE_LEG_KEY,
        identity.ClosureId("closure-1"),
        1,
        None,
        venue.VenueAttemptState.WORKING,
        values.Quantity(2),
        values.Quantity(2),
        identity.EvidenceReference("evidence-1"),
        venue.VenueClosureKind.BROKER_TERMINAL,
        identity.VenueInputId("input-2"),
    )
    object.__setattr__(
        book,
        "_closure_head_by_leg",
        book._closure_head_by_leg.insert_new(
            venue._leg_index_key(_FIXTURE_LEG_KEY),
            closure,
            venue._closure_commitment(closure),
        ),
    )
    book = _book_with_reconciliations(
        book,
        (
            ("input-1", _fixture_fill_reconciliation("input-1")),
            ("input-2", _fixture_revision_reconciliation("input-2")),
        ),
    )

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_reconciliation_rows(
        book, _reconciliation_selection()
    )

    assert rows[0] == "m2.venue.Reconciliations/v1"
    assert rows[1] == 2
    # Closure heads are walked before coverage, so the closure's input leads.
    assert rows[2][0][0] == "m2.venue.RevisionReconciliation/v1"
    assert len(rows[2][0]) == 11
    assert rows[2][0][10] == "revision unresolved"
    assert rows[2][1][0] == "m2.venue.FillReconciliation/v1"
    assert len(rows[2][1]) == 9
    assert rows[2][1][8] == "unsafe to apply"
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.venue.Reconciliations/v1"
    )


def test_r20_venue_reconciliation_index_refuses_an_unreferenced_input() -> None:
    state, _ = _authority_state_with_effects()
    book = _book_with_reconciliations(
        _book_with_broker_coverage(state.venue),
        (
            ("input-1", _fixture_fill_reconciliation("input-1")),
            ("input-9", _fixture_fill_reconciliation("input-9")),
        ),
    )

    with pytest.raises(ValueError, match="unreferenced input"):
        checkpoint_codec._encode_runtime_checkpoint_venue_reconciliation_rows(
            book, _reconciliation_selection()
        )


def test_r20_venue_reconciliation_refuses_a_row_outside_the_selected_legs() -> None:
    state, _ = _authority_state_with_effects()
    book = _book_with_reconciliations(
        _book_with_broker_coverage(state.venue),
        (("input-1", _fixture_fill_reconciliation("input-1")),),
    )
    selection = _root_selection(
        _owner_selection(_venue_claim_selection(), "owner-order-9"), "root-1"
    )

    with pytest.raises(ValueError, match="selected owner set"):
        checkpoint_codec._encode_runtime_checkpoint_venue_reconciliation_rows(
            book, selection
        )


_FIXTURE_POSITION_SCOPE = PositionScope(
    identity.BrokerId("paper"),
    identity.EnvironmentId("paper"),
    identity.AccountId("account"),
    identity.SymbolId("AAPL"),
)
_FIXTURE_VENUE_SCOPE = venue.VenueScope(
    _APPLICATION,
    identity.BrokerId("paper"),
    identity.EnvironmentId("paper"),
    identity.AccountId("account"),
)


def _digest(marker: int) -> bytes:
    return bytes((marker,)) * 32


def _fixture_execution_checkpoint() -> venue.VenueExecutionCheckpoint:
    return venue.VenueExecutionCheckpoint(
        position_scope=_FIXTURE_POSITION_SCOPE,
        registry_count=0,
        registry_commitment=_digest(1),
        position_commitment=_digest(2),
        root_heads_commitment=_digest(3),
        integrity_bits=0,
        account_reconciliation_required=False,
        reconciliation_transition_count=0,
        reconciliation_transition_head=_digest(4),
    )


def _fixture_transition_proof() -> venue._ProtectionTransitionProof:
    """A genesis, non-advancing, ordinary proof the venue itself calls authentic."""

    genesis = venue._protection_genesis_cursor()
    checkpoint = _fixture_execution_checkpoint()
    return venue._ProtectionTransitionProof(
        position_scope=_FIXTURE_POSITION_SCOPE,
        predecessor_cursor=genesis,
        cursor=genesis,
        predecessor_book_scope=_FIXTURE_VENUE_SCOPE,
        book_scope=_FIXTURE_VENUE_SCOPE,
        predecessor_book_commitment=_digest(5),
        book_commitment=_digest(5),
        predecessor_execution_commitment=_digest(6),
        execution_commitment=_digest(6),
        predecessor_execution_checkpoint=checkpoint,
        execution_checkpoint=checkpoint,
        predecessor_summary=venue._SymbolAuthoritySummary(),
        summary=venue._SymbolAuthoritySummary(),
        predecessor_binding=None,
        binding=None,
        predecessor_execution_binding_matches=True,
        execution_binding_matches=True,
        predecessor_account_reconciliation_clear=True,
        account_reconciliation_clear=True,
        command_commitment=_digest(7),
        disposition=venue.VenueRecoveryDisposition.REFUSED,
        quantity_delta=0,
    )


def _fixture_bootstrap_record() -> venue._BootstrapBoundTargetRecord:
    """One authentic active record minted through the venue's own constructor."""

    binding = venue.VenueExecutionBinding(
        position_scope=_FIXTURE_POSITION_SCOPE,
        position_commitment=_digest(2),
        root_heads_commitment=_digest(3),
        integrity_bits=0,
    )
    registry_input = venue._new_bootstrap_target_registry_input(
        application_generation_id=_APPLICATION,
        source_kind=venue._BootstrapSourceKind.EMPTY_ACCOUNT,
        position_scope=_FIXTURE_POSITION_SCOPE,
        source_execution_commitment=_digest(8),
        target_genesis_execution_commitment=_digest(9),
        target_execution_commitment=_digest(10),
        prior_account_registry_count=0,
        prior_account_registry_commitment=_digest(11),
        reconciliation_transition_count=0,
        reconciliation_transition_head=_digest(12),
    )
    return venue._new_bootstrap_bound_target_record(
        application_generation_id=_APPLICATION,
        position_scope=_FIXTURE_POSITION_SCOPE,
        source_kind=venue._BootstrapSourceKind.EMPTY_ACCOUNT,
        source_execution_commitment=_digest(8),
        target_genesis_execution_commitment=_digest(9),
        target_execution_commitment=_digest(10),
        binding=binding,
        account_registry_count=0,
        account_registry_commitment=_digest(11),
        reconciliation_transition_count=0,
        reconciliation_transition_head=_digest(12),
        bootstrap_input=registry_input,
        neutral_checkpoint_proof=_fixture_transition_proof(),
    )


def _fixture_consumed_bootstrap_record() -> object:
    effect = venue.BrokerEffect(
        venue.VenueEffectScope(
            _APPLICATION,
            identity.BrokerId("paper"),
            identity.EnvironmentId("paper"),
            identity.AccountId("account"),
            identity.EffectId("bootstrap-effect"),
            identity.RequestOccurrenceId("bootstrap-request"),
            identity.MandateId("bootstrap-mandate"),
            venue.EffectKind.SUBMIT,
            identity.ClientOrderId("bootstrap-coid"),
            identity.SymbolId("AAPL"),
            ExecutionSide.BUY,
            values.Quantity(1),
            b"\x07" * 32,
        )
    )
    return venue._new_consumed_bootstrap_bound_target_record(
        active_record=_fixture_bootstrap_record(),
        effect=effect,
        request_input_id=identity.VenueInputId("bootstrap-input"),
    )


def _book_with_bootstrap_target(
    book: venue.VenueRecoveryBook,
    value: object,
    position_scope: PositionScope = _FIXTURE_POSITION_SCOPE,
) -> venue.VenueRecoveryBook:
    forged = copy(book)
    object.__setattr__(
        forged,
        "_bootstrap_bound_target_by_scope",
        book._bootstrap_bound_target_by_scope.insert_new(
            venue._position_scope_index_key(position_scope), value, b"\x04" * 32
        ),
    )
    return forged


def _bootstrap_selection() -> records._RuntimeCheckpointSelectionSet:
    return _venue_claim_selection()


def test_r20_venue_transition_proof_encodes_its_twenty_five_inert_members() -> None:
    row = checkpoint_codec._encode_runtime_checkpoint_venue_transition_proof(
        _fixture_transition_proof()
    )

    assert row[0] == "m2.venue.ProtectionTransitionProof/v1"
    assert len(row) == 25
    assert row[2][0] == "m2.venue.ProtectionTransitionCursor/v1"
    assert len(row[2]) == 6
    assert row[2][4] is None and row[2][5] is None
    assert row[4][0] == "m2.venue.Scope/v1" and len(row[4]) == 5
    assert row[12][0] == "m2.venue.SymbolAuthoritySummary/v1"
    assert len(row[12]) == 10
    assert row[12][5] == ["m2.venue.StandDownEffects/v1", 0, []]
    assert row[14] is None and row[15] is None
    assert row[21] == ["m1.venue.VenueRecoveryDisposition", "REFUSED"]
    assert row[22] == 0
    assert row[23] == ["m1.venue.ProtectionTransitionSourceKind", "ORDINARY"]
    checkpoint_codec._validate_checkpoint_nested_value(row)


def test_r20_venue_transition_proof_refuses_an_inauthentic_lineage() -> None:
    proof = _fixture_transition_proof()
    forged = copy(proof)
    # An APPLIED disposition on a cursor that never advanced is exactly what the
    # venue's own lineage check rejects; the projector must not launder it.
    object.__setattr__(forged, "disposition", venue.VenueRecoveryDisposition.APPLIED)

    with pytest.raises(ValueError, match="lineage is not authentic"):
        checkpoint_codec._encode_runtime_checkpoint_venue_transition_proof(forged)


def test_r20_venue_bootstrap_target_rows_project_the_active_record() -> None:
    state, _ = _authority_state_with_effects()
    book = _book_with_bootstrap_target(state.venue, _fixture_bootstrap_record())

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_bootstrap_target_rows(
        book, _bootstrap_selection()
    )

    assert rows[0] == "m2.venue.BootstrapTargets/v1"
    assert rows[1] == 1
    row = rows[2][0]
    assert row[0] == "m2.venue.BootstrapTargetActive/v1"
    assert len(row) == 25
    assert row[3] == ["m1.venue.BootstrapSourceKind", "EMPTY_ACCOUNT"]
    assert row[7][0] == "m2.venue.ExecutionBinding/v1" and len(row[7]) == 5
    for index in (20, 24):
        assert row[index][0] == "m2.venue.ProtectionTransitionProof/v1"
        assert len(row[index]) == 25
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.venue.BootstrapTargets/v1"
    )


def test_r20_venue_bootstrap_target_rows_project_the_consumed_record() -> None:
    state, _ = _authority_state_with_effects()
    book = _book_with_bootstrap_target(
        state.venue, _fixture_consumed_bootstrap_record()
    )

    rows = checkpoint_codec._encode_runtime_checkpoint_venue_bootstrap_target_rows(
        book, _bootstrap_selection()
    )

    row = rows[2][0]
    assert row[0] == "m2.venue.BootstrapTargetConsumed/v1"
    assert len(row) == 6
    assert row[1][0] == "m2.venue.BootstrapTargetActive/v1"
    assert len(row[1]) == 25
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.venue.BootstrapTargets/v1"
    )


@pytest.mark.parametrize("value", [b"\x05" * 32, object()])
def test_r20_venue_bootstrap_target_refuses_a_staged_or_seal_value(
    value: object,
) -> None:
    state, _ = _authority_state_with_effects()
    book = _book_with_bootstrap_target(state.venue, value)

    with pytest.raises(TypeError, match="neither an active nor a consumed record"):
        checkpoint_codec._encode_runtime_checkpoint_venue_bootstrap_target_rows(
            book, _bootstrap_selection()
        )


def test_r20_venue_bootstrap_target_map_refuses_an_unselected_scope() -> None:
    state, _ = _authority_state_with_effects()
    book = _book_with_bootstrap_target(
        state.venue,
        _fixture_bootstrap_record(),
        PositionScope(
            identity.BrokerId("paper"),
            identity.EnvironmentId("paper"),
            identity.AccountId("account"),
            identity.SymbolId("MSFT"),
        ),
    )

    with pytest.raises(ValueError, match="outside the selected scope set"):
        checkpoint_codec._encode_runtime_checkpoint_venue_bootstrap_target_rows(
            book, _bootstrap_selection()
        )


def _fixture_execution_binding() -> venue.VenueExecutionBinding:
    return venue.VenueExecutionBinding(
        position_scope=_FIXTURE_POSITION_SCOPE,
        position_commitment=_digest(2),
        root_heads_commitment=_digest(3),
        integrity_bits=0,
    )


def _fixture_resolved_registry_outcome(input_value: str) -> object:
    return venue._ResolvedRegistryProjectionOutcome(
        input_id=identity.VenueInputId(input_value),
        command_commitment=_digest(13),
        target_checkpoint=_fixture_execution_checkpoint(),
        source_binding=_fixture_execution_binding(),
        resulting_registry_count=1,
        resulting_registry_commitment=_digest(14),
        reason="target registry projection retained exact source and binding proof",
    )


def _fixture_unresolved_registry_outcome(input_value: str) -> object:
    return venue._UnresolvedRegistryAdvanceOutcome(
        input_id=identity.VenueInputId(input_value),
        command_commitment=_digest(15),
        target_checkpoint=_fixture_execution_checkpoint(),
        prior_account_registry_count=0,
        prior_account_registry_commitment=_digest(16),
        prior_source_binding=_fixture_execution_binding(),
        resulting_source_binding=_fixture_execution_binding(),
        resulting_registry_count=1,
        resulting_registry_commitment=_digest(17),
        reason="canonical source advanced before venue ownership attribution",
    )


def _book_with_execution_reconciliations(
    book: venue.VenueRecoveryBook,
    records_by_input: tuple[tuple[str, object], ...],
) -> venue.VenueRecoveryBook:
    forged = copy(book)
    index = book._execution_reconciliation_by_input
    for input_value, record in records_by_input:
        index = index.insert_new(
            venue._input_index_key(identity.VenueInputId(input_value)),
            record,
            b"\x06" * 32,
        )
    object.__setattr__(forged, "_execution_reconciliation_by_input", index)
    return forged


def _fixture_refreshed_bootstrap_record(
    checkpoint_input_value: str,
) -> venue._BootstrapBoundTargetRecord:
    """An advanced record whose serving checkpoint input differs from its origin.

    The initial record must name one input for both roles, so a second referenced
    catch-up input only exists once the record has been refreshed: the constructor
    admits an explicit checkpoint input exactly when a distinct anchor proof is
    retained beside the serving one.
    """

    binding = venue.VenueExecutionBinding(
        position_scope=_FIXTURE_POSITION_SCOPE,
        position_commitment=_digest(2),
        root_heads_commitment=_digest(3),
        integrity_bits=0,
    )
    registry_input = venue._new_bootstrap_target_registry_input(
        application_generation_id=_APPLICATION,
        source_kind=venue._BootstrapSourceKind.EMPTY_ACCOUNT,
        position_scope=_FIXTURE_POSITION_SCOPE,
        source_execution_commitment=_digest(8),
        target_genesis_execution_commitment=_digest(9),
        target_execution_commitment=_digest(10),
        prior_account_registry_count=0,
        prior_account_registry_commitment=_digest(11),
        reconciliation_transition_count=0,
        reconciliation_transition_head=_digest(12),
    )
    return venue._new_bootstrap_bound_target_record(
        application_generation_id=_APPLICATION,
        position_scope=_FIXTURE_POSITION_SCOPE,
        source_kind=venue._BootstrapSourceKind.EMPTY_ACCOUNT,
        source_execution_commitment=_digest(8),
        target_genesis_execution_commitment=_digest(9),
        target_execution_commitment=_digest(18),
        binding=binding,
        account_registry_count=1,
        account_registry_commitment=_digest(19),
        reconciliation_transition_count=0,
        reconciliation_transition_head=_digest(12),
        bootstrap_input=registry_input,
        neutral_checkpoint_proof=_fixture_transition_proof(),
        bootstrap_neutral_checkpoint_proof=_fixture_transition_proof(),
        checkpoint_input_id=identity.VenueInputId(checkpoint_input_value),
        checkpoint_command_commitment=_digest(20),
    )


def _bootstrap_input_ids() -> tuple[str, str]:
    record = _fixture_bootstrap_record()
    return record.bootstrap_input_id.value, record.checkpoint_input_id.value


def test_r20_venue_execution_reconciliation_rows_project_both_union_arms() -> None:
    state, _ = _authority_state_with_effects()
    bootstrap_input, _ = _bootstrap_input_ids()
    record = _fixture_refreshed_bootstrap_record("catch-up-2")
    assert record.bootstrap_input_id.value == bootstrap_input
    assert record.checkpoint_input_id.value == "catch-up-2"
    book = _book_with_execution_reconciliations(
        _book_with_bootstrap_target(state.venue, record),
        (
            (bootstrap_input, _fixture_resolved_registry_outcome(bootstrap_input)),
            ("catch-up-2", _fixture_unresolved_registry_outcome("catch-up-2")),
        ),
    )

    rows = (
        checkpoint_codec._encode_runtime_checkpoint_venue_execution_reconciliation_rows(
            book, _bootstrap_selection()
        )
    )

    assert rows[0] == "m2.venue.ExecutionReconciliations/v1"
    assert rows[1] == 2
    # The origin input is referenced before the serving checkpoint input.
    resolved, unresolved = rows[2]
    assert resolved[0] == "m2.venue.ResolvedRegistryProjection/v1"
    assert len(resolved) == 9
    assert resolved[3][0] == "m2.venue.ExecutionCheckpoint/v1"
    assert resolved[4][0] == "m2.venue.ExecutionBinding/v1"
    assert resolved[8] == ["m1.venue.ResolvedProjectionKind", "REGISTRY_ADVANCE"]
    assert unresolved[0] == "m2.venue.UnresolvedRegistryAdvance/v1"
    assert len(unresolved) == 11
    assert unresolved[6][0] == "m2.venue.ExecutionBinding/v1"
    assert unresolved[7][0] == "m2.venue.ExecutionBinding/v1"
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.venue.ExecutionReconciliations/v1"
    )


def test_r20_venue_execution_reconciliation_refuses_an_unreferenced_input() -> None:
    state, _ = _authority_state_with_effects()
    bootstrap_input, _ = _bootstrap_input_ids()
    book = _book_with_execution_reconciliations(
        _book_with_bootstrap_target(state.venue, _fixture_bootstrap_record()),
        (
            (bootstrap_input, _fixture_resolved_registry_outcome(bootstrap_input)),
            ("catch-up-9", _fixture_resolved_registry_outcome("catch-up-9")),
        ),
    )

    with pytest.raises(ValueError, match="unreferenced input"):
        checkpoint_codec._encode_runtime_checkpoint_venue_execution_reconciliation_rows(
            book, _bootstrap_selection()
        )


def test_r20_venue_execution_reconciliation_refuses_a_row_outside_the_scopes() -> None:
    state, _ = _authority_state_with_effects()
    bootstrap_input, _ = _bootstrap_input_ids()
    outcome = venue._ResolvedRegistryProjectionOutcome(
        input_id=identity.VenueInputId(bootstrap_input),
        command_commitment=_digest(13),
        target_checkpoint=venue.VenueExecutionCheckpoint(
            position_scope=PositionScope(
                identity.BrokerId("paper"),
                identity.EnvironmentId("paper"),
                identity.AccountId("account"),
                identity.SymbolId("MSFT"),
            ),
            registry_count=0,
            registry_commitment=_digest(1),
            position_commitment=_digest(2),
            root_heads_commitment=_digest(3),
            integrity_bits=0,
            account_reconciliation_required=False,
            reconciliation_transition_count=0,
            reconciliation_transition_head=_digest(4),
        ),
        source_binding=venue.VenueExecutionBinding(
            position_scope=PositionScope(
                identity.BrokerId("paper"),
                identity.EnvironmentId("paper"),
                identity.AccountId("account"),
                identity.SymbolId("MSFT"),
            ),
            position_commitment=_digest(2),
            root_heads_commitment=_digest(3),
            integrity_bits=0,
        ),
        resulting_registry_count=1,
        resulting_registry_commitment=_digest(14),
        reason="target registry projection retained exact source and binding proof",
    )
    book = _book_with_execution_reconciliations(
        _book_with_bootstrap_target(state.venue, _fixture_bootstrap_record()),
        ((bootstrap_input, outcome),),
    )

    with pytest.raises(ValueError, match="selected scope set"):
        checkpoint_codec._encode_runtime_checkpoint_venue_execution_reconciliation_rows(
            book, _bootstrap_selection()
        )


_ACQ_GENERATION = identity.AcquisitionGenerationId("ab" * 32)
_ACQ_SUCCESSOR_GENERATION = identity.AcquisitionGenerationId("cd" * 32)


def _effect_permit(
    effect_value: str = "acq-effect-1",
    *,
    generation_id: identity.AcquisitionGenerationId = _ACQ_GENERATION,
) -> authority.AcquisitionEffectPermit:
    """Mint one real effect permit through the authority constructor, not by hand."""

    return authority._new_acquisition_effect_permit(
        input_id=authority.AuthorityInputId(f"{effect_value}-input"),
        application_generation_id=_APPLICATION,
        position_scope=_DORMANT_POSITION_SCOPE,
        session_id=authority.SessionId("permit-session"),
        generation_id=generation_id,
        acquisition_mandate_id=identity.AcquisitionMandateId("acq-mandate"),
        protection_mandate_id=identity.MandateId("prot-mandate"),
        binding_commitment=bytes.fromhex("11" * 32),
        emergency_recovery_compatibility_commitment=bytes.fromhex("22" * 32),
        predecessor_controller_head=bytes.fromhex("32" * 32),
        controller_head=bytes.fromhex("33" * 32),
        successor_ordinal=3,
        execution_snapshot_commitment=bytes.fromhex("44" * 32),
        scope_execution_commitment=bytes.fromhex("55" * 32),
        venue_commitment=bytes.fromhex("66" * 32),
        authority_context_commitment=bytes.fromhex("77" * 32),
        protection_commitment=bytes.fromhex("bb" * 32),
        terms=authority.AcquisitionEffectTerms(
            quantity=values.Quantity(2),
            limit_price=_FIXTURE_PRICE,
            order_type=authority.AcquisitionOrderType.LIMIT,
            evaluation_time=17,
        ),
        effect_id=identity.EffectId(effect_value),
        request_occurrence_id=identity.RequestOccurrenceId(f"{effect_value}-request"),
        client_order_id=identity.ClientOrderId(f"{effect_value}-coid"),
    )


def _currentness_entry() -> object:
    return authority._new_acquisition_currentness_entry(
        source_kind=authority._AcquisitionCurrentnessSourceKind.CANONICAL_FACT,
        application_generation_id=_APPLICATION,
        position_scope=_DORMANT_POSITION_SCOPE,
        session_id=authority.SessionId("permit-session"),
        generation_id=_ACQ_GENERATION,
        acquisition_mandate_id=identity.AcquisitionMandateId("acq-mandate"),
        protection_mandate_id=identity.MandateId("prot-mandate"),
        binding_commitment=bytes.fromhex("11" * 32),
        emergency_recovery_compatibility_commitment=bytes.fromhex("22" * 32),
        controller_head=bytes.fromhex("33" * 32),
        successor_ordinal=3,
        scope_execution_commitment=bytes.fromhex("55" * 32),
        venue_commitment=bytes.fromhex("66" * 32),
        protection_commitment=bytes.fromhex("bb" * 32),
        predecessor_slot_commitment=bytes.fromhex("cc" * 32),
    )


def _state_with_acquisition_slot(
    state: authority.ExecutionAuthorityState,
    *,
    inactive: bool = False,
    empty: bool = False,
) -> authority.ExecutionAuthorityState:
    """Install one authentic slot for the fixture scope through real constructors."""

    forged = copy(state)
    slot_key = authority._acquisition_scope_key(_APPLICATION, _DORMANT_POSITION_SCOPE)
    object.__setattr__(
        forged,
        "_acquisition_currentness_by_scope",
        state._acquisition_currentness_by_scope.insert_new(
            slot_key, _currentness_entry(), b"\x11" * 32
        ),
    )
    if empty:
        return forged
    permit = _effect_permit()
    descriptor = authority._new_acquisition_effect_descriptor(permit)
    active = authority._new_acquisition_active_effect(descriptor)
    scope_descriptor: object = descriptor
    scope_active: object = active
    if inactive:
        scope_descriptor = authority._new_acquisition_inactive_slot(
            active, descriptor, _ACQ_SUCCESSOR_GENERATION
        )
        scope_active = scope_descriptor
    object.__setattr__(
        forged,
        "_acquisition_descriptor_by_effect",
        state._acquisition_descriptor_by_effect.insert_new(
            authority._effect_key(permit.effect_id), descriptor, b"\x12" * 32
        ),
    )
    object.__setattr__(
        forged,
        "_acquisition_descriptor_by_scope",
        state._acquisition_descriptor_by_scope.insert_new(
            slot_key, scope_descriptor, b"\x13" * 32
        ),
    )
    object.__setattr__(
        forged,
        "_acquisition_active_by_scope",
        state._acquisition_active_by_scope.insert_new(
            slot_key, scope_active, b"\x14" * 32
        ),
    )
    return forged


def test_r20_acquisition_effect_permit_encodes_its_21_semantic_members() -> None:
    row = checkpoint_codec._encode_runtime_checkpoint_acquisition_effect_permit(
        _effect_permit()
    )

    assert row[0] == "m2.authority.AcquisitionEffectPermit/v1"
    assert len(row) == 22
    assert row[3][0] == "m1.fills.PositionScope/v1"
    assert row[12] == 3
    assert row[18][0] == "m1.authority.AcquisitionEffectTerms/v1"
    checkpoint_codec._validate_checkpoint_nested_value(row)


def test_r20_acquisition_effect_permit_refuses_an_inauthentic_member() -> None:
    permit = _effect_permit()
    forged = copy(permit)
    object.__setattr__(forged, "successor_ordinal", 4)

    with pytest.raises(ValueError, match="not authority-authentic"):
        checkpoint_codec._encode_runtime_checkpoint_acquisition_effect_permit(forged)


def test_r20_acquisition_slot_rows_project_an_active_scope() -> None:
    state, _ = _authority_state_with_effects()
    state = _state_with_acquisition_slot(state)

    rows, referenced = (
        checkpoint_codec._encode_runtime_checkpoint_acquisition_slot_rows(
            state, _APPLICATION, (_DORMANT_POSITION_SCOPE,)
        )
    )

    assert rows[0] == "m2.authority.AcquisitionSlots/v1"
    assert rows[1] == 1
    row = rows[2][0]
    assert row[0] == "m2.authority.AcquisitionSlot/v1"
    assert len(row) == 4
    assert row[2][0] == "m2.authority.AcquisitionCurrentness/v1"
    assert len(row[2]) == 16
    assert row[3][0] == "m2.authority.AcquisitionSlotActive/v1"
    assert len(row[3]) == 3
    assert referenced == (identity.EffectId("acq-effect-1"),)
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.authority.AcquisitionSlots/v1"
    )


def test_r20_acquisition_slot_rows_project_an_inactive_scope() -> None:
    state, _ = _authority_state_with_effects()
    state = _state_with_acquisition_slot(state, inactive=True)

    rows, referenced = (
        checkpoint_codec._encode_runtime_checkpoint_acquisition_slot_rows(
            state, _APPLICATION, (_DORMANT_POSITION_SCOPE,)
        )
    )

    row = rows[2][0]
    assert row[3][0] == "m2.authority.AcquisitionSlotInactive/v1"
    assert len(row[3]) == 4
    assert referenced == (identity.EffectId("acq-effect-1"),)
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.authority.AcquisitionSlots/v1"
    )


def test_r20_acquisition_slot_rows_project_an_empty_scope() -> None:
    state, _ = _authority_state_with_effects()
    state = _state_with_acquisition_slot(state, empty=True)

    rows, referenced = (
        checkpoint_codec._encode_runtime_checkpoint_acquisition_slot_rows(
            state, _APPLICATION, (_DORMANT_POSITION_SCOPE,)
        )
    )

    assert rows[2][0][3] == ["m2.authority.AcquisitionSlotEmpty/v1"]
    assert referenced == ()
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.authority.AcquisitionSlots/v1"
    )


def test_r20_acquisition_slot_rows_refuse_a_mixed_descriptor_and_active_pair() -> None:
    state, _ = _authority_state_with_effects()
    state = _state_with_acquisition_slot(state)
    slot_key = authority._acquisition_scope_key(_APPLICATION, _DORMANT_POSITION_SCOPE)
    forged = copy(state)
    permit = _effect_permit()
    descriptor = authority._new_acquisition_effect_descriptor(permit)
    active = authority._new_acquisition_active_effect(descriptor)
    object.__setattr__(
        forged,
        "_acquisition_descriptor_by_scope",
        state._acquisition_descriptor_by_scope.replace_existing(
            slot_key,
            authority._new_acquisition_inactive_slot(
                active, descriptor, _ACQ_SUCCESSOR_GENERATION
            ),
            b"\x15" * 32,
        ),
    )

    with pytest.raises(ValueError, match="mixes an inactive and active variant"):
        checkpoint_codec._encode_runtime_checkpoint_acquisition_slot_rows(
            forged, _APPLICATION, (_DORMANT_POSITION_SCOPE,)
        )


def test_r20_acquisition_slot_rows_refuse_an_unselected_scope_entry() -> None:
    state, _ = _authority_state_with_effects()
    state = _state_with_acquisition_slot(state)

    with pytest.raises(ValueError, match="currentness scope index retains"):
        checkpoint_codec._encode_runtime_checkpoint_acquisition_slot_rows(
            state, _APPLICATION, ()
        )


def test_r20_acquisition_slot_rows_refuse_a_slot_without_currentness() -> None:
    state, _ = _authority_state_with_effects()
    state = _state_with_acquisition_slot(state)
    forged = copy(state)
    object.__setattr__(
        forged,
        "_acquisition_currentness_by_scope",
        type(state._acquisition_currentness_by_scope).empty(),
    )

    with pytest.raises(ValueError, match="omits its required currentness"):
        checkpoint_codec._encode_runtime_checkpoint_acquisition_slot_rows(
            forged, _APPLICATION, (_DORMANT_POSITION_SCOPE,)
        )


def test_r20_acquisition_descriptor_rows_project_slot_and_selected_effects() -> None:
    state, _ = _authority_state_with_effects()
    state = _state_with_acquisition_slot(state)
    effect_id = identity.EffectId("acq-effect-1")

    rows = checkpoint_codec._encode_runtime_checkpoint_acquisition_descriptor_rows(
        state, (effect_id,), (effect_id, identity.EffectId("effect-1"))
    )

    assert rows[0] == "m2.authority.AcquisitionDescriptors/v1"
    # The selected effect without a descriptor contributes nothing; the slot
    # reference is not duplicated by naming the same effect twice.
    assert rows[1] == 1
    row = rows[2][0]
    assert row[0] == "m2.authority.AcquisitionDescriptor/v1"
    assert len(row) == 3
    assert row[2][0] == "m2.authority.AcquisitionEffectPermit/v1"
    checkpoint_codec._validate_checkpoint_collection(
        rows, "m2.authority.AcquisitionDescriptors/v1"
    )


def test_r20_acquisition_descriptor_rows_refuse_an_absent_slot_descriptor() -> None:
    state, _ = _authority_state_with_effects()
    state = _state_with_acquisition_slot(state)
    forged = copy(state)
    object.__setattr__(
        forged,
        "_acquisition_descriptor_by_effect",
        type(state._acquisition_descriptor_by_effect).empty(),
    )

    with pytest.raises(ValueError, match="names an absent descriptor"):
        checkpoint_codec._encode_runtime_checkpoint_acquisition_descriptor_rows(
            forged, (identity.EffectId("acq-effect-1"),), ()
        )


def _emergency_grant() -> object:
    return authority._EmergencyGrant(
        authority.EmergencyGrantId("grant-1"),
        identity.AccountId("account"),
        identity.SymbolId("AAPL"),
        authority.SessionId("effect-session"),
        authority.ActorId("operator"),
        "audited emergency override",
        identity.EvidenceReference("grant-evidence"),
    )


def test_r20_emergency_grant_encodes_its_seven_semantic_members() -> None:
    row = checkpoint_codec._encode_runtime_checkpoint_emergency_grant(
        _emergency_grant()
    )

    assert row[0] == "m2.authority.EmergencyGrant/v1"
    assert len(row) == 8
    assert row[6] == "audited emergency override"
    checkpoint_codec._validate_checkpoint_nested_value(row)


def test_r20_emergency_grant_refuses_a_member_of_the_wrong_exact_type() -> None:
    grant = _emergency_grant()
    forged = copy(grant)
    object.__setattr__(forged, "reason", "")

    with pytest.raises(ValueError):
        checkpoint_codec._encode_runtime_checkpoint_emergency_grant(forged)


def test_r20_projected_venue_and_authority_wires_pass_their_own_validators() -> None:
    """The projector's own output must satisfy the wire validator it ships with.

    Every family test above checks one collection in isolation. This is the closure
    over all of them: a fully populated book and authority state project through the
    real top-row encoders, and the resulting rows are handed straight to the
    validators the load path uses. A family that encodes a shape its own validator
    refuses cannot survive here.
    """

    state, _ = _authority_state_with_effects()
    effect_scope = state.venue._effect_by_id.get(
        venue._effect_index_key(identity.EffectId("effect-1"))
    ).effect.scope
    book = _book_with_owner_leg(state.venue, _FIXTURE_LEG_KEY, effect_scope)
    book = _book_with_bootstrap_target(
        _book_with_broker_coverage(book), _fixture_bootstrap_record()
    )
    closure = venue.VenueTerminalClosure(
        _FIXTURE_LEG_KEY,
        identity.ClosureId("closure-1"),
        1,
        None,
        venue.VenueAttemptState.WORKING,
        values.Quantity(2),
        values.Quantity(2),
        identity.EvidenceReference("evidence-1"),
        venue.VenueClosureKind.BROKER_TERMINAL,
        identity.VenueInputId("input-1"),
    )
    object.__setattr__(
        book,
        "_closure_head_by_leg",
        book._closure_head_by_leg.insert_new(
            venue._leg_index_key(_FIXTURE_LEG_KEY),
            closure,
            venue._closure_commitment(closure),
        ),
    )
    book = _book_with_reconciliations(
        book, (("input-1", _fixture_fill_reconciliation("input-1")),)
    )
    bootstrap_input, _ = _bootstrap_input_ids()
    book = _book_with_execution_reconciliations(
        book, ((bootstrap_input, _fixture_resolved_registry_outcome(bootstrap_input)),)
    )
    selection = _root_selection(
        _owner_selection(_venue_claim_selection(), "owner-order-1"), "root-1"
    )

    venue_wire, venue_commitment, venue_source_owner = (
        checkpoint_codec._encode_runtime_checkpoint_venue(book, selection)
    )

    assert venue_wire[0] == "m2.venue.State/v1"
    assert len(venue_wire) == 23
    assert venue_commitment != venue_source_owner
    checkpoint_codec._validate_runtime_checkpoint_venue_wire(venue_wire)

    authority_state = _state_with_acquisition_slot(state)
    object.__setattr__(authority_state, "venue", book)
    authority_wire, authority_commitment, authority_source_owner = (
        checkpoint_codec._encode_runtime_checkpoint_authority(
            authority_state,
            venue_commitment,
            _APPLICATION,
            (_DORMANT_POSITION_SCOPE,),
            (identity.EffectId("effect-1"),),
        )
    )

    assert authority_wire[0] == "m2.authority.Checkpoint/v1"
    assert len(authority_wire) == 14
    assert authority_commitment != authority_source_owner
    checkpoint_codec._validate_runtime_checkpoint_authority_wire(authority_wire)

    # The families this session added are populated, not the empty forms the
    # earlier refusal-only projector emitted. Each is checked by its own tag so a
    # layout change cannot silently retarget the assertion.
    for index, tag in (
        (12, "m2.venue.ClosureHeads/v1"),
        (17, "m2.venue.Reconciliations/v1"),
        (18, "m2.venue.ExecutionReconciliations/v1"),
        (20, "m2.venue.BootstrapTargets/v1"),
    ):
        assert venue_wire[index][0] == tag, (index, venue_wire[index][0])
        assert venue_wire[index][1] == 1, (tag, venue_wire[index][1])
    for index, tag in (
        (11, "m2.authority.AcquisitionDescriptors/v1"),
        (12, "m2.authority.AcquisitionSlots/v1"),
    ):
        assert authority_wire[index][0] == tag, (index, authority_wire[index][0])
        assert authority_wire[index][1] == 1, (tag, authority_wire[index][1])
