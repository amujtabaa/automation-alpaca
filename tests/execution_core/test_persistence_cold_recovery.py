from __future__ import annotations

import ast
from dataclasses import replace
import inspect
from types import SimpleNamespace

import pytest

from app.execution_core import acquisition
from app.execution_core import identity
from app.execution_core import protection
from app.execution_core import values
from app.execution_core import venue
from app.execution_core.persistence import checkpoint_codec
from app.execution_core.persistence import market_recovery
from app.execution_core.persistence import operations
from app.execution_core.persistence import owner_lock
from app.execution_core.persistence import records
from app.execution_core.persistence import startup
from app.execution_core.persistence import unit_of_work
from tests.execution_core import test_acquisition as acquisition_fixtures
from tests.execution_core import test_protection as protection_fixtures
import test_persistence_startup_hydration as hydration_fixtures


class _Connection:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.in_transaction = False
        self.closed = False

    def close(self) -> None:
        self.events.append("close")
        self.closed = True


def test_cold_context_loader_uses_only_bounded_checkpoint_routes() -> None:
    tree = ast.parse(inspect.getsource(unit_of_work._m2_load_compact_context))
    repository_calls = tuple(
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "_repository"
    )
    assert repository_calls == (
        "load_runtime_checkpoint",
        "select_runtime_checkpoint",
    )


class _Datastore(startup._StartupDatastorePort):
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.connection = _Connection(events)

    def open(self) -> _Connection:
        self.events.append("open")
        return self.connection


class _FailingDatastore(startup._StartupDatastorePort):
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def open(self) -> _Connection:
        self.events.append("open")
        raise OSError("injected datastore refusal")


class _Owner(owner_lock.OwnerLockPort):
    def __init__(self, events: list[str], *, lose_on_check: int | None = None) -> None:
        super().__init__()
        self.events = events
        self.lose_on_check = lose_on_check
        self.checks = 0
        self.released = False

    def acquire(self) -> owner_lock.OwnerLeaseEvidence:
        self.events.append("acquire")
        return self._issue("cold-owner")

    def is_current(self, evidence: owner_lock.OwnerLeaseEvidence) -> bool:
        self.checks += 1
        self.events.append(f"owner-current-{self.checks}")
        return bool(
            self._recognizes(evidence)
            and not self.released
            and self.lose_on_check != self.checks
        )

    def release(self, evidence: owner_lock.OwnerLeaseEvidence) -> None:
        self.events.append("release")
        if self._recognizes(evidence):
            self.released = True


class _NoEffectQueries(market_recovery.EffectQueryPort):
    def query(
        self, request: market_recovery.EffectQueryRequest
    ) -> market_recovery.EffectQueryResult:
        del request
        raise AssertionError("effect query was not admitted")


class _NoMarketSource(market_recovery.MarketSourcePort):
    def subscribe(
        self, request: market_recovery.MarketSubscriptionRequest
    ) -> market_recovery.MarketSubscriptionEvidence | None:
        del request
        raise AssertionError("market source was not admitted")


class _UnsupportedMarketSource(market_recovery.MarketSourcePort):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[market_recovery.MarketSubscriptionRequest] = []

    def subscribe(
        self, request: market_recovery.MarketSubscriptionRequest
    ) -> market_recovery.MarketSubscriptionEvidence | None:
        self.requests.append(request)
        return None


def _dormant_context() -> tuple[
    unit_of_work.UnitOfWorkContext,
    records.RuntimeCheckpointSelectionProof,
]:
    loaded, proof = hydration_fixtures._loaded_dormant_checkpoint()
    restored = checkpoint_codec._restore_compact_runtime_checkpoint(loaded, proof)
    head = records.KernelCheckpointRecord(
        loaded.application_generation_id,
        loaded.currentness_head_ordinal,
        loaded.payload_sha256,
        loaded.checkpoint_version_ordinal,
    )
    return (
        unit_of_work.UnitOfWorkContext(
            head,
            restored.venue,
            restored.authority,
            tuple(
                (
                    owner.scope_id,
                    owner.acquisition,
                    owner.execution,
                    owner.protection,
                )
                for owner in restored.scope_owners
            ),
        ),
        proof,
    )


def _request(proof: records.RuntimeCheckpointSelectionProof) -> startup.StartupRequest:
    return startup.StartupRequest(
        proof.request.application_generation_id,
        proof.request.execution_profile_id,
        proof.request.market_source_profile_id,
    )


def _patch_recovery_boundary(
    monkeypatch: pytest.MonkeyPatch,
    holder: dict[str, object],
    proof: records.RuntimeCheckpointSelectionProof,
    events: list[str],
) -> None:
    def cutover(*args: object) -> unit_of_work._ColdCompactCutoverResult:
        del args
        events.append("cutover")
        context = holder["context"]
        assert type(context) is unit_of_work.UnitOfWorkContext
        return unit_of_work._ColdCompactCutoverResult(
            unit_of_work.UnitOfWorkDisposition.EXACT_REPLAY,
            context,
            proof,
        )

    def reread(*args: object) -> tuple[object, object]:
        del args
        events.append("reread")
        return holder["context"], proof

    monkeypatch.setattr(unit_of_work, "_m2_cold_compact_cutover", cutover)
    monkeypatch.setattr(unit_of_work, "_m2_reread_cold_context", reread)


