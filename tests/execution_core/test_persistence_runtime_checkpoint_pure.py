"""Pure R13 checkpoint carrier, wire, binding, and authenticity controls."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from typing import Any

import pytest

from app.execution_core import authority, identity, profiles, venue
from app.execution_core.persistence import checkpoint_codec, records


_EXECUTION_PROFILE = "11" * 32
_MARKET_PROFILE = "22" * 32
_LOAD_BINDING = bytes.fromhex("33" * 32)
_SELECTION_BINDING = bytes.fromhex("44" * 32)
_APPLICATION = identity.ApplicationGenerationId("checkpoint-app")


def _canonical(value: list[object]) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


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
) -> records.RuntimeCheckpointSelectionProof:
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
    assert first._owner_preimage.venue_owner_commitment == (
        first_book._protection_commitment
    )
    assert first._owner_preimage != second._owner_preimage
    assert first._binding != second._binding
