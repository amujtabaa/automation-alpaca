"""RED contracts for venue/execution registry catch-up and recovery hydration.

These tests remain pure and deterministic.  They intentionally require a
recovery-aware seam instead of weakening ``ExecutionSnapshot.bind_verified``'s
broker-authoritative public hydration boundary.
"""

from __future__ import annotations

from copy import copy
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from unittest.mock import patch

import pytest

import app.execution_core as execution_core
import app.execution_core.venue as venue_module
from app.execution_core import (
    AccountId,
    AcceptanceProofKind,
    BrokerEffectState,
    ClaimOccurrenceId,
    ClientOrderId,
    CloseAcceptanceSet,
    EffectId,
    EffectKind,
    EvidenceReference,
    ExecutionSide,
    ExecutionSnapshot,
    FirstObservationClassification,
    MandateId,
    OrderId,
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
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    apply_venue_recovery_input,
)
from tests.execution_core import test_venue_recovery as recovery_fixtures
from app.execution_core.venue import _audit_hydrate_book


def _required_api(name: str) -> object:
    value = getattr(execution_core, name, None)
    assert value is not None, f"public execution-core API {name} is required"
    return value


def _catch_up(
    *,
    book: VenueRecoveryBook,
    input_id: str,
    target_execution: ExecutionSnapshot,
    source_execution: ExecutionSnapshot,
) -> object:
    input_type = _required_api("CatchUpExecutionRegistry")
    checkpoint_type = _required_api("VenueExecutionCheckpoint")
    assert book.execution_registry_count is not None
    assert book.execution_registry_commitment is not None
    return input_type(
        input_id=VenueInputId(input_id),
        target_checkpoint=checkpoint_type.from_execution(target_execution),
        prior_account_registry_count=book.execution_registry_count,
        prior_account_registry_commitment=book.execution_registry_commitment,
        prior_source_binding=book.execution_binding(source_execution.position.scope),
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
        expected_reconciliation_cursor=execution.reconciliation_cursor,
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


@contextmanager
def _forbid_recursive_snapshot_representation():
    with patch.object(
        ExecutionSnapshot,
        "__repr__",
        lambda _self: _raise_materialization("execution-snapshot repr"),
    ):
        yield


@contextmanager
def _forbid_venue_audit_views():
    """Tripwire every history-materializing venue-book compatibility view."""

    audit_views = (
        "effects",
        "claims",
        "owners",
        "active_attempts",
        "closure_heads",
        "execution_bindings",
        "input_records",
        "closure_history",
        "human_coverages",
        "broker_coverages",
        "reconciliations",
        "execution_reconciliations",
    )
    with ExitStack() as stack:
        for name in audit_views:
            trap = property(
                lambda _self, view=name: _raise_materialization(f"venue {view}")
            )
            stack.enter_context(patch.object(VenueRecoveryBook, name, trap))
        stack.enter_context(
            patch.object(
                VenueRecoveryBook,
                "effect",
                lambda _self, _effect_id: _raise_materialization("venue effect audit"),
            )
        )
        yield


def _register_msft_effect(
    book: object,
    account_execution: ExecutionSnapshot,
) -> tuple[object, PositionScope, ExecutionSnapshot, EffectId]:
    return _register_symbol_effect(
        book,
        account_execution,
        symbol_value="MSFT",
        identity_prefix="binding-recovery-msft",
    )


def _register_symbol_effect(
    book: object,
    account_execution: ExecutionSnapshot,
    *,
    symbol_value: str,
    identity_prefix: str,
) -> tuple[object, PositionScope, ExecutionSnapshot, EffectId]:
    symbol = SymbolId(symbol_value)
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
    effect_id = EffectId(f"{identity_prefix}-effect")
    registered = apply_venue_recovery_input(
        book,
        execution,
        RequestedEffect(
            input_id=VenueInputId(f"{identity_prefix}-request"),
            effect_id=effect_id,
            request_occurrence_id=RequestOccurrenceId(f"{identity_prefix}-occurrence"),
            mandate_id=MandateId(f"{identity_prefix}-mandate"),
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId(f"{identity_prefix}-client"),
            symbol_id=symbol,
            side=ExecutionSide.BUY,
            quantity=Quantity(4),
            economic_scope=f"{symbol_value}|BUY|{identity_prefix}".encode(),
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
        book=attested.book,
        input_id="catch-up-msft-after-human",
        target_execution=stale_msft,
        source_execution=attested.execution,
    )
    with _forbid_history_materialization():
        rebound = apply_venue_recovery_input(attested.book, stale_msft, item)

    assert rebound.disposition is VenueRecoveryDisposition.APPLIED
    assert rebound.quantity_delta == 0
    assert rebound.execution.position.scope == msft_scope
    assert rebound.execution.position.commitment == stale_msft.position.commitment
    assert rebound.execution.root_heads.commitment == stale_msft.root_heads.commitment
    assert (
        rebound.execution.seen_facts.commitment
        == attested.execution.seen_facts.commitment
    )
    assert rebound.book._execution_matches(rebound.execution, msft_scope)
    outcome = rebound.book._execution_reconciliation_for_input(item.input_id)
    assert outcome is not None
    assert outcome.position_scope == msft_scope
    assert outcome.attribution_resolved is True
    hydrated = _audit_hydrate_book(rebound.book, rebound.execution)
    assert hydrated._execution_matches(rebound.execution, msft_scope)
    assert hydrated._execution_reconciliation_for_input(item.input_id) == outcome


def test_mixed_account_history_projects_to_a_third_symbol_and_hydrates() -> None:
    """A target lag may contain already-canonical facts from multiple symbols."""

    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, msft_scope, stale_msft, _ = _register_msft_effect(
        book,
        aapl_execution,
    )
    registered, goog_scope, stale_goog, _ = _register_symbol_effect(
        registered,
        aapl_execution,
        symbol_value="GOOG",
        identity_prefix="binding-recovery-goog",
    )
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="three-symbol-aapl"),
        input_id="three-symbol-aapl-attestation",
    )
    synced_msft = apply_venue_recovery_input(
        attested.book,
        stale_msft,
        _catch_up(
            book=attested.book,
            input_id="three-symbol-sync-msft",
            target_execution=stale_msft,
            source_execution=attested.execution,
        ),
    )
    assert synced_msft.disposition is VenueRecoveryDisposition.APPLIED

    msft_fact = recovery_fixtures._broker_fill(
        "three-symbol-msft-source",
        "three-symbol-msft-root",
        quantity=1,
    )
    msft_fact = replace(
        msft_fact,
        scope=replace(msft_fact.scope, symbol_id=msft_scope.symbol_id),
    )
    msft_ahead = recovery_fixtures._apply_broker(synced_msft.execution, msft_fact)
    source_advance = apply_venue_recovery_input(
        synced_msft.book,
        attested.execution,
        _catch_up(
            book=synced_msft.book,
            input_id="three-symbol-msft-source-advance",
            target_execution=attested.execution,
            source_execution=msft_ahead,
        ),
    )
    assert (
        source_advance.disposition
        is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    )

    projected_goog = apply_venue_recovery_input(
        source_advance.book,
        stale_goog,
        _catch_up(
            book=source_advance.book,
            input_id="three-symbol-project-goog",
            target_execution=stale_goog,
            source_execution=msft_ahead,
        ),
    )

    assert projected_goog.disposition is VenueRecoveryDisposition.APPLIED
    assert projected_goog.execution.position.scope == goog_scope
    assert projected_goog.execution.seen_facts.count == 2
    hydrated = _audit_hydrate_book(projected_goog.book, projected_goog.execution)
    assert hydrated._execution_matches(projected_goog.execution, goog_scope)


def test_cross_symbol_catch_up_does_not_serialize_retained_registry_history() -> None:
    """Live input indexing must commit compact proof, not recursive snapshots."""

    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, _, stale_msft, _ = _register_msft_effect(book, aapl_execution)
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="bounded-catch-up-repr"),
        input_id="bounded-catch-up-repr-attestation",
    )
    item = _catch_up(
        book=attested.book,
        input_id="bounded-catch-up-repr-input",
        target_execution=stale_msft,
        source_execution=attested.execution,
    )

    with _forbid_recursive_snapshot_representation():
        rebound = apply_venue_recovery_input(attested.book, stale_msft, item)

    assert rebound.disposition is VenueRecoveryDisposition.APPLIED
    assert rebound.quantity_delta == 0