def test_owner_lock_precedes_datastore_and_dormant_success_retains_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, proof = _dormant_context()
    events: list[str] = []
    holder: dict[str, object] = {"context": context}
    _patch_recovery_boundary(monkeypatch, holder, proof, events)
    owner = _Owner(events)
    datastore = _Datastore(events)

    result = startup.start_startup(
        _request(proof),
        owner_lock=owner,
        datastore=datastore,
        effect_queries=_NoEffectQueries(),
        market_source=_NoMarketSource(),
    )

    assert result.disposition is startup.StartupDisposition.SERVING
    assert result.successor_context is context
    assert result.owner_lease is not None
    assert events.index("acquire") < events.index("open") < events.index("cutover")
    assert events.count("cutover") == 2
    assert events[-1].startswith("owner-current-")
    assert datastore.connection.closed
    assert not owner.released


def test_owner_loss_after_open_stops_before_database_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, proof = _dormant_context()
    events: list[str] = []
    holder: dict[str, object] = {"context": context}
    _patch_recovery_boundary(monkeypatch, holder, proof, events)
    owner = _Owner(events, lose_on_check=3)
    datastore = _Datastore(events)

    result = startup.start_startup(
        _request(proof),
        owner_lock=owner,
        datastore=datastore,
        effect_queries=_NoEffectQueries(),
        market_source=_NoMarketSource(),
    )

    assert result.refusal_code is startup.StartupRefusalCode.OWNER_LOST
    assert "cutover" not in events
    assert datastore.connection.closed
    assert owner.released


def test_initial_cutover_ambiguity_is_datastore_failure_before_query_or_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _context, proof = _dormant_context()
    events: list[str] = []

    def ambiguous(*args: object) -> unit_of_work._ColdCompactCutoverResult:
        del args
        events.append("cutover")
        return unit_of_work._ColdCompactCutoverResult(
            unit_of_work.UnitOfWorkDisposition.RECONCILIATION_ONLY,
            None,
            None,
            unit_of_work._ColdCompactCutoverFailure.COMMIT_AMBIGUITY,
        )

    monkeypatch.setattr(unit_of_work, "_m2_cold_compact_cutover", ambiguous)
    owner = _Owner(events)
    datastore = _Datastore(events)

    result = startup.start_startup(
        _request(proof),
        owner_lock=owner,
        datastore=datastore,
        effect_queries=_NoEffectQueries(),
        market_source=_NoMarketSource(),
    )

    assert result.refusal_code is startup.StartupRefusalCode.DATASTORE_INTEGRITY
    assert events.count("cutover") == 1
    assert owner.released


def test_datastore_open_failure_is_classified_without_query_or_source() -> None:
    _context, proof = _dormant_context()
    events: list[str] = []
    owner = _Owner(events)

    result = startup.start_startup(
        _request(proof),
        owner_lock=owner,
        datastore=_FailingDatastore(events),
        effect_queries=_NoEffectQueries(),
        market_source=_NoMarketSource(),
    )

    assert result.refusal_code is startup.StartupRefusalCode.DATASTORE_INTEGRITY
    assert events.index("acquire") < events.index("open") < events.index("release")
    assert owner.released


@pytest.mark.parametrize(
    ("failure", "expected"),
    (
        (
            unit_of_work._ColdCompactCutoverFailure.INPUT,
            startup.StartupRefusalCode.INTERNAL_INTEGRITY,
        ),
        (
            unit_of_work._ColdCompactCutoverFailure.CURRENT_PROOF,
            startup.StartupRefusalCode.CURRENT_PROOF_FAILURE,
        ),
        (
            unit_of_work._ColdCompactCutoverFailure.INVALIDATION,
            startup.StartupRefusalCode.INVALIDATION_FAILURE,
        ),
        (
            unit_of_work._ColdCompactCutoverFailure.DATASTORE,
            startup.StartupRefusalCode.DATASTORE_INTEGRITY,
        ),
        (
            unit_of_work._ColdCompactCutoverFailure.COMMIT_AMBIGUITY,
            startup.StartupRefusalCode.DATASTORE_INTEGRITY,
        ),
    ),
)
def test_cutover_failure_categories_map_to_exact_startup_refusal(
    failure: unit_of_work._ColdCompactCutoverFailure,
    expected: startup.StartupRefusalCode,
) -> None:
    result = unit_of_work._ColdCompactCutoverResult(
        unit_of_work.UnitOfWorkDisposition.REFUSED,
        None,
        None,
        failure,
    )

    assert startup._cutover_refusal_code(result) is expected


