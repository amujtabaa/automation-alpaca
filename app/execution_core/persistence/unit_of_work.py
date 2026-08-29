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
from typing import TypeVar as _TypeVar
from typing import cast as _cast

from .. import acquisition as _acquisition
from .. import authority as _authority
from .. import fills as _fills
from .. import identity as _identity
from .. import position as _position
from .. import protection as _protection
from .. import recovery as _recovery
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
_RepositoryRecordT = _TypeVar("_RepositoryRecordT")


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
class _SelectedScopeAuthority:
    scope: _records.ScopeRecord
    controller: _records.SymbolControllerRecord
    generation: _records.AcquisitionGenerationRecord
    protection: _records.ProtectionAuthorityRecord


@_dataclass(frozen=True, slots=True)
class _SelectedAcquisitionAuthority:
    scope: _records.ScopeRecord
    controller: _records.SymbolControllerRecord
    generation: _records.AcquisitionGenerationRecord
    generation_current: _records.AcquisitionGenerationCurrentRecord
    protection: _records.ProtectionAuthorityRecord
    stream: _records.MarketStreamAuthorityRecord
    cursor: _records.MarketCursorRecord


@_dataclass(frozen=True, slots=True)
class _PersistedEffectClaim:
    effect: _records.VenueEffectRecord
    claim: _records.DispatchClaimRecord


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


def _require_retained_checkpoint_payload(
    context: UnitOfWorkContext,
    authenticated_current: _checkpoint_codec.RuntimeCheckpointEnvelope,
    loaded: _records.RepositoryOutcome[object],
) -> None:
    retained = loaded.record
    if (
        loaded.kind is not _records.RepositoryOutcomeKind.FOUND
        or type(retained) is not _checkpoint_codec.RuntimeCheckpointEnvelope
        or not _checkpoint_codec.RuntimeCheckpointEnvelope._is_authentic(retained)
        or retained._provenance != "LOADED"
        or retained.canonical_payload_bytes
        != authenticated_current.canonical_payload_bytes
        or retained.payload_sha256 != context.expected_checkpoint.checkpoint_sha256
    ):
        raise _TechnicalRefusal(
            "runtime owners do not equal the retained checkpoint payload"
        )


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
        loaded = _repository.load_runtime_checkpoint(
            connection,
            _records.RuntimeCheckpointLoadRequest(
                application_generation_id,
                execution_profile_id,
                application_record.selected_market_source_profile_id,
            ),
        )
        _require_retained_checkpoint_payload(context, authenticated_current, loaded)
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


def _next_root_fill_key_id(connection: _SQLiteConnectionProtocol) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(root_fill_key_id), 0) + 1 FROM root_fill"
    ).fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("root-fill ID query returned the wrong shape")
    return _require_positive_int("next root-fill ID", row[0])


def _next_execution_fact_id(connection: _SQLiteConnectionProtocol) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(fact_id), 0) + 1 FROM execution_fact"
    ).fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("execution-fact ID query returned the wrong shape")
    return _require_positive_int("next execution-fact ID", row[0])


def _next_execution_fact_ordinal(connection: _SQLiteConnectionProtocol) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(fact_ordinal), 0) + 1 FROM execution_fact"
    ).fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("execution-fact ordinal query returned the wrong shape")
    return _require_positive_int("next execution-fact ordinal", row[0])


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


def _next_venue_effect_id(connection: _SQLiteConnectionProtocol) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(effect_id), 0) + 1 FROM venue_effect"
    ).fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("effect ID query returned the wrong shape")
    return _require_positive_int("next effect ID", row[0])


def _next_venue_effect_created_ordinal(
    connection: _SQLiteConnectionProtocol,
) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(created_ordinal), 0) + 1 FROM venue_effect"
    ).fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("effect ordinal query returned the wrong shape")
    return _require_positive_int("next effect ordinal", row[0])


def _next_acceptance_set_id(connection: _SQLiteConnectionProtocol) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(acceptance_set_id), 0) + 1 FROM acceptance_set"
    ).fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("acceptance-set ID query returned the wrong shape")
    return _require_positive_int("next acceptance-set ID", row[0])


def _next_dispatch_claim_id(connection: _SQLiteConnectionProtocol) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(claim_id), 0) + 1 FROM dispatch_claim"
    ).fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("claim ID query returned the wrong shape")
    return _require_positive_int("next claim ID", row[0])


def _next_dispatch_claim_ordinal(
    connection: _SQLiteConnectionProtocol,
) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(claim_ordinal), 0) + 1 FROM dispatch_claim"
    ).fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("claim ordinal query returned the wrong shape")
    return _require_positive_int("next claim ordinal", row[0])


def _next_acceptance_evidence_id(
    connection: _SQLiteConnectionProtocol,
) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(evidence_id), 0) + 1 FROM acceptance_evidence"
    ).fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("evidence ID query returned the wrong shape")
    return _require_positive_int("next evidence ID", row[0])


def _next_acceptance_evidence_ordinal(
    connection: _SQLiteConnectionProtocol,
) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(evidence_ordinal), 0) + 1 FROM acceptance_evidence"
    ).fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("evidence ordinal query returned the wrong shape")
    return _require_positive_int("next evidence ordinal", row[0])


def _next_closure_id(connection: _SQLiteConnectionProtocol) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(CASE WHEN closure_id > 0 THEN closure_id END), 0) + 1"
        " FROM closure_chain"
    ).fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("closure ID query returned the wrong shape")
    return _require_positive_int("next closure ID", row[0])


def _next_broker_outbox_sequence(
    connection: _SQLiteConnectionProtocol,
) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(outbox_sequence), 0) + 1 FROM broker_outbox"
    ).fetchone()
    if type(row) is not tuple or len(row) != 1:
        raise _TechnicalRefusal("outbox sequence query returned the wrong shape")
    return _require_positive_int("next outbox sequence", row[0])


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


def _required_repository_record(
    name: str,
    outcome: _records.RepositoryOutcome[_RepositoryRecordT],
    expected_type: type[_RepositoryRecordT],
) -> _RepositoryRecordT:
    record = outcome.record
    if (
        outcome.kind is not _records.RepositoryOutcomeKind.FOUND
        or type(record) is not expected_type
    ):
        raise _TechnicalRefusal(f"{name} direct proof is absent or invalid")
    return record


def _require_repository_absence(
    name: str,
    outcome: _records.RepositoryOutcome[_RepositoryRecordT],
) -> None:
    if (
        outcome.kind is not _records.RepositoryOutcomeKind.ABSENT
        or outcome.record is not None
    ):
        raise _TechnicalRefusal(f"{name} direct absence proof is invalid")


def _broker_fact_economics(
    fact: _fills.BrokerFillFact
    | _fills.BrokerTradeCorrectFact
    | _fills.BrokerTradeBustFact
    | _fills.HumanAttestedFillFact,
) -> tuple[_fills.Quantity, _fills.ReportedPrice | None]:
    if type(fact) is _fills.BrokerFillFact:
        return fact.quantity, fact.price
    if type(fact) is _fills.HumanAttestedFillFact:
        return fact.quantity, fact.price
    if type(fact) is _fills.BrokerTradeCorrectFact:
        return fact.revised_quantity, fact.revised_price
    if type(fact) is _fills.BrokerTradeBustFact:
        return _fills.Quantity(0), fact.reported_price
    raise _TechnicalRefusal("broker execution fact type is not admitted")


def _execution_record_matches_fact(
    record: _records.ExecutionFactRecord,
    fact: _fills.BrokerFillFact
    | _fills.BrokerTradeCorrectFact
    | _fills.BrokerTradeBustFact
    | _fills.HumanAttestedFillFact,
    *,
    root_fill_key_id: int,
    predecessor_fact_id: int | None,
) -> bool:
    quantity, price = _broker_fact_economics(fact)
    human = fact if type(fact) is _fills.HumanAttestedFillFact else None
    return bool(
        record.root_fill_key_id == root_fill_key_id
        and record.source_event_id == fact.key.source_event_id
        and record.order_id == fact.scope.order_id
        and record.side == fact.scope.side.value
        and record.kind == fact.kind.value
        and record.authority == fact.authority.value
        and record.quantity == quantity
        and record.price == price
        and record.request_occurrence_id
        == (None if human is None else human.request_occurrence_id)
        and record.claim_occurrence_id
        == (None if human is None else human.claim_occurrence_id)
        and record.prior_cumulative_quantity
        == (None if human is None else human.prior_cumulative_quantity)
        and record.resulting_cumulative_quantity
        == (None if human is None else human.resulting_cumulative_quantity)
        and record.actor_id == (None if human is None else human.actor)
        and record.reason_text == (None if human is None else human.reason)
        and record.evidence_reference
        == (None if human is None else human.evidence_reference)
        and record.predecessor_fact_id == predecessor_fact_id
    )


def _broker_owner_records(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    fact: _fills.BrokerFillFact
    | _fills.BrokerTradeCorrectFact
    | _fills.BrokerTradeBustFact,
) -> tuple[_records.VenueEffectRecord, _records.VenueIdentityOwnerRecord] | None:
    leg_key = _identity.VenueLegKey(
        fact.scope.broker,
        fact.scope.environment,
        fact.scope.account,
        fact.scope.order_id,
    )
    owner = prepared.context.venue.owner(leg_key)
    if owner is None:
        return None
    effect = prepared.context.venue._current_effect(owner.effect_id)
    if effect is None:
        raise _TechnicalRefusal("broker execution owner has no retained effect")
    owner_record = _cast(
        _records.VenueIdentityOwnerRecord,
        _required_repository_record(
            "broker execution venue owner",
            _repository.load_venue_identity_owner(
                connection,
                prepared.execution_profile_id,
                leg_key.order_id,
            ),
            _records.VenueIdentityOwnerRecord,
        ),
    )
    effect_record = _cast(
        _records.VenueEffectRecord,
        _required_repository_record(
            "broker execution effect",
            _repository.load_venue_effect(connection, owner_record.effect_id),
            _records.VenueEffectRecord,
        ),
    )
    if (
        not _effect_matches_record(effect, effect_record)
        or effect_record.scope_id != prepared.scope_id
        or effect_record.application_generation_id != prepared.application_generation_id
        or effect_record.execution_profile_id != prepared.execution_profile_id
        or owner_record.scope_id != prepared.scope_id
        or owner_record.execution_profile_id != prepared.execution_profile_id
        or owner_record.owner_id != leg_key.order_id
        or owner_record.observation_id != owner.observation_id
        or owner_record.effect_id != effect_record.effect_id
        or owner_record.owner_generation_id != effect_record.acquisition_generation_id
    ):
        raise _TechnicalRefusal("broker execution venue owner proof disagrees")
    return effect_record, owner_record


def _broker_execution_predecessor_records(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    fact: _fills.BrokerFillFact
    | _fills.BrokerTradeCorrectFact
    | _fills.BrokerTradeBustFact,
    proof: _position._M2ExecutionObservationProof,
) -> tuple[
    _records.RootFillRecord | None,
    _records.AcquisitionRootRouteRecord | None,
    _records.ExecutionFactRecord | None,
]:
    _require_repository_absence(
        "broker execution source",
        _repository.load_execution_fact_by_source(
            connection,
            prepared.execution_profile_id,
            fact.key.source_event_id,
        ),
    )
    root_outcome = _repository.load_root_fill_by_external(
        connection,
        prepared.execution_profile_id,
        fact.root_fill_id,
    )
    if proof.root_head is None:
        _require_repository_absence("broker execution root", root_outcome)
        if proof.predecessor_observation is not None:
            raise _TechnicalRefusal("rootless broker proof claims a predecessor")
        return None, None, None

    root = _cast(
        _records.RootFillRecord,
        _required_repository_record(
            "broker execution root",
            root_outcome,
            _records.RootFillRecord,
        ),
    )
    route_outcome = _repository.load_acquisition_root_route(
        connection,
        root.root_fill_key_id,
    )
    if route_outcome.kind is _records.RepositoryOutcomeKind.ABSENT:
        route = None
    else:
        route = _cast(
            _records.AcquisitionRootRouteRecord,
            _required_repository_record(
                "broker execution root route",
                route_outcome,
                _records.AcquisitionRootRouteRecord,
            ),
        )
    head = _cast(
        _records.ExecutionFactHeadRecord,
        _required_repository_record(
            "broker execution fact head",
            _repository.load_execution_fact_head(
                connection,
                root.root_fill_key_id,
            ),
            _records.ExecutionFactHeadRecord,
        ),
    )
    current = _cast(
        _records.ExecutionFactRecord,
        _required_repository_record(
            "broker execution current fact",
            _repository.load_execution_fact(connection, head.fact_id),
            _records.ExecutionFactRecord,
        ),
    )
    root_head = proof.root_head
    if (
        root.scope_id != prepared.scope_id
        or root.application_generation_id != prepared.application_generation_id
        or root.execution_profile_id != prepared.execution_profile_id
        or root.root_fill_id != fact.root_fill_id
        or root.current_fact_id != head.fact_id
        or root.economics_head_ordinal != head.fact_ordinal
        or current.fact_id != head.fact_id
        or current.fact_ordinal != head.fact_ordinal
        or current.root_fill_key_id != root.root_fill_key_id
        or current.source_event_id != root_head.current_source_event_id
        or current.order_id != root_head.scope.order_id
        or current.side != root_head.scope.side.value
        or current.kind != root_head.kind.value
        or current.authority != root_head.authority.value
        or current.quantity != root_head.quantity
        or current.price != root_head.price
        or root.current_kind != current.kind
        or root.current_authority != current.authority
        or root.current_side != current.side
        or root.current_quantity != current.quantity
        or root.current_price != current.price
    ):
        raise _TechnicalRefusal("broker execution predecessor proof disagrees")
    if route is not None and (
        route.root_fill_key_id != root.root_fill_key_id
        or route.scope_id != root.scope_id
        or route.application_generation_id != root.application_generation_id
        or route.execution_profile_id != root.execution_profile_id
        or route.acquisition_generation_id != root.owner_generation_id
    ):
        raise _TechnicalRefusal("broker execution root route proof disagrees")
    predecessor = proof.predecessor_observation
    if type(fact) in {
        _fills.BrokerTradeCorrectFact,
        _fills.BrokerTradeBustFact,
    } and (
        predecessor is None
        or type(predecessor.fact)
        not in {
            _fills.BrokerFillFact,
            _fills.BrokerTradeCorrectFact,
            _fills.BrokerTradeBustFact,
        }
        or not _execution_record_matches_fact(
            current,
            _cast(
                _fills.BrokerFillFact
                | _fills.BrokerTradeCorrectFact
                | _fills.BrokerTradeBustFact,
                predecessor.fact,
            ),
            root_fill_key_id=root.root_fill_key_id,
            predecessor_fact_id=current.predecessor_fact_id,
        )
    ):
        raise _TechnicalRefusal("broker revision predecessor is not exact")
    return root, route, current