def test_live_lifecycle_reducers_do_not_materialize_audit_views() -> None:
    """Registration through closure advances only bounded persistent deltas."""

    with _forbid_venue_audit_views():
        book, execution, _ = recovery_fixtures._released_state()

    assert book.active_attempt(recovery_fixtures.LEG_A) is None
    assert book.closure_head(recovery_fixtures.LEG_A) is not None
    assert book._execution_pair_matches_fast(execution)


def test_finalization_and_scope_demotion_use_indexed_current_state() -> None:
    """Finality and stale authority must not scan historical lifecycle views."""

    book, execution, _ = recovery_fixtures._released_state()
    proof = recovery_fixtures._acceptance_proof(
        book,
        AcceptanceProofKind.COVERED_RECONCILIATION,
        "bounded-lifecycle-finalization",
    )
    with _forbid_venue_audit_views():
        finalized = apply_venue_recovery_input(
            book,
            execution,
            CloseAcceptanceSet(
                input_id=VenueInputId("bounded-lifecycle-close-acceptance"),
                effect_id=recovery_fixtures.EFFECT,
                proof=proof,
            ),
        )
    assert finalized.disposition is VenueRecoveryDisposition.APPLIED
    finalized_effect = finalized.book.effect(recovery_fixtures.EFFECT)
    assert finalized_effect is not None
    assert finalized_effect.state is BrokerEffectState.OPERATOR_RECONCILED

    mismatch = RecordBrokerFillEvidence(
        input_id=VenueInputId("bounded-lifecycle-demotion"),
        effect_id=recovery_fixtures.EFFECT,
        leg_key=recovery_fixtures.LEG_A,
        prior_cumulative_quantity=Quantity(0),
        resulting_cumulative_quantity=Quantity(4),
        fact=recovery_fixtures._broker_fill(
            "bounded-lifecycle-demotion-source",
            "bounded-lifecycle-demotion-root",
            quantity=4,
            units=101,
        ),
        evidence_digest=b"\x9a" * 32,
    )
    with _forbid_venue_audit_views():
        demoted = apply_venue_recovery_input(
            finalized.book,
            finalized.execution,
            mismatch,
        )
    assert demoted.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    demoted_effect = demoted.book.effect(recovery_fixtures.EFFECT)
    assert demoted_effect is not None
    assert demoted_effect.state is BrokerEffectState.NEEDS_REVIEW


def test_cross_symbol_catch_up_advances_from_intermediate_book_registry() -> None:
    """A lagging symbol can traverse a valid intermediate account prefix."""

    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, _, stale_msft, _ = _register_msft_effect(book, aapl_execution)
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="intermediate-prefix-one"),
        input_id="intermediate-prefix-human",
    )
    ahead = recovery_fixtures._apply_broker(
        attested.execution,
        recovery_fixtures._broker_fill(
            "intermediate-prefix-broker-source",
            "intermediate-prefix-broker-root",
            quantity=1,
        ),
    )

    rebound = apply_venue_recovery_input(
        attested.book,
        stale_msft,
        _catch_up(
            book=attested.book,
            input_id="intermediate-prefix-msft-catch-up",
            target_execution=stale_msft,
            source_execution=ahead,
        ),
    )

    assert stale_msft.seen_facts.count == 0
    assert attested.execution.seen_facts.count == 1
    assert ahead.seen_facts.count == 2
    assert rebound.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert rebound.execution.seen_facts.count == 2
    assert rebound.book != attested.book
    assert len(rebound.book.execution_reconciliations) == (
        len(attested.book.execution_reconciliations) + 1
    )
    assert rebound.quantity_delta == 0


def test_cross_symbol_catch_up_uses_bounded_suffix_scope_proof() -> None:
    """Live catch-up must not walk the retained account-registry suffix."""

    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, _, stale_msft, _ = _register_msft_effect(book, aapl_execution)
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="bounded-suffix-one"),
        input_id="bounded-suffix-human",
    )
    ahead = recovery_fixtures._apply_broker(
        attested.execution,
        recovery_fixtures._broker_fill(
            "bounded-suffix-broker-source",
            "bounded-suffix-broker-root",
            quantity=1,
        ),
    )

    with patch.object(
        SeenFactIndex,
        "observation_at",
        side_effect=AssertionError("live catch-up walked registry history"),
    ):
        rebound = apply_venue_recovery_input(
            attested.book,
            stale_msft,
            _catch_up(
                book=attested.book,
                input_id="bounded-suffix-msft-catch-up",
                target_execution=stale_msft,
                source_execution=ahead,
            ),
        )

    assert rebound.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert rebound.execution.seen_facts.count == ahead.seen_facts.count
    assert rebound.quantity_delta == 0


def test_catch_up_rejects_a_mixed_symbol_registry_suffix() -> None:
    """A multi-symbol suffix cannot be attributed to its final symbol."""

    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, msft_scope, stale_msft, _ = _register_msft_effect(
        book,
        aapl_execution,
    )
    aapl_ahead = recovery_fixtures._apply_broker(
        aapl_execution,
        recovery_fixtures._broker_fill(
            "mixed-suffix-aapl-source",
            "mixed-suffix-aapl-root",
            quantity=1,
        ),
    )
    msft_at_aapl_registry = ExecutionSnapshot.bind_verified(
        PositionState.flat(msft_scope),
        PositionIntegrity.CONSISTENT,
        RootHeadIndex.empty(msft_scope),
        aapl_ahead.seen_facts,
    )
    msft_fact = recovery_fixtures._broker_fill(
        "mixed-suffix-msft-source",
        "mixed-suffix-msft-root",
        quantity=1,
    )
    msft_fact = replace(
        msft_fact,
        scope=replace(msft_fact.scope, symbol_id=msft_scope.symbol_id),
    )
    mixed_source = recovery_fixtures._apply_broker(
        msft_at_aapl_registry,
        msft_fact,
    )

    blocked = apply_venue_recovery_input(
        registered,
        stale_msft,
        _catch_up(
            book=registered,
            input_id="reject-mixed-symbol-registry-suffix",
            target_execution=stale_msft,
            source_execution=mixed_source,
        ),
    )

    assert blocked.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert blocked.book is registered
    assert blocked.execution is stale_msft
    assert registered.execution_registry_count == 0
    assert mixed_source.seen_facts.count == 2


def test_catch_up_refuses_an_unbound_source_that_reuses_an_owned_order_id() -> None:
    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    msft_scope = PositionScope(
        broker=recovery_fixtures.BROKER,
        environment=recovery_fixtures.ENVIRONMENT,
        account=recovery_fixtures.ACCOUNT,
        symbol_id=SymbolId("MSFT-UNREGISTERED"),
    )
    conflicting_fact = replace(
        recovery_fixtures._broker_fill(
            "cross-owner-unbound-source",
            "cross-owner-unbound-root",
            quantity=1,
        ),
        scope=recovery_fixtures._execution_scope(symbol=msft_scope.symbol_id),
    )
    source = recovery_fixtures._apply_broker(
        ExecutionSnapshot.flat(msft_scope),
        conflicting_fact,
    )

    refused = apply_venue_recovery_input(
        book,
        aapl_execution,
        _catch_up(
            book=book,
            input_id="reject-unbound-cross-owner-source",
            target_execution=aapl_execution,
            source_execution=source,
        ),
    )

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.book is book
    assert refused.execution is aapl_execution


def test_unresolved_bound_source_blocks_every_account_effect_until_attributed() -> None:
    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, msft_scope, stale_msft, _ = _register_msft_effect(
        book,
        aapl_execution,
    )
    conflicting_fact = replace(
        recovery_fixtures._broker_fill(
            "cross-owner-bound-source",
            "cross-owner-bound-root",
            quantity=1,
        ),
        scope=recovery_fixtures._execution_scope(symbol=msft_scope.symbol_id),
    )
    source = recovery_fixtures._apply_broker(stale_msft, conflicting_fact)
    caught_up = apply_venue_recovery_input(
        registered,
        aapl_execution,
        _catch_up(
            book=registered,
            input_id="unresolved-bound-cross-owner-source",
            target_execution=aapl_execution,
            source_execution=source,
        ),
    )

    assert caught_up.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert caught_up.book._has_unresolved_execution_reconciliation(msft_scope)
    assert caught_up.book._has_unresolved_execution_reconciliation(
        recovery_fixtures.POSITION_SCOPE
    )
    hydrated = _audit_hydrate_book(caught_up.book, caught_up.execution)
    assert hydrated._has_unresolved_execution_reconciliation(msft_scope)
    assert hydrated._has_unresolved_execution_reconciliation(
        recovery_fixtures.POSITION_SCOPE
    )
    blocked = apply_venue_recovery_input(
        caught_up.book,
        caught_up.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("release-after-bound-cross-owner-catch-up"),
            effect_id=recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_A,
            claim_occurrence_id=recovery_fixtures.CLAIM,
            venue_cumulative_quantity=Quantity(0),
            broker_terminal_state=VenueAttemptState.CANCELED,
            actor=recovery_fixtures.ACTOR,
            reason="unattributed account truth must block sibling release",
            evidence_reference=EvidenceReference("bound-cross-owner-release-evidence"),
            closure_id=execution_core.ClosureId("bound-cross-owner-release-closure"),
            evidence_digest=b"\xc7" * 32,
        ),
    )
    assert blocked.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert blocked.book.closure_head(recovery_fixtures.LEG_A) is None


