"""RED pins for bidirectional venue provenance and final-state integrity.

The tests use only pure execution-core transitions and the checkpoint's verified
internal rebuild route.  They perform no I/O and intentionally preserve source
inputs while tampering only with their claimed outcomes.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

import app.execution_core.venue as venue_module
from app.execution_core.fills import BrokerTradeCorrectFact
from app.execution_core.identity import (
    AccountId,
    ClosureId,
    EvidenceReference,
    ExecutionFactKey,
    SourceEventId,
    VenueInputId,
)
from app.execution_core.position import ExecutionSnapshot, PositionIntegrity
from app.execution_core.recovery import (
    RecordBrokerFillEvidence,
    RecordBrokerRevisionEvidence,
    ReleaseVenueLeg,
)
from app.execution_core.values import Quantity
from app.execution_core.venue import (
    AcceptanceProofKind,
    BrokerEffectState,
    CatchUpExecutionRegistry,
    CloseAcceptanceSet,
    VenueAttemptState,
    VenueExecutionCheckpoint,
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    VenueRecoveryTransition,
    VenueScope,
    _audit_hydrate_book,
    apply_venue_recovery_input,
)
from tests.execution_core import test_venue_recovery as recovery_fixtures


def _finalized_human_effect():
    book, execution, _ = recovery_fixtures._released_state()
    finalized = apply_venue_recovery_input(
        book,
        execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("provenance-close-human-effect"),
            effect_id=recovery_fixtures.EFFECT,
            proof=recovery_fixtures._acceptance_proof(
                book,
                AcceptanceProofKind.COVERED_RECONCILIATION,
                "provenance-human-parent-proof",
            ),
        ),
    )
    assert finalized.disposition is VenueRecoveryDisposition.APPLIED
    assert (
        finalized.book.effect(recovery_fixtures.EFFECT).state
        is BrokerEffectState.OPERATOR_RECONCILED
    )
    return finalized


def _broker_coverage_with_alias():
    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    fact = recovery_fixtures._broker_fill(
        "provenance-alias-source",
        "provenance-alias-root",
        quantity=2,
    )
    direct_command = RecordBrokerFillEvidence(
        input_id=VenueInputId("provenance-direct-broker-input"),
        effect_id=recovery_fixtures.EFFECT,
        leg_key=recovery_fixtures.LEG_A,
        prior_cumulative_quantity=Quantity(0),
        resulting_cumulative_quantity=Quantity(2),
        fact=fact,
        evidence_digest=b"\xd1" * 32,
    )
    direct = apply_venue_recovery_input(book, execution, direct_command)
    assert direct.disposition is VenueRecoveryDisposition.APPLIED

    alias_command = replace(
        direct_command,
        input_id=VenueInputId("provenance-semantic-broker-alias"),
    )
    aliased = apply_venue_recovery_input(
        direct.book,
        direct.execution,
        alias_command,
    )
    assert aliased.disposition is VenueRecoveryDisposition.APPLIED
    assert aliased.quantity_delta == 0
    return aliased, direct_command, alias_command


def _post_final_fill_conflict():
    finalized = _finalized_human_effect()
    conflict = RecordBrokerFillEvidence(
        input_id=VenueInputId("provenance-post-final-conflict"),
        effect_id=recovery_fixtures.EFFECT,
        leg_key=recovery_fixtures.LEG_A,
        prior_cumulative_quantity=Quantity(0),
        resulting_cumulative_quantity=Quantity(4),
        fact=recovery_fixtures._broker_fill(
            "provenance-post-final-source",
            "provenance-post-final-root",
            quantity=4,
            units=101,
        ),
        evidence_digest=b"\xd2" * 32,
    )
    reconciled = apply_venue_recovery_input(
        finalized.book,
        finalized.execution,
        conflict,
    )
    assert reconciled.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert reconciled.book.reconciliations
    return reconciled


def _post_final_registry_reconciliation():
    finalized = _finalized_human_effect()
    ahead = recovery_fixtures._apply_broker(
        finalized.execution,
        recovery_fixtures._broker_fill(
            "provenance-catch-up-source",
            "provenance-catch-up-root",
            quantity=2,
        ),
    )
    caught_up = apply_venue_recovery_input(
        finalized.book,
        finalized.execution,
        CatchUpExecutionRegistry(
            input_id=VenueInputId("provenance-catch-up-input"),
            target_checkpoint=VenueExecutionCheckpoint.from_execution(
                finalized.execution
            ),
            prior_account_registry_count=(finalized.book.execution_registry_count),
            prior_account_registry_commitment=(
                finalized.book.execution_registry_commitment
            ),
            prior_source_binding=finalized.book.execution_binding(ahead.position.scope),
            source_execution=ahead,
        ),
    )
    assert caught_up.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert any(
        not record.attribution_resolved
        for record in caught_up.book.execution_reconciliations
    )
    return caught_up


def _post_final_unresolved_mapping():
    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    first_fact = recovery_fixtures._broker_fill(
        "provenance-mapping-first-source",
        "provenance-mapping-first-root",
        quantity=2,
    )
    first = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("provenance-mapping-first-input"),
            effect_id=recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(2),
            fact=first_fact,
            evidence_digest=b"\xd3" * 32,
        ),
    )
    second_fact = recovery_fixtures._broker_fill(
        "provenance-mapping-second-source",
        "provenance-mapping-second-root",
        quantity=2,
    )
    second = apply_venue_recovery_input(
        first.book,
        first.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("provenance-mapping-second-input"),
            effect_id=recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_A,
            prior_cumulative_quantity=Quantity(2),
            resulting_cumulative_quantity=Quantity(4),
            fact=second_fact,
            evidence_digest=b"\xd4" * 32,
        ),
    )
    released = apply_venue_recovery_input(
        second.book,
        second.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("provenance-mapping-release"),
            effect_id=recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_A,
            claim_occurrence_id=recovery_fixtures.CLAIM,
            venue_cumulative_quantity=Quantity(4),
            broker_terminal_state=VenueAttemptState.FILLED,
            actor=recovery_fixtures.ACTOR,
            reason="two exact broker intervals close at full capacity",
            evidence_reference=recovery_fixtures.EVIDENCE,
            closure_id=ClosureId("provenance-mapping-release-closure"),
            evidence_digest=b"\xd5" * 32,
        ),
    )
    finalized = apply_venue_recovery_input(
        released.book,
        released.execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("provenance-mapping-parent-close"),
            effect_id=recovery_fixtures.EFFECT,
            proof=recovery_fixtures._acceptance_proof(
                released.book,
                AcceptanceProofKind.COVERED_RECONCILIATION,
                "provenance-mapping-parent-proof",
            ),
        ),
    )
    assert (
        finalized.book.effect(recovery_fixtures.EFFECT).state
        is BrokerEffectState.OPERATOR_RECONCILED
    )

    correction = BrokerTradeCorrectFact(
        key=ExecutionFactKey(
            broker=recovery_fixtures.BROKER,
            environment=recovery_fixtures.ENVIRONMENT,
            account=recovery_fixtures.ACCOUNT,
            source_event_id=SourceEventId("provenance-non-tail-correction"),
        ),
        scope=recovery_fixtures._execution_scope(),
        root_fill_id=first_fact.root_fill_id,
        predecessor_source_event_id=first_fact.key.source_event_id,
        revised_quantity=Quantity(1),
        revised_price=recovery_fixtures._price(101),
    )
    unresolved = apply_venue_recovery_input(
        finalized.book,
        finalized.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("provenance-non-tail-correction-input"),
            effect_id=recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_A,
            prior_root_quantity=Quantity(2),
            prior_venue_cumulative_quantity=Quantity(4),
            resulting_venue_cumulative_quantity=Quantity(3),
            fact=correction,
            evidence_digest=b"\xd6" * 32,
            closure_id=ClosureId("provenance-non-tail-correction-closure"),
            evidence_reference=EvidenceReference(
                "provenance-non-tail-correction-proof"
            ),
        ),
    )
    assert unresolved.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert any(
        not coverage.mapping_exact for coverage in unresolved.book.broker_coverages
    )
    return unresolved


def _force_operator_reconciled(book):
    effect = book.effect(recovery_fixtures.EFFECT)
    assert effect is not None
    forced = replace(effect, state=BrokerEffectState.OPERATOR_RECONCILED)
    return tuple(
        forced if entry.effect_id == forced.effect_id else entry
        for entry in book.effects
    )


def test_public_checkpoint_has_no_importable_construction_capability() -> None:
    """Ordinary imports and the generated initializer must not mint checkpoints."""

    for name in (
        "_BOOK_CONSTRUCTION_TOKEN",
        "_rebuild_book",
        "_evolve_book",
    ):
        assert name not in vars(venue_module)
    with pytest.raises(TypeError, match="opaque|empty|reducer"):
        VenueRecoveryBook(scope=recovery_fixtures.VENUE_SCOPE)

    with pytest.raises(TypeError, match="opaque|subclass"):

        class ForgedBook(VenueRecoveryBook):
            pass

    with pytest.raises(TypeError, match="transition|subclass"):

        class ForgedTransition(VenueRecoveryTransition):
            pass


def test_empty_and_audit_hydration_reject_venue_scope_subclasses() -> None:
    class DelayedVenueScope(VenueScope):
        report_other_account = False

        def __getattribute__(self, name: str) -> object:
            if name == "account" and type(self).report_other_account:
                return AccountId("other-paper-account")
            return super().__getattribute__(name)

    exact_scope = recovery_fixtures.VENUE_SCOPE
    delayed_scope = DelayedVenueScope(
        generation=exact_scope.generation,
        broker=exact_scope.broker,
        environment=exact_scope.environment,
        account=exact_scope.account,
    )

    with pytest.raises(TypeError, match="exact VenueScope"):
        VenueRecoveryBook.empty(delayed_scope)

    book, execution = recovery_fixtures._seed_needs_review()
    with pytest.raises(TypeError, match="exact VenueScope"):
        _audit_hydrate_book(book, execution, scope=delayed_scope)


def test_venue_scope_rejects_a_delayed_account_identity_subclass() -> None:
    class DelayedAccountId(AccountId):
        reported_value = recovery_fixtures.ACCOUNT.value

        def __getattribute__(self, name: str) -> object:
            if name == "value":
                return type(self).reported_value
            return super().__getattribute__(name)

    exact_scope = recovery_fixtures.VENUE_SCOPE
    with pytest.raises(TypeError, match="account"):
        VenueScope(
            generation=exact_scope.generation,
            broker=exact_scope.broker,
            environment=exact_scope.environment,
            account=DelayedAccountId(exact_scope.account.value),
        )


def test_public_transition_rejects_execution_snapshot_subclasses() -> None:
    """Subclass overrides cannot impersonate one exact paired high-water."""

    book, execution = recovery_fixtures._seed_needs_review(capacity=4)

    class ForgedExecution(ExecutionSnapshot):
        pass

    forged = ForgedExecution(
        position=execution.position,
        integrity=execution.integrity,
        root_heads=execution.root_heads,
        seen_facts=execution.seen_facts,
    )
    with pytest.raises(TypeError, match="exact ExecutionSnapshot"):
        apply_venue_recovery_input(
            book,
            forged,
            book.input_records[0].item,
        )


def test_public_transition_cannot_mint_or_replace_quantity_delta() -> None:
    """Only the reducer may construct an exact transition and its economic delta."""

    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    replayed = apply_venue_recovery_input(
        book,
        execution,
        book.input_records[0].item,
    )
    assert replayed.disposition is VenueRecoveryDisposition.EXACT_REPLAY

    with pytest.raises(TypeError, match="opaque|reducer"):
        VenueRecoveryTransition(
            book=book,
            execution=execution,
            disposition=VenueRecoveryDisposition.APPLIED,
            quantity_delta=999,
        )
    with pytest.raises(TypeError, match="opaque|reducer"):
        replace(replayed, quantity_delta=-777)


def test_dataclasses_replace_cannot_mint_checkpoint_authority() -> None:
    """A valid output must not donate authority to a pre-fill checkpoint."""

    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    attested = recovery_fixtures._ingest(
        book,
        execution,
        recovery_fixtures._human_fill(input_suffix="provenance-replace-forgery"),
        input_id="provenance-replace-forgery-input",
    )
    assert attested.disposition is VenueRecoveryDisposition.APPLIED

    replace_kwargs = {
        "active_attempts": attested.book.active_attempts,
        "input_records": attested.book.input_records,
        "execution_registry_commitment": (attested.book.execution_registry_commitment),
        "execution_bindings": attested.book.execution_bindings,
        "human_coverages": attested.book.human_coverages,
    }
    with pytest.raises(TypeError, match="opaque|replace|reducer"):
        replace(book, **replace_kwargs)


def test_public_transition_constructor_cannot_pair_stale_human_authority() -> None:
    """Opaque construction cannot pair human authority with a stale snapshot."""

    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    attested = recovery_fixtures._ingest(
        book,
        execution,
        recovery_fixtures._human_fill(input_suffix="provenance-human-pair"),
        input_id="provenance-human-pair-input",
    )
    assert attested.disposition is VenueRecoveryDisposition.APPLIED

    with pytest.raises(TypeError, match="opaque|reducer"):
        VenueRecoveryTransition(
            book=attested.book,
            execution=execution,
            disposition=VenueRecoveryDisposition.APPLIED,
            quantity_delta=4,
        )


def test_public_transition_constructor_cannot_pair_stale_corroboration() -> None:
    """Opaque construction cannot pair corroboration with a prior registry."""

    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    attested = recovery_fixtures._ingest(
        book,
        execution,
        recovery_fixtures._human_fill(input_suffix="provenance-corroboration-pair"),
        input_id="provenance-corroboration-pair-human-input",
    )
    assert attested.disposition is VenueRecoveryDisposition.APPLIED
    corroborated = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("provenance-corroboration-pair-broker-input"),
            effect_id=recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=recovery_fixtures._broker_fill(
                "provenance-corroboration-pair-source",
                "provenance-corroboration-pair-root",
                quantity=4,
            ),
            evidence_digest=b"\xe1" * 32,
        ),
    )
    assert corroborated.disposition is VenueRecoveryDisposition.APPLIED
    assert corroborated.quantity_delta == 0

    with pytest.raises(TypeError, match="opaque|reducer"):
        VenueRecoveryTransition(
            book=corroborated.book,
            execution=attested.execution,
            disposition=VenueRecoveryDisposition.APPLIED,
            quantity_delta=0,
        )


def test_checkpoint_rejects_human_input_after_coverage_is_stripped() -> None:
    book, execution = recovery_fixtures._seed_needs_review()
    attested = recovery_fixtures._ingest(
        book,
        execution,
        recovery_fixtures._human_fill(input_suffix="provenance-strip-human"),
        input_id="provenance-strip-human-input",
    )
    attempt = attested.book.active_attempt(recovery_fixtures.LEG_A)
    assert attempt is not None

    with pytest.raises(ValueError, match="outcome|provenance|recovery input"):
        _audit_hydrate_book(
            attested.book,
            attested.execution,
            human_coverages=(),
            active_attempts=(replace(attempt, cumulative_quantity=Quantity(0)),),
        )


def test_checkpoint_rejects_semantic_alias_retargeted_as_direct_provenance() -> None:
    aliased, direct_command, alias_command = _broker_coverage_with_alias()
    coverage = aliased.book.broker_coverages[0]
    retargeted = replace(
        coverage,
        root_source_input_id=alias_command.input_id,
        head_source_input_id=alias_command.input_id,
    )
    retained_inputs = tuple(
        record
        for record in aliased.book.input_records
        if record.input_id != direct_command.input_id
    )

    with pytest.raises(ValueError, match="alias|direct|provenance"):
        _audit_hydrate_book(
            aliased.book,
            aliased.execution,
            input_records=retained_inputs,
            broker_coverages=(retargeted,),
        )


def test_direct_source_plus_semantic_alias_remains_a_valid_checkpoint() -> None:
    aliased, direct_command, _ = _broker_coverage_with_alias()

    rebuilt = _audit_hydrate_book(aliased.book, aliased.execution)

    assert rebuilt == aliased.book
    assert rebuilt.broker_coverages[0].root_source_input_id == direct_command.input_id


def test_checkpoint_rejects_stripped_owned_broker_attribution() -> None:
    """Execution economics cannot survive without their retained venue outcome."""

    aliased, _, _ = _broker_coverage_with_alias()
    attempt = aliased.book.active_attempt(recovery_fixtures.LEG_A)
    assert attempt is not None
    retained_inputs = tuple(
        record
        for record in aliased.book.input_records
        if not isinstance(record.item, RecordBrokerFillEvidence)
    )

    with pytest.raises(ValueError, match="broker observation|venue outcome"):
        _audit_hydrate_book(
            aliased.book,
            aliased.execution,
            input_records=retained_inputs,
            broker_coverages=(),
            active_attempts=(replace(attempt, cumulative_quantity=Quantity(0)),),
        )


def test_changed_broker_attribution_cannot_advance_serving_high_water() -> None:
    """A rejected command cannot poison the indexed release high-water."""

    aliased, direct_command, _ = _broker_coverage_with_alias()
    prior_high_water = aliased.book._economic_high_water(recovery_fixtures.LEG_A)
    changed = replace(
        direct_command,
        input_id=VenueInputId("provenance-changed-attribution-replay"),
        resulting_cumulative_quantity=Quantity(4),
    )

    rejected = apply_venue_recovery_input(
        aliased.book,
        aliased.execution,
        changed,
    )

    assert rejected.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert rejected.book._economic_high_water(recovery_fixtures.LEG_A) == (
        prior_high_water
    )


def test_checkpoint_rejects_changed_fill_input_after_reconciliation_is_stripped() -> (
    None
):
    book, execution = recovery_fixtures._seed_needs_review()
    attested = recovery_fixtures._ingest(
        book,
        execution,
        recovery_fixtures._human_fill(input_suffix="provenance-fill-base"),
        input_id="provenance-fill-base-input",
    )
    changed = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("provenance-changed-fill-input"),
            effect_id=recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=recovery_fixtures._broker_fill(
                "provenance-changed-fill-source",
                "provenance-changed-fill-root",
                quantity=4,
                units=101,
            ),
            evidence_digest=b"\xd7" * 32,
        ),
    )
    assert changed.book.reconciliations

    with pytest.raises(ValueError, match="outcome|provenance|recovery input"):
        _audit_hydrate_book(
            changed.book,
            changed.execution,
            reconciliations=(),
        )


def test_checkpoint_rejects_catch_up_input_after_registry_outcome_is_stripped() -> None:
    caught_up = _post_final_registry_reconciliation()

    with pytest.raises(ValueError, match="outcome|provenance|recovery input"):
        _audit_hydrate_book(
            caught_up.book,
            caught_up.execution,
            execution_reconciliations=(),
        )


def test_later_conflicting_evidence_cannot_remain_currently_operator_reconciled() -> (
    None
):
    reconciled = _post_final_fill_conflict()

    assert (
        reconciled.book.effect(recovery_fixtures.EFFECT).state
        is not BrokerEffectState.OPERATOR_RECONCILED
    )


def test_constructor_rejects_operator_state_with_unresolved_recovery_record() -> None:
    reconciled = _post_final_fill_conflict()

    with pytest.raises(ValueError, match="operator|reconcil|unresolved"):
        _audit_hydrate_book(
            reconciled.book,
            reconciled.execution,
            effects=_force_operator_reconciled(reconciled.book),
        )


def test_constructor_rejects_operator_state_with_unresolved_registry_record() -> None:
    caught_up = _post_final_registry_reconciliation()

    with pytest.raises(ValueError, match="operator|reconcil|unresolved"):
        _audit_hydrate_book(
            caught_up.book,
            caught_up.execution,
            effects=_force_operator_reconciled(caught_up.book),
        )


@pytest.mark.parametrize(
    "integrity_bit",
    [
        PositionIntegrity.EXECUTION_FACT_CONFLICT,
        PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED,
    ],
    ids=("fact-conflict", "execution-reconciliation"),
)
def test_constructor_rejects_operator_state_with_unresolved_binding_bits(
    integrity_bit: PositionIntegrity,
) -> None:
    finalized = _finalized_human_effect()
    binding = finalized.book.execution_binding(recovery_fixtures.POSITION_SCOPE)
    assert binding is not None
    forged_binding = replace(
        binding,
        integrity_bits=binding.integrity_bits | integrity_bit.value,
    )

    with pytest.raises(ValueError, match="operator|integrity|conflict|reconcil"):
        _audit_hydrate_book(
            finalized.book,
            finalized.execution,
            execution_bindings=(forged_binding,),
        )


def test_constructor_rejects_operator_state_with_unresolved_mapping() -> None:
    unresolved = _post_final_unresolved_mapping()

    with pytest.raises(ValueError, match="operator|mapping|reconcil|unresolved"):
        _audit_hydrate_book(
            unresolved.book,
            unresolved.execution,
            effects=_force_operator_reconciled(unresolved.book),
        )
