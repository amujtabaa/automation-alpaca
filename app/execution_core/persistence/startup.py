"""Fail-closed M2 cold-start coordinator."""

from __future__ import annotations

from collections.abc import Iterable as _Iterable
from dataclasses import dataclass as _dataclass
from enum import Enum as _Enum

from .. import identity as _identity
from .. import protection as _protection
from .. import venue as _venue
from . import market_recovery as _market_recovery
from . import operations as _operations
from . import owner_lock as _owner_lock
from . import records as _records
from . import unit_of_work as _unit_of_work
from .schema import SQLiteConnectionProtocol as _SQLiteConnectionProtocol


_BLOCKING_CLAIMED_EFFECT_STATES = frozenset(
    {"DISPATCH_CLAIMED", "OUTCOME_UNKNOWN", "NEEDS_REVIEW"}
)


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


class _StartupDatastorePort:
    """Private injected connection factory; startup never discovers configuration."""

    def open(self) -> _SQLiteConnectionProtocol:
        raise NotImplementedError


def _owner_is_current(
    port: _owner_lock.OwnerLockPort,
    evidence: _owner_lock.OwnerLeaseEvidence,
) -> bool:
    try:
        return bool(
            _owner_lock._owner_lease_is_authentic(port, evidence)
            and port.is_current(evidence) is True
        )
    except Exception:
        return False


def _release_owner(
    port: _owner_lock.OwnerLockPort,
    evidence: _owner_lock.OwnerLeaseEvidence,
) -> None:
    try:
        port.release(evidence)
    except Exception:
        return


def _close_connection(connection: _SQLiteConnectionProtocol | None) -> bool:
    if connection is None:
        return True
    close = getattr(connection, "close", None)
    if not callable(close):
        return False
    try:
        close()
    except Exception:
        return False
    return True


def _stop_startup(
    code: StartupRefusalCode,
    owner_lock: _owner_lock.OwnerLockPort,
    evidence: _owner_lock.OwnerLeaseEvidence,
    connection: _SQLiteConnectionProtocol | None,
) -> StartupResult:
    _close_connection(connection)
    _release_owner(owner_lock, evidence)
    return _non_serving(code)


def _effect_query_requests(
    request: StartupRequest,
    proof: _records.RuntimeCheckpointSelectionProof,
) -> tuple[_market_recovery.EffectQueryRequest, ...] | None:
    selection = proof._selection
    effects_by_id = {effect.effect_id: effect for effect in selection.effects}
    if len(effects_by_id) != len(selection.effects):
        return None
    requests: list[_market_recovery.EffectQueryRequest] = []
    seen_effects: set[int] = set()
    for claim in selection.claims:
        effect = effects_by_id.get(claim.effect_id)
        if effect is None or claim.effect_id in seen_effects:
            return None
        seen_effects.add(claim.effect_id)
        if effect.lifecycle_state not in _BLOCKING_CLAIMED_EFFECT_STATES:
            continue
        try:
            requests.append(
                _market_recovery.EffectQueryRequest(
                    request.application_generation_id,
                    request.execution_profile_id,
                    effect.scope_id,
                    effect.effect_external,
                    claim.claim_occurrence_id,
                )
            )
        except (TypeError, ValueError, OverflowError):
            return None
    return tuple(requests)


def _effect_operation_matches_request(
    proof: _records.RuntimeCheckpointSelectionProof,
    query: _market_recovery.EffectQueryRequest,
    operation: _operations.VenueRecoveryOperation,
) -> bool:
    coordinates = operation.coordinates
    if (
        coordinates.application_generation_id != query.application_generation_id
        or coordinates.execution_profile_id != query.execution_profile_id
        or coordinates.scope_id != query.scope_id
    ):
        return False
    effects = tuple(
        effect
        for effect in proof._selection.effects
        if effect.scope_id == query.scope_id
        and effect.effect_external == query.effect_id
    )
    if len(effects) != 1:
        return False
    effect = effects[0]
    streams = tuple(
        stream
        for stream in proof._selection.streams
        if stream.scope_id == effect.scope_id
        and stream.acquisition_generation_id == effect.acquisition_generation_id
    )
    if len(streams) != 1:
        return False
    expected_session = streams[0].session_id
    item = operation.item
    if type(item) is _venue.ObserveVenueStatus:
        if coordinates.session_id not in {None, expected_session}:
            return False
        return any(
            owner.effect_id == effect.effect_id
            and owner.scope_id == effect.scope_id
            and owner.owner_id == item.leg_key.order_id
            for owner in proof._selection.owners
        )
    if coordinates.session_id != expected_session:
        return False
    item_effect_id = getattr(item, "effect_id", None)
    if type(item_effect_id) is not _identity.EffectId:
        return False
    if item_effect_id != query.effect_id:
        return False
    item_claim = getattr(item, "claim_occurrence_id", query.claim_occurrence_id)
    return item_claim == query.claim_occurrence_id


