"""Exact immutable identities for canonical broker execution facts."""

from __future__ import annotations

from dataclasses import dataclass


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
