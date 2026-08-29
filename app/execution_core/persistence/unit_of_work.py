"""Atomic M2 transaction boundary with post-commit-only effect eligibility.

This module owns transaction lifecycle but performs no external publication.  The
fixed operation routes are added behind the private prepare/execute seams in
coherent slices; callers cannot inject callbacks or write plans.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
from dataclasses import replace as _replace
from enum import Enum as _Enum
import hashlib as _hashlib
from typing import TypeAlias as _TypeAlias
from typing import cast as _cast

from .. import acquisition as _acquisition
from .. import authority as _authority
from .. import identity as _identity
from .. import position as _position
from .. import protection as _protection
from .. import venue as _venue
from . import checkpoint_codec as _checkpoint_codec
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
    canonical_payload_bytes: bytes
    input_domain: _operations.OperationDomain
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    scope_id: int
    session_id: _identity.SessionId | None
    acquisition_generation_id: _identity.AcquisitionGenerationId | None
    market_source_profile_id: str | None
    stream_generation_id: _identity.MarketStreamGenerationId | None
    input_identity_sha256: str
    selection_proof: _records.RuntimeCheckpointSelectionProof
    authenticated_current: _checkpoint_codec.RuntimeCheckpointEnvelope


@_dataclass(frozen=True, slots=True)
class _ClaimedPrimaryInput:
    operation: _operations.M2Operation
    record: _records.DurableInputRecord


@_dataclass(frozen=True, slots=True)
class _RetainedTerminalInput:
    operation: _operations.M2Operation
    input_record: _records.DurableInputRecord
    outcome_record: _records.DurableInputOutcomeRecord


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


def _noncommitting_result(disposition: UnitOfWorkDisposition) -> UnitOfWorkResult:
    if disposition not in {
        UnitOfWorkDisposition.EXACT_REPLAY,
        UnitOfWorkDisposition.CONFLICT,
    }:
        raise ValueError("noncommitting result disposition is not admitted")
    return UnitOfWorkResult(disposition, None, None, None, None)


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
    try:
        payload = _operations.encode_m2_operation(operation)
        (
            input_domain,
            application_generation_id,
            execution_profile_id,
            scope_id,
            session_id,
            acquisition_generation_id,
            market_source_profile_id,
            stream_generation_id,
            input_identity_sha256,
        ) = _operations._derive_m2_durable_input_projection(operation)
        application = _repository.load_application_generation(
            connection,
            application_generation_id,
        )
        if (
            application.kind is not _records.RepositoryOutcomeKind.FOUND
            or type(application.record) is not _records.ApplicationGenerationRecord
        ):
            raise _TechnicalRefusal("application generation is not current proof")
        application_record = application.record
        if application_record.selected_execution_profile_id != execution_profile_id:
            raise _TechnicalRefusal("operation execution profile is not selected")
        if (
            market_source_profile_id is not None
            and market_source_profile_id
            != application_record.selected_market_source_profile_id
        ):
            raise _TechnicalRefusal("operation market profile is not selected")
        request = _records.RuntimeCheckpointSelectionRequest(
            application_generation_id,
            execution_profile_id,
            application_record.selected_market_source_profile_id,
            context.expected_checkpoint,
        )
        selected = _repository.select_runtime_checkpoint(connection, request)
        if (
            selected.kind is not _records.RepositoryOutcomeKind.FOUND
            or type(selected.record) is not _records.RuntimeCheckpointSelectionProof
            or not _records.RuntimeCheckpointSelectionProof._is_authentic(
                selected.record
            )
        ):
            raise _TechnicalRefusal("runtime checkpoint selection was refused")
        proof = selected.record
        selected_scope_ids = tuple(item.scope_id for item in proof._selection.scopes)
        if scope_id not in selected_scope_ids:
            raise _TechnicalRefusal("operation scope is not selected")
        if acquisition_generation_id is not None:
            selected_generations = (
                proof._selection.live_generations
                + proof._selection.unresolved_generations
            )
            if not any(
                item.acquisition_generation_id == acquisition_generation_id
                and item.scope_id == scope_id
                for item in selected_generations
            ):
                raise _TechnicalRefusal(
                    "operation acquisition generation is not selected"
                )
        if stream_generation_id is not None:
            if not any(
                item.stream_generation_id == stream_generation_id
                and item.scope_id == scope_id
                and item.acquisition_generation_id == acquisition_generation_id
                and item.source_profile_id == market_source_profile_id
                and item.session_id == session_id
                for item in proof._selection.streams
            ):
                raise _TechnicalRefusal("operation market stream is not selected")
        owner_rows = tuple(
            _checkpoint_codec._RuntimeCheckpointScopeOwners(*owner)
            for owner in context.scope_owners
        )
        authenticated_current = _checkpoint_codec._project_runtime_checkpoint(
            proof,
            context.venue,
            context.authority,
            owner_rows,
        )
    except _TechnicalRefusal:
        raise
    except (TypeError, ValueError, OverflowError) as exc:
        raise _TechnicalRefusal("runtime owner authentication failed") from exc
    return _PreparedOperation(
        operation,
        context,
        payload,
        input_domain,
        application_generation_id,
        execution_profile_id,
        scope_id,
        session_id,
        acquisition_generation_id,
        market_source_profile_id,
        stream_generation_id,
        input_identity_sha256,
        proof,
        authenticated_current,
    )


def _next_durable_input_created_ordinal(
    connection: _SQLiteConnectionProtocol,
) -> int:
    cursor = connection.execute(
        "SELECT COALESCE(MAX(created_ordinal), 0) + 1 FROM durable_input"
    )
    row = cursor.fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("ordinal query returned the wrong shape")
    return _require_positive_int("next durable input ordinal", row[0])


def _claim_primary_input(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    capability: _repository._RuntimeWriteCapability,
) -> _ClaimedPrimaryInput | _TransactionDecision:
    created_ordinal = _next_durable_input_created_ordinal(connection)
    candidate = _records.DurableInputRecord(
        prepared.application_generation_id,
        prepared.execution_profile_id,
        prepared.scope_id,
        prepared.input_domain,
        prepared.session_id,
        prepared.acquisition_generation_id,
        prepared.market_source_profile_id,
        prepared.stream_generation_id,
        prepared.input_identity_sha256,
        1,
        prepared.canonical_payload_bytes,
        _hashlib.sha256(prepared.canonical_payload_bytes).hexdigest(),
        "CLAIMED",
        created_ordinal,
    )
    claimed = _repository.claim_durable_input(
        connection,
        candidate,
        capability=capability,
    )
    fact = claimed.record
    if type(fact) is not _operations.InputDedupeFact:
        raise _TechnicalRefusal("primary input claim returned no exact fact")
    if (
        fact.input_domain != candidate.input_domain.value
        or fact.input_identity_sha256 != candidate.input_identity_sha256
        or fact.payload_sha256 != candidate.payload_sha256
        or fact.semantic_matches
    ):
        raise _TechnicalRefusal("primary input claim fact does not agree")
    if (
        claimed.kind is _records.RepositoryOutcomeKind.APPLIED
        and fact.kind is _operations.InputDedupeKind.UNSEEN
        and fact.retained_outcome_sha256 is None
    ):
        return _ClaimedPrimaryInput(prepared.operation, candidate)
    if (
        claimed.kind is _records.RepositoryOutcomeKind.FOUND
        and fact.kind is _operations.InputDedupeKind.EXACT_REPLAY
        and fact.retained_outcome_sha256 is not None
    ):
        return _TransactionDecision(
            False,
            _noncommitting_result(UnitOfWorkDisposition.EXACT_REPLAY),
            None,
        )
    if (
        claimed.kind is _records.RepositoryOutcomeKind.CONFLICT
        and fact.kind is _operations.InputDedupeKind.IDENTITY_CONFLICT
        and fact.retained_outcome_sha256 is None
    ):
        return _TransactionDecision(
            False,
            _noncommitting_result(UnitOfWorkDisposition.CONFLICT),
            None,
        )
    raise _TechnicalRefusal("primary input claim classification is inconsistent")


def _next_decision_receipt_ordinal(
    connection: _SQLiteConnectionProtocol,
) -> int:
    cursor = connection.execute(
        "SELECT COALESCE(MAX(receipt_ordinal), 0) + 1 FROM decision_receipt"
    )
    row = cursor.fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("receipt ordinal query returned the wrong shape")
    return _require_positive_int("next decision receipt ordinal", row[0])


def _next_semantic_key_created_ordinal(
    connection: _SQLiteConnectionProtocol,
) -> int:
    cursor = connection.execute(
        "SELECT COALESCE(MAX(created_ordinal), 0) + 1 FROM durable_input_semantic_key"
    )
    row = cursor.fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("semantic-key ordinal query returned the wrong shape")
    return _require_positive_int("next semantic-key ordinal", row[0])


def _require_applied_repository_outcome(
    name: str,
    outcome: _records.RepositoryOutcome[object],
) -> None:
    if outcome.kind is not _records.RepositoryOutcomeKind.APPLIED:
        raise _TechnicalRefusal(f"{name} was not applied exactly")


def _scope_execution(
    context: UnitOfWorkContext,
    scope_id: int,
) -> _position.ExecutionSnapshot:
    for (
        retained_scope_id,
        _acquisition_owner,
        execution,
        _protection_owner,
    ) in context.scope_owners:
        if retained_scope_id == scope_id:
            return execution
    raise _TechnicalRefusal("operation scope has no execution owner")


def _context_scope_rows(
    context: UnitOfWorkContext,
) -> tuple[_checkpoint_codec._RuntimeCheckpointScopeOwners, ...]:
    return tuple(
        _checkpoint_codec._RuntimeCheckpointScopeOwners(*owner)
        for owner in context.scope_owners
    )


def _bounded_context_changed(
    prepared: _PreparedOperation,
    successor_context: UnitOfWorkContext,
) -> bool:
    if (
        successor_context.venue is prepared.context.venue
        and successor_context.authority is prepared.context.authority
        and successor_context.scope_owners is prepared.context.scope_owners
    ):
        return False
    try:
        successor = _checkpoint_codec._project_runtime_checkpoint(
            prepared.selection_proof,
            successor_context.venue,
            successor_context.authority,
            _context_scope_rows(successor_context),
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise _TechnicalRefusal("successor owner comparison was refused") from exc
    return bool(
        successor.canonical_payload_bytes
        != prepared.authenticated_current.canonical_payload_bytes
    )


def _store_successor_checkpoint(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    successor_context: UnitOfWorkContext,
    capability: _repository._RuntimeWriteCapability,
) -> UnitOfWorkContext:
    request = _records.RuntimeCheckpointSelectionRequest(
        prepared.application_generation_id,
        prepared.execution_profile_id,
        prepared.selection_proof.request.market_source_profile_id,
        prepared.context.expected_checkpoint,
    )
    selected = _repository.select_runtime_checkpoint(connection, request)
    if (
        selected.kind is not _records.RepositoryOutcomeKind.FOUND
        or type(selected.record) is not _records.RuntimeCheckpointSelectionProof
        or not _records.RuntimeCheckpointSelectionProof._is_authentic(selected.record)
    ):
        raise _TechnicalRefusal("successor checkpoint selection was refused")
    proof = selected.record
    try:
        envelope = _checkpoint_codec._project_runtime_checkpoint(
            proof,
            successor_context.venue,
            successor_context.authority,
            _context_scope_rows(successor_context),
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise _TechnicalRefusal("successor owner projection was refused") from exc
    stored = _repository.store_runtime_checkpoint(
        connection,
        proof,
        envelope,
        capability=capability,
    )
    receipt = stored.record
    if (
        stored.kind is not _records.RepositoryOutcomeKind.APPLIED
        or type(receipt) is not _records.RuntimeCheckpointWriteReceipt
        or not _records.RuntimeCheckpointWriteReceipt._is_authentic(receipt)
        or receipt.predecessor_checkpoint != prepared.context.expected_checkpoint
    ):
        raise _TechnicalRefusal("successor checkpoint was not stored exactly")
    return _replace(
        successor_context,
        expected_checkpoint=receipt.resulting_checkpoint,
    )


def _decision_receipt(
    claimed: _records.DurableInputRecord,
    *,
    receipt_ordinal: int,
    owner_domain: str,
    owner_disposition: str,
    terminal_technical_state: str,
    checkpoint_reference: tuple[int, int, str] | None,
) -> _records.DecisionReceiptRecord:
    result_sha256 = _records._derive_owner_result_sha256(
        owner_domain,
        owner_disposition,
        terminal_technical_state,
        checkpoint_reference,
    )
    document = [
        1,
        "m2.decision-receipt/v1",
        _operations._encode_m2_m1_atom(claimed.application_generation_id),
        _operations._encode_m2_enum(claimed.input_domain),
        claimed.input_identity_sha256,
        receipt_ordinal,
        owner_domain,
        owner_disposition,
        terminal_technical_state,
        result_sha256,
        None if checkpoint_reference is None else [*checkpoint_reference],
    ]
    payload = _operations._encode_m2_document_kind(0x04, document)
    return _records.DecisionReceiptRecord(
        receipt_ordinal,
        claimed.application_generation_id,
        claimed.input_domain,
        claimed.input_identity_sha256,
        owner_domain,
        owner_disposition,
        terminal_technical_state,
        result_sha256,
        None if checkpoint_reference is None else checkpoint_reference[0],
        None if checkpoint_reference is None else checkpoint_reference[1],
        None if checkpoint_reference is None else checkpoint_reference[2],
        payload,
        len(payload),
        _hashlib.sha256(payload).hexdigest(),
    )


def _durable_input_outcome(
    receipt: _records.DecisionReceiptRecord,
) -> _records.DurableInputOutcomeRecord:
    checkpoint_reference = (
        None
        if receipt.checkpoint_currentness_head_ordinal is None
        else [
            receipt.checkpoint_currentness_head_ordinal,
            receipt.checkpoint_version_ordinal,
            receipt.checkpoint_payload_sha256,
        ]
    )
    document = [
        1,
        "m2.durable-input-outcome/v1",
        _operations._encode_m2_m1_atom(receipt.application_generation_id),
        _operations._encode_m2_enum(receipt.input_domain),
        receipt.input_identity_sha256,
        receipt.owner_domain,
        receipt.owner_disposition,
        receipt.terminal_technical_state,
        receipt.result_sha256,
        checkpoint_reference,
        receipt.receipt_ordinal,
        receipt.receipt_sha256,
    ]
    payload = _operations._encode_m2_document_kind(0x03, document)
    return _records.DurableInputOutcomeRecord(
        receipt.application_generation_id,
        receipt.input_domain,
        receipt.input_identity_sha256,
        receipt.owner_domain,
        receipt.owner_disposition,
        receipt.terminal_technical_state,
        receipt.result_sha256,
        receipt.checkpoint_currentness_head_ordinal,
        receipt.checkpoint_version_ordinal,
        receipt.checkpoint_payload_sha256,
        receipt.receipt_ordinal,
        receipt.receipt_sha256,
        payload,
        len(payload),
        _hashlib.sha256(payload).hexdigest(),
    )


def _load_terminal_semantic_input(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    key_kind: _operations.InputSemanticKeyKind,
    key_bytes: bytes,
) -> _RetainedTerminalInput | None:
    retained = _repository.load_durable_input_by_semantic_key(
        connection,
        key_kind,
        prepared.application_generation_id,
        prepared.execution_profile_id,
        prepared.scope_id,
        key_bytes,
    )
    if retained.kind is _records.RepositoryOutcomeKind.ABSENT:
        return None
    if (
        retained.kind is not _records.RepositoryOutcomeKind.FOUND
        or type(retained.record) is not _records.DurableInputRecord
    ):
        raise _TechnicalRefusal("semantic-key lookup was not exact")
    retained_input = retained.record
    try:
        retained_operation = _operations.decode_m2_operation(
            retained_input.canonical_payload_bytes
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise _TechnicalRefusal("retained semantic input is not canonical") from exc
    retained_outcome = _repository.load_durable_input_outcome(
        connection,
        retained_input.application_generation_id,
        retained_input.input_domain,
        retained_input.input_identity_sha256,
    )
    if (
        retained_outcome.kind is not _records.RepositoryOutcomeKind.FOUND
        or type(retained_outcome.record) is not _records.DurableInputOutcomeRecord
        or retained_outcome.record.terminal_technical_state != "TERMINAL"
    ):
        raise _TechnicalRefusal("retained semantic outcome is not terminal evidence")
    return _RetainedTerminalInput(
        retained_operation,
        retained_input,
        retained_outcome.record,
    )


def _authority_query_key_bytes(
    prepared: _PreparedOperation,
    command: _authority.ClaimBrokerQuery,
) -> bytes:
    return _operations.encode_m2_semantic_key(
        _operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
        (
            prepared.application_generation_id.value,
            prepared.execution_profile_id,
            prepared.scope_id,
        ),
        ("query-claim-id", command.query_claim_id.value),
    )


def _authority_query_observation(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    command: _authority.ClaimBrokerQuery,
) -> _authority._M2AuthorityQueryObservationProof:
    key_bytes = _authority_query_key_bytes(prepared, command)
    retained = _load_terminal_semantic_input(
        connection,
        prepared,
        _operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
        key_bytes,
    )
    if retained is None:
        return _authority._m2_authority_query_observation_from_direct_evidence(
            prepared.context.authority,
            command,
            retained_command=None,
            retained_input_bytes=None,
            retained_outcome_bytes=None,
        )
    if (
        type(retained.operation) is not _operations.AuthorityOperation
        or type(retained.operation.command) is not _authority.ClaimBrokerQuery
        or retained.operation.command.query_claim_id != command.query_claim_id
    ):
        raise _TechnicalRefusal("retained query input has the wrong owner identity")
    return _authority._m2_authority_query_observation_from_direct_evidence(
        prepared.context.authority,
        command,
        retained_command=retained.operation.command,
        retained_input_bytes=retained.input_record.canonical_payload_bytes,
        retained_outcome_bytes=retained.outcome_record.canonical_outcome_bytes,
    )


def _store_authority_query_semantic_key(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    command: _authority.ClaimBrokerQuery,
    capability: _repository._RuntimeWriteCapability,
) -> None:
    key_bytes = _authority_query_key_bytes(prepared, command)
    record = _records.DurableInputSemanticKeyRecord(
        _operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1,
        prepared.application_generation_id,
        prepared.execution_profile_id,
        prepared.scope_id,
        key_bytes,
        _hashlib.sha256(key_bytes).hexdigest(),
        claimed.application_generation_id,
        claimed.input_domain,
        claimed.input_identity_sha256,
        _next_semantic_key_created_ordinal(connection),
    )
    _require_applied_repository_outcome(
        "authority query semantic key",
        _repository.store_durable_input_semantic_key(
            connection,
            record,
            capability=capability,
        ),
    )


def _authority_manual_key_bytes(
    prepared: _PreparedOperation,
    command: _authority.BeginManualFlatten | _authority.AdvanceManualFlatten,
) -> bytes:
    return _operations.encode_m2_semantic_key(
        _operations.InputSemanticKeyKind.AUTHORITY_MANUAL_FLATTEN_V1,
        (
            prepared.application_generation_id.value,
            prepared.execution_profile_id,
            prepared.scope_id,
        ),
        ("manual-flatten-id", command.flatten_id.value),
    )


def _authority_manual_observation(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    command: _authority.BeginManualFlatten | _authority.AdvanceManualFlatten,
) -> _authority._M2AuthorityManualObservationProof:
    execution = _scope_execution(prepared.context, prepared.scope_id)
    key_bytes = _authority_manual_key_bytes(prepared, command)
    retained = _load_terminal_semantic_input(
        connection,
        prepared,
        _operations.InputSemanticKeyKind.AUTHORITY_MANUAL_FLATTEN_V1,
        key_bytes,
    )
    if retained is None:
        return _authority._m2_authority_manual_observation_from_direct_evidence(
            prepared.context.authority,
            command,
            active_symbol_id=execution.position.scope.symbol_id,
            retained_command=None,
            retained_input_bytes=None,
            retained_outcome_bytes=None,
        )
    if (
        type(retained.operation) is not _operations.AuthorityOperation
        or type(retained.operation.command) is not _authority.BeginManualFlatten
        or retained.operation.command.flatten_id != command.flatten_id
    ):
        raise _TechnicalRefusal("retained manual input has the wrong owner identity")
    return _authority._m2_authority_manual_observation_from_direct_evidence(
        prepared.context.authority,
        command,
        active_symbol_id=execution.position.scope.symbol_id,
        retained_command=retained.operation.command,
        retained_input_bytes=retained.input_record.canonical_payload_bytes,
        retained_outcome_bytes=retained.outcome_record.canonical_outcome_bytes,
    )


def _store_authority_manual_semantic_key(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    command: _authority.BeginManualFlatten,
    capability: _repository._RuntimeWriteCapability,
) -> None:
    key_bytes = _authority_manual_key_bytes(prepared, command)
    record = _records.DurableInputSemanticKeyRecord(
        _operations.InputSemanticKeyKind.AUTHORITY_MANUAL_FLATTEN_V1,
        prepared.application_generation_id,
        prepared.execution_profile_id,
        prepared.scope_id,
        key_bytes,
        _hashlib.sha256(key_bytes).hexdigest(),
        claimed.application_generation_id,
        claimed.input_domain,
        claimed.input_identity_sha256,
        _next_semantic_key_created_ordinal(connection),
    )
    _require_applied_repository_outcome(
        "authority manual semantic key",
        _repository.store_durable_input_semantic_key(
            connection,
            record,
            capability=capability,
        ),
    )


def _complete_claimed_input(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    *,
    owner_domain: str,
    owner_disposition: str,
    successor_context: UnitOfWorkContext,
    checkpoint_changed: bool,
    pending_effect: _PostCommitEffectCandidate | None,
    capability: _repository._RuntimeWriteCapability,
) -> _TransactionDecision:
    if checkpoint_changed:
        completed_context = _store_successor_checkpoint(
            connection,
            prepared,
            successor_context,
            capability,
        )
        head = completed_context.expected_checkpoint
        checkpoint_reference: tuple[int, int, str] | None = (
            head.currentness_head_ordinal,
            head.checkpoint_version_ordinal,
            head.checkpoint_sha256,
        )
    else:
        if successor_context is not prepared.context:
            raise _TechnicalRefusal("no-change result substituted an owner context")
        completed_context = successor_context
        checkpoint_reference = None
    terminal_state = (
        "RECONCILIATION_PENDING"
        if owner_disposition == "RECONCILIATION_REQUIRED"
        else "TERMINAL"
    )
    receipt = _decision_receipt(
        claimed,
        receipt_ordinal=_next_decision_receipt_ordinal(connection),
        owner_domain=owner_domain,
        owner_disposition=owner_disposition,
        terminal_technical_state=terminal_state,
        checkpoint_reference=checkpoint_reference,
    )
    outcome = _durable_input_outcome(receipt)
    _require_applied_repository_outcome(
        "decision receipt",
        _repository.store_decision_receipt(
            connection,
            receipt,
            capability=capability,
        ),
    )
    _require_applied_repository_outcome(
        "durable input outcome",
        _repository.store_durable_input_outcome(
            connection,
            outcome,
            capability=capability,
        ),
    )
    finalized = _replace(claimed, technical_state=terminal_state)
    _require_applied_repository_outcome(
        "durable input finalization",
        _repository.finalize_durable_input(
            connection,
            finalized,
            capability=capability,
        ),
    )
    result = UnitOfWorkResult(
        UnitOfWorkDisposition.COMMITTED,
        owner_domain,
        owner_disposition,
        completed_context,
        None,
    )
    return _TransactionDecision(True, result, pending_effect)


def _execute_authority_operation(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    capability: _repository._RuntimeWriteCapability,
) -> _TransactionDecision:
    operation = prepared.operation
    if type(operation) is not _operations.AuthorityOperation:
        raise _TechnicalRefusal("authority route received the wrong operation")
    if type(operation.command) not in (
        _authority.EngageKill,
        _authority.ClaimBrokerQuery,
        _authority.BeginManualFlatten,
        _authority.AdvanceManualFlatten,
    ):
        raise _TechnicalRefusal("authority command route is not implemented")
    execution = _scope_execution(prepared.context, prepared.scope_id)
    manual_command = (
        _cast(
            _authority.BeginManualFlatten | _authority.AdvanceManualFlatten,
            operation.command,
        )
        if type(operation.command)
        in (_authority.BeginManualFlatten, _authority.AdvanceManualFlatten)
        else None
    )
    manual_observation = (
        _authority_manual_observation(connection, prepared, manual_command)
        if manual_command is not None
        else None
    )
    query_observation = (
        _authority_query_observation(connection, prepared, operation.command)
        if type(operation.command) is _authority.ClaimBrokerQuery
        else None
    )
    transition = _authority._m2_apply_execution_authority_input(
        prepared.context.authority,
        execution,
        operation.command,
        manual_observation=manual_observation,
        query_observation=query_observation,
    )
    if transition.created_effect_ids:
        raise _TechnicalRefusal("authority transition emitted unwritten effects")
    if (
        transition.venue_transitions
        or transition.acquisition_receipt is not None
        or transition.acquisition_claim_receipt is not None
    ):
        raise _TechnicalRefusal("authority transition emitted an unrelated derivative")
    if type(operation.command) is _authority.ClaimBrokerQuery:
        if transition.disposition is _authority.AuthorityDisposition.APPLIED:
            fresh_query = transition.fresh_claim
            if (
                type(fresh_query) is not _authority._FreshQueryClaim
                or fresh_query.query_claim_id != operation.command.query_claim_id
                or fresh_query.symbol_id != operation.command.symbol_id
                or fresh_query.kind is not operation.command.kind
            ):
                raise _TechnicalRefusal(
                    "query transition omitted its exact fresh claim"
                )
            _store_authority_query_semantic_key(
                connection,
                prepared,
                claimed,
                operation.command,
                capability,
            )
        elif transition.fresh_claim is not None:
            raise _TechnicalRefusal("non-applied query emitted a fresh claim")
    else:
        if transition.fresh_claim is not None:
            raise _TechnicalRefusal("authority transition emitted a fresh claim")
        if (
            type(operation.command) is _authority.BeginManualFlatten
            and transition.disposition is _authority.AuthorityDisposition.APPLIED
        ):
            _store_authority_manual_semantic_key(
                connection,
                prepared,
                claimed,
                operation.command,
                capability,
            )
    candidate_context = (
        UnitOfWorkContext(
            prepared.context.expected_checkpoint,
            transition.state.venue,
            transition.state,
            prepared.context.scope_owners,
        )
        if transition.state is not prepared.context.authority
        else prepared.context
    )
    changed = _bounded_context_changed(prepared, candidate_context)
    successor_context = candidate_context if changed else prepared.context
    return _complete_claimed_input(
        connection,
        prepared,
        claimed,
        owner_domain="AUTHORITY",
        owner_disposition=transition.disposition.value,
        successor_context=successor_context,
        checkpoint_changed=changed,
        pending_effect=None,
        capability=capability,
    )


def _execute_prepared(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    capability: _repository._RuntimeWriteCapability,
) -> _TransactionDecision:
    primary = _claim_primary_input(connection, prepared, capability)
    if type(primary) is _TransactionDecision:
        return primary
    claimed = _cast(_ClaimedPrimaryInput, primary)
    if type(prepared.operation) is _operations.AuthorityOperation:
        return _execute_authority_operation(
            connection,
            prepared,
            claimed.record,
            capability,
        )
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