def _proof_has_complete_claimed_reconciliation(
    proof: _records.RuntimeCheckpointSelectionProof,
) -> bool:
    if not _records.RuntimeCheckpointSelectionProof._is_authentic(proof):
        return False
    selection = proof._selection
    effects_by_id = {effect.effect_id: effect for effect in selection.effects}
    if len(effects_by_id) != len(selection.effects):
        return False
    seen_effects: set[int] = set()
    for claim in selection.claims:
        effect = effects_by_id.get(claim.effect_id)
        if (
            effect is None
            or claim.effect_id in seen_effects
            or claim.execution_profile_id != effect.execution_profile_id
            or effect.lifecycle_state in _BLOCKING_CLAIMED_EFFECT_STATES
        ):
            return False
        seen_effects.add(claim.effect_id)
    return True


def _cutover_refusal_code(
    result: _unit_of_work._ColdCompactCutoverResult,
) -> StartupRefusalCode | None:
    if result.disposition in {
        _unit_of_work.UnitOfWorkDisposition.COMMITTED,
        _unit_of_work.UnitOfWorkDisposition.EXACT_REPLAY,
    }:
        return None
    if result.failure is _unit_of_work._ColdCompactCutoverFailure.CURRENT_PROOF:
        return StartupRefusalCode.CURRENT_PROOF_FAILURE
    if result.failure is _unit_of_work._ColdCompactCutoverFailure.INVALIDATION:
        return StartupRefusalCode.INVALIDATION_FAILURE
    if result.failure in {
        _unit_of_work._ColdCompactCutoverFailure.DATASTORE,
        _unit_of_work._ColdCompactCutoverFailure.COMMIT_AMBIGUITY,
    }:
        return StartupRefusalCode.DATASTORE_INTEGRITY
    return StartupRefusalCode.INTERNAL_INTEGRITY


def _active_market_authority(
    context: _unit_of_work.UnitOfWorkContext,
    proof: _records.RuntimeCheckpointSelectionProof,
    scope_id: int,
) -> (
    tuple[
        _protection.PositionProtectionState,
        _unit_of_work._SelectedAcquisitionAuthority,
    ]
    | None
):
    owners = tuple(owner for owner in context.scope_owners if owner[0] == scope_id)
    if len(owners) != 1:
        return None
    _, acquisition, execution, protection = owners[0]
    if acquisition is None or protection is None:
        return None
    try:
        selected = _unit_of_work._selected_acquisition_authority_for_coordinates(
            proof,
            proof.request.application_generation_id,
            proof.request.execution_profile_id,
            scope_id,
            acquisition._controller.live_generation_id,
            acquisition,
            execution,
            protection,
        )
    except Exception:
        return None
    if selected.cursor is None:
        return None
    return protection, selected


def _retry_coordinate(
    request: StartupRequest,
    scope_id: int,
    stream_generation_id: _identity.MarketStreamGenerationId,
) -> str:
    return (
        f"cold:{request.application_generation_id.value}:"
        f"{scope_id}:{stream_generation_id.value}"
    )


def _retained_market_coordinate(
    state: _protection.PositionProtectionState,
) -> int | None:
    mode = state.mandate.evidence_policy.sequence_mode
    if mode is _protection.MarketSequenceMode.SEQUENCED:
        return state._market_source_sequence
    return state._market_source_time


