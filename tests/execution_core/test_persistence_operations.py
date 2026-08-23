"""RED-first contracts for the WO-0168a pure operation codec foundation."""

from __future__ import annotations

from dataclasses import fields
from hashlib import sha256
import json
import struct
from typing import get_args

import pytest

from app.execution_core import identity
import app.execution_core.persistence.operations as operations


_KEY_PREFIX = b"execution-core/m2-semantic-key/v1\n"


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
        "decode_m2_semantic_key",
        "encode_m2_semantic_key",
    }

    assert set(operations.__all__) == expected
    assert {name for name in vars(operations) if not name.startswith("_")} == expected