def _active_context() -> tuple[
    unit_of_work.UnitOfWorkContext,
    protection.PositionProtectionState,
    object,
]:
    _authority_module, _scope, claimed, filled = (
        acquisition_fixtures._r8_current_generation_fill_transition(
            acknowledged=True,
            prefill_needs_review=False,
        )
    )
    applied = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert applied.protection is not None
    dormant, _proof = _dormant_context()
    context = unit_of_work.UnitOfWorkContext(
        dormant.expected_checkpoint,
        applied.venue,
        applied.authority,
        ((1, applied.state, applied.execution, applied.protection),),
    )
    generation_id = identity.AcquisitionGenerationId("ab" * 32)
    policy = applied.protection.mandate.evidence_policy
    stream = records.MarketStreamAuthorityRecord(
        policy.stream_generation,
        1,
        applied.venue.scope.generation,
        generation_id,
        "c" * 64,
        "b" * 64,
        applied.protection.mandate.session_id,
        policy.sequence_mode.value,
    )
    cursor = records.MarketCursorRecord(
        stream.stream_generation_id,
        1,
        stream.application_generation_id,
        stream.acquisition_generation_id,
        stream.generation_mandate_commitment_sha256,
        stream.source_profile_id,
        stream.session_id,
        stream.sequence_mode,
        0,
        0,
    )
    return context, applied.protection, SimpleNamespace(stream=stream, cursor=cursor)


class _MarketSource(market_recovery.MarketSourcePort):
    def __init__(
        self,
        state: protection.PositionProtectionState,
        *,
        fence_ordinal: int,
        current_answers: tuple[bool, ...] = (True, True, True),
        variant: str | None = None,
    ) -> None:
        super().__init__()
        self.state = state
        self.fence_ordinal = fence_ordinal
        self.current_answers = list(current_answers)
        self.variant = variant
        self.events: list[str] = []
        self.requests: list[market_recovery.MarketSubscriptionRequest] = []

    def subscribe(
        self, request: market_recovery.MarketSubscriptionRequest
    ) -> market_recovery.MarketSubscriptionEvidence:
        self.events.append("subscribe")
        self.requests.append(request)
        issued_request = request
        if self.variant == "wrong-subscription":
            issued_request = replace(request, market_source_profile_id="d" * 64)
        return self._issue_subscription(issued_request, "cold-ack")

    def post_ack_fence(
        self, subscription: market_recovery.MarketSubscriptionEvidence
    ) -> market_recovery.MarketFenceEvidence:
        self.events.append("fence")
        return self._issue_fence(
            subscription,
            self.fence_ordinal,
            covers_pre_ack=self.variant != "uncovered-fence",
        )

    def baseline_at_fence(
        self,
        subscription: market_recovery.MarketSubscriptionEvidence,
        fence: market_recovery.MarketFenceEvidence,
    ) -> market_recovery.MarketBaselineEvidence:
        self.events.append("baseline")
        mandate = self.state.mandate
        sequence = (
            fence.fence_ordinal
            if mandate.evidence_policy.sequence_mode
            is protection.MarketSequenceMode.SEQUENCED
            else None
        )
        if self.variant == "wrong-coordinate" and sequence is not None:
            sequence += 1
        occurrence = protection_fixtures._occurrence(
            protection,
            "cold-baseline",
            bid=100,
            ask=101,
            sequence=sequence,
            source_time=fence.fence_ordinal,
            evaluation_time=fence.fence_ordinal,
            market_epoch=(
                self.state._market_expected_epoch + 1
                if self.variant == "wrong-epoch"
                and self.state._market_expected_epoch is not None
                else self.state._market_expected_epoch
            ),
            tick_units=mandate.tick.tick_units.value,
            scale=mandate.tick.scale,
            halted=self.variant == "halted",
            source_id=(
                identity.MarketDataSourceId("foreign-source")
                if self.variant == "wrong-source"
                else mandate.evidence_policy.source_id
            ),
            stream_generation=(
                identity.MarketStreamGenerationId("ef" * 32)
                if self.variant == "wrong-generation"
                else mandate.evidence_policy.stream_generation
            ),
            position_scope=mandate.position_scope,
            session_id=mandate.session_id,
        )
        return self._issue_baseline(
            subscription,
            fence,
            occurrence,
            (
                fence.fence_ordinal + 1
                if self.variant == "excluded-mismatch"
                else fence.fence_ordinal
            ),
        )

    def is_current(
        self,
        subscription: market_recovery.MarketSubscriptionEvidence,
        fence: market_recovery.MarketFenceEvidence,
    ) -> bool:
        del subscription, fence
        self.events.append("source-current")
        return self.current_answers.pop(0) if self.current_answers else True


