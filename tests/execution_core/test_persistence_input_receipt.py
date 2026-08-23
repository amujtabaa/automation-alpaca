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
