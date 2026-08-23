"""Pure durable-input and decision-receipt contracts for WO-0168a."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from hashlib import sha256

import pytest

from app.execution_core import fills, protection, values, venue
from app.execution_core.identity import (
    AccountId,
    AcquisitionGenerationId,
    ApplicationGenerationId,
    BrokerId,
    ClaimOccurrenceId,
    ClientOrderId,
    EffectId,
    EnvironmentId,
    MarketDataSourceId,
    MarketStreamGenerationId,
    MandateId,
    OrderId,
    RequestOccurrenceId,
    SessionId,
    SymbolId,
    VenueInputId,
    VenueLegKey,
    VenueObservationId,
)
from app.execution_core.persistence import operations, records


_EXPECTED_OWNER_RESULT_SHA256 = (
    "61e25664bdb0efb5d750ce2c74ecf95969e4a4071aea1c31093e53b156e2319c"
)
_EXPECTED_RECEIPT_DOCUMENT = (
    405,
    "f3dc31f727646fa14b626f4a378a59f2814171e1f559aefc13bdaaf22c866e9a",
)
_EXPECTED_OUTCOME_DOCUMENT = (
    477,
    "188b89b8d82e9e4cf0e8b7b2df33417a3f0eb73da8c35bb312c0d3a0568040bf",
)
_EXPECTED_OUTBOX_DOCUMENT = (
    823,
    "25b096dc0a1d3b9dd6b9dec79c388ff614598d6de23575e9e5fc1e9503ee257b",
)


def _market_operation() -> operations.MarketOccurrenceOperation:
    application_generation_id = ApplicationGenerationId("durable-input-app")
    session_id = SessionId("durable-input-session")
    acquisition_generation_id = AcquisitionGenerationId("cd" * 32)
    stream_generation_id = MarketStreamGenerationId("01" * 32)
    position_scope = fills.PositionScope(
        BrokerId("broker"),
        EnvironmentId("paper"),
        AccountId("account"),
        SymbolId("symbol"),
    )
    price_scale = values.PriceScale(Decimal("0.01"))
    price = values.ReportedPrice(
        values.PriceUnits(100),
        price_scale,
        values.TickMetadata(values.PriceUnits(1), price_scale),
    )
    occurrence = protection.MarketOccurrence(
        MarketDataSourceId("source"),
        stream_generation_id,
        position_scope,
        session_id,
        0,
        0,
        100,
        101,
        protection.MarketKind.BEST_BID,
        price,
        price,
        None,
        None,
        None,
        False,
    )
    return operations.MarketOccurrenceOperation(
        operations.MarketOperationCoordinates(
            application_generation_id,
            "ab" * 32,
            7,
            session_id,
            acquisition_generation_id,
            "ef" * 32,
            stream_generation_id,
        ),
        occurrence,
    )


def _passive_venue_operation() -> operations.VenueRecoveryOperation:
    application_generation_id = ApplicationGenerationId("venue-input-app")
    item = venue.ObserveVenueStatus(
        VenueInputId("passive-observation"),
        VenueLegKey(
            BrokerId("broker"),
            EnvironmentId("paper"),
            AccountId("account"),
            OrderId("order"),
        ),
        venue.VenueAttemptState.WORKING,
        VenueObservationId("passive-observation-id"),
        values.Quantity(1),
    )
    return operations.VenueRecoveryOperation(
        operations.VenueOperationCoordinates(
            application_generation_id,
            "03" * 32,
            8,
            None,
        ),
        item,
    )


def _durable_input_record(
    operation: operations.M2Operation,
    *,
    technical_state: str,
    created_ordinal: int,
) -> records.DurableInputRecord:
    payload = operations.encode_m2_operation(operation)
    (
        input_domain,
        application_generation_id,
        execution_profile_id,
        scope_id,
        session_id,
        acquisition_generation_id,
        market_source_profile_id,
        stream_generation_id,
        input_identity_sha256,
    ) = operations._derive_m2_durable_input_projection(
        operations.decode_m2_operation(payload)
    )
    return records.DurableInputRecord(
        application_generation_id,
        execution_profile_id,
        scope_id,
        input_domain,
        session_id,
        acquisition_generation_id,
        market_source_profile_id,
        stream_generation_id,
        input_identity_sha256,
        1,
        payload,
        sha256(payload).hexdigest(),
        technical_state,
        created_ordinal,
    )


def _decision_receipt_record() -> records.DecisionReceiptRecord:
    application_generation_id = ApplicationGenerationId("receipt-app")
    input_domain = operations.OperationDomain.AUTHORITY
    input_identity_sha256 = "11" * 32
    checkpoint_reference = (0, 1, "12" * 32)
    result_sha256 = records._derive_owner_result_sha256(
        "AUTHORITY",
        "APPLIED",
        "TERMINAL",
        checkpoint_reference,
    )
    document = [
        1,
        "m2.decision-receipt/v1",
        operations._encode_m2_m1_atom(application_generation_id),
        operations._encode_m2_enum(input_domain),
        input_identity_sha256,
        1,
        "AUTHORITY",
        "APPLIED",
        "TERMINAL",
        result_sha256,
        [*checkpoint_reference],
    ]
    canonical_receipt_bytes = operations._encode_m2_document_kind(0x04, document)
    return records.DecisionReceiptRecord(
        1,
        application_generation_id,
        input_domain,
        input_identity_sha256,
        "AUTHORITY",
        "APPLIED",
        "TERMINAL",
        result_sha256,
        checkpoint_reference[0],
        checkpoint_reference[1],
        checkpoint_reference[2],
        canonical_receipt_bytes,
        len(canonical_receipt_bytes),
        sha256(canonical_receipt_bytes).hexdigest(),
    )


def _durable_input_outcome_record(
    receipt: records.DecisionReceiptRecord,
) -> records.DurableInputOutcomeRecord:
    document = [
        1,
        "m2.durable-input-outcome/v1",
        operations._encode_m2_m1_atom(receipt.application_generation_id),
        operations._encode_m2_enum(receipt.input_domain),
        receipt.input_identity_sha256,
        receipt.owner_domain,
        receipt.owner_disposition,
        receipt.terminal_technical_state,
        receipt.result_sha256,
        [
            receipt.checkpoint_currentness_head_ordinal,
            receipt.checkpoint_version_ordinal,
            receipt.checkpoint_payload_sha256,
        ],
        receipt.receipt_ordinal,
        receipt.receipt_sha256,
    ]
    canonical_outcome_bytes = operations._encode_m2_document_kind(0x03, document)
    return records.DurableInputOutcomeRecord(
        receipt.application_generation_id,
        receipt.input_domain,
        receipt.input_identity_sha256,
        receipt.owner_domain,
        receipt.owner_disposition,
        receipt.terminal_technical_state,
        receipt.result_sha256,
        receipt.checkpoint_currentness_head_ordinal,
        receipt.checkpoint_version_ordinal,
        receipt.checkpoint_payload_sha256,
        receipt.receipt_ordinal,
        receipt.receipt_sha256,
        canonical_outcome_bytes,
        len(canonical_outcome_bytes),
        sha256(canonical_outcome_bytes).hexdigest(),
    )


def _broker_outbox_record() -> records.BrokerOutboxRecord:
    application_generation_id = ApplicationGenerationId("outbox-app")
    acquisition_generation_id = AcquisitionGenerationId("20" * 32)
    input_domain = operations.OperationDomain.AUTHORITY
    document = [
        1,
        "m2.broker-outbox/v1",
        1,
        operations._encode_m2_m1_atom(application_generation_id),
        "21" * 32,
        4,
        operations._encode_m2_m1_atom(acquisition_generation_id),
        operations._encode_m2_enum(input_domain),
        "22" * 32,
        3,
        operations._encode_m2_m1_atom(EffectId("effect-external")),
        operations._encode_m2_m1_atom(RequestOccurrenceId("request-occurrence")),
        operations._encode_m2_m1_atom(MandateId("mandate")),
        "23" * 32,
        0,
        1,
        "NORMAL",
        operations._encode_m2_enum(venue.EffectKind.SUBMIT),
        operations._encode_m2_m1_atom(ClientOrderId("client-order")),
        None,
        operations._encode_m2_enum(fills.ExecutionSide.BUY),
        operations._encode_m2_m1_atom(values.Quantity(1)),
        b"economic-scope".hex(),
        5,
        operations._encode_m2_m1_atom(ClaimOccurrenceId("claim-occurrence")),
        1,
    ]
    canonical_payload_bytes = operations._encode_m2_document_kind(0x05, document)
    return records.BrokerOutboxRecord(
        1,
        application_generation_id,
        "21" * 32,
        4,
        acquisition_generation_id,
        input_domain,
        "22" * 32,
        3,
        5,
        canonical_payload_bytes,
        len(canonical_payload_bytes),
        sha256(canonical_payload_bytes).hexdigest(),
    )


def _with_mismatched_document_length(document_bytes: bytes) -> bytes:
    prefix = b"execution-core/m2-document/v1\n"
    length_start = len(prefix) + 1
    declared_length = int.from_bytes(
        document_bytes[length_start : length_start + 8],
        "big",
    )
    return (
        document_bytes[:length_start]
        + (declared_length + 1).to_bytes(8, "big")
        + document_bytes[length_start + 8 :]
    )


def _set_document_member(
    document: list[object],
    index: int,
    nested_index: int | None,
    replacement: object,
) -> None:
    if nested_index is None:
        document[index] = replacement
        return
    nested = document[index]
    assert type(nested) is list
    nested[nested_index] = replacement


def test_durable_input_record_refuses_payloads_that_are_not_canonical_operations() -> (
    None
):
    payload = b"not an M2 operation document"

    with pytest.raises(ValueError, match="canonical operation"):
        records.DurableInputRecord(
            ApplicationGenerationId("invalid-operation-app"),
            "01" * 32,
            1,
            operations.OperationDomain.VENUE_RECOVERY,
            None,
            None,
            None,
            None,
            "02" * 32,
            1,
            payload,
            sha256(payload).hexdigest(),
            "CLAIMED",
            1,
        )


def test_durable_input_record_binds_exact_coordinate_shape_and_payload() -> None:
    record = _durable_input_record(
        _market_operation(), technical_state="CLAIMED", created_ordinal=1
    )

    assert record.canonical_payload_bytes == operations.encode_m2_operation(
        _market_operation()
    )
    assert record.payload_sha256 == sha256(record.canonical_payload_bytes).hexdigest()

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
    with pytest.raises(ValueError, match="identity does not match canonical operation"):
        records.DurableInputRecord(
            record.application_generation_id,
            record.execution_profile_id,
            record.scope_id,
            record.input_domain,
            record.session_id,
            record.acquisition_generation_id,
            record.market_source_profile_id,
            record.stream_generation_id,
            "ff" * 32,
            record.operation_contract_version,
            record.canonical_payload_bytes,
            record.payload_sha256,
            record.technical_state,
            record.created_ordinal,
        )


def test_durable_input_record_keeps_passive_venue_session_optional_only() -> None:
    record = _durable_input_record(
        _passive_venue_operation(), technical_state="TERMINAL", created_ordinal=2
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


def test_receipt_and_outcome_records_bind_every_shared_result_member() -> None:
    receipt = _decision_receipt_record()
    outcome = _durable_input_outcome_record(receipt)

    assert receipt.receipt_length == len(receipt.canonical_receipt_bytes)
    assert outcome.outcome_length == len(outcome.canonical_outcome_bytes)

    malformed_receipt_document = operations._decode_m2_document_kind(
        receipt.canonical_receipt_bytes,
        0x04,
    )
    malformed_receipt_document[7] = "REFUSED"
    malformed_receipt_bytes = operations._encode_m2_document_kind(
        0x04,
        malformed_receipt_document,
    )
    with pytest.raises(ValueError, match="disposition does not match document"):
        records.DecisionReceiptRecord(
            receipt.receipt_ordinal,
            receipt.application_generation_id,
            receipt.input_domain,
            receipt.input_identity_sha256,
            receipt.owner_domain,
            receipt.owner_disposition,
            receipt.terminal_technical_state,
            receipt.result_sha256,
            receipt.checkpoint_currentness_head_ordinal,
            receipt.checkpoint_version_ordinal,
            receipt.checkpoint_payload_sha256,
            malformed_receipt_bytes,
            len(malformed_receipt_bytes),
            sha256(malformed_receipt_bytes).hexdigest(),
        )

    malformed_outcome_document = operations._decode_m2_document_kind(
        outcome.canonical_outcome_bytes,
        0x03,
    )
    malformed_outcome_document[10] = receipt.receipt_ordinal + 1
    malformed_outcome_bytes = operations._encode_m2_document_kind(
        0x03,
        malformed_outcome_document,
    )
    with pytest.raises(ValueError, match="receipt ordinal does not match document"):
        records.DurableInputOutcomeRecord(
            outcome.application_generation_id,
            outcome.input_domain,
            outcome.input_identity_sha256,
            outcome.owner_domain,
            outcome.owner_disposition,
            outcome.terminal_technical_state,
            outcome.result_sha256,
            outcome.checkpoint_currentness_head_ordinal,
            outcome.checkpoint_version_ordinal,
            outcome.checkpoint_payload_sha256,
            outcome.receipt_ordinal,
            outcome.receipt_sha256,
            malformed_outcome_bytes,
            len(malformed_outcome_bytes),
            sha256(malformed_outcome_bytes).hexdigest(),
        )

    with pytest.raises(ValueError, match="result SHA-256 does not match result fields"):
        records.DecisionReceiptRecord(
            receipt.receipt_ordinal,
            receipt.application_generation_id,
            receipt.input_domain,
            receipt.input_identity_sha256,
            receipt.owner_domain,
            receipt.owner_disposition,
            receipt.terminal_technical_state,
            "ff" * 32,
            receipt.checkpoint_currentness_head_ordinal,
            receipt.checkpoint_version_ordinal,
            receipt.checkpoint_payload_sha256,
            receipt.canonical_receipt_bytes,
            receipt.receipt_length,
            receipt.receipt_sha256,
        )

    cross_owner_result_sha256 = records._derive_owner_result_sha256(
        "POSITION",
        "APPLIED",
        "TERMINAL",
        (
            receipt.checkpoint_currentness_head_ordinal,
            receipt.checkpoint_version_ordinal,
            receipt.checkpoint_payload_sha256,
        ),
    )
    cross_owner_document = operations._decode_m2_document_kind(
        receipt.canonical_receipt_bytes,
        0x04,
    )
    cross_owner_document[6] = "POSITION"
    cross_owner_document[9] = cross_owner_result_sha256
    cross_owner_bytes = operations._encode_m2_document_kind(0x04, cross_owner_document)
    with pytest.raises(ValueError, match="owner domain does not match input domain"):
        records.DecisionReceiptRecord(
            receipt.receipt_ordinal,
            receipt.application_generation_id,
            receipt.input_domain,
            receipt.input_identity_sha256,
            "POSITION",
            "APPLIED",
            "TERMINAL",
            cross_owner_result_sha256,
            receipt.checkpoint_currentness_head_ordinal,
            receipt.checkpoint_version_ordinal,
            receipt.checkpoint_payload_sha256,
            cross_owner_bytes,
            len(cross_owner_bytes),
            sha256(cross_owner_bytes).hexdigest(),
        )


def test_broker_outbox_record_binds_its_sequence_and_immutable_coordinates() -> None:
    outbox = _broker_outbox_record()

    assert outbox.payload_length == len(outbox.canonical_payload_bytes)
    malformed_document = operations._decode_m2_document_kind(
        outbox.canonical_payload_bytes,
        0x05,
    )
    malformed_document[2] = outbox.outbox_sequence + 1
    malformed_bytes = operations._encode_m2_document_kind(0x05, malformed_document)
    with pytest.raises(ValueError, match="sequence does not match document"):
        records.BrokerOutboxRecord(
            outbox.outbox_sequence,
            outbox.application_generation_id,
            outbox.execution_profile_id,
            outbox.scope_id,
            outbox.acquisition_generation_id,
            outbox.input_domain,
            outbox.input_identity_sha256,
            outbox.effect_id,
            outbox.claim_id,
            malformed_bytes,
            len(malformed_bytes),
            sha256(malformed_bytes).hexdigest(),
        )


def test_r12_documents_have_fixed_known_answers_and_refuse_length_mutants() -> None:
    receipt = _decision_receipt_record()
    outcome = _durable_input_outcome_record(receipt)
    outbox = _broker_outbox_record()

    assert receipt.result_sha256 == _EXPECTED_OWNER_RESULT_SHA256
    assert (
        receipt.receipt_length,
        receipt.receipt_sha256,
    ) == _EXPECTED_RECEIPT_DOCUMENT
    assert (
        outcome.outcome_length,
        outcome.outcome_sha256,
    ) == _EXPECTED_OUTCOME_DOCUMENT
    assert (
        outbox.payload_length,
        outbox.payload_sha256,
    ) == _EXPECTED_OUTBOX_DOCUMENT

    for record, bytes_name, length_name, digest_name in (
        (
            receipt,
            "canonical_receipt_bytes",
            "receipt_length",
            "receipt_sha256",
        ),
        (
            outcome,
            "canonical_outcome_bytes",
            "outcome_length",
            "outcome_sha256",
        ),
        (
            outbox,
            "canonical_payload_bytes",
            "payload_length",
            "payload_sha256",
        ),
    ):
        malformed_bytes = _with_mismatched_document_length(getattr(record, bytes_name))
        with pytest.raises(ValueError, match="document is not canonical"):
            replace(
                record,
                **{
                    bytes_name: malformed_bytes,
                    length_name: len(malformed_bytes),
                    digest_name: sha256(malformed_bytes).hexdigest(),
                },
            )


@pytest.mark.parametrize(
    ("receipt_index", "outcome_index", "nested_index", "replacement"),
    (
        (6, 5, None, "POSITION"),
        (7, 6, None, "REFUSED"),
        (8, 7, None, "RECONCILIATION_PENDING"),
        (9, 8, None, "ff" * 32),
        (10, 9, 0, 1),
        (10, 9, 1, 2),
        (10, 9, 2, "ff" * 32),
    ),
)
def test_receipt_and_outcome_refuse_each_mutated_shared_result_member(
    receipt_index: int,
    outcome_index: int,
    nested_index: int | None,
    replacement: object,
) -> None:
    receipt = _decision_receipt_record()
    outcome = _durable_input_outcome_record(receipt)
    mutated_receipt_document = operations._decode_m2_document_kind(
        receipt.canonical_receipt_bytes,
        0x04,
    )
    mutated_outcome_document = operations._decode_m2_document_kind(
        outcome.canonical_outcome_bytes,
        0x03,
    )
    _set_document_member(
        mutated_receipt_document,
        receipt_index,
        nested_index,
        replacement,
    )
    _set_document_member(
        mutated_outcome_document,
        outcome_index,
        nested_index,
        replacement,
    )
    mutated_receipt_bytes = operations._encode_m2_document_kind(
        0x04,
        mutated_receipt_document,
    )
    mutated_outcome_bytes = operations._encode_m2_document_kind(
        0x03,
        mutated_outcome_document,
    )

    with pytest.raises(ValueError):
        replace(
            receipt,
            canonical_receipt_bytes=mutated_receipt_bytes,
            receipt_length=len(mutated_receipt_bytes),
            receipt_sha256=sha256(mutated_receipt_bytes).hexdigest(),
        )
    with pytest.raises(ValueError):
        replace(
            outcome,
            canonical_outcome_bytes=mutated_outcome_bytes,
            outcome_length=len(mutated_outcome_bytes),
            outcome_sha256=sha256(mutated_outcome_bytes).hexdigest(),
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
