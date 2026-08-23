"""Pure R13 checkpoint carrier, wire, binding, and authenticity controls."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json

import pytest

from app.execution_core import identity
from app.execution_core.persistence import checkpoint_codec


_EXECUTION_PROFILE = "11" * 32
_MARKET_PROFILE = "22" * 32
_LOAD_BINDING = bytes.fromhex("33" * 32)
_SELECTION_BINDING = bytes.fromhex("44" * 32)


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


def _scope_row(scope_id: int) -> list[object]:
    position_scope = [
        "m1.fills.PositionScope/v1",
        ["1", "broker_id", ["paper"]],
        ["1", "environment_id", ["paper"]],
        ["1", "account_id", ["account"]],
        ["1", "symbol_id", ["AAPL"]],
    ]
    return [
        "m2.runtime-checkpoint.scope/v1",
        scope_id,
        position_scope,
        [
            "m2.acquisition.State/v1",
            ["1", "application_generation_id", ["checkpoint-app"]],
            position_scope,
            *([None] * 14),
        ],
        ["m2.position.execution-state/v1", position_scope, *([None] * 19)],
        ["m2.protection.checkpoint/v1", *([None] * 31)],
    ]


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
        carrier()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        type("Forged", (carrier,), {})


def test_loaded_decode_is_canonical_registered_and_round_trips_exact_bytes() -> None:
    payload = _outer_payload(scopes=[_scope_row(9)])

    envelope = checkpoint_codec._decode_runtime_checkpoint(payload, _LOAD_BINDING)

    assert type(envelope) is checkpoint_codec.RuntimeCheckpointEnvelope
    assert envelope.application_generation_id == identity.ApplicationGenerationId(
        "checkpoint-app"
    )
    assert envelope.currentness_head_ordinal == 7
    assert envelope.checkpoint_version_ordinal == 3
    assert envelope._provenance == "LOADED"
    assert envelope._owner_preimage is None
    assert len(envelope.scopes) == 1
    assert envelope.scopes[0].scope_id == 9
    assert envelope.payload_sha256 == hashlib.sha256(payload).hexdigest()
    assert checkpoint_codec.RuntimeCheckpointEnvelope._is_authentic(envelope)
    assert checkpoint_codec.encode_runtime_checkpoint(envelope) is payload


def test_decode_refuses_noncanonical_bytes_wrong_shape_and_scope_order() -> None:
    canonical = _outer_payload()
    spaced = canonical.replace(b",", b", ", 1)
    with pytest.raises(ValueError, match="canonical"):
        checkpoint_codec._decode_runtime_checkpoint(spaced, _LOAD_BINDING)

    wrong_outer = json.loads(canonical)
    wrong_outer.append(None)
    with pytest.raises(ValueError, match="outer envelope"):
        checkpoint_codec._decode_runtime_checkpoint(
            _canonical(wrong_outer), _LOAD_BINDING
        )

    with pytest.raises(ValueError, match="strictly ordered"):
        checkpoint_codec._decode_runtime_checkpoint(
            _outer_payload(scopes=[_scope_row(2), _scope_row(2)]), _LOAD_BINDING
        )

    zero_version = json.loads(_outer_payload())
    zero_version[6] = 0
    with pytest.raises(ValueError, match="version ordinal must be positive"):
        checkpoint_codec._decode_runtime_checkpoint(
            _canonical(zero_version), _LOAD_BINDING
        )


def test_decode_refuses_profile_alias_bad_binding_and_cross_scope_splice() -> None:
    payload = json.loads(_outer_payload(scopes=[_scope_row(1)]))
    payload[3] = "AA" * 32
    with pytest.raises(ValueError, match="execution profile"):
        checkpoint_codec._decode_runtime_checkpoint(_canonical(payload), _LOAD_BINDING)

    with pytest.raises(ValueError, match="load proof binding"):
        checkpoint_codec._decode_runtime_checkpoint(_outer_payload(), b"short")

    payload = json.loads(_outer_payload(scopes=[_scope_row(1)]))
    payload[9][2][0][4][1] = [
        "m1.fills.PositionScope/v1",
        ["1", "broker_id", ["other"]],
        ["1", "environment_id", ["paper"]],
        ["1", "account_id", ["account"]],
        ["1", "symbol_id", ["AAPL"]],
    ]
    with pytest.raises(ValueError, match="components do not agree"):
        checkpoint_codec._decode_runtime_checkpoint(_canonical(payload), _LOAD_BINDING)


def test_forgery_and_post_issuance_mutation_fail_fresh_authenticity() -> None:
    envelope = checkpoint_codec._decode_runtime_checkpoint(
        _outer_payload(), _LOAD_BINDING
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
    payload = json.loads(_outer_payload())
    envelope = checkpoint_codec._issue_projected_runtime_checkpoint(
        selection_proof_binding=_SELECTION_BINDING,
        application_generation_id=identity.ApplicationGenerationId("checkpoint-app"),
        execution_profile_id=_EXECUTION_PROFILE,
        market_source_profile_id=_MARKET_PROFILE,
        currentness_head_ordinal=7,
        checkpoint_version_ordinal=3,
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
    assert checkpoint_codec.encode_runtime_checkpoint(envelope) == _outer_payload()

    loaded = checkpoint_codec._decode_runtime_checkpoint(
        checkpoint_codec.encode_runtime_checkpoint(envelope), _LOAD_BINDING
    )
    assert loaded._provenance == "LOADED"
    assert loaded._owner_preimage is None
    assert loaded._binding != envelope._binding


def test_owner_preimage_mutation_and_scope_coordinate_splice_fail() -> None:
    payload = json.loads(_outer_payload())
    envelope = checkpoint_codec._issue_projected_runtime_checkpoint(
        selection_proof_binding=_SELECTION_BINDING,
        application_generation_id=identity.ApplicationGenerationId("checkpoint-app"),
        execution_profile_id=_EXECUTION_PROFILE,
        market_source_profile_id=_MARKET_PROFILE,
        currentness_head_ordinal=7,
        checkpoint_version_ordinal=3,
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
            currentness_head_ordinal=7,
            checkpoint_version_ordinal=3,
            venue_wire=payload[7],
            authority_wire=payload[8],
            scope_wires=(),
            venue_owner_commitment=bytes.fromhex("55" * 32),
            authority_owner_commitment=bytes.fromhex("66" * 32),
            scope_owner_commitments=((1, b"a" * 32, b"b" * 32, b"c" * 32),),
        )


def test_records_projector_seam_refuses_a_forged_contract_proof() -> None:
    with pytest.raises(TypeError, match="exact RuntimeCheckpointSelectionProof"):
        checkpoint_codec._project_runtime_checkpoint(object(), object(), object(), ())
