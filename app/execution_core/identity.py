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
class ExecutionFactKey:
    """The complete four-part deduplication key for one execution fact."""

    broker: BrokerId
    environment: EnvironmentId
    account: AccountId
    source_event_id: SourceEventId

    def __post_init__(self) -> None:
        if not isinstance(self.broker, BrokerId):
            raise TypeError("broker must be BrokerId")
        if not isinstance(self.environment, EnvironmentId):
            raise TypeError("environment must be EnvironmentId")
        if not isinstance(self.account, AccountId):
            raise TypeError("account must be AccountId")
        if not isinstance(self.source_event_id, SourceEventId):
            raise TypeError("source event must be SourceEventId")


@dataclass(frozen=True, slots=True)
class RootFillKey:
    """The account-scoped identity of one immutable root-fill sequence."""

    broker: BrokerId
    environment: EnvironmentId
    account: AccountId
    root_fill_id: RootFillId

    def __post_init__(self) -> None:
        if not isinstance(self.broker, BrokerId):
            raise TypeError("broker must be BrokerId")
        if not isinstance(self.environment, EnvironmentId):
            raise TypeError("environment must be EnvironmentId")
        if not isinstance(self.account, AccountId):
            raise TypeError("account must be AccountId")
        if not isinstance(self.root_fill_id, RootFillId):
            raise TypeError("root fill must be RootFillId")