def test_account_wide_catch_up_revokes_already_finalized_sibling_authority() -> None:
    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, msft_scope, msft_execution, _ = _register_msft_effect(
        book,
        aapl_execution,
    )
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="pre-account-wide-conflict"),
        input_id="pre-account-wide-conflict-attestation",
    )
    synced_msft = apply_venue_recovery_input(
        attested.book,
        msft_execution,
        _catch_up(
            book=attested.book,
            input_id="sync-msft-before-account-wide-conflict",
            target_execution=msft_execution,
            source_execution=attested.execution,
        ),
    )
    assert synced_msft.disposition is VenueRecoveryDisposition.APPLIED
    released = apply_venue_recovery_input(
        synced_msft.book,
        attested.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("release-before-account-wide-conflict"),
            effect_id=recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_A,
            claim_occurrence_id=recovery_fixtures.CLAIM,
            venue_cumulative_quantity=Quantity(4),
            broker_terminal_state=VenueAttemptState.CANCELED,
            actor=recovery_fixtures.ACTOR,
            reason="exact parity before later account-wide conflict",
            evidence_reference=EvidenceReference("pre-account-conflict-release"),
            closure_id=execution_core.ClosureId("pre-account-conflict-closure"),
            evidence_digest=b"\xc8" * 32,
        ),
    )
    finalized = apply_venue_recovery_input(
        released.book,
        released.execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("close-before-account-wide-conflict"),
            effect_id=recovery_fixtures.EFFECT,
            proof=recovery_fixtures._acceptance_proof(
                released.book,
                AcceptanceProofKind.COVERED_RECONCILIATION,
                "proof-before-account-wide-conflict",
            ),
        ),
    )
    assert (
        finalized.book.effect(recovery_fixtures.EFFECT).state
        is BrokerEffectState.OPERATOR_RECONCILED
    )
    conflicting_fact = replace(
        recovery_fixtures._broker_fill(
            "post-final-account-conflict-source",
            "post-final-account-conflict-root",
            quantity=1,
        ),
        scope=recovery_fixtures._execution_scope(symbol=msft_scope.symbol_id),
    )
    source = recovery_fixtures._apply_broker(synced_msft.execution, conflicting_fact)

    caught_up = apply_venue_recovery_input(
        finalized.book,
        finalized.execution,
        _catch_up(
            book=finalized.book,
            input_id="post-final-account-conflict-catch-up",
            target_execution=finalized.execution,
            source_execution=source,
        ),
    )

    assert caught_up.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert caught_up.book._has_unresolved_execution_reconciliation(
        recovery_fixtures.POSITION_SCOPE
    )
    effect = caught_up.book.effect(recovery_fixtures.EFFECT)
    assert effect is not None
    assert effect.state is BrokerEffectState.NEEDS_REVIEW
    assert effect.acceptance_set_state is execution_core.AcceptanceSetState.CLOSED
    hydrated = _audit_hydrate_book(caught_up.book, caught_up.execution)
    hydrated_effect = hydrated.effect(recovery_fixtures.EFFECT)
    assert hydrated_effect is not None
    assert hydrated_effect.state is BrokerEffectState.NEEDS_REVIEW


def test_same_symbol_catch_up_uses_indexed_coverage_provenance() -> None:
    """Live catch-up must not rescan retained human or broker coverages."""

    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    attested = recovery_fixtures._ingest(
        book,
        execution,
        recovery_fixtures._human_fill(input_suffix="indexed-provenance-human"),
        input_id="indexed-provenance-human-input",
    )
    ahead = recovery_fixtures._apply_broker(
        attested.execution,
        recovery_fixtures._broker_fill(
            "indexed-provenance-broker-source",
            "indexed-provenance-broker-root",
            quantity=1,
        ),
    )

    with patch.object(
        venue_module,
        "_execution_head_matches_fact",
        side_effect=AssertionError("live catch-up rescanned coverage provenance"),
    ):
        caught_up = apply_venue_recovery_input(
            attested.book,
            attested.execution,
            _catch_up(
                book=attested.book,
                input_id="indexed-provenance-catch-up",
                target_execution=attested.execution,
                source_execution=ahead,
            ),
        )

    assert caught_up.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert caught_up.execution.seen_facts.count == ahead.seen_facts.count
    assert caught_up.quantity_delta == 0


def test_applied_catch_up_replays_after_later_healthy_registry_advance() -> None:
    """An exact technical replay cannot be invalidated by later healthy truth."""

    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, _, stale_msft, _ = _register_msft_effect(book, aapl_execution)
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="catch-up-replay-human"),
        input_id="catch-up-replay-human-input",
    )
    original_item = _catch_up(
        book=attested.book,
        input_id="catch-up-replay-original",
        target_execution=stale_msft,
        source_execution=attested.execution,
    )
    first = apply_venue_recovery_input(
        attested.book,
        stale_msft,
        original_item,
    )
    assert first.disposition is VenueRecoveryDisposition.APPLIED

    evidence = _matching_broker_evidence(
        source="catch-up-replay-corroboration",
        root="catch-up-replay-corroboration-root",
    )
    corroborated = apply_venue_recovery_input(
        first.book,
        attested.execution,
        evidence,
    )
    assert corroborated.disposition is VenueRecoveryDisposition.APPLIED
    advanced = apply_venue_recovery_input(
        corroborated.book,
        first.execution,
        _catch_up(
            book=corroborated.book,
            input_id="catch-up-replay-later-advance",
            target_execution=first.execution,
            source_execution=corroborated.execution,
        ),
    )
    assert advanced.disposition is VenueRecoveryDisposition.APPLIED

    stale_source_trap = AssertionError("exact replay consulted stale source truth")
    with (
        patch.object(SeenFactIndex, "has_prefix", side_effect=stale_source_trap),
        patch.object(
            SeenFactIndex,
            "suffix_belongs_to",
            side_effect=stale_source_trap,
        ),
        patch.object(
            venue_module.VenueRecoveryBook,
            "_execution_symbol_matches",
            side_effect=stale_source_trap,
        ),
    ):
        replayed = apply_venue_recovery_input(
            advanced.book,
            advanced.execution,
            original_item,
        )

    assert replayed.disposition is VenueRecoveryDisposition.EXACT_REPLAY
    assert replayed.book is advanced.book
    assert replayed.execution is advanced.execution
    assert replayed.quantity_delta == 0


def test_retained_catch_up_replay_is_bound_to_its_declared_target_scope() -> None:
    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, _, stale_msft, _ = _register_msft_effect(book, aapl_execution)
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="target-bound-replay-human"),
        input_id="target-bound-replay-attestation",
    )
    item = _catch_up(
        book=attested.book,
        input_id="target-bound-replay-catch-up",
        target_execution=stale_msft,
        source_execution=attested.execution,
    )
    first = apply_venue_recovery_input(attested.book, stale_msft, item)
    assert first.disposition is VenueRecoveryDisposition.APPLIED

    wrong_runtime_target = apply_venue_recovery_input(
        first.book,
        attested.execution,
        item,
    )
    assert wrong_runtime_target.disposition is VenueRecoveryDisposition.REFUSED
    assert wrong_runtime_target.book is first.book
    assert wrong_runtime_target.execution is attested.execution

    changed_command = replace(
        item,
        target_checkpoint=type(item.target_checkpoint).from_execution(
            attested.execution
        ),
    )
    conflicted = apply_venue_recovery_input(
        first.book,
        first.execution,
        changed_command,
    )
    assert conflicted.disposition is VenueRecoveryDisposition.CONFLICT
    assert conflicted.book is first.book
    assert conflicted.execution is first.execution


