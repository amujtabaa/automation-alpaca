"""Pure R13 checkpoint carrier, wire, binding, and authenticity controls."""

from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import inspect
import json
import struct
from typing import Any

import pytest

from app.execution_core import authority, identity, profiles, venue
from app.execution_core.fills import PositionScope
from app.execution_core.position import ExecutionSnapshot
from app.execution_core.persistence import checkpoint_codec, records


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


def test_owner_projector_refuses_spliced_authority_and_nonempty_source_order() -> None:
    proof = _selection_proof()
    book, state = _empty_owners()
    other_book, other_state = _empty_owners("other-account")

    with pytest.raises(ValueError, match="selected venue owner"):
        checkpoint_codec._project_runtime_checkpoint(proof, book, other_state, ())

    sequence_type = type(book._effect_order)
    object.__setattr__(
        book,
        "_effect_order",
        sequence_type.from_values(
            (identity.EffectId("unselected-effect"),), lambda _value: b"x" * 32
        ),
    )
    with pytest.raises((RuntimeError, ValueError)):
        checkpoint_codec._project_runtime_checkpoint(proof, book, state, ())
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


def test_r20_both_venue_commitments_track_every_selected_source_member() -> None:
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
