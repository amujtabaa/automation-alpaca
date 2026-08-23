"""Pure durable-input and decision-receipt contracts for WO-0168a."""

from __future__ import annotations

from hashlib import sha256

import pytest

from app.execution_core.identity import (
    AcquisitionGenerationId,
    ApplicationGenerationId,
    MarketStreamGenerationId,
    SessionId,
)
from app.execution_core.persistence import operations, records


def test_durable_input_record_binds_exact_coordinate_shape_and_payload() -> None:
    payload = b"execution-core/m2-document/v1\n\x01\x00\x00\x00\x00\x00\x00\x00\x02[]"
    record = records.DurableInputRecord(
        ApplicationGenerationId("durable-input-app"),
        "ab" * 32,
        7,
        operations.OperationDomain.MARKET_OCCURRENCE,
        SessionId("durable-input-session"),
        AcquisitionGenerationId("cd" * 32),
        "ef" * 32,
        MarketStreamGenerationId("01" * 32),
        "02" * 32,
        1,
        payload,
        sha256(payload).hexdigest(),
        "CLAIMED",
        1,
    )

    assert record.canonical_payload_bytes == payload
    assert record.payload_sha256 == sha256(payload).hexdigest()

    with pytest.raises(ValueError, match="market coordinates"):
        records.DurableInputRecord(
            record.application_generation_id,
            record.execution_profile_id,
            record.scope_id,
            record.input_domain,
            None,
            record.acquisition_generation_id,
            record.market_source_profile_id,
            record.stream_generation_id,
            record.input_identity_sha256,
            record.operation_contract_version,
            record.canonical_payload_bytes,
            record.payload_sha256,
            record.technical_state,
            record.created_ordinal,
        )
    with pytest.raises(ValueError, match="technical state"):
        records.DurableInputRecord(
            record.application_generation_id,
            record.execution_profile_id,
            record.scope_id,
            record.input_domain,
            record.session_id,
            record.acquisition_generation_id,
            record.market_source_profile_id,
            record.stream_generation_id,
            record.input_identity_sha256,
            record.operation_contract_version,
            record.canonical_payload_bytes,
            record.payload_sha256,
            "UNKNOWN",
            record.created_ordinal,
        )


def test_durable_input_record_keeps_passive_venue_session_optional_only() -> None:
    payload = b"passive-venue-observation"
    record = records.DurableInputRecord(
        ApplicationGenerationId("venue-input-app"),
        "03" * 32,
        8,
        operations.OperationDomain.VENUE_RECOVERY,
        None,
        None,
        None,
        None,
        "04" * 32,
        1,
        payload,
        sha256(payload).hexdigest(),
        "TERMINAL",
        2,
    )

    assert record.session_id is None
    with pytest.raises(ValueError, match="cannot retain acquisition or market"):
        records.DurableInputRecord(
            record.application_generation_id,
            record.execution_profile_id,
            record.scope_id,
            record.input_domain,
            record.session_id,
            AcquisitionGenerationId("05" * 32),
            None,
            None,
            record.input_identity_sha256,
            record.operation_contract_version,
            record.canonical_payload_bytes,
            record.payload_sha256,
            record.technical_state,
            record.created_ordinal,
        )


def test_durable_input_semantic_key_record_binds_bytes_to_exact_collision_domain() -> (
    None
):
    application_generation_id = ApplicationGenerationId("semantic-key-app")
    execution_profile_id = "06" * 32
    key_bytes = operations.encode_m2_semantic_key(
        operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
        (application_generation_id.value, execution_profile_id, 9),
        ("query-claim-id", "claim-1"),
    )
    record = records.DurableInputSemanticKeyRecord(
        operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
        application_generation_id,
        execution_profile_id,
        9,
        key_bytes,
        sha256(key_bytes).hexdigest(),
        application_generation_id,
        operations.OperationDomain.AUTHORITY,
        "07" * 32,
        3,
    )

    assert record.canonical_key_bytes == key_bytes
    assert record.key_sha256 == sha256(key_bytes).hexdigest()

    with pytest.raises(ValueError, match="authority semantic key coordinates"):
        records.DurableInputSemanticKeyRecord(
            record.key_kind,
            record.key_application_generation_id,
            record.execution_profile_id,
            10,
            record.canonical_key_bytes,
            record.key_sha256,
            record.input_application_generation_id,
            record.input_domain,
            record.input_identity_sha256,
            record.created_ordinal,
        )

    with pytest.raises(ValueError, match="kind does not match canonical"):
        records.DurableInputSemanticKeyRecord(
            operations.InputSemanticKeyKind.AUTHORITY_MANUAL_FLATTEN_V1,
            record.key_application_generation_id,
            record.execution_profile_id,
            record.key_scope_id,
            record.canonical_key_bytes,
            record.key_sha256,
            record.input_application_generation_id,
            record.input_domain,
            record.input_identity_sha256,
            record.created_ordinal,
        )

    with pytest.raises(
        ValueError,
        match="authority semantic key input application generation",
    ):
        records.DurableInputSemanticKeyRecord(
            record.key_kind,
            record.key_application_generation_id,
            record.execution_profile_id,
            record.key_scope_id,
            record.canonical_key_bytes,
            record.key_sha256,
            ApplicationGenerationId("other-semantic-key-app"),
            record.input_domain,
            record.input_identity_sha256,
            record.created_ordinal,
        )


def test_durable_input_semantic_key_record_keeps_venue_collision_domain_unscoped() -> (
    None
):
    application_generation_id = ApplicationGenerationId("venue-semantic-key-app")
    execution_profile_id = "08" * 32
    key_bytes = operations.encode_m2_semantic_key(
        operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
        (execution_profile_id,),
        ("venue-semantic-digest", "09" * 32),
    )
    record = records.DurableInputSemanticKeyRecord(
        operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
        None,
        execution_profile_id,
        None,
        key_bytes,
        sha256(key_bytes).hexdigest(),
        application_generation_id,
        operations.OperationDomain.VENUE_RECOVERY,
        "0a" * 32,
        4,
    )

    assert record.key_application_generation_id is None
    assert record.key_scope_id is None
    with pytest.raises(ValueError, match="venue semantic key coordinates"):
        records.DurableInputSemanticKeyRecord(
            record.key_kind,
            application_generation_id,
            record.execution_profile_id,
            1,
            record.canonical_key_bytes,
            record.key_sha256,
            record.input_application_generation_id,
            record.input_domain,
            record.input_identity_sha256,
            record.created_ordinal,
        )
