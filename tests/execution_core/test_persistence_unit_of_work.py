"""Pure RED/GREEN controls for the M2 atomic unit-of-work boundary."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from app.execution_core import authority
from app.execution_core.persistence import checkpoint_codec
import test_persistence_runtime_checkpoint_pure as checkpoint_fixtures


def _payload_equal_manual_contexts() -> tuple[
    object,
    authority.ExecutionAuthorityState,
    authority.ExecutionAuthorityState,
    object,
    object,
]:
    proof, book, clean, owners = checkpoint_fixtures._dormant_projection_inputs()
    _, _, source, _ = checkpoint_fixtures._manual_projection_inputs()
    flatten_id = authority.ManualFlattenId("manual-flatten-AAPL")
    manual = source._manual_by_id.get(authority._manual_key(flatten_id))
    assert manual is not None

    altered = deepcopy(clean)
    object.__setattr__(
        altered,
        "_manual_by_id",
        authority._inserted(
            clean._manual_by_id,
            authority._manual_key(flatten_id),
            manual,
        ),
    )
    clean_payload = checkpoint_codec.encode_runtime_checkpoint(
        checkpoint_codec._project_runtime_checkpoint(proof, book, clean, owners)
    )
    altered_payload = checkpoint_codec.encode_runtime_checkpoint(
        checkpoint_codec._project_runtime_checkpoint(
            proof,
            altered.venue,
            altered,
            owners,
        )
    )
    assert clean_payload == altered_payload
    return proof, clean, altered, owners[0].execution, manual


def _direct_manual_proof(
    state: authority.ExecutionAuthorityState,
    command: object,
    *,
    retained_command: authority.BeginManualFlatten | None = None,
    retained_input_bytes: bytes | None = None,
    retained_outcome_bytes: bytes | None = None,
) -> object:
    return authority._m2_authority_manual_observation_from_direct_evidence(
        state,
        command,
        retained_command=retained_command,
        retained_input_bytes=retained_input_bytes,
        retained_outcome_bytes=retained_outcome_bytes,
    )


def test_manual_kernel_ignores_unbound_payload_equal_history() -> None:
    _, clean, altered, execution, manual = _payload_equal_manual_contexts()
    begin = replace(
        manual.command,
        input_id=authority.AuthorityInputId("uow-fresh-manual-begin"),
    )
    advance = authority.AdvanceManualFlatten(
        authority.AuthorityInputId("uow-fresh-manual-advance"),
        manual.command.flatten_id,
    )

    clean_begin = authority._m2_apply_execution_authority_input(
        clean,
        execution,
        begin,
        manual_observation=_direct_manual_proof(clean, begin),
    )
    altered_begin = authority._m2_apply_execution_authority_input(
        altered,
        execution,
        begin,
        manual_observation=_direct_manual_proof(altered, begin),
    )
    assert (clean_begin.disposition, clean_begin.reason) == (
        altered_begin.disposition,
        altered_begin.reason,
    )
    public_clean_begin = authority.apply_execution_authority_input(
        clean,
        execution,
        begin,
    )
    public_altered_begin = authority.apply_execution_authority_input(
        altered,
        execution,
        begin,
    )
    assert (public_clean_begin.disposition, public_clean_begin.reason) == (
        public_altered_begin.disposition,
        public_altered_begin.reason,
    )

    clean_advance = authority._m2_apply_execution_authority_input(
        clean,
        execution,
        advance,
        manual_observation=_direct_manual_proof(clean, advance),
    )
    altered_advance = authority._m2_apply_execution_authority_input(
        altered,
        execution,
        advance,
        manual_observation=_direct_manual_proof(altered, advance),
    )
    assert (clean_advance.disposition, clean_advance.reason) == (
        altered_advance.disposition,
        altered_advance.reason,
    )
    assert clean_advance.disposition is authority.AuthorityDisposition.REFUSED
    public_clean_advance = authority.apply_execution_authority_input(
        clean,
        execution,
        advance,
    )
    public_altered_advance = authority.apply_execution_authority_input(
        altered,
        execution,
        advance,
    )
    assert (public_clean_advance.disposition, public_clean_advance.reason) == (
        public_altered_advance.disposition,
        public_altered_advance.reason,
    )


def test_manual_direct_proof_requires_retained_bytes_and_terminal_outcome() -> None:
    _, clean, _, execution, manual = _payload_equal_manual_contexts()
    begin = replace(
        manual.command,
        input_id=authority.AuthorityInputId("uow-retained-manual-begin"),
    )
    with pytest.raises(ValueError, match="retained evidence"):
        _direct_manual_proof(
            clean,
            begin,
            retained_command=manual.command,
            retained_input_bytes=b"retained-input",
        )

    retained = _direct_manual_proof(
        clean,
        begin,
        retained_command=manual.command,
        retained_input_bytes=b"retained-input",
        retained_outcome_bytes=b"retained-terminal-outcome",
    )
    result = authority._m2_apply_execution_authority_input(
        clean,
        execution,
        begin,
        manual_observation=retained,
    )
    assert result.disposition is authority.AuthorityDisposition.CONFLICT


def test_manual_active_current_direct_proof_matches_public_owner_route() -> None:
    _, _, state, owners = checkpoint_fixtures._manual_projection_inputs()
    flatten_id = authority.ManualFlattenId("manual-flatten-AAPL")
    manual = state._manual_by_id.get(authority._manual_key(flatten_id))
    assert manual is not None
    advance = authority.AdvanceManualFlatten(
        authority.AuthorityInputId("uow-active-manual-advance"),
        flatten_id,
    )
    proof = _direct_manual_proof(
        state,
        advance,
        retained_command=manual.command,
        retained_input_bytes=b"retained-input",
        retained_outcome_bytes=b"retained-terminal-outcome",
    )

    direct = authority._m2_apply_execution_authority_input(
        state,
        owners[0].execution,
        advance,
        manual_observation=proof,
    )
    public = authority.apply_execution_authority_input(
        state,
        owners[0].execution,
        advance,
    )
    assert (direct.disposition, direct.reason, direct.state) == (
        public.disposition,
        public.reason,
        public.state,
    )


def test_manual_observation_proof_is_owner_issued_and_required() -> None:
    _, clean, _, execution, manual = _payload_equal_manual_contexts()
    begin = replace(
        manual.command,
        input_id=authority.AuthorityInputId("uow-forged-manual-proof"),
    )
    with pytest.raises(TypeError, match="owner-issued"):
        authority._M2AuthorityManualObservationProof()
    forged = object.__new__(authority._M2AuthorityManualObservationProof)
    with pytest.raises(ValueError, match="observation proof"):
        authority._m2_apply_execution_authority_input(
            clean,
            execution,
            begin,
            manual_observation=forged,
        )
