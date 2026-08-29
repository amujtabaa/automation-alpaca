"""Pure RED/GREEN controls for the M2 atomic unit-of-work boundary."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from app.execution_core import authority
from app.execution_core import identity
from app.execution_core.persistence import checkpoint_codec
from app.execution_core.persistence import operations
from app.execution_core.persistence import records
from app.execution_core.persistence import unit_of_work
import test_persistence_runtime_checkpoint_pure as checkpoint_fixtures
import test_persistence_input_receipt as input_fixtures


def _payload_equal_manual_contexts() -> tuple[
    object,
    authority.ExecutionAuthorityState,
    authority.ExecutionAuthorityState,
    object,
    object,
]:
    proof, book, clean, owners = checkpoint_fixtures._dormant_projection_inputs()
    _, _, source, _ = checkpoint_fixtures._manual_projection_inputs()
    flatten_id = authority.ManualFlattenId("manual-flatten-AAPL")
    manual = source._manual_by_id.get(authority._manual_key(flatten_id))
    assert manual is not None

    altered = deepcopy(clean)
    object.__setattr__(
        altered,
        "_manual_by_id",
        authority._inserted(
            clean._manual_by_id,
            authority._manual_key(flatten_id),
            manual,
        ),
    )
    clean_payload = checkpoint_codec.encode_runtime_checkpoint(
        checkpoint_codec._project_runtime_checkpoint(proof, book, clean, owners)
    )
    altered_payload = checkpoint_codec.encode_runtime_checkpoint(
        checkpoint_codec._project_runtime_checkpoint(
            proof,
            altered.venue,
            altered,
            owners,
        )
    )
    assert clean_payload == altered_payload
    return proof, clean, altered, owners[0].execution, manual


def _direct_manual_proof(
    state: authority.ExecutionAuthorityState,
    command: object,
    *,
    active_symbol_id: identity.SymbolId | None = None,
    retained_command: authority.BeginManualFlatten | None = None,
    retained_input_bytes: bytes | None = None,
    retained_outcome_bytes: bytes | None = None,
) -> object:
    return authority._m2_authority_manual_observation_from_direct_evidence(
        state,
        command,
        active_symbol_id=active_symbol_id,
        retained_command=retained_command,
        retained_input_bytes=retained_input_bytes,
        retained_outcome_bytes=retained_outcome_bytes,
    )


def test_manual_kernel_ignores_unbound_payload_equal_history() -> None:
    _, clean, altered, execution, manual = _payload_equal_manual_contexts()
    begin = replace(
        manual.command,
        input_id=authority.AuthorityInputId("uow-fresh-manual-begin"),
    )
    advance = authority.AdvanceManualFlatten(
        authority.AuthorityInputId("uow-fresh-manual-advance"),
        manual.command.flatten_id,
    )

    clean_begin = authority._m2_apply_execution_authority_input(
        clean,
        execution,
        begin,
        manual_observation=_direct_manual_proof(clean, begin),
    )
    altered_begin = authority._m2_apply_execution_authority_input(
        altered,
        execution,
        begin,
        manual_observation=_direct_manual_proof(altered, begin),
    )
    assert (clean_begin.disposition, clean_begin.reason) == (
        altered_begin.disposition,
        altered_begin.reason,
    )
    public_clean_begin = authority.apply_execution_authority_input(
        clean,
        execution,
        begin,
    )
    public_altered_begin = authority.apply_execution_authority_input(
        altered,
        execution,
        begin,
    )
    assert (public_clean_begin.disposition, public_clean_begin.reason) == (
        public_altered_begin.disposition,
        public_altered_begin.reason,
    )

    clean_advance = authority._m2_apply_execution_authority_input(
        clean,
        execution,
        advance,
        manual_observation=_direct_manual_proof(clean, advance),
    )
    altered_advance = authority._m2_apply_execution_authority_input(
        altered,
        execution,
        advance,
        manual_observation=_direct_manual_proof(altered, advance),
    )
    assert (clean_advance.disposition, clean_advance.reason) == (
        altered_advance.disposition,
        altered_advance.reason,
    )
    assert clean_advance.disposition is authority.AuthorityDisposition.REFUSED
    public_clean_advance = authority.apply_execution_authority_input(
        clean,
        execution,
        advance,
    )
    public_altered_advance = authority.apply_execution_authority_input(
        altered,
        execution,
        advance,
    )
    assert (public_clean_advance.disposition, public_clean_advance.reason) == (
        public_altered_advance.disposition,
        public_altered_advance.reason,
    )


def test_manual_direct_proof_requires_retained_bytes_and_terminal_outcome() -> None:
    _, clean, _, execution, manual = _payload_equal_manual_contexts()
    begin = replace(
        manual.command,
        input_id=authority.AuthorityInputId("uow-retained-manual-begin"),
    )
    with pytest.raises(ValueError, match="retained evidence"):
        _direct_manual_proof(
            clean,
            begin,
            retained_command=manual.command,
            retained_input_bytes=b"retained-input",
        )

    retained = _direct_manual_proof(
        clean,
        begin,
        retained_command=manual.command,
        retained_input_bytes=b"retained-input",
        retained_outcome_bytes=b"retained-terminal-outcome",
    )
    result = authority._m2_apply_execution_authority_input(
        clean,
        execution,
        begin,
        manual_observation=retained,
    )
    assert result.disposition is authority.AuthorityDisposition.CONFLICT


def test_manual_active_current_direct_proof_matches_public_owner_route() -> None:
    _, _, state, owners = checkpoint_fixtures._manual_projection_inputs()
    flatten_id = authority.ManualFlattenId("manual-flatten-AAPL")
    manual = state._manual_by_id.get(authority._manual_key(flatten_id))
    assert manual is not None
    advance = authority.AdvanceManualFlatten(
        authority.AuthorityInputId("uow-active-manual-advance"),
        flatten_id,
    )
    proof = _direct_manual_proof(
        state,
        advance,
        active_symbol_id=manual.command.symbol_id,
    )

    direct = authority._m2_apply_execution_authority_input(
        state,
        owners[0].execution,
        advance,
        manual_observation=proof,
    )
    public = authority.apply_execution_authority_input(
        state,
        owners[0].execution,
        advance,
    )
    assert (direct.disposition, direct.reason, direct.state) == (
        public.disposition,
        public.reason,
        public.state,
    )


def test_manual_observation_proof_is_owner_issued_and_required() -> None:
    _, clean, _, execution, manual = _payload_equal_manual_contexts()
    begin = replace(
        manual.command,
        input_id=authority.AuthorityInputId("uow-forged-manual-proof"),
    )
    with pytest.raises(TypeError, match="owner-issued"):
        authority._M2AuthorityManualObservationProof()
    forged = object.__new__(authority._M2AuthorityManualObservationProof)
    with pytest.raises(ValueError, match="observation proof"):
        authority._m2_apply_execution_authority_input(
            clean,
            execution,
            begin,
            manual_observation=forged,
        )


def test_query_kernel_ignores_omitted_payload_equal_history() -> None:
    _, _, clean, owners = checkpoint_fixtures._dormant_projection_inputs()
    retained = authority.ClaimBrokerQuery(
        identity.AuthorityInputId("retained-query-input"),
        identity.QueryClaimId("query-identity"),
        identity.SymbolId("AAPL"),
        authority.AuthorityQueryKind.QUERY,
    )
    command = replace(
        retained,
        input_id=identity.AuthorityInputId("fresh-query-input"),
    )
    altered = deepcopy(clean)
    object.__setattr__(
        altered,
        "_query_by_id",
        authority._inserted(
            clean._query_by_id,
            authority._query_key(retained.query_claim_id),
            retained,
        ),
    )
    object.__setattr__(
        altered,
        "_input_by_id",
        authority._inserted(
            clean._input_by_id,
            authority._input_key(retained.input_id),
            retained,
        ),
    )

    clean_proof = authority._m2_authority_query_observation_from_direct_evidence(
        clean,
        command,
        retained_command=None,
        retained_input_bytes=None,
        retained_outcome_bytes=None,
    )
    altered_absence = authority._m2_authority_query_observation_from_direct_evidence(
        altered,
        command,
        retained_command=None,
        retained_input_bytes=None,
        retained_outcome_bytes=None,
    )
    clean_result = authority._m2_apply_execution_authority_input(
        clean,
        owners[0].execution,
        command,
        manual_observation=None,
        query_observation=clean_proof,
    )
    altered_result = authority._m2_apply_execution_authority_input(
        altered,
        owners[0].execution,
        command,
        manual_observation=None,
        query_observation=altered_absence,
    )
    assert (clean_result.disposition, clean_result.reason) == (
        altered_result.disposition,
        altered_result.reason,
    )

    retained_proof = authority._m2_authority_query_observation_from_direct_evidence(
        altered,
        command,
        retained_command=retained,
        retained_input_bytes=b"retained-query-input",
        retained_outcome_bytes=b"retained-query-outcome",
    )
    direct_retained = authority._m2_apply_execution_authority_input(
        altered,
        owners[0].execution,
        command,
        manual_observation=None,
        query_observation=retained_proof,
    )
    public_retained = authority.apply_execution_authority_input(
        altered,
        owners[0].execution,
        command,
    )
    assert direct_retained.disposition is authority.AuthorityDisposition.CONFLICT
    assert public_retained.disposition is authority.AuthorityDisposition.CONFLICT


class _TransactionConnection:
    def __init__(
        self,
        *,
        commit_error: Exception | None = None,
        rollback_error: Exception | None = None,
    ) -> None:
        self.in_transaction = False
        self.commit_error = commit_error
        self.rollback_error = rollback_error
        self.events: list[str] = []

    def execute(self, sql: str, parameters: object = ()) -> object:
        del parameters
        self.events.append(sql)
        if sql == "BEGIN IMMEDIATE":
            assert not self.in_transaction
            self.in_transaction = True
        elif sql == "COMMIT":
            assert self.in_transaction
            if self.commit_error is not None:
                raise self.commit_error
            self.in_transaction = False
        elif sql == "ROLLBACK":
            assert self.in_transaction
            if self.rollback_error is not None:
                raise self.rollback_error
            self.in_transaction = False
        else:
            raise AssertionError(f"unexpected transaction SQL: {sql}")
        return object()

    def close(self) -> None:
        self.events.append("CLOSE")


def _uow_context() -> unit_of_work.UnitOfWorkContext:
    proof, book, state, owners = checkpoint_fixtures._dormant_projection_inputs()
    expected = records.KernelCheckpointRecord(
        proof.request.application_generation_id,
        0,
        "0" * 64,
        1,
    )
    return unit_of_work.UnitOfWorkContext(
        expected,
        book,
        state,
        tuple(
            (
                owner.scope_id,
                owner.acquisition,
                owner.execution,
                owner.protection,
            )
            for owner in owners
        ),
    )


def _patch_prepared_path(
    monkeypatch: pytest.MonkeyPatch,
    body: object,
) -> None:
    monkeypatch.setattr(unit_of_work, "_canonicalize_operation", lambda value: value)
    monkeypatch.setattr(
        unit_of_work,
        "_prepare_transaction",
        lambda connection, operation, context: _prepared_primary_claim(),
    )
    monkeypatch.setattr(unit_of_work, "_execute_prepared", body)


def _refused_result() -> unit_of_work.UnitOfWorkResult:
    return unit_of_work.UnitOfWorkResult(
        unit_of_work.UnitOfWorkDisposition.REFUSED,
        None,
        None,
        None,
        None,
    )


def _committed_result(
    context: unit_of_work.UnitOfWorkContext,
) -> unit_of_work.UnitOfWorkResult:
    return unit_of_work.UnitOfWorkResult(
        unit_of_work.UnitOfWorkDisposition.COMMITTED,
        "AUTHORITY",
        "APPLIED",
        context,
        None,
    )


def test_unit_of_work_exports_are_exact_and_invalid_input_never_begins() -> None:
    assert set(unit_of_work.__all__) == {
        "PostCommitEffectEligibility",
        "UnitOfWorkContext",
        "UnitOfWorkDisposition",
        "UnitOfWorkResult",
        "execute_unit_of_work",
    }
    connection = _TransactionConnection()
    result = unit_of_work.execute_unit_of_work(connection, object(), _uow_context())
    assert result.disposition is unit_of_work.UnitOfWorkDisposition.REFUSED
    assert connection.events == []


def test_body_fault_retires_lease_then_rolls_back_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection()
    retained_capability: list[object] = []

    def fail_body(
        body_connection: object,
        prepared: object,
        capability: object,
    ) -> object:
        del body_connection, prepared
        retained_capability.append(capability)
        raise RuntimeError("injected body fault")

    _patch_prepared_path(monkeypatch, fail_body)
    with pytest.raises(RuntimeError, match="injected body fault"):
        unit_of_work.execute_unit_of_work(connection, object(), _uow_context())
    assert connection.events == ["BEGIN IMMEDIATE", "ROLLBACK"]
    with pytest.raises(ValueError, match="not current"):
        unit_of_work._repository._require_write_capability(
            connection,
            retained_capability[0],
        )


def test_noncommitting_decision_retires_lease_and_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection()

    def refuse(
        body_connection: object,
        prepared: object,
        capability: object,
    ) -> unit_of_work._TransactionDecision:
        del body_connection, prepared, capability
        return unit_of_work._TransactionDecision(False, _refused_result(), None)

    _patch_prepared_path(monkeypatch, refuse)
    result = unit_of_work.execute_unit_of_work(connection, object(), _uow_context())
    assert result.disposition is unit_of_work.UnitOfWorkDisposition.REFUSED
    assert connection.events == ["BEGIN IMMEDIATE", "ROLLBACK"]


def test_commit_mints_effect_eligibility_only_after_normal_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection()
    context = _uow_context()

    def commit(
        body_connection: object,
        prepared: object,
        capability: object,
    ) -> unit_of_work._TransactionDecision:
        del body_connection, prepared, capability
        assert connection.events == ["BEGIN IMMEDIATE"]
        return unit_of_work._TransactionDecision(
            True,
            _committed_result(context),
            unit_of_work._PostCommitEffectCandidate(7, 11, 13, "a" * 64),
        )

    _patch_prepared_path(monkeypatch, commit)
    result = unit_of_work.execute_unit_of_work(connection, object(), context)
    assert connection.events == ["BEGIN IMMEDIATE", "COMMIT"]
    assert result.effect_eligibility == unit_of_work.PostCommitEffectEligibility(
        7,
        11,
        13,
        "a" * 64,
    )


def test_commit_ambiguity_never_rolls_back_or_mints_eligibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection(commit_error=RuntimeError("ambiguous commit"))
    context = _uow_context()

    def commit(
        body_connection: object,
        prepared: object,
        capability: object,
    ) -> unit_of_work._TransactionDecision:
        del body_connection, prepared, capability
        return unit_of_work._TransactionDecision(
            True,
            _committed_result(context),
            unit_of_work._PostCommitEffectCandidate(7, 11, 13, "a" * 64),
        )

    _patch_prepared_path(monkeypatch, commit)
    result = unit_of_work.execute_unit_of_work(connection, object(), context)
    assert result.disposition is unit_of_work.UnitOfWorkDisposition.RECONCILIATION_ONLY
    assert result.effect_eligibility is None
    assert connection.events == ["BEGIN IMMEDIATE", "COMMIT", "CLOSE"]


def test_rollback_ambiguity_propagates_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection(
        rollback_error=RuntimeError("ambiguous rollback")
    )

    def refuse(
        body_connection: object,
        prepared: object,
        capability: object,
    ) -> unit_of_work._TransactionDecision:
        del body_connection, prepared, capability
        return unit_of_work._TransactionDecision(False, _refused_result(), None)

    _patch_prepared_path(monkeypatch, refuse)
    with pytest.raises(RuntimeError, match="ambiguous rollback"):
        unit_of_work.execute_unit_of_work(connection, object(), _uow_context())
    assert connection.events == ["BEGIN IMMEDIATE", "ROLLBACK"]


class _OrdinalCursor:
    def __init__(self, ordinal: int) -> None:
        self.ordinal = ordinal

    def fetchone(self) -> tuple[int]:
        return (self.ordinal,)


class _PrimaryClaimConnection:
    def __init__(self, ordinal: int = 1) -> None:
        self.ordinal = ordinal
        self.statements: list[str] = []

    def execute(self, sql: str, parameters: object = ()) -> _OrdinalCursor:
        del parameters
        self.statements.append(sql)
        assert sql == (
            "SELECT COALESCE(MAX(created_ordinal), 0) + 1 FROM durable_input"
        )
        return _OrdinalCursor(self.ordinal)


class _CompletionConnection:
    def __init__(self, receipt_ordinal: int = 4) -> None:
        self.receipt_ordinal = receipt_ordinal
        self.statements: list[str] = []

    def execute(self, sql: str, parameters: object = ()) -> _OrdinalCursor:
        del parameters
        self.statements.append(sql)
        assert sql == (
            "SELECT COALESCE(MAX(receipt_ordinal), 0) + 1 FROM decision_receipt"
        )
        return _OrdinalCursor(self.receipt_ordinal)


def _prepared_primary_claim() -> unit_of_work._PreparedOperation:
    operation = input_fixtures._passive_venue_operation()
    payload = operations.encode_m2_operation(operation)
    (
        domain,
        application_generation_id,
        execution_profile_id,
        scope_id,
        session_id,
        acquisition_generation_id,
        market_source_profile_id,
        stream_generation_id,
        input_identity_sha256,
    ) = operations._derive_m2_durable_input_projection(operation)
    return unit_of_work._PreparedOperation(
        operation,
        _uow_context(),
        payload,
        domain,
        application_generation_id,
        execution_profile_id,
        scope_id,
        session_id,
        acquisition_generation_id,
        market_source_profile_id,
        stream_generation_id,
        input_identity_sha256,
        object(),
        object(),
    )


def test_primary_claim_builds_exact_canonical_record_at_next_ordinal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _PrimaryClaimConnection(9)
    captured: list[records.DurableInputRecord] = []

    def claim(
        claim_connection: object,
        record: records.DurableInputRecord,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[operations.InputDedupeFact]:
        del capability
        assert claim_connection is connection
        captured.append(record)
        return records.RepositoryOutcome(
            records.RepositoryOutcomeKind.APPLIED,
            operations.InputDedupeFact(
                operations.InputDedupeKind.UNSEEN,
                record.input_domain.value,
                record.input_identity_sha256,
                record.payload_sha256,
                None,
                (),
            ),
        )

    monkeypatch.setattr(unit_of_work._repository, "claim_durable_input", claim)
    result = unit_of_work._claim_primary_input(
        connection,
        _prepared_primary_claim(),
        object(),
    )

    assert type(result) is unit_of_work._ClaimedPrimaryInput
    assert result.record is captured[0]
    assert result.record.created_ordinal == 9
    assert result.record.technical_state == "CLAIMED"
    assert result.record.canonical_payload_bytes == operations.encode_m2_operation(
        result.operation
    )


@pytest.mark.parametrize(
    ("repository_kind", "dedupe_kind", "expected_disposition"),
    (
        (
            records.RepositoryOutcomeKind.FOUND,
            operations.InputDedupeKind.EXACT_REPLAY,
            unit_of_work.UnitOfWorkDisposition.EXACT_REPLAY,
        ),
        (
            records.RepositoryOutcomeKind.CONFLICT,
            operations.InputDedupeKind.IDENTITY_CONFLICT,
            unit_of_work.UnitOfWorkDisposition.CONFLICT,
        ),
    ),
)
def test_primary_replay_and_conflict_short_circuit_before_owner_reduction(
    monkeypatch: pytest.MonkeyPatch,
    repository_kind: records.RepositoryOutcomeKind,
    dedupe_kind: operations.InputDedupeKind,
    expected_disposition: unit_of_work.UnitOfWorkDisposition,
) -> None:
    prepared = _prepared_primary_claim()
    connection = _PrimaryClaimConnection()

    def claim(
        claim_connection: object,
        record: records.DurableInputRecord,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[operations.InputDedupeFact]:
        del claim_connection, capability
        return records.RepositoryOutcome(
            repository_kind,
            operations.InputDedupeFact(
                dedupe_kind,
                record.input_domain.value,
                record.input_identity_sha256,
                record.payload_sha256,
                "ab" * 32
                if dedupe_kind is operations.InputDedupeKind.EXACT_REPLAY
                else None,
                (),
            ),
        )

    monkeypatch.setattr(unit_of_work._repository, "claim_durable_input", claim)
    result = unit_of_work._claim_primary_input(connection, prepared, object())

    assert type(result) is unit_of_work._TransactionDecision
    assert result.commit is False
    assert result.result.disposition is expected_disposition
    assert result.pending_effect is None


def test_committed_no_change_decision_stores_coherent_receipt_outcome_then_finalizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepared_primary_claim()
    claimed = records.DurableInputRecord(
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
        unit_of_work._hashlib.sha256(prepared.canonical_payload_bytes).hexdigest(),
        "CLAIMED",
        3,
    )
    connection = _CompletionConnection()
    stored: list[object] = []

    def applied(
        target_connection: object,
        record: object,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[object]:
        del capability
        assert target_connection is connection
        stored.append(record)
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    monkeypatch.setattr(unit_of_work._repository, "store_decision_receipt", applied)
    monkeypatch.setattr(
        unit_of_work._repository,
        "store_durable_input_outcome",
        applied,
    )
    monkeypatch.setattr(unit_of_work._repository, "finalize_durable_input", applied)

    decision = unit_of_work._complete_claimed_input(
        connection,
        prepared,
        claimed,
        owner_domain="VENUE_RECOVERY",
        owner_disposition="REFUSED",
        successor_context=prepared.context,
        checkpoint_changed=False,
        pending_effect=None,
        capability=object(),
    )

    assert decision.commit is True
    assert decision.result.disposition is unit_of_work.UnitOfWorkDisposition.COMMITTED
    assert decision.result.owner_domain == "VENUE_RECOVERY"
    assert decision.result.owner_disposition == "REFUSED"
    assert decision.result.successor_context is prepared.context
    assert decision.pending_effect is None
    assert tuple(type(item) for item in stored) == (
        records.DecisionReceiptRecord,
        records.DurableInputOutcomeRecord,
        records.DurableInputRecord,
    )
    receipt, outcome, finalized = stored
    assert type(receipt) is records.DecisionReceiptRecord
    assert type(outcome) is records.DurableInputOutcomeRecord
    assert type(finalized) is records.DurableInputRecord
    assert receipt.receipt_ordinal == 4
    assert receipt.checkpoint_payload_sha256 is None
    assert outcome.receipt_sha256 == receipt.receipt_sha256
    assert outcome.result_sha256 == receipt.result_sha256
    assert finalized.technical_state == "TERMINAL"


def test_authority_engage_kill_route_uses_shared_kernel_and_common_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepared_primary_claim()
    command = authority.EngageKill(
        authority.AuthorityInputId("uow-engage-kill"),
        authority.ActorId("operator"),
        "operator kill",
        authority.EvidenceReference("evidence"),
    )
    scope_id = prepared.context.scope_owners[0][0]
    operation = operations.AuthorityOperation(
        operations.ExecutionOperationCoordinates(
            prepared.application_generation_id,
            prepared.execution_profile_id,
            scope_id,
        ),
        command,
    )
    payload = operations.encode_m2_operation(operation)
    projection = operations._derive_m2_durable_input_projection(operation)
    prepared = replace(
        prepared,
        operation=operation,
        canonical_payload_bytes=payload,
        input_domain=operations.OperationDomain.AUTHORITY,
        scope_id=scope_id,
        input_identity_sha256=projection[-1],
    )
    owner_called: list[object] = []
    completed: list[tuple[str, str, bool]] = []

    def owner(
        state: authority.ExecutionAuthorityState,
        execution: object,
        item: object,
        *,
        manual_observation: object,
        query_observation: object,
    ) -> authority.ExecutionAuthorityTransition:
        del execution
        assert state is prepared.context.authority
        assert item is command
        assert manual_observation is None
        assert query_observation is None
        owner_called.append(item)
        return authority.ExecutionAuthorityTransition(
            state,
            authority.AuthorityDisposition.EXACT_REPLAY,
            None,
            (),
            None,
            (),
            None,
            None,
        )

    def complete(
        connection: object,
        prepared_operation: object,
        claimed_record: object,
        *,
        owner_domain: str,
        owner_disposition: str,
        successor_context: object,
        checkpoint_changed: bool,
        pending_effect: object,
        capability: object,
    ) -> unit_of_work._TransactionDecision:
        del connection, prepared_operation, claimed_record, successor_context
        del pending_effect, capability
        completed.append((owner_domain, owner_disposition, checkpoint_changed))
        return unit_of_work._TransactionDecision(
            True,
            _committed_result(prepared.context),
            None,
        )

    monkeypatch.setattr(
        unit_of_work._authority,
        "_m2_apply_execution_authority_input",
        owner,
    )
    monkeypatch.setattr(unit_of_work, "_complete_claimed_input", complete)

    result = unit_of_work._execute_authority_operation(
        object(),
        prepared,
        records.DurableInputRecord(
            prepared.application_generation_id,
            prepared.execution_profile_id,
            prepared.scope_id,
            prepared.input_domain,
            None,
            None,
            None,
            None,
            prepared.input_identity_sha256,
            1,
            payload,
            unit_of_work._hashlib.sha256(payload).hexdigest(),
            "CLAIMED",
            1,
        ),
        object(),
    )

    assert result.commit is True
    assert owner_called == [command]
    assert completed == [("AUTHORITY", "EXACT_REPLAY", False)]


def test_bounded_change_detection_ignores_omitted_owner_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepared_primary_claim()
    successor_authority = deepcopy(prepared.context.authority)
    successor = unit_of_work.UnitOfWorkContext(
        prepared.context.expected_checkpoint,
        successor_authority.venue,
        successor_authority,
        prepared.context.scope_owners,
    )
    projected: list[object] = []

    class _Envelope:
        canonical_payload_bytes = b"same-bounded-payload"

    monkeypatch.setattr(
        unit_of_work._checkpoint_codec,
        "_project_runtime_checkpoint",
        lambda proof, venue, authority_state, owners: (
            projected.append((proof, venue, authority_state, owners)) or _Envelope()
        ),
    )
    prepared = replace(prepared, authenticated_current=_Envelope())

    assert unit_of_work._bounded_context_changed(prepared, successor) is False
    assert len(projected) == 1


def test_authority_query_applied_claims_semantic_key_before_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepared_primary_claim()
    scope_id, _, execution, _ = prepared.context.scope_owners[0]
    command = authority.ClaimBrokerQuery(
        identity.AuthorityInputId("uow-query-input"),
        identity.QueryClaimId("uow-query-claim"),
        execution.position.scope.symbol_id,
        authority.AuthorityQueryKind.QUERY,
    )
    operation = operations.AuthorityOperation(
        operations.ExecutionOperationCoordinates(
            prepared.application_generation_id,
            prepared.execution_profile_id,
            scope_id,
        ),
        command,
    )
    payload = operations.encode_m2_operation(operation)
    projection = operations._derive_m2_durable_input_projection(operation)
    prepared = replace(
        prepared,
        operation=operation,
        canonical_payload_bytes=payload,
        input_domain=operations.OperationDomain.AUTHORITY,
        scope_id=scope_id,
        input_identity_sha256=projection[-1],
    )
    claimed = records.DurableInputRecord(
        prepared.application_generation_id,
        prepared.execution_profile_id,
        prepared.scope_id,
        prepared.input_domain,
        None,
        None,
        None,
        None,
        prepared.input_identity_sha256,
        1,
        payload,
        unit_of_work._hashlib.sha256(payload).hexdigest(),
        "CLAIMED",
        1,
    )
    successor_state = deepcopy(prepared.context.authority)
    observation = object()
    stored: list[records.DurableInputSemanticKeyRecord] = []
    completed: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(
        unit_of_work,
        "_authority_query_observation",
        lambda connection, prepared_operation, query: observation,
    )

    def owner(
        state: authority.ExecutionAuthorityState,
        execution_state: object,
        item: object,
        *,
        manual_observation: object,
        query_observation: object,
    ) -> authority.ExecutionAuthorityTransition:
        del state, execution_state, manual_observation
        assert item is command
        assert query_observation is observation
        return authority.ExecutionAuthorityTransition(
            successor_state,
            authority.AuthorityDisposition.APPLIED,
            None,
            (),
            authority._FreshQueryClaim(
                command.query_claim_id,
                command.symbol_id,
                command.kind,
            ),
            (),
            None,
            None,
        )

    def store_key(
        connection: object,
        record: records.DurableInputSemanticKeyRecord,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[object]:
        del connection, capability
        stored.append(record)
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    def complete(
        connection: object,
        prepared_operation: object,
        claimed_record: object,
        *,
        owner_domain: str,
        owner_disposition: str,
        successor_context: object,
        checkpoint_changed: bool,
        pending_effect: object,
        capability: object,
    ) -> unit_of_work._TransactionDecision:
        del connection, prepared_operation, claimed_record, successor_context
        del pending_effect, capability
        completed.append((owner_domain, owner_disposition, checkpoint_changed))
        return unit_of_work._TransactionDecision(
            True,
            _committed_result(prepared.context),
            None,
        )

    monkeypatch.setattr(
        unit_of_work._authority,
        "_m2_apply_execution_authority_input",
        owner,
    )
    monkeypatch.setattr(unit_of_work, "_bounded_context_changed", lambda *args: True)
    monkeypatch.setattr(
        unit_of_work,
        "_next_semantic_key_created_ordinal",
        lambda connection: 7,
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "store_durable_input_semantic_key",
        store_key,
    )
    monkeypatch.setattr(unit_of_work, "_complete_claimed_input", complete)

    unit_of_work._execute_authority_operation(
        object(),
        prepared,
        claimed,
        object(),
    )

    assert len(stored) == 1
    assert (
        stored[0].key_kind is operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1
    )
    assert stored[0].input_identity_sha256 == claimed.input_identity_sha256
    assert stored[0].created_ordinal == 7
    assert completed == [("AUTHORITY", "APPLIED", True)]


def test_authority_manual_begin_uses_direct_proof_and_claims_semantic_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepared_primary_claim()
    scope_id, _, execution, _ = prepared.context.scope_owners[0]
    command = authority.BeginManualFlatten(
        identity.AuthorityInputId("uow-manual-input"),
        identity.ManualFlattenId("uow-manual-flatten"),
        identity.SessionId("uow-manual-session"),
        execution.position.scope.symbol_id,
        identity.ActorId("operator"),
        "bounded manual flatten",
        identity.EvidenceReference("manual-evidence"),
        None,
    )
    operation = operations.AuthorityOperation(
        operations.ExecutionOperationCoordinates(
            prepared.application_generation_id,
            prepared.execution_profile_id,
            scope_id,
        ),
        command,
    )
    payload = operations.encode_m2_operation(operation)
    projection = operations._derive_m2_durable_input_projection(operation)
    prepared = replace(
        prepared,
        operation=operation,
        canonical_payload_bytes=payload,
        input_domain=operations.OperationDomain.AUTHORITY,
        scope_id=scope_id,
        input_identity_sha256=projection[-1],
    )
    claimed = records.DurableInputRecord(
        prepared.application_generation_id,
        prepared.execution_profile_id,
        prepared.scope_id,
        prepared.input_domain,
        None,
        None,
        None,
        None,
        prepared.input_identity_sha256,
        1,
        payload,
        unit_of_work._hashlib.sha256(payload).hexdigest(),
        "CLAIMED",
        1,
    )
    observation = object()
    owner_calls: list[tuple[object, object]] = []
    semantic_calls: list[tuple[object, object]] = []

    monkeypatch.setattr(
        unit_of_work,
        "_authority_manual_observation",
        lambda connection, prepared_operation, item: observation,
    )

    def owner(
        state: authority.ExecutionAuthorityState,
        execution_state: object,
        item: object,
        *,
        manual_observation: object,
        query_observation: object,
    ) -> authority.ExecutionAuthorityTransition:
        del state, execution_state
        owner_calls.append((manual_observation, query_observation))
        assert item is command
        return authority.ExecutionAuthorityTransition(
            prepared.context.authority,
            authority.AuthorityDisposition.APPLIED,
            None,
            (),
            None,
            (),
            None,
            None,
        )

    def store_manual_key(
        connection: object,
        prepared_operation: object,
        claimed_record: object,
        item: object,
        capability: object,
    ) -> None:
        del connection, prepared_operation, claimed_record
        semantic_calls.append((item, capability))

    monkeypatch.setattr(
        unit_of_work._authority,
        "_m2_apply_execution_authority_input",
        owner,
    )
    monkeypatch.setattr(
        unit_of_work,
        "_store_authority_manual_semantic_key",
        store_manual_key,
    )
    monkeypatch.setattr(
        unit_of_work,
        "_complete_claimed_input",
        lambda *args, **kwargs: unit_of_work._TransactionDecision(
            True,
            _committed_result(prepared.context),
            None,
        ),
    )

    capability = object()
    decision = unit_of_work._execute_authority_operation(
        object(),
        prepared,
        claimed,
        capability,
    )

    assert decision.commit is True
    assert owner_calls == [(observation, None)]
    assert semantic_calls == [(command, capability)]
