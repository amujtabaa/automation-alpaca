"""Checkpoint-codec boundary for authenticated current-proof adaptation.

This module owns fixed checkpoint component encodings and the safe bridge from
a repository-issued current proof to the protection hydrator.  It never selects
rows, opens a connection, or serializes arbitrary Python objects.
"""

from __future__ import annotations as _annotations

from typing import TypeVar as _TypeVar
from typing import cast as _cast

from .. import durable_codec as _durable_codec
from .. import identity as _identity
from .. import position as _position
from .. import protection as _protection
from .. import values as _values
from . import operations as _operations
from . import records as _records


_M2_PROTECTION_CHECKPOINT_TAG = "m2.protection.checkpoint/v1"
_M2_EXECUTION_STATE_TAG = "m2.position.execution-state/v1"
_M2_TAIL_FOLD_INPUT_TAG = "m2.position.tail-fold-input/v1"
_M1ValueT = _TypeVar("_M1ValueT")


def _encode_m2_protection_policy(value: object) -> list[str]:
    """Encode the checkpoint-owned protection policy without a generic enum path."""

    if type(value) is not _protection.ProtectionPolicy:
        raise TypeError("protection policy must be exact ProtectionPolicy")
    return ["m2.protection.ProtectionPolicy", value.value]


def _decode_m2_protection_policy(value: object) -> _protection.ProtectionPolicy:
    """Decode one exact checkpoint-owned policy enum pair."""

    if type(value) is not list or len(value) != 2:
        raise ValueError("protection policy must be a two-member array")
    owner_tag, member = value
    if owner_tag != "m2.protection.ProtectionPolicy" or type(member) is not str:
        raise ValueError("protection policy tag is not admitted")
    try:
        decoded = _protection.ProtectionPolicy(member)
    except ValueError as error:
        raise ValueError("protection policy value is not admitted") from error
    if _encode_m2_protection_policy(decoded) != value:
        raise ValueError("protection policy is not canonical")
    return decoded


def _encode_m2_optional_m1_value(value: object) -> list[object] | None:
    """Encode one explicitly optional owned M1 value for a fixed field."""

    return (
        None
        if value is None
        else _operations._encode_m2_m1_atom(_cast(_durable_codec._OwningValue, value))
    )


def _decode_m2_optional_m1_value(
    name: str,
    value: object,
    expected: type[_M1ValueT],
) -> _M1ValueT | None:
    """Decode one explicitly optional owned M1 value for a fixed field."""

    return _operations._decode_m2_optional_m1_as(name, value, expected)


def _decode_m2_optional_exact_int(name: str, value: object) -> int | None:
    """Decode one explicitly optional exact integer checkpoint field."""

    if value is None:
        return None
    return _operations._require_exact_int(name, value)


def _decode_m2_exact_bool(name: str, value: object) -> bool:
    """Decode one exact Boolean checkpoint field."""

    if type(value) is not bool:
        raise TypeError(f"{name} must be exact bool")
    return value


def _encode_m2_basis_authority(value: object) -> list[str]:
    """Encode the closed M2 execution basis-authority enum."""

    if type(value) is not _position.BasisAuthority:
        raise TypeError("basis authority must be exact BasisAuthority")
    return ["m2.position.BasisAuthority", value.value]


def _decode_m2_basis_authority(value: object) -> _position.BasisAuthority:
    """Decode one exact M2 execution basis-authority enum pair."""

    if type(value) is not list or len(value) != 2:
        raise ValueError("basis authority must be a two-member array")
    owner_tag, member = value
    if owner_tag != "m2.position.BasisAuthority" or type(member) is not str:
        raise ValueError("basis authority tag is not admitted")
    try:
        decoded = _position.BasisAuthority(member)
    except ValueError as error:
        raise ValueError("basis authority value is not admitted") from error
    if _encode_m2_basis_authority(decoded) != value:
        raise ValueError("basis authority is not canonical")
    return decoded


def _encode_m2_position_integrity(value: object) -> list[object]:
    """Encode the exact closed bit set for one M2 execution state."""

    if type(value) is not _position.PositionIntegrity:
        raise TypeError("position integrity must be exact PositionIntegrity")
    return ["m2.position.PositionIntegrity", value.value]