def _patch_active_runtime(
    monkeypatch: pytest.MonkeyPatch,
    holder: dict[str, object],
    selected: object,
    *,
    effect_eligibility: unit_of_work.PostCommitEffectEligibility | None = None,
) -> None:
    def active(
        context: unit_of_work.UnitOfWorkContext,
        proof: object,
        scope_id: int,
    ) -> tuple[object, object]:
        del proof
        owner = next(item for item in context.scope_owners if item[0] == scope_id)
        assert owner[3] is not None
        return owner[3], selected

    def execute(
        connection: object,
        operation: object,
        context: unit_of_work.UnitOfWorkContext,
    ) -> unit_of_work.UnitOfWorkResult:
        del connection
        assert type(operation) is operations.MarketOccurrenceOperation
        scope_id, acquisition_owner, execution, state = context.scope_owners[0]
        assert state is not None
        projection = protection._m2_project_current_protection_venue(
            context.venue,
            execution,
            state,
        )
        transition = protection._m2_reduce_position_protection_market(
            state,
            projection,
            operation.occurrence,
        )
        assert transition.disposition is protection.ProtectionDisposition.APPLIED
        successor = replace(
            context,
            scope_owners=((scope_id, acquisition_owner, execution, transition.state),),
        )
        holder["context"] = successor
        return unit_of_work.UnitOfWorkResult(
            unit_of_work.UnitOfWorkDisposition.COMMITTED,
            "PROTECTION",
            "APPLIED",
            successor,
            effect_eligibility,
        )

    monkeypatch.setattr(startup, "_active_market_authority", active)
    monkeypatch.setattr(unit_of_work, "execute_unit_of_work", execute)


def test_initial_zero_fence_baseline_can_serve_and_final_checks_repeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, state, selected = _active_context()
    assert state._market_source_sequence is None
    assert state._market_baseline_required
    _dormant, proof = _dormant_context()
    holder: dict[str, object] = {"context": context}
    events: list[str] = []
    _patch_recovery_boundary(monkeypatch, holder, proof, events)
    _patch_active_runtime(monkeypatch, holder, selected)
    source = _MarketSource(state, fence_ordinal=0)
    owner = _Owner(events)

    result = startup.start_startup(
        _request(proof),
        owner_lock=owner,
        datastore=_Datastore(events),
        effect_queries=_NoEffectQueries(),
        market_source=source,
    )

    assert result.disposition is startup.StartupDisposition.SERVING
    assert source.events[:3] == ["subscribe", "fence", "baseline"]
    assert source.events.count("source-current") == 3
    assert source.requests == [
        market_recovery.MarketSubscriptionRequest(
            proof.request.market_source_profile_id,
            selected.stream.stream_generation_id,
            protection.MarketSequenceMode(selected.stream.sequence_mode),
            (
                f"cold:{proof.request.application_generation_id.value}:"
                f"1:{selected.stream.stream_generation_id.value}"
            ),
        )
    ]
    assert result.successor_context is holder["context"]
    assert not owner.released


def test_retained_cursor_equality_fails_before_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, state, selected = _active_context()
    projection = protection._m2_project_current_protection_venue(
        context.venue,
        context.scope_owners[0][2],
        state,
    )
    baseline = protection_fixtures._occurrence(
        protection,
        "retained-baseline",
        bid=100,
        ask=101,
        sequence=0,
        source_time=0,
        evaluation_time=0,
        market_epoch=0,
        tick_units=state.mandate.tick.tick_units.value,
        scale=state.mandate.tick.scale,
        source_id=state.mandate.evidence_policy.source_id,
        stream_generation=state.mandate.evidence_policy.stream_generation,
        position_scope=state.mandate.position_scope,
        session_id=state.mandate.session_id,
    )
    applied = protection._m2_reduce_position_protection_market(
        state,
        projection,
        baseline,
    )
    invalidated = protection.invalidate_position_protection_market(
        applied.state,
        projection,
    )
    assert invalidated.state._market_source_sequence == 0
    context = replace(
        context,
        scope_owners=(
            (
                1,
                context.scope_owners[0][1],
                context.scope_owners[0][2],
                invalidated.state,
            ),
        ),
    )
    _dormant, proof = _dormant_context()
    holder: dict[str, object] = {"context": context}
    events: list[str] = []
    _patch_recovery_boundary(monkeypatch, holder, proof, events)
    _patch_active_runtime(monkeypatch, holder, selected)
    source = _MarketSource(invalidated.state, fence_ordinal=0)
    owner = _Owner(events)

    result = startup.start_startup(
        _request(proof),
        owner_lock=owner,
        datastore=_Datastore(events),
        effect_queries=_NoEffectQueries(),
        market_source=source,
    )

    assert result.refusal_code is startup.StartupRefusalCode.FENCE_FAILURE
    assert source.events == ["subscribe", "fence"]
    assert owner.released


def test_source_currentness_loss_at_final_edge_is_non_serving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, state, selected = _active_context()
    _dormant, proof = _dormant_context()
    holder: dict[str, object] = {"context": context}
    events: list[str] = []
    _patch_recovery_boundary(monkeypatch, holder, proof, events)
    _patch_active_runtime(monkeypatch, holder, selected)
    source = _MarketSource(
        state,
        fence_ordinal=0,
        current_answers=(True, True, False),
    )
    owner = _Owner(events)

    result = startup.start_startup(
        _request(proof),
        owner_lock=owner,
        datastore=_Datastore(events),
        effect_queries=_NoEffectQueries(),
        market_source=source,
    )

    assert result.refusal_code is startup.StartupRefusalCode.BASELINE_FAILURE
    assert source.events.count("source-current") == 3
    assert owner.released