def test_first_catch_up_refuses_a_declared_target_scope_mismatch() -> None:
    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, _, stale_msft, _ = _register_msft_effect(book, aapl_execution)
    item = _catch_up(
        book=registered,
        input_id="forged-first-target-catch-up",
        target_execution=stale_msft,
        source_execution=aapl_execution,
    )

    refused = apply_venue_recovery_input(registered, aapl_execution, item)

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.book is registered
    assert refused.execution is aapl_execution


def test_retained_catch_up_id_conflicts_before_cross_account_validation() -> None:
    """A changed payload cannot disguise one retained input ID as refusal."""

    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, _, stale_msft, _ = _register_msft_effect(book, aapl_execution)
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="catch-up-conflict-human"),
        input_id="catch-up-conflict-human-input",
    )
    original = _catch_up(
        book=attested.book,
        input_id="catch-up-conflict-retained-id",
        target_execution=stale_msft,
        source_execution=attested.execution,
    )
    first = apply_venue_recovery_input(attested.book, stale_msft, original)
    assert first.disposition is VenueRecoveryDisposition.APPLIED

    foreign_scope = replace(
        first.execution.position.scope,
        account=AccountId("foreign-paper-account"),
    )
    changed = _catch_up(
        book=first.book,
        input_id="catch-up-conflict-retained-id",
        target_execution=first.execution,
        source_execution=ExecutionSnapshot.flat(foreign_scope),
    )
    conflicted = apply_venue_recovery_input(
        first.book,
        first.execution,
        changed,
    )

    assert conflicted.disposition is VenueRecoveryDisposition.CONFLICT
    assert conflicted.book is first.book
    assert conflicted.execution is first.execution
    assert conflicted.quantity_delta == 0


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
        book=corroborated.book,
        input_id="catch-up-msft-after-corroboration",
        target_execution=stale_msft,
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


def test_independent_zero_economic_corroboration_requires_venue_provenance() -> None:
    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, _, stale_msft, _ = _register_msft_effect(book, aapl_execution)
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="independent-corroboration"),
        input_id="independent-corroboration-attestation",
    )
    evidence = _matching_broker_evidence(
        source="independent-corroboration-source",
        root="independent-corroboration-root",
    )
    independent_transition = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        evidence,
    )
    independent = independent_transition.execution
    observation = independent.seen_facts.get(evidence.fact.key)
    assert observation is not None
    assert (
        observation.classification
        is FirstObservationClassification.CORROBORATED_ZERO_ECONOMIC
    )

    blocked = apply_venue_recovery_input(
        attested.book,
        stale_msft,
        _catch_up(
            book=attested.book,
            input_id="reject-independent-corroboration-catch-up",
            target_execution=stale_msft,
            source_execution=independent,
        ),
    )

    assert blocked.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert blocked.book is attested.book
    assert blocked.execution is stale_msft
    assert blocked.book.human_coverages[0].broker_corroborated is False


def test_same_symbol_independent_truth_catches_up_and_blocks_release() -> None:
    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    fact = recovery_fixtures._broker_fill(
        "independent-catch-up-source",
        "independent-catch-up-root",
        quantity=2,
    )
    ahead = recovery_fixtures._apply_broker(execution, fact)
    item = _catch_up(
        book=book,
        input_id="catch-up-independent-aapl-truth",
        target_execution=execution,
        source_execution=ahead,
    )

    with _forbid_history_materialization():
        caught_up = apply_venue_recovery_input(book, execution, item)

    assert caught_up.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
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
    assert record.prior_registry_commitment == execution.seen_facts.commitment
    assert record.resulting_registry_commitment == ahead.seen_facts.commitment
    assert record.prior_position_commitment == execution.position.commitment
    assert record.resulting_position_commitment == ahead.position.commitment
    assert record.prior_root_heads_commitment == execution.root_heads.commitment
    assert record.resulting_root_heads_commitment == ahead.root_heads.commitment

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
            closure_id=execution_core.ClosureId("unattributed-canonical-truth-closure"),
            evidence_digest=b"\xc2" * 32,
        ),
    )
    assert blocked.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert blocked.book.closure_head(recovery_fixtures.LEG_A) is None

    replay_trap = AssertionError("unresolved exact replay revalidated stale source truth")
    with (
        patch.object(SeenFactIndex, "has_prefix", side_effect=replay_trap),
        patch.object(SeenFactIndex, "suffix_belongs_to", side_effect=replay_trap),
    ):
        replayed = apply_venue_recovery_input(
            caught_up.book,
            caught_up.execution,
            item,
        )
    assert replayed.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert replayed.book is caught_up.book
    assert replayed.execution is caught_up.execution
    assert replayed.quantity_delta == 0


def test_unresolved_execution_cursor_cannot_bootstrap_a_fresh_book() -> None:
    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    ahead = recovery_fixtures._apply_broker(
        execution,
        recovery_fixtures._broker_fill(
            "fresh-book-rollback-source",
            "fresh-book-rollback-root",
            quantity=2,
        ),
    )
    caught_up = apply_venue_recovery_input(
        book,
        execution,
        _catch_up(
            book=book,
            input_id="fresh-book-rollback-catch-up",
            target_execution=execution,
            source_execution=ahead,
        ),
    )
    assert caught_up.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert caught_up.execution.reconciliation_transition_count == 1

    fresh_book = VenueRecoveryBook.empty(recovery_fixtures.VENUE_SCOPE)
    refused = apply_venue_recovery_input(
        fresh_book,
        caught_up.execution,
        RequestedEffect(
            input_id=VenueInputId("fresh-book-rollback-request"),
            effect_id=EffectId("fresh-book-rollback-effect"),
            request_occurrence_id=RequestOccurrenceId(
                "fresh-book-rollback-occurrence"
            ),
            mandate_id=MandateId("fresh-book-rollback-mandate"),
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId("fresh-book-rollback-client"),
            symbol_id=recovery_fixtures.SYMBOL,
            side=ExecutionSide.BUY,
            quantity=Quantity(1),
            economic_scope=b"AAPL|BUY|fresh-book-rollback",
        ),
    )

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.book is fresh_book
    assert refused.execution is caught_up.execution
    assert fresh_book.effect(EffectId("fresh-book-rollback-effect")) is None


def test_nonempty_genesis_cursor_snapshot_cannot_bootstrap_a_fresh_book() -> None:
    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    ahead = recovery_fixtures._apply_broker(
        execution,
        recovery_fixtures._broker_fill(
            "fresh-book-genesis-source",
            "fresh-book-genesis-root",
            quantity=2,
        ),
    )
    assert ahead.seen_facts.count == execution.seen_facts.count + 1
    assert ahead.reconciliation_transition_count == 0
    assert ahead.account_reconciliation_required is False

    fresh_book = VenueRecoveryBook.empty(recovery_fixtures.VENUE_SCOPE)
    refused = apply_venue_recovery_input(
        fresh_book,
        ahead,
        RequestedEffect(
            input_id=VenueInputId("fresh-book-genesis-request"),
            effect_id=EffectId("fresh-book-genesis-effect"),
            request_occurrence_id=RequestOccurrenceId(
                "fresh-book-genesis-occurrence"
            ),
            mandate_id=MandateId("fresh-book-genesis-mandate"),
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId("fresh-book-genesis-client"),
            symbol_id=recovery_fixtures.SYMBOL,
            side=ExecutionSide.BUY,
            quantity=Quantity(1),
            economic_scope=b"AAPL|BUY|fresh-book-genesis",
        ),
    )

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.book is fresh_book
    assert refused.execution is ahead
    assert fresh_book.effect(EffectId("fresh-book-genesis-effect")) is None


def test_catch_up_rejects_an_inner_registry_subclass_before_using_its_proofs() -> (
    None
):
    class DelayedSeenFactIndex(SeenFactIndex):
        @property
        def count(self) -> int:
            raise AssertionError("untrusted registry count was invoked")

        @property
        def commitment(self) -> bytes:
            raise AssertionError("untrusted registry commitment was invoked")

        def has_prefix(self, _count: int, _commitment: bytes) -> bool:
            raise AssertionError("untrusted prefix proof was invoked")

        def suffix_belongs_to(
            self,
            _count: int,
            _position_scope: PositionScope,
        ) -> bool:
            raise AssertionError("untrusted suffix proof was invoked")

    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    forged_source = object.__new__(ExecutionSnapshot)
    object.__setattr__(forged_source, "position", execution.position)
    object.__setattr__(forged_source, "integrity", execution.integrity)
    object.__setattr__(forged_source, "root_heads", execution.root_heads)
    object.__setattr__(
        forged_source,
        "seen_facts",
        DelayedSeenFactIndex.empty(recovery_fixtures.POSITION_SCOPE),
    )
    item = _catch_up(
        book=book,
        input_id="reject-inner-registry-subclass",
        target_execution=execution,
        source_execution=forged_source,
    )

    with pytest.raises(TypeError, match="seen_facts must be"):
        apply_venue_recovery_input(book, execution, item)