def _decode_m2_position_integrity(value: object) -> _position.PositionIntegrity:
    """Decode one exact closed M2 position-integrity enum pair."""

    if type(value) is not list or len(value) != 2:
        raise ValueError("position integrity must be a two-member array")
    owner_tag, member = value
    if owner_tag != "m2.position.PositionIntegrity" or type(member) is not int:
        raise ValueError("position integrity tag is not admitted")
    try:
        decoded = _position.PositionIntegrity(member)
    except ValueError as error:
        raise ValueError("position integrity value is not admitted") from error
    if _encode_m2_position_integrity(decoded) != value:
        raise ValueError("position integrity is not canonical")
    return decoded


def _encode_m2_optional_exact_basis(
    value: _values.ExactBasis | None,
) -> list[object] | None:
    """Encode one explicitly optional exact long-basis value."""

    if value is None:
        return None
    if type(value) is not _values.ExactBasis:
        raise TypeError("cost basis must be exact ExactBasis")
    return _operations._encode_m2_fraction(value.value)


def _decode_m2_optional_exact_basis(value: object) -> _values.ExactBasis | None:
    """Decode one explicitly optional exact long-basis value."""

    if value is None:
        return None
    return _values.ExactBasis(_operations._decode_m2_fraction(value))


def _encode_m2_tail_fold_input(value: object) -> list[object]:
    """Encode the exact bounded predecessor proof for one tail fold."""

    if type(value) is not _position.FoldInput:
        raise TypeError("tail fold input must be exact FoldInput")
    if not value.is_bound:
        raise ValueError("tail fold input must carry a bound predecessor proof")
    return [
        _M2_TAIL_FOLD_INPUT_TAG,
        value.raw_quantity,
        _operations._encode_m2_fraction(value.cost_basis.value),
        _encode_m2_optional_m1_value(value.price_metadata),
        (
            None
            if value.position_scope is None
            else _operations._encode_m2_position_scope(value.position_scope)
        ),
        _encode_m2_optional_m1_value(value.tail_root_key),
        value.prefix_count,
        _operations._encode_m2_bytes(value.prefix_heads_commitment),
    ]


def _decode_m2_tail_fold_input(value: object) -> _position.FoldInput:
    """Decode and re-encode one exact bounded tail-fold predecessor proof."""

    fields = _operations._require_m2_aggregate(value, _M2_TAIL_FOLD_INPUT_TAG, 7)
    scope = (
        None if fields[3] is None else _operations._decode_m2_position_scope(fields[3])
    )
    decoded = _position.FoldInput(
        _operations._require_exact_int("tail fold raw quantity", fields[0]),
        _values.ExactBasis(_operations._decode_m2_fraction(fields[1])),
        _decode_m2_optional_m1_value(
            "tail fold price metadata",
            fields[2],
            _values.ReportedPrice,
        ),
        scope,
        _decode_m2_optional_m1_value(
            "tail fold root key",
            fields[4],
            _identity.RootFillKey,
        ),
        _operations._require_exact_int("tail fold prefix count", fields[5]),
        _operations._decode_m2_bytes("tail fold prefix commitment", fields[6]),
    )
    if not decoded.is_bound:
        raise ValueError("tail fold input must carry a bound predecessor proof")
    if _encode_m2_tail_fold_input(decoded) != value:
        raise ValueError("tail fold input is not canonical")
    return decoded