@pytest.mark.parametrize(
    ("variant", "expected_code", "expected_events"),
    (
        (
            "wrong-subscription",
            startup.StartupRefusalCode.UNSUPPORTED_SOURCE,
            ("subscribe",),
        ),
        (
            "uncovered-fence",
            startup.StartupRefusalCode.FENCE_FAILURE,
            ("subscribe", "fence"),
        ),
        (
            "excluded-mismatch",
            startup.StartupRefusalCode.BASELINE_FAILURE,
            ("subscribe", "fence", "baseline"),
        ),
        (
            "wrong-source",
            startup.StartupRefusalCode.BASELINE_FAILURE,
            ("subscribe", "fence", "baseline"),
        ),
        (
            "wrong-generation",
            startup.StartupRefusalCode.BASELINE_FAILURE,
            ("subscribe", "fence", "baseline"),
        ),
        (
            "wrong-epoch",
            startup.StartupRefusalCode.BASELINE_FAILURE,
            ("subscribe", "fence", "baseline"),
        ),
        (
            "wrong-coordinate",
            startup.StartupRefusalCode.BASELINE_FAILURE,
            ("subscribe", "fence", "baseline"),
        ),
        (
            "halted",
            startup.StartupRefusalCode.BASELINE_FAILURE,
            ("subscribe", "fence", "baseline"),
        ),
    ),
)
def test_port_issued_source_evidence_mutants_fail_before_baseline_commit(
    monkeypatch: pytest.MonkeyPatch,
    variant: str,
    expected_code: startup.StartupRefusalCode,
    expected_events: tuple[str, ...],
) -> None:
    context, state, selected = _active_context()
    _dormant, proof = _dormant_context()
    holder: dict[str, object] = {"context": context}
    events: list[str] = []
    _patch_recovery_boundary(monkeypatch, holder, proof, events)
    _patch_active_runtime(monkeypatch, holder, selected)
    source = _MarketSource(state, fence_ordinal=0, variant=variant)
    owner = _Owner(events)

    result = startup.start_startup(
        _request(proof),
        owner_lock=owner,
        datastore=_Datastore(events),
        effect_queries=_NoEffectQueries(),
        market_source=source,
    )

    assert result.refusal_code is expected_code
    assert tuple(source.events) == expected_events
    assert holder["context"] is context
    assert owner.released


def test_baseline_commit_cannot_publish_effect_eligibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, state, selected = _active_context()
    _dormant, proof = _dormant_context()
    holder: dict[str, object] = {"context": context}
    events: list[str] = []
    _patch_recovery_boundary(monkeypatch, holder, proof, events)
    _patch_active_runtime(
        monkeypatch,
        holder,
        selected,
        effect_eligibility=unit_of_work.PostCommitEffectEligibility(
            1,
            1,
            1,
            "a" * 64,
        ),
    )
    source = _MarketSource(state, fence_ordinal=0)
    owner = _Owner(events)

    result = startup.start_startup(
        _request(proof),
        owner_lock=owner,
        datastore=_Datastore(events),
        effect_queries=_NoEffectQueries(),
        market_source=source,
    )

    assert result.refusal_code is startup.StartupRefusalCode.BASELINE_FAILURE
    assert source.events == ["subscribe", "fence", "baseline"]
    assert owner.released


def test_source_refusal_retry_reloads_committed_c1_without_retaining_c0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, state, selected = _active_context()
    _dormant, proof = _dormant_context()
    holder: dict[str, object] = {"context": context}
    events: list[str] = []
    cutover_dispositions: list[unit_of_work.UnitOfWorkDisposition] = []

    def cutover(*args: object) -> unit_of_work._ColdCompactCutoverResult:
        del args
        disposition = (
            unit_of_work.UnitOfWorkDisposition.COMMITTED
            if not cutover_dispositions
            else unit_of_work.UnitOfWorkDisposition.EXACT_REPLAY
        )
        cutover_dispositions.append(disposition)
        current = holder["context"]
        assert type(current) is unit_of_work.UnitOfWorkContext
        return unit_of_work._ColdCompactCutoverResult(disposition, current, proof)

    monkeypatch.setattr(unit_of_work, "_m2_cold_compact_cutover", cutover)
    monkeypatch.setattr(
        unit_of_work,
        "_m2_reread_cold_context",
        lambda *args: (holder["context"], proof),
    )
    _patch_active_runtime(monkeypatch, holder, selected)
    unsupported = _UnsupportedMarketSource()
    first_owner = _Owner(events)

    first = startup.start_startup(
        _request(proof),
        owner_lock=first_owner,
        datastore=_Datastore(events),
        effect_queries=_NoEffectQueries(),
        market_source=unsupported,
    )

    assert first.refusal_code is startup.StartupRefusalCode.UNSUPPORTED_SOURCE
    assert first.successor_context is None
    assert first_owner.released
    assert len(unsupported.requests) == 1

    source = _MarketSource(state, fence_ordinal=0)
    second_owner = _Owner(events)
    second = startup.start_startup(
        _request(proof),
        owner_lock=second_owner,
        datastore=_Datastore(events),
        effect_queries=_NoEffectQueries(),
        market_source=source,
    )

    assert second.disposition is startup.StartupDisposition.SERVING
    assert second.successor_context is holder["context"]
    assert cutover_dispositions == [
        unit_of_work.UnitOfWorkDisposition.COMMITTED,
        unit_of_work.UnitOfWorkDisposition.EXACT_REPLAY,
        unit_of_work.UnitOfWorkDisposition.EXACT_REPLAY,
        unit_of_work.UnitOfWorkDisposition.EXACT_REPLAY,
    ]
    assert not second_owner.released


