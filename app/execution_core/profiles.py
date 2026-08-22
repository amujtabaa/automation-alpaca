"""ADR-024 v1 execution-connection and market-data-source profile contracts.

Both immutable profiles carry one activation-minted opaque identifier plus
canonical non-secret coordinates, and one SHA-256 domain-separated commitment
over the exact v1 byte plan of ADR-024 rules 1-7:

- four-byte unsigned big-endian domain length, then eight-byte unsigned
  big-endian part lengths;
- opaque ``*_profile_id``, ``credential_handle_fingerprint``,
  ``deployment_identity`` and every ``*_sha256`` field contribute their
  decoded 32 bytes from 64 lowercase hexadecimal characters;
- ordinary text contributes its exact UTF-8 bytes and must already be NFC,
  nonempty, and free of ASCII control characters;
- ``broker_provider``-style tokens are uppercase ASCII ``[A-Z][A-Z0-9_]{0,31}``;
- versions are decimal ``MAJOR.MINOR.PATCH`` triples without leading zeros;
- origins are canonical ASCII ``https://host[:port]`` values, never
  library-normalized or reserialized.

The digest being calculated is never part of its own preimage. Profile IDs
are activation inputs and never derived from commitments. This module is
pure: no credentials, identifiers at rest, network, database, clock,
randomness, or side effects. Provider account identifiers exist only as
transient arguments of ``broker_account_identity_sha256`` and are never
retained on any object.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from hashlib import sha256


EXECUTION_CONNECTION_PROFILE_DOMAIN = "execution-connection-profile/v1"
MARKET_DATA_SOURCE_PROFILE_DOMAIN = "market-data-source-profile/v1"
BROKER_ACCOUNT_IDENTITY_DOMAIN = "broker-account-identity/v1"

_DOMAIN_LENGTH_BYTES = 4
_PART_LENGTH_BYTES = 8

_LOWERCASE_HEX = frozenset("0123456789abcdef")
_ASCII_DIGITS = frozenset("0123456789")
_TOKEN_TAIL_CHARACTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def _require_text(value: object, label: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{label} must be text")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _is_lowercase_hex_digest(value: str) -> bool:
    return len(value) == 64 and all(character in _LOWERCASE_HEX for character in value)


def _is_provider_token(value: str) -> bool:
    if not 1 <= len(value) <= 32:
        return False
    if not "A" <= value[0] <= "Z":
        return False
    return all(character in _TOKEN_TAIL_CHARACTERS for character in value[1:])


def _is_contract_version(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 3:
        return False
    for part in parts:
        if part == "0":
            continue
        if not part or part[0] not in "123456789":
            return False
        if not all(character in _ASCII_DIGITS for character in part):
            return False
    return True


def _is_canonical_text(value: str) -> bool:
    if not value:
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    for character in value:
        code_point = ord(character)
        if code_point < 0x20 or code_point == 0x7F:
            return False
    return unicodedata.normalize("NFC", value) == value


def _is_dns_label(label: str) -> bool:
    if not 1 <= len(label) <= 63:
        return False
    if not "a" <= label[0] <= "z":
        return False
    for character in label[1:]:
        if (
            character != "-"
            and not "a" <= character <= "z"
            and not "0" <= character <= "9"
        ):
            return False
    return len(label) == 1 or label[-1] != "-"


def _is_port(port: str) -> bool:
    if not port or not port.isascii():
        return False
    if not all(character in _ASCII_DIGITS for character in port):
        return False
    if len(port) > 1 and port[0] == "0":
        return False
    number = int(port)
    return 1 <= number <= 65535 and number != 443


def _is_canonical_origin(value: str) -> bool:
    prefix = "https://"
    if not value.startswith(prefix):
        return False
    rest = value[len(prefix) :]
    host, separator, port = rest.partition(":")
    if not 1 <= len(host) <= 253:
        return False
    for label in host.split("."):
        if not _is_dns_label(label):
            return False
    if separator:
        return _is_port(port)
    return True


def _frame_payload(domain: str, parts: tuple[bytes, ...]) -> bytes:
    domain_bytes = domain.encode("ascii")
    payload = bytearray()
    payload += len(domain_bytes).to_bytes(_DOMAIN_LENGTH_BYTES, "big")
    payload += domain_bytes
    for part in parts:
        payload += len(part).to_bytes(_PART_LENGTH_BYTES, "big")
        payload += part
    return bytes(payload)


def _opaque_part(value: str) -> bytes:
    return bytes.fromhex(value)


def _text_part(value: str) -> bytes:
    return value.encode("utf-8")


@dataclass(frozen=True, slots=True)
class ExecutionConnectionProfile:
    """The one immutable selected execution connection of a generation."""

    connection_profile_id: str
    application_generation: str
    broker_provider: str
    environment_class: str
    account_identity: str
    trade_command_origin: str
    order_query_origin: str
    order_event_origin: str
    credential_handle_fingerprint: str
    adapter_contract_version: str
    capability_profile_sha256: str
    deployment_identity: str
    profile_commitment_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _require(
            _is_lowercase_hex_digest(
                _require_text(self.connection_profile_id, "connection_profile_id")
            ),
            "connection_profile_id must be 64 lowercase hexadecimal characters",
        )
        _require(
            _is_canonical_text(
                _require_text(self.application_generation, "application_generation")
            ),
            "application_generation must be nonblank NFC text without control "
            "characters",
        )
        _require(
            _is_provider_token(_require_text(self.broker_provider, "broker_provider")),
            "broker_provider must match [A-Z][A-Z0-9_]{0,31}",
        )
        _require(
            _is_provider_token(
                _require_text(self.environment_class, "environment_class")
            ),
            "environment_class must match [A-Z][A-Z0-9_]{0,31}",
        )
        _require(
            _is_lowercase_hex_digest(
                _require_text(self.account_identity, "account_identity")
            ),
            "account_identity must be 64 lowercase hexadecimal characters",
        )
        for origin_field in (
            "trade_command_origin",
            "order_query_origin",
            "order_event_origin",
        ):
            origin = getattr(self, origin_field)
            _require(
                _is_canonical_origin(_require_text(origin, origin_field)),
                f"{origin_field} must be a canonical https://host[:port] origin",
            )
        _require(
            _is_lowercase_hex_digest(
                _require_text(
                    self.credential_handle_fingerprint,
                    "credential_handle_fingerprint",
                )
            ),
            "credential_handle_fingerprint must be 64 lowercase hexadecimal characters",
        )
        _require(
            _is_contract_version(
                _require_text(self.adapter_contract_version, "adapter_contract_version")
            ),
            "adapter_contract_version must be a MAJOR.MINOR.PATCH decimal triple",
        )
        _require(
            _is_lowercase_hex_digest(
                _require_text(
                    self.capability_profile_sha256, "capability_profile_sha256"
                )
            ),
            "capability_profile_sha256 must be 64 lowercase hexadecimal characters",
        )
        _require(
            _is_lowercase_hex_digest(
                _require_text(self.deployment_identity, "deployment_identity")
            ),
            "deployment_identity must be 64 lowercase hexadecimal characters",
        )
        payload = execution_payload(self)
        object.__setattr__(
            self, "profile_commitment_sha256", sha256(payload).hexdigest()
        )


@dataclass(frozen=True, slots=True)
class MarketDataSourceProfile:
    """The separate immutable market-data provenance contract."""

    market_source_profile_id: str
    provider: str
    environment_or_feed: str
    source_origin: str
    entitlement_class: str
    normalization_contract_version: str
    data_capability_profile_sha256: str
    source_profile_commitment_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        _require(
            _is_lowercase_hex_digest(
                _require_text(self.market_source_profile_id, "market_source_profile_id")
            ),
            "market_source_profile_id must be 64 lowercase hexadecimal characters",
        )
        _require(
            _is_provider_token(_require_text(self.provider, "provider")),
            "provider must match [A-Z][A-Z0-9_]{0,31}",
        )
        _require(
            _is_canonical_text(
                _require_text(self.environment_or_feed, "environment_or_feed")
            ),
            "environment_or_feed must be nonblank NFC text without control characters",
        )
        _require(
            _is_canonical_origin(_require_text(self.source_origin, "source_origin")),
            "source_origin must be a canonical https://host[:port] origin",
        )
        _require(
            _is_provider_token(
                _require_text(self.entitlement_class, "entitlement_class")
            ),
            "entitlement_class must match [A-Z][A-Z0-9_]{0,31}",
        )
        _require(
            _is_contract_version(
                _require_text(
                    self.normalization_contract_version,
                    "normalization_contract_version",
                )
            ),
            "normalization_contract_version must be a MAJOR.MINOR.PATCH decimal triple",
        )
        _require(
            _is_lowercase_hex_digest(
                _require_text(
                    self.data_capability_profile_sha256,
                    "data_capability_profile_sha256",
                )
            ),
            "data_capability_profile_sha256 must be 64 lowercase hexadecimal "
            "characters",
        )
        payload = market_source_payload(self)
        object.__setattr__(
            self,
            "source_profile_commitment_sha256",
            sha256(payload).hexdigest(),
        )


def execution_payload(profile_without_digest: ExecutionConnectionProfile) -> bytes:
    """Exact v1 preimage bytes; the commitment itself is excluded."""

    return _frame_payload(
        EXECUTION_CONNECTION_PROFILE_DOMAIN,
        (
            _opaque_part(profile_without_digest.connection_profile_id),
            _text_part(profile_without_digest.application_generation),
            _text_part(profile_without_digest.broker_provider),
            _text_part(profile_without_digest.environment_class),
            _opaque_part(profile_without_digest.account_identity),
            _text_part(profile_without_digest.trade_command_origin),
            _text_part(profile_without_digest.order_query_origin),
            _text_part(profile_without_digest.order_event_origin),
            _opaque_part(profile_without_digest.credential_handle_fingerprint),
            _text_part(profile_without_digest.adapter_contract_version),
            _opaque_part(profile_without_digest.capability_profile_sha256),
            _opaque_part(profile_without_digest.deployment_identity),
        ),
    )


def execution_profile_preimage(
    profile_without_digest: ExecutionConnectionProfile,
) -> bytes:
    """Return the exact v1 execution-commitment preimage bytes."""

    if type(profile_without_digest) is not ExecutionConnectionProfile:
        raise TypeError(
            "execution_profile_preimage requires an ExecutionConnectionProfile"
        )
    return execution_payload(profile_without_digest)


def market_source_payload(
    profile_without_digest: MarketDataSourceProfile,
) -> bytes:
    """Exact v1 preimage bytes; the commitment itself is excluded."""

    return _frame_payload(
        MARKET_DATA_SOURCE_PROFILE_DOMAIN,
        (
            _opaque_part(profile_without_digest.market_source_profile_id),
            _text_part(profile_without_digest.provider),
            _text_part(profile_without_digest.environment_or_feed),
            _text_part(profile_without_digest.source_origin),
            _text_part(profile_without_digest.entitlement_class),
            _text_part(profile_without_digest.normalization_contract_version),
            _opaque_part(profile_without_digest.data_capability_profile_sha256),
        ),
    )


def market_source_profile_preimage(
    profile_without_digest: MarketDataSourceProfile,
) -> bytes:
    """Return the exact v1 market-source-commitment preimage bytes."""

    if type(profile_without_digest) is not MarketDataSourceProfile:
        raise TypeError(
            "market_source_profile_preimage requires a MarketDataSourceProfile"
        )
    return market_source_payload(profile_without_digest)


def broker_account_identity_sha256(
    broker_provider: str,
    environment_class: str,
    adapter_contract_version: str,
    provider_account_identifier: str,
) -> str:
    """Digest the non-secret provider-account assertion; retain nothing."""

    _require(
        _is_provider_token(_require_text(broker_provider, "broker_provider")),
        "broker_provider must match [A-Z][A-Z0-9_]{0,31}",
    )
    _require(
        _is_provider_token(_require_text(environment_class, "environment_class")),
        "environment_class must match [A-Z][A-Z0-9_]{0,31}",
    )
    _require(
        _is_contract_version(
            _require_text(adapter_contract_version, "adapter_contract_version")
        ),
        "adapter_contract_version must be a MAJOR.MINOR.PATCH decimal triple",
    )
    identifier = _require_text(
        provider_account_identifier, "provider_account_identifier"
    )
    _require(
        _is_canonical_text(identifier) and len(identifier) <= 256,
        "provider_account_identifier must be 1-256 NFC scalar values without "
        "control characters",
    )
    payload = _frame_payload(
        BROKER_ACCOUNT_IDENTITY_DOMAIN,
        (
            _text_part(broker_provider),
            _text_part(environment_class),
            _text_part(adapter_contract_version),
            _text_part(identifier),
        ),
    )
    return sha256(payload).hexdigest()
