"""Checkpoint-codec boundary for authenticated current-proof adaptation.

This module owns fixed checkpoint component encodings and the safe bridge from
a repository-issued current proof to the protection hydrator.  It never selects
rows, opens a connection, or serializes arbitrary Python objects.
"""

from __future__ import annotations as _annotations

from dataclasses import dataclass as _dataclass
from typing import TypeVar as _TypeVar
from typing import cast as _cast

from .. import durable_codec as _durable_codec
from .. import identity as _identity
from .. import protection as _protection
from .. import values as _values
from . import operations as _operations
from . import records as _records


_M2_PROTECTION_CHECKPOINT_TAG = "m2.protection.checkpoint/v1"
_M1ValueT = _TypeVar("_M1ValueT")


@_dataclass(frozen=True, slots=True, init=False)
class RuntimeCheckpointEnvelope:
    """Reserved exact checkpoint shape; only its completed owner codec may issue it."""

    contract_version: int
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    market_source_profile_id: str
    currentness_head_ordinal: int
    checkpoint_version_ordinal: int
    authority_state: object
    scope_states: tuple[object, ...]
    active_or_unresolved_effect_refs: tuple[object, ...]
    active_or_unresolved_route_refs: tuple[object, ...]
    payload_sha256: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("RuntimeCheckpointEnvelope is codec-issued")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("RuntimeCheckpointEnvelope cannot be subclassed")


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


__all__ = ("RuntimeCheckpointEnvelope",)
