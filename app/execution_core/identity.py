"""Exact immutable identities for canonical broker execution facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class _ExactIdentity:
    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str:
            raise TypeError("identity must be a string")
        if not self.value.strip():
            raise ValueError("identity must be nonblank")


@dataclass(frozen=True, slots=True)
class BrokerId(_ExactIdentity):
    """Exact broker identity."""


@dataclass(frozen=True, slots=True)
class EnvironmentId(_ExactIdentity):
    """Exact venue environment identity."""


@dataclass(frozen=True, slots=True)
class AccountId(_ExactIdentity):
    """Exact broker account identity."""


@dataclass(frozen=True, slots=True)
class SymbolId(_ExactIdentity):
    """Exact broker symbol identity."""


@dataclass(frozen=True, slots=True)
class OrderId(_ExactIdentity):
    """Exact broker order identity."""


@dataclass(frozen=True, slots=True)
class RootFillId(_ExactIdentity):
    """Exact broker root-fill identity."""


@dataclass(frozen=True, slots=True)
class SourceEventId(_ExactIdentity):
    """Exact broker source-event identity."""


@dataclass(frozen=True, slots=True)
class ApplicationGenerationId(_ExactIdentity):
    """Exact reset-application generation identity."""


@dataclass(frozen=True, slots=True)
class EffectId(_ExactIdentity):
    """Exact broker-effect identity."""


@dataclass(frozen=True, slots=True)
class RequestOccurrenceId(_ExactIdentity):
    """Exact mutating-request occurrence identity."""


@dataclass(frozen=True, slots=True)
class ClientOrderId(_ExactIdentity):
    """Exact broker-visible creating-client identity."""


@dataclass(frozen=True, slots=True)
class ClaimOccurrenceId(_ExactIdentity):
    """Exact immutable dispatch-claim occurrence identity."""


@dataclass(frozen=True, slots=True)
class ClosureId(_ExactIdentity):
    """Exact immutable terminal-closure identity."""


@dataclass(frozen=True, slots=True)
class VenueInputId(_ExactIdentity):
    """Exact technical-deduplication identity for a venue input."""


@dataclass(frozen=True, slots=True)
class VenueObservationId(_ExactIdentity):
    """Exact correlated venue-observation identity."""


@dataclass(frozen=True, slots=True)
class ActorId(_ExactIdentity):
    """Exact human actor identity."""


@dataclass(frozen=True, slots=True)
class EvidenceReference(_ExactIdentity):
    """Exact external evidence reference supplied as command data."""


@dataclass(frozen=True, slots=True)
class MandateId(_ExactIdentity):
    """Exact immutable mandate identity."""


@dataclass(frozen=True, slots=True)
class AcquisitionMandateId(_ExactIdentity):
    """Exact immutable operator-approved acquisition mandate identity."""


@dataclass(frozen=True, slots=True)
class EmergencyRecoveryCompatibilityId(_ExactIdentity):
    """Exact immutable compatibility identity for mixed-generation recovery."""


@dataclass(frozen=True, slots=True)
class MarketDataSourceId(_ExactIdentity):
    """Exact immutable market-data source identity."""


@dataclass(frozen=True, slots=True)
class MarketOccurrenceId(_ExactIdentity):
    """Exact immutable market-data occurrence identity."""

    _bytes: bytes = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _ExactIdentity.__post_init__(self)
        if len(self.value) != 64 or any(
            character not in "0123456789abcdef" for character in self.value
        ):
            raise ValueError(
                "market occurrence identity must be lowercase SHA-256 hexadecimal text"
            )
        decoded = bytes.fromhex(self.value)
        encoded = self.value.encode("ascii")
        object.__setattr__(self, "_bytes", decoded)
        object.__setattr__(
            self,
            "_seal",
            sha256(int.to_bytes(len(encoded), 8, "big") + encoded + decoded).digest(),
        )


@dataclass(frozen=True, slots=True)
class MarketStreamGenerationId(_ExactIdentity):
    """Exact immutable market-data stream-generation identity."""

    _bytes: bytes = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _ExactIdentity.__post_init__(self)
        if len(self.value) != 64 or any(
            character not in "0123456789abcdef" for character in self.value
        ):
            raise ValueError(
                "market stream generation identity must be lowercase SHA-256 "
                "hexadecimal text"
            )
        decoded = bytes.fromhex(self.value)
        encoded = self.value.encode("ascii")
        object.__setattr__(self, "_bytes", decoded)
        object.__setattr__(
            self,
            "_seal",
            sha256(int.to_bytes(len(encoded), 8, "big") + encoded + decoded).digest(),
        )


@dataclass(frozen=True, slots=True)
class AcquisitionGenerationId(_ExactIdentity):
    """Exact immutable identity of one serial acquisition generation.

    This is an opaque value only.  Admission, controller currentness, and all
    effect authority remain outside E1.
    """

    _bytes: bytes = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _ExactIdentity.__post_init__(self)
        if len(self.value) != 64 or any(
            character not in "0123456789abcdef" for character in self.value
        ):
            raise ValueError(
                "acquisition generation identity must be lowercase SHA-256 "
                "hexadecimal text"
            )
        decoded = bytes.fromhex(self.value)
        encoded = self.value.encode("ascii")
        object.__setattr__(self, "_bytes", decoded)
        object.__setattr__(
            self,
            "_seal",
            sha256(int.to_bytes(len(encoded), 8, "big") + encoded + decoded).digest(),
        )


def _market_identity_is_canonical(
    value: MarketOccurrenceId | MarketStreamGenerationId,
) -> bool:
    """Re-derive the complete text, byte-cache, and seal relationship."""

    if (
        type(value) is not MarketOccurrenceId
        and type(value) is not MarketStreamGenerationId
    ):
        return False
    return (
        type(value.value) is str
        and type(value._bytes) is bytes
        and len(value._bytes) == 32
        and value.value == value._bytes.hex()
        and type(value._seal) is bytes
        and len(value._seal) == 32
        and value._seal
        == sha256(
            int.to_bytes(len(value.value.encode("ascii")), 8, "big")
            + value.value.encode("ascii")
            + value._bytes
        ).digest()
    )


def _acquisition_generation_id_is_canonical(
    value: AcquisitionGenerationId,
) -> bool:
    """Re-derive the complete text, byte-cache, and seal relationship."""

    if type(value) is not AcquisitionGenerationId:
        return False
    try:
        text = value.value
        decoded = value._bytes
        seal = value._seal
    except AttributeError:
        return False
    return (
        type(text) is str
        and type(decoded) is bytes
        and len(decoded) == 32
        and text == decoded.hex()
        and type(seal) is bytes
        and len(seal) == 32
        and seal
        == sha256(
            int.to_bytes(len(text.encode("ascii")), 8, "big")
            + text.encode("ascii")
            + decoded
        ).digest()
    )


@dataclass(frozen=True, slots=True)
class AuthorityInputId(_ExactIdentity):
    """Exact technical-deduplication identity for one authority input."""


@dataclass(frozen=True, slots=True)
class QueryClaimId(_ExactIdentity):
    """Exact one-shot broker query or reconciliation claim identity."""


@dataclass(frozen=True, slots=True)
class SessionId(_ExactIdentity):
    """Exact immutable trading-session identity."""


@dataclass(frozen=True, slots=True)
class EmergencyGrantId(_ExactIdentity):
    """Exact immutable emergency-reduction grant identity."""


@dataclass(frozen=True, slots=True)
class ManualFlattenId(_ExactIdentity):
    """Exact immutable manual-flatten workflow identity."""


@dataclass(frozen=True, slots=True)
class ExecutionFactKey:
    """The complete four-part deduplication key for one execution fact."""

    broker: BrokerId
    environment: EnvironmentId
    account: AccountId
    source_event_id: SourceEventId

    def __post_init__(self) -> None:
        if type(self.broker) is not BrokerId:
            raise TypeError("broker must be BrokerId")
        if type(self.environment) is not EnvironmentId:
            raise TypeError("environment must be EnvironmentId")
        if type(self.account) is not AccountId:
            raise TypeError("account must be AccountId")
        if type(self.source_event_id) is not SourceEventId:
            raise TypeError("source event must be SourceEventId")


@dataclass(frozen=True, slots=True)
class RootFillKey:
    """The account-scoped identity of one immutable root-fill sequence."""

    broker: BrokerId
    environment: EnvironmentId
    account: AccountId
    root_fill_id: RootFillId

    def __post_init__(self) -> None:
        if type(self.broker) is not BrokerId:
            raise TypeError("broker must be BrokerId")
        if type(self.environment) is not EnvironmentId:
            raise TypeError("environment must be EnvironmentId")
        if type(self.account) is not AccountId:
            raise TypeError("account must be AccountId")
        if type(self.root_fill_id) is not RootFillId:
            raise TypeError("root fill must be RootFillId")


@dataclass(frozen=True, slots=True)
class VenueLegKey:
    """Composite immutable identity of one concrete broker order leg."""

    broker: BrokerId
    environment: EnvironmentId
    account: AccountId
    order_id: OrderId

    def __post_init__(self) -> None:
        if type(self.broker) is not BrokerId:
            raise TypeError("broker must be BrokerId")
        if type(self.environment) is not EnvironmentId:
            raise TypeError("environment must be EnvironmentId")
        if type(self.account) is not AccountId:
            raise TypeError("account must be AccountId")
        if type(self.order_id) is not OrderId:
            raise TypeError("order_id must be OrderId")
