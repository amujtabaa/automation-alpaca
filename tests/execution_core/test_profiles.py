"""Independent known-answer controls for ADR-024 v1 profile commitments.

Every expected preimage and digest in this module is constructed literally,
here in the test file, from the exact byte plan of ADR-024 rules 1-7. None of
the expected answers is ever calculated by a production framing or commitment
helper; production outputs are only compared against these independent
literals, and each contract mutant must fail its intended check.
"""

from __future__ import annotations

import dataclasses
import unicodedata
from hashlib import sha256

import pytest

from app.execution_core.profiles import (
    ExecutionConnectionProfile,
    MarketDataSourceProfile,
    broker_account_identity_sha256,
    execution_profile_preimage,
    market_source_profile_preimage,
)


EXECUTION_DOMAIN = b"execution-connection-profile/v1"
MARKET_DOMAIN = b"market-data-source-profile/v1"
ACCOUNT_DOMAIN = b"broker-account-identity/v1"

CONNECTION_PROFILE_ID = "a1" * 32
CREDENTIAL_HANDLE_FINGERPRINT = "b2" * 32
CAPABILITY_PROFILE_SHA256 = "c3" * 32
DEPLOYMENT_IDENTITY = "d4" * 32
MARKET_SOURCE_PROFILE_ID = "e5" * 32
DATA_CAPABILITY_PROFILE_SHA256 = "f6" * 32

APPLICATION_GENERATION = "generation-2026-08-21"
BROKER_PROVIDER = "ALPACA"
ENVIRONMENT_CLASS = "PAPER"
ADAPTER_CONTRACT_VERSION = "1.2.3"
TRADE_COMMAND_ORIGIN = "https://paper-api.alpaca.markets"
ORDER_QUERY_ORIGIN = "https://paper-api.alpaca.markets"
ORDER_EVENT_ORIGIN = "https://stream.data.alpaca.markets"

PROVIDER_TOKEN = "ALPACA"
ENVIRONMENT_OR_FEED = "iex-feed"
SOURCE_ORIGIN = "https://stream.data.alpaca.markets"
ENTITLEMENT_CLASS = "IEX"
NORMALIZATION_CONTRACT_VERSION = "0.1.0"

ACCOUNT_IDENTIFIER = "paper-account-001"


def _independent_payload(domain: bytes, parts: list[bytes]) -> bytes:
    """Literal v1 framing: 4-byte domain length, then 8-byte part lengths."""

    chunks = [len(domain).to_bytes(4, "big"), domain]
    for part in parts:
        chunks.append(len(part).to_bytes(8, "big"))
        chunks.append(part)
    return b"".join(chunks)


def _literal_digest(domain: bytes, parts: list[bytes]) -> str:
    return sha256(_independent_payload(domain, parts)).hexdigest()


EXPECTED_ACCOUNT_DIGEST = _literal_digest(
    ACCOUNT_DOMAIN,
    [
        BROKER_PROVIDER.encode("utf-8"),
        ENVIRONMENT_CLASS.encode("utf-8"),
        ADAPTER_CONTRACT_VERSION.encode("utf-8"),
        ACCOUNT_IDENTIFIER.encode("utf-8"),
    ],
)

EXPECTED_EXECUTION_PAYLOAD = _independent_payload(
    EXECUTION_DOMAIN,
    [
        bytes.fromhex(CONNECTION_PROFILE_ID),
        APPLICATION_GENERATION.encode("utf-8"),
        BROKER_PROVIDER.encode("utf-8"),
        ENVIRONMENT_CLASS.encode("utf-8"),
        bytes.fromhex(EXPECTED_ACCOUNT_DIGEST),
        TRADE_COMMAND_ORIGIN.encode("utf-8"),
        ORDER_QUERY_ORIGIN.encode("utf-8"),
        ORDER_EVENT_ORIGIN.encode("utf-8"),
        bytes.fromhex(CREDENTIAL_HANDLE_FINGERPRINT),
        ADAPTER_CONTRACT_VERSION.encode("utf-8"),
        bytes.fromhex(CAPABILITY_PROFILE_SHA256),
        bytes.fromhex(DEPLOYMENT_IDENTITY),
    ],
)

