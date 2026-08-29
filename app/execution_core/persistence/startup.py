"""Fail-closed M2 cold-start coordinator."""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
from enum import Enum as _Enum

from .. import identity as _identity
from . import market_recovery as _market_recovery
from . import owner_lock as _owner_lock
from . import unit_of_work as _unit_of_work


def _require_digest(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be exact text")
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{name} must be lowercase SHA-256 text")
    return value


class StartupPhase(str, _Enum):
    BOOTSTRAPPING = "BOOTSTRAPPING"
    RECONCILING = "RECONCILING"
    SERVING = "SERVING"
    NON_SERVING = "NON_SERVING"


class StartupDisposition(str, _Enum):
    SERVING = "SERVING"
    NON_SERVING = "NON_SERVING"


class StartupRefusalCode(str, _Enum):
    OWNER_DENIED = "OWNER_DENIED"
    OWNER_LOST = "OWNER_LOST"
    DATASTORE_INTEGRITY = "DATASTORE_INTEGRITY"
    CURRENT_PROOF_FAILURE = "CURRENT_PROOF_FAILURE"
    UNRESOLVED_EFFECTS = "UNRESOLVED_EFFECTS"
    INVALIDATION_FAILURE = "INVALIDATION_FAILURE"
    UNSUPPORTED_SOURCE = "UNSUPPORTED_SOURCE"
    FENCE_FAILURE = "FENCE_FAILURE"
    BASELINE_FAILURE = "BASELINE_FAILURE"
    INTERNAL_INTEGRITY = "INTERNAL_INTEGRITY"


@_dataclass(frozen=True, slots=True)
class StartupRequest:
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    market_source_profile_id: str

    def __post_init__(self) -> None:
        if type(self) is not StartupRequest:
            raise TypeError("StartupRequest rejects subclasses")
        if (
            type(self.application_generation_id)
            is not _identity.ApplicationGenerationId
        ):
            raise TypeError("application_generation_id must be exact")
        _identity.ApplicationGenerationId(self.application_generation_id.value)
        _require_digest("execution_profile_id", self.execution_profile_id)
        _require_digest("market_source_profile_id", self.market_source_profile_id)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("StartupRequest cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class StartupResult:
    phase: StartupPhase
    disposition: StartupDisposition
    refusal_code: StartupRefusalCode | None
    owner_lease: _owner_lock.OwnerLeaseEvidence | None
    successor_context: _unit_of_work.UnitOfWorkContext | None

    def __post_init__(self) -> None:
        if type(self) is not StartupResult:
            raise TypeError("StartupResult rejects subclasses")
        if type(self.phase) is not StartupPhase:
            raise TypeError("phase must be exact StartupPhase")
        if type(self.disposition) is not StartupDisposition:
            raise TypeError("disposition must be exact StartupDisposition")
        if self.disposition is StartupDisposition.SERVING:
            if self.phase is not StartupPhase.SERVING or self.refusal_code is not None:
                raise ValueError("serving result has inconsistent final state")
            if type(self.owner_lease) is not _owner_lock.OwnerLeaseEvidence:
                raise TypeError("serving result requires exact owner evidence")
            if type(self.successor_context) is not _unit_of_work.UnitOfWorkContext:
                raise TypeError("serving result requires exact successor context")
            return
        if (
            self.phase is not StartupPhase.NON_SERVING
            or type(self.refusal_code) is not StartupRefusalCode
            or self.owner_lease is not None
            or self.successor_context is not None
        ):
            raise ValueError(
                "non-serving result must retain only an exact refusal code"
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("StartupResult cannot be subclassed")


def _non_serving(code: StartupRefusalCode) -> StartupResult:
    return StartupResult(
        StartupPhase.NON_SERVING,
        StartupDisposition.NON_SERVING,
        code,
        None,
        None,
    )


def start_startup(
    request: StartupRequest,
    *,
    owner_lock: _owner_lock.OwnerLockPort,
    datastore: object,
    effect_queries: _market_recovery.EffectQueryPort,
    market_source: _market_recovery.MarketSourcePort,
) -> StartupResult:
    """Run the bounded cold-start sequence; implementation is completed in this WO."""

    del datastore, effect_queries, market_source
    if type(request) is not StartupRequest or not isinstance(
        owner_lock, _owner_lock.OwnerLockPort
    ):
        return _non_serving(StartupRefusalCode.INTERNAL_INTEGRITY)
    evidence = owner_lock.acquire()
    if evidence is None or not _owner_lock._owner_lease_is_authentic(
        owner_lock, evidence
    ):
        return _non_serving(StartupRefusalCode.OWNER_DENIED)
    if not owner_lock.is_current(evidence):
        owner_lock.release(evidence)
        return _non_serving(StartupRefusalCode.OWNER_LOST)
    owner_lock.release(evidence)
    return _non_serving(StartupRefusalCode.INTERNAL_INTEGRITY)


__all__ = (
    "StartupDisposition",
    "StartupPhase",
    "StartupRefusalCode",
    "StartupRequest",
    "StartupResult",
    "start_startup",
)
