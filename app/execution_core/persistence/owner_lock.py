"""Fail-closed process-owner evidence for M2 cold startup."""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
from typing import NoReturn as _NoReturn


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


@_dataclass(frozen=True, slots=True, init=False)
class OwnerLeaseEvidence:
    """One factory-issued lease observation bound to an exact lock port."""

    owner_occurrence_id: str
    _port_token: object
    _lease_token: object

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("OwnerLeaseEvidence is lock-port-issued only")

    def __copy__(self) -> OwnerLeaseEvidence:
        raise TypeError("OwnerLeaseEvidence cannot be copied")

    def __deepcopy__(self, memo: object) -> OwnerLeaseEvidence:
        del memo
        raise TypeError("OwnerLeaseEvidence cannot be copied")

    def __reduce__(self) -> _NoReturn:
        raise TypeError("OwnerLeaseEvidence cannot be reduced")

    def __reduce_ex__(self, protocol: object) -> _NoReturn:
        del protocol
        raise TypeError("OwnerLeaseEvidence cannot be reduced")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("OwnerLeaseEvidence cannot be subclassed")


class OwnerLockPort:
    """Narrow injected process-lock capability; it performs no takeover inference."""

    def __init__(self) -> None:
        self._owner_lock_port_token = object()
        self._owner_lock_issued: dict[int, OwnerLeaseEvidence] = {}

    def _issue(self, owner_occurrence_id: str) -> OwnerLeaseEvidence:
        occurrence = _require_text("owner_occurrence_id", owner_occurrence_id)
        evidence = object.__new__(OwnerLeaseEvidence)
        object.__setattr__(evidence, "owner_occurrence_id", occurrence)
        object.__setattr__(evidence, "_port_token", self._owner_lock_port_token)
        object.__setattr__(evidence, "_lease_token", object())
        self._owner_lock_issued[id(evidence)] = evidence
        return evidence

    def _recognizes(self, evidence: object) -> bool:
        return bool(
            type(evidence) is OwnerLeaseEvidence
            and evidence._port_token is self._owner_lock_port_token
            and self._owner_lock_issued.get(id(evidence)) is evidence
        )

    def acquire(self) -> OwnerLeaseEvidence | None:
        raise NotImplementedError

    def is_current(self, evidence: OwnerLeaseEvidence) -> bool:
        raise NotImplementedError

    def release(self, evidence: OwnerLeaseEvidence) -> None:
        raise NotImplementedError


def _owner_lease_is_authentic(
    port: OwnerLockPort,
    evidence: object,
) -> bool:
    return type(port) is not OwnerLockPort and port._recognizes(evidence)


__all__ = ("OwnerLeaseEvidence", "OwnerLockPort")