EXPECTED_MARKET_PAYLOAD = _independent_payload(
    MARKET_DOMAIN,
    [
        bytes.fromhex(MARKET_SOURCE_PROFILE_ID),
        PROVIDER_TOKEN.encode("utf-8"),
        ENVIRONMENT_OR_FEED.encode("utf-8"),
        SOURCE_ORIGIN.encode("utf-8"),
        ENTITLEMENT_CLASS.encode("utf-8"),
        NORMALIZATION_CONTRACT_VERSION.encode("utf-8"),
        bytes.fromhex(DATA_CAPABILITY_PROFILE_SHA256),
    ],
)

EXECUTION_FIELD_NAMES = (
    "connection_profile_id",
    "application_generation",
    "broker_provider",
    "environment_class",
    "account_identity",
    "trade_command_origin",
    "order_query_origin",
    "order_event_origin",
    "credential_handle_fingerprint",
    "adapter_contract_version",
    "capability_profile_sha256",
    "deployment_identity",
    "profile_commitment_sha256",
)

MARKET_FIELD_NAMES = (
    "market_source_profile_id",
    "provider",
    "environment_or_feed",
    "source_origin",
    "entitlement_class",
    "normalization_contract_version",
    "data_capability_profile_sha256",
    "source_profile_commitment_sha256",
)


def _execution_profile() -> ExecutionConnectionProfile:
    return ExecutionConnectionProfile(
        connection_profile_id=CONNECTION_PROFILE_ID,
        application_generation=APPLICATION_GENERATION,
        broker_provider=BROKER_PROVIDER,
        environment_class=ENVIRONMENT_CLASS,
        account_identity=EXPECTED_ACCOUNT_DIGEST,
        trade_command_origin=TRADE_COMMAND_ORIGIN,
        order_query_origin=ORDER_QUERY_ORIGIN,
        order_event_origin=ORDER_EVENT_ORIGIN,
        credential_handle_fingerprint=CREDENTIAL_HANDLE_FINGERPRINT,
        adapter_contract_version=ADAPTER_CONTRACT_VERSION,
        capability_profile_sha256=CAPABILITY_PROFILE_SHA256,
        deployment_identity=DEPLOYMENT_IDENTITY,
    )


def _market_source_profile() -> MarketDataSourceProfile:
    return MarketDataSourceProfile(
        market_source_profile_id=MARKET_SOURCE_PROFILE_ID,
        provider=PROVIDER_TOKEN,
        environment_or_feed=ENVIRONMENT_OR_FEED,
        source_origin=SOURCE_ORIGIN,
        entitlement_class=ENTITLEMENT_CLASS,
        normalization_contract_version=NORMALIZATION_CONTRACT_VERSION,
        data_capability_profile_sha256=DATA_CAPABILITY_PROFILE_SHA256,
    )


# ---------------------------------------------------------------------------
# AC-3 / AC-4: literal known answers.


def test_account_assertion_digest_matches_independent_literal() -> None:
    actual = broker_account_identity_sha256(
        BROKER_PROVIDER,
        ENVIRONMENT_CLASS,
        ADAPTER_CONTRACT_VERSION,
        ACCOUNT_IDENTIFIER,
    )

    assert type(actual) is str
    assert actual == EXPECTED_ACCOUNT_DIGEST
    assert len(actual) == 64
    assert actual == actual.lower()


def test_execution_profile_commitment_matches_independent_literal_preimage() -> None:
    profile = _execution_profile()

    assert profile.profile_commitment_sha256 == sha256(
        EXPECTED_EXECUTION_PAYLOAD
    ).hexdigest()
    assert execution_profile_preimage(profile) == EXPECTED_EXECUTION_PAYLOAD


def test_market_source_commitment_matches_independent_literal_preimage() -> None:
    profile = _market_source_profile()

    assert profile.source_profile_commitment_sha256 == sha256(
        EXPECTED_MARKET_PAYLOAD
    ).hexdigest()
    assert market_source_profile_preimage(profile) == EXPECTED_MARKET_PAYLOAD


