"""Atomic M2 transaction boundary with post-commit-only effect eligibility.

This module owns transaction lifecycle but performs no external publication.  The
fixed operation routes are added behind the private prepare/execute seams in
coherent slices; callers cannot inject callbacks or write plans.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
from dataclasses import replace as _replace
from enum import Enum as _Enum
from typing import TypeAlias as _TypeAlias
from typing import cast as _cast

from .. import acquisition as _acquisition
from .. import authority as _authority
from .. import position as _position
from .. import protection as _protection
from .. import venue as _venue
from . import operations as _operations
from . import records as _records
from . import repository as _repository
from .schema import SQLiteConnectionProtocol as _SQLiteConnectionProtocol


_ScopeOwner: _TypeAlias = tuple[
    int,
    _acquisition.AcquisitionControllerState | None,
    _position.ExecutionSnapshot,
    _protection.PositionProtectionState | None,
]


class UnitOfWorkDisposition(str, _Enum):
    COMMITTED = "COMMITTED"
    REFUSED = "REFUSED"
    EXACT_REPLAY = "EXACT_REPLAY"
    CONFLICT = "CONFLICT"
    RECONCILIATION_ONLY = "RECONCILIATION_ONLY"


def _require_positive_int(name: str, value: object) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact integer")
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def _require_sha256(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be exact text")
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{name} must be lowercase SHA-256 hexadecimal text")
    return value


@_dataclass(frozen=True, slots=True)
class PostCommitEffectEligibility:
    outbox_sequence: int
    effect_id: int
    claim_id: int
    payload_sha256: str

    def __post_init__(self) -> None:
        if type(self) is not PostCommitEffectEligibility:
            raise TypeError("PostCommitEffectEligibility rejects subclasses")
        _require_positive_int("outbox_sequence", self.outbox_sequence)
        _require_positive_int("effect_id", self.effect_id)
        _require_positive_int("claim_id", self.claim_id)
        _require_sha256("payload_sha256", self.payload_sha256)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("PostCommitEffectEligibility cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class UnitOfWorkContext:
    expected_checkpoint: _records.KernelCheckpointRecord
    venue: _venue.VenueRecoveryBook
    authority: _authority.ExecutionAuthorityState
    scope_owners: tuple[_ScopeOwner, ...]

    def __post_init__(self) -> None:
        if type(self) is not UnitOfWorkContext:
            raise TypeError("UnitOfWorkContext rejects subclasses")
        if type(self.expected_checkpoint) is not _records.KernelCheckpointRecord:
            raise TypeError("expected_checkpoint must be exact KernelCheckpointRecord")
        if type(self.venue) is not _venue.VenueRecoveryBook:
            raise TypeError("venue must be exact VenueRecoveryBook")
        if type(self.authority) is not _authority.ExecutionAuthorityState:
            raise TypeError("authority must be exact ExecutionAuthorityState")
        _authority._validate_authority_state(self.authority)
        if self.authority.venue is not self.venue:
            raise ValueError("authority must retain the exact venue owner")
        if type(self.scope_owners) is not tuple:
            raise TypeError("scope_owners must be an exact tuple")
        prior_scope_id = 0
        for owner in self.scope_owners:
            if type(owner) is not tuple or len(owner) != 4:
                raise TypeError("scope owner must be an exact four-member tuple")
            scope_id, acquisition, execution, protection = owner
            _require_positive_int("scope_id", scope_id)
            if scope_id <= prior_scope_id:
                raise ValueError("scope owners must be strictly scope-ID ordered")
            prior_scope_id = scope_id
            if (
                acquisition is not None
                and type(acquisition) is not _acquisition.AcquisitionControllerState
            ):
                raise TypeError("acquisition owner must be exact or None")
            if type(execution) is not _position.ExecutionSnapshot:
                raise TypeError("execution owner must be exact ExecutionSnapshot")
            if (
                protection is not None
                and type(protection) is not _protection.PositionProtectionState
            ):
                raise TypeError("protection owner must be exact or None")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("UnitOfWorkContext cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class UnitOfWorkResult:
    disposition: UnitOfWorkDisposition
    owner_domain: str | None
    owner_disposition: str | None
    successor_context: UnitOfWorkContext | None
    effect_eligibility: PostCommitEffectEligibility | None

    def __post_init__(self) -> None:
        if type(self) is not UnitOfWorkResult:
            raise TypeError("UnitOfWorkResult rejects subclasses")
        if type(self.disposition) is not UnitOfWorkDisposition:
            raise TypeError("disposition must be exact UnitOfWorkDisposition")
        if self.disposition is UnitOfWorkDisposition.COMMITTED:
            if type(self.owner_domain) is not str or not self.owner_domain:
                raise ValueError("committed result requires an owner domain")
            if type(self.owner_disposition) is not str or not self.owner_disposition:
                raise ValueError("committed result requires an owner disposition")
            if type(self.successor_context) is not UnitOfWorkContext:
                raise TypeError("committed result requires an exact successor context")
            if (
                self.effect_eligibility is not None
                and type(self.effect_eligibility) is not PostCommitEffectEligibility
            ):
                raise TypeError("effect eligibility must be exact")
        elif any(
            member is not None
            for member in (
                self.owner_domain,
                self.owner_disposition,
                self.successor_context,
                self.effect_eligibility,
            )
        ):
            raise ValueError(
                "non-committed result cannot publish owner state or effects"
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("UnitOfWorkResult cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class _PostCommitEffectCandidate:
    outbox_sequence: int
    effect_id: int
    claim_id: int
    payload_sha256: str

    def __post_init__(self) -> None:
        _require_positive_int("outbox_sequence", self.outbox_sequence)
        _require_positive_int("effect_id", self.effect_id)
        _require_positive_int("claim_id", self.claim_id)
        _require_sha256("payload_sha256", self.payload_sha256)


@_dataclass(frozen=True, slots=True)
class _PreparedOperation:
    operation: _operations.M2Operation
    context: UnitOfWorkContext


@_dataclass(frozen=True, slots=True)
class _TransactionDecision:
    commit: bool
    result: UnitOfWorkResult
    pending_effect: _PostCommitEffectCandidate | None

    def __post_init__(self) -> None:
        if type(self.commit) is not bool:
            raise TypeError("transaction decision commit must be exact bool")
        if type(self.result) is not UnitOfWorkResult:
            raise TypeError("transaction decision result must be exact")
        if (
            self.pending_effect is not None
            and type(self.pending_effect) is not _PostCommitEffectCandidate
        ):
            raise TypeError("pending effect must be exact")
        if self.commit:
            if self.result.disposition is not UnitOfWorkDisposition.COMMITTED:
                raise ValueError("commit decision requires a committed owner result")
        elif (
            self.result.disposition is UnitOfWorkDisposition.COMMITTED
            or self.pending_effect is not None
        ):
            raise ValueError(
                "rollback decision cannot publish committed state or effects"
            )


class _TechnicalRefusal(Exception):
    pass


def _refused_result() -> UnitOfWorkResult:
    return UnitOfWorkResult(UnitOfWorkDisposition.REFUSED, None, None, None, None)


def _reconciliation_result() -> UnitOfWorkResult:
    return UnitOfWorkResult(
        UnitOfWorkDisposition.RECONCILIATION_ONLY,
        None,
        None,
        None,
        None,
    )


def _canonicalize_operation(operation: object) -> _operations.M2Operation:
    encoded = _operations.encode_m2_operation(_cast(_operations.M2Operation, operation))
    decoded = _operations.decode_m2_operation(encoded)
    if (
        type(decoded) is not type(operation)
        or _operations.encode_m2_operation(decoded) != encoded
    ):
        raise ValueError("operation is not an exact canonical M2 operation")
    return decoded


def _prepare_transaction(
    connection: _SQLiteConnectionProtocol,
    operation: _operations.M2Operation,
    context: UnitOfWorkContext,
) -> _PreparedOperation:
    del connection
    return _PreparedOperation(operation, context)


def _execute_prepared(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    capability: _repository._RuntimeWriteCapability,
) -> _TransactionDecision:
    del connection, prepared, capability
    raise _TechnicalRefusal("operation route is not implemented in this slice")


def _rollback_once(
    connection: _SQLiteConnectionProtocol,
    capability: _repository._RuntimeWriteCapability | None,
) -> None:
    if capability is not None:
        _repository._retire_runtime_write_lease(connection, capability)
    connection.execute("ROLLBACK")


def _close_ambiguous_connection(connection: _SQLiteConnectionProtocol) -> None:
    close = getattr(connection, "close", None)
    if close is None:
        return
    try:
        close()
    except Exception:
        return


def execute_unit_of_work(
    connection: _SQLiteConnectionProtocol,
    operation: object,
    context: UnitOfWorkContext,
) -> UnitOfWorkResult:
    """Execute one fixed M2 route in one transaction with no external I/O."""

    if type(context) is not UnitOfWorkContext:
        return _refused_result()
    try:
        canonical_operation = _canonicalize_operation(operation)
    except (TypeError, ValueError, OverflowError):
        return _refused_result()
    if getattr(connection, "in_transaction", False) is True:
        return _refused_result()

    connection.execute("BEGIN IMMEDIATE")
    capability: _repository._RuntimeWriteCapability | None = None
    try:
        prepared = _prepare_transaction(connection, canonical_operation, context)
        capability = _repository._activate_runtime_write_lease(connection)
        decision = _execute_prepared(connection, prepared, capability)
    except _TechnicalRefusal:
        _rollback_once(connection, capability)
        return _refused_result()
    except Exception:
        _rollback_once(connection, capability)
        raise

    if not decision.commit:
        _rollback_once(connection, capability)
        return decision.result

    _repository._retire_runtime_write_lease(connection, capability)
    try:
        connection.execute("COMMIT")
    except Exception:
        _close_ambiguous_connection(connection)
        return _reconciliation_result()
    if decision.pending_effect is None:
        return decision.result
    pending = decision.pending_effect
    eligibility = PostCommitEffectEligibility(
        pending.outbox_sequence,
        pending.effect_id,
        pending.claim_id,
        pending.payload_sha256,
    )
    return _replace(decision.result, effect_eligibility=eligibility)


__all__ = (
    "PostCommitEffectEligibility",
    "UnitOfWorkContext",
    "UnitOfWorkDisposition",
    "UnitOfWorkResult",
    "execute_unit_of_work",
)