def test_effect_query_enumeration_preserves_unclaimed_effects_without_query() -> None:
    context, proof = _dormant_context()
    del context
    effect = records.VenueEffectRecord(
        1,
        identity.EffectId("cold-effect"),
        1,
        proof.request.application_generation_id,
        proof.request.execution_profile_id,
        identity.AcquisitionGenerationId("ab" * 32),
        "c" * 64,
        0,
        0,
        "NORMAL",
        identity.RequestOccurrenceId("cold-request"),
        identity.MandateId("cold-mandate"),
        "SUBMIT",
        identity.ClientOrderId("cold-client"),
        None,
        "BUY",
        values.Quantity(1),
        b"scope",
        "REQUESTED",
        "OPEN",
        None,
        None,
        None,
        None,
        1,
    )
    request = _request(proof)
    unclaimed = SimpleNamespace(
        _selection=SimpleNamespace(effects=(effect,), claims=())
    )
    assert startup._effect_query_requests(request, unclaimed) == ()

    claim = records.DispatchClaimRecord(
        1,
        effect.effect_id,
        proof.request.execution_profile_id,
        identity.ClaimOccurrenceId("cold-claim"),
        1,
    )
    claimed = SimpleNamespace(
        _selection=SimpleNamespace(
            effects=(replace(effect, lifecycle_state="DISPATCH_CLAIMED"),),
            claims=(claim,),
        )
    )
    requests = startup._effect_query_requests(request, claimed)
    assert requests is not None
    assert requests == (
        market_recovery.EffectQueryRequest(
            request.application_generation_id,
            request.execution_profile_id,
            1,
            effect.effect_external,
            claim.claim_occurrence_id,
        ),
    )


@pytest.mark.parametrize(
    ("lifecycle_state", "claimed", "expected"),
    (
        ("REQUESTED", False, True),
        ("ACKNOWLEDGED", True, True),
        ("REJECTED", True, True),
        ("OPERATOR_RECONCILED", True, True),
        ("DISPATCH_CLAIMED", True, False),
        ("OUTCOME_UNKNOWN", True, False),
        ("NEEDS_REVIEW", True, False),
    ),
)
def test_claimed_reconciliation_requires_a_known_post_query_state(
    lifecycle_state: str,
    claimed: bool,
    expected: bool,
) -> None:
    _context, base = _dormant_context()
    effect = records.VenueEffectRecord(
        1,
        identity.EffectId("coverage-effect"),
        1,
        base.request.application_generation_id,
        base.request.execution_profile_id,
        identity.AcquisitionGenerationId("ab" * 32),
        "c" * 64,
        0,
        0,
        "NORMAL",
        identity.RequestOccurrenceId("coverage-request"),
        identity.MandateId("coverage-mandate"),
        "SUBMIT",
        identity.ClientOrderId("coverage-client"),
        None,
        "BUY",
        values.Quantity(1),
        b"coverage",
        lifecycle_state,
        "OPEN",
        None,
        None,
        None,
        None,
        1,
    )
    claims = (
        (
            records.DispatchClaimRecord(
                1,
                effect.effect_id,
                effect.execution_profile_id,
                identity.ClaimOccurrenceId("coverage-claim"),
                1,
            ),
        )
        if claimed
        else ()
    )
    proof = records._issue_runtime_checkpoint_selection_proof(
        base.request,
        base.application_generation,
        base.execution_profile,
        base.market_source_profile,
        base.predecessor_checkpoint,
        base.target_currentness_head_ordinal,
        base.target_checkpoint_version_ordinal,
        replace(base._selection, effects=(effect,), claims=claims),
    )

    assert startup._proof_has_complete_claimed_reconciliation(proof) is expected