def _encode_m2_execution_state_component(state: object) -> list[object]:
    """Encode every bounded execution-state member in frozen field order."""

    if type(state) is not _position._M2ExecutionState:
        raise TypeError("state must be exact _M2ExecutionState")
    if not _position._m2_execution_state_is_authentic(state):
        raise ValueError("execution state is not authentic")
    return [
        _M2_EXECUTION_STATE_TAG,
        _operations._encode_m2_position_scope(state.scope),
        state.raw_quantity,
        _encode_m2_basis_authority(state.basis_authority),
        _encode_m2_optional_exact_basis(state.cost_basis),
        _encode_m2_optional_m1_value(state.basis_price_metadata),
        None
        if state.tail_fold_input is None
        else _encode_m2_tail_fold_input(state.tail_fold_input),
        _encode_m2_position_integrity(state.integrity_floor),
        _encode_m2_position_integrity(state.integrity),
        state.account_reconciliation_required,
        state.reconciliation_transition_count,
        _operations._encode_m2_bytes(state.reconciliation_transition_head),
        state.root_count,
        _operations._encode_m2_bytes(state.root_order_commitment),
        _operations._encode_m2_bytes(state.head_ids_commitment),
        _operations._encode_m2_bytes(state.root_heads_commitment),
        _operations._encode_m2_bytes(state.seen_facts_commitment),
        _operations._encode_m2_bytes(state.root_head_map_commitment),
        _operations._encode_m2_bytes(state.seen_fact_map_commitment),
        _operations._encode_m2_bytes(state.root_claim_map_commitment),
        _operations._encode_m2_bytes(state.commitment),
    ]


def _decode_m2_execution_state_component(
    value: object,
    proof: _position._M2ExecutionObservationProof,
) -> _position._M2ExecutionState:
    """Decode only through the owner's aggregate-bound direct-proof seam."""

    fields = _operations._require_m2_aggregate(value, _M2_EXECUTION_STATE_TAG, 20)
    decoded_fields = (
        _operations._decode_m2_position_scope(fields[0]),
        _operations._require_exact_int("execution state raw quantity", fields[1]),
        _decode_m2_basis_authority(fields[2]),
        _decode_m2_optional_exact_basis(fields[3]),
        _decode_m2_optional_m1_value(
            "execution state basis price metadata", fields[4], _values.ReportedPrice
        ),
        None if fields[5] is None else _decode_m2_tail_fold_input(fields[5]),
        _decode_m2_position_integrity(fields[6]),
        _decode_m2_position_integrity(fields[7]),
        _decode_m2_exact_bool("execution state reconciliation required", fields[8]),
        _operations._require_exact_int(
            "execution state reconciliation transition count", fields[9]
        ),
        _operations._decode_m2_bytes(
            "execution state reconciliation transition head", fields[10]
        ),
        _operations._require_exact_int("execution state root count", fields[11]),
        _operations._decode_m2_bytes(
            "execution state root order commitment", fields[12]
        ),
        _operations._decode_m2_bytes("execution state head ids commitment", fields[13]),
        _operations._decode_m2_bytes(
            "execution state root heads commitment", fields[14]
        ),
        _operations._decode_m2_bytes(
            "execution state seen facts commitment", fields[15]
        ),
        _operations._decode_m2_bytes(
            "execution state root head map commitment", fields[16]
        ),
        _operations._decode_m2_bytes(
            "execution state seen fact map commitment", fields[17]
        ),
        _operations._decode_m2_bytes(
            "execution state root claim map commitment", fields[18]
        ),
    )
    decoded = _position._m2_execution_state_from_direct_proof(decoded_fields, proof)
    retained_commitment = _operations._decode_m2_bytes(
        "execution state commitment", fields[19]
    )
    if retained_commitment != decoded.commitment:
        raise ValueError("execution state is not authentic")
    if _encode_m2_execution_state_component(decoded) != value:
        raise ValueError("execution state component is not canonical")
    return decoded