def _broker_execution_transition_for_operation(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
) -> tuple[
    _position.ExecutionTransition,
    _acquisition.AcquisitionControllerTransition | None,
    tuple[_venue.VenueRecoveryTransition, ...],
    _SelectedAcquisitionAuthority,
    _records.RootFillRecord | None,
    _records.AcquisitionRootRouteRecord | None,
    _records.ExecutionFactRecord | None,
    _records.VenueEffectRecord | None,
    _records.VenueIdentityOwnerRecord | None,
]:
    operation = prepared.operation
    if type(operation) is not _operations.BrokerExecutionOperation:
        raise _TechnicalRefusal("broker execution route received another operation")
    acquisition, execution, protection = _selected_scope_owner(prepared)
    selected = _selected_acquisition_authority(
        prepared,
        acquisition,
        execution,
        protection,
    )
    fact = operation.fact
    position_scope = execution.position.scope
    venue_scope = prepared.context.venue.scope
    if (
        fact.scope.position_scope != position_scope
        or fact.scope.broker != venue_scope.broker
        or fact.scope.environment != venue_scope.environment
        or fact.scope.account != venue_scope.account
        or selected.scope.symbol != position_scope.symbol_id
    ):
        raise _TechnicalRefusal("broker execution scope is not selected")
    try:
        state = _position._m2_execution_state_from_snapshot(execution)
        proof = _position._M2ExecutionObservationProof.from_snapshot(
            state,
            execution,
            fact,
        )
        direct_classification = _position._m2_apply_broker_execution_fact(
            state,
            proof,
        )
        public_transition = _position.apply_broker_execution_fact(
            execution.position,
            execution.integrity,
            execution.root_heads,
            execution.seen_facts,
            fact,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise _TechnicalRefusal("broker execution owner reduction was refused") from exc
    if (
        public_transition.disposition,
        public_transition.original_classification,
    ) != direct_classification:
        raise _TechnicalRefusal(
            "broker execution shared-kernel classification disagrees"
        )
    if (
        public_transition.disposition
        is _position.TransitionDisposition.RECONCILIATION_REQUIRED
    ):
        return (
            public_transition,
            None,
            (),
            selected,
            None,
            None,
            None,
            None,
            None,
        )
    if public_transition.disposition is not _position.TransitionDisposition.APPLIED:
        raise _TechnicalRefusal(
            "broker execution primary input is not one new owner decision"
        )
    root, route, predecessor = _broker_execution_predecessor_records(
        connection,
        prepared,
        fact,
        proof,
    )
    owner_records = _broker_owner_records(connection, prepared, fact)
    if owner_records is None or (root is not None and route is None):
        if route is not None:
            raise _TechnicalRefusal("broker execution route lost its exact venue owner")
        return (
            public_transition,
            None,
            (),
            selected,
            root,
            route,
            predecessor,
            None,
            None,
        )
    effect_record, owner_record = owner_records
    if route is not None and (
        route.effect_id != effect_record.effect_id
        or route.owner_id != owner_record.owner_id
        or route.observation_id != owner_record.observation_id
        or route.acquisition_generation_id != owner_record.owner_generation_id
    ):
        raise _TechnicalRefusal("broker execution route owner is substituted")
    successor_execution = _position.ExecutionSnapshot(
        public_transition.position,
        public_transition.integrity,
        public_transition.root_heads,
        public_transition.seen_facts,
    )
    try:
        venue_transition = _venue._m2_catch_up_broker_execution_fact(
            prepared.context.venue,
            execution,
            successor_execution,
            fact,
        )
        acquisition_transition = _acquisition.reduce_acquisition_controller(
            acquisition,
            venue_transition,
            protection,
            prepared.context.authority,
        )
        derivatives = _acquisition._m2_acquisition_transition_venue_derivatives(
            acquisition_transition
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise _TechnicalRefusal(
            "broker execution composite reduction was refused"
        ) from exc
    if (
        acquisition_transition.disposition
        is not _acquisition.AcquisitionControllerDisposition.APPLIED
        or acquisition_transition.execution != successor_execution
        or acquisition_transition.venue is not acquisition_transition.authority.venue
        or acquisition_transition.protection is None
    ):
        raise _TechnicalRefusal("broker execution acquisition reduction is incomplete")
    return (
        public_transition,
        acquisition_transition,
        derivatives,
        selected,
        root,
        route,
        predecessor,
        effect_record,
        owner_record,
    )


def _selected_scope_authority(
    prepared: _PreparedOperation,
    effect_scope: _venue.VenueEffectScope,
) -> _SelectedScopeAuthority:
    selection = prepared.selection_proof._selection
    venue_scope = prepared.context.venue.scope
    if (
        effect_scope.generation != prepared.application_generation_id
        or effect_scope.broker != venue_scope.broker
        or effect_scope.environment != venue_scope.environment
        or effect_scope.account != venue_scope.account
    ):
        raise _TechnicalRefusal("effect scope is outside the selected application")
    scopes = tuple(
        record
        for record in selection.scopes
        if record.application_generation_id == prepared.application_generation_id
        and record.execution_profile_id == prepared.execution_profile_id
        and record.symbol == effect_scope.symbol_id
    )
    if len(scopes) != 1:
        raise _TechnicalRefusal("effect scope does not select one durable scope")
    scope = scopes[0]
    controllers = tuple(
        record for record in selection.controllers if record.scope_id == scope.scope_id
    )
    protections = tuple(
        record
        for record in selection.protection_authorities
        if record.scope_id == scope.scope_id
    )
    if len(controllers) != 1 or len(protections) != 1:
        raise _TechnicalRefusal("effect scope current authority is incomplete")
    controller = controllers[0]
    protection = protections[0]
    generation_id = controller.live_acquisition_generation_id
    generations = tuple(
        record
        for record in selection.live_generations
        if record.scope_id == scope.scope_id
        and record.acquisition_generation_id == generation_id
    )
    if (
        generation_id is None
        or len(generations) != 1
        or protection.expected_controller_head_ordinal
        != controller.currentness_head_ordinal
    ):
        raise _TechnicalRefusal("effect scope lacks exact live generation authority")
    return _SelectedScopeAuthority(
        scope,
        controller,
        generations[0],
        protection,
    )


def _effect_target_order_id(
    scope: _venue.VenueEffectScope,
) -> _identity.OrderId | None:
    target = scope.target_leg_key
    if target is None:
        return None
    if (
        target.broker != scope.broker
        or target.environment != scope.environment
        or target.account != scope.account
    ):
        raise _TechnicalRefusal("effect target leg is outside its account")
    return target.order_id


def _effect_matches_record(
    effect: _venue.BrokerEffect,
    record: _records.VenueEffectRecord,
) -> bool:
    scope = effect.scope
    return bool(
        record.effect_external == scope.effect_id
        and record.application_generation_id == scope.generation
        and record.request_occurrence_id == scope.request_occurrence_id
        and record.mandate_id == scope.mandate_id
        and record.effect_kind == scope.kind.value
        and record.client_order_id == scope.client_order_id
        and record.target_order_id == _effect_target_order_id(scope)
        and record.side == scope.side.value
        and record.quantity == scope.quantity
        and record.economic_scope == scope.economic_scope
        and record.lifecycle_state == effect.state.value
        and record.disposition == effect.acceptance_set_state.value
    )


def _new_venue_effect_record(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    effect: _venue.BrokerEffect,
    authority: _SelectedScopeAuthority | None = None,
) -> _records.VenueEffectRecord:
    selected = (
        _selected_scope_authority(prepared, effect.scope)
        if authority is None
        else authority
    )
    if (
        selected.scope.scope_id != prepared.scope_id
        or selected.scope.application_generation_id
        != prepared.application_generation_id
        or selected.scope.execution_profile_id != prepared.execution_profile_id
        or selected.scope.symbol != effect.scope.symbol_id
        or selected.controller.scope_id != selected.scope.scope_id
        or selected.controller.live_acquisition_generation_id
        != selected.generation.acquisition_generation_id
        or selected.protection.scope_id != selected.scope.scope_id
    ):
        raise _TechnicalRefusal("new effect authority is not exact")
    record = _records.VenueEffectRecord(
        _next_venue_effect_id(connection),
        effect.scope.effect_id,
        selected.scope.scope_id,
        selected.scope.application_generation_id,
        selected.scope.execution_profile_id,
        selected.generation.acquisition_generation_id,
        selected.generation.mandate_commitment_sha256,
        selected.controller.currentness_head_ordinal,
        selected.protection.version_ordinal,
        selected.protection.authority_class,
        effect.scope.request_occurrence_id,
        effect.scope.mandate_id,
        effect.scope.kind.value,
        effect.scope.client_order_id,
        _effect_target_order_id(effect.scope),
        effect.scope.side.value,
        effect.scope.quantity,
        effect.scope.economic_scope,
        effect.state.value,
        effect.acceptance_set_state.value,
        None,
        None,
        None,
        None,
        _next_venue_effect_created_ordinal(connection),
    )
    if (
        effect.state is not _venue.BrokerEffectState.REQUESTED
        or effect.acceptance_set_state is not _venue.AcceptanceSetState.OPEN
        or effect.acceptance_proof is not None
        or not _effect_matches_record(effect, record)
    ):
        raise _TechnicalRefusal("new effect is not an exact open request")
    return record


def _selected_effects_by_external(
    prepared: _PreparedOperation,
) -> dict[_identity.EffectId, _records.VenueEffectRecord]:
    result: dict[_identity.EffectId, _records.VenueEffectRecord] = {}
    for record in prepared.selection_proof._selection.effects:
        if record.effect_external in result:
            raise _TechnicalRefusal("selected effects repeat an external identity")
        result[record.effect_external] = record
    return result


def _selected_acceptance_by_effect(
    prepared: _PreparedOperation,
) -> dict[int, _records.AcceptanceSetRecord]:
    result: dict[int, _records.AcceptanceSetRecord] = {}
    for record in prepared.selection_proof._selection.acceptance_sets:
        if record.effect_id in result:
            raise _TechnicalRefusal("selected acceptance sets repeat an effect")
        result[record.effect_id] = record
    return result


def _selected_claims_by_effect(
    prepared: _PreparedOperation,
) -> dict[int, _records.DispatchClaimRecord]:
    result: dict[int, _records.DispatchClaimRecord] = {}
    for record in prepared.selection_proof._selection.claims:
        if record.effect_id in result:
            raise _TechnicalRefusal("selected claims repeat an effect")
        result[record.effect_id] = record
    return result


def _selected_owners_by_leg(
    prepared: _PreparedOperation,
) -> dict[_identity.VenueLegKey, _records.VenueIdentityOwnerRecord]:
    venue_scope = prepared.context.venue.scope
    result: dict[_identity.VenueLegKey, _records.VenueIdentityOwnerRecord] = {}
    for record in prepared.selection_proof._selection.owners:
        leg_key = _identity.VenueLegKey(
            venue_scope.broker,
            venue_scope.environment,
            venue_scope.account,
            record.owner_id,
        )
        if leg_key in result:
            raise _TechnicalRefusal("selected venue owners repeat a leg identity")
        result[leg_key] = record
    return result


def _selected_closures_by_owner(
    prepared: _PreparedOperation,
) -> dict[_identity.OrderId, _records.ClosureChainRecord]:
    result: dict[_identity.OrderId, _records.ClosureChainRecord] = {}
    for record in prepared.selection_proof._selection.closure_heads:
        if record.owner_id in result:
            raise _TechnicalRefusal("selected closures repeat an owner identity")
        result[record.owner_id] = record
    return result


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
    venue_wide = key_kind.value.startswith("VENUE_")
    retained = _repository.load_durable_input_by_semantic_key(
        connection,
        key_kind,
        None if venue_wide else prepared.application_generation_id,
        prepared.execution_profile_id,
        None if venue_wide else prepared.scope_id,
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


def _venue_command_key_bytes(
    prepared: _PreparedOperation,
    item: object,
) -> bytes:
    try:
        semantic_digest = _venue._semantic_input_key(item).hex()
    except (TypeError, ValueError, OverflowError) as exc:
        raise _TechnicalRefusal("venue semantic identity is not canonical") from exc
    return _operations.encode_m2_semantic_key(
        _operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
        (prepared.execution_profile_id,),
        ("venue-semantic-digest", semantic_digest),
    )


def _venue_execution_fact_key_bytes(
    prepared: _PreparedOperation,
    item: object,
) -> bytes | None:
    fact_key = getattr(getattr(item, "fact", None), "key", None)
    if fact_key is None:
        return None
    if type(fact_key) is not _identity.ExecutionFactKey:
        raise _TechnicalRefusal("venue execution fact identity is not canonical")
    return _operations.encode_m2_semantic_key(
        _operations.InputSemanticKeyKind.VENUE_EXECUTION_FACT_V1,
        (prepared.execution_profile_id,),
        (
            "execution-fact-key",
            fact_key.broker.value,
            fact_key.environment.value,
            fact_key.account.value,
            fact_key.source_event_id.value,
        ),
    )


def _venue_coverage_root_key_bytes(
    prepared: _PreparedOperation,
    root_key: _fills.RootFillKey,
) -> bytes:
    if type(root_key) is not _fills.RootFillKey:
        raise _TechnicalRefusal("venue coverage root identity is not canonical")
    return _operations.encode_m2_semantic_key(
        _operations.InputSemanticKeyKind.VENUE_COVERAGE_ROOT_V1,
        (prepared.execution_profile_id,),
        (
            "root-fill-key",
            root_key.broker.value,
            root_key.environment.value,
            root_key.account.value,
            root_key.root_fill_id.value,
        ),
    )


def _venue_coverage_interval_key_bytes(
    prepared: _PreparedOperation,
    leg_key: _identity.VenueLegKey,
    prior: _fills.Quantity,
    resulting: _fills.Quantity,
) -> bytes:
    if (
        type(leg_key) is not _identity.VenueLegKey
        or type(prior) is not _fills.Quantity
        or type(resulting) is not _fills.Quantity
    ):
        raise _TechnicalRefusal("venue coverage interval is not canonical")
    return _operations.encode_m2_semantic_key(
        _operations.InputSemanticKeyKind.VENUE_COVERAGE_INTERVAL_V1,
        (prepared.execution_profile_id,),
        (
            "coverage-interval",
            leg_key.broker.value,
            leg_key.environment.value,
            leg_key.account.value,
            leg_key.order_id.value,
            prior.value,
            resulting.value,
        ),
    )


def _venue_broker_fact_key_bytes(
    prepared: _PreparedOperation,
    fact_key: _identity.ExecutionFactKey,
) -> bytes:
    if type(fact_key) is not _identity.ExecutionFactKey:
        raise _TechnicalRefusal("venue broker fact identity is not canonical")
    return _operations.encode_m2_semantic_key(
        _operations.InputSemanticKeyKind.VENUE_BROKER_FACT_V1,
        (prepared.execution_profile_id,),
        (
            "execution-fact-key",
            fact_key.broker.value,
            fact_key.environment.value,
            fact_key.account.value,
            fact_key.source_event_id.value,
        ),
    )


def _venue_coverage_lookup_plan(
    prepared: _PreparedOperation,
    item: object,
) -> tuple[
    tuple[_operations.InputSemanticKeyKind, bytes] | None,
    tuple[_operations.InputSemanticKeyKind, bytes] | None,
    tuple[_operations.InputSemanticKeyKind, bytes] | None,
]:
    """Derive the fixed root, interval, and broker-fact lookup slots."""

    if type(item) is _recovery.IngestHumanAttestedFill:
        human = _cast(_recovery.IngestHumanAttestedFill, item)
        root_key = human.fact.root_key
        leg_key = human.fact.leg_key
        prior = human.fact.prior_cumulative_quantity
        resulting = human.fact.resulting_cumulative_quantity
        broker_fact_key = None
    elif type(item) is _recovery.RecordBrokerFillEvidence:
        broker_fill = _cast(_recovery.RecordBrokerFillEvidence, item)
        root_key = broker_fill.fact.root_key
        leg_key = broker_fill.leg_key
        prior = broker_fill.prior_cumulative_quantity
        resulting = broker_fill.resulting_cumulative_quantity
        broker_fact_key = broker_fill.fact.key
    elif type(item) is _recovery.RecordBrokerRevisionEvidence:
        revision = _cast(_recovery.RecordBrokerRevisionEvidence, item)
        root_key = revision.fact.root_key
        leg_key = revision.leg_key
        prior = revision.prior_venue_cumulative_quantity
        resulting = revision.resulting_venue_cumulative_quantity
        broker_fact_key = revision.fact.key
    else:
        return (None, None, None)
    return (
        (
            _operations.InputSemanticKeyKind.VENUE_COVERAGE_ROOT_V1,
            _venue_coverage_root_key_bytes(prepared, root_key),
        ),
        (
            _operations.InputSemanticKeyKind.VENUE_COVERAGE_INTERVAL_V1,
            _venue_coverage_interval_key_bytes(
                prepared,
                leg_key,
                prior,
                resulting,
            ),
        ),
        (
            None
            if broker_fact_key is None
            else (
                _operations.InputSemanticKeyKind.VENUE_BROKER_FACT_V1,
                _venue_broker_fact_key_bytes(prepared, broker_fact_key),
            )
        ),
    )


def _venue_direct_observation(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    item: object,
) -> tuple[_venue._M2VenueState, _venue._M2VenueObservationProof]:
    key_bytes = _venue_command_key_bytes(prepared, item)
    retained = _load_terminal_semantic_input(
        connection,
        prepared,
        _operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
        key_bytes,
    )
    fact_key_bytes = _venue_execution_fact_key_bytes(prepared, item)
    retained_fact = (
        None
        if fact_key_bytes is None
        else _load_terminal_semantic_input(
            connection,
            prepared,
            _operations.InputSemanticKeyKind.VENUE_EXECUTION_FACT_V1,
            fact_key_bytes,
        )
    )
    coverage_plan = _venue_coverage_lookup_plan(prepared, item)
    retained_coverage = tuple(
        (
            None
            if planned is None
            else _load_terminal_semantic_input(
                connection,
                prepared,
                planned[0],
                planned[1],
            )
        )
        for planned in coverage_plan
    )
    state = _venue._m2_venue_state_from_book(prepared.context.venue)
    retained_item: object | None = None
    retained_input_bytes: bytes | None = None
    retained_outcome_bytes: bytes | None = None
    if retained is not None:
        operation = retained.operation
        if (
            type(operation) is not _operations.VenueRecoveryOperation
            or operation.coordinates.execution_profile_id
            != prepared.execution_profile_id
            or _venue._semantic_input_key(operation.item)
            != _venue._semantic_input_key(item)
        ):
            raise _TechnicalRefusal("retained venue semantic owner is not exact")
        retained_item = operation.item
        retained_input_bytes = retained.input_record.canonical_payload_bytes
        retained_outcome_bytes = retained.outcome_record.canonical_outcome_bytes
    retained_fact_item: object | None = None
    retained_fact_input_bytes: bytes | None = None
    retained_fact_outcome_bytes: bytes | None = None
    if retained_fact is not None:
        operation = retained_fact.operation
        expected_fact_key = getattr(getattr(item, "fact", None), "key", None)
        retained_fact_key = getattr(
            getattr(getattr(operation, "item", None), "fact", None),
            "key",
            None,
        )
        if (
            type(operation) is not _operations.VenueRecoveryOperation
            or operation.coordinates.execution_profile_id
            != prepared.execution_profile_id
            or type(expected_fact_key) is not _identity.ExecutionFactKey
            or retained_fact_key != expected_fact_key
        ):
            raise _TechnicalRefusal("retained venue fact owner is not exact")
        retained_fact_item = operation.item
        retained_fact_input_bytes = retained_fact.input_record.canonical_payload_bytes
        retained_fact_outcome_bytes = (
            retained_fact.outcome_record.canonical_outcome_bytes
        )
    retained_coverage_items: list[object | None] = []
    retained_coverage_input_bytes: list[bytes | None] = []
    retained_coverage_outcome_bytes: list[bytes | None] = []
    for retained_match in retained_coverage:
        if retained_match is None:
            retained_coverage_items.append(None)
            retained_coverage_input_bytes.append(None)
            retained_coverage_outcome_bytes.append(None)
            continue
        retained_operation = retained_match.operation
        if (
            type(retained_operation) is not _operations.VenueRecoveryOperation
            or retained_operation.coordinates.execution_profile_id
            != prepared.execution_profile_id
        ):
            raise _TechnicalRefusal("retained venue coverage owner is not exact")
        retained_coverage_items.append(retained_operation.item)
        retained_coverage_input_bytes.append(
            retained_match.input_record.canonical_payload_bytes
        )
        retained_coverage_outcome_bytes.append(
            retained_match.outcome_record.canonical_outcome_bytes
        )
    proof = _venue._m2_venue_observation_from_direct_evidence(
        state,
        item,
        retained_item=retained_item,
        retained_input_bytes=retained_input_bytes,
        retained_outcome_bytes=retained_outcome_bytes,
        retained_fact_item=retained_fact_item,
        retained_fact_input_bytes=retained_fact_input_bytes,
        retained_fact_outcome_bytes=retained_fact_outcome_bytes,
        retained_coverage_items=_cast(
            tuple[object | None, object | None, object | None],
            tuple(retained_coverage_items),
        ),
        retained_coverage_input_bytes=_cast(
            tuple[bytes | None, bytes | None, bytes | None],
            tuple(retained_coverage_input_bytes),
        ),
        retained_coverage_outcome_bytes=_cast(
            tuple[bytes | None, bytes | None, bytes | None],
            tuple(retained_coverage_outcome_bytes),
        ),
    )
    return state, proof


def _store_venue_semantic_key(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    key_kind: _operations.InputSemanticKeyKind,
    key_bytes: bytes,
    capability: _repository._RuntimeWriteCapability,
) -> None:
    record = _records.DurableInputSemanticKeyRecord(
        key_kind,
        None,
        prepared.execution_profile_id,
        None,
        key_bytes,
        _hashlib.sha256(key_bytes).hexdigest(),
        claimed.application_generation_id,
        claimed.input_domain,
        claimed.input_identity_sha256,
        _next_semantic_key_created_ordinal(connection),
    )
    _require_applied_repository_outcome(
        f"venue {key_kind.value} semantic key",
        _repository.store_durable_input_semantic_key(
            connection,
            record,
            capability=capability,
        ),
    )


def _store_venue_command_semantic_key(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    item: object,
    capability: _repository._RuntimeWriteCapability,
) -> None:
    _store_venue_semantic_key(
        connection,
        prepared,
        claimed,
        _operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
        _venue_command_key_bytes(prepared, item),
        capability,
    )


def _store_venue_transition_semantic_keys(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    transition: _venue.VenueRecoveryTransition,
    capability: _repository._RuntimeWriteCapability,
) -> None:
    operation = prepared.operation
    if type(operation) is not _operations.VenueRecoveryOperation:
        raise _TechnicalRefusal("venue semantic writes received another operation")
    item = operation.item
    item_input_id = getattr(item, "input_id", None)
    if type(item_input_id) is not _identity.VenueInputId:
        raise _TechnicalRefusal("venue semantic writes lack an exact input identity")
    if prepared.context.venue._input_record(item_input_id) is not None:
        raise _TechnicalRefusal("unseen durable input already exists in venue history")
    resulting_input = transition.book._input_record(item_input_id)
    if resulting_input is None:
        return
    if resulting_input.item != item:
        raise _TechnicalRefusal("venue transition retained another input payload")

    planned: list[tuple[_operations.InputSemanticKeyKind, bytes]] = []

    def add(kind: _operations.InputSemanticKeyKind, key_bytes: bytes) -> None:
        candidate = (kind, key_bytes)
        if candidate not in planned:
            planned.append(candidate)

    if resulting_input.semantic_alias_of is None:
        add(
            _operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
            _venue_command_key_bytes(prepared, item),
        )

    fact = getattr(item, "fact", None)
    fact_key = getattr(fact, "key", None)
    if type(fact_key) is _identity.ExecutionFactKey:
        predecessor_fact_input = prepared.context.venue._fact_input_record(fact_key)
        resulting_fact_input = transition.book._fact_input_record(fact_key)
        if (
            predecessor_fact_input is None
            and resulting_fact_input is not None
            and resulting_fact_input.input_id == item_input_id
        ):
            fact_key_bytes = _venue_execution_fact_key_bytes(prepared, item)
            if fact_key_bytes is None:
                raise _TechnicalRefusal("venue fact semantic key was not derived")
            add(
                _operations.InputSemanticKeyKind.VENUE_EXECUTION_FACT_V1,
                fact_key_bytes,
            )

    root_key = getattr(fact, "root_key", None)
    if type(root_key) is _fills.RootFillKey:
        predecessor_human = prepared.context.venue._human_coverage_for_root(root_key)
        resulting_human = transition.book._human_coverage_for_root(root_key)
        predecessor_broker = prepared.context.venue._broker_coverage_for_root(root_key)
        resulting_broker = transition.book._broker_coverage_for_root(root_key)
        if (
            type(resulting_human) is _recovery.HumanCoverage
            and resulting_human.source_input_id == item_input_id
            and predecessor_human is None
        ):
            add(
                _operations.InputSemanticKeyKind.VENUE_COVERAGE_ROOT_V1,
                _venue_coverage_root_key_bytes(prepared, root_key),
            )
            add(
                _operations.InputSemanticKeyKind.VENUE_COVERAGE_INTERVAL_V1,
                _venue_coverage_interval_key_bytes(
                    prepared,
                    resulting_human.leg_key,
                    resulting_human.fact.prior_cumulative_quantity,
                    resulting_human.fact.resulting_cumulative_quantity,
                ),
            )
        if (
            type(resulting_human) is _recovery.HumanCoverage
            and resulting_human.broker_source_input_id == item_input_id
            and resulting_human.broker_fact is not None
            and (
                predecessor_human is None
                or predecessor_human.broker_source_input_id != item_input_id
            )
        ):
            add(
                _operations.InputSemanticKeyKind.VENUE_BROKER_FACT_V1,
                _venue_broker_fact_key_bytes(
                    prepared,
                    resulting_human.broker_fact.key,
                ),
            )
        if (
            type(resulting_broker) is _recovery._BrokerCoverage
            and resulting_broker.root_source_input_id == item_input_id
            and predecessor_broker is None
        ):
            add(
                _operations.InputSemanticKeyKind.VENUE_COVERAGE_ROOT_V1,
                _venue_coverage_root_key_bytes(prepared, root_key),
            )
            add(
                _operations.InputSemanticKeyKind.VENUE_COVERAGE_INTERVAL_V1,
                _venue_coverage_interval_key_bytes(
                    prepared,
                    resulting_broker.leg_key,
                    resulting_broker.prior_cumulative_quantity,
                    resulting_broker.resulting_cumulative_quantity,
                ),
            )
        if (
            type(resulting_broker) is _recovery._BrokerCoverage
            and resulting_broker.head_source_input_id == item_input_id
            and (
                predecessor_broker is None
                or predecessor_broker.head_source_input_id != item_input_id
            )
        ):
            if predecessor_broker is not None and (
                predecessor_broker.prior_cumulative_quantity
                != resulting_broker.prior_cumulative_quantity
                or predecessor_broker.resulting_cumulative_quantity
                != resulting_broker.resulting_cumulative_quantity
            ):
                add(
                    _operations.InputSemanticKeyKind.VENUE_COVERAGE_INTERVAL_V1,
                    _venue_coverage_interval_key_bytes(
                        prepared,
                        resulting_broker.leg_key,
                        resulting_broker.prior_cumulative_quantity,
                        resulting_broker.resulting_cumulative_quantity,
                    ),
                )
            add(
                _operations.InputSemanticKeyKind.VENUE_BROKER_FACT_V1,
                _venue_broker_fact_key_bytes(
                    prepared,
                    resulting_broker.head_fact.key,
                ),
            )

    for kind, key_bytes in planned:
        _store_venue_semantic_key(
            connection,
            prepared,
            claimed,
            kind,
            key_bytes,
            capability,
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


def _authority_grant_key_bytes(
    prepared: _PreparedOperation,
    grant_id: _identity.EmergencyGrantId,
) -> bytes:
    return _operations.encode_m2_semantic_key(
        _operations.InputSemanticKeyKind.AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1,
        (
            prepared.application_generation_id.value,
            prepared.execution_profile_id,
            prepared.scope_id,
        ),
        ("emergency-grant-id", grant_id.value),
    )


def _authority_grant_observation(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    grant_id: _identity.EmergencyGrantId,
) -> _authority._M2AuthorityGrantObservationProof:
    key_bytes = _authority_grant_key_bytes(prepared, grant_id)
    retained = _load_terminal_semantic_input(
        connection,
        prepared,
        _operations.InputSemanticKeyKind.AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1,
        key_bytes,
    )
    if retained is None:
        return _authority._m2_authority_grant_observation_from_direct_evidence(
            prepared.context.authority,
            grant_id,
            retained_claim=None,
            retained_input_bytes=None,
            retained_outcome_bytes=None,
        )
    if (
        type(retained.operation) is not _operations.AuthorityOperation
        or type(retained.operation.command) is not _authority.ClaimEffect
        or retained.outcome_record.owner_domain != "AUTHORITY"
        or retained.outcome_record.owner_disposition != "APPLIED"
    ):
        raise _TechnicalRefusal("retained grant input is not an applied claim")
    retained_claim = retained.operation.command
    return _authority._m2_authority_grant_observation_from_direct_evidence(
        prepared.context.authority,
        grant_id,
        retained_claim=retained_claim,
        retained_input_bytes=retained.input_record.canonical_payload_bytes,
        retained_outcome_bytes=retained.outcome_record.canonical_outcome_bytes,
    )


def _store_authority_grant_semantic_key(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    grant_id: _identity.EmergencyGrantId,
    capability: _repository._RuntimeWriteCapability,
) -> None:
    key_bytes = _authority_grant_key_bytes(prepared, grant_id)
    record = _records.DurableInputSemanticKeyRecord(
        _operations.InputSemanticKeyKind.AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1,
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
        "authority emergency-grant semantic key",
        _repository.store_durable_input_semantic_key(
            connection,
            record,
            capability=capability,
        ),
    )


def _updated_venue_effect_record(
    retained: _records.VenueEffectRecord,
    effect: _venue.BrokerEffect,
    *,
    closure_proof_kind: str | None = None,
    closure_proof_digest: str | None = None,
    closure_proof_evidence_id: int | None = None,
    closure_proof_claim_id: int | None = None,
) -> _records.VenueEffectRecord:
    if (
        closure_proof_kind is None
        and closure_proof_digest is None
        and closure_proof_evidence_id is None
        and closure_proof_claim_id is None
        and retained.closure_proof_kind is not None
    ):
        closure_proof_kind = retained.closure_proof_kind
        closure_proof_digest = retained.closure_proof_digest
        closure_proof_evidence_id = retained.closure_proof_evidence_id
        closure_proof_claim_id = retained.closure_proof_claim_id
    updated = _replace(
        retained,
        lifecycle_state=effect.state.value,
        disposition=effect.acceptance_set_state.value,
        closure_proof_kind=closure_proof_kind,
        closure_proof_digest=closure_proof_digest,
        closure_proof_evidence_id=closure_proof_evidence_id,
        closure_proof_claim_id=closure_proof_claim_id,
    )
    if not _effect_matches_record(effect, updated):
        raise _TechnicalRefusal("resulting effect disagrees with durable authority")
    return updated


def _store_new_effect_with_acceptance(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    effect: _venue.BrokerEffect,
    capability: _repository._RuntimeWriteCapability,
    new_effect_authority: _SelectedScopeAuthority | None,
) -> tuple[_records.VenueEffectRecord, _records.AcceptanceSetRecord]:
    effect_record = _new_venue_effect_record(
        connection,
        prepared,
        effect,
        new_effect_authority,
    )
    _require_applied_repository_outcome(
        "venue effect",
        _repository.store_venue_effect(
            connection,
            effect_record,
            capability=capability,
        ),
    )
    acceptance = _records.AcceptanceSetRecord(
        _next_acceptance_set_id(connection),
        effect_record.effect_id,
    )
    _require_applied_repository_outcome(
        "acceptance set",
        _repository.store_acceptance_set(
            connection,
            acceptance,
            capability=capability,
        ),
    )
    return effect_record, acceptance


def _persist_authority_venue_transitions(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    transitions: tuple[_venue.VenueRecoveryTransition, ...],
    capability: _repository._RuntimeWriteCapability,
    *,
    new_effect_authority: _SelectedScopeAuthority | None = None,
    predecessor_book: _venue.VenueRecoveryBook | None = None,
) -> tuple[
    tuple[_records.VenueEffectRecord, ...],
    tuple[_PersistedEffectClaim, ...],
]:
    if not transitions:
        return (), ()
    effects = _selected_effects_by_external(prepared)
    acceptance = _selected_acceptance_by_effect(prepared)
    claims = _selected_claims_by_effect(prepared)
    persisted_effects: list[_records.VenueEffectRecord] = []
    persisted_claims: list[_PersistedEffectClaim] = []
    expected_predecessor_commitment = _venue._protection_book_commitment(
        prepared.context.venue if predecessor_book is None else predecessor_book
    )
    for transition in transitions:
        try:
            source = _venue._m2_venue_transition_source_item(transition)
            closure_source = _venue._m2_venue_transition_acceptance_closure(transition)
        except (TypeError, ValueError, OverflowError) as exc:
            raise _TechnicalRefusal(
                "venue transition source proof was refused"
            ) from exc
        proof = transition._protection_proof
        if (
            proof.predecessor_book_commitment != expected_predecessor_commitment
            or transition.disposition is not _venue.VenueRecoveryDisposition.APPLIED
        ):
            raise _TechnicalRefusal("venue transition chain is not contiguous")
        expected_predecessor_commitment = proof.book_commitment
        if source is None or type(source) in {
            _venue.CatchUpExecutionRegistry,
            _venue._BrokerExecutionRegistryCatchUp,
        }:
            continue
        if closure_source is None and type(source) not in (
            _venue.RequestedEffect,
            _venue.RecordDispatchClaim,
            _venue.CancelBeforeDispatch,
        ):
            raise _TechnicalRefusal("authority venue transition source is not admitted")
        if closure_source is not None:
            effect_id = closure_source.effect_id
        else:
            effect_id = _cast(
                _venue.RequestedEffect
                | _venue.RecordDispatchClaim
                | _venue.CancelBeforeDispatch,
                source,
            ).effect_id
        effect = transition.book._current_effect(effect_id)
        if type(effect) is not _venue.BrokerEffect:
            raise _TechnicalRefusal("venue transition omitted its resulting effect")
        if closure_source is None and type(source) is _venue.RequestedEffect:
            if (
                source.effect_id != effect.effect_id
                or source.request_occurrence_id != effect.scope.request_occurrence_id
                or source.mandate_id != effect.scope.mandate_id
                or source.kind is not effect.scope.kind
                or source.client_order_id != effect.scope.client_order_id
                or source.symbol_id != effect.scope.symbol_id
                or source.side is not effect.scope.side
                or source.quantity != effect.scope.quantity
                or source.economic_scope != effect.scope.economic_scope
                or source.target_leg_key != effect.scope.target_leg_key
                or source.effect_id in effects
            ):
                raise _TechnicalRefusal("requested effect result is not exact")
            effect_record, acceptance_record = _store_new_effect_with_acceptance(
                connection,
                prepared,
                effect,
                capability,
                new_effect_authority,
            )
            effects[source.effect_id] = effect_record
            acceptance[effect_record.effect_id] = acceptance_record
            persisted_effects.append(effect_record)
            continue
        retained = effects.get(effect_id)
        if retained is None:
            raise _TechnicalRefusal("venue transition effect is not selected")
        if type(source) is _venue.RecordDispatchClaim:
            if effect.claim_occurrence_id != source.claim_occurrence_id:
                raise _TechnicalRefusal("dispatch transition claim is not exact")
            if retained.effect_id in claims:
                raise _TechnicalRefusal("dispatch transition repeats a retained claim")
            claim = _records.DispatchClaimRecord(
                _next_dispatch_claim_id(connection),
                retained.effect_id,
                retained.execution_profile_id,
                source.claim_occurrence_id,
                _next_dispatch_claim_ordinal(connection),
            )
            _require_applied_repository_outcome(
                "dispatch claim",
                _repository.store_dispatch_claim(
                    connection,
                    claim,
                    capability=capability,
                ),
            )
            updated = _updated_venue_effect_record(retained, effect)
            # Dispatch-claim insertion is the accepted schema's sole owner of
            # REQUESTED -> DISPATCH_CLAIMED. A second application-side CAS
            # would observe the trigger's result and turn every claim into a
            # false conflict.
            claims[retained.effect_id] = claim
            effects[effect_id] = updated
            persisted_claims.append(_PersistedEffectClaim(updated, claim))
            continue
        if type(source) is _venue.CancelBeforeDispatch:
            updated = _updated_venue_effect_record(retained, effect)
            if (
                updated.lifecycle_state
                != _venue.BrokerEffectState.CANCELED_BEFORE_DISPATCH.value
                or updated.disposition != _venue.AcceptanceSetState.OPEN.value
            ):
                raise _TechnicalRefusal("cancel transition did not remain open")
            _require_applied_repository_outcome(
                "canceled venue effect",
                _repository.advance_venue_effect(
                    connection,
                    retained.lifecycle_state,
                    retained.disposition,
                    updated,
                    capability=capability,
                ),
            )
            effects[effect_id] = updated
            continue
        if closure_source is not None:
            accepted = acceptance.get(retained.effect_id)
            if accepted is None:
                raise _TechnicalRefusal("closure transition lacks its acceptance set")
            proof_claim_id: int | None = None
            if closure_source.claim_occurrence_id is not None:
                retained_claim = claims.get(retained.effect_id)
                if (
                    retained_claim is None
                    or retained_claim.claim_occurrence_id
                    != closure_source.claim_occurrence_id
                ):
                    raise _TechnicalRefusal("closure transition lacks its exact claim")
                proof_claim_id = retained_claim.claim_id
            evidence = _records.AcceptanceEvidenceRecord(
                _next_acceptance_evidence_id(connection),
                accepted.acceptance_set_id,
                retained.effect_id,
                "CLOSURE_PROOF",
                closure_source.proof_kind,
                closure_source.evidence_digest.hex(),
                _next_acceptance_evidence_ordinal(connection),
                None,
                None,
            )
            _require_applied_repository_outcome(
                "acceptance closure evidence",
                _repository.store_acceptance_evidence(
                    connection,
                    evidence,
                    capability=capability,
                ),
            )
            updated = _updated_venue_effect_record(
                retained,
                effect,
                closure_proof_kind=closure_source.proof_kind,
                closure_proof_digest=closure_source.evidence_digest.hex(),
                closure_proof_evidence_id=evidence.evidence_id,
                closure_proof_claim_id=proof_claim_id,
            )
            _require_applied_repository_outcome(
                "closed venue effect",
                _repository.advance_venue_effect(
                    connection,
                    retained.lifecycle_state,
                    retained.disposition,
                    updated,
                    capability=capability,
                ),
            )
            effects[effect_id] = updated
            continue
        raise _TechnicalRefusal("authority venue transition source is not admitted")
    return tuple(persisted_effects), tuple(persisted_claims)


def _broker_outbox_record(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    persisted: _PersistedEffectClaim,
) -> _records.BrokerOutboxRecord:
    effect = persisted.effect
    claim = persisted.claim
    if (
        claimed.input_domain
        not in {
            _operations.OperationDomain.AUTHORITY,
            _operations.OperationDomain.CLAIM_ACQUISITION_EFFECT,
        }
        or effect.application_generation_id != prepared.application_generation_id
        or effect.execution_profile_id != prepared.execution_profile_id
        or effect.scope_id != prepared.scope_id
        or claim.effect_id != effect.effect_id
        or claim.execution_profile_id != effect.execution_profile_id
        or effect.lifecycle_state != _venue.BrokerEffectState.DISPATCH_CLAIMED.value
        or effect.disposition != _venue.AcceptanceSetState.OPEN.value
    ):
        raise _TechnicalRefusal("broker outbox claim coordinates are not exact")
    sequence = _next_broker_outbox_sequence(connection)
    document = [
        1,
        "m2.broker-outbox/v1",
        sequence,
        _operations._encode_m2_m1_atom(effect.application_generation_id),
        effect.execution_profile_id,
        effect.scope_id,
        _operations._encode_m2_m1_atom(effect.acquisition_generation_id),
        _operations._encode_m2_enum(claimed.input_domain),
        claimed.input_identity_sha256,
        effect.effect_id,
        _operations._encode_m2_m1_atom(effect.effect_external),
        _operations._encode_m2_m1_atom(effect.request_occurrence_id),
        _operations._encode_m2_m1_atom(effect.mandate_id),
        effect.generation_mandate_commitment_sha256,
        effect.expected_controller_head_ordinal,
        effect.expected_protection_version_ordinal,
        effect.authority_class,
        _operations._encode_m2_enum(_venue.EffectKind(effect.effect_kind)),
        None
        if effect.client_order_id is None
        else _operations._encode_m2_m1_atom(effect.client_order_id),
        None
        if effect.target_order_id is None
        else _operations._encode_m2_m1_atom(effect.target_order_id),
        _operations._encode_m2_enum(_fills.ExecutionSide(effect.side)),
        _operations._encode_m2_m1_atom(effect.quantity),
        effect.economic_scope.hex(),
        claim.claim_id,
        _operations._encode_m2_m1_atom(claim.claim_occurrence_id),
        claim.claim_ordinal,
    ]
    payload = _operations._encode_m2_document_kind(0x05, document)
    return _records.BrokerOutboxRecord(
        sequence,
        effect.application_generation_id,
        effect.execution_profile_id,
        effect.scope_id,
        effect.acquisition_generation_id,
        claimed.input_domain,
        claimed.input_identity_sha256,
        effect.effect_id,
        claim.claim_id,
        payload,
        len(payload),
        _hashlib.sha256(payload).hexdigest(),
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
    pending_outbox: _records.BrokerOutboxRecord | None,
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
    pending_effect: _PostCommitEffectCandidate | None = None
    if pending_outbox is not None:
        if type(pending_outbox) is not _records.BrokerOutboxRecord:
            raise _TechnicalRefusal("pending broker outbox must be exact")
        _require_applied_repository_outcome(
            "broker outbox",
            _repository.store_broker_outbox(
                connection,
                pending_outbox,
                capability=capability,
            ),
        )
        pending_effect = _PostCommitEffectCandidate(
            pending_outbox.outbox_sequence,
            pending_outbox.effect_id,
            pending_outbox.claim_id,
            pending_outbox.payload_sha256,
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
        _authority.CreateBrokerEffect,
        _authority.ClaimEffect,
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
    if type(operation.command) is _authority.CreateBrokerEffect:
        required_grant_id = operation.command.emergency_grant_id
    elif type(operation.command) is _authority.ClaimEffect:
        try:
            required_grant_id = _authority._m2_authority_effect_emergency_grant_id(
                prepared.context.authority,
                operation.command.effect_id,
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise _TechnicalRefusal(
                "claim effect authorization was not authenticated"
            ) from exc
    else:
        required_grant_id = None
    grant_observation = (
        _authority_grant_observation(connection, prepared, required_grant_id)
        if required_grant_id is not None
        else None
    )
    transition = _authority._m2_apply_execution_authority_input(
        prepared.context.authority,
        execution,
        operation.command,
        manual_observation=manual_observation,
        query_observation=query_observation,
        grant_observation=grant_observation,
    )
    if (
        transition.acquisition_receipt is not None
        or transition.acquisition_claim_receipt is not None
    ):
        raise _TechnicalRefusal("authority transition emitted an unrelated derivative")
    persisted_effects, persisted_claims = _persist_authority_venue_transitions(
        connection,
        prepared,
        transition.venue_transitions,
        capability,
    )
    if tuple(record.effect_external for record in persisted_effects) != (
        transition.created_effect_ids
    ):
        raise _TechnicalRefusal(
            "authority transition created-effect proof is incomplete"
        )
    if transition.venue_transitions:
        if transition.venue_transitions[-1].book is not transition.state.venue:
            raise _TechnicalRefusal("authority transition venue chain is incomplete")
    elif transition.state.venue is not prepared.context.venue:
        raise _TechnicalRefusal("authority changed venue without a transition proof")
    pending_outbox: _records.BrokerOutboxRecord | None = None
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
        if persisted_claims:
            raise _TechnicalRefusal("query transition emitted a dispatch claim")
    elif type(operation.command) is _authority.ClaimEffect:
        if transition.disposition is _authority.AuthorityDisposition.APPLIED:
            fresh_claim = transition.fresh_claim
            if (
                type(fresh_claim) is not _authority._FreshEffectClaim
                or fresh_claim.effect_id != operation.command.effect_id
                or fresh_claim.claim_occurrence_id
                != operation.command.claim_occurrence_id
                or fresh_claim.emergency_grant_id != required_grant_id
                or len(persisted_claims) != 1
                or persisted_claims[0].effect.effect_external != fresh_claim.effect_id
                or persisted_claims[0].claim.claim_occurrence_id
                != fresh_claim.claim_occurrence_id
            ):
                raise _TechnicalRefusal(
                    "effect transition omitted its exact fresh claim"
                )
            if required_grant_id is not None:
                _store_authority_grant_semantic_key(
                    connection,
                    prepared,
                    claimed,
                    required_grant_id,
                    capability,
                )
            pending_outbox = _broker_outbox_record(
                connection,
                prepared,
                claimed,
                persisted_claims[0],
            )
        elif transition.fresh_claim is not None or persisted_claims:
            raise _TechnicalRefusal("non-applied effect emitted a fresh claim")
    else:
        if transition.fresh_claim is not None:
            raise _TechnicalRefusal("authority transition emitted a fresh claim")
        if persisted_claims:
            raise _TechnicalRefusal("authority transition emitted an unrelated claim")
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
        pending_outbox=pending_outbox,
        capability=capability,
    )


def _selected_acquisition_owner(
    prepared: _PreparedOperation,
) -> tuple[
    _acquisition.AcquisitionControllerState,
    _position.ExecutionSnapshot,
    _protection.PositionProtectionState | None,
]:
    acquisition, execution, protection = _selected_scope_owner(prepared)
    if (
        prepared.acquisition_generation_id is None
        or acquisition._controller.live_generation_id
        != prepared.acquisition_generation_id
        or acquisition._mandate.session_id != prepared.session_id
    ):
        raise _TechnicalRefusal("acquisition operation owner is not exact")
    return acquisition, execution, protection


def _selected_scope_owner(
    prepared: _PreparedOperation,
) -> tuple[
    _acquisition.AcquisitionControllerState,
    _position.ExecutionSnapshot,
    _protection.PositionProtectionState | None,
]:
    """Return the exact selected serving owner without inventing operation coordinates."""

    for scope_id, acquisition, execution, protection in prepared.context.scope_owners:
        if scope_id != prepared.scope_id:
            continue
        if (
            type(acquisition) is not _acquisition.AcquisitionControllerState
            or acquisition.position_scope != execution.position.scope
        ):
            raise _TechnicalRefusal("operation scope owner is not exact")
        return acquisition, execution, protection
    raise _TechnicalRefusal("operation scope has no serving owner")


def _venue_transition_for_operation(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
) -> tuple[
    _venue.VenueRecoveryTransition,
    _acquisition.AcquisitionControllerState,
    _position.ExecutionSnapshot,
    _protection.PositionProtectionState | None,
    _venue._M2VenueObservationProof,
]:
    operation = prepared.operation
    if type(operation) is not _operations.VenueRecoveryOperation:
        raise _TechnicalRefusal("venue route received another operation")
    acquisition, execution, protection = _selected_scope_owner(prepared)
    try:
        state, proof = _venue_direct_observation(
            connection,
            prepared,
            operation.item,
        )
        transition = _venue._m2_apply_venue_input_from_direct_observation(
            state,
            execution,
            proof,
        )
        source = _venue._m2_venue_transition_source_item(transition)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _TechnicalRefusal("venue owner reduction was refused") from exc
    if (
        source != operation.item
        or transition.execution.position.scope != execution.position.scope
        or transition.book.scope != prepared.context.venue.scope
        or transition.disposition
        not in {
            _venue.VenueRecoveryDisposition.APPLIED,
            _venue.VenueRecoveryDisposition.EXACT_REPLAY,
            _venue.VenueRecoveryDisposition.CONFLICT,
            _venue.VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
            _venue.VenueRecoveryDisposition.REFUSED,
        }
    ):
        raise _TechnicalRefusal("venue owner transition is not exact")
    return transition, acquisition, execution, protection, proof


def _venue_composite_transition_for_operation(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
) -> tuple[
    _venue.VenueRecoveryTransition,
    _acquisition.AcquisitionControllerTransition | None,
    tuple[_venue.VenueRecoveryTransition, ...],
    _SelectedAcquisitionAuthority,
    _venue.AcquisitionFactRelation | None,
]:
    transition, acquisition, execution, protection, observation = (
        _venue_transition_for_operation(connection, prepared)
    )
    selected = _selected_acquisition_authority(
        prepared,
        acquisition,
        execution,
        protection,
    )
    try:
        relation = transition.book.project_acquisition_fact(transition).fact_relation()
        owner_changed = bool(
            transition._protection_proof.book_commitment
            != transition._protection_proof.predecessor_book_commitment
            or transition.execution.commitment != execution.commitment
        )
        if relation is not None:
            acquisition_transition = _acquisition.reduce_acquisition_controller(
                acquisition,
                transition,
                protection,
                prepared.context.authority,
            )
        elif owner_changed:
            refresh = _authority._m2_refresh_acquisition_context_from_venue_transition(
                prepared.context.authority,
                execution,
                acquisition.position_scope,
                transition,
                observation,
            )
            acquisition_transition, _ = _acquisition._m2_rebase_acquisition_venue(
                acquisition,
                refresh,
                protection,
            )
        else:
            acquisition_transition = None
        derivatives = (
            ()
            if acquisition_transition is None
            else _acquisition._m2_acquisition_transition_venue_derivatives(
                acquisition_transition
            )
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise _TechnicalRefusal("venue composite reduction was refused") from exc
    if acquisition_transition is None:
        if relation is not None or owner_changed or derivatives:
            raise _TechnicalRefusal(
                "venue owner change omitted acquisition currentness"
            )
    elif (
        acquisition_transition.disposition
        is not _acquisition.AcquisitionControllerDisposition.APPLIED
        or acquisition_transition.execution != transition.execution
        or acquisition_transition.venue is not transition.book
        or acquisition_transition.authority.venue is not transition.book
    ):
        raise _TechnicalRefusal("venue acquisition reduction is incomplete")
    return transition, acquisition_transition, derivatives, selected, relation


def _venue_item_leg_key(item: object) -> _identity.VenueLegKey | None:
    leg_key = getattr(item, "leg_key", None)
    if type(leg_key) is _identity.VenueLegKey:
        return leg_key
    fact_leg_key = getattr(getattr(item, "fact", None), "leg_key", None)
    return fact_leg_key if type(fact_leg_key) is _identity.VenueLegKey else None


def _venue_item_effect_id(
    book: _venue.VenueRecoveryBook,
    item: object,
) -> _identity.EffectId:
    effect_id = getattr(item, "effect_id", None)
    if type(effect_id) is _identity.EffectId:
        return effect_id
    leg_key = _venue_item_leg_key(item)
    owner = None if leg_key is None else book.owner(leg_key)
    if owner is None:
        raise _TechnicalRefusal("venue operation has no exact effect owner")
    return owner.effect_id


def _persist_venue_owner_rows(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    transition: _venue.VenueRecoveryTransition,
    capability: _repository._RuntimeWriteCapability,
) -> tuple[
    _records.VenueEffectRecord,
    _records.VenueIdentityOwnerRecord | None,
    bool,
]:
    operation = prepared.operation
    if type(operation) is not _operations.VenueRecoveryOperation:
        raise _TechnicalRefusal("venue owner persistence received another operation")
    item = operation.item
    effect_id = _venue_item_effect_id(prepared.context.venue, item)
    predecessor_effect = prepared.context.venue._current_effect(effect_id)
    successor_effect = transition.book._current_effect(effect_id)
    retained = _selected_effects_by_external(prepared).get(effect_id)
    if retained is None:
        retained = _cast(
            _records.VenueEffectRecord,
            _required_repository_record(
                "targeted venue effect",
                _repository._load_venue_effect_by_external(
                    connection,
                    prepared.execution_profile_id,
                    effect_id,
                ),
                _records.VenueEffectRecord,
            ),
        )
    if (
        type(predecessor_effect) is not _venue.BrokerEffect
        or type(successor_effect) is not _venue.BrokerEffect
        or retained is None
        or not _effect_matches_record(predecessor_effect, retained)
    ):
        raise _TechnicalRefusal("venue effect persistence lacks exact authority")

    leg_key = _venue_item_leg_key(item)
    predecessor_owner = (
        None if leg_key is None else prepared.context.venue.owner(leg_key)
    )
    successor_owner = None if leg_key is None else transition.book.owner(leg_key)
    owner_is_new = bool(predecessor_owner is None and successor_owner is not None)
    late_owner = bool(
        owner_is_new
        and predecessor_effect.acceptance_set_state
        in {
            _venue.AcceptanceSetState.CLOSED,
            _venue.AcceptanceSetState.INVALIDATED,
        }
    )

    if late_owner:
        partial = _replace(
            retained,
            lifecycle_state=successor_effect.state.value,
        )
        if partial != retained:
            _require_applied_repository_outcome(
                "late-owner venue effect lifecycle",
                _repository.advance_venue_effect(
                    connection,
                    retained.lifecycle_state,
                    retained.disposition,
                    partial,
                    capability=capability,
                ),
            )
            retained = partial
    else:
        updated = _updated_venue_effect_record(retained, successor_effect)
        if updated != retained:
            _require_applied_repository_outcome(
                "venue effect",
                _repository.advance_venue_effect(
                    connection,
                    retained.lifecycle_state,
                    retained.disposition,
                    updated,
                    capability=capability,
                ),
            )
            retained = updated

    new_owner_record: _records.VenueIdentityOwnerRecord | None = None
    if owner_is_new:
        assert successor_owner is not None
        if (
            leg_key is None
            or successor_owner.leg_key != leg_key
            or successor_owner.effect_id != effect_id
            or successor_owner.effect_scope != successor_effect.scope
        ):
            raise _TechnicalRefusal("venue owner result is not exact")
        new_owner_record = _records.VenueIdentityOwnerRecord(
            prepared.scope_id,
            prepared.execution_profile_id,
            leg_key.order_id,
            successor_owner.observation_id,
            retained.effect_id,
            None,
            retained.acquisition_generation_id,
            late_owner,
        )
        _require_applied_repository_outcome(
            "venue identity owner",
            _repository.store_venue_identity_owner(
                connection,
                new_owner_record,
                capability=capability,
            ),
        )

    if late_owner:
        if new_owner_record is None:
            raise _TechnicalRefusal("late venue owner omitted its relational owner")
        acceptance = _selected_acceptance_by_effect(prepared).get(retained.effect_id)
        if acceptance is None:
            acceptance = _cast(
                _records.AcceptanceSetRecord,
                _required_repository_record(
                    "targeted acceptance set",
                    _repository.load_acceptance_set_for_effect(
                        connection,
                        retained.effect_id,
                    ),
                    _records.AcceptanceSetRecord,
                ),
            )
        if acceptance is None:
            raise _TechnicalRefusal("late venue owner lacks its acceptance set")
        evidence = _records.AcceptanceEvidenceRecord(
            _next_acceptance_evidence_id(connection),
            acceptance.acceptance_set_id,
            retained.effect_id,
            "INVALIDATION",
            None,
            _hashlib.sha256(prepared.canonical_payload_bytes).hexdigest(),
            _next_acceptance_evidence_ordinal(connection),
            new_owner_record.owner_id,
            new_owner_record.observation_id,
        )
        _require_applied_repository_outcome(
            "late-owner invalidation evidence",
            _repository.store_acceptance_evidence(
                connection,
                evidence,
                capability=capability,
            ),
        )
        expected = _replace(
            retained,
            disposition=successor_effect.acceptance_set_state.value,
        )
        loaded = _cast(
            _records.VenueEffectRecord,
            _required_repository_record(
                "invalidated venue effect",
                _repository.load_venue_effect(connection, retained.effect_id),
                _records.VenueEffectRecord,
            ),
        )
        if loaded != expected or not _effect_matches_record(successor_effect, loaded):
            raise _TechnicalRefusal("late-owner invalidation result is not exact")
        retained = loaded
    elif not _effect_matches_record(successor_effect, retained):
        raise _TechnicalRefusal("venue effect result was not retained exactly")
    return retained, new_owner_record, late_owner


def _persist_venue_terminal_closure(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    transition: _venue.VenueRecoveryTransition,
    effect_record: _records.VenueEffectRecord,
    capability: _repository._RuntimeWriteCapability,
) -> _records.ClosureChainRecord | None:
    operation = prepared.operation
    if type(operation) is not _operations.VenueRecoveryOperation:
        raise _TechnicalRefusal("venue closure persistence received another operation")
    leg_key = _venue_item_leg_key(operation.item)
    if leg_key is None:
        return None
    predecessor = prepared.context.venue.closure_head(leg_key)
    successor = transition.book.closure_head(leg_key)
    if successor is None or successor == predecessor:
        return None
    item_input_id = getattr(operation.item, "input_id", None)
    if (
        successor.source_input_id != item_input_id
        or successor.leg_key != leg_key
        or successor.kind
        not in {
            _venue.VenueClosureKind.BROKER_TERMINAL,
            _venue.VenueClosureKind.BROKER_ECONOMIC,
            _venue.VenueClosureKind.OPERATOR_RECONCILED,
        }
    ):
        raise _TechnicalRefusal("venue closure result is not exact")
    retained_predecessor = _selected_closures_by_owner(prepared).get(leg_key.order_id)
    if predecessor is None:
        if (
            successor.ordinal != 1
            or successor.predecessor_closure_id is not None
            or retained_predecessor is not None
        ):
            raise _TechnicalRefusal("first venue closure has a predecessor")
        predecessor_id = None
    else:
        if (
            retained_predecessor is None
            or retained_predecessor.ordinal != predecessor.ordinal
            or retained_predecessor.effect_id != effect_record.effect_id
            or successor.ordinal != predecessor.ordinal + 1
            or successor.predecessor_closure_id != predecessor.closure_id
        ):
            raise _TechnicalRefusal("venue closure predecessor is not exact")
        predecessor_id = retained_predecessor.closure_id
    record = _records.ClosureChainRecord(
        _next_closure_id(connection),
        prepared.scope_id,
        leg_key.order_id,
        successor.ordinal,
        effect_record.effect_id,
        "TERMINAL_LEG",
        predecessor_id,
    )
    _require_applied_repository_outcome(
        "venue terminal closure",
        _repository.store_closure(
            connection,
            record,
            capability=capability,
        ),
    )
    return record


def _venue_relation_owner_records(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    relation: _venue.AcquisitionFactRelation,
) -> tuple[_records.VenueEffectRecord, _records.VenueIdentityOwnerRecord]:
    if type(relation) is not _venue.AcquisitionFactRelation:
        raise _TechnicalRefusal("venue fact relation is not exact")
    effect = _selected_effects_by_external(prepared).get(relation.effect_id)
    if effect is None:
        effect = _cast(
            _records.VenueEffectRecord,
            _required_repository_record(
                "venue fact effect",
                _repository._load_venue_effect_by_external(
                    connection,
                    prepared.execution_profile_id,
                    relation.effect_id,
                ),
                _records.VenueEffectRecord,
            ),
        )
    owner = _selected_owners_by_leg(prepared).get(relation.leg_key)
    scopes = tuple(
        row
        for row in prepared.selection_proof._selection.scopes
        if row.scope_id == prepared.scope_id
    )
    if (
        effect is None
        or owner is None
        or len(scopes) != 1
        or relation.application_generation_id != prepared.application_generation_id
        or effect.scope_id != prepared.scope_id
        or scopes[0].symbol != relation.position_scope.symbol_id
    ):
        raise _TechnicalRefusal("venue fact relation lacks its exact owner")
    if (
        effect.effect_id != owner.effect_id
        or effect.request_occurrence_id != relation.request_occurrence_id
        or owner.scope_id != prepared.scope_id
        or owner.execution_profile_id != prepared.execution_profile_id
        or owner.owner_id != relation.leg_key.order_id
        or owner.owner_generation_id != effect.acquisition_generation_id
    ):
        raise _TechnicalRefusal("venue fact relation owner is substituted")
    return effect, owner


def _venue_canonical_fact(
    item: object,
    relation: _venue.AcquisitionFactRelation,
) -> (
    _fills.BrokerFillFact
    | _fills.BrokerTradeCorrectFact
    | _fills.BrokerTradeBustFact
    | _fills.HumanAttestedFillFact
):
    fact = getattr(item, "fact", None)
    if type(fact) not in {
        _fills.BrokerFillFact,
        _fills.BrokerTradeCorrectFact,
        _fills.BrokerTradeBustFact,
        _fills.HumanAttestedFillFact,
    }:
        raise _TechnicalRefusal("venue fact relation omitted its canonical fact")
    canonical = _cast(
        _fills.BrokerFillFact
        | _fills.BrokerTradeCorrectFact
        | _fills.BrokerTradeBustFact
        | _fills.HumanAttestedFillFact,
        fact,
    )
    if (
        canonical.key != relation.fact_key
        or canonical.root_key != relation.root_key
        or canonical.scope.position_scope != relation.position_scope
    ):
        raise _TechnicalRefusal("venue canonical fact disagrees with its relation")
    return canonical


def _venue_execution_fact_record(
    prepared: _PreparedOperation,
    fact: _fills.BrokerFillFact
    | _fills.BrokerTradeCorrectFact
    | _fills.BrokerTradeBustFact
    | _fills.HumanAttestedFillFact,
    *,
    fact_id: int,
    root_fill_key_id: int,
    predecessor_fact_id: int | None,
    fact_ordinal: int,
) -> _records.ExecutionFactRecord:
    quantity, price = _broker_fact_economics(fact)
    human = fact if type(fact) is _fills.HumanAttestedFillFact else None
    return _records.ExecutionFactRecord(
        fact_id,
        prepared.scope_id,
        prepared.application_generation_id,
        prepared.execution_profile_id,
        root_fill_key_id,
        fact.key.source_event_id,
        fact.scope.order_id,
        fact.scope.side.value,
        fact.kind.value,
        fact.authority.value,
        quantity,
        price,
        None if human is None else human.request_occurrence_id,
        None if human is None else human.claim_occurrence_id,
        None if human is None else human.prior_cumulative_quantity,
        None if human is None else human.resulting_cumulative_quantity,
        None if human is None else human.actor,
        None if human is None else human.reason,
        None if human is None else human.evidence_reference,
        predecessor_fact_id,
        fact_ordinal,
    )


def _persist_venue_economics(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    transition: _venue.VenueRecoveryTransition,
    relation: _venue.AcquisitionFactRelation,
    capability: _repository._RuntimeWriteCapability,
) -> tuple[
    _records.ExecutionFactRecord,
    _records.RootFillRecord,
    _records.AcquisitionRootRouteRecord,
    _records.ExecutionFactRecord | None,
]:
    operation = prepared.operation
    if type(operation) is not _operations.VenueRecoveryOperation:
        raise _TechnicalRefusal("venue economics received another operation")
    fact = _venue_canonical_fact(operation.item, relation)
    effect, owner = _venue_relation_owner_records(connection, prepared, relation)
    root_outcome = _repository.load_root_fill_by_external(
        connection,
        prepared.execution_profile_id,
        fact.root_fill_id,
    )
    predecessor_fact: _records.ExecutionFactRecord | None
    if fact.kind is _fills.FactKind.FILL:
        _require_repository_absence("venue root fill", root_outcome)
        root_fill_key_id = _next_root_fill_key_id(connection)
        root = _records.RootFillRecord(
            root_fill_key_id,
            prepared.scope_id,
            prepared.application_generation_id,
            prepared.execution_profile_id,
            owner.owner_generation_id,
            fact.root_fill_id,
            None,
            None,
            None,
            None,
            None,
            None,
            0,
        )
        _require_applied_repository_outcome(
            "venue root fill",
            _repository.store_root_fill(
                connection,
                root,
                capability=capability,
            ),
        )
        route = _records.AcquisitionRootRouteRecord(
            root_fill_key_id,
            prepared.scope_id,
            prepared.application_generation_id,
            prepared.execution_profile_id,
            owner.owner_generation_id,
            effect.effect_id,
            owner.owner_id,
            owner.observation_id,
        )
        _require_applied_repository_outcome(
            "venue acquisition root route",
            _repository.store_acquisition_root_route(
                connection,
                route,
                capability=capability,
            ),
        )
        predecessor_fact = None
        predecessor_fact_id = None
    else:
        root = _cast(
            _records.RootFillRecord,
            _required_repository_record(
                "venue root fill",
                root_outcome,
                _records.RootFillRecord,
            ),
        )
        route = _cast(
            _records.AcquisitionRootRouteRecord,
            _required_repository_record(
                "venue acquisition root route",
                _repository.load_acquisition_root_route(
                    connection,
                    root.root_fill_key_id,
                ),
                _records.AcquisitionRootRouteRecord,
            ),
        )
        if root.current_fact_id is None:
            raise _TechnicalRefusal("venue revision root has no current fact")
        predecessor_fact = _cast(
            _records.ExecutionFactRecord,
            _required_repository_record(
                "venue revision predecessor",
                _repository.load_execution_fact(
                    connection,
                    root.current_fact_id,
                ),
                _records.ExecutionFactRecord,
            ),
        )
        expected_predecessor = getattr(fact, "predecessor_source_event_id", None)
        if (
            route.effect_id != effect.effect_id
            or route.owner_id != owner.owner_id
            or route.observation_id != owner.observation_id
            or route.acquisition_generation_id != owner.owner_generation_id
            or predecessor_fact.source_event_id != expected_predecessor
            or predecessor_fact.fact_id != root.current_fact_id
        ):
            raise _TechnicalRefusal("venue revision predecessor route is not exact")
        predecessor_fact_id = predecessor_fact.fact_id

    quantity, price = _broker_fact_economics(fact)
    fact_record = _venue_execution_fact_record(
        prepared,
        fact,
        fact_id=_next_execution_fact_id(connection),
        root_fill_key_id=root.root_fill_key_id,
        predecessor_fact_id=predecessor_fact_id,
        fact_ordinal=_next_execution_fact_ordinal(connection),
    )
    _require_applied_repository_outcome(
        "venue execution fact",
        _repository.store_execution_fact(
            connection,
            fact_record,
            capability=capability,
        ),
    )
    retained_root = _cast(
        _records.RootFillRecord,
        _required_repository_record(
            "resulting venue root fill",
            _repository.load_root_fill(connection, root.root_fill_key_id),
            _records.RootFillRecord,
        ),
    )
    retained_route = _cast(
        _records.AcquisitionRootRouteRecord,
        _required_repository_record(
            "resulting venue root route",
            _repository.load_acquisition_root_route(
                connection,
                root.root_fill_key_id,
            ),
            _records.AcquisitionRootRouteRecord,
        ),
    )
    retained_fact = _cast(
        _records.ExecutionFactRecord,
        _required_repository_record(
            "resulting venue execution fact",
            _repository.load_execution_fact_by_source(
                connection,
                prepared.execution_profile_id,
                fact.key.source_event_id,
            ),
            _records.ExecutionFactRecord,
        ),
    )
    retained_head = _cast(
        _records.ExecutionFactHeadRecord,
        _required_repository_record(
            "resulting venue execution fact head",
            _repository.load_execution_fact_head(
                connection,
                root.root_fill_key_id,
            ),
            _records.ExecutionFactHeadRecord,
        ),
    )
    if (
        retained_route != route
        or retained_fact != fact_record
        or retained_head
        != _records.ExecutionFactHeadRecord(
            root.root_fill_key_id,
            fact_record.fact_id,
            fact_record.fact_ordinal,
        )
        or retained_root.current_fact_id != fact_record.fact_id
        or retained_root.current_kind != fact.kind.value
        or retained_root.current_authority != fact.authority.value
        or retained_root.current_side != fact.scope.side.value
        or retained_root.current_quantity != quantity
        or retained_root.current_price != price
        or retained_root.economics_head_ordinal != fact_record.fact_ordinal
        or not _execution_record_matches_fact(
            retained_fact,
            fact,
            root_fill_key_id=root.root_fill_key_id,
            predecessor_fact_id=predecessor_fact_id,
        )
        or transition.execution.seen_facts.get(fact.key) is None
    ):
        raise _TechnicalRefusal("resulting venue economics are not exact")
    return fact_record, retained_root, retained_route, predecessor_fact


def _selected_acquisition_authority(
    prepared: _PreparedOperation,
    acquisition: _acquisition.AcquisitionControllerState,
    execution: _position.ExecutionSnapshot,
    protection: _protection.PositionProtectionState | None,
) -> _SelectedAcquisitionAuthority:
    selection = prepared.selection_proof._selection
    scopes = tuple(row for row in selection.scopes if row.scope_id == prepared.scope_id)
    controllers = tuple(
        row for row in selection.controllers if row.scope_id == prepared.scope_id
    )
    protections = tuple(
        row
        for row in selection.protection_authorities
        if row.scope_id == prepared.scope_id
    )
    if len(scopes) != 1 or len(controllers) != 1 or len(protections) != 1:
        raise _TechnicalRefusal("acquisition current rows are not singular")
    scope = scopes[0]
    controller = controllers[0]
    protection_record = protections[0]
    generation_id = controller.live_acquisition_generation_id
    generations = tuple(
        row
        for row in selection.live_generations
        if row.scope_id == prepared.scope_id
        and row.acquisition_generation_id == generation_id
    )
    currents = tuple(
        row
        for row in selection.live_generation_current
        if row.scope_id == prepared.scope_id
        and row.acquisition_generation_id == generation_id
    )
    streams = tuple(
        row
        for row in selection.streams
        if row.scope_id == prepared.scope_id
        and row.acquisition_generation_id == generation_id
    )
    if (
        generation_id is None
        or (
            prepared.acquisition_generation_id is not None
            and prepared.acquisition_generation_id != generation_id
        )
        or len(generations) != 1
        or len(currents) != 1
        or len(streams) != 1
    ):
        raise _TechnicalRefusal("acquisition live authority is not singular")
    generation = generations[0]
    generation_current = currents[0]
    stream = streams[0]
    cursors = tuple(
        row
        for row in selection.cursors
        if row.scope_id == prepared.scope_id
        and row.stream_generation_id == stream.stream_generation_id
    )
    if len(cursors) != 1:
        raise _TechnicalRefusal("acquisition market cursor is not singular")
    cursor = cursors[0]
    owner_generation = acquisition.registry.record(generation_id)
    owner_route = _acquisition._registry_market_stream_route(
        acquisition.registry,
        stream.stream_generation_id,
    )
    if (
        scope.application_generation_id != prepared.application_generation_id
        or scope.execution_profile_id != prepared.execution_profile_id
        or scope.symbol != acquisition.position_scope.symbol_id
        or controller.application_generation_id != prepared.application_generation_id
        or controller.execution_profile_id != prepared.execution_profile_id
        or controller.aggregate_quantity != execution.position.raw_quantity
        or controller.currentness_head_ordinal
        != protection_record.expected_controller_head_ordinal
        or generation.status != "LIVE"
        or owner_generation is None
        or owner_route is None
        or owner_generation.serving_class
        is not _acquisition.GenerationServingClass.LIVE
        or owner_generation.binding != owner_route.binding
        or owner_generation.binding.successor_ordinal + 1
        != generation.successor_ordinal
        or owner_generation.binding.dual_mandate_binding_commitment.hex()
        != generation.mandate_commitment_sha256
        or owner_generation.binding.emergency_recovery_compatibility_commitment.hex()
        != generation.emergency_compatibility_sha256
        or stream.application_generation_id != prepared.application_generation_id
        or stream.generation_mandate_commitment_sha256
        != generation.mandate_commitment_sha256
        or stream.session_id != acquisition._mandate.session_id
        or stream.stream_generation_id
        != acquisition._mandate.protection_mandate.evidence_policy.stream_generation
        or stream.sequence_mode
        != acquisition._mandate.protection_mandate.evidence_policy.sequence_mode.value
        or cursor.application_generation_id != stream.application_generation_id
        or cursor.acquisition_generation_id != stream.acquisition_generation_id
        or cursor.generation_mandate_commitment_sha256
        != stream.generation_mandate_commitment_sha256
        or cursor.source_profile_id != stream.source_profile_id
        or cursor.session_id != stream.session_id
        or cursor.sequence_mode != stream.sequence_mode
    ):
        raise _TechnicalRefusal(
            "acquisition durable authority disagrees with its owner"
        )
    active_coordinates = (
        protection_record.active_stream_generation_id,
        protection_record.active_acquisition_generation_id,
        protection_record.active_generation_mandate_commitment_sha256,
        protection_record.active_source_profile_id,
        protection_record.active_session_id,
        protection_record.active_sequence_mode,
    )
    if protection is None:
        if (
            any(value is not None for value in active_coordinates)
            or generation_current.active_protection_count != 0
            or protection_record.authority_class != "NORMAL"
        ):
            raise _TechnicalRefusal("dormant protection authority is partially active")
    else:
        expected_authority_class = (
            "HARD_BAIL"
            if protection.policy is _protection.ProtectionPolicy.HARD_BAIL
            else "NORMAL"
        )
        if (
            generation_current.active_protection_count != 1
            or protection_record.authority_class != expected_authority_class
            or active_coordinates
            != (
                stream.stream_generation_id,
                generation.acquisition_generation_id,
                generation.mandate_commitment_sha256,
                stream.source_profile_id,
                stream.session_id,
                stream.sequence_mode,
            )
            or protection.mandate != acquisition._mandate.protection_mandate
            or protection.commitment.hex() != protection_record.state_commitment_sha256
        ):
            raise _TechnicalRefusal(
                "active protection authority disagrees with its owner"
            )
    return _SelectedAcquisitionAuthority(
        scope,
        controller,
        generation,
        generation_current,
        protection_record,
        stream,
        cursor,
    )


def _scope_effect_authority(
    selected: _SelectedAcquisitionAuthority,
    controller: _records.SymbolControllerRecord,
    protection: _records.ProtectionAuthorityRecord,
) -> _SelectedScopeAuthority:
    return _SelectedScopeAuthority(
        selected.scope,
        controller,
        selected.generation,
        protection,
    )


def _advance_acquisition_currentness(
    connection: _SQLiteConnectionProtocol,
    selected: _SelectedAcquisitionAuthority,
    predecessor_state: _protection.PositionProtectionState | None,
    successor_state: _protection.PositionProtectionState | None,
    capability: _repository._RuntimeWriteCapability,
) -> _SelectedScopeAuthority:
    active = (
        selected.protection.active_stream_generation_id,
        selected.protection.active_acquisition_generation_id,
        selected.protection.active_generation_mandate_commitment_sha256,
        selected.protection.active_source_profile_id,
        selected.protection.active_session_id,
        selected.protection.active_sequence_mode,
    )
    if successor_state is None:
        if predecessor_state is not None or any(value is not None for value in active):
            raise _TechnicalRefusal("currentness advance cannot discard protection")
        authority_class = "NORMAL"
        state_commitment = selected.protection.state_commitment_sha256
    else:
        if (
            predecessor_state is None
            or successor_state.mandate.evidence_policy.stream_generation
            != selected.stream.stream_generation_id
            or successor_state.mandate.session_id != selected.stream.session_id
            or successor_state.mandate.evidence_policy.sequence_mode.value
            != selected.stream.sequence_mode
            or active
            != (
                selected.stream.stream_generation_id,
                selected.generation.acquisition_generation_id,
                selected.generation.mandate_commitment_sha256,
                selected.stream.source_profile_id,
                selected.stream.session_id,
                selected.stream.sequence_mode,
            )
            or successor_state._cursor_ordinal < selected.cursor.fixed_cursor_ordinal
        ):
            raise _TechnicalRefusal("successor protection authority is not contiguous")
        protection_changed = successor_state.commitment != predecessor_state.commitment
        if protection_changed:
            published = max(
                selected.cursor.published_head_ordinal + 1,
                successor_state._cursor_ordinal,
            )
            cursor = _replace(
                selected.cursor,
                fixed_cursor_ordinal=successor_state._cursor_ordinal,
                published_head_ordinal=published,
            )
            _require_applied_repository_outcome(
                "market cursor",
                _repository.advance_market_cursor(
                    connection,
                    selected.cursor.fixed_cursor_ordinal,
                    selected.cursor.published_head_ordinal,
                    cursor,
                    capability=capability,
                ),
            )
        authority_class = (
            "HARD_BAIL"
            if successor_state.policy is _protection.ProtectionPolicy.HARD_BAIL
            else "NORMAL"
        )
        state_commitment = successor_state.commitment.hex()
    controller = _replace(
        selected.controller,
        currentness_head_ordinal=selected.controller.currentness_head_ordinal + 1,
        controller_version_ordinal=selected.controller.controller_version_ordinal + 1,
    )
    _advance_controller_record(
        connection,
        selected.controller,
        controller,
        capability,
    )
    protection = _replace(
        selected.protection,
        authority_class=authority_class,
        expected_controller_head_ordinal=controller.currentness_head_ordinal,
        state_commitment_sha256=state_commitment,
        version_ordinal=selected.protection.version_ordinal + 1,
    )
    _advance_protection_record(
        connection,
        selected.protection,
        protection,
        capability,
    )
    return _scope_effect_authority(selected, controller, protection)


def _advance_venue_protection_after_trigger(
    connection: _SQLiteConnectionProtocol,
    selected: _SelectedAcquisitionAuthority,
    controller: _records.SymbolControllerRecord,
    predecessor_state: _protection.PositionProtectionState | None,
    successor_state: _protection.PositionProtectionState | None,
    capability: _repository._RuntimeWriteCapability,
) -> _SelectedScopeAuthority:
    active = (
        selected.protection.active_stream_generation_id,
        selected.protection.active_acquisition_generation_id,
        selected.protection.active_generation_mandate_commitment_sha256,
        selected.protection.active_source_profile_id,
        selected.protection.active_session_id,
        selected.protection.active_sequence_mode,
    )
    expected_active = (
        selected.stream.stream_generation_id,
        selected.generation.acquisition_generation_id,
        selected.generation.mandate_commitment_sha256,
        selected.stream.source_profile_id,
        selected.stream.session_id,
        selected.stream.sequence_mode,
    )
    if successor_state is None:
        if predecessor_state is not None or any(value is not None for value in active):
            raise _TechnicalRefusal("triggered currentness cannot discard protection")
        authority_class = "NORMAL"
        state_commitment = selected.protection.state_commitment_sha256
        successor_active: tuple[object | None, ...] = (None,) * 6
    else:
        if (
            successor_state.mandate.evidence_policy.stream_generation
            != selected.stream.stream_generation_id
            or successor_state.mandate.session_id != selected.stream.session_id
            or successor_state.mandate.evidence_policy.sequence_mode.value
            != selected.stream.sequence_mode
            or successor_state._cursor_ordinal < selected.cursor.fixed_cursor_ordinal
            or (
                predecessor_state is None and any(value is not None for value in active)
            )
            or (predecessor_state is not None and active != expected_active)
        ):
            raise _TechnicalRefusal("triggered successor protection is not contiguous")
        protection_changed = bool(
            predecessor_state is None
            or successor_state.commitment != predecessor_state.commitment
        )
        if protection_changed:
            published = max(
                selected.cursor.published_head_ordinal + 1,
                successor_state._cursor_ordinal,
            )
            cursor = _replace(
                selected.cursor,
                fixed_cursor_ordinal=successor_state._cursor_ordinal,
                published_head_ordinal=published,
            )
            _require_applied_repository_outcome(
                "venue market cursor",
                _repository.advance_market_cursor(
                    connection,
                    selected.cursor.fixed_cursor_ordinal,
                    selected.cursor.published_head_ordinal,
                    cursor,
                    capability=capability,
                ),
            )
        authority_class = (
            "HARD_BAIL"
            if successor_state.policy is _protection.ProtectionPolicy.HARD_BAIL
            else "NORMAL"
        )
        state_commitment = successor_state.commitment.hex()
        successor_active = expected_active
    protection = _records.ProtectionAuthorityRecord(
        selected.protection.scope_id,
        authority_class,
        _cast(_identity.MarketStreamGenerationId | None, successor_active[0]),
        _cast(_identity.AcquisitionGenerationId | None, successor_active[1]),
        _cast(str | None, successor_active[2]),
        _cast(str | None, successor_active[3]),
        _cast(_identity.SessionId | None, successor_active[4]),
        _cast(str | None, successor_active[5]),
        controller.currentness_head_ordinal,
        state_commitment,
        selected.protection.version_ordinal + 1,
    )
    _advance_protection_record(
        connection,
        selected.protection,
        protection,
        capability,
    )
    return _scope_effect_authority(selected, controller, protection)


def _triggered_venue_controller(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    selected: _SelectedAcquisitionAuthority,
    transition: _venue.VenueRecoveryTransition,
    *,
    expected_step: int,
) -> _records.SymbolControllerRecord:
    if expected_step not in (0, 1):
        raise _TechnicalRefusal("venue controller step is not bounded")
    controller = _cast(
        _records.SymbolControllerRecord,
        _required_repository_record(
            "resulting venue symbol controller",
            _repository.load_symbol_controller(connection, prepared.scope_id),
            _records.SymbolControllerRecord,
        ),
    )
    if (
        controller.application_generation_id != prepared.application_generation_id
        or controller.execution_profile_id != prepared.execution_profile_id
        or controller.live_acquisition_generation_id
        != selected.generation.acquisition_generation_id
        or controller.aggregate_quantity != transition.execution.position.raw_quantity
        or controller.currentness_head_ordinal
        != selected.controller.currentness_head_ordinal + expected_step
        or controller.controller_version_ordinal
        != selected.controller.controller_version_ordinal + expected_step
    ):
        raise _TechnicalRefusal("venue trigger did not advance the exact controller")
    return controller


def _acquisition_successor_context(
    prepared: _PreparedOperation,
    transition: _acquisition.AcquisitionControllerTransition,
) -> UnitOfWorkContext:
    if (
        type(transition) is not _acquisition.AcquisitionControllerTransition
        or type(transition.state) is not _acquisition.AcquisitionControllerState
        or type(transition.execution) is not _position.ExecutionSnapshot
        or type(transition.authority) is not _authority.ExecutionAuthorityState
        or transition.authority.venue is not transition.venue
        or transition.state.position_scope != transition.execution.position.scope
    ):
        raise _TechnicalRefusal("acquisition transition owner set is not exact")
    replaced = False
    owners: list[_ScopeOwner] = []
    for scope_id, acquisition, execution, protection in prepared.context.scope_owners:
        if scope_id == prepared.scope_id:
            owners.append(
                (
                    scope_id,
                    transition.state,
                    transition.execution,
                    transition.protection,
                )
            )
            replaced = True
        else:
            owners.append((scope_id, acquisition, execution, protection))
    if not replaced:
        raise _TechnicalRefusal("acquisition successor scope is absent")
    return UnitOfWorkContext(
        prepared.context.expected_checkpoint,
        transition.venue,
        transition.authority,
        tuple(owners),
    )


def _acquisition_transition_for_operation(
    prepared: _PreparedOperation,
) -> tuple[
    _acquisition.AcquisitionControllerTransition,
    tuple[_venue.VenueRecoveryTransition, ...],
]:
    operation = prepared.operation
    acquisition, execution, protection = _selected_acquisition_owner(prepared)
    try:
        refresh = _authority.refresh_acquisition_context(
            prepared.context.authority,
            execution,
            acquisition.position_scope,
        )
        if type(operation) is _operations.BeginAcquisitionGenerationOperation:
            if refresh.authority is None or refresh.execution is None:
                raise _TechnicalRefusal("acquisition generation refresh is incomplete")
            bootstrap = refresh.authority.venue.project_acquisition_bootstrap(
                refresh.execution,
                acquisition.position_scope,
            )
            admission = _authority.project_acquisition_admission(
                refresh.authority,
                refresh.execution,
                acquisition.position_scope,
            )
            transition = _acquisition._m2_begin_acquisition_generation(
                acquisition,
                operation.successor_mandate,
                bootstrap,
                admission,
                refresh,
                protection,
            )
        elif type(operation) is _operations.CreateAcquisitionEffectOperation:
            transition = _acquisition._m2_create_acquisition_effect(
                acquisition,
                refresh,
                protection,
                operation.terms,
                operation.input_id,
            )
        elif type(operation) is _operations.ClaimAcquisitionEffectOperation:
            transition = _acquisition._m2_claim_acquisition_effect(
                acquisition,
                refresh,
                protection,
                operation.effect_id,
                operation.claim_occurrence_id,
                operation.input_id,
            )
        elif type(operation) is _operations.BeginAcquisitionPreemptionOperation:
            transition = _acquisition._m2_begin_acquisition_preemption(
                acquisition,
                refresh,
                protection,
                operation.input_id,
            )
        else:
            raise _TechnicalRefusal("acquisition operation route is not admitted here")
        derivatives = (
            refresh.venue_transitions
            + _acquisition._m2_acquisition_transition_venue_derivatives(transition)
        )
    except _TechnicalRefusal:
        raise
    except (TypeError, ValueError, OverflowError) as exc:
        raise _TechnicalRefusal("acquisition owner reduction was refused") from exc
    return transition, derivatives


def _advance_protection_record(
    connection: _SQLiteConnectionProtocol,
    predecessor: _records.ProtectionAuthorityRecord,
    successor: _records.ProtectionAuthorityRecord,
    capability: _repository._RuntimeWriteCapability,
) -> None:
    _require_applied_repository_outcome(
        "protection authority",
        _repository.advance_protection_authority(
            connection,
            predecessor.version_ordinal,
            successor,
            capability=capability,
        ),
    )


def _advance_controller_record(
    connection: _SQLiteConnectionProtocol,
    predecessor: _records.SymbolControllerRecord,
    successor: _records.SymbolControllerRecord,
    capability: _repository._RuntimeWriteCapability,
) -> None:
    _require_applied_repository_outcome(
        "symbol controller",
        _repository.advance_symbol_controller(
            connection,
            predecessor.controller_version_ordinal,
            successor,
            capability=capability,
        ),
    )


def _execute_generation_operation(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    transition: _acquisition.AcquisitionControllerTransition,
    selected: _SelectedAcquisitionAuthority,
    capability: _repository._RuntimeWriteCapability,
) -> _TransactionDecision:
    if type(prepared.operation) is not _operations.BeginAcquisitionGenerationOperation:
        raise _TechnicalRefusal("generation route received another operation")
    candidate_context = _acquisition_successor_context(prepared, transition)
    if (
        transition.disposition
        is not _acquisition.AcquisitionControllerDisposition.APPLIED
    ):
        return _complete_claimed_input(
            connection,
            prepared,
            claimed,
            owner_domain="ACQUISITION",
            owner_disposition=transition.disposition.value,
            successor_context=prepared.context,
            checkpoint_changed=False,
            pending_outbox=None,
            capability=capability,
        )
    if (
        selected.controller.aggregate_quantity != 0
        or selected.controller.integrity_state != "CONSISTENT"
        or selected.generation_current.unresolved_effect_count != 0
        or selected.generation_current.active_protection_count != 0
        or transition.execution.position.raw_quantity != 0
        or transition.protection is not None
    ):
        raise _TechnicalRefusal("generation successor authority is not closed")

    retained_protection = selected.protection
    if retained_protection.active_stream_generation_id is not None:
        neutral = _replace(
            retained_protection,
            authority_class="NORMAL",
            active_stream_generation_id=None,
            active_acquisition_generation_id=None,
            active_generation_mandate_commitment_sha256=None,
            active_source_profile_id=None,
            active_session_id=None,
            active_sequence_mode=None,
            version_ordinal=retained_protection.version_ordinal + 1,
        )
        _advance_protection_record(
            connection,
            retained_protection,
            neutral,
            capability,
        )
        retained_protection = neutral

    predecessor_controller = selected.controller
    null_controller = _replace(
        predecessor_controller,
        live_acquisition_generation_id=None,
        currentness_head_ordinal=predecessor_controller.currentness_head_ordinal + 1,
        controller_version_ordinal=(
            predecessor_controller.controller_version_ordinal + 1
        ),
    )
    _advance_controller_record(
        connection,
        predecessor_controller,
        null_controller,
        capability,
    )
    null_protection = _replace(
        retained_protection,
        expected_controller_head_ordinal=null_controller.currentness_head_ordinal,
        version_ordinal=retained_protection.version_ordinal + 1,
    )
    _advance_protection_record(
        connection,
        retained_protection,
        null_protection,
        capability,
    )
    _require_applied_repository_outcome(
        "retired acquisition generation",
        _repository.retire_acquisition_generation(
            connection,
            selected.generation.acquisition_generation_id,
            capability=capability,
        ),
    )

    successor_id = transition.state._controller.live_generation_id
    successor_owner = (
        None if successor_id is None else transition.state.registry.record(successor_id)
    )
    if (
        successor_id is None
        or successor_id == selected.generation.acquisition_generation_id
        or successor_owner is None
        or successor_owner.serving_class is not _acquisition.GenerationServingClass.LIVE
        or successor_owner.binding.successor_ordinal + 1
        != selected.generation.successor_ordinal + 1
        or successor_owner.binding.dual_mandate_binding_commitment
        != transition.state._mandate.binding.commitment
    ):
        raise _TechnicalRefusal("generation successor binding is not exact")
    successor_generation = _records.AcquisitionGenerationRecord(
        successor_id,
        selected.scope.scope_id,
        "LIVE",
        successor_owner.binding.successor_ordinal + 1,
        selected.generation.acquisition_generation_id,
        successor_owner.binding.dual_mandate_binding_commitment.hex(),
        successor_owner.binding.emergency_recovery_compatibility_commitment.hex(),
    )
    _require_applied_repository_outcome(
        "successor acquisition generation",
        _repository.store_acquisition_generation(
            connection,
            successor_generation,
            capability=capability,
        ),
    )
    current = _repository.load_acquisition_generation_current(
        connection,
        successor_id,
    )
    expected_current = _records.AcquisitionGenerationCurrentRecord(
        successor_id,
        selected.scope.scope_id,
        0,
        0,
        0,
    )
    if (
        current.kind is not _records.RepositoryOutcomeKind.FOUND
        or current.record != expected_current
    ):
        raise _TechnicalRefusal("successor generation current proof is not exact")

    mandate = transition.state._mandate
    policy = mandate.protection_mandate.evidence_policy
    route = _acquisition._registry_market_stream_route(
        transition.state.registry,
        policy.stream_generation,
    )
    if route is None or route.binding != successor_owner.binding:
        raise _TechnicalRefusal("successor market stream route is not exact")
    source_profile_id = prepared.selection_proof.request.market_source_profile_id
    stream = _records.MarketStreamAuthorityRecord(
        policy.stream_generation,
        selected.scope.scope_id,
        prepared.application_generation_id,
        successor_id,
        successor_generation.mandate_commitment_sha256,
        source_profile_id,
        mandate.session_id,
        policy.sequence_mode.value,
    )
    _require_applied_repository_outcome(
        "successor market stream",
        _repository.store_market_stream_authority(
            connection,
            stream,
            capability=capability,
        ),
    )
    venue_context = transition.venue.project_acquisition_context(
        transition.execution,
        transition.state.position_scope,
    )
    if not venue_context.matches_current(
        transition.venue,
        transition.execution,
        transition.state.application_generation_id,
        transition.state.position_scope,
    ):
        raise _TechnicalRefusal("successor venue cursor is not current")
    fixed_cursor = venue_context._source_protection_cursor_ordinal
    cursor = _records.MarketCursorRecord(
        stream.stream_generation_id,
        stream.scope_id,
        stream.application_generation_id,
        stream.acquisition_generation_id,
        stream.generation_mandate_commitment_sha256,
        stream.source_profile_id,
        stream.session_id,
        stream.sequence_mode,
        fixed_cursor,
        fixed_cursor,
    )
    _require_applied_repository_outcome(
        "successor market cursor",
        _repository.store_market_cursor(
            connection,
            cursor,
            capability=capability,
        ),
    )

    successor_controller = _replace(
        null_controller,
        live_acquisition_generation_id=successor_id,
        currentness_head_ordinal=null_controller.currentness_head_ordinal + 1,
        controller_version_ordinal=null_controller.controller_version_ordinal + 1,
    )
    _advance_controller_record(
        connection,
        null_controller,
        successor_controller,
        capability,
    )
    successor_protection = _replace(
        null_protection,
        expected_controller_head_ordinal=(
            successor_controller.currentness_head_ordinal
        ),
        version_ordinal=null_protection.version_ordinal + 1,
    )
    _advance_protection_record(
        connection,
        null_protection,
        successor_protection,
        capability,
    )
    return _complete_claimed_input(
        connection,
        prepared,
        claimed,
        owner_domain="ACQUISITION",
        owner_disposition=transition.disposition.value,
        successor_context=candidate_context,
        checkpoint_changed=True,
        pending_outbox=None,
        capability=capability,
    )


def _execute_acquisition_operation(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    capability: _repository._RuntimeWriteCapability,
) -> _TransactionDecision:
    predecessor_acquisition, predecessor_execution, predecessor_protection = (
        _selected_acquisition_owner(prepared)
    )
    selected = _selected_acquisition_authority(
        prepared,
        predecessor_acquisition,
        predecessor_execution,
        predecessor_protection,
    )
    transition, derivatives = _acquisition_transition_for_operation(prepared)
    if type(prepared.operation) is _operations.BeginAcquisitionGenerationOperation:
        return _execute_generation_operation(
            connection,
            prepared,
            claimed,
            transition,
            selected,
            capability,
        )
    applied = (
        transition.disposition is _acquisition.AcquisitionControllerDisposition.APPLIED
    )
    if not applied and derivatives:
        raise _TechnicalRefusal("non-applied acquisition transition emitted writes")
    new_effect_authority: _SelectedScopeAuthority | None = None
    claim_route = (
        type(prepared.operation) is _operations.ClaimAcquisitionEffectOperation
    )
    if applied and not claim_route:
        new_effect_authority = _advance_acquisition_currentness(
            connection,
            selected,
            predecessor_protection,
            transition.protection,
            capability,
        )
    persisted_effects, persisted_claims = _persist_authority_venue_transitions(
        connection,
        prepared,
        derivatives,
        capability,
        new_effect_authority=new_effect_authority,
    )
    created_effect_ids = tuple(record.effect_external for record in persisted_effects)
    if transition.created_effect_id is None:
        if created_effect_ids:
            raise _TechnicalRefusal("acquisition transition emitted an extra effect")
    elif created_effect_ids != (transition.created_effect_id,):
        raise _TechnicalRefusal("acquisition transition omitted its exact effect")

    operation = prepared.operation
    pending_outbox: _records.BrokerOutboxRecord | None = None
    if type(operation) is _operations.ClaimAcquisitionEffectOperation:
        if (
            transition.disposition
            is _acquisition.AcquisitionControllerDisposition.APPLIED
        ):
            fresh_claim = transition.fresh_claim
            if (
                type(fresh_claim) is not _authority.AcquisitionClaimReceipt
                or fresh_claim.effect_id != operation.effect_id
                or fresh_claim.claim_occurrence_id != operation.claim_occurrence_id
                or len(persisted_claims) != 1
                or persisted_claims[0].effect.effect_external != fresh_claim.effect_id
                or persisted_claims[0].claim.claim_occurrence_id
                != fresh_claim.claim_occurrence_id
            ):
                raise _TechnicalRefusal(
                    "acquisition claim transition omitted its exact claim"
                )
            pending_outbox = _broker_outbox_record(
                connection,
                prepared,
                claimed,
                persisted_claims[0],
            )
        elif transition.fresh_claim is not None or persisted_claims:
            raise _TechnicalRefusal("non-applied acquisition claim emitted a claim")
    elif transition.fresh_claim is not None or persisted_claims:
        raise _TechnicalRefusal("acquisition transition emitted an unrelated claim")
    if applied and claim_route:
        _advance_acquisition_currentness(
            connection,
            selected,
            predecessor_protection,
            transition.protection,
            capability,
        )

    candidate_context = _acquisition_successor_context(prepared, transition)
    successor_context = candidate_context if applied else prepared.context
    return _complete_claimed_input(
        connection,
        prepared,
        claimed,
        owner_domain="ACQUISITION",
        owner_disposition=transition.disposition.value,
        successor_context=successor_context,
        checkpoint_changed=applied,
        pending_outbox=pending_outbox,
        capability=capability,
    )


def _market_transition_for_operation(
    prepared: _PreparedOperation,
) -> tuple[
    _protection.ProtectionTransition,
    _acquisition.AcquisitionControllerTransition | None,
    tuple[_venue.VenueRecoveryTransition, ...],
]:
    operation = prepared.operation
    if type(operation) is not _operations.MarketOccurrenceOperation:
        raise _TechnicalRefusal("market operation route is not exact")
    acquisition, execution, current_protection = _selected_acquisition_owner(prepared)
    if current_protection is None:
        raise _TechnicalRefusal("market operation has no current protection owner")
    mandate = current_protection.mandate
    if (
        operation.coordinates.stream_generation_id
        != mandate.evidence_policy.stream_generation
        or operation.coordinates.session_id != mandate.session_id
        or operation.occurrence.position_scope != acquisition.position_scope
    ):
        raise _TechnicalRefusal("market operation protection coordinates are not exact")
    try:
        projection = _protection._m2_project_current_protection_venue(
            prepared.context.venue,
            execution,
            current_protection,
        )
        protection_transition = _protection._m2_reduce_position_protection_market(
            current_protection,
            projection,
            operation.occurrence,
        )
        if (
            protection_transition.disposition
            is not _protection.ProtectionDisposition.APPLIED
        ):
            return protection_transition, None, ()
        refresh = _authority.refresh_acquisition_context(
            prepared.context.authority,
            execution,
            acquisition.position_scope,
        )
        if refresh.venue_context is None:
            raise _TechnicalRefusal(
                "market operation acquisition refresh is incomplete"
            )
        predecessor_context = _protection.project_acquisition_protection_context(
            current_protection,
            prepared.context.venue,
            execution,
            refresh.venue_context,
        )
        current_context = _protection.project_acquisition_protection_context(
            protection_transition.state,
            prepared.context.venue,
            execution,
            refresh.venue_context,
        )
        if predecessor_context is None or current_context is None:
            raise _TechnicalRefusal("market operation protection context is incomplete")
        rebase = _protection.project_acquisition_protection_rebase(
            current_protection,
            protection_transition,
            predecessor_context,
            current_context,
        )
        if rebase is None:
            raise _TechnicalRefusal("market operation protection rebase was refused")
        acquisition_transition = _acquisition._m2_rebase_acquisition_protection(
            acquisition,
            refresh,
            rebase,
        )
        if (
            acquisition_transition.disposition
            is not _acquisition.AcquisitionControllerDisposition.APPLIED
            or acquisition_transition.protection is not protection_transition.state
        ):
            raise _TechnicalRefusal("market operation acquisition rebase was refused")
        if protection_transition.goal is None:
            derivatives = _acquisition._m2_acquisition_transition_venue_derivatives(
                acquisition_transition
            )
        else:
            exit_input_id = _authority.AuthorityInputId(
                "market-protection-exit:"
                + _fills._commit_parts(
                    b"execution-core/uow/market-protection-exit-input/v1",
                    bytes.fromhex(prepared.input_identity_sha256),
                    protection_transition._seal,
                    protection_transition.state.commitment,
                ).hex()
            )
            exit_refresh = _authority.refresh_acquisition_context(
                acquisition_transition.authority,
                acquisition_transition.execution,
                acquisition_transition.state.position_scope,
            )
            acquisition_transition = _acquisition.create_acquisition_protection_exit(
                acquisition_transition.state,
                exit_refresh,
                acquisition_transition.protection,
                protection_transition,
                exit_input_id,
            )
            if (
                acquisition_transition.disposition
                is not _acquisition.AcquisitionControllerDisposition.APPLIED
                or acquisition_transition.created_effect_id is None
            ):
                raise _TechnicalRefusal("market operation protection exit was refused")
            derivatives = _acquisition._m2_acquisition_transition_venue_derivatives(
                acquisition_transition
            )
    except _TechnicalRefusal:
        raise
    except (TypeError, ValueError, OverflowError) as exc:
        raise _TechnicalRefusal("market owner reduction was refused") from exc
    return protection_transition, acquisition_transition, derivatives


def _execute_market_operation(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    capability: _repository._RuntimeWriteCapability,
) -> _TransactionDecision:
    predecessor_acquisition, predecessor_execution, predecessor_protection = (
        _selected_acquisition_owner(prepared)
    )
    selected = _selected_acquisition_authority(
        prepared,
        predecessor_acquisition,
        predecessor_execution,
        predecessor_protection,
    )
    protection_transition, acquisition_transition, derivatives = (
        _market_transition_for_operation(prepared)
    )
    applied = (
        protection_transition.disposition is _protection.ProtectionDisposition.APPLIED
    )
    if not applied:
        if acquisition_transition is not None or derivatives:
            raise _TechnicalRefusal("non-applied market transition emitted writes")
        return _complete_claimed_input(
            connection,
            prepared,
            claimed,
            owner_domain="PROTECTION",
            owner_disposition=protection_transition.disposition.value,
            successor_context=prepared.context,
            checkpoint_changed=False,
            pending_outbox=None,
            capability=capability,
        )
    if (
        acquisition_transition is None
        or acquisition_transition.protection is None
        or predecessor_protection is None
        or acquisition_transition.protection.commitment
        == predecessor_protection.commitment
    ):
        raise _TechnicalRefusal("applied market transition omitted successor authority")
    resulting_authority = _advance_acquisition_currentness(
        connection,
        selected,
        predecessor_protection,
        acquisition_transition.protection,
        capability,
    )
    persisted_effects, persisted_claims = _persist_authority_venue_transitions(
        connection,
        prepared,
        derivatives,
        capability,
        new_effect_authority=resulting_authority,
    )
    if persisted_claims:
        raise _TechnicalRefusal("market transition emitted a dispatch claim")
    created_effect_ids = tuple(record.effect_external for record in persisted_effects)
    if acquisition_transition.created_effect_id is None:
        if created_effect_ids:
            raise _TechnicalRefusal("market transition emitted an extra effect")
    elif created_effect_ids != (acquisition_transition.created_effect_id,):
        raise _TechnicalRefusal("market transition omitted its exact effect")
    successor_context = _acquisition_successor_context(
        prepared,
        acquisition_transition,
    )
    return _complete_claimed_input(
        connection,
        prepared,
        claimed,
        owner_domain="PROTECTION",
        owner_disposition=protection_transition.disposition.value,
        successor_context=successor_context,
        checkpoint_changed=True,
        pending_outbox=None,
        capability=capability,
    )


def _execute_venue_operation(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    capability: _repository._RuntimeWriteCapability,
) -> _TransactionDecision:
    operation = prepared.operation
    if type(operation) is not _operations.VenueRecoveryOperation:
        raise _TechnicalRefusal("venue route received another operation")
    (
        transition,
        acquisition_transition,
        derivatives,
        selected,
        relation,
    ) = _venue_composite_transition_for_operation(connection, prepared)
    _store_venue_transition_semantic_keys(
        connection,
        prepared,
        claimed,
        transition,
        capability,
    )
    if acquisition_transition is None:
        return _complete_claimed_input(
            connection,
            prepared,
            claimed,
            owner_domain="VENUE_RECOVERY",
            owner_disposition=transition.disposition.value,
            successor_context=prepared.context,
            checkpoint_changed=False,
            pending_outbox=None,
            capability=capability,
        )

    effect_record, _, late_owner = _persist_venue_owner_rows(
        connection,
        prepared,
        transition,
        capability,
    )
    _persist_venue_terminal_closure(
        connection,
        prepared,
        transition,
        effect_record,
        capability,
    )
    predecessor_protection = _selected_scope_owner(prepared)[2]
    successor_protection = acquisition_transition.protection
    if relation is not None:
        fact_record, _, route_record, predecessor_fact = _persist_venue_economics(
            connection,
            prepared,
            transition,
            relation,
            capability,
        )
        identical_retired_revision = bool(
            predecessor_fact is not None
            and route_record.acquisition_generation_id
            != selected.generation.acquisition_generation_id
            and predecessor_fact.side == fact_record.side
            and predecessor_fact.quantity == fact_record.quantity
            and predecessor_fact.price == fact_record.price
        )
        controller = _triggered_venue_controller(
            connection,
            prepared,
            selected,
            transition,
            expected_step=0 if identical_retired_revision else 1,
        )
        generation_current = _cast(
            _records.AcquisitionGenerationCurrentRecord,
            _required_repository_record(
                "resulting venue acquisition current",
                _repository.load_acquisition_generation_current(
                    connection,
                    route_record.acquisition_generation_id,
                ),
                _records.AcquisitionGenerationCurrentRecord,
            ),
        )
        if (
            generation_current.scope_id != prepared.scope_id
            or generation_current.current_economics_head_ordinal
            != fact_record.fact_ordinal
        ):
            raise _TechnicalRefusal("venue economics currentness is not exact")
        resulting_authority = _advance_venue_protection_after_trigger(
            connection,
            selected,
            controller,
            predecessor_protection,
            successor_protection,
            capability,
        )
    elif late_owner:
        controller = _triggered_venue_controller(
            connection,
            prepared,
            selected,
            transition,
            expected_step=1,
        )
        resulting_authority = _advance_venue_protection_after_trigger(
            connection,
            selected,
            controller,
            predecessor_protection,
            successor_protection,
            capability,
        )
    else:
        resulting_authority = _advance_acquisition_currentness(
            connection,
            selected,
            predecessor_protection,
            successor_protection,
            capability,
        )

    derivative_tail = derivatives
    if derivative_tail:
        try:
            first_source = _venue._m2_venue_transition_source_item(derivative_tail[0])
        except (TypeError, ValueError, OverflowError) as exc:
            raise _TechnicalRefusal("venue derivative proof was refused") from exc
        if first_source == operation.item:
            derivative_tail = derivative_tail[1:]
    persisted_effects, persisted_claims = _persist_authority_venue_transitions(
        connection,
        prepared,
        derivative_tail,
        capability,
        new_effect_authority=resulting_authority,
        predecessor_book=transition.book,
    )
    if persisted_claims:
        raise _TechnicalRefusal("venue transition emitted a dispatch claim")
    del persisted_effects
    successor_context = _acquisition_successor_context(
        prepared,
        acquisition_transition,
    )
    if not _bounded_context_changed(prepared, successor_context):
        raise _TechnicalRefusal("venue currentness changed without a checkpoint delta")
    return _complete_claimed_input(
        connection,
        prepared,
        claimed,
        owner_domain="VENUE_RECOVERY",
        owner_disposition=transition.disposition.value,
        successor_context=successor_context,
        checkpoint_changed=True,
        pending_outbox=None,
        capability=capability,
    )


def _execute_broker_execution_operation(
    connection: _SQLiteConnectionProtocol,
    prepared: _PreparedOperation,
    claimed: _records.DurableInputRecord,
    capability: _repository._RuntimeWriteCapability,
) -> _TransactionDecision:
    operation = prepared.operation
    if type(operation) is not _operations.BrokerExecutionOperation:
        raise _TechnicalRefusal("broker execution route received another operation")
    (
        execution_transition,
        acquisition_transition,
        derivatives,
        selected,
        predecessor_root,
        predecessor_route,
        predecessor_fact,
        effect_record,
        owner_record,
    ) = _broker_execution_transition_for_operation(connection, prepared)
    if (
        execution_transition.disposition
        is _position.TransitionDisposition.RECONCILIATION_REQUIRED
    ):
        if (
            any(
                value is not None
                for value in (
                    acquisition_transition,
                    predecessor_root,
                    predecessor_route,
                    predecessor_fact,
                    effect_record,
                    owner_record,
                )
            )
            or derivatives
        ):
            raise _TechnicalRefusal("broker reconciliation produced a write plan")
        return _complete_claimed_input(
            connection,
            prepared,
            claimed,
            owner_domain="POSITION",
            owner_disposition=execution_transition.disposition.value,
            successor_context=prepared.context,
            checkpoint_changed=False,
            pending_outbox=None,
            capability=capability,
        )
    if execution_transition.disposition is not _position.TransitionDisposition.APPLIED:
        raise _TechnicalRefusal("broker execution disposition is not admitted")
    fact = operation.fact
    if predecessor_root is None:
        if (
            type(fact) is not _fills.BrokerFillFact
            or predecessor_route is not None
            or predecessor_fact is not None
        ):
            raise _TechnicalRefusal("new broker root proof is inconsistent")
        root_fill_key_id = _next_root_fill_key_id(connection)
        owner_generation_id = (
            selected.generation.acquisition_generation_id
            if owner_record is None
            else owner_record.owner_generation_id
        )
        root_record = _records.RootFillRecord(
            root_fill_key_id,
            prepared.scope_id,
            prepared.application_generation_id,
            prepared.execution_profile_id,
            owner_generation_id,
            fact.root_fill_id,
            None,
            None,
            None,
            None,
            None,
            None,
            0,
        )
        route_record = (
            None
            if effect_record is None or owner_record is None
            else _records.AcquisitionRootRouteRecord(
                root_fill_key_id,
                prepared.scope_id,
                prepared.application_generation_id,
                prepared.execution_profile_id,
                owner_record.owner_generation_id,
                effect_record.effect_id,
                owner_record.owner_id,
                owner_record.observation_id,
            )
        )
        _require_applied_repository_outcome(
            "root fill",
            _repository.store_root_fill(
                connection,
                root_record,
                capability=capability,
            ),
        )
        if route_record is not None:
            _require_applied_repository_outcome(
                "acquisition root route",
                _repository.store_acquisition_root_route(
                    connection,
                    route_record,
                    capability=capability,
                ),
            )
        predecessor_fact_id = None
    else:
        if (
            type(fact)
            not in {
                _fills.BrokerTradeCorrectFact,
                _fills.BrokerTradeBustFact,
            }
            or predecessor_route is None
            or predecessor_fact is None
        ):
            raise _TechnicalRefusal("broker revision proof is incomplete")
        root_fill_key_id = predecessor_root.root_fill_key_id
        root_record = predecessor_root
        route_record = predecessor_route
        predecessor_fact_id = predecessor_fact.fact_id

    fact_id = _next_execution_fact_id(connection)
    fact_ordinal = _next_execution_fact_ordinal(connection)
    quantity, price = _broker_fact_economics(fact)
    fact_record = _records.ExecutionFactRecord(
        fact_id,
        prepared.scope_id,
        prepared.application_generation_id,
        prepared.execution_profile_id,
        root_fill_key_id,
        fact.key.source_event_id,
        fact.scope.order_id,
        fact.scope.side.value,
        fact.kind.value,
        fact.authority.value,
        quantity,
        price,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        predecessor_fact_id,
        fact_ordinal,
    )
    _require_applied_repository_outcome(
        "execution fact",
        _repository.store_execution_fact(
            connection,
            fact_record,
            capability=capability,
        ),
    )

    retained_root = _cast(
        _records.RootFillRecord,
        _required_repository_record(
            "resulting root fill",
            _repository.load_root_fill(connection, root_fill_key_id),
            _records.RootFillRecord,
        ),
    )
    retained_route_outcome = _repository.load_acquisition_root_route(
        connection,
        root_fill_key_id,
    )
    if route_record is None:
        if retained_route_outcome.kind is not _records.RepositoryOutcomeKind.ABSENT:
            raise _TechnicalRefusal("unmatched broker fact acquired a route")
        retained_route = None
    else:
        retained_route = _cast(
            _records.AcquisitionRootRouteRecord,
            _required_repository_record(
                "resulting root route",
                retained_route_outcome,
                _records.AcquisitionRootRouteRecord,
            ),
        )
    retained_fact = _cast(
        _records.ExecutionFactRecord,
        _required_repository_record(
            "resulting execution fact",
            _repository.load_execution_fact_by_source(
                connection,
                prepared.execution_profile_id,
                fact.key.source_event_id,
            ),
            _records.ExecutionFactRecord,
        ),
    )
    if (
        retained_route != route_record
        or retained_fact != fact_record
        or retained_root.current_fact_id != fact_id
        or retained_root.economics_head_ordinal != fact_ordinal
        or retained_root.current_kind != fact.kind.value
        or retained_root.current_authority != fact.authority.value
        or retained_root.current_side != fact.scope.side.value
        or retained_root.current_quantity != quantity
        or retained_root.current_price != price
        or not _execution_record_matches_fact(
            retained_fact,
            fact,
            root_fill_key_id=root_fill_key_id,
            predecessor_fact_id=predecessor_fact_id,
        )
    ):
        raise _TechnicalRefusal("resulting broker fact rows are not exact")

    controller = _cast(
        _records.SymbolControllerRecord,
        _required_repository_record(
            "resulting symbol controller",
            _repository.load_symbol_controller(connection, prepared.scope_id),
            _records.SymbolControllerRecord,
        ),
    )
    identical_retired_revision = bool(
        predecessor_fact is not None
        and route_record is not None
        and route_record.acquisition_generation_id
        != selected.generation.acquisition_generation_id
        and predecessor_fact.side == fact_record.side
        and predecessor_fact.quantity == fact_record.quantity
        and predecessor_fact.price == fact_record.price
    )
    controller_step = 0 if identical_retired_revision else 1
    if (
        controller.application_generation_id != prepared.application_generation_id
        or controller.execution_profile_id != prepared.execution_profile_id
        or controller.live_acquisition_generation_id
        != selected.generation.acquisition_generation_id
        or controller.aggregate_quantity != execution_transition.position.raw_quantity
        or controller.currentness_head_ordinal
        != selected.controller.currentness_head_ordinal + controller_step
        or controller.controller_version_ordinal
        != selected.controller.controller_version_ordinal + controller_step
    ):
        raise _TechnicalRefusal("broker fact did not advance the exact controller")
    if route_record is None:
        expected_integrity = (
            "NEGATIVE_POSITION_QUARANTINED"
            if controller.aggregate_quantity < 0
            else "UNMATCHED_LINEAGE_QUARANTINED"
        )
        if (
            controller.integrity_state != expected_integrity
            or acquisition_transition is not None
            or effect_record is not None
            or owner_record is not None
            or derivatives
        ):
            raise _TechnicalRefusal(
                "unmatched broker fact did not enter exact quarantine"
            )
        unchanged_generation = _cast(
            _records.AcquisitionGenerationCurrentRecord,
            _required_repository_record(
                "unmatched broker generation current",
                _repository.load_acquisition_generation_current(
                    connection,
                    selected.generation.acquisition_generation_id,
                ),
                _records.AcquisitionGenerationCurrentRecord,
            ),
        )
        if unchanged_generation != selected.generation_current:
            raise _TechnicalRefusal(
                "unmatched broker fact advanced acquisition authority"
            )
        return _complete_claimed_input(
            connection,
            prepared,
            claimed,
            owner_domain="POSITION",
            owner_disposition="RECONCILIATION_REQUIRED",
            successor_context=prepared.context,
            checkpoint_changed=False,
            pending_outbox=None,
            capability=capability,
        )
    if acquisition_transition is None or effect_record is None or owner_record is None:
        raise _TechnicalRefusal("attributed broker fact omitted its owner transition")
    generation_current = _cast(
        _records.AcquisitionGenerationCurrentRecord,
        _required_repository_record(
            "resulting acquisition generation current",
            _repository.load_acquisition_generation_current(
                connection,
                route_record.acquisition_generation_id,
            ),
            _records.AcquisitionGenerationCurrentRecord,
        ),
    )
    if (
        generation_current.scope_id != prepared.scope_id
        or generation_current.current_economics_head_ordinal != fact_ordinal
    ):
        raise _TechnicalRefusal("broker fact generation current is not exact")

    successor_protection = acquisition_transition.protection
    assert successor_protection is not None
    protection_record = _records.ProtectionAuthorityRecord(
        prepared.scope_id,
        (
            "HARD_BAIL"
            if successor_protection.policy is _protection.ProtectionPolicy.HARD_BAIL
            else "NORMAL"
        ),
        selected.stream.stream_generation_id,
        selected.generation.acquisition_generation_id,
        selected.generation.mandate_commitment_sha256,
        selected.stream.source_profile_id,
        selected.stream.session_id,
        selected.stream.sequence_mode,
        controller.currentness_head_ordinal,
        successor_protection.commitment.hex(),
        selected.protection.version_ordinal + 1,
    )
    _advance_protection_record(
        connection,
        selected.protection,
        protection_record,
        capability,
    )
    resulting_authority = _scope_effect_authority(
        selected,
        controller,
        protection_record,
    )
    persisted_effects, persisted_claims = _persist_authority_venue_transitions(
        connection,
        prepared,
        derivatives,
        capability,
        new_effect_authority=resulting_authority,
    )
    if persisted_claims:
        raise _TechnicalRefusal("broker execution derivative emitted a dispatch claim")
    del persisted_effects
    successor_context = _acquisition_successor_context(
        prepared,
        acquisition_transition,
    )
    return _complete_claimed_input(
        connection,
        prepared,
        claimed,
        owner_domain="POSITION",
        owner_disposition=execution_transition.disposition.value,
        successor_context=successor_context,
        checkpoint_changed=True,
        pending_outbox=None,
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
    if type(prepared.operation) is _operations.VenueRecoveryOperation:
        return _execute_venue_operation(
            connection,
            prepared,
            claimed.record,
            capability,
        )
    if type(prepared.operation) is _operations.BrokerExecutionOperation:
        return _execute_broker_execution_operation(
            connection,
            prepared,
            claimed.record,
            capability,
        )
    if type(prepared.operation) is _operations.AuthorityOperation:
        return _execute_authority_operation(
            connection,
            prepared,
            claimed.record,
            capability,
        )
    if type(prepared.operation) in {
        _operations.BeginAcquisitionGenerationOperation,
        _operations.CreateAcquisitionEffectOperation,
        _operations.ClaimAcquisitionEffectOperation,
        _operations.BeginAcquisitionPreemptionOperation,
    }:
        return _execute_acquisition_operation(
            connection,
            prepared,
            claimed.record,
            capability,
        )
    if type(prepared.operation) is _operations.MarketOccurrenceOperation:
        return _execute_market_operation(
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
