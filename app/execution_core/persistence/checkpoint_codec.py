"""Narrow checkpoint-codec boundary for authenticated current-proof adaptation.

The complete canonical checkpoint encoder/decoder remains owner work within
WO-0168a.  This module already owns the one safe bridge from a repository-issued
current proof to the protection hydrator; it never selects rows or opens a
connection itself.
"""

from __future__ import annotations as _annotations

from dataclasses import dataclass as _dataclass

from .. import identity as _identity
from .. import protection as _protection
from . import records as _records


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