def test_reconciliation_operation_is_bound_to_exact_effect_scope_and_session() -> None:
    _context, proof = _dormant_context()
    effect = records.VenueEffectRecord(
        1,
        identity.EffectId("bound-effect"),
        1,
        proof.request.application_generation_id,
        proof.request.execution_profile_id,
        identity.AcquisitionGenerationId("ab" * 32),
        "c" * 64,
        0,
        0,
        "NORMAL",
        identity.RequestOccurrenceId("bound-request"),
        identity.MandateId("bound-mandate"),
        "SUBMIT",
        identity.ClientOrderId("bound-client"),
        None,
        "BUY",
        values.Quantity(1),
        b"scope",
        "DISPATCH_CLAIMED",
        "OPEN",
        None,
        None,
        None,
        None,
        1,
    )
    claim = records.DispatchClaimRecord(
        1,
        effect.effect_id,
        proof.request.execution_profile_id,
        identity.ClaimOccurrenceId("bound-claim"),
        1,
    )
    session_id = identity.SessionId("bound-session")
    stream = records.MarketStreamAuthorityRecord(
        identity.MarketStreamGenerationId("cd" * 32),
        1,
        proof.request.application_generation_id,
        effect.acquisition_generation_id,
        effect.generation_mandate_commitment_sha256,
        proof.request.market_source_profile_id,
        session_id,
        protection.MarketSequenceMode.SEQUENCED.value,
    )
    selection_proof = SimpleNamespace(
        _selection=SimpleNamespace(
            effects=(effect,),
            claims=(claim,),
            streams=(stream,),
            owners=(),
        )
    )
    query = market_recovery.EffectQueryRequest(
        proof.request.application_generation_id,
        proof.request.execution_profile_id,
        1,
        effect.effect_external,
        claim.claim_occurrence_id,
    )
    item = venue.RecoverClaimedEffect(
        identity.VenueInputId("bound-recovery"),
        effect.effect_external,
    )

    def operation(
        *,
        application: identity.ApplicationGenerationId = (
            proof.request.application_generation_id
        ),
        profile: str = proof.request.execution_profile_id,
        scope_id: int = 1,
        session: identity.SessionId | None = session_id,
        recovery_item: object = item,
    ) -> operations.VenueRecoveryOperation:
        return operations.VenueRecoveryOperation(
            operations.VenueOperationCoordinates(
                application,
                profile,
                scope_id,
                session,
            ),
            recovery_item,  # type: ignore[arg-type]
        )

    assert startup._effect_operation_matches_request(
        selection_proof,
        query,
        operation(),
    )
    assert not startup._effect_operation_matches_request(
        selection_proof,
        query,
        operation(application=identity.ApplicationGenerationId("foreign-app")),
    )
    assert not startup._effect_operation_matches_request(
        selection_proof,
        query,
        operation(profile="d" * 64),
    )
    assert not startup._effect_operation_matches_request(
        selection_proof,
        query,
        operation(scope_id=2),
    )
    assert not startup._effect_operation_matches_request(
        selection_proof,
        query,
        operation(session=identity.SessionId("foreign-session")),
    )
    assert not startup._effect_operation_matches_request(
        selection_proof,
        query,
        operation(
            recovery_item=venue.RecoverClaimedEffect(
                identity.VenueInputId("foreign-recovery"),
                identity.EffectId("foreign-effect"),
            )
        ),
    )


def _unresolved_union_proof() -> tuple[
    records.RuntimeCheckpointSelectionProof,
    records.RuntimeCheckpointSelectionProof,
]:
    _context, resolved = _dormant_context()
    generation_id = identity.AcquisitionGenerationId("ab" * 32)
    effects = tuple(
        records.VenueEffectRecord(
            ordinal,
            identity.EffectId(f"union-effect-{ordinal}"),
            1,
            resolved.request.application_generation_id,
            resolved.request.execution_profile_id,
            generation_id,
            "c" * 64,
            0,
            0,
            "NORMAL",
            identity.RequestOccurrenceId(f"union-request-{ordinal}"),
            identity.MandateId(f"union-mandate-{ordinal}"),
            "SUBMIT",
            identity.ClientOrderId(f"union-client-{ordinal}"),
            None,
            "BUY",
            values.Quantity(1),
            bytes([ordinal]),
            "DISPATCH_CLAIMED",
            lifecycle,
            None,
            None,
            None,
            None,
            ordinal,
        )
        for ordinal, lifecycle in enumerate(
            ("OPEN", "INVALIDATED", "CLOSED"),
            start=1,
        )
    )
    claims = tuple(
        records.DispatchClaimRecord(
            effect.effect_id,
            effect.effect_id,
            effect.execution_profile_id,
            identity.ClaimOccurrenceId(f"union-claim-{effect.effect_id}"),
            effect.effect_id,
        )
        for effect in effects
    )
    stream = records.MarketStreamAuthorityRecord(
        identity.MarketStreamGenerationId("cd" * 32),
        1,
        resolved.request.application_generation_id,
        generation_id,
        "c" * 64,
        resolved.request.market_source_profile_id,
        identity.SessionId("union-session"),
        protection.MarketSequenceMode.SEQUENCED.value,
    )
    selection = replace(
        resolved._selection,
        effects=effects,
        claims=claims,
        streams=(stream,),
    )
    unresolved = records._issue_runtime_checkpoint_selection_proof(
        resolved.request,
        resolved.application_generation,
        resolved.execution_profile,
        resolved.market_source_profile,
        resolved.predecessor_checkpoint,
        resolved.target_currentness_head_ordinal,
        resolved.target_checkpoint_version_ordinal,
        selection,
    )
    return unresolved, resolved


