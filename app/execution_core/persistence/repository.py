"""Narrow typed SQLite repository for accepted M2-I2 families (WO-0167).

Every operation takes an explicit already-open connection, calls the
accepted ``verify_schema_connection`` guard first, and never commits,
begins, rolls back, opens, discovers, or configures anything. Loads return
explicit typed outcomes; a successful SELECT never implies serving.
Writes are plain inserts or expected-key guarded statements; integrity
defects surface as CONFLICT/INTEGRITY_FAILURE outcomes instead of being
swallowed. No dynamic SQL, no upserts, no reducer semantics.
"""

from __future__ import annotations as _annotations

import sqlite3 as _sqlite3

from . import records as _records
from .records import (
    AcceptanceSetRecord,
    AcquisitionGenerationCurrentRecord,
    AcquisitionGenerationRecord,
    ApplicationGenerationRecord,
    DispatchClaimRecord,
    ExecutionFactHeadRecord,
    KernelCheckpointRecord,
    RepositoryOutcome,
    RepositoryOutcomeKind,
    ScopeRecord,
)
from .schema import verify_schema_connection as _verify_schema_connection


def _committed() -> _records.RepositoryOutcome:
    return _records.RepositoryOutcome(_records.RepositoryOutcomeKind.COMMITTED)


def _write(
    connection: _sqlite3.Connection,
    sql: str,
    parameters: tuple,
) -> _records.RepositoryOutcome:
    _verify_schema_connection(connection)
    try:
        connection.execute(sql, parameters)
    except _sqlite3.IntegrityError:
        return _records.RepositoryOutcome(
            _records.RepositoryOutcomeKind.CONFLICT
        )
    except _sqlite3.DatabaseError:
        return _records.RepositoryOutcome(
            _records.RepositoryOutcomeKind.INTEGRITY_FAILURE
        )
    return _committed()


def _load(
    connection: _sqlite3.Connection,
    sql: str,
    parameters: tuple,
    build,
) -> _records.RepositoryOutcome:
    _verify_schema_connection(connection)
    try:
        row = connection.execute(sql, parameters).fetchone()
    except _sqlite3.DatabaseError:
        return _records.RepositoryOutcome(
            _records.RepositoryOutcomeKind.INTEGRITY_FAILURE
        )
    if row is None:
        return _records.RepositoryOutcome(_records.RepositoryOutcomeKind.ABSENT)
    record = build(row)
    if record is None:
        return _records.RepositoryOutcome(
            _records.RepositoryOutcomeKind.INTEGRITY_FAILURE
        )
    return _records.RepositoryOutcome(
        _records.RepositoryOutcomeKind.FOUND, record
    )


_APPLICATION_GENERATION_COLUMNS = (
    "application_generation_id, selected_execution_profile_id,"
    " selected_market_source_profile_id, activation_ordinal"
)


def store_application_generation(
    connection: _sqlite3.Connection,
    record: _records.ApplicationGenerationRecord,
) -> _records.RepositoryOutcome:
    return _write(
        connection,
        f"INSERT INTO application_generation ({_APPLICATION_GENERATION_COLUMNS})"
        " VALUES (?, ?, ?, ?)",
        (
            record.application_generation_id,
            record.selected_execution_profile_id,
            record.selected_market_source_profile_id,
            record.activation_ordinal,
        ),
    )


def load_application_generation(
    connection: _sqlite3.Connection,
    application_generation_id: str,
) -> _records.RepositoryOutcome:
    return _load(
        connection,
        f"SELECT {_APPLICATION_GENERATION_COLUMNS}"
        " FROM application_generation WHERE application_generation_id = ?",
        (application_generation_id,),
        lambda row: _records.ApplicationGenerationRecord(*row),
    )


_SCOPE_COLUMNS = "scope_id, application_generation_id, execution_profile_id, symbol_text"


def store_scope(
    connection: _sqlite3.Connection,
    record: _records.ScopeRecord,
) -> _records.RepositoryOutcome:
    return _write(
        connection,
        f"INSERT INTO acquisition_scope ({_SCOPE_COLUMNS})"
        " VALUES (?, ?, ?, ?)",
        (
            record.scope_id,
            record.application_generation_id,
            record.execution_profile_id,
            record.symbol_text,
        ),
    )


def load_scope(
    connection: _sqlite3.Connection,
    scope_id: int,
) -> _records.RepositoryOutcome:
    return _load(
        connection,
        f"SELECT {_SCOPE_COLUMNS} FROM acquisition_scope WHERE scope_id = ?",
        (scope_id,),
        lambda row: _records.ScopeRecord(*row),
    )


_ACQUISITION_GENERATION_COLUMNS = (
    "acquisition_generation_id, scope_id, status, successor_ordinal,"
    " predecessor_generation_id, mandate_commitment_sha256,"
    " emergency_compatibility_sha256"
)


def store_acquisition_generation(
    connection: _sqlite3.Connection,
    record: _records.AcquisitionGenerationRecord,
) -> _records.RepositoryOutcome:
    return _write(
        connection,
        f"INSERT INTO acquisition_generation"
        f" ({_ACQUISITION_GENERATION_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            record.acquisition_generation_id,
            record.scope_id,
            record.status,
            record.successor_ordinal,
            record.predecessor_generation_id,
            record.mandate_commitment_sha256,
            record.emergency_compatibility_sha256,
        ),
    )