def test_hydration_rejects_relabelled_unresolved_registry_advance() -> None:
    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    ahead = recovery_fixtures._apply_broker(
        execution,
        recovery_fixtures._broker_fill(
            "forged-resolution-source",
            "forged-resolution-root",
            quantity=2,
        ),
    )
    item = _catch_up(
        book=book,
        input_id="forged-resolution-catch-up",
        target_execution=execution,
        source_execution=ahead,
    )
    caught_up = apply_venue_recovery_input(book, execution, item)
    assert (
        caught_up.disposition
        is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    )
    [unresolved] = caught_up.book.execution_reconciliations
    forged = venue_module._ResolvedRegistryProjectionOutcome(
        input_id=unresolved.input_id,
        command_commitment=unresolved.command_commitment,
        target_checkpoint=unresolved.target_checkpoint,
        source_binding=unresolved.resulting_source_binding,
        resulting_registry_count=unresolved.resulting_registry_count,
        resulting_registry_commitment=unresolved.resulting_registry_commitment,
        reason="forged relabel of unresolved source advance",
    )

    with pytest.raises(
        ValueError,
        match="catch-up|outcome|reconciliation|source|prior",
    ):
        _audit_hydrate_book(
            caught_up.book,
            caught_up.execution,
            execution_reconciliations=(forged,),
        )


def test_hydration_rejects_a_coordinated_cross_symbol_catch_up_rewrite() -> None:
    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, msft_scope, stale_msft, _ = _register_msft_effect(
        book,
        aapl_execution,
    )
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="coordinated-rewrite-aapl"),
        input_id="coordinated-rewrite-aapl-attestation",
    )
    synced_msft = apply_venue_recovery_input(
        attested.book,
        stale_msft,
        _catch_up(
            book=attested.book,
            input_id="coordinated-rewrite-sync-msft",
            target_execution=stale_msft,
            source_execution=attested.execution,
        ),
    )
    assert synced_msft.execution.reconciliation_transition_count == 1
    assert (
        synced_msft.execution.reconciliation_transition_head
        == synced_msft.book._registry_transition_head_commitment
    )
    assert not synced_msft.execution.account_reconciliation_required
    msft_fact = recovery_fixtures._broker_fill(
        "coordinated-rewrite-msft-source",
        "coordinated-rewrite-msft-root",
        quantity=1,
    )
    msft_fact = replace(
        msft_fact,
        scope=replace(
            msft_fact.scope,
            symbol_id=msft_scope.symbol_id,
            order_id=OrderId("coordinated-rewrite-unowned-msft-order"),
        ),
    )
    msft_ahead = recovery_fixtures._apply_broker(synced_msft.execution, msft_fact)
    advance_item = _catch_up(
        book=synced_msft.book,
        input_id="coordinated-rewrite-source-advance",
        target_execution=attested.execution,
        source_execution=msft_ahead,
    )
    advanced = apply_venue_recovery_input(
        synced_msft.book,
        attested.execution,
        advance_item,
    )
    assert advanced.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert advanced.execution.reconciliation_transition_count == 2
    assert (
        advanced.execution.reconciliation_transition_head
        == advanced.book._registry_transition_head_commitment
    )
    assert advanced.execution.account_reconciliation_required

    later_execution = recovery_fixtures._apply_broker(
        advanced.execution,
        recovery_fixtures._broker_fill(
            "coordinated-rewrite-later-source",
            "coordinated-rewrite-later-root",
            quantity=1,
        ),
    )
    assert (
        later_execution.reconciliation_transition_count
        == advanced.execution.reconciliation_transition_count
    )
    assert (
        later_execution.reconciliation_transition_head
        == advanced.execution.reconciliation_transition_head
    )
    assert later_execution.account_reconciliation_required
    result_binding = venue_module._execution_binding_for_snapshot(msft_ahead)
    forged_item = replace(
        advance_item,
        prior_account_registry_count=msft_ahead.seen_facts.count,
        prior_account_registry_commitment=msft_ahead.seen_facts.commitment,
        prior_source_binding=result_binding,
    )
    forged_outcome = venue_module._ResolvedRegistryProjectionOutcome(
        input_id=forged_item.input_id,
        command_commitment=venue_module._catch_up_input_commitment(forged_item),
        target_checkpoint=forged_item.target_checkpoint,
        source_binding=result_binding,
        resulting_registry_count=msft_ahead.seen_facts.count,
        resulting_registry_commitment=msft_ahead.seen_facts.commitment,
        reason="coordinated rewrite must not replace a chained source advance",
    )
    forged_inputs = tuple(
        replace(record, item=forged_item)
        if record.input_id == advance_item.input_id
        else record
        for record in advanced.book.input_records
    )
    forged_outcomes = tuple(
        forged_outcome if record.input_id == advance_item.input_id else record
        for record in advanced.book.execution_reconciliations
    )

    def proof_sequence(items: tuple[object, ...]):
        retained = venue_module._PersistentSequence.empty()
        for proof in items:
            retained = retained.append(proof, proof.commitment)
        return retained

    def rebuilt_proofs(
        input_records: tuple[object, ...],
        outcomes: tuple[object, ...],
    ) -> tuple[object, ...]:
        items_by_id = {record.input_id: record.item for record in input_records}
        predecessor = None
        rebuilt = []
        for ordinal, outcome in enumerate(outcomes, start=1):
            proof = venue_module._registry_transition_proof_for(
                ordinal=ordinal,
                predecessor_commitment=predecessor,
                venue_scope=advanced.book.scope,
                item=items_by_id[outcome.input_id],
                outcome=outcome,
            )
            rebuilt.append(proof)
            predecessor = proof.commitment
        return tuple(rebuilt)

    forged_proofs = rebuilt_proofs(forged_inputs, forged_outcomes)
    fully_forged = copy(advanced.book)
    object.__setattr__(
        fully_forged,
        "_registry_transition_ledger",
        proof_sequence(forged_proofs),
    )
    object.__setattr__(
        fully_forged,
        "_registry_transition_head_commitment",
        forged_proofs[-1].commitment,
    )

    with pytest.raises(
        ValueError,
        match="account|external|registry|reconciliation|source|transition",
    ):
        _audit_hydrate_book(
            fully_forged,
            advanced.execution,
            input_records=forged_inputs,
            execution_reconciliations=forged_outcomes,
        )

    same_count_outcomes = tuple(
        replace(record, reason="same-count reconciliation fork")
        if record.input_id == advance_item.input_id
        else record
        for record in advanced.book.execution_reconciliations
    )
    same_count_proofs = rebuilt_proofs(
        advanced.book.input_records,
        same_count_outcomes,
    )
    same_count_fork = copy(advanced.book)
    object.__setattr__(
        same_count_fork,
        "_registry_transition_ledger",
        proof_sequence(same_count_proofs),
    )
    object.__setattr__(
        same_count_fork,
        "_registry_transition_head_commitment",
        same_count_proofs[-1].commitment,
    )
    with pytest.raises(ValueError, match="external|cursor|reconciliation"):
        _audit_hydrate_book(
            same_count_fork,
            advanced.execution,
            execution_reconciliations=same_count_outcomes,
        )

    proofs = advanced.book._registry_transition_ledger.to_tuple()
    assert len(proofs) == 2
    foreign_generation_scope = replace(
        advanced.book.scope,
        generation=execution_core.ApplicationGenerationId(
            "coordinated-rewrite-foreign-generation"
        ),
    )
    with pytest.raises(ValueError, match="transition|outcome|predecessor"):
        venue_module._validate_registry_transition_chain(
            proofs,
            advanced.book.input_records,
            advanced.book.execution_reconciliations,
            advanced.book._registry_transition_head_commitment,
            foreign_generation_scope,
        )

    omitted_inputs = tuple(
        record
        for record in advanced.book.input_records
        if record.input_id != advance_item.input_id
    )
    omitted_outcomes = tuple(
        record
        for record in advanced.book.execution_reconciliations
        if record.input_id != advance_item.input_id
    )
    omitted_proofs = rebuilt_proofs(omitted_inputs, omitted_outcomes)
    omitted = copy(advanced.book)
    object.__setattr__(
        omitted,
        "_registry_transition_ledger",
        proof_sequence(omitted_proofs),
    )
    object.__setattr__(
        omitted,
        "_registry_transition_head_commitment",
        omitted_proofs[-1].commitment,
    )
    with pytest.raises(
        ValueError,
        match="account|external|registry|reconciliation|source|transition",
    ):
        _audit_hydrate_book(
            omitted,
            advanced.execution,
            input_records=omitted_inputs,
            execution_reconciliations=omitted_outcomes,
        )

    reordered = copy(advanced.book)
    reordered_inputs_list = list(advanced.book.input_records)
    catch_up_indexes = [
        index
        for index, record in enumerate(reordered_inputs_list)
        if type(record.item) is _required_api("CatchUpExecutionRegistry")
    ]
    assert len(catch_up_indexes) == 2
    first_index, second_index = catch_up_indexes
    reordered_inputs_list[first_index], reordered_inputs_list[second_index] = (
        reordered_inputs_list[second_index],
        reordered_inputs_list[first_index],
    )
    reordered_inputs = tuple(reordered_inputs_list)
    reordered_outcomes = tuple(reversed(advanced.book.execution_reconciliations))
    reversed_proofs = rebuilt_proofs(reordered_inputs, reordered_outcomes)
    object.__setattr__(
        reordered,
        "_registry_transition_ledger",
        proof_sequence(reversed_proofs),
    )
    object.__setattr__(
        reordered,
        "_registry_transition_head_commitment",
        reversed_proofs[-1].commitment,
    )
    with pytest.raises(
        ValueError,
        match="account|external|order|registry|reconciliation|transition",
    ):
        _audit_hydrate_book(
            reordered,
            advanced.execution,
            input_records=reordered_inputs,
            execution_reconciliations=reordered_outcomes,
        )

    mutated_predecessor = replace(
        proofs[1],
        predecessor_commitment=b"\xff" * 32,
    )
    mutated = copy(advanced.book)
    mutated_proofs = (proofs[0], mutated_predecessor)
    object.__setattr__(
        mutated,
        "_registry_transition_ledger",
        proof_sequence(mutated_proofs),
    )
    object.__setattr__(
        mutated,
        "_registry_transition_head_commitment",
        mutated_predecessor.commitment,
    )
    with pytest.raises(ValueError, match="predecessor"):
        _audit_hydrate_book(mutated, advanced.execution)