def _encode_m2_protection_checkpoint_component(
    checkpoint: object,
) -> list[object]:
    """Encode every fixed protection checkpoint member in frozen field order."""

    if type(checkpoint) is not _protection._M2ProtectionCheckpoint:
        raise TypeError("checkpoint must be exact _M2ProtectionCheckpoint")
    if not _protection._m2_protection_checkpoint_is_authentic(checkpoint):
        raise ValueError("protection checkpoint is not authentic")
    return [
        _M2_PROTECTION_CHECKPOINT_TAG,
        _encode_m2_protection_policy(checkpoint.policy),
        _operations._encode_m2_protection_mandate(checkpoint.mandate),
        checkpoint.raw_quantity,
        _operations._encode_m2_bytes(checkpoint.execution_commitment),
        checkpoint.formula_available,
        _encode_m2_optional_m1_value(checkpoint.armed_hard_bail_trigger),
        _encode_m2_optional_m1_value(checkpoint.activation_price),
        _encode_m2_optional_m1_value(checkpoint.high_watermark),
        _encode_m2_optional_m1_value(checkpoint.trail),
        checkpoint.waiting_buy_resolution,
        _operations._encode_m2_bytes(checkpoint.commitment),
        checkpoint.cursor_ordinal,
        _operations._encode_m2_bytes(checkpoint.cursor_head),
        checkpoint.market_occurrence_epoch,
        checkpoint.market_committed_epoch,
        checkpoint.market_expected_epoch,
        checkpoint.market_source_sequence,
        checkpoint.market_source_time,
        checkpoint.market_evaluation_time,
        _encode_m2_optional_m1_value(checkpoint.market_occurrence_identity),
        checkpoint.market_halted,
        checkpoint.market_baseline_required,
        checkpoint.market_exhausted,
        _encode_m2_optional_m1_value(checkpoint.market_last_primary),
        _encode_m2_optional_m1_value(checkpoint.hard_bid_identity),
        checkpoint.hard_bid_source_time,
        _encode_m2_optional_m1_value(checkpoint.trade_identity),
        checkpoint.trade_source_time,
        _encode_m2_optional_m1_value(checkpoint.trail_bid_identity),
        checkpoint.trail_bid_source_time,
        _operations._encode_m2_bytes(checkpoint.exit_provenance),
    ]


def _decode_m2_protection_checkpoint_component(
    value: object,
) -> _protection._M2ProtectionCheckpoint:
    """Decode and re-encode one exact fixed protection checkpoint component."""

    fields = _operations._require_m2_aggregate(
        value,
        _M2_PROTECTION_CHECKPOINT_TAG,
        31,
    )
    formula_available = _decode_m2_exact_bool(
        "protection checkpoint formula availability", fields[4]
    )
    waiting_buy_resolution = _decode_m2_exact_bool(
        "protection checkpoint waiting-buy resolution", fields[9]
    )
    market_halted = _decode_m2_exact_bool(
        "protection checkpoint market halted", fields[20]
    )
    market_baseline_required = _decode_m2_exact_bool(
        "protection checkpoint market baseline required", fields[21]
    )
    market_exhausted = _decode_m2_exact_bool(
        "protection checkpoint market exhausted", fields[22]
    )
    decoded = _protection._M2ProtectionCheckpoint(
        _decode_m2_protection_policy(fields[0]),
        _operations._decode_m2_protection_mandate(fields[1]),
        _operations._require_exact_int("protection checkpoint raw quantity", fields[2]),
        _operations._decode_m2_bytes(
            "protection checkpoint execution commitment", fields[3]
        ),
        formula_available,
        _decode_m2_optional_m1_value(
            "protection checkpoint armed trigger",
            fields[5],
            _values.ReportedPrice,
        ),
        _decode_m2_optional_m1_value(
            "protection checkpoint activation price",
            fields[6],
            _values.ReportedPrice,
        ),
        _decode_m2_optional_m1_value(
            "protection checkpoint high watermark",
            fields[7],
            _values.ReportedPrice,
        ),
        _decode_m2_optional_m1_value(
            "protection checkpoint trail",
            fields[8],
            _values.ReportedPrice,
        ),
        waiting_buy_resolution,
        _operations._decode_m2_bytes("protection checkpoint commitment", fields[10]),
        _operations._require_exact_int(
            "protection checkpoint cursor ordinal", fields[11]
        ),
        _operations._decode_m2_bytes("protection checkpoint cursor head", fields[12]),
        _decode_m2_optional_exact_int(
            "protection checkpoint occurrence epoch", fields[13]
        ),
        _decode_m2_optional_exact_int(
            "protection checkpoint committed epoch", fields[14]
        ),
        _decode_m2_optional_exact_int(
            "protection checkpoint expected epoch", fields[15]
        ),
        _decode_m2_optional_exact_int(
            "protection checkpoint source sequence", fields[16]
        ),
        _decode_m2_optional_exact_int("protection checkpoint source time", fields[17]),
        _decode_m2_optional_exact_int(
            "protection checkpoint evaluation time", fields[18]
        ),
        _decode_m2_optional_m1_value(
            "protection checkpoint occurrence identity",
            fields[19],
            _identity.MarketOccurrenceId,
        ),
        market_halted,
        market_baseline_required,
        market_exhausted,
        _decode_m2_optional_m1_value(
            "protection checkpoint last primary",
            fields[23],
            _values.ReportedPrice,
        ),
        _decode_m2_optional_m1_value(
            "protection checkpoint hard bid identity",
            fields[24],
            _identity.MarketOccurrenceId,
        ),
        _decode_m2_optional_exact_int(
            "protection checkpoint hard bid time", fields[25]
        ),
        _decode_m2_optional_m1_value(
            "protection checkpoint trade identity",
            fields[26],
            _identity.MarketOccurrenceId,
        ),
        _decode_m2_optional_exact_int("protection checkpoint trade time", fields[27]),
        _decode_m2_optional_m1_value(
            "protection checkpoint trail bid identity",
            fields[28],
            _identity.MarketOccurrenceId,
        ),
        _decode_m2_optional_exact_int(
            "protection checkpoint trail bid time", fields[29]
        ),
        _operations._decode_m2_bytes(
            "protection checkpoint exit provenance", fields[30]
        ),
    )
    if not _protection._m2_protection_checkpoint_is_authentic(decoded):
        raise ValueError("protection checkpoint is not authentic")
    if _encode_m2_protection_checkpoint_component(decoded) != value:
        raise ValueError("protection checkpoint component is not canonical")
    return decoded


