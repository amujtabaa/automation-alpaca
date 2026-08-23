"""RED-first contracts for the WO-0168a pure operation codec foundation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, replace
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
import struct
from typing import get_args

import pytest

from app.execution_core import (
    acquisition,
    authority,
    fills,
    identity,
    protection,
    recovery,
    values,
    venue,
)
import app.execution_core.persistence.operations as operations


_KEY_PREFIX = b"execution-core/m2-semantic-key/v1\n"

_EXPECTED_OPTIONAL_SHAPE_DOCUMENT_SHA256 = {
    "observe-none": "b2832dcfc684fd557988f92f771dfdef6c92cc4c093b7bc2882185951f9ceeab",
    "observe-closure-only": "e754b6338cd4e0558f524b4174e76f9ac008f18b488b6106de93f3eef542ae08",
    "observe-evidence-only": "dad8ed66afb8c369ccf254c5a60eb868fc35fa1fc51a69367da67beed0e87a32",
    "observe-both": "ab0f54f817892dc854e3bc6eb7a8a6df4a960f4a96c48441715b3e68d2b0f8d0",
    "fill-absent": "2b3c27b55c48ace5661eba7713764facd9535581c373bb5f4e730350cffb4b0b",
    "fill-populated": "f8210db4a1df9508071cdb449f2685a77ef0e07a3aacc4e515f160ec22c76a18",
    "revision-absent": "6c4a401ebe0a20b8a3a29df46a9bc9a68dba013e425c88e87c401caf5ad36751",
    "revision-populated": "cb696f652d77557bb43674d7eab780b7ce866716b9cc818670440c2c6a956090",
    "market-best-sequenced": "99fad9074825f7e4dd1e8c3a07e054e4ff000169e6518826ba46f7c8e2711036",
    "market-best-source-time": "da09f521b52c5a8fc3cb50583f15f8ad300708bfacd12bfe8356f1dea5f3a455",
    "market-best-atr": "ec0bd5ae70a3642396dd47be28929685eaf654a0af3118418a4ee60bc1ceea93",
    "market-best-structure": "1ad9d5ded7981d0b8fd0dca830b38a281eb333fed2bc49c21f042925cec3e58f",
    "market-best-both-trails": "82d8293294333b656101288c11e25ab4e6ea08f57ff23fcf0cb19d3c169608c1",
    "market-trade": "bbbe0bb27fef4e899649fd0af61cb26bb5b5f08993659c4c97cf0c747528c1bb",
}


def _operation_price(units: int = 100) -> values.ReportedPrice:
    scale = values.PriceScale(Decimal("0.01"))
    return values.ReportedPrice(
        values.PriceUnits(units),
        scale,
        values.TickMetadata(values.PriceUnits(1), scale),
    )


def _operation_position_scope() -> fills.PositionScope:
    return fills.PositionScope(
        identity.BrokerId("broker"),
        identity.EnvironmentId("paper"),
        identity.AccountId("account"),
        identity.SymbolId("symbol"),
    )


def _operation_execution_scope() -> fills.ExecutionScope:
    scope = _operation_position_scope()
    return fills.ExecutionScope(
        scope.broker,
        scope.environment,
        scope.account,
        identity.OrderId("order"),
        scope.symbol_id,
        fills.ExecutionSide.BUY,
    )


def _operation_coordinates() -> tuple[
    operations.ExecutionOperationCoordinates,
    operations.VenueOperationCoordinates,
    operations.VenueOperationCoordinates,
    operations.AcquisitionOperationCoordinates,
    operations.MarketOperationCoordinates,
]:
    application_generation_id = identity.ApplicationGenerationId("ab" * 32)
    session_id = identity.SessionId("session")
    acquisition_generation_id = identity.AcquisitionGenerationId("cd" * 32)
    stream_generation_id = identity.MarketStreamGenerationId("ef" * 32)
    execution = operations.ExecutionOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
    )
    venue_coordinates = operations.VenueOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
        session_id,
    )
    passive_venue_coordinates = operations.VenueOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
        None,
    )
    acquisition_coordinates = operations.AcquisitionOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
        session_id,
        acquisition_generation_id,
    )
    market_coordinates = operations.MarketOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
        session_id,
        acquisition_generation_id,
        "22" * 32,
        stream_generation_id,
    )
    return (
        execution,
        venue_coordinates,
        passive_venue_coordinates,
        acquisition_coordinates,
        market_coordinates,
    )


def _operation_mandate(
    *,
    session_id: identity.SessionId | None = None,
) -> acquisition.AcquisitionMandate:
    position_scope = _operation_position_scope()
    resolved_session_id = (
        identity.SessionId("session") if session_id is None else session_id
    )
    price = _operation_price()
    emergency_guard = protection.ExecutionGuard("emergency", b"e" * 32)
    compatibility = protection.EmergencyRecoveryCompatibility(
        identity.EmergencyRecoveryCompatibilityId("compatibility"),
        position_scope,
        resolved_session_id,
        "compatibility-v1",
        b"c" * 32,
        emergency_guard,
        5,
        1,
        1_000,
        values.Quantity(10),
    )
    protection_mandate = protection.ProtectionMandate(
        identity.MandateId("protection-mandate"),
        position_scope,
        resolved_session_id,
        "protection-v1",
        Fraction(1, 10),
        Fraction(1, 5),
        Fraction(1, 20),
        Fraction(2),
        price.tick,
        protection.ExecutionGuard("normal", b"n" * 32),
        emergency_guard,
        protection.EvidencePolicy(
            identity.MarketDataSourceId("source"),
            identity.MarketStreamGenerationId("ef" * 32),
            protection.MarketSequenceMode.SEQUENCED,
            10,
            5,
            Fraction(1, 2),
        ),
        values.Quantity(10),
        5,
        1_000,
        compatibility,
    )
    return acquisition._m2_hydrate_acquisition_mandate(
        acquisition_mandate_id=identity.AcquisitionMandateId("acquisition-mandate"),
        position_scope=position_scope,
        session_id=resolved_session_id,
        configuration_version="acquisition-v1",
        maximum_quantity=values.Quantity(10),
        maximum_notional=Fraction(1_000),
        maximum_entry_price=price,
        allowed_order_types=(authority.AcquisitionOrderType.LIMIT,),
        expiry=1_000,
        deadline=900,
        fixed_child_cap=values.Quantity(1),
        certified_participation_cap=Fraction(1, 2),
        cancel_reprice_budget=2,
        protection_mandate=protection_mandate,
    )


def _all_exact_operations() -> tuple[operations.M2Operation, ...]:
    (
        execution_coordinates,
        venue_coordinates,
        passive_venue_coordinates,
        acquisition_coordinates,
        market_coordinates,
    ) = _operation_coordinates()
    execution_scope = _operation_execution_scope()
    price = _operation_price()
    leg_key = identity.VenueLegKey(
        execution_scope.broker,
        execution_scope.environment,
        execution_scope.account,
        execution_scope.order_id,
    )
    fill_fact = fills.BrokerFillFact(
        identity.ExecutionFactKey(
            execution_scope.broker,
            execution_scope.environment,
            execution_scope.account,
            identity.SourceEventId("fill-event"),
        ),
        execution_scope,
        identity.RootFillId("fill-root"),
        values.Quantity(11),
        price,
    )
    correction_fact = fills.BrokerTradeCorrectFact(
        identity.ExecutionFactKey(
            execution_scope.broker,
            execution_scope.environment,
            execution_scope.account,
            identity.SourceEventId("correct-event"),
        ),
        execution_scope,
        fill_fact.root_fill_id,
        fill_fact.key.source_event_id,
        values.Quantity(13),
        price,
    )
    bust_fact = fills.BrokerTradeBustFact(
        identity.ExecutionFactKey(
            execution_scope.broker,
            execution_scope.environment,
            execution_scope.account,
            identity.SourceEventId("bust-event"),
        ),
        execution_scope,
        fill_fact.root_fill_id,
        fill_fact.key.source_event_id,
        price,
    )
    human_fact = fills.HumanAttestedFillFact(
        identity.ExecutionFactKey(
            execution_scope.broker,
            execution_scope.environment,
            execution_scope.account,
            identity.SourceEventId("human-event"),
        ),
        execution_scope,
        identity.RootFillId("human-root"),
        leg_key,
        identity.RequestOccurrenceId("request"),
        identity.ClaimOccurrenceId("claim"),
        values.Quantity(7),
        values.Quantity(23),
        values.Quantity(30),
        price,
        identity.ActorId("operator"),
        "attested",
        identity.EvidenceReference("evidence"),
    )
    request = authority.BrokerEffectRequest(
        identity.EffectId("effect"),
        identity.RequestOccurrenceId("request"),
        identity.MandateId("protection-mandate"),
        venue.EffectKind.SUBMIT,
        identity.ClientOrderId("client-order"),
        execution_scope.symbol_id,
        fills.ExecutionSide.BUY,
        values.Quantity(1),
        b"economic-scope",
        None,
    )
    mandate = _operation_mandate()
    market_occurrence = protection.MarketOccurrence(
        identity.MarketDataSourceId("source"),
        identity.MarketStreamGenerationId("ef" * 32),
        _operation_position_scope(),
        identity.SessionId("session"),
        0,
        0,
        100,
        101,
        protection.MarketKind.BEST_BID,
        price,
        _operation_price(101),
        None,
        None,
        None,
        False,
    )
    return (
        operations.BrokerExecutionOperation(execution_coordinates, fill_fact),
        operations.BrokerExecutionOperation(execution_coordinates, correction_fact),
        operations.BrokerExecutionOperation(execution_coordinates, bust_fact),
        operations.VenueRecoveryOperation(
            venue_coordinates,
            venue.RecordTransportOutcome(
                identity.VenueInputId("transport"),
                identity.EffectId("effect"),
                venue.BrokerEffectState.REQUESTED,
            ),
        ),
        operations.VenueRecoveryOperation(
            venue_coordinates,
            venue.RecoverClaimedEffect(
                identity.VenueInputId("recover"),
                identity.EffectId("effect"),
            ),
        ),
        operations.VenueRecoveryOperation(
            venue_coordinates,
            venue.DiscoverVenueLeg(
                identity.VenueInputId("discover"),
                identity.EffectId("effect"),
                leg_key,
                identity.VenueObservationId("discover-observation"),
            ),
        ),
        operations.VenueRecoveryOperation(
            passive_venue_coordinates,
            venue.ObserveVenueStatus(
                identity.VenueInputId("status"),
                leg_key,
                venue.VenueAttemptState.WORKING,
                identity.VenueObservationId("status-observation"),
                values.Quantity(29),
                identity.ClosureId("status-closure"),
                identity.EvidenceReference("status-evidence"),
            ),
        ),
        operations.VenueRecoveryOperation(
            venue_coordinates,
            recovery.IngestHumanAttestedFill(
                identity.VenueInputId("human"), identity.EffectId("effect"), human_fact
            ),
        ),
        operations.VenueRecoveryOperation(
            venue_coordinates,
            recovery.ReleaseVenueLeg(
                identity.VenueInputId("release"),
                identity.EffectId("effect"),
                leg_key,
                identity.ClaimOccurrenceId("claim"),
                values.Quantity(1),
                venue.VenueAttemptState.FILLED,
                identity.ActorId("operator"),
                "released",
                identity.EvidenceReference("evidence"),
                identity.ClosureId("closure"),
                b"d" * 32,
            ),
        ),
        operations.VenueRecoveryOperation(
            venue_coordinates,
            recovery.RecordBrokerFillEvidence(
                identity.VenueInputId("broker-fill"),
                identity.EffectId("effect"),
                leg_key,
                values.Quantity(37),
                values.Quantity(48),
                fill_fact,
                b"f" * 32,
                identity.ClosureId("fill-closure"),
                identity.EvidenceReference("fill-evidence"),
            ),
        ),
        operations.VenueRecoveryOperation(
            venue_coordinates,
            recovery.RecordBrokerRevisionEvidence(
                identity.VenueInputId("broker-revision"),
                identity.EffectId("effect"),
                leg_key,
                values.Quantity(11),
                values.Quantity(53),
                values.Quantity(55),
                correction_fact,
                b"r" * 32,
                identity.ClosureId("revision-closure"),
                identity.EvidenceReference("revision-evidence"),
            ),
        ),
        operations.AuthorityOperation(
            execution_coordinates,
            authority.CreateBrokerEffect(
                identity.AuthorityInputId("create"),
                identity.SessionId("session"),
                request,
                None,
                None,
            ),
        ),
        operations.AuthorityOperation(
            execution_coordinates,
            authority.ClaimEffect(
                identity.AuthorityInputId("claim-effect"),
                identity.EffectId("effect"),
                identity.ClaimOccurrenceId("claim"),
            ),
        ),
        operations.AuthorityOperation(
            execution_coordinates,
            authority.ClaimBrokerQuery(
                identity.AuthorityInputId("query"),
                identity.QueryClaimId("query-claim"),
                execution_scope.symbol_id,
                authority.AuthorityQueryKind.QUERY,
            ),
        ),
        operations.AuthorityOperation(
            execution_coordinates,
            authority.EngageKill(
                identity.AuthorityInputId("kill"),
                identity.ActorId("operator"),
                "kill reason",
                identity.EvidenceReference("evidence"),
            ),
        ),
        operations.AuthorityOperation(
            execution_coordinates,
            authority.BeginManualFlatten(
                identity.AuthorityInputId("flatten"),
                identity.ManualFlattenId("flatten-id"),
                identity.SessionId("session"),
                execution_scope.symbol_id,
                identity.ActorId("operator"),
                "flatten reason",
                identity.EvidenceReference("evidence"),
                None,
            ),
        ),
        operations.AuthorityOperation(
            execution_coordinates,
            authority.AdvanceManualFlatten(
                identity.AuthorityInputId("advance"),
                identity.ManualFlattenId("flatten-id"),
            ),
        ),
        operations.BeginAcquisitionGenerationOperation(
            acquisition_coordinates,
            identity.AuthorityInputId("begin-generation"),
            mandate,
        ),
        operations.CreateAcquisitionEffectOperation(
            acquisition_coordinates,
            identity.AuthorityInputId("create-acquisition"),
            authority.AcquisitionEffectTerms(
                values.Quantity(1),
                price,
                authority.AcquisitionOrderType.LIMIT,
                100,
            ),
        ),
        operations.ClaimAcquisitionEffectOperation(
            acquisition_coordinates,
            identity.AuthorityInputId("claim-acquisition"),
            identity.EffectId("effect"),
            identity.ClaimOccurrenceId("claim"),
        ),
        operations.BeginAcquisitionPreemptionOperation(
            acquisition_coordinates,
            identity.AuthorityInputId("preempt-acquisition"),
        ),
        operations.MarketOccurrenceOperation(market_coordinates, market_occurrence),
    )


def _operation_document(operation: operations.M2Operation) -> list[object]:
    document = operations._decode_m2_document(operations.encode_m2_operation(operation))
    assert type(document) is list
    return document


def _decode_operation_document(document: list[object]) -> operations.M2Operation:
    return operations.decode_m2_operation(operations._encode_m2_document(document))


def _require_wire_list(value: object) -> list[object]:
    assert type(value) is list
    return value


def _operation_for_payload_tag(payload_tag: str) -> operations.M2Operation:
    for operation in _all_exact_operations():
        document = _operation_document(operation)
        payload = document[4]
        assert type(payload) is list
        if payload[0] == payload_tag:
            return operation
    raise AssertionError(f"no exact operation has payload tag {payload_tag}")


def _all_legal_optional_shape_operations() -> tuple[
    tuple[str, operations.M2Operation], ...
]:
    """Enumerate every independently legal optional representation once."""

    observe = _operation_for_payload_tag("m1.venue.ObserveVenueStatus/v1")
    fill = _operation_for_payload_tag("m1.recovery.RecordBrokerFillEvidence/v1")
    revision = _operation_for_payload_tag("m1.recovery.RecordBrokerRevisionEvidence/v1")
    market = _operation_for_payload_tag("m2.protection.MarketOccurrenceOperation/v1")
    assert type(observe) is operations.VenueRecoveryOperation
    assert type(observe.item) is venue.ObserveVenueStatus
    assert type(fill) is operations.VenueRecoveryOperation
    assert type(fill.item) is recovery.RecordBrokerFillEvidence
    assert type(revision) is operations.VenueRecoveryOperation
    assert type(revision.item) is recovery.RecordBrokerRevisionEvidence
    assert type(market) is operations.MarketOccurrenceOperation

    observed_none = replace(
        observe.item,
        input_id=identity.VenueInputId("optional-observe-none"),
        observation_id=identity.VenueObservationId("optional-observe-none"),
        closure_id=None,
        evidence_reference=None,
    )
    observed_closure = replace(
        observe.item,
        input_id=identity.VenueInputId("optional-observe-closure"),
        observation_id=identity.VenueObservationId("optional-observe-closure"),
        evidence_reference=None,
    )
    observed_evidence = replace(
        observe.item,
        input_id=identity.VenueInputId("optional-observe-evidence"),
        observation_id=identity.VenueObservationId("optional-observe-evidence"),
        closure_id=None,
    )
    observed_both = replace(
        observe.item,
        input_id=identity.VenueInputId("optional-observe-both"),
        observation_id=identity.VenueObservationId("optional-observe-both"),
    )

    fill_absent = replace(fill.item, closure_id=None, evidence_reference=None)
    revision_absent = replace(
        revision.item,
        closure_id=None,
        evidence_reference=None,
    )

    base_occurrence = market.occurrence
    market_without_sequence = replace(base_occurrence, source_sequence=None)
    market_with_atr = replace(
        base_occurrence,
        atr_distance=_operation_price(3),
    )
    market_with_structure = replace(
        base_occurrence,
        structure_trail=_operation_price(98),
    )
    market_with_both_trails = replace(
        base_occurrence,
        atr_distance=_operation_price(3),
        structure_trail=_operation_price(98),
    )
    trade_occurrence = replace(
        base_occurrence,
        kind=protection.MarketKind.TRADE,
        best_bid=None,
        best_ask=None,
        trade_price=_operation_price(100),
        atr_distance=None,
        structure_trail=None,
    )

    return (
        (
            "observe-none",
            operations.VenueRecoveryOperation(observe.coordinates, observed_none),
        ),
        (
            "observe-closure-only",
            operations.VenueRecoveryOperation(observe.coordinates, observed_closure),
        ),
        (
            "observe-evidence-only",
            operations.VenueRecoveryOperation(observe.coordinates, observed_evidence),
        ),
        (
            "observe-both",
            operations.VenueRecoveryOperation(observe.coordinates, observed_both),
        ),
        (
            "fill-absent",
            operations.VenueRecoveryOperation(fill.coordinates, fill_absent),
        ),
        ("fill-populated", fill),
        (
            "revision-absent",
            operations.VenueRecoveryOperation(revision.coordinates, revision_absent),
        ),
        ("revision-populated", revision),
        ("market-best-sequenced", market),
        (
            "market-best-source-time",
            operations.MarketOccurrenceOperation(
                market.coordinates,
                market_without_sequence,
            ),
        ),
        (
            "market-best-atr",
            operations.MarketOccurrenceOperation(market.coordinates, market_with_atr),
        ),
        (
            "market-best-structure",
            operations.MarketOccurrenceOperation(
                market.coordinates,
                market_with_structure,
            ),
        ),
        (
            "market-best-both-trails",
            operations.MarketOccurrenceOperation(
                market.coordinates,
                market_with_both_trails,
            ),
        ),
        (
            "market-trade",
            operations.MarketOccurrenceOperation(market.coordinates, trade_occurrence),
        ),
    )


@pytest.mark.parametrize(
    ("kind", "coordinates", "source", "expected_json", "expected_sha256"),
    [
        (
            operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
            ("ep",),
            (
                "venue-semantic-digest",
                "0000000000000000000000000000000000000000000000000000000000000000",
            ),
            '[1,"VENUE_COMMAND_V2",["ep"],["venue-semantic-digest","0000000000000000000000000000000000000000000000000000000000000000"]]',
            "1843bf3067f4b195fedfc5f91f3e16eb2709d030dee8df7501057e1ab96faa52",
        ),
        (
            operations.InputSemanticKeyKind.VENUE_EXECUTION_FACT_V1,
            ("ep",),
            ("execution-fact-key", "b", "e", "a", "s"),
            '[1,"VENUE_EXECUTION_FACT_V1",["ep"],["execution-fact-key","b","e","a","s"]]',
            "156419b82505dabe31bc5c20c5cd6db14eec7656039af3069e868a938ef52a03",
        ),
        (
            operations.InputSemanticKeyKind.VENUE_COVERAGE_ROOT_V1,
            ("ep",),
            ("root-fill-key", "b", "e", "a", "r"),
            '[1,"VENUE_COVERAGE_ROOT_V1",["ep"],["root-fill-key","b","e","a","r"]]',
            "450a3e32afee6722f0eb8b37fd11be884ee2fc491a5324e032b4f5f0bbe7afc6",
        ),
        (
            operations.InputSemanticKeyKind.VENUE_COVERAGE_INTERVAL_V1,
            ("ep",),
            ("coverage-interval", "b", "e", "a", "o", 0, 1),
            '[1,"VENUE_COVERAGE_INTERVAL_V1",["ep"],["coverage-interval","b","e","a","o",0,1]]',
            "1691d21d732c6b202ee02a1fc0d271091c99ffa325dcd373bb830cf98d93b7bc",
        ),
        (
            operations.InputSemanticKeyKind.VENUE_BROKER_FACT_V1,
            ("ep",),
            ("execution-fact-key", "b", "e", "a", "s"),
            '[1,"VENUE_BROKER_FACT_V1",["ep"],["execution-fact-key","b","e","a","s"]]',
            "666308088204232ad04268ca34e07b8f256ab0b8990875756542fde18a59b4d5",
        ),
        (
            operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
            ("app", "ep", 7),
            ("query-claim-id", "q"),
            '[1,"AUTHORITY_QUERY_CLAIM_V1",["app","ep",7],["query-claim-id","q"]]',
            "2f9b20479eb5e93934f56c5ec3e026c732d747d12f1692a185102bf740aa05f3",
        ),
        (
            operations.InputSemanticKeyKind.AUTHORITY_MANUAL_FLATTEN_V1,
            ("app", "ep", 7),
            ("manual-flatten-id", "m"),
            '[1,"AUTHORITY_MANUAL_FLATTEN_V1",["app","ep",7],["manual-flatten-id","m"]]',
            "9e83b189cecd3c6dda3bfc422ee8ac66a71acca705829bbba220fd1bdbb527ff",
        ),
        (
            operations.InputSemanticKeyKind.AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1,
            ("app", "ep", 7),
            ("emergency-grant-id", "g"),
            '[1,"AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1",["app","ep",7],["emergency-grant-id","g"]]',
            "b1b571b9462e44a139c62a1e8ae93d3c6c104b78f83db3416b9e916727aabce4",
        ),
    ],
)
def test_semantic_key_known_answers_are_exact(
    kind: operations.InputSemanticKeyKind,
    coordinates: tuple[str | int, ...],
    source: tuple[str | int, ...],
    expected_json: str,
    expected_sha256: str,
) -> None:
    encoded = operations.encode_m2_semantic_key(kind, coordinates, source)
    payload = expected_json.encode("utf-8")

    assert encoded == (
        _KEY_PREFIX
        + bytes((list(operations.InputSemanticKeyKind).index(kind) + 1,))
        + struct.pack(">Q", len(payload))
        + payload
    )
    assert sha256(encoded).hexdigest() == expected_sha256
    assert operations.decode_m2_semantic_key(encoded) == (kind, coordinates, source)


def test_semantic_key_decode_rejects_noncanonical_json_even_when_it_parses() -> None:
    payload = json.dumps(
        [
            1,
            "AUTHORITY_QUERY_CLAIM_V1",
            ["app", "ep", 7],
            ["query-claim-id", "q"],
        ],
        ensure_ascii=True,
        allow_nan=False,
        separators=(", ", ": "),
    ).encode("utf-8")
    forged = _KEY_PREFIX + b"\x06" + struct.pack(">Q", len(payload)) + payload

    with pytest.raises(ValueError, match="canonical"):
        operations.decode_m2_semantic_key(forged)


def test_semantic_key_decode_rejects_envelope_and_kind_mutants() -> None:
    encoded = operations.encode_m2_semantic_key(
        operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
        ("app", "ep", 7),
        ("query-claim-id", "q"),
    )
    kind_offset = len(_KEY_PREFIX)
    length_offset = kind_offset + 1

    unknown_kind = encoded[:kind_offset] + b"\x09" + encoded[length_offset:]
    mismatched_kind = encoded[:kind_offset] + b"\x01" + encoded[length_offset:]
    malformed_length = (
        encoded[:length_offset]
        + struct.pack(">Q", len(encoded) + 1)
        + encoded[length_offset + 8 :]
    )

    for forged in (unknown_kind, mismatched_kind, malformed_length):
        with pytest.raises(ValueError):
            operations.decode_m2_semantic_key(forged)


@pytest.mark.parametrize(
    ("kind", "coordinates", "source"),
    [
        (
            operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
            ("ep", "unexpected"),
            ("venue-semantic-digest", "00" * 32),
        ),
        (
            operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
            ("ep",),
            ("venue-semantic-digest", "not-a-digest"),
        ),
        (
            operations.InputSemanticKeyKind.VENUE_COVERAGE_INTERVAL_V1,
            ("ep",),
            ("coverage-interval", "b", "e", "a", "o", True, 1),
        ),
        (
            operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
            ("app", "ep", True),
            ("query-claim-id", "q"),
        ),
        (
            operations.InputSemanticKeyKind.AUTHORITY_MANUAL_FLATTEN_V1,
            ("app", "ep", 7),
            ("query-claim-id", "m"),
        ),
    ],
)
def test_semantic_key_rejects_wrong_coordinate_or_source_shape(
    kind: operations.InputSemanticKeyKind,
    coordinates: tuple[str | int, ...],
    source: tuple[str | int, ...],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        operations.encode_m2_semantic_key(kind, coordinates, source)


def test_retained_semantic_key_rehashes_bytes_and_preserves_exact_identity() -> None:
    raw_key = operations.encode_m2_semantic_key(
        operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
        ("app", "ep", 7),
        ("query-claim-id", "q"),
    )
    retained = operations.InputSemanticKey(
        operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
        raw_key,
        sha256(raw_key).hexdigest(),
        "authority-command/v1",
        "a1" * 32,
    )

    assert retained.canonical_key_bytes == raw_key
    assert retained.key_sha256 == sha256(raw_key).hexdigest()
    with pytest.raises(ValueError, match="digest"):
        operations.InputSemanticKey(
            operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
            raw_key,
            "00" * 32,
            "authority-command/v1",
            "a1" * 32,
        )
    with pytest.raises(ValueError, match="kind"):
        operations.InputSemanticKey(
            operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
            raw_key,
            sha256(raw_key).hexdigest(),
            "authority-command/v1",
            "a1" * 32,
        )


def test_input_dedupe_fact_keeps_alternate_match_distinct_from_primary_replay() -> None:
    raw_key = operations.encode_m2_semantic_key(
        operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
        ("app", "ep", 7),
        ("query-claim-id", "q"),
    )
    semantic_match = operations.InputSemanticKey(
        operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
        raw_key,
        sha256(raw_key).hexdigest(),
        "authority-command/v1",
        "a1" * 32,
    )

    unseen = operations.InputDedupeFact(
        operations.InputDedupeKind.UNSEEN,
        "authority-command/v1",
        "b2" * 32,
        "c3" * 32,
        None,
        (semantic_match,),
    )
    replay = operations.InputDedupeFact(
        operations.InputDedupeKind.EXACT_REPLAY,
        "authority-command/v1",
        "b2" * 32,
        "c3" * 32,
        "d4" * 32,
        (),
    )

    assert unseen.semantic_matches == (semantic_match,)
    assert replay.retained_outcome_sha256 == "d4" * 32
    with pytest.raises(ValueError, match="outcome"):
        operations.InputDedupeFact(
            operations.InputDedupeKind.EXACT_REPLAY,
            "authority-command/v1",
            "b2" * 32,
            "c3" * 32,
            None,
            (),
        )
    with pytest.raises(ValueError, match="duplicate"):
        operations.InputDedupeFact(
            operations.InputDedupeKind.UNSEEN,
            "authority-command/v1",
            "b2" * 32,
            "c3" * 32,
            None,
            (semantic_match, semantic_match),
        )


def test_input_dedupe_fact_reauthenticates_forged_or_mutated_semantic_matches() -> None:
    raw_key = operations.encode_m2_semantic_key(
        operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
        ("app", "ep", 7),
        ("query-claim-id", "q"),
    )
    mutated = operations.InputSemanticKey(
        operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
        raw_key,
        sha256(raw_key).hexdigest(),
        "authority-command/v1",
        "a1" * 32,
    )
    object.__setattr__(mutated, "canonical_key_bytes", b"forged-key-bytes")

    forged = object.__new__(operations.InputSemanticKey)
    object.__setattr__(
        forged,
        "kind",
        operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
    )
    object.__setattr__(forged, "canonical_key_bytes", b"forged-key-bytes")
    object.__setattr__(forged, "key_sha256", "00" * 32)
    object.__setattr__(forged, "retained_input_domain", "authority-command/v1")
    object.__setattr__(forged, "retained_input_identity_sha256", "a1" * 32)

    for invalid_match in (mutated, forged):
        with pytest.raises(ValueError):
            operations.InputDedupeFact(
                operations.InputDedupeKind.UNSEEN,
                "authority-command/v1",
                "b2" * 32,
                "c3" * 32,
                None,
                (invalid_match,),
            )


def test_closed_enum_values_are_exactly_the_frozen_domains() -> None:
    assert [member.value for member in operations.InputDedupeKind] == [
        "UNSEEN",
        "EXACT_REPLAY",
        "IDENTITY_CONFLICT",
    ]
    assert [member.value for member in operations.InputSemanticKeyKind] == [
        "VENUE_COMMAND_V2",
        "VENUE_EXECUTION_FACT_V1",
        "VENUE_COVERAGE_ROOT_V1",
        "VENUE_COVERAGE_INTERVAL_V1",
        "VENUE_BROKER_FACT_V1",
        "AUTHORITY_QUERY_CLAIM_V1",
        "AUTHORITY_MANUAL_FLATTEN_V1",
        "AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1",
    ]
    assert [member.value for member in operations.OperationDomain] == [
        "BROKER_EXECUTION",
        "VENUE_RECOVERY",
        "AUTHORITY",
        "BEGIN_ACQUISITION_GENERATION",
        "CREATE_ACQUISITION_EFFECT",
        "CLAIM_ACQUISITION_EFFECT",
        "BEGIN_ACQUISITION_PREEMPTION",
        "MARKET_OCCURRENCE",
    ]
    with pytest.raises(ValueError, match="outcome"):
        operations.InputDedupeFact(
            operations.InputDedupeKind.IDENTITY_CONFLICT,
            "authority-command/v1",
            "b2" * 32,
            "c3" * 32,
            "d4" * 32,
            (),
        )


def test_coordinate_values_are_exact_ordered_slotted_and_not_subclassable() -> None:
    application_generation_id = identity.ApplicationGenerationId("ab" * 32)
    acquisition_generation_id = identity.AcquisitionGenerationId("cd" * 32)
    market_stream_generation_id = identity.MarketStreamGenerationId("ef" * 32)
    session_id = identity.SessionId("session-1")

    execution = operations.ExecutionOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
    )
    venue = operations.VenueOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
        session_id,
    )
    acquisition = operations.AcquisitionOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
        session_id,
        acquisition_generation_id,
    )
    market = operations.MarketOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
        session_id,
        acquisition_generation_id,
        "22" * 32,
        market_stream_generation_id,
    )

    assert [field.name for field in fields(execution)] == [
        "application_generation_id",
        "execution_profile_id",
        "scope_id",
    ]
    assert [field.name for field in fields(venue)] == [
        "application_generation_id",
        "execution_profile_id",
        "scope_id",
        "session_id",
    ]
    assert [field.name for field in fields(acquisition)] == [
        "application_generation_id",
        "execution_profile_id",
        "scope_id",
        "session_id",
        "acquisition_generation_id",
    ]
    assert [field.name for field in fields(market)] == [
        "application_generation_id",
        "execution_profile_id",
        "scope_id",
        "session_id",
        "acquisition_generation_id",
        "market_source_profile_id",
        "stream_generation_id",
    ]

    class _IntAlias(int):
        pass

    with pytest.raises(TypeError, match="scope_id"):
        operations.ExecutionOperationCoordinates(
            application_generation_id,
            "11" * 32,
            _IntAlias(7),
        )
    with pytest.raises(TypeError, match="subclass"):

        class _DerivedCoordinates(operations.ExecutionOperationCoordinates):
            pass


@pytest.mark.parametrize(
    ("name", "expected_fields"),
    [
        ("BrokerExecutionOperation", ["coordinates", "fact"]),
        ("VenueRecoveryOperation", ["coordinates", "item"]),
        ("AuthorityOperation", ["coordinates", "command"]),
        (
            "BeginAcquisitionGenerationOperation",
            ["coordinates", "input_id", "successor_mandate"],
        ),
        (
            "CreateAcquisitionEffectOperation",
            ["coordinates", "input_id", "terms"],
        ),
        (
            "ClaimAcquisitionEffectOperation",
            ["coordinates", "input_id", "effect_id", "claim_occurrence_id"],
        ),
        ("BeginAcquisitionPreemptionOperation", ["coordinates", "input_id"]),
        ("MarketOccurrenceOperation", ["coordinates", "occurrence"]),
    ],
)
def test_admitted_operation_wrappers_have_exact_members_and_reject_subclasses(
    name: str,
    expected_fields: list[str],
) -> None:
    operation_type = getattr(operations, name)

    assert [field.name for field in fields(operation_type)] == expected_fields
    with pytest.raises(TypeError, match="cannot be subclassed"):
        type(f"Derived{name}", (operation_type,), {})


def test_operation_union_is_closed_over_the_eight_admitted_top_level_types() -> None:
    assert set(get_args(operations.M2Operation)) == {
        operations.BrokerExecutionOperation,
        operations.VenueRecoveryOperation,
        operations.AuthorityOperation,
        operations.BeginAcquisitionGenerationOperation,
        operations.CreateAcquisitionEffectOperation,
        operations.ClaimAcquisitionEffectOperation,
        operations.BeginAcquisitionPreemptionOperation,
        operations.MarketOccurrenceOperation,
    }


def test_operation_wrappers_refuse_foreign_payloads_before_any_reducer_work() -> None:
    application_generation_id = identity.ApplicationGenerationId("ab" * 32)
    acquisition_generation_id = identity.AcquisitionGenerationId("cd" * 32)
    market_stream_generation_id = identity.MarketStreamGenerationId("ef" * 32)
    session_id = identity.SessionId("session-1")
    execution_coordinates = operations.ExecutionOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
    )
    venue_coordinates = operations.VenueOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
        session_id,
    )
    acquisition_coordinates = operations.AcquisitionOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
        session_id,
        acquisition_generation_id,
    )
    market_coordinates = operations.MarketOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
        session_id,
        acquisition_generation_id,
        "22" * 32,
        market_stream_generation_id,
    )

    invalid_cases = (
        (operations.BrokerExecutionOperation, (execution_coordinates, object())),
        (operations.VenueRecoveryOperation, (venue_coordinates, object())),
        (operations.AuthorityOperation, (execution_coordinates, object())),
        (
            operations.BeginAcquisitionGenerationOperation,
            (acquisition_coordinates, object(), object()),
        ),
        (
            operations.CreateAcquisitionEffectOperation,
            (acquisition_coordinates, object(), object()),
        ),
        (
            operations.ClaimAcquisitionEffectOperation,
            (acquisition_coordinates, object(), object(), object()),
        ),
        (
            operations.BeginAcquisitionPreemptionOperation,
            (acquisition_coordinates, object()),
        ),
        (operations.MarketOccurrenceOperation, (market_coordinates, object())),
    )
    for operation_type, arguments in invalid_cases:
        with pytest.raises(TypeError):
            operation_type(*arguments)


def test_missing_venue_session_is_limited_to_passive_status_observation() -> None:
    application_generation_id = identity.ApplicationGenerationId("ab" * 32)
    missing_session_coordinates = operations.VenueOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
        None,
    )
    leg_key = identity.VenueLegKey(
        identity.BrokerId("broker"),
        identity.EnvironmentId("paper"),
        identity.AccountId("account"),
        identity.OrderId("order"),
    )
    passive_status = venue.ObserveVenueStatus(
        identity.VenueInputId("status-input"),
        leg_key,
        venue.VenueAttemptState.WORKING,
        identity.VenueObservationId("status-observation"),
        values.Quantity(0),
    )
    active_recovery = venue.RecoverClaimedEffect(
        identity.VenueInputId("recovery-input"),
        identity.EffectId("effect"),
    )

    assert (
        operations.VenueRecoveryOperation(
            missing_session_coordinates,
            passive_status,
        ).item
        is passive_status
    )
    with pytest.raises(ValueError, match="missing session"):
        operations.VenueRecoveryOperation(
            missing_session_coordinates,
            active_recovery,
        )


def test_operations_bind_payload_sessions_and_market_stream_to_coordinates() -> None:
    (
        _,
        _,
        _,
        acquisition_coordinates,
        market_coordinates,
    ) = _operation_coordinates()
    market_operation = next(
        operation
        for operation in _all_exact_operations()
        if type(operation) is operations.MarketOccurrenceOperation
    )
    assert type(market_operation) is operations.MarketOccurrenceOperation

    with pytest.raises(ValueError, match="successor_mandate session"):
        operations.BeginAcquisitionGenerationOperation(
            acquisition_coordinates,
            identity.AuthorityInputId("mismatched-generation"),
            _operation_mandate(session_id=identity.SessionId("other-session")),
        )
    with pytest.raises(ValueError, match="occurrence session"):
        operations.MarketOccurrenceOperation(
            market_coordinates,
            replace(
                market_operation.occurrence,
                session_id=identity.SessionId("other-session"),
            ),
        )
    with pytest.raises(ValueError, match="occurrence stream"):
        operations.MarketOccurrenceOperation(
            market_coordinates,
            replace(
                market_operation.occurrence,
                stream_generation=identity.MarketStreamGenerationId("01" * 32),
            ),
        )


def test_revision_evidence_encode_rechecks_its_closed_fact_union() -> None:
    operations_under_test = _all_exact_operations()
    broker_fill_operation = operations_under_test[0]
    revision_operation = next(
        operation
        for operation in operations_under_test
        if type(operation) is operations.VenueRecoveryOperation
        and type(operation.item) is recovery.RecordBrokerRevisionEvidence
    )
    assert type(broker_fill_operation) is operations.BrokerExecutionOperation
    assert type(revision_operation) is operations.VenueRecoveryOperation
    assert type(revision_operation.item) is recovery.RecordBrokerRevisionEvidence

    object.__setattr__(revision_operation.item, "fact", broker_fill_operation.fact)

    with pytest.raises(TypeError, match="correction or bust"):
        operations.encode_m2_operation(revision_operation)


def test_private_operation_wire_foundation_is_canonical_and_typed() -> None:
    application_generation_id = identity.ApplicationGenerationId("ab" * 32)
    coordinates = operations.ExecutionOperationCoordinates(
        application_generation_id,
        "11" * 32,
        7,
    )

    encoded_coordinates = operations._encode_m2_coordinates(coordinates)

    assert encoded_coordinates == [
        "m2.operations.ExecutionOperationCoordinates/v1",
        ["1", "application_generation_id", ["ab" * 32]],
        "11" * 32,
        7,
    ]
    assert operations._decode_m2_coordinates(encoded_coordinates) == coordinates
    assert operations._encode_m2_enum(operations.OperationDomain.BROKER_EXECUTION) == [
        "m2.operations.OperationDomain",
        "BROKER_EXECUTION",
    ]

    payload = [
        1,
        "m2.operation/v1",
        ["m2.operations.OperationDomain", "BROKER_EXECUTION"],
        encoded_coordinates,
        ["m1.fills.BrokerFillFact/v1"],
    ]
    document = operations._encode_m2_document(payload)
    canonical_json = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")

    assert document == (
        b"execution-core/m2-document/v1\n"
        + b"\x01"
        + struct.pack(">Q", len(canonical_json))
        + canonical_json
    )
    assert operations._decode_m2_document(document) == payload


def test_private_operation_wire_foundation_rejects_noncanonical_or_wrongly_typed_parts() -> (
    None
):
    application_generation_id = identity.ApplicationGenerationId("ab" * 32)
    coordinates = operations._encode_m2_coordinates(
        operations.ExecutionOperationCoordinates(
            application_generation_id,
            "11" * 32,
            7,
        )
    )
    payload = [
        1,
        "m2.operation/v1",
        ["m2.operations.OperationDomain", "BROKER_EXECUTION"],
        coordinates,
        ["m1.fills.BrokerFillFact/v1"],
    ]
    spaced_json = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        separators=(", ", ": "),
    ).encode("utf-8")
    malformed_document = (
        b"execution-core/m2-document/v1\n"
        + b"\x01"
        + struct.pack(">Q", len(spaced_json))
        + spaced_json
    )
    bad_tag = list(coordinates)
    bad_tag[0] = "m2.operations.VenueOperationCoordinates/v1"

    with pytest.raises(ValueError, match="canonical"):
        operations._decode_m2_document(malformed_document)
    with pytest.raises(ValueError, match="coordinate"):
        operations._decode_m2_coordinates(bad_tag)
    with pytest.raises(ValueError, match="enum"):
        operations._decode_m2_enum(["m2.operations.OperationDomain", "NOT_A_DOMAIN"])


def test_every_frozen_operation_payload_round_trips_through_exact_owner_codecs() -> (
    None
):
    expected_payload_tags = {
        "m1.fills.BrokerFillFact/v1",
        "m1.fills.BrokerTradeCorrectFact/v1",
        "m1.fills.BrokerTradeBustFact/v1",
        "m1.venue.RecordTransportOutcome/v1",
        "m1.venue.RecoverClaimedEffect/v1",
        "m1.venue.DiscoverVenueLeg/v1",
        "m1.venue.ObserveVenueStatus/v1",
        "m1.recovery.IngestHumanAttestedFill/v1",
        "m1.recovery.ReleaseVenueLeg/v1",
        "m1.recovery.RecordBrokerFillEvidence/v1",
        "m1.recovery.RecordBrokerRevisionEvidence/v1",
        "m1.authority.CreateBrokerEffect/v1",
        "m1.authority.ClaimEffect/v1",
        "m1.authority.ClaimBrokerQuery/v1",
        "m1.authority.EngageKill/v1",
        "m1.authority.BeginManualFlatten/v1",
        "m1.authority.AdvanceManualFlatten/v1",
        "m2.acquisition.BeginAcquisitionGeneration/v1",
        "m2.acquisition.CreateAcquisitionEffect/v1",
        "m2.acquisition.ClaimAcquisitionEffect/v1",
        "m2.acquisition.BeginAcquisitionPreemption/v1",
        "m2.protection.MarketOccurrenceOperation/v1",
    }
    observed_payload_tags: set[str] = set()

    for operation in _all_exact_operations():
        encoded = operations.encode_m2_operation(operation)
        document = operations._decode_m2_document(encoded)
        payload = document[4]

        assert type(payload) is list
        assert type(payload[0]) is str
        observed_payload_tags.add(payload[0])
        assert operations.decode_m2_operation(encoded) == operation
        assert (
            operations.encode_m2_operation(operations.decode_m2_operation(encoded))
            == encoded
        )

    assert observed_payload_tags == expected_payload_tags


_EXPECTED_OPERATION_DOCUMENT_SHA256 = {
    "m1.fills.BrokerFillFact/v1": "d789e71c24ad8a6bf92ad08d368f2d66c257336ea26c357bbbb5c7f140e4ee06",
    "m1.fills.BrokerTradeCorrectFact/v1": "b0c7ab22a12f0cafb3768ec86cce1524af0c3c89fb9b54a692f48f52bf6a43e2",
    "m1.fills.BrokerTradeBustFact/v1": "96178c862aee043819537a6a822cbf1a5158e46bd25ebf54516dd18d78608eef",
    "m1.venue.RecordTransportOutcome/v1": "a2038760f420d2c3c51431ba66b3296877d70801a88c86d67aa0cfb1b82b04ef",
    "m1.venue.RecoverClaimedEffect/v1": "da2a076cbde01b6764813ba9e4cd29b2bbbe91ac6c0387ee2f5882e3a6fdadf2",
    "m1.venue.DiscoverVenueLeg/v1": "577b79f669d90d6cd10d5bfa009052a427a57f9e3bb0f7853ab4991d81608ca9",
    "m1.venue.ObserveVenueStatus/v1": "88b66d7cbecd32f6b98e9deff14e6677e06af61f5eab899cd3ee2f2dba502528",
    "m1.recovery.IngestHumanAttestedFill/v1": "1f63c65164d5ba7d2d7a2676b7ca076bf0460a410ea914ea7e61fcc0013940cd",
    "m1.recovery.ReleaseVenueLeg/v1": "a96461eaf95409cf281e2ed9027fa3721ac0f7ba17d4d4c9ef0c23e5de710b30",
    "m1.recovery.RecordBrokerFillEvidence/v1": "f8210db4a1df9508071cdb449f2685a77ef0e07a3aacc4e515f160ec22c76a18",
    "m1.recovery.RecordBrokerRevisionEvidence/v1": "cb696f652d77557bb43674d7eab780b7ce866716b9cc818670440c2c6a956090",
    "m1.authority.CreateBrokerEffect/v1": "cb1a22150d6d621543539676f5a571ad0fdd5afd23b8ab6fbf18ef95aeb34763",
    "m1.authority.ClaimEffect/v1": "313ee42379ac15dd50463d9b00435cbf6ead7f028b90cabc0f25b5d3c953e848",
    "m1.authority.ClaimBrokerQuery/v1": "ecea173353d6e5fe43153b8f8f1ff493082ef08f197a0dfc9e12a15229d7b405",
    "m1.authority.EngageKill/v1": "3acc65e4335fa29f1dce005c0d4a4809316847432cd07fe329b5220eab9529c9",
    "m1.authority.BeginManualFlatten/v1": "e0a2e1e21c3390c2cd0ff9ef75eebefe8465eed0f21fecee96ce64b20e42e694",
    "m1.authority.AdvanceManualFlatten/v1": "1ec19b48b8b1d1a3640cc3a2e3522973df8c87fb3d20bbef33ebec6c46bbf2f4",
    "m2.acquisition.BeginAcquisitionGeneration/v1": "fd49000ebbe7fbfef8ef426ce4a5fcbfe81322c98977e1d76a4b54f32005cd36",
    "m2.acquisition.CreateAcquisitionEffect/v1": "bc56648a7761db4e18bb6a27a3dee432376543b3cc8576077603e6de7a0b4b3b",
    "m2.acquisition.ClaimAcquisitionEffect/v1": "0e41c56022974f067d64fdba7f0ea885045bc37b028ac24d96b3e18973d5ed26",
    "m2.acquisition.BeginAcquisitionPreemption/v1": "800dd66284e7b5f2ee1c628a17cd5d0b9f52fc7f2fd1a8c35af7c0cd72076e6e",
    "m2.protection.MarketOccurrenceOperation/v1": "99fad9074825f7e4dd1e8c3a07e054e4ff000169e6518826ba46f7c8e2711036",
}


def test_every_frozen_operation_document_matches_its_known_answer_bytes() -> None:
    observed_tags: set[str] = set()

    for operation in _all_exact_operations():
        encoded = operations.encode_m2_operation(operation)
        document = operations._decode_m2_document(encoded)
        payload = document[4]
        assert type(payload) is list
        payload_tag = payload[0]
        assert type(payload_tag) is str
        observed_tags.add(payload_tag)
        assert (
            sha256(encoded).hexdigest()
            == _EXPECTED_OPERATION_DOCUMENT_SHA256[payload_tag]
        )

    assert observed_tags == set(_EXPECTED_OPERATION_DOCUMENT_SHA256)


def test_operation_decode_refuses_domain_coordinate_payload_and_canonicality_mutants() -> (
    None
):
    encoded = operations.encode_m2_operation(_all_exact_operations()[0])
    document = operations._decode_m2_document(encoded)
    coordinates = document[3]
    payload = document[4]
    assert type(coordinates) is list
    assert type(payload) is list

    wrong_domain = list(document)
    wrong_domain[2] = ["m2.operations.OperationDomain", "VENUE_RECOVERY"]
    wrong_coordinate = list(document)
    wrong_coordinate[3] = [
        "m2.operations.VenueOperationCoordinates/v1",
        *coordinates[1:],
        None,
    ]
    wrong_payload = list(document)
    wrong_payload[4] = ["m1.venue.RecoverClaimedEffect/v1", *payload[1:]]

    for mutant in (wrong_domain, wrong_coordinate, wrong_payload):
        with pytest.raises((TypeError, ValueError)):
            operations.decode_m2_operation(operations._encode_m2_document(mutant))

    noncanonical = json.dumps(
        document,
        ensure_ascii=True,
        allow_nan=False,
        separators=(", ", ": "),
    ).encode("utf-8")
    malformed_document = (
        b"execution-core/m2-document/v1\n"
        + b"\x01"
        + struct.pack(">Q", len(noncanonical))
        + noncanonical
    )
    with pytest.raises(ValueError, match="canonical"):
        operations.decode_m2_operation(malformed_document)


def test_every_frozen_payload_rejects_count_tag_and_position_mutants() -> None:
    documents = tuple(
        _operation_document(operation) for operation in _all_exact_operations()
    )
    payload_tags: list[str] = []
    for document in documents:
        payload = document[4]
        assert type(payload) is list
        payload_tag = payload[0]
        assert type(payload_tag) is str
        payload_tags.append(payload_tag)

    for document in documents:
        payload = document[4]
        assert type(payload) is list
        payload_tag = payload[0]
        assert type(payload_tag) is str
        alternate_tag = next(tag for tag in payload_tags if tag != payload_tag)

        missing_field = deepcopy(document)
        missing_payload = missing_field[4]
        assert type(missing_payload) is list
        missing_payload.pop()

        extra_field = deepcopy(document)
        extra_payload = extra_field[4]
        assert type(extra_payload) is list
        extra_payload.append("unexpected")

        alternate_payload_tag = deepcopy(document)
        alternate_payload = alternate_payload_tag[4]
        assert type(alternate_payload) is list
        alternate_payload[0] = alternate_tag

        reordered = deepcopy(document)
        reordered_payload = reordered[4]
        assert type(reordered_payload) is list
        if len(reordered_payload) > 2:
            reordered_payload[1], reordered_payload[2] = (
                reordered_payload[2],
                reordered_payload[1],
            )
        else:
            reordered[3], reordered[4] = reordered[4], reordered[3]

        for mutant in (
            missing_field,
            extra_field,
            alternate_payload_tag,
            reordered,
        ):
            with pytest.raises((TypeError, ValueError)):
                _decode_operation_document(mutant)


def test_every_domain_rejects_foreign_closed_payloads_and_domain_substitutions() -> (
    None
):
    documents = tuple(
        _operation_document(operation) for operation in _all_exact_operations()
    )
    domains: set[str] = set()
    document_domains: list[str] = []
    for document in documents:
        domain = document[2]
        assert type(domain) is list
        domain_value = domain[1]
        assert type(domain_value) is str
        domains.add(domain_value)
        document_domains.append(domain_value)

    for document, domain_value in zip(documents, document_domains, strict=True):
        for foreign, foreign_domain in zip(documents, document_domains, strict=True):
            if foreign_domain == domain_value:
                continue
            foreign_payload = foreign[4]
            assert type(foreign_payload) is list
            mutant = deepcopy(document)
            mutant[4] = deepcopy(foreign_payload)
            with pytest.raises((TypeError, ValueError)):
                _decode_operation_document(mutant)

        for alternate_domain in domains - {domain_value}:
            mutant = deepcopy(document)
            mutant_domain = mutant[2]
            assert type(mutant_domain) is list
            mutant_domain[1] = alternate_domain
            with pytest.raises((TypeError, ValueError)):
                _decode_operation_document(mutant)


def test_every_domain_rejects_each_wrong_coordinate_family() -> None:
    documents = tuple(
        _operation_document(operation) for operation in _all_exact_operations()
    )
    representative_by_domain: dict[str, list[object]] = {}
    coordinate_prototype_by_tag: dict[str, list[object]] = {}

    for document in documents:
        domain = document[2]
        coordinates = document[3]
        assert type(domain) is list
        assert type(coordinates) is list
        domain_value = domain[1]
        coordinate_tag = coordinates[0]
        assert type(domain_value) is str
        assert type(coordinate_tag) is str
        representative_by_domain.setdefault(domain_value, document)
        coordinate_prototype_by_tag.setdefault(coordinate_tag, coordinates)

    assert len(representative_by_domain) == 8
    assert len(coordinate_prototype_by_tag) == 4

    for document in representative_by_domain.values():
        expected_coordinates = document[3]
        assert type(expected_coordinates) is list
        expected_tag = expected_coordinates[0]
        assert type(expected_tag) is str
        for coordinate_tag, foreign_coordinates in coordinate_prototype_by_tag.items():
            if coordinate_tag == expected_tag:
                continue
            mutant = deepcopy(document)
            mutant[3] = deepcopy(foreign_coordinates)
            with pytest.raises((TypeError, ValueError)):
                _decode_operation_document(mutant)


def test_public_decode_rejects_noncanonical_atoms_enums_hex_and_fractions() -> None:
    broker_document = _operation_document(_all_exact_operations()[0])
    malformed_atom_version = deepcopy(broker_document)
    malformed_atom_tag = deepcopy(broker_document)
    reordered_atom_header = deepcopy(broker_document)
    wrong_enum_owner = deepcopy(broker_document)

    malformed_version_atom = _require_wire_list(
        _require_wire_list(malformed_atom_version[4])[3]
    )
    malformed_tag_atom = _require_wire_list(
        _require_wire_list(malformed_atom_tag[4])[3]
    )
    reordered_header_atom = _require_wire_list(
        _require_wire_list(reordered_atom_header[4])[3]
    )
    enum_owner = _require_wire_list(
        _require_wire_list(_require_wire_list(wrong_enum_owner[4])[2])[6]
    )
    malformed_version_atom[0] = "m0.value/v1"
    malformed_tag_atom[1] = "not-a-root-fill-id"
    reordered_header_atom[0], reordered_header_atom[1] = (
        reordered_header_atom[1],
        reordered_header_atom[0],
    )
    enum_owner[0] = "m1.venue.VenueAttemptState"

    fill_evidence_document = _operation_document(
        _operation_for_payload_tag("m1.recovery.RecordBrokerFillEvidence/v1")
    )
    uppercase_hex = deepcopy(fill_evidence_document)
    whitespace_hex = deepcopy(fill_evidence_document)
    uppercase_payload = _require_wire_list(uppercase_hex[4])
    whitespace_payload = _require_wire_list(whitespace_hex[4])
    assert type(uppercase_payload[7]) is str
    assert type(whitespace_payload[7]) is str
    uppercase_payload[7] = "AB" * 32
    whitespace_payload[7] = f" {'ab' * 32}"

    acquisition_document = _operation_document(
        _operation_for_payload_tag("m2.acquisition.BeginAcquisitionGeneration/v1")
    )
    unreduced_fraction = deepcopy(acquisition_document)
    boolean_fraction = deepcopy(acquisition_document)
    invalid_fraction = deepcopy(acquisition_document)
    unreduced_wire_fraction = _require_wire_list(
        _require_wire_list(_require_wire_list(unreduced_fraction[4])[2])[6]
    )
    boolean_wire_fraction = _require_wire_list(
        _require_wire_list(_require_wire_list(boolean_fraction[4])[2])[6]
    )
    invalid_wire_fraction = _require_wire_list(
        _require_wire_list(_require_wire_list(invalid_fraction[4])[2])[6]
    )
    unreduced_wire_fraction[1] = 2_000
    unreduced_wire_fraction[2] = 2
    boolean_wire_fraction[1] = True
    invalid_wire_fraction[2] = -1

    for mutant in (
        malformed_atom_version,
        malformed_atom_tag,
        reordered_atom_header,
        wrong_enum_owner,
        uppercase_hex,
        whitespace_hex,
        unreduced_fraction,
        boolean_fraction,
        invalid_fraction,
    ):
        with pytest.raises((TypeError, ValueError)):
            _decode_operation_document(mutant)


def test_every_legal_optional_payload_shape_has_a_known_answer_and_round_trip() -> None:
    cases = _all_legal_optional_shape_operations()
    actual_names = tuple(name for name, _ in cases)

    assert len(actual_names) == len(set(actual_names))
    assert set(actual_names) == set(_EXPECTED_OPTIONAL_SHAPE_DOCUMENT_SHA256)
    for name, operation in cases:
        encoded = operations.encode_m2_operation(operation)
        decoded = operations.decode_m2_operation(encoded)

        assert (
            sha256(encoded).hexdigest()
            == _EXPECTED_OPTIONAL_SHAPE_DOCUMENT_SHA256[name]
        )
        assert decoded == operation
        assert operations.encode_m2_operation(decoded) == encoded


def test_optional_payload_slots_reject_incoherent_pairs_and_wrong_types() -> None:
    legal = dict(_all_legal_optional_shape_operations())

    observed_both = _operation_document(legal["observe-both"])
    observed_payload = _require_wire_list(observed_both[4])
    bad_observed_closure = deepcopy(observed_both)
    bad_observed_evidence = deepcopy(observed_both)
    _require_wire_list(bad_observed_closure[4])[-2] = deepcopy(observed_payload[-1])
    _require_wire_list(bad_observed_evidence[4])[-1] = deepcopy(observed_payload[-2])

    rejected: list[list[object]] = [bad_observed_closure, bad_observed_evidence]
    for family in ("fill", "revision"):
        absent = _operation_document(legal[f"{family}-absent"])
        populated = _operation_document(legal[f"{family}-populated"])
        absent_payload = _require_wire_list(absent[4])
        populated_payload = _require_wire_list(populated[4])

        missing_closure = deepcopy(populated)
        missing_evidence = deepcopy(populated)
        only_closure = deepcopy(absent)
        only_evidence = deepcopy(absent)
        _require_wire_list(missing_closure[4])[-2] = None
        _require_wire_list(missing_evidence[4])[-1] = None
        _require_wire_list(only_closure[4])[-2] = deepcopy(populated_payload[-2])
        _require_wire_list(only_evidence[4])[-1] = deepcopy(populated_payload[-1])
        assert absent_payload[-2:] == [None, None]
        rejected.extend(
            (missing_closure, missing_evidence, only_closure, only_evidence)
        )

    market_best = _operation_document(legal["market-best-both-trails"])
    market_trade = _operation_document(legal["market-trade"])
    best_payload = _require_wire_list(_require_wire_list(market_best[4])[1])
    malformed_sequence = deepcopy(market_best)
    malformed_bid = deepcopy(market_trade)
    malformed_ask = deepcopy(market_trade)
    malformed_trade = deepcopy(market_best)
    malformed_atr = deepcopy(market_best)
    malformed_structure = deepcopy(market_best)
    _require_wire_list(_require_wire_list(malformed_sequence[4])[1])[6] = True
    _require_wire_list(_require_wire_list(malformed_bid[4])[1])[10] = deepcopy(
        best_payload[10]
    )
    _require_wire_list(_require_wire_list(malformed_ask[4])[1])[11] = deepcopy(
        best_payload[11]
    )
    _require_wire_list(_require_wire_list(malformed_trade[4])[1])[12] = deepcopy(
        best_payload[10]
    )
    _require_wire_list(_require_wire_list(malformed_atr[4])[1])[13] = deepcopy(
        best_payload[1]
    )
    _require_wire_list(_require_wire_list(malformed_structure[4])[1])[14] = deepcopy(
        best_payload[1]
    )
    rejected.extend(
        (
            malformed_sequence,
            malformed_bid,
            malformed_ask,
            malformed_trade,
            malformed_atr,
            malformed_structure,
        )
    )

    for document in rejected:
        with pytest.raises((TypeError, ValueError)):
            _decode_operation_document(document)


def test_nested_protection_mandate_tamper_is_refused_by_owner_and_public_codec() -> (
    None
):
    mandate = _operation_mandate()
    object.__setattr__(mandate.protection_mandate, "loss_fraction", Fraction(1, 4))

    assert not protection._protection_mandate_is_authentic(mandate.protection_mandate)
    assert not acquisition._acquisition_mandate_is_authentic(mandate)
    with pytest.raises(ValueError, match="protection mandate is not authentic"):
        acquisition.AcquisitionMandate(
            mandate.acquisition_mandate_id,
            mandate.position_scope,
            mandate.session_id,
            mandate.configuration_version,
            mandate.maximum_quantity,
            mandate.maximum_notional,
            mandate.maximum_entry_price,
            mandate.allowed_order_types,
            mandate.expiry,
            mandate.deadline,
            mandate.fixed_child_cap,
            mandate.certified_participation_cap,
            mandate.cancel_reprice_budget,
            mandate.protection_mandate,
            mandate.binding,
        )

    operation = _operation_for_payload_tag(
        "m2.acquisition.BeginAcquisitionGeneration/v1"
    )
    assert type(operation) is operations.BeginAcquisitionGenerationOperation
    object.__setattr__(
        operation.successor_mandate.protection_mandate,
        "loss_fraction",
        Fraction(1, 4),
    )
    with pytest.raises(ValueError, match="authentic"):
        operations.encode_m2_operation(operation)


@pytest.mark.parametrize(
    ("attribute", "value"),
    (("source_time", 102), ("evaluation_time", 102)),
)
def test_market_occurrence_tamper_is_refused_by_wrapper_and_public_codec(
    attribute: str,
    value: int,
) -> None:
    operation = _operation_for_payload_tag("m2.protection.MarketOccurrenceOperation/v1")
    assert type(operation) is operations.MarketOccurrenceOperation
    object.__setattr__(operation.occurrence, attribute, value)

    with pytest.raises(ValueError, match="authentic market occurrence"):
        operations.MarketOccurrenceOperation(
            operation.coordinates, operation.occurrence
        )
    with pytest.raises(ValueError, match="authentic market occurrence"):
        operations.encode_m2_operation(operation)


def test_acquisition_hydration_rebuilds_the_private_binding_from_terms_only() -> None:
    mandate = _operation_mandate()
    encoded = operations._encode_m2_acquisition_mandate(mandate)
    decoded = operations._decode_m2_acquisition_mandate(encoded)

    assert decoded == mandate
    assert decoded.binding == mandate.binding
    assert acquisition._acquisition_mandate_is_authentic(decoded)
    assert "DualMandateBinding" not in json.dumps(encoded, separators=(",", ":"))


def test_operation_foundation_public_exports_are_exact_and_inert() -> None:
    expected = (
        "AcquisitionOperationCoordinates",
        "AuthorityOperation",
        "BeginAcquisitionGenerationOperation",
        "BeginAcquisitionPreemptionOperation",
        "BrokerExecutionOperation",
        "ClaimAcquisitionEffectOperation",
        "CreateAcquisitionEffectOperation",
        "ExecutionOperationCoordinates",
        "InputDedupeFact",
        "InputDedupeKind",
        "InputSemanticKey",
        "InputSemanticKeyKind",
        "M2Operation",
        "MarketOccurrenceOperation",
        "MarketOperationCoordinates",
        "OperationDomain",
        "VenueOperationCoordinates",
        "VenueRecoveryOperation",
        "decode_m2_operation",
        "decode_m2_semantic_key",
        "encode_m2_operation",
        "encode_m2_semantic_key",
    )

    assert operations.__all__ == expected
    assert {name for name in vars(operations) if not name.startswith("_")} == set(
        expected
    )
