from __future__ import annotations

import copy
import pickle

import pytest

from app.execution_core import identity
from app.execution_core import protection
from app.execution_core.persistence import market_recovery
from app.execution_core.persistence import owner_lock
from app.execution_core.persistence import startup


_APPLICATION = identity.ApplicationGenerationId("app-generation-startup")
_EXECUTION_PROFILE = "a" * 64
_MARKET_PROFILE = "b" * 64


def test_startup_public_surface_and_frozen_values_are_exact() -> None:
    assert startup.__all__ == (
        "StartupDisposition",
        "StartupPhase",
        "StartupRefusalCode",
        "StartupRequest",
        "StartupResult",
        "start_startup",
    )
    assert tuple(item.value for item in startup.StartupPhase) == (
        "BOOTSTRAPPING",
        "RECONCILING",
        "SERVING",
        "NON_SERVING",
    )
    assert tuple(item.value for item in startup.StartupDisposition) == (
        "SERVING",
        "NON_SERVING",
    )
    assert tuple(item.value for item in startup.StartupRefusalCode) == (
        "OWNER_DENIED",
        "OWNER_LOST",
        "DATASTORE_INTEGRITY",
        "CURRENT_PROOF_FAILURE",
        "UNRESOLVED_EFFECTS",
        "INVALIDATION_FAILURE",
        "UNSUPPORTED_SOURCE",
        "FENCE_FAILURE",
        "BASELINE_FAILURE",
        "INTERNAL_INTEGRITY",
    )


def test_startup_request_contains_only_immutable_selection_coordinates() -> None:
    request = startup.StartupRequest(
        _APPLICATION,
        _EXECUTION_PROFILE,
        _MARKET_PROFILE,
    )

    assert request.application_generation_id == _APPLICATION
    assert request.execution_profile_id == _EXECUTION_PROFILE
    assert request.market_source_profile_id == _MARKET_PROFILE
    assert request.__slots__ == (
        "application_generation_id",
        "execution_profile_id",
        "market_source_profile_id",
    )
    with pytest.raises((AttributeError, TypeError)):
        request.execution_profile_id = "c" * 64  # type: ignore[misc]
    with pytest.raises(ValueError):
        startup.StartupRequest(_APPLICATION, "not-a-digest", _MARKET_PROFILE)


def test_non_serving_result_cannot_leak_owner_or_context() -> None:
    result = startup.StartupResult(
        startup.StartupPhase.NON_SERVING,
        startup.StartupDisposition.NON_SERVING,
        startup.StartupRefusalCode.OWNER_DENIED,
        None,
        None,
    )

    assert result.owner_lease is None
    assert result.successor_context is None
    with pytest.raises(ValueError):
        startup.StartupResult(
            startup.StartupPhase.RECONCILING,
            startup.StartupDisposition.NON_SERVING,
            None,
            None,
            None,
        )


class _FakeOwnerLock(owner_lock.OwnerLockPort):
    def __init__(self, occurrence: str) -> None:
        super().__init__()
        self.occurrence = occurrence
        self.current = True
        self.released = False

    def acquire(self) -> owner_lock.OwnerLeaseEvidence | None:
        return self._issue(self.occurrence)

    def is_current(self, evidence: owner_lock.OwnerLeaseEvidence) -> bool:
        return self.current and self._recognizes(evidence)

    def release(self, evidence: owner_lock.OwnerLeaseEvidence) -> None:
        if self._recognizes(evidence):
            self.released = True
            self.current = False


def test_owner_lease_is_factory_issued_noncopyable_and_port_bound() -> None:
    first = _FakeOwnerLock("owner-occurrence-1")
    second = _FakeOwnerLock("owner-occurrence-2")
    evidence = first.acquire()

    assert type(evidence) is owner_lock.OwnerLeaseEvidence
    assert evidence is not None
    assert evidence.owner_occurrence_id == "owner-occurrence-1"
    assert first.is_current(evidence)
    assert not second.is_current(evidence)
    for copier in (copy.copy, copy.deepcopy, pickle.dumps):
        with pytest.raises(TypeError):
            copier(evidence)

    forged = object.__new__(owner_lock.OwnerLeaseEvidence)
    for name in evidence.__slots__:
        object.__setattr__(forged, name, getattr(evidence, name))
    assert not first.is_current(forged)

    first.release(evidence)
    assert first.released
    assert not first.is_current(evidence)


def test_owner_lock_namespace_is_exact() -> None:
    assert owner_lock.__all__ == ("OwnerLeaseEvidence", "OwnerLockPort")


def test_market_recovery_namespace_and_exact_refusal_result() -> None:
    assert market_recovery.__all__ == (
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
    request = market_recovery.EffectQueryRequest(
        _APPLICATION,
        _EXECUTION_PROFILE,
        7,
        identity.EffectId("effect-1"),
        identity.ClaimOccurrenceId("claim-1"),
    )
    unresolved = market_recovery.EffectQueryResult(
        request,
        market_recovery.EffectQueryDisposition.UNRESOLVED,
        None,
    )
    assert unresolved.operation is None
    with pytest.raises(ValueError):
        market_recovery.EffectQueryResult(
            request,
            market_recovery.EffectQueryDisposition.RESOLVED,
            None,
        )


def test_market_subscription_request_pins_exact_source_coordinates() -> None:
    request = market_recovery.MarketSubscriptionRequest(
        _MARKET_PROFILE,
        identity.MarketStreamGenerationId("c" * 64),
        protection.MarketSequenceMode.SEQUENCED,
        "cold-retry-1",
    )

    assert request.market_source_profile_id == _MARKET_PROFILE
    assert request.sequence_mode is protection.MarketSequenceMode.SEQUENCED
    with pytest.raises(TypeError):
        market_recovery.MarketSubscriptionRequest(
            _MARKET_PROFILE,
            identity.MarketStreamGenerationId("c" * 64),
            "STRICT",  # type: ignore[arg-type]
            "cold-retry-1",
        )