def _baseline_matches_authority(
    state: _protection.PositionProtectionState,
    fence: _market_recovery.MarketFenceEvidence,
    baseline: _market_recovery.MarketBaselineEvidence,
) -> bool:
    occurrence = baseline.occurrence
    policy = state.mandate.evidence_policy
    coordinate = fence.fence_ordinal
    if coordinate == 18_446_744_073_709_551_615:
        return False
    retained = _retained_market_coordinate(state)
    if retained is not None and coordinate <= retained:
        return False
    if (
        state._market_exhausted
        or not state._market_baseline_required
        or state._market_expected_epoch is None
        or occurrence.source_id != policy.source_id
        or occurrence.stream_generation != policy.stream_generation
        or occurrence.position_scope != state.mandate.position_scope
        or occurrence.session_id != state.mandate.session_id
        or occurrence.market_epoch != state._market_expected_epoch
        or occurrence.halted
    ):
        return False
    if policy.sequence_mode is _protection.MarketSequenceMode.SEQUENCED:
        return occurrence.source_sequence == coordinate
    return occurrence.source_sequence is None and occurrence.source_time == coordinate


def _source_is_current(
    source: _market_recovery.MarketSourcePort,
    subscription: _market_recovery.MarketSubscriptionEvidence,
    fence: _market_recovery.MarketFenceEvidence,
) -> bool:
    try:
        return bool(
            _market_recovery._market_subscription_is_authentic(
                source,
                subscription,
                subscription.request,
            )
            and _market_recovery._market_fence_is_authentic(
                source,
                fence,
                subscription,
            )
            and source.is_current(subscription, fence) is True
        )
    except Exception:
        return False


def _retained_sources_refusal(
    owner_lock: _owner_lock.OwnerLockPort,
    evidence: _owner_lock.OwnerLeaseEvidence,
    source: _market_recovery.MarketSourcePort,
    retained: _Iterable[
        tuple[
            _market_recovery.MarketSubscriptionEvidence,
            _market_recovery.MarketFenceEvidence,
        ]
    ],
) -> StartupRefusalCode | None:
    """Fence every source-currentness call with the process owner lease."""

    for subscription, fence in retained:
        if not _owner_is_current(owner_lock, evidence):
            return StartupRefusalCode.OWNER_LOST
        source_current = _source_is_current(source, subscription, fence)
        if not _owner_is_current(owner_lock, evidence):
            return StartupRefusalCode.OWNER_LOST
        if not source_current:
            return StartupRefusalCode.BASELINE_FAILURE
    return None