def test_catch_up_requires_an_exact_target_scope_type() -> None:
    class PositionScopeSubclass(PositionScope):
        pass

    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    checkpoint_type = _required_api("VenueExecutionCheckpoint")
    forged_scope = PositionScopeSubclass(
        broker=execution.position.scope.broker,
        environment=execution.position.scope.environment,
        account=execution.position.scope.account,
        symbol_id=execution.position.scope.symbol_id,
    )

    with pytest.raises(TypeError, match="position_scope.*PositionScope"):
        checkpoint_type(
            position_scope=forged_scope,
            registry_count=execution.seen_facts.count,
            registry_commitment=execution.seen_facts.commitment,
            position_commitment=execution.position.commitment,
            root_heads_commitment=execution.root_heads.commitment,
            integrity_bits=execution.integrity.value,
            account_reconciliation_required=(
                execution.account_reconciliation_required
            ),
            reconciliation_transition_count=(
                execution.reconciliation_transition_count
            ),
            reconciliation_transition_head=(
                execution.reconciliation_transition_head
            ),
        )


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
        book=advanced.book,
        input_id="reject-non-prefix-registry",
        target_execution=advanced.execution,
        source_execution=divergent,
    )
    with _forbid_history_materialization():
        non_prefix = apply_venue_recovery_input(
            advanced.book,
            advanced.execution,
            non_prefix_item,
        )
    assert non_prefix.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert non_prefix.book == advanced.book
    assert non_prefix.execution == advanced.execution

    foreign_scope = PositionScope(
        broker=recovery_fixtures.BROKER,
        environment=recovery_fixtures.ENVIRONMENT,
        account=AccountId("different-paper-account"),
        symbol_id=recovery_fixtures.SYMBOL,
    )
    cross_account_item = _catch_up(
        book=advanced.book,
        input_id="reject-cross-account-registry",
        target_execution=advanced.execution,
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
    assert hydrated.root_heads.commitment == attested.execution.root_heads.commitment
    assert hydrated.seen_facts.commitment == attested.execution.seen_facts.commitment
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
        hydrated.seen_facts.commitment == corroborated.execution.seen_facts.commitment
    )
    assert corroborated.book._execution_matches(
        hydrated,
        recovery_fixtures.POSITION_SCOPE,
    )


def test_recovery_hydration_rejects_snapshot_component_subclasses() -> None:
    class PositionStateSubclass(PositionState):
        pass

    class RootHeadIndexSubclass(RootHeadIndex):
        pass

    class SeenFactIndexSubclass(SeenFactIndex):
        pass

    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    binder = _required_api("bind_venue_execution_snapshot")
    cases = (
        (
            PositionStateSubclass.flat(recovery_fixtures.POSITION_SCOPE),
            execution.root_heads,
            execution.seen_facts,
            "position must be PositionState",
        ),
        (
            execution.position,
            RootHeadIndexSubclass.empty(recovery_fixtures.POSITION_SCOPE),
            execution.seen_facts,
            "root_heads must be RootHeadIndex",
        ),
        (
            execution.position,
            execution.root_heads,
            SeenFactIndexSubclass.empty(recovery_fixtures.POSITION_SCOPE),
            "seen_facts must be SeenFactIndex",
        ),
    )

    for position, root_heads, seen_facts, message in cases:
        with pytest.raises(TypeError, match=message):
            binder(
                book,
                position,
                execution.integrity,
                root_heads,
                seen_facts,
                expected_reconciliation_cursor=execution.reconciliation_cursor,
            )


def test_recovery_hydration_rejects_scope_subclass_before_equality() -> None:
    class DelayedPositionScope(PositionScope):
        def __eq__(self, _other: object) -> bool:
            raise AssertionError("untrusted scope equality was invoked")

        __hash__ = PositionScope.__hash__

    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    scope = DelayedPositionScope(
        broker=recovery_fixtures.BROKER,
        environment=recovery_fixtures.ENVIRONMENT,
        account=recovery_fixtures.ACCOUNT,
        symbol_id=recovery_fixtures.SYMBOL,
    )
    binder = _required_api("bind_venue_execution_snapshot")

    with pytest.raises(TypeError, match="position.scope must be PositionScope"):
        binder(
            book,
            PositionState.flat(scope),
            execution.integrity,
            RootHeadIndex.empty(scope),
            SeenFactIndex.empty(scope),
            expected_reconciliation_cursor=execution.reconciliation_cursor,
        )


def test_checkpoint_and_audit_factories_reject_inner_subclass_before_registry() -> (
    None
):
    class DelayedSeenFactIndex(SeenFactIndex):
        @property
        def count(self) -> int:
            raise AssertionError("untrusted checkpoint registry count was invoked")

    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    forged = object.__new__(ExecutionSnapshot)
    object.__setattr__(forged, "position", execution.position)
    object.__setattr__(forged, "integrity", execution.integrity)
    object.__setattr__(forged, "root_heads", execution.root_heads)
    object.__setattr__(
        forged,
        "seen_facts",
        DelayedSeenFactIndex.empty(recovery_fixtures.POSITION_SCOPE),
    )
    checkpoint_type = _required_api("VenueExecutionCheckpoint")

    with pytest.raises(TypeError, match="seen_facts must be"):
        checkpoint_type.from_execution(forged)
    with pytest.raises(TypeError, match="seen_facts must be"):
        _audit_hydrate_book(book, forged)