def test_nfc_unicode_text_contributes_exact_utf8_bytes() -> None:
    generation = "génération-α-01"
    expected = _literal_digest(
        EXECUTION_DOMAIN,
        [
            bytes.fromhex(CONNECTION_PROFILE_ID),
            generation.encode("utf-8"),
            BROKER_PROVIDER.encode("utf-8"),
            ENVIRONMENT_CLASS.encode("utf-8"),
            bytes.fromhex(EXPECTED_ACCOUNT_DIGEST),
            TRADE_COMMAND_ORIGIN.encode("utf-8"),
            ORDER_QUERY_ORIGIN.encode("utf-8"),
            ORDER_EVENT_ORIGIN.encode("utf-8"),
            bytes.fromhex(CREDENTIAL_HANDLE_FINGERPRINT),
            ADAPTER_CONTRACT_VERSION.encode("utf-8"),
            bytes.fromhex(CAPABILITY_PROFILE_SHA256),
            bytes.fromhex(DEPLOYMENT_IDENTITY),
        ],
    )
    profile = ExecutionConnectionProfile(
        connection_profile_id=CONNECTION_PROFILE_ID,
        application_generation=generation,
        broker_provider=BROKER_PROVIDER,
        environment_class=ENVIRONMENT_CLASS,
        account_identity=EXPECTED_ACCOUNT_DIGEST,
        trade_command_origin=TRADE_COMMAND_ORIGIN,
        order_query_origin=ORDER_QUERY_ORIGIN,
        order_event_origin=ORDER_EVENT_ORIGIN,
        credential_handle_fingerprint=CREDENTIAL_HANDLE_FINGERPRINT,
        adapter_contract_version=ADAPTER_CONTRACT_VERSION,
        capability_profile_sha256=CAPABILITY_PROFILE_SHA256,
        deployment_identity=DEPLOYMENT_IDENTITY,
    )

    assert profile.profile_commitment_sha256 == expected


# ---------------------------------------------------------------------------
# AC-4 mutation controls: each mutant fails its intended contract violation.


def test_domain_mutant_produces_a_different_digest() -> None:
    mutant = _literal_digest(
        b"execution-connection-profils/v1",
        [
            bytes.fromhex(CONNECTION_PROFILE_ID),
            APPLICATION_GENERATION.encode("utf-8"),
            BROKER_PROVIDER.encode("utf-8"),
            ENVIRONMENT_CLASS.encode("utf-8"),
            bytes.fromhex(EXPECTED_ACCOUNT_DIGEST),
            TRADE_COMMAND_ORIGIN.encode("utf-8"),
            ORDER_QUERY_ORIGIN.encode("utf-8"),
            ORDER_EVENT_ORIGIN.encode("utf-8"),
            bytes.fromhex(CREDENTIAL_HANDLE_FINGERPRINT),
            ADAPTER_CONTRACT_VERSION.encode("utf-8"),
            bytes.fromhex(CAPABILITY_PROFILE_SHA256),
            bytes.fromhex(DEPLOYMENT_IDENTITY),
        ],
    )

    assert mutant != sha256(EXPECTED_EXECUTION_PAYLOAD).hexdigest()


def test_part_order_mutant_produces_a_different_digest() -> None:
    reordered = [
        bytes.fromhex(CONNECTION_PROFILE_ID),
        BROKER_PROVIDER.encode("utf-8"),
        APPLICATION_GENERATION.encode("utf-8"),
        ENVIRONMENT_CLASS.encode("utf-8"),
        bytes.fromhex(EXPECTED_ACCOUNT_DIGEST),
        TRADE_COMMAND_ORIGIN.encode("utf-8"),
        ORDER_QUERY_ORIGIN.encode("utf-8"),
        ORDER_EVENT_ORIGIN.encode("utf-8"),
        bytes.fromhex(CREDENTIAL_HANDLE_FINGERPRINT),
        ADAPTER_CONTRACT_VERSION.encode("utf-8"),
        bytes.fromhex(CAPABILITY_PROFILE_SHA256),
        bytes.fromhex(DEPLOYMENT_IDENTITY),
    ]

    assert _literal_digest(EXECUTION_DOMAIN, reordered) != sha256(
        EXPECTED_EXECUTION_PAYLOAD
    ).hexdigest()


