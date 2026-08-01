"""RED contracts for venue/execution registry catch-up and recovery hydration.

These tests remain pure and deterministic.  They intentionally require a
recovery-aware seam instead of weakening ``ExecutionSnapshot.bind_verified``'s
broker-authoritative public hydration boundary.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import pytest

import app.execution_core as execution_core
from app.execution_core import (
    AccountId,
    ClaimOccurrenceId,
    ClientOrderId,
    EffectId,
    EffectKind,
    EvidenceReference,
    ExecutionSide,
    ExecutionSnapshot,
    FirstObservationClassification,
    MandateId,
    PositionIntegrity,
    PositionScope,
    PositionState,
    Quantity,
    RecordBrokerFillEvidence,
    RecordDispatchClaim,
    ReleaseVenueLeg,
    RequestOccurrenceId,
    RequestedEffect,
    RootHeadIndex,
    SeenFactIndex,
    SymbolId,
    VenueAttemptState,
    VenueInputId,
    VenueRecoveryDisposition,
    apply_venue_recovery_input,
)
from tests.execution_core import test_venue_recovery as recovery_fixtures
from app.execution_core.venue import _rebuild_book


def _required_api(name: str) -> object:
    value = getattr(execution_core, name, None)
    assert value is not None, f"public execution-core API {name} is required"
    return value


def _catch_up(
    *,
    input_id: str,
    source_execution: ExecutionSnapshot,
) -> object:
    input_type = _required_api("CatchUpExecutionRegistry")
    return input_type(
        input_id=VenueInputId(input_id),
        source_execution=source_execution,
    )


def _bind_recovery_snapshot(
    book: object,
    execution: ExecutionSnapshot,
) -> ExecutionSnapshot:
    binder = _required_api("bind_venue_execution_snapshot")
    result = binder(
        book,
        execution.position,
        execution.integrity,
        execution.root_heads,
        execution.seen_facts,
    )
    assert isinstance(result, ExecutionSnapshot)
    return result


def _raise_materialization(name: str) -> None:
    raise AssertionError(f"{name} history materialized on the catch-up path")


@contextmanager
def _forbid_history_materialization():
    seen_trap = property(lambda _self: _raise_materialization("seen-fact"))
    roots_trap = property(lambda _self: _raise_materialization("root-head"))
    with (
        patch.object(SeenFactIndex, "entries", seen_trap),
        patch.object(RootHeadIndex, "entries", roots_trap),
    ):
        yield


def _register_msft_effect(
    book: object,
    account_execution: ExecutionSnapshot,
) -> tuple[object, PositionScope, ExecutionSnapshot, EffectId]:
    symbol = SymbolId("MSFT")
    position_scope = PositionScope(
        broker=recovery_fixtures.BROKER,
        environment=recovery_fixtures.ENVIRONMENT,
        account=recovery_fixtures.ACCOUNT,
        symbol_id=symbol,
    )
    execution = ExecutionSnapshot.bind_verified(
        PositionState.flat(position_scope),
        PositionIntegrity.CONSISTENT,
        RootHeadIndex.empty(position_scope),
        account_execution.seen_facts,
    )
    effect_id = EffectId("binding-recovery-msft-effect")
    registered = apply_venue_recovery_input(
        book,
        execution,
        RequestedEffect(
            input_id=VenueInputId("binding-recovery-msft-request"),
            effect_id=effect_id,
            request_occurrence_id=RequestOccurrenceId(
                "binding-recovery-msft-occurrence"
            ),
            mandate_id=MandateId("binding-recovery-msft-mandate"),
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId("binding-recovery-msft-client"),
            symbol_id=symbol,
            side=ExecutionSide.BUY,
            quantity=Quantity(4),
            economic_scope=b"MSFT|BUY|binding-recovery",
        ),
    )
    assert registered.disposition is VenueRecoveryDisposition.APPLIED
    return registered.book, position_scope, execution, effect_id


def _matching_broker_evidence(
    *,
    source: str,
    root: str,
) -> RecordBrokerFillEvidence:
    return RecordBrokerFillEvidence(
        input_id=VenueInputId(f"{source}-input"),
        effect_id=recovery_fixtures.EFFECT,
        leg_key=recovery_fixtures.LEG_A,
        prior_cumulative_quantity=Quantity(0),
        resulting_cumulative_quantity=Quantity(4),
        fact=recovery_fixtures._broker_fill(
            source,
            root,
            quantity=4,
        ),
        evidence_digest=b"\xc1" * 32,
    )


def test_cross_symbol_catch_up_after_human_attestation_is_indexed() -> None:
    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, msft_scope, stale_msft, _ = _register_msft_effect(
        book,
        aapl_execution,
    )
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="cross-symbol-human"),
        input_id="cross-symbol-human-attestation",
    )
    assert attested.disposition is VenueRecoveryDisposition.APPLIED

    with pytest.raises(ValueError, match="broker-authoritative"):
        ExecutionSnapshot.bind_verified(
            PositionState.flat(msft_scope),
            PositionIntegrity.CONSISTENT,
            RootHeadIndex.empty(msft_scope),
            attested.execution.seen_facts,
        )

    item = _catch_up(
        input_id="catch-up-msft-after-human",
        source_execution=attested.execution,
    )
    with _forbid_history_materialization():
        rebound = apply_venue_recovery_input(attested.book, stale_msft, item)

    assert rebound.disposition is VenueRecoveryDisposition.APPLIED
    assert rebound.quantity_delta == 0
    assert rebound.execution.position.scope == msft_scope
    assert (
        rebound.execution.position.commitment == stale_msft.position.commitment
    )
    assert (
        rebound.execution.root_heads.commitment
        == stale_msft.root_heads.commitment
    )
    assert (
        rebound.execution.seen_facts.commitment
        == attested.execution.seen_facts.commitment
    )
    assert rebound.book._execution_matches(rebound.execution, msft_scope)


def test_cross_symbol_catch_up_after_zero_economic_corroboration() -> None:
    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, msft_scope, stale_msft, _ = _register_msft_effect(
        book,
        aapl_execution,
    )
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="cross-symbol-corroborated"),
        input_id="cross-symbol-corroborated-attestation",
    )
    evidence = _matching_broker_evidence(
        source="cross-symbol-corroboration-source",
        root="cross-symbol-corroboration-root",
    )
    corroborated = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        evidence,
    )
    observation = corroborated.execution.seen_facts.get(evidence.fact.key)
    assert observation is not None
    assert (
        observation.classification
        is FirstObservationClassification.CORROBORATED_ZERO_ECONOMIC
    )

    with pytest.raises(ValueError, match="broker-authoritative|zero-economic"):
        ExecutionSnapshot.bind_verified(
            PositionState.flat(msft_scope),
            PositionIntegrity.CONSISTENT,
            RootHeadIndex.empty(msft_scope),
            corroborated.execution.seen_facts,
        )

    item = _catch_up(
        input_id="catch-up-msft-after-corroboration",
        source_execution=corroborated.execution,
    )
    with _forbid_history_materialization():
        rebound = apply_venue_recovery_input(
            corroborated.book,
            stale_msft,
            item,
        )

    assert rebound.disposition is VenueRecoveryDisposition.APPLIED
    assert rebound.execution.position.scope == msft_scope
    assert (
        rebound.execution.seen_facts.commitment
        == corroborated.execution.seen_facts.commitment
    )
    assert rebound.book._execution_matches(rebound.execution, msft_scope)


def test_same_symbol_independent_truth_catches_up_and_blocks_release() -> None:
    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    fact = recovery_fixtures._broker_fill(
        "independent-catch-up-source",
        "independent-catch-up-root",
        quantity=2,
    )
    ahead = recovery_fixtures._apply_broker(execution, fact)
    item = _catch_up(
        input_id="catch-up-independent-aapl-truth",
        source_execution=ahead,
    )

    with _forbid_history_materialization():
        caught_up = apply_venue_recovery_input(book, execution, item)

    assert (
        caught_up.disposition
        is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    )
    assert caught_up.quantity_delta == 0
    assert caught_up.execution.position.raw_quantity == 2
    assert caught_up.book._execution_matches(
        caught_up.execution,
        recovery_fixtures.POSITION_SCOPE,
    )

    record_type = _required_api("ExecutionRegistryReconciliationRecord")
    records = [
        record
        for record in caught_up.book.execution_reconciliations
        if isinstance(record, record_type)
    ]
    assert len(records) == 1
    record = records[0]
    assert record.input_id == item.input_id
    assert record.position_scope == recovery_fixtures.POSITION_SCOPE
    assert record.canonical_applied is True
    assert record.reason.strip()
    assert (
        record.prior_registry_commitment
        == execution.seen_facts.commitment
    )
    assert (
        record.resulting_registry_commitment
        == ahead.seen_facts.commitment
    )
    assert (
        record.prior_position_commitment == execution.position.commitment
    )
    assert record.resulting_position_commitment == ahead.position.commitment
    assert (
        record.prior_root_heads_commitment
        == execution.root_heads.commitment
    )
    assert (
        record.resulting_root_heads_commitment
        == ahead.root_heads.commitment
    )

    blocked = apply_venue_recovery_input(
        caught_up.book,
        caught_up.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("release-with-unattributed-canonical-truth"),
            effect_id=recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_A,
            claim_occurrence_id=recovery_fixtures.CLAIM,
            venue_cumulative_quantity=Quantity(0),
            broker_terminal_state=VenueAttemptState.CANCELED,
            actor=recovery_fixtures.ACTOR,
            reason="unattributed canonical truth must block release",
            evidence_reference=EvidenceReference(
                "unattributed-canonical-truth-release"
            ),
            closure_id=execution_core.ClosureId(
                "unattributed-canonical-truth-closure"
            ),
            evidence_digest=b"\xc2" * 32,
        ),
    )
    assert (
        blocked.disposition
        is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    )
    assert blocked.book.closure_head(recovery_fixtures.LEG_A) is None


def test_catch_up_refuses_non_prefix_and_cross_account_sources() -> None:
    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    first_fact = recovery_fixtures._broker_fill(
        "prefix-source",
        "prefix-root",
        quantity=1,
    )
    advanced = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("record-prefix-fact"),
            effect_id=recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(1),
            fact=first_fact,
            evidence_digest=b"\xc3" * 32,
        ),
    )
    divergent = recovery_fixtures._apply_broker(
        execution,
        recovery_fixtures._broker_fill(
            "divergent-source",
            "divergent-root",
            quantity=1,
        ),
    )
    non_prefix_item = _catch_up(
        input_id="reject-non-prefix-registry",
        source_execution=divergent,
    )
    with _forbid_history_materialization():
        non_prefix = apply_venue_recovery_input(
            advanced.book,
            advanced.execution,
            non_prefix_item,
        )
    assert (
        non_prefix.disposition
        is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    )
    assert non_prefix.book == advanced.book
    assert non_prefix.execution == advanced.execution

    foreign_scope = PositionScope(
        broker=recovery_fixtures.BROKER,
        environment=recovery_fixtures.ENVIRONMENT,
        account=AccountId("different-paper-account"),
        symbol_id=recovery_fixtures.SYMBOL,
    )
    cross_account_item = _catch_up(
        input_id="reject-cross-account-registry",
        source_execution=ExecutionSnapshot.flat(foreign_scope),
    )
    with _forbid_history_materialization():
        cross_account = apply_venue_recovery_input(
            advanced.book,
            advanced.execution,
            cross_account_item,
        )
    assert cross_account.disposition is VenueRecoveryDisposition.REFUSED
    assert cross_account.book == advanced.book
    assert cross_account.execution == advanced.execution


def test_recovery_hydration_restores_a_human_root_but_strict_bind_stays_strict() -> (
    None
):
    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    attested = recovery_fixtures._ingest(
        book,
        execution,
        recovery_fixtures._human_fill(input_suffix="restart-human"),
        input_id="restart-human-attestation",
    )

    with pytest.raises(ValueError, match="broker-authoritative"):
        ExecutionSnapshot.bind_verified(
            attested.execution.position,
            attested.execution.integrity,
            attested.execution.root_heads,
            attested.execution.seen_facts,
        )

    hydrated = _bind_recovery_snapshot(attested.book, attested.execution)
    assert hydrated.position.commitment == attested.execution.position.commitment
    assert (
        hydrated.root_heads.commitment
        == attested.execution.root_heads.commitment
    )
    assert (
        hydrated.seen_facts.commitment
        == attested.execution.seen_facts.commitment
    )
    assert hydrated.integrity is attested.execution.integrity
    assert attested.book._execution_matches(
        hydrated,
        recovery_fixtures.POSITION_SCOPE,
    )


def test_recovery_hydration_restores_zero_economic_corroboration() -> None:
    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    attested = recovery_fixtures._ingest(
        book,
        execution,
        recovery_fixtures._human_fill(input_suffix="restart-corroborated"),
        input_id="restart-corroborated-attestation",
    )
    evidence = _matching_broker_evidence(
        source="restart-corroboration-source",
        root="restart-corroboration-root",
    )
    corroborated = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        evidence,
    )
    observation = corroborated.execution.seen_facts.get(evidence.fact.key)
    assert observation is not None
    assert (
        observation.classification
        is FirstObservationClassification.CORROBORATED_ZERO_ECONOMIC
    )

    hydrated = _bind_recovery_snapshot(
        corroborated.book,
        corroborated.execution,
    )
    assert (
        hydrated.seen_facts.commitment
        == corroborated.execution.seen_facts.commitment
    )
    assert corroborated.book._execution_matches(
        hydrated,
        recovery_fixtures.POSITION_SCOPE,
    )


def test_recovery_hydration_rejects_missing_or_forged_book_provenance() -> None:
    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    attested = recovery_fixtures._ingest(
        book,
        execution,
        recovery_fixtures._human_fill(input_suffix="trusted-hydration"),
        input_id="trusted-hydration-attestation",
    )

    missing_human_provenance = _rebuild_book(
        book,
        execution_registry_commitment=(
            attested.execution.seen_facts.commitment
        ),
        execution_bindings=attested.book.execution_bindings,
    )
    with pytest.raises(ValueError, match="provenance|coverage|human"):
        _bind_recovery_snapshot(
            missing_human_provenance,
            attested.execution,
        )

    other_book, other_execution = recovery_fixtures._seed_needs_review(
        capacity=4
    )
    other_attested = recovery_fixtures._ingest(
        other_book,
        other_execution,
        recovery_fixtures._human_fill(input_suffix="forged-hydration"),
        input_id="forged-hydration-attestation",
    )
    forged_coverage = _rebuild_book(
        other_attested.book,
        execution_registry_commitment=(
            attested.execution.seen_facts.commitment
        ),
        execution_bindings=attested.book.execution_bindings,
    )
    with pytest.raises(ValueError, match="provenance|coverage|root"):
        _bind_recovery_snapshot(forged_coverage, attested.execution)

    evidence = _matching_broker_evidence(
        source="missing-corroboration-source",
        root="missing-corroboration-root",
    )
    corroborated = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        evidence,
    )
    missing_corroboration = _rebuild_book(
        attested.book,
        execution_registry_commitment=(
            corroborated.execution.seen_facts.commitment
        ),
        execution_bindings=corroborated.book.execution_bindings,
    )
    with pytest.raises(ValueError, match="provenance|corroboration|broker"):
        _bind_recovery_snapshot(
            missing_corroboration,
            corroborated.execution,
        )


def test_cross_symbol_projection_does_not_mutate_target_economics() -> None:
    """Pin the target symbol even when the source symbol carries economics."""

    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, msft_scope, stale_msft, effect_id = _register_msft_effect(
        book,
        aapl_execution,
    )
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="projection-economics"),
        input_id="projection-economics-attestation",
    )
    projected = apply_venue_recovery_input(
        attested.book,
        stale_msft,
        _catch_up(
            input_id="projection-does-not-cross-wire-economics",
            source_execution=attested.execution,
        ),
    )
    claim = apply_venue_recovery_input(
        projected.book,
        projected.execution,
        RecordDispatchClaim(
            input_id=VenueInputId("claim-projected-msft-effect"),
            effect_id=effect_id,
            claim_occurrence_id=ClaimOccurrenceId("claim-projected-msft"),
        ),
    )

    assert projected.execution.position.scope == msft_scope
    assert projected.execution.position.raw_quantity == 0
    assert projected.execution.root_heads.count == 0
    assert claim.disposition is VenueRecoveryDisposition.APPLIED
