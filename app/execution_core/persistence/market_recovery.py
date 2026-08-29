"""Typed observation-only capabilities for M2 effect and market recovery."""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
from enum import Enum as _Enum
from typing import NoReturn as _NoReturn
from typing import cast as _cast

from .. import identity as _identity
from .. import protection as _protection
from . import operations as _operations


def _require_text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be exact text")
    if not value or not value.strip():
        raise ValueError(f"{name} must be nonblank")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{name} must be valid UTF-8 text") from exc
    return value


def _require_digest(name: str, value: object) -> str:
    text = _require_text(name, value)
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise ValueError(f"{name} must be lowercase SHA-256 text")
    return text


def _require_positive_int(name: str, value: object) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


class EffectQueryDisposition(str, _Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    UNSUPPORTED = "UNSUPPORTED"


@_dataclass(frozen=True, slots=True)
class EffectQueryRequest:
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    scope_id: int
    effect_id: _identity.EffectId
    claim_occurrence_id: _identity.ClaimOccurrenceId

    def __post_init__(self) -> None:
        if type(self) is not EffectQueryRequest:
            raise TypeError("EffectQueryRequest rejects subclasses")
        if (
            type(self.application_generation_id)
            is not _identity.ApplicationGenerationId
        ):
            raise TypeError("application_generation_id must be exact")
        _identity.ApplicationGenerationId(self.application_generation_id.value)
        _require_digest("execution_profile_id", self.execution_profile_id)
        _require_positive_int("scope_id", self.scope_id)
        if type(self.effect_id) is not _identity.EffectId:
            raise TypeError("effect_id must be exact EffectId")
        _identity.EffectId(self.effect_id.value)
        if type(self.claim_occurrence_id) is not _identity.ClaimOccurrenceId:
            raise TypeError("claim_occurrence_id must be exact ClaimOccurrenceId")
        _identity.ClaimOccurrenceId(self.claim_occurrence_id.value)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("EffectQueryRequest cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class EffectQueryResult:
    request: EffectQueryRequest
    disposition: EffectQueryDisposition
    operation: _operations.VenueRecoveryOperation | None

    def __post_init__(self) -> None:
        if type(self) is not EffectQueryResult:
            raise TypeError("EffectQueryResult rejects subclasses")
        if type(self.request) is not EffectQueryRequest:
            raise TypeError("request must be exact EffectQueryRequest")
        if type(self.disposition) is not EffectQueryDisposition:
            raise TypeError("disposition must be exact EffectQueryDisposition")
        if self.disposition is EffectQueryDisposition.RESOLVED:
            if type(self.operation) is not _operations.VenueRecoveryOperation:
                raise ValueError("resolved query requires one exact recovery operation")
        elif self.operation is not None:
            raise ValueError("non-resolved query cannot carry an operation")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("EffectQueryResult cannot be subclassed")


class EffectQueryPort:
    def query(self, request: EffectQueryRequest) -> EffectQueryResult:
        raise NotImplementedError


@_dataclass(frozen=True, slots=True)
class MarketSubscriptionRequest:
    market_source_profile_id: str
    stream_generation_id: _identity.MarketStreamGenerationId
    sequence_mode: _protection.MarketSequenceMode
    retry_coordinate: str

    def __post_init__(self) -> None:
        if type(self) is not MarketSubscriptionRequest:
            raise TypeError("MarketSubscriptionRequest rejects subclasses")
        _require_digest("market_source_profile_id", self.market_source_profile_id)
        if type(self.stream_generation_id) is not _identity.MarketStreamGenerationId:
            raise TypeError("stream_generation_id must be exact")
        if not _identity._market_identity_is_canonical(self.stream_generation_id):
            raise ValueError("stream_generation_id must be canonical")
        if type(self.sequence_mode) is not _protection.MarketSequenceMode:
            raise TypeError("sequence_mode must be exact MarketSequenceMode")
        _require_text("retry_coordinate", self.retry_coordinate)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("MarketSubscriptionRequest cannot be subclassed")


class _NonCopyableEvidence:
    __slots__ = ()

    def __copy__(self) -> object:
        raise TypeError(f"{type(self).__name__} cannot be copied")

    def __deepcopy__(self, memo: object) -> object:
        del memo
        raise TypeError(f"{type(self).__name__} cannot be copied")

    def __reduce__(self) -> _NoReturn:
        raise TypeError(f"{type(self).__name__} cannot be reduced")

    def __reduce_ex__(self, protocol: object) -> _NoReturn:
        del protocol
        raise TypeError(f"{type(self).__name__} cannot be reduced")


@_dataclass(frozen=True, slots=True, init=False)
class MarketSubscriptionEvidence(_NonCopyableEvidence):
    request: MarketSubscriptionRequest
    acknowledgement_id: str
    _port_token: object
    _evidence_token: object

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("MarketSubscriptionEvidence is source-port-issued only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("MarketSubscriptionEvidence cannot be subclassed")


@_dataclass(frozen=True, slots=True, init=False)
class MarketFenceEvidence(_NonCopyableEvidence):
    subscription: MarketSubscriptionEvidence
    fence_ordinal: int
    covers_pre_ack: bool
    _port_token: object
    _evidence_token: object

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("MarketFenceEvidence is source-port-issued only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("MarketFenceEvidence cannot be subclassed")


@_dataclass(frozen=True, slots=True, init=False)
class MarketBaselineEvidence(_NonCopyableEvidence):
    subscription: MarketSubscriptionEvidence
    fence: MarketFenceEvidence
    occurrence: _protection.MarketOccurrence
    excluded_through_ordinal: int
    _port_token: object
    _evidence_token: object

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("MarketBaselineEvidence is source-port-issued only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("MarketBaselineEvidence cannot be subclassed")


class MarketSourcePort:
    """Observation-only market source used after durable cold invalidation."""

    def __init__(self) -> None:
        self._market_source_port_token = object()
        self._market_source_issued: dict[int, object] = {}

    def _retain(self, evidence: object) -> object:
        self._market_source_issued[id(evidence)] = evidence
        return evidence

    def _recognizes(self, evidence: object) -> bool:
        if type(evidence) not in {
            MarketSubscriptionEvidence,
            MarketFenceEvidence,
            MarketBaselineEvidence,
        }:
            return False
        exact = _cast(
            MarketSubscriptionEvidence | MarketFenceEvidence | MarketBaselineEvidence,
            evidence,
        )
        return bool(
            exact._port_token is self._market_source_port_token
            and self._market_source_issued.get(id(exact)) is exact
        )

    def _issue_subscription(
        self,
        request: MarketSubscriptionRequest,
        acknowledgement_id: str,
    ) -> MarketSubscriptionEvidence:
        if type(request) is not MarketSubscriptionRequest:
            raise TypeError("request must be exact MarketSubscriptionRequest")
        acknowledgement = _require_text("acknowledgement_id", acknowledgement_id)
        evidence = object.__new__(MarketSubscriptionEvidence)
        object.__setattr__(evidence, "request", request)
        object.__setattr__(evidence, "acknowledgement_id", acknowledgement)
        object.__setattr__(evidence, "_port_token", self._market_source_port_token)
        object.__setattr__(evidence, "_evidence_token", object())
        return self._retain(evidence)  # type: ignore[return-value]

    def _issue_fence(
        self,
        subscription: MarketSubscriptionEvidence,
        fence_ordinal: int,
        *,
        covers_pre_ack: bool,
    ) -> MarketFenceEvidence:
        if not self._recognizes(subscription):
            raise ValueError("subscription is not source-port-authentic")
        ordinal = _require_positive_int("fence_ordinal", fence_ordinal)
        if type(covers_pre_ack) is not bool:
            raise TypeError("covers_pre_ack must be exact bool")
        evidence = object.__new__(MarketFenceEvidence)
        object.__setattr__(evidence, "subscription", subscription)
        object.__setattr__(evidence, "fence_ordinal", ordinal)
        object.__setattr__(evidence, "covers_pre_ack", covers_pre_ack)
        object.__setattr__(evidence, "_port_token", self._market_source_port_token)
        object.__setattr__(evidence, "_evidence_token", object())
        return self._retain(evidence)  # type: ignore[return-value]

    def _issue_baseline(
        self,
        subscription: MarketSubscriptionEvidence,
        fence: MarketFenceEvidence,
        occurrence: _protection.MarketOccurrence,
        excluded_through_ordinal: int,
    ) -> MarketBaselineEvidence:
        if not self._recognizes(subscription) or not self._recognizes(fence):
            raise ValueError("market evidence is not source-port-authentic")
        if fence.subscription is not subscription:
            raise ValueError("fence is not bound to subscription")
        if type(occurrence) is not _protection.MarketOccurrence:
            raise TypeError("occurrence must be exact MarketOccurrence")
        if not _protection._market_occurrence_is_authentic(occurrence):
            raise ValueError("occurrence must be authentic")
        excluded = _require_positive_int(
            "excluded_through_ordinal", excluded_through_ordinal
        )
        evidence = object.__new__(MarketBaselineEvidence)
        object.__setattr__(evidence, "subscription", subscription)
        object.__setattr__(evidence, "fence", fence)
        object.__setattr__(evidence, "occurrence", occurrence)
        object.__setattr__(evidence, "excluded_through_ordinal", excluded)
        object.__setattr__(evidence, "_port_token", self._market_source_port_token)
        object.__setattr__(evidence, "_evidence_token", object())
        return self._retain(evidence)  # type: ignore[return-value]

    def subscribe(
        self, request: MarketSubscriptionRequest
    ) -> MarketSubscriptionEvidence | None:
        raise NotImplementedError

    def post_ack_fence(
        self, subscription: MarketSubscriptionEvidence
    ) -> MarketFenceEvidence | None:
        raise NotImplementedError

    def baseline_at_fence(
        self,
        subscription: MarketSubscriptionEvidence,
        fence: MarketFenceEvidence,
    ) -> MarketBaselineEvidence | None:
        raise NotImplementedError

    def is_current(
        self,
        subscription: MarketSubscriptionEvidence,
        fence: MarketFenceEvidence,
    ) -> bool:
        raise NotImplementedError


__all__ = (
    "EffectQueryDisposition",
    "EffectQueryPort",
    "EffectQueryRequest",
    "EffectQueryResult",
    "MarketBaselineEvidence",
    "MarketFenceEvidence",
    "MarketSourcePort",
    "MarketSubscriptionEvidence",
    "MarketSubscriptionRequest",
)
