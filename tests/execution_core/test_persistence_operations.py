"""RED-first contracts for the WO-0168a pure operation codec foundation."""

from __future__ import annotations

from dataclasses import fields
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


def _operation_mandate() -> acquisition.AcquisitionMandate:
    position_scope = _operation_position_scope()
    session_id = identity.SessionId("session")
    price = _operation_price()
    emergency_guard = protection.ExecutionGuard("emergency", b"e" * 32)
    compatibility = protection.EmergencyRecoveryCompatibility(
        identity.EmergencyRecoveryCompatibilityId("compatibility"),
        position_scope,
        session_id,
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
        session_id,
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
        session_id=session_id,
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
        values.Quantity(1),
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
        values.Quantity(1),
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
        values.Quantity(1),
        values.Quantity(0),
        values.Quantity(1),
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
                values.Quantity(0),
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
                values.Quantity(0),
                values.Quantity(1),
                fill_fact,
                b"f" * 32,
            ),
        ),
        operations.VenueRecoveryOperation(
            venue_coordinates,
            recovery.RecordBrokerRevisionEvidence(
                identity.VenueInputId("broker-revision"),
                identity.EffectId("effect"),
                leg_key,
                values.Quantity(1),
                values.Quantity(1),
                values.Quantity(1),
                correction_fact,
                b"r" * 32,
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


def test_operation_decode_refuses_domain_coordinate_payload_and_canonicality_mutants() -> (
    None
):
    encoded = operations.encode_m2_operation(_all_exact_operations()[0])
    document = operations._decode_m2_document(encoded)

    wrong_domain = list(document)
    wrong_domain[2] = ["m2.operations.OperationDomain", "VENUE_RECOVERY"]
    wrong_coordinate = list(document)
    wrong_coordinate[3] = [
        "m2.operations.VenueOperationCoordinates/v1",
        *document[3][1:],
        None,
    ]
    wrong_payload = list(document)
    wrong_payload[4] = ["m1.venue.RecoverClaimedEffect/v1", *document[4][1:]]

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


def test_acquisition_hydration_rebuilds_the_private_binding_from_terms_only() -> None:
    mandate = _operation_mandate()
    encoded = operations._encode_m2_acquisition_mandate(mandate)
    decoded = operations._decode_m2_acquisition_mandate(encoded)

    assert decoded == mandate
    assert decoded.binding == mandate.binding
    assert acquisition._acquisition_mandate_is_authentic(decoded)
    assert "DualMandateBinding" not in json.dumps(encoded, separators=(",", ":"))


def test_operation_foundation_public_exports_are_exact_and_inert() -> None:
    expected = {
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
    }

    assert set(operations.__all__) == expected
    assert {name for name in vars(operations) if not name.startswith("_")} == expected