def test_length_width_mutant_produces_a_different_digest() -> None:
    domain = EXECUTION_DOMAIN
    parts = [
        bytes.fromhex(CONNECTION_PROFILE_ID),
        APPLICATION_GENERATION.encode("utf-8"),
        BROKER_PROVIDER.encode("utf-8"),
        ENVIRONMENT_CLASS.encode("utf-8"),
        bytes.fromhex(EXPECTED_ACCOUNT_DIGEST),
        TRADE_COMMAND_ORIGIN.encode("utf-8"),
        ORDER_QUERY_ORIGIN.encode("utf-8"),
        ORDER_EVENT_ORIGIN.encode("utf-8"),
        bytes.fromhex(CREDENTIAL_HANDLE_FINGERPRINT),
        ADAPTER_CONTRACT_VERSION.encode("utf-8"),
        bytes.fromhex(CAPABILITY_PROFILE_SHA256),
        bytes.fromhex(DEPLOYMENT_IDENTITY),
    ]
    chunks = [len(domain).to_bytes(4, "big"), domain]
    for part in parts:
        chunks.append(len(part).to_bytes(4, "big"))
        chunks.append(part)

    assert sha256(b"".join(chunks)).hexdigest() != sha256(
        EXPECTED_EXECUTION_PAYLOAD
    ).hexdigest()


def test_omission_mutant_produces_a_different_digest() -> None:
    omitted = [
        bytes.fromhex(CONNECTION_PROFILE_ID),
        APPLICATION_GENERATION.encode("utf-8"),
        BROKER_PROVIDER.encode("utf-8"),
        ENVIRONMENT_CLASS.encode("utf-8"),
        bytes.fromhex(EXPECTED_ACCOUNT_DIGEST),
        TRADE_COMMAND_ORIGIN.encode("utf-8"),
        ORDER_QUERY_ORIGIN.encode("utf-8"),
        ORDER_EVENT_ORIGIN.encode("utf-8"),
        bytes.fromhex(CREDENTIAL_HANDLE_FINGERPRINT),
        ADAPTER_CONTRACT_VERSION.encode("utf-8"),
        bytes.fromhex(CAPABILITY_PROFILE_SHA256),
    ]

    assert _literal_digest(EXECUTION_DOMAIN, omitted) != sha256(
        EXPECTED_EXECUTION_PAYLOAD
    ).hexdigest()


def test_digest_self_inclusion_mutant_is_excluded_from_the_real_payload() -> None:
    digest_bytes = bytes.fromhex(sha256(EXPECTED_EXECUTION_PAYLOAD).hexdigest())
    self_inclusive = (
        EXPECTED_EXECUTION_PAYLOAD
        + len(digest_bytes).to_bytes(8, "big")
        + digest_bytes
    )

    assert len(EXPECTED_EXECUTION_PAYLOAD) < len(self_inclusive)
    assert sha256(self_inclusive).hexdigest() != sha256(
        EXPECTED_EXECUTION_PAYLOAD
    ).hexdigest()