class _ResolvedEffectQueries(market_recovery.EffectQueryPort):
    def __init__(
        self,
        session_id: identity.SessionId,
        *,
        corrupt: str | None = None,
    ) -> None:
        self.session_id = session_id
        self.corrupt = corrupt
        self.requests: list[market_recovery.EffectQueryRequest] = []

    def query(
        self, request: market_recovery.EffectQueryRequest
    ) -> market_recovery.EffectQueryResult:
        self.requests.append(request)
        returned_request = request
        application = request.application_generation_id
        profile = request.execution_profile_id
        scope_id = request.scope_id
        session_id = self.session_id
        effect_id = request.effect_id
        if len(self.requests) == 1:
            if self.corrupt == "request":
                returned_request = replace(
                    request,
                    claim_occurrence_id=identity.ClaimOccurrenceId("foreign-claim"),
                )
            elif self.corrupt == "application":
                application = identity.ApplicationGenerationId("foreign-app")
            elif self.corrupt == "profile":
                profile = "d" * 64
            elif self.corrupt == "scope":
                scope_id += 1
            elif self.corrupt == "session":
                session_id = identity.SessionId("foreign-session")
            elif self.corrupt == "effect":
                effect_id = identity.EffectId("foreign-effect")
        operation = operations.VenueRecoveryOperation(
            operations.VenueOperationCoordinates(
                application,
                profile,
                scope_id,
                session_id,
            ),
            venue.RecordTransportOutcome(
                identity.VenueInputId(f"resolve-{request.effect_id.value}"),
                effect_id,
                venue.BrokerEffectState.ACKNOWLEDGED,
            ),
        )
        return market_recovery.EffectQueryResult(
            returned_request,
            market_recovery.EffectQueryDisposition.RESOLVED,
            operation,
        )


def _patch_unresolved_union_runtime(
    monkeypatch: pytest.MonkeyPatch,
    context: unit_of_work.UnitOfWorkContext,
    unresolved: records.RuntimeCheckpointSelectionProof,
    resolved: records.RuntimeCheckpointSelectionProof,
    applied: list[operations.VenueRecoveryOperation],
) -> None:
    cutover_calls = 0

    def cutover(*args: object) -> unit_of_work._ColdCompactCutoverResult:
        nonlocal cutover_calls
        del args
        cutover_calls += 1
        proof = unresolved if cutover_calls == 1 else resolved
        return unit_of_work._ColdCompactCutoverResult(
            unit_of_work.UnitOfWorkDisposition.EXACT_REPLAY,
            context,
            proof,
        )

    def execute(
        connection: object,
        operation: object,
        current: unit_of_work.UnitOfWorkContext,
    ) -> unit_of_work.UnitOfWorkResult:
        del connection
        assert type(operation) is operations.VenueRecoveryOperation
        applied.append(operation)
        return unit_of_work.UnitOfWorkResult(
            unit_of_work.UnitOfWorkDisposition.COMMITTED,
            "VENUE",
            "APPLIED",
            current,
            None,
        )

    monkeypatch.setattr(unit_of_work, "_m2_cold_compact_cutover", cutover)
    monkeypatch.setattr(
        unit_of_work,
        "_m2_reread_cold_context",
        lambda *args: (context, resolved),
    )
    monkeypatch.setattr(unit_of_work, "execute_unit_of_work", execute)


def test_complete_claimed_unresolved_union_is_queried_once_and_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, _base_proof = _dormant_context()
    unresolved, resolved = _unresolved_union_proof()
    applied: list[operations.VenueRecoveryOperation] = []
    _patch_unresolved_union_runtime(
        monkeypatch,
        context,
        unresolved,
        resolved,
        applied,
    )
    queries = _ResolvedEffectQueries(unresolved._selection.streams[0].session_id)
    events: list[str] = []

    result = startup.start_startup(
        _request(unresolved),
        owner_lock=_Owner(events),
        datastore=_Datastore(events),
        effect_queries=queries,
        market_source=_NoMarketSource(),
    )

    assert result.disposition is startup.StartupDisposition.SERVING
    assert tuple(request.effect_id for request in queries.requests) == tuple(
        effect.effect_external for effect in unresolved._selection.effects
    )
    assert len(queries.requests) == len(applied) == 3
    assert tuple(operation.item.effect_id for operation in applied) == tuple(
        request.effect_id for request in queries.requests
    )


@pytest.mark.parametrize(
    "corrupt",
    ("request", "application", "profile", "scope", "session", "effect"),
)
def test_cross_bound_reconciliation_result_stops_before_uow(
    monkeypatch: pytest.MonkeyPatch,
    corrupt: str,
) -> None:
    context, _base_proof = _dormant_context()
    unresolved, resolved = _unresolved_union_proof()
    applied: list[operations.VenueRecoveryOperation] = []
    _patch_unresolved_union_runtime(
        monkeypatch,
        context,
        unresolved,
        resolved,
        applied,
    )
    queries = _ResolvedEffectQueries(
        unresolved._selection.streams[0].session_id,
        corrupt=corrupt,
    )
    events: list[str] = []
    owner = _Owner(events)

    result = startup.start_startup(
        _request(unresolved),
        owner_lock=owner,
        datastore=_Datastore(events),
        effect_queries=queries,
        market_source=_NoMarketSource(),
    )

    assert result.refusal_code is startup.StartupRefusalCode.INTERNAL_INTEGRITY
    assert len(queries.requests) == 1
    assert applied == []
    assert owner.released