def test_recovery_hydration_rejects_missing_or_forged_book_provenance() -> None:
    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    attested = recovery_fixtures._ingest(
        book,
        execution,
        recovery_fixtures._human_fill(input_suffix="trusted-hydration"),
        input_id="trusted-hydration-attestation",
    )

    with pytest.raises(ValueError, match="provenance|coverage|human"):
        _audit_hydrate_book(
            book,
            attested.execution,
            execution_registry_commitment=(attested.execution.seen_facts.commitment),
            execution_bindings=attested.book.execution_bindings,
        )

    other_book, other_execution = recovery_fixtures._seed_needs_review(capacity=4)
    other_attested = recovery_fixtures._ingest(
        other_book,
        other_execution,
        recovery_fixtures._human_fill(input_suffix="forged-hydration"),
        input_id="forged-hydration-attestation",
    )
    with pytest.raises(ValueError, match="provenance|coverage|root"):
        _audit_hydrate_book(
            other_attested.book,
            attested.execution,
            execution_registry_commitment=(attested.execution.seen_facts.commitment),
            execution_bindings=attested.book.execution_bindings,
        )

    evidence = _matching_broker_evidence(
        source="missing-corroboration-source",
        root="missing-corroboration-root",
    )
    corroborated = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        evidence,
    )
    with pytest.raises(ValueError, match="provenance|corroboration|broker"):
        _audit_hydrate_book(
            attested.book,
            corroborated.execution,
            execution_registry_commitment=(
                corroborated.execution.seen_facts.commitment
            ),
            execution_bindings=corroborated.book.execution_bindings,
        )