def load_acquisition_generation_current(
    connection: _sqlite3.Connection,
    acquisition_generation_id: str,
) -> _records.RepositoryOutcome:
    columns = (
        "acquisition_generation_id, scope_id,"
        " current_economics_head_ordinal, unresolved_effect_count,"
        " active_protection_count"
    )
    return _load(
        connection,
        f"SELECT {columns} FROM acquisition_generation_current"
        " WHERE acquisition_generation_id = ?",
        (acquisition_generation_id,),
        lambda row: _records.AcquisitionGenerationCurrentRecord(*row),
    )


def store_acquisition_generation_current(
    connection: _sqlite3.Connection,
    record: _records.AcquisitionGenerationCurrentRecord,
) -> _records.RepositoryOutcome:
    columns = (
        "acquisition_generation_id, scope_id,"
        " current_economics_head_ordinal, unresolved_effect_count,"
        " active_protection_count"
    )
    guarded = (
        "INSERT INTO acquisition_generation_current ("
        + columns
        + ") VALUES (?, ?, ?, ?, ?)"
    )
    return _write(
        connection,
        guarded,
        (
            record.acquisition_generation_id,
            record.scope_id,
            record.current_economics_head_ordinal,
            record.unresolved_effect_count,
            record.active_protection_count,
        ),
    )


_CHECKPOINT_COLUMNS = (
    "application_generation_id, currentness_head_ordinal,"
    " checkpoint_sha256, checkpoint_version_ordinal"
)


def record_kernel_checkpoint(
    connection: _sqlite3.Connection,
    record: _records.KernelCheckpointRecord,
) -> _records.RepositoryOutcome:
    return _write(
        connection,
        f"INSERT INTO kernel_checkpoint ({_CHECKPOINT_COLUMNS})"
        " VALUES (?, ?, ?, ?)",
        (
            record.application_generation_id,
            record.currentness_head_ordinal,
            record.checkpoint_sha256,
            record.checkpoint_version_ordinal,
        ),
    )


def load_kernel_checkpoint(
    connection: _sqlite3.Connection,
    application_generation_id: str,
) -> _records.RepositoryOutcome:
    return _load(
        connection,
        f"SELECT {_CHECKPOINT_COLUMNS} FROM kernel_checkpoint"
        " WHERE application_generation_id = ?",
        (application_generation_id,),
        lambda row: _records.KernelCheckpointRecord(*row),
    )


_FACT_HEAD_COLUMNS = "root_fill_key_id, fact_id, fact_ordinal"


def record_execution_fact_head(
    connection: _sqlite3.Connection,
    record: _records.ExecutionFactHeadRecord,
) -> _records.RepositoryOutcome:
    return _write(
        connection,
        f"INSERT INTO execution_fact_head ({_FACT_HEAD_COLUMNS})"
        " VALUES (?, ?, ?)",
        (record.root_fill_key_id, record.fact_id, record.fact_ordinal),
    )


def load_execution_fact_head(
    connection: _sqlite3.Connection,
    root_fill_key_id: int,
) -> _records.RepositoryOutcome:
    return _load(
        connection,
        f"SELECT {_FACT_HEAD_COLUMNS} FROM execution_fact_head"
        " WHERE root_fill_key_id = ?",
        (root_fill_key_id,),
        lambda row: _records.ExecutionFactHeadRecord(*row),
    )


_CLAIM_COLUMNS = (
    "claim_id, effect_id, execution_profile_id, claim_occurrence_external,"
    " claim_ordinal"
)


def record_dispatch_claim(
    connection: _sqlite3.Connection,
    record: _records.DispatchClaimRecord,
) -> _records.RepositoryOutcome:
    return _write(
        connection,
        f"INSERT INTO dispatch_claim ({_CLAIM_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?)",
        (
            record.claim_id,
            record.effect_id,
            record.execution_profile_id,
            record.claim_occurrence_external,
            record.claim_ordinal,
        ),
    )


def load_dispatch_claim(
    connection: _sqlite3.Connection,
    claim_id: int,
) -> _records.RepositoryOutcome:
    return _load(
        connection,
        f"SELECT {_CLAIM_COLUMNS} FROM dispatch_claim WHERE claim_id = ?",
        (claim_id,),
        lambda row: _records.DispatchClaimRecord(*row),
    )


_ACCEPTANCE_SET_COLUMNS = "acceptance_set_id, effect_id"


def store_acceptance_set(
    connection: _sqlite3.Connection,
    record: _records.AcceptanceSetRecord,
) -> _records.RepositoryOutcome:
    return _write(
        connection,
        f"INSERT INTO acceptance_set ({_ACCEPTANCE_SET_COLUMNS})"
        " VALUES (?, ?)",
        (record.acceptance_set_id, record.effect_id),
    )


def load_acceptance_set(
    connection: _sqlite3.Connection,
    acceptance_set_id: int,
) -> _records.RepositoryOutcome:
    return _load(
        connection,
        f"SELECT {_ACCEPTANCE_SET_COLUMNS} FROM acceptance_set"
        " WHERE acceptance_set_id = ?",
        (acceptance_set_id,),
        lambda row: _records.AcceptanceSetRecord(*row),
    )


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
    "load_acceptance_set",
    "load_acquisition_generation_current",
    "load_application_generation",
    "load_dispatch_claim",
    "load_execution_fact_head",
    "load_kernel_checkpoint",
    "load_scope",
    "record_dispatch_claim",
    "record_execution_fact_head",
    "record_kernel_checkpoint",
    "store_acceptance_set",
    "store_acquisition_generation",
    "store_acquisition_generation_current",
    "store_application_generation",
    "store_scope",
)