def _m2_protection_authority_proof_from_current_proof(
    checkpoint: _protection._M2ProtectionCheckpoint,
    current_proof: _records.CurrentProofSlice,
) -> _protection._M2ProtectionAuthorityProof:
    """Issue protection authority only from one sealed repository current proof."""

    if type(checkpoint) is not _protection._M2ProtectionCheckpoint:
        raise TypeError("checkpoint must be exact _M2ProtectionCheckpoint")
    if type(current_proof) is not _records.CurrentProofSlice:
        raise TypeError("current_proof must be exact CurrentProofSlice")
    if not _records.CurrentProofSlice._is_authentic(current_proof):
        raise ValueError("current_proof is not repository-authentic")
    authority = current_proof.protection_authority
    stream = current_proof.market_stream_authority
    if (
        type(stream) is not _records.MarketStreamAuthorityRecord
        or type(authority.active_stream_generation_id)
        is not _identity.MarketStreamGenerationId
        or type(authority.active_acquisition_generation_id)
        is not _identity.AcquisitionGenerationId
        or type(authority.active_generation_mandate_commitment_sha256) is not str
        or type(authority.active_source_profile_id) is not str
        or type(authority.active_session_id) is not _identity.SessionId
        or type(authority.active_sequence_mode) is not str
    ):
        raise ValueError("current_proof has no complete active protection authority")
    return _protection._m2_issue_protection_authority_proof(
        _protection._M2ProtectionAuthorityProof,
        current_proof.application_generation.application_generation_id,
        current_proof.execution_profile.connection_profile_id,
        current_proof.market_source_profile.market_source_profile_id,
        current_proof.scope.scope_id,
        checkpoint.mandate.position_scope,
        current_proof.symbol_controller.currentness_head_ordinal,
        current_proof.symbol_controller.live_acquisition_generation_id,
        authority.authority_class,
        authority.active_stream_generation_id,
        authority.active_acquisition_generation_id,
        authority.active_generation_mandate_commitment_sha256,
        authority.active_source_profile_id,
        authority.active_session_id,
        _protection.MarketSequenceMode(authority.active_sequence_mode),
        authority.expected_controller_head_ordinal,
        authority.state_commitment_sha256,
        authority.version_ordinal,
        checkpoint.mandate.evidence_policy.source_id,
    )


__all__: tuple[str, ...] = ()