def test_recovery_hydration_requires_an_independently_retained_cursor() -> None:
    book, aapl_execution = recovery_fixtures._seed_needs_review(capacity=4)
    registered, msft_scope, stale_msft, _ = _register_msft_effect(
        book,
        aapl_execution,
    )
    attested = recovery_fixtures._ingest(
        registered,
        aapl_execution,
        recovery_fixtures._human_fill(input_suffix="independent-cursor"),
        input_id="independent-cursor-attestation",
    )
    projected = apply_venue_recovery_input(
        attested.book,
        stale_msft,
        _catch_up(
            book=attested.book,
            input_id="independent-cursor-projection",
            target_execution=stale_msft,
            source_execution=attested.execution,
        ),
    )
    binder = _required_api("bind_venue_execution_snapshot")
    unbound_seen = SeenFactIndex(
        entries=projected.execution.seen_facts.entries,
        position_scope=msft_scope,
    )
    rebound = binder(
        projected.book,
        PositionState.flat(msft_scope),
        PositionIntegrity.CONSISTENT,
        RootHeadIndex.empty(msft_scope),
        unbound_seen,
        expected_reconciliation_cursor=(
            projected.execution.reconciliation_cursor
        ),
    )
    assert rebound.commitment == projected.execution.commitment

    self_authorizing_book = copy(projected.book)
    object.__setattr__(
        self_authorizing_book,
        "_registry_transition_ledger",
        venue_module._PersistentSequence.empty(),
    )
    object.__setattr__(
        self_authorizing_book,
        "_registry_transition_head_commitment",
        None,
    )
    with pytest.raises(ValueError, match="execution|cursor|high-water"):
        binder(
            self_authorizing_book,
            PositionState.flat(msft_scope),
            PositionIntegrity.CONSISTENT,
            RootHeadIndex.empty(msft_scope),
            unbound_seen,
            expected_reconciliation_cursor=(
                projected.execution.reconciliation_cursor
            ),
        )

    forged_cursor = replace(
        projected.execution.reconciliation_cursor,
        snapshot_commitment=b"\x00" * 32,
    )
    with pytest.raises(ValueError, match="independently retained snapshot"):
        binder(
            projected.book,
            PositionState.flat(msft_scope),
            PositionIntegrity.CONSISTENT,
            RootHeadIndex.empty(msft_scope),
            unbound_seen,
            expected_reconciliation_cursor=forged_cursor,
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
            book=attested.book,
            input_id="projection-does-not-cross-wire-economics",
            target_execution=stale_msft,
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


def _registry_contract_fixture():
    book, target = recovery_fixtures._seed_needs_review(capacity=4)
    source = recovery_fixtures._apply_broker(
        target,
        recovery_fixtures._broker_fill(
            "registry-contract-source",
            "registry-contract-root",
            quantity=1,
        ),
    )
    checkpoint = venue_module.VenueExecutionCheckpoint.from_execution(target)
    prior_binding = venue_module._execution_binding_for_snapshot(target)
    source_binding = venue_module._execution_binding_for_snapshot(source)
    resolved_item = venue_module.CatchUpExecutionRegistry(
        input_id=VenueInputId("registry-contract-resolved"),
        target_checkpoint=checkpoint,
        prior_account_registry_count=source.seen_facts.count,
        prior_account_registry_commitment=source.seen_facts.commitment,
        prior_source_binding=source_binding,
        source_execution=source,
    )
    resolved = venue_module._ResolvedRegistryProjectionOutcome(
        input_id=resolved_item.input_id,
        command_commitment=venue_module._catch_up_input_commitment(resolved_item),
        target_checkpoint=checkpoint,
        source_binding=source_binding,
        resulting_registry_count=source.seen_facts.count,
        resulting_registry_commitment=source.seen_facts.commitment,
        reason="the target is a proven prefix of the retained account registry",
    )
    unresolved_item = venue_module.CatchUpExecutionRegistry(
        input_id=VenueInputId("registry-contract-unresolved"),
        target_checkpoint=checkpoint,
        prior_account_registry_count=target.seen_facts.count,
        prior_account_registry_commitment=target.seen_facts.commitment,
        prior_source_binding=prior_binding,
        source_execution=source,
    )
    unresolved = venue_module._UnresolvedRegistryAdvanceOutcome(
        input_id=unresolved_item.input_id,
        command_commitment=venue_module._catch_up_input_commitment(unresolved_item),
        target_checkpoint=checkpoint,
        prior_account_registry_count=target.seen_facts.count,
        prior_account_registry_commitment=target.seen_facts.commitment,
        prior_source_binding=prior_binding,
        resulting_source_binding=source_binding,
        resulting_registry_count=source.seen_facts.count,
        resulting_registry_commitment=source.seen_facts.commitment,
        reason="the source advanced without one proven venue attribution",
    )
    return book, target, source, resolved_item, resolved, unresolved_item, unresolved


def test_registry_value_objects_reject_malformed_exact_contracts() -> None:
    _, target, source, resolved_item, resolved, unresolved_item, unresolved = (
        _registry_contract_fixture()
    )
    binding = venue_module._execution_binding_for_snapshot(target)
    checkpoint = venue_module.VenueExecutionCheckpoint.from_execution(target)

    binding_cases = (
        ("position_scope", object(), "position_scope"),
        ("position_commitment", b"", "position_commitment"),
        ("root_heads_commitment", b"short", "root_heads_commitment"),
        ("integrity_bits", True, "integrity_bits"),
        ("integrity_bits", -1, "integrity_bits"),
    )
    for field_name, value, message in binding_cases:
        with pytest.raises((TypeError, ValueError), match=message):
            replace(binding, **{field_name: value})

    checkpoint_cases = (
        ("position_scope", object(), "position_scope"),
        ("registry_count", True, "registry_count"),
        ("registry_count", -1, "registry_count"),
        ("registry_commitment", b"", "registry_commitment"),
        ("position_commitment", b"", "position_commitment"),
        ("root_heads_commitment", b"", "root_heads_commitment"),
        ("integrity_bits", True, "integrity_bits"),
        ("integrity_bits", -1, "integrity_bits"),
        (
            "account_reconciliation_required",
            1,
            "account_reconciliation_required",
        ),
        ("reconciliation_transition_count", True, "transition_count"),
        ("reconciliation_transition_count", -1, "transition_count"),
        ("reconciliation_transition_head", b"", "transition_head"),
    )
    for field_name, value, message in checkpoint_cases:
        with pytest.raises((TypeError, ValueError), match=message):
            replace(checkpoint, **{field_name: value})

    catch_up_cases = (
        ("input_id", object(), "input_id"),
        ("target_checkpoint", object(), "target_checkpoint"),
        ("prior_account_registry_count", True, "registry_count"),
        ("prior_account_registry_count", -1, "registry_count"),
        ("prior_account_registry_commitment", b"", "registry_commitment"),
        ("prior_source_binding", object(), "prior_source_binding"),
        ("source_execution", object(), "source_execution"),
    )
    for field_name, value, message in catch_up_cases:
        with pytest.raises((TypeError, ValueError), match=message):
            replace(resolved_item, **{field_name: value})

    common_outcome_cases = (
        ("input_id", object(), "input_id"),
        ("command_commitment", b"", "command_commitment"),
        ("target_checkpoint", object(), "target_checkpoint"),
        (
            "resulting_registry_count",
            resolved.target_checkpoint.registry_count,
            "strictly exceed",
        ),
        ("resulting_registry_commitment", b"", "registry_commitment"),
        ("reason", " ", "reason"),
        ("reason", 1, "reason"),
        ("source_binding", object(), "source_binding"),
    )
    for field_name, value, message in common_outcome_cases:
        with pytest.raises((TypeError, ValueError), match=message):
            replace(resolved, **{field_name: value})

    foreign_binding = replace(
        unresolved.resulting_source_binding,
        position_scope=replace(
            unresolved.resulting_source_binding.position_scope,
            symbol_id=SymbolId("MSFT"),
        ),
    )
    unresolved_cases = (
        ("prior_account_registry_count", -1, "strict prefix"),
        (
            "prior_account_registry_count",
            unresolved.resulting_registry_count,
            "strict prefix",
        ),
        ("prior_account_registry_commitment", b"", "registry_commitment"),
        ("prior_source_binding", object(), "prior_source_binding"),
        ("resulting_source_binding", object(), "resulting_source_binding"),
        ("resulting_source_binding", foreign_binding, "exact position scope"),
    )
    for field_name, value, message in unresolved_cases:
        with pytest.raises((TypeError, ValueError), match=message):
            replace(unresolved, **{field_name: value})

    with pytest.raises(TypeError, match="execution"):
        venue_module.VenueExecutionCheckpoint.from_execution(object())
    with pytest.raises(TypeError, match="item"):
        venue_module._catch_up_input_commitment(object())
    assert source.seen_facts.count == 1
    assert unresolved_item.prior_source_binding == unresolved.prior_source_binding


def test_registry_outcome_views_expose_the_exact_committed_heads() -> None:
    _, _, _, _, resolved, _, unresolved = _registry_contract_fixture()

    assert resolved.canonical_applied
    assert resolved.attribution_resolved
    assert resolved.position_scope == resolved.target_checkpoint.position_scope
    assert resolved.prior_registry_count == resolved.target_checkpoint.registry_count
    assert (
        resolved.prior_registry_commitment
        == resolved.target_checkpoint.registry_commitment
    )
    assert (
        resolved.prior_position_commitment
        == resolved.resulting_position_commitment
        == resolved.target_checkpoint.position_commitment
    )
    assert (
        resolved.prior_root_heads_commitment
        == resolved.resulting_root_heads_commitment
        == resolved.target_checkpoint.root_heads_commitment
    )
    assert (
        resolved.prior_integrity_bits
        == resolved.resulting_integrity_bits
        == resolved.target_checkpoint.integrity_bits
    )

    assert unresolved.canonical_applied
    assert not unresolved.attribution_resolved
    assert (
        unresolved.position_scope
        == unresolved.resulting_source_binding.position_scope
    )
    assert unresolved.prior_registry_count == unresolved.prior_account_registry_count
    assert (
        unresolved.prior_registry_commitment
        == unresolved.prior_account_registry_commitment
    )
    assert (
        unresolved.prior_position_commitment
        == unresolved.prior_source_binding.position_commitment
    )
    assert (
        unresolved.resulting_position_commitment
        == unresolved.resulting_source_binding.position_commitment
    )
    assert (
        unresolved.prior_root_heads_commitment
        == unresolved.prior_source_binding.root_heads_commitment
    )
    assert (
        unresolved.resulting_root_heads_commitment
        == unresolved.resulting_source_binding.root_heads_commitment
    )
    assert (
        unresolved.prior_integrity_bits
        == unresolved.prior_source_binding.integrity_bits
    )
    assert (
        unresolved.resulting_integrity_bits
        == unresolved.resulting_source_binding.integrity_bits
    )


def test_registry_transition_proof_rejects_contradictions_and_chain_forks() -> None:
    book, _, _, resolved_item, resolved, unresolved_item, unresolved = (
        _registry_contract_fixture()
    )
    proof_for = venue_module._registry_transition_proof_for

    with pytest.raises(TypeError, match="venue_scope"):
        proof_for(
            ordinal=1,
            predecessor_commitment=None,
            venue_scope=object(),
            item=resolved_item,
            outcome=resolved,
        )
    with pytest.raises(TypeError, match="CatchUp"):
        proof_for(
            ordinal=1,
            predecessor_commitment=None,
            venue_scope=book.scope,
            item=object(),
            outcome=resolved,
        )
    with pytest.raises(ValueError, match="prior source binding"):
        proof_for(
            ordinal=1,
            predecessor_commitment=None,
            venue_scope=book.scope,
            item=replace(resolved_item, prior_source_binding=None),
            outcome=resolved,
        )
    with pytest.raises(ValueError, match="resolved projection"):
        proof_for(
            ordinal=1,
            predecessor_commitment=None,
            venue_scope=book.scope,
            item=resolved_item,
            outcome=replace(resolved, resulting_registry_commitment=b"\x91" * 32),
        )
    with pytest.raises(ValueError, match="source advance"):
        proof_for(
            ordinal=1,
            predecessor_commitment=None,
            venue_scope=book.scope,
            item=unresolved_item,
            outcome=replace(
                unresolved,
                prior_account_registry_commitment=b"\x92" * 32,
            ),
        )
    with pytest.raises(TypeError, match="outcome type"):
        proof_for(
            ordinal=1,
            predecessor_commitment=None,
            venue_scope=book.scope,
            item=resolved_item,
            outcome=object(),
        )

    proof = proof_for(
        ordinal=1,
        predecessor_commitment=None,
        venue_scope=book.scope,
        item=resolved_item,
        outcome=resolved,
    )
    record = venue_module.VenueInputRecord(
        input_id=resolved_item.input_id,
        item=resolved_item,
    )
    validate_chain = venue_module._validate_registry_transition_chain
    validate_chain(
        (proof,),
        (record,),
        (resolved,),
        proof.commitment,
        book.scope,
    )
    with pytest.raises(ValueError, match="input order"):
        validate_chain((proof,), (), (resolved,), proof.commitment, book.scope)
    with pytest.raises(ValueError, match="length"):
        validate_chain((), (record,), (resolved,), None, book.scope)
    with pytest.raises(TypeError, match="proof type"):
        validate_chain(
            (object(),),
            (record,),
            (resolved,),
            proof.commitment,
            book.scope,
        )
    shadow_record = venue_module.VenueInputRecord(
        input_id=resolved_item.input_id,
        item=object(),
    )
    with pytest.raises(ValueError, match="exact CatchUp input"):
        validate_chain(
            (proof,),
            (record, shadow_record),
            (resolved,),
            proof.commitment,
            book.scope,
        )
    with pytest.raises(ValueError, match="predecessor or outcome"):
        validate_chain(
            (replace(proof, ordinal=2),),
            (record,),
            (resolved,),
            proof.commitment,
            book.scope,
        )
    with pytest.raises(ValueError, match="head"):
        validate_chain(
            (proof,),
            (record,),
            (resolved,),
            b"\x93" * 32,
            book.scope,
        )

    higher_item = replace(
        resolved_item,
        input_id=VenueInputId("registry-contract-higher"),
        prior_account_registry_count=2,
        prior_account_registry_commitment=b"\x94" * 32,
    )
    higher_outcome = replace(
        resolved,
        input_id=higher_item.input_id,
        command_commitment=venue_module._catch_up_input_commitment(higher_item),
        resulting_registry_count=2,
        resulting_registry_commitment=b"\x94" * 32,
    )
    lower_item = replace(
        resolved_item,
        input_id=VenueInputId("registry-contract-lower"),
    )
    lower_outcome = replace(
        resolved,
        input_id=lower_item.input_id,
        command_commitment=venue_module._catch_up_input_commitment(lower_item),
    )
    higher_proof = proof_for(
        ordinal=1,
        predecessor_commitment=None,
        venue_scope=book.scope,
        item=higher_item,
        outcome=higher_outcome,
    )
    lower_proof = proof_for(
        ordinal=2,
        predecessor_commitment=higher_proof.commitment,
        venue_scope=book.scope,
        item=lower_item,
        outcome=lower_outcome,
    )
    with pytest.raises(ValueError, match="regresses"):
        validate_chain(
            (higher_proof, lower_proof),
            (
                venue_module.VenueInputRecord(
                    input_id=higher_item.input_id,
                    item=higher_item,
                ),
                venue_module.VenueInputRecord(
                    input_id=lower_item.input_id,
                    item=lower_item,
                ),
            ),
            (higher_outcome, lower_outcome),
            lower_proof.commitment,
            book.scope,
        )