def start_startup(
    request: StartupRequest,
    *,
    owner_lock: _owner_lock.OwnerLockPort,
    datastore: _StartupDatastorePort,
    effect_queries: _market_recovery.EffectQueryPort,
    market_source: _market_recovery.MarketSourcePort,
) -> StartupResult:
    """Run the owner-locked cold recovery sequence and fail closed on uncertainty."""

    if (
        type(request) is not StartupRequest
        or not isinstance(owner_lock, _owner_lock.OwnerLockPort)
        or not isinstance(datastore, _StartupDatastorePort)
        or not isinstance(effect_queries, _market_recovery.EffectQueryPort)
        or not isinstance(market_source, _market_recovery.MarketSourcePort)
    ):
        return _non_serving(StartupRefusalCode.INTERNAL_INTEGRITY)
    try:
        evidence = owner_lock.acquire()
    except Exception:
        return _non_serving(StartupRefusalCode.OWNER_DENIED)
    if evidence is None or not _owner_lock._owner_lease_is_authentic(
        owner_lock, evidence
    ):
        return _non_serving(StartupRefusalCode.OWNER_DENIED)
    if not _owner_is_current(owner_lock, evidence):
        _release_owner(owner_lock, evidence)
        return _non_serving(StartupRefusalCode.OWNER_LOST)

    connection: _SQLiteConnectionProtocol | None = None
    try:
        if not _owner_is_current(owner_lock, evidence):
            return _stop_startup(
                StartupRefusalCode.OWNER_LOST,
                owner_lock,
                evidence,
                connection,
            )
        try:
            connection = datastore.open()
        except Exception:
            return _stop_startup(
                StartupRefusalCode.DATASTORE_INTEGRITY,
                owner_lock,
                evidence,
                connection,
            )
        if not _owner_is_current(owner_lock, evidence):
            return _stop_startup(
                StartupRefusalCode.OWNER_LOST,
                owner_lock,
                evidence,
                connection,
            )

        try:
            initial_cutover = _unit_of_work._m2_cold_compact_cutover(
                connection,
                request.application_generation_id,
                request.execution_profile_id,
                request.market_source_profile_id,
            )
        except Exception:
            return _stop_startup(
                StartupRefusalCode.DATASTORE_INTEGRITY,
                owner_lock,
                evidence,
                connection,
            )
        if not _owner_is_current(owner_lock, evidence):
            return _stop_startup(
                StartupRefusalCode.OWNER_LOST,
                owner_lock,
                evidence,
                connection,
            )
        initial_refusal = _cutover_refusal_code(initial_cutover)
        if initial_refusal is not None:
            return _stop_startup(
                initial_refusal,
                owner_lock,
                evidence,
                connection,
            )
        context = initial_cutover.successor_context
        proof = initial_cutover.selection_proof
        if (
            type(context) is not _unit_of_work.UnitOfWorkContext
            or type(proof) is not _records.RuntimeCheckpointSelectionProof
        ):
            return _stop_startup(
                StartupRefusalCode.CURRENT_PROOF_FAILURE,
                owner_lock,
                evidence,
                connection,
            )

        query_requests = _effect_query_requests(request, proof)
        if query_requests is None:
            return _stop_startup(
                StartupRefusalCode.UNRESOLVED_EFFECTS,
                owner_lock,
                evidence,
                connection,
            )
        for query_request in query_requests:
            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            query_result = effect_queries.query(query_request)
            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            if (
                type(query_result) is not _market_recovery.EffectQueryResult
                or query_result.request != query_request
            ):
                return _stop_startup(
                    StartupRefusalCode.INTERNAL_INTEGRITY,
                    owner_lock,
                    evidence,
                    connection,
                )
            if (
                query_result.disposition
                is _market_recovery.EffectQueryDisposition.UNSUPPORTED
            ):
                return _stop_startup(
                    StartupRefusalCode.UNSUPPORTED_SOURCE,
                    owner_lock,
                    evidence,
                    connection,
                )
            if (
                query_result.disposition
                is not _market_recovery.EffectQueryDisposition.RESOLVED
                or type(query_result.operation)
                is not _operations.VenueRecoveryOperation
            ):
                return _stop_startup(
                    StartupRefusalCode.UNRESOLVED_EFFECTS,
                    owner_lock,
                    evidence,
                    connection,
                )
            if not _effect_operation_matches_request(
                proof,
                query_request,
                query_result.operation,
            ):
                return _stop_startup(
                    StartupRefusalCode.INTERNAL_INTEGRITY,
                    owner_lock,
                    evidence,
                    connection,
                )
            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            result = _unit_of_work.execute_unit_of_work(
                connection,
                query_result.operation,
                context,
            )
            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            if result.disposition is _unit_of_work.UnitOfWorkDisposition.COMMITTED:
                if (
                    type(result.successor_context)
                    is not _unit_of_work.UnitOfWorkContext
                    or result.effect_eligibility is not None
                ):
                    return _stop_startup(
                        StartupRefusalCode.INTERNAL_INTEGRITY,
                        owner_lock,
                        evidence,
                        connection,
                    )
                context = result.successor_context
            elif (
                result.disposition
                is not _unit_of_work.UnitOfWorkDisposition.EXACT_REPLAY
            ):
                return _stop_startup(
                    StartupRefusalCode.UNRESOLVED_EFFECTS,
                    owner_lock,
                    evidence,
                    connection,
                )

        if not _owner_is_current(owner_lock, evidence):
            return _stop_startup(
                StartupRefusalCode.OWNER_LOST,
                owner_lock,
                evidence,
                connection,
            )
        try:
            context, proof = _unit_of_work._m2_reread_cold_context(
                connection,
                request.application_generation_id,
                request.execution_profile_id,
                request.market_source_profile_id,
                context.expected_checkpoint,
            )
        except Exception:
            return _stop_startup(
                StartupRefusalCode.CURRENT_PROOF_FAILURE,
                owner_lock,
                evidence,
                connection,
            )
        if not _owner_is_current(owner_lock, evidence):
            return _stop_startup(
                StartupRefusalCode.OWNER_LOST,
                owner_lock,
                evidence,
                connection,
            )
        if not _proof_has_complete_claimed_reconciliation(proof):
            return _stop_startup(
                StartupRefusalCode.UNRESOLVED_EFFECTS,
                owner_lock,
                evidence,
                connection,
            )

        if not _owner_is_current(owner_lock, evidence):
            return _stop_startup(
                StartupRefusalCode.OWNER_LOST,
                owner_lock,
                evidence,
                connection,
            )
        try:
            final_cutover = _unit_of_work._m2_cold_compact_cutover(
                connection,
                request.application_generation_id,
                request.execution_profile_id,
                request.market_source_profile_id,
            )
        except Exception:
            return _stop_startup(
                StartupRefusalCode.DATASTORE_INTEGRITY,
                owner_lock,
                evidence,
                connection,
            )
        if not _owner_is_current(owner_lock, evidence):
            return _stop_startup(
                StartupRefusalCode.OWNER_LOST,
                owner_lock,
                evidence,
                connection,
            )
        final_refusal = _cutover_refusal_code(final_cutover)
        if final_refusal is not None:
            return _stop_startup(
                final_refusal,
                owner_lock,
                evidence,
                connection,
            )
        context = final_cutover.successor_context
        proof = final_cutover.selection_proof
        if (
            type(context) is not _unit_of_work.UnitOfWorkContext
            or type(proof) is not _records.RuntimeCheckpointSelectionProof
            or not _proof_has_complete_claimed_reconciliation(proof)
        ):
            return _stop_startup(
                StartupRefusalCode.CURRENT_PROOF_FAILURE,
                owner_lock,
                evidence,
                connection,
            )

        active_scope_ids = tuple(
            scope_id
            for scope_id, _acquisition, _execution, protection in context.scope_owners
            if protection is not None
        )
        retained_subscriptions: list[
            tuple[
                _market_recovery.MarketSubscriptionEvidence,
                _market_recovery.MarketFenceEvidence,
            ]
        ] = []
        for scope_id in active_scope_ids:
            authority = _active_market_authority(context, proof, scope_id)
            if authority is None:
                return _stop_startup(
                    StartupRefusalCode.CURRENT_PROOF_FAILURE,
                    owner_lock,
                    evidence,
                    connection,
                )
            protection_state, selected = authority
            subscription_request = _market_recovery.MarketSubscriptionRequest(
                request.market_source_profile_id,
                selected.stream.stream_generation_id,
                _protection.MarketSequenceMode(selected.stream.sequence_mode),
                _retry_coordinate(
                    request,
                    scope_id,
                    selected.stream.stream_generation_id,
                ),
            )
            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            subscription = market_source.subscribe(subscription_request)
            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            if not _market_recovery._market_subscription_is_authentic(
                market_source,
                subscription,
                subscription_request,
            ):
                return _stop_startup(
                    StartupRefusalCode.UNSUPPORTED_SOURCE,
                    owner_lock,
                    evidence,
                    connection,
                )
            assert type(subscription) is _market_recovery.MarketSubscriptionEvidence

            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            fence = market_source.post_ack_fence(subscription)
            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            if not _market_recovery._market_fence_is_authentic(
                market_source,
                fence,
                subscription,
            ):
                return _stop_startup(
                    StartupRefusalCode.FENCE_FAILURE,
                    owner_lock,
                    evidence,
                    connection,
                )
            assert type(fence) is _market_recovery.MarketFenceEvidence
            retained_coordinate = _retained_market_coordinate(protection_state)
            if fence.fence_ordinal == 18_446_744_073_709_551_615 or (
                retained_coordinate is not None
                and fence.fence_ordinal <= retained_coordinate
            ):
                return _stop_startup(
                    StartupRefusalCode.FENCE_FAILURE,
                    owner_lock,
                    evidence,
                    connection,
                )

            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            baseline = market_source.baseline_at_fence(
                subscription,
                fence,
            )
            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            if not _market_recovery._market_baseline_is_authentic(
                market_source,
                baseline,
                subscription,
                fence,
            ):
                return _stop_startup(
                    StartupRefusalCode.BASELINE_FAILURE,
                    owner_lock,
                    evidence,
                    connection,
                )
            assert type(baseline) is _market_recovery.MarketBaselineEvidence
            if not _baseline_matches_authority(
                protection_state,
                fence,
                baseline,
            ):
                return _stop_startup(
                    StartupRefusalCode.BASELINE_FAILURE,
                    owner_lock,
                    evidence,
                    connection,
                )
            operation = _operations.MarketOccurrenceOperation(
                _operations.MarketOperationCoordinates(
                    request.application_generation_id,
                    request.execution_profile_id,
                    scope_id,
                    selected.stream.session_id,
                    selected.stream.acquisition_generation_id,
                    request.market_source_profile_id,
                    selected.stream.stream_generation_id,
                ),
                baseline.occurrence,
            )
            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            result = _unit_of_work.execute_unit_of_work(
                connection,
                operation,
                context,
            )
            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            if result.disposition is _unit_of_work.UnitOfWorkDisposition.COMMITTED:
                if (
                    type(result.successor_context)
                    is not _unit_of_work.UnitOfWorkContext
                    or result.effect_eligibility is not None
                ):
                    return _stop_startup(
                        StartupRefusalCode.BASELINE_FAILURE,
                        owner_lock,
                        evidence,
                        connection,
                    )
                context = result.successor_context
            elif (
                result.disposition
                is not _unit_of_work.UnitOfWorkDisposition.EXACT_REPLAY
            ):
                return _stop_startup(
                    StartupRefusalCode.BASELINE_FAILURE,
                    owner_lock,
                    evidence,
                    connection,
                )

            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            try:
                context, proof = _unit_of_work._m2_reread_cold_context(
                    connection,
                    request.application_generation_id,
                    request.execution_profile_id,
                    request.market_source_profile_id,
                    context.expected_checkpoint,
                )
            except Exception:
                return _stop_startup(
                    StartupRefusalCode.CURRENT_PROOF_FAILURE,
                    owner_lock,
                    evidence,
                    connection,
                )
            if not _owner_is_current(owner_lock, evidence):
                return _stop_startup(
                    StartupRefusalCode.OWNER_LOST,
                    owner_lock,
                    evidence,
                    connection,
                )
            resulting = _active_market_authority(context, proof, scope_id)
            if resulting is None:
                return _stop_startup(
                    StartupRefusalCode.BASELINE_FAILURE,
                    owner_lock,
                    evidence,
                    connection,
                )
            resulting_state, _resulting_selected = resulting
            if (
                resulting_state._market_baseline_required
                or resulting_state._market_exhausted
                or resulting_state._market_occurrence_identity
                != baseline.occurrence.occurrence_id
                or not _proof_has_complete_claimed_reconciliation(proof)
            ):
                return _stop_startup(
                    StartupRefusalCode.BASELINE_FAILURE,
                    owner_lock,
                    evidence,
                    connection,
                )
            source_refusal = _retained_sources_refusal(
                owner_lock,
                evidence,
                market_source,
                ((subscription, fence),),
            )
            if source_refusal is not None:
                return _stop_startup(
                    source_refusal,
                    owner_lock,
                    evidence,
                    connection,
                )
            retained_subscriptions.append((subscription, fence))

        if not _owner_is_current(owner_lock, evidence):
            return _stop_startup(
                StartupRefusalCode.OWNER_LOST,
                owner_lock,
                evidence,
                connection,
            )
        if not _close_connection(connection):
            connection = None
            return _stop_startup(
                StartupRefusalCode.DATASTORE_INTEGRITY,
                owner_lock,
                evidence,
                connection,
            )
        connection = None
        if not _owner_is_current(owner_lock, evidence):
            return _stop_startup(
                StartupRefusalCode.OWNER_LOST,
                owner_lock,
                evidence,
                connection,
            )
        source_refusal = _retained_sources_refusal(
            owner_lock,
            evidence,
            market_source,
            retained_subscriptions,
        )
        if source_refusal is not None:
            return _stop_startup(
                source_refusal,
                owner_lock,
                evidence,
                connection,
            )
        source_refusal = _retained_sources_refusal(
            owner_lock,
            evidence,
            market_source,
            retained_subscriptions,
        )
        if source_refusal is not None:
            return _stop_startup(
                source_refusal,
                owner_lock,
                evidence,
                connection,
            )
        if not _owner_is_current(owner_lock, evidence):
            return _stop_startup(
                StartupRefusalCode.OWNER_LOST,
                owner_lock,
                evidence,
                connection,
            )
        return StartupResult(
            StartupPhase.SERVING,
            StartupDisposition.SERVING,
            None,
            evidence,
            context,
        )
    except Exception:
        return _stop_startup(
            StartupRefusalCode.INTERNAL_INTEGRITY,
            owner_lock,
            evidence,
            connection,
        )


__all__ = (
    "StartupDisposition",
    "StartupPhase",
    "StartupRefusalCode",
    "StartupRequest",
    "StartupResult",
    "start_startup",
)
