"""Immutable typed records for the WO-0167 narrow SQLite repository.

Each record mirrors exactly one accepted M2-I2 table family and carries only
public constructor values. Records are frozen, deterministic, and bound to
their profile/scope/version coordinates; they contain no behavior.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any


class RepositoryOutcomeKind(enum.Enum):
    COMMITTED = "committed"
    FOUND = "found"
    ABSENT = "absent"
    CONFLICT = "conflict"
    INTEGRITY_FAILURE = "integrity-failure"


@dataclass(frozen=True, slots=True)
class RepositoryOutcome:
    """Explicit typed result: never implies serving by itself."""

    kind: RepositoryOutcomeKind
    record: Any = None


@dataclass(frozen=True, slots=True)
class ApplicationGenerationRecord:
    application_generation_id: str
    selected_execution_profile_id: str
    selected_market_source_profile_id: str
    activation_ordinal: int


@dataclass(frozen=True, slots=True)
class ScopeRecord:
    scope_id: int
    application_generation_id: str
    execution_profile_id: str
    symbol_text: str


@dataclass(frozen=True, slots=True)
class AcquisitionGenerationRecord:
    acquisition_generation_id: str
    scope_id: int
    status: str
    successor_ordinal: int
    predecessor_generation_id: str | None
    mandate_commitment_sha256: str
    emergency_compatibility_sha256: str


@dataclass(frozen=True, slots=True)
class AcquisitionGenerationCurrentRecord:
    acquisition_generation_id: str
    scope_id: int
    current_economics_head_ordinal: int
    unresolved_effect_count: int
    active_protection_count: int


@dataclass(frozen=True, slots=True)
class KernelCheckpointRecord:
    application_generation_id: str
    currentness_head_ordinal: int
    checkpoint_sha256: str
    checkpoint_version_ordinal: int


@dataclass(frozen=True, slots=True)
class ExecutionFactHeadRecord:
    root_fill_key_id: int
    fact_id: int
    fact_ordinal: int


@dataclass(frozen=True, slots=True)
class DispatchClaimRecord:
    claim_id: int
    effect_id: int
    execution_profile_id: str
    claim_occurrence_external: str
    claim_ordinal: int


@dataclass(frozen=True, slots=True)
class AcceptanceSetRecord:
    acceptance_set_id: int
    effect_id: int


__all__ = (
    "AcceptanceSetRecord",
    "AcquisitionGenerationCurrentRecord",
    "AcquisitionGenerationRecord",
    "ApplicationGenerationRecord",
    "DispatchClaimRecord",
    "ExecutionFactHeadRecord",
    "KernelCheckpointRecord",
    "RepositoryOutcome",
    "RepositoryOutcomeKind",
    "ScopeRecord",
)