@pytest.mark.parametrize(
    "origin",
    [
        "http://paper-api.alpaca.markets",
        "//paper-api.alpaca.markets",
        "https://",
        "https://Paper-API.alpaca.markets",
        "https://paper_api.alpaca.markets",
        "https://-paper-api.alpaca.markets",
        "https://paper-api.alpaca.markets-",
        "https://paper-api.alpaca.markets.",
        "https://paper-api..alpaca.markets",
        "https://pa-per-api.alpaca.markets/",
        "https://pa-per-api.alpaca.markets?v=1",
        "https://pa-per-api.alpaca.markets#frag",
        "https://user@paper-api.alpaca.markets",
        "https://192.168.0.1",
        "https://[::1]",
        "https://paper-api.alpaca.markets:443",
        "https://paper-api.alpaca.markets:",
        "https://paper-api.alpaca.markets:0",
        "https://paper-api.alpaca.markets:0080",
        "https://paper-api.alpaca.markets:65536",
        "https://paper-api.alpaca.markets:99999999999",
        "https://paper-api.alpaca.markets%25",
        "https://" + "a" * 64 + ".example.com",
        "https://" + ".".join(["a" * 63] * 5),
        "https://" + ".".join([("a" * 61) + "z"] * 5) + ".com",
        "",
        "HTTPS://paper-api.alpaca.markets",
    ],
)
def test_noncanonical_origins_are_refused(origin: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        ExecutionConnectionProfile(
            connection_profile_id=CONNECTION_PROFILE_ID,
            application_generation=APPLICATION_GENERATION,
            broker_provider=BROKER_PROVIDER,
            environment_class=ENVIRONMENT_CLASS,
            account_identity=EXPECTED_ACCOUNT_DIGEST,
            trade_command_origin=origin,
            order_query_origin=ORDER_QUERY_ORIGIN,
            order_event_origin=ORDER_EVENT_ORIGIN,
            credential_handle_fingerprint=CREDENTIAL_HANDLE_FINGERPRINT,
            adapter_contract_version=ADAPTER_CONTRACT_VERSION,
            capability_profile_sha256=CAPABILITY_PROFILE_SHA256,
            deployment_identity=DEPLOYMENT_IDENTITY,
        )


@pytest.mark.parametrize(
    "origin",
    [
        "https://a.bc",
        "https://x-y.example.com:8443",
        "https://ab.example:1",
        "https://" + "a" * 63 + ".example.com",
        "https://" + ".".join([("a" * 61) + "z"] * 4) + ".com",
    ],
)
def test_canonical_origins_are_accepted(origin: str) -> None:
    ExecutionConnectionProfile(
        connection_profile_id=CONNECTION_PROFILE_ID,
        application_generation=APPLICATION_GENERATION,
        broker_provider=BROKER_PROVIDER,
        environment_class=ENVIRONMENT_CLASS,
        account_identity=EXPECTED_ACCOUNT_DIGEST,
        trade_command_origin=origin,
        order_query_origin=ORDER_QUERY_ORIGIN,
        order_event_origin=ORDER_EVENT_ORIGIN,
        credential_handle_fingerprint=CREDENTIAL_HANDLE_FINGERPRINT,
        adapter_contract_version=ADAPTER_CONTRACT_VERSION,
        capability_profile_sha256=CAPABILITY_PROFILE_SHA256,
        deployment_identity=DEPLOYMENT_IDENTITY,
    )


def test_lowercase_or_malformed_tokens_are_refused() -> None:
    coordinates: dict[str, object] = {
        "connection_profile_id": CONNECTION_PROFILE_ID,
        "application_generation": APPLICATION_GENERATION,
        "broker_provider": BROKER_PROVIDER,
        "environment_class": ENVIRONMENT_CLASS,
        "account_identity": EXPECTED_ACCOUNT_DIGEST,
        "trade_command_origin": TRADE_COMMAND_ORIGIN,
        "order_query_origin": ORDER_QUERY_ORIGIN,
        "order_event_origin": ORDER_EVENT_ORIGIN,
        "credential_handle_fingerprint": CREDENTIAL_HANDLE_FINGERPRINT,
        "adapter_contract_version": ADAPTER_CONTRACT_VERSION,
        "capability_profile_sha256": CAPABILITY_PROFILE_SHA256,
        "deployment_identity": DEPLOYMENT_IDENTITY,
    }
    mutants = (
        ("broker_provider", "alpaca"),
        ("broker_provider", "ALPACA-BROKER"),
        ("broker_provider", "ALPACA "),
        ("broker_provider", " ALPACA"),
        ("broker_provider", ""),
        ("broker_provider", "A" * 33),
        ("environment_class", "paper"),
    )

    for field_name, mutant_value in mutants:
        candidate = dict(coordinates)
        candidate[field_name] = mutant_value
        with pytest.raises((TypeError, ValueError)):
            ExecutionConnectionProfile(**candidate)  # type: ignore[arg-type]

    boundary = dict(coordinates)
    boundary["broker_provider"] = "A" * 32
    ExecutionConnectionProfile(**boundary)  # type: ignore[arg-type]


def test_entitlement_and_market_provider_tokens_follow_the_same_rule() -> None:
    with pytest.raises((TypeError, ValueError)):
        MarketDataSourceProfile(
            market_source_profile_id=MARKET_SOURCE_PROFILE_ID,
            provider="alpaca",
            environment_or_feed=ENVIRONMENT_OR_FEED,
            source_origin=SOURCE_ORIGIN,
            entitlement_class=ENTITLEMENT_CLASS,
            normalization_contract_version=NORMALIZATION_CONTRACT_VERSION,
            data_capability_profile_sha256=DATA_CAPABILITY_PROFILE_SHA256,
        )
    with pytest.raises((TypeError, ValueError)):
        MarketDataSourceProfile(
            market_source_profile_id=MARKET_SOURCE_PROFILE_ID,
            provider=PROVIDER_TOKEN,
            environment_or_feed=ENVIRONMENT_OR_FEED,
            source_origin=SOURCE_ORIGIN,
            entitlement_class="iex",
            normalization_contract_version=NORMALIZATION_CONTRACT_VERSION,
            data_capability_profile_sha256=DATA_CAPABILITY_PROFILE_SHA256,
        )


@pytest.mark.parametrize(
    "version",
    ["01.2.3", "1.02.3", "1.2.03", "1.2", "1.2.3.4", "v1.2.3", "", "1.2.x"],
)
def test_noncanonical_contract_versions_are_refused(version: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        ExecutionConnectionProfile(
            connection_profile_id=CONNECTION_PROFILE_ID,
            application_generation=APPLICATION_GENERATION,
            broker_provider=BROKER_PROVIDER,
            environment_class=ENVIRONMENT_CLASS,
            account_identity=EXPECTED_ACCOUNT_DIGEST,
            trade_command_origin=TRADE_COMMAND_ORIGIN,
            order_query_origin=ORDER_QUERY_ORIGIN,
            order_event_origin=ORDER_EVENT_ORIGIN,
            credential_handle_fingerprint=CREDENTIAL_HANDLE_FINGERPRINT,
            adapter_contract_version=version,
            capability_profile_sha256=CAPABILITY_PROFILE_SHA256,
            deployment_identity=DEPLOYMENT_IDENTITY,
        )


@pytest.mark.parametrize(
    "digest_text",
    [
        "AB" * 32,
        "g1" * 32,
        "ab" * 31,
        "ab" * 33,
        "ab",
        "",
        "0x" + "ab" * 31,
    ],
)
def test_uppercase_wrong_case_or_wrong_length_hex_fields_are_refused(
    digest_text: str,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        ExecutionConnectionProfile(
            connection_profile_id=digest_text,
            application_generation=APPLICATION_GENERATION,
            broker_provider=BROKER_PROVIDER,
            environment_class=ENVIRONMENT_CLASS,
            account_identity=EXPECTED_ACCOUNT_DIGEST,
            trade_command_origin=TRADE_COMMAND_ORIGIN,
            order_query_origin=ORDER_QUERY_ORIGIN,
            order_event_origin=ORDER_EVENT_ORIGIN,
            credential_handle_fingerprint=CREDENTIAL_HANDLE_FINGERPRINT,
            adapter_contract_version=ADAPTER_CONTRACT_VERSION,
            capability_profile_sha256=CAPABILITY_PROFILE_SHA256,
            deployment_identity=DEPLOYMENT_IDENTITY,
        )


def test_non_nfc_text_coordinates_are_refused_without_normalization() -> None:
    decomposed = unicodedata.normalize("NFD", "génération-α")

    with pytest.raises((TypeError, ValueError)):
        ExecutionConnectionProfile(
            connection_profile_id=CONNECTION_PROFILE_ID,
            application_generation=decomposed,
            broker_provider=BROKER_PROVIDER,
            environment_class=ENVIRONMENT_CLASS,
            account_identity=EXPECTED_ACCOUNT_DIGEST,
            trade_command_origin=TRADE_COMMAND_ORIGIN,
            order_query_origin=ORDER_QUERY_ORIGIN,
            order_event_origin=ORDER_EVENT_ORIGIN,
            credential_handle_fingerprint=CREDENTIAL_HANDLE_FINGERPRINT,
            adapter_contract_version=ADAPTER_CONTRACT_VERSION,
            capability_profile_sha256=CAPABILITY_PROFILE_SHA256,
            deployment_identity=DEPLOYMENT_IDENTITY,
        )
    with pytest.raises((TypeError, ValueError)):
        MarketDataSourceProfile(
            market_source_profile_id=MARKET_SOURCE_PROFILE_ID,
            provider=PROVIDER_TOKEN,
            environment_or_feed=unicodedata.normalize("NFD", "café-feed"),
            source_origin=SOURCE_ORIGIN,
            entitlement_class=ENTITLEMENT_CLASS,
            normalization_contract_version=NORMALIZATION_CONTRACT_VERSION,
            data_capability_profile_sha256=DATA_CAPABILITY_PROFILE_SHA256,
        )


def test_control_bearing_text_coordinates_are_refused() -> None:
    with pytest.raises((TypeError, ValueError)):
        ExecutionConnectionProfile(
            connection_profile_id=CONNECTION_PROFILE_ID,
            application_generation="generation\u0007bell",
            broker_provider=BROKER_PROVIDER,
            environment_class=ENVIRONMENT_CLASS,
            account_identity=EXPECTED_ACCOUNT_DIGEST,
            trade_command_origin=TRADE_COMMAND_ORIGIN,
            order_query_origin=ORDER_QUERY_ORIGIN,
            order_event_origin=ORDER_EVENT_ORIGIN,
            credential_handle_fingerprint=CREDENTIAL_HANDLE_FINGERPRINT,
            adapter_contract_version=ADAPTER_CONTRACT_VERSION,
            capability_profile_sha256=CAPABILITY_PROFILE_SHA256,
            deployment_identity=DEPLOYMENT_IDENTITY,
        )


# ---------------------------------------------------------------------------
# Account assertion input rules (ADR-024 rule 4).


def test_account_assertion_refuses_non_string_or_empty_identifier() -> None:
    with pytest.raises((TypeError, ValueError)):
        broker_account_identity_sha256(
            BROKER_PROVIDER, ENVIRONMENT_CLASS, ADAPTER_CONTRACT_VERSION, ""
        )
    with pytest.raises((TypeError, ValueError)):
        broker_account_identity_sha256(
            BROKER_PROVIDER,
            ENVIRONMENT_CLASS,
            ADAPTER_CONTRACT_VERSION,
            12345,  # type: ignore[arg-type]
        )


def test_account_assertion_identifier_length_bounds_are_enforced() -> None:
    accepted = "x" * 256
    rejected = "x" * 257

    first = broker_account_identity_sha256(
        BROKER_PROVIDER, ENVIRONMENT_CLASS, ADAPTER_CONTRACT_VERSION, accepted
    )
    assert first == _literal_digest(
        ACCOUNT_DOMAIN,
        [
            BROKER_PROVIDER.encode("utf-8"),
            ENVIRONMENT_CLASS.encode("utf-8"),
            ADAPTER_CONTRACT_VERSION.encode("utf-8"),
            accepted.encode("utf-8"),
        ],
    )
    with pytest.raises((TypeError, ValueError)):
        broker_account_identity_sha256(
            BROKER_PROVIDER, ENVIRONMENT_CLASS, ADAPTER_CONTRACT_VERSION, rejected
        )


def test_account_assertion_refuses_non_nfc_or_control_identifier() -> None:
    with pytest.raises((TypeError, ValueError)):
        broker_account_identity_sha256(
            BROKER_PROVIDER,
            ENVIRONMENT_CLASS,
            ADAPTER_CONTRACT_VERSION,
            unicodedata.normalize("NFD", "café-account"),
        )
    with pytest.raises((TypeError, ValueError)):
        broker_account_identity_sha256(
            BROKER_PROVIDER,
            ENVIRONMENT_CLASS,
            ADAPTER_CONTRACT_VERSION,
            "account\u0007id",
        )


def test_changed_identifier_bytes_change_the_assertion_digest() -> None:
    other = broker_account_identity_sha256(
        BROKER_PROVIDER, ENVIRONMENT_CLASS, ADAPTER_CONTRACT_VERSION, "other-001"
    )

    assert other != EXPECTED_ACCOUNT_DIGEST
    assert other == _literal_digest(
        ACCOUNT_DOMAIN,
        [
            BROKER_PROVIDER.encode("utf-8"),
            ENVIRONMENT_CLASS.encode("utf-8"),
            ADAPTER_CONTRACT_VERSION.encode("utf-8"),
            b"other-001",
        ],
    )


def test_account_assertion_token_and_version_arguments_stay_validated() -> None:
    with pytest.raises((TypeError, ValueError)):
        broker_account_identity_sha256(
            "alpaca", ENVIRONMENT_CLASS, ADAPTER_CONTRACT_VERSION, ACCOUNT_IDENTIFIER
        )
    with pytest.raises((TypeError, ValueError)):
        broker_account_identity_sha256(
            BROKER_PROVIDER, ENVIRONMENT_CLASS, "1.02.3", ACCOUNT_IDENTIFIER
        )


# ---------------------------------------------------------------------------
# AC-3: separation and activation-minted identity.


def test_execution_and_market_profiles_have_the_exact_adr_field_orders() -> None:
    assert tuple(field.name for field in dataclasses.fields(ExecutionConnectionProfile)) == EXECUTION_FIELD_NAMES
    assert tuple(field.name for field in dataclasses.fields(MarketDataSourceProfile)) == MARKET_FIELD_NAMES


def test_profiles_reject_cross_family_coordinates() -> None:
    with pytest.raises(TypeError):
        ExecutionConnectionProfile(  # type: ignore[misc]
            market_source_profile_id=MARKET_SOURCE_PROFILE_ID,
        )
    with pytest.raises(TypeError):
        MarketDataSourceProfile(  # type: ignore[misc]
            connection_profile_id=CONNECTION_PROFILE_ID,
        )


def test_execution_identity_does_not_imply_market_source_identity() -> None:
    execution = _execution_profile()
    market = _market_source_profile()

    assert execution.profile_commitment_sha256 != market.source_profile_commitment_sha256
    assert execution.account_identity != market.source_profile_commitment_sha256
    for name in MARKET_FIELD_NAMES:
        assert not hasattr(execution, f"market_{name}")


def test_profile_ids_remain_activation_inputs_not_digest_derivations() -> None:
    first = _execution_profile()
    second = ExecutionConnectionProfile(
        connection_profile_id="ff" * 32,
        application_generation=APPLICATION_GENERATION,
        broker_provider=BROKER_PROVIDER,
        environment_class=ENVIRONMENT_CLASS,
        account_identity=EXPECTED_ACCOUNT_DIGEST,
        trade_command_origin=TRADE_COMMAND_ORIGIN,
        order_query_origin=ORDER_QUERY_ORIGIN,
        order_event_origin=ORDER_EVENT_ORIGIN,
        credential_handle_fingerprint=CREDENTIAL_HANDLE_FINGERPRINT,
        adapter_contract_version=ADAPTER_CONTRACT_VERSION,
        capability_profile_sha256=CAPABILITY_PROFILE_SHA256,
        deployment_identity=DEPLOYMENT_IDENTITY,
    )

    assert first.connection_profile_id == CONNECTION_PROFILE_ID
    assert second.connection_profile_id == "ff" * 32
    assert first.profile_commitment_sha256 != second.profile_commitment_sha256


def test_changing_only_the_account_binding_changes_the_commitment() -> None:
    other_account = _literal_digest(
        ACCOUNT_DOMAIN,
        [
            BROKER_PROVIDER.encode("utf-8"),
            ENVIRONMENT_CLASS.encode("utf-8"),
            ADAPTER_CONTRACT_VERSION.encode("utf-8"),
            b"different-account",
        ],
    )
    rebased = ExecutionConnectionProfile(
        connection_profile_id=CONNECTION_PROFILE_ID,
        application_generation=APPLICATION_GENERATION,
        broker_provider=BROKER_PROVIDER,
        environment_class=ENVIRONMENT_CLASS,
        account_identity=other_account,
        trade_command_origin=TRADE_COMMAND_ORIGIN,
        order_query_origin=ORDER_QUERY_ORIGIN,
        order_event_origin=ORDER_EVENT_ORIGIN,
        credential_handle_fingerprint=CREDENTIAL_HANDLE_FINGERPRINT,
        adapter_contract_version=ADAPTER_CONTRACT_VERSION,
        capability_profile_sha256=CAPABILITY_PROFILE_SHA256,
        deployment_identity=DEPLOYMENT_IDENTITY,
    )

    assert rebased.profile_commitment_sha256 != sha256(
        EXPECTED_EXECUTION_PAYLOAD
    ).hexdigest()


def test_two_identical_constructors_agree_deterministically() -> None:
    assert _execution_profile() == _execution_profile()
    assert (
        _execution_profile().profile_commitment_sha256
        == _execution_profile().profile_commitment_sha256
    )
    assert _market_source_profile() == _market_source_profile()


def test_profiles_are_immutable() -> None:
    execution = _execution_profile()
    market = _market_source_profile()

    with pytest.raises(dataclasses.FrozenInstanceError):
        execution.broker_provider = "WEBULL"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        market.provider = "WEBULL"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EC-4: no credential or provider-account material is retained.


def test_no_secret_or_identifier_member_exists_on_either_profile() -> None:
    forbidden_fragments = ("identifier", "secret", "token", "api_key")

    for field_names in (EXECUTION_FIELD_NAMES, MARKET_FIELD_NAMES):
        offenders = [
            name
            for name in field_names
            if any(fragment in name for fragment in forbidden_fragments)
        ]
        assert offenders == [], sorted(offenders)


def test_provider_account_identifier_never_appears_in_representation() -> None:
    execution = _execution_profile()
    market = _market_source_profile()

    for value in (repr(execution), repr(market), str(execution)):
        assert ACCOUNT_IDENTIFIER not in value
