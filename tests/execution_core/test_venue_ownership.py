"""RED examples for venue-effect ownership and occurrence closure.

These tests intentionally describe the pure M1B contract before ``venue.py``
exists.  Broker completeness, persistence, and runtime dispatch remain typed
inputs or later gates; no test infers them from a terminal order.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.execution_core.fills import ExecutionSide, PositionScope
from app.execution_core.identity import (
    AccountId,
    ApplicationGenerationId,
    BrokerId,
    ClaimOccurrenceId,
    ClientOrderId,
    ClosureId,
    EffectId,
    EnvironmentId,
    EvidenceReference,
    MandateId,
    OrderId,
    RequestOccurrenceId,
    SymbolId,
    VenueInputId,
    VenueLegKey,
    VenueObservationId,
)
from app.execution_core.position import ExecutionSnapshot
from app.execution_core.values import Quantity
from app.execution_core.venue import (
    AcceptanceProof,
    AcceptanceProofKind,
    AcceptanceSetState,
    BrokerEffectState,
    CancelBeforeDispatch,
    CloseAcceptanceSet,
    DiscoverVenueLeg,
    EffectKind,
    ObserveVenueStatus,
    PendingVenueOperation,
    RecordDispatchClaim,
    RecordPendingVenueOperation,
    RecordTransportOutcome,
    RecoverClaimedEffect,
    RequestedEffect,
    VenueAttemptState,
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    VenueScope,
    _rebuild_book,
    apply_venue_recovery_input,
)


BROKER = BrokerId("alpaca")
ENVIRONMENT = EnvironmentId("paper")
ACCOUNT = AccountId("account-001")
GENERATION = ApplicationGenerationId("reset-generation-1")
SYMBOL = SymbolId("AAPL")
VENUE_SCOPE = VenueScope(
    generation=GENERATION,
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
)
POSITION_SCOPE = PositionScope(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    symbol_id=SYMBOL,
)
EXECUTION = ExecutionSnapshot.flat(POSITION_SCOPE)


def _request(
    tag: str = "submit-1",
    *,
    kind: EffectKind = EffectKind.SUBMIT,
    side: ExecutionSide = ExecutionSide.BUY,
) -> RequestedEffect:
    return RequestedEffect(
        input_id=VenueInputId(f"request-{tag}"),
        effect_id=EffectId(f"effect-{tag}"),
        request_occurrence_id=RequestOccurrenceId(f"occurrence-{tag}"),
        mandate_id=MandateId(f"mandate-{tag}"),
        kind=kind,
        client_order_id=ClientOrderId(f"client-{tag}"),
        symbol_id=SYMBOL,
        side=side,
        quantity=Quantity(10),
        economic_scope=f"economic-{tag}".encode(),
    )


def _leg(tag: str) -> VenueLegKey:
    return VenueLegKey(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        order_id=OrderId(f"venue-order-{tag}"),
    )


def _apply(
    book: VenueRecoveryBook,
    item: object,
    execution: ExecutionSnapshot = EXECUTION,
):
    return apply_venue_recovery_input(book, execution, item)


def _requested(tag: str = "submit-1") -> tuple[VenueRecoveryBook, RequestedEffect]:
    request = _request(tag)
    transition = _apply(VenueRecoveryBook.empty(VENUE_SCOPE), request)
    assert transition.disposition is VenueRecoveryDisposition.APPLIED
    return transition.book, request


def _claimed(tag: str = "submit-1") -> tuple[VenueRecoveryBook, RequestedEffect]:
    book, request = _requested(tag)
    transition = _apply(
        book,
        RecordDispatchClaim(
            input_id=VenueInputId(f"claim-{tag}"),
            effect_id=request.effect_id,
            claim_occurrence_id=ClaimOccurrenceId(f"claim-occurrence-{tag}"),
        ),
    )
    assert transition.disposition is VenueRecoveryDisposition.APPLIED
    return transition.book, request


def _acknowledged(tag: str = "submit-1") -> tuple[VenueRecoveryBook, RequestedEffect]:
    book, request = _claimed(tag)
    transition = _apply(
        book,
        RecordTransportOutcome(
            input_id=VenueInputId(f"ack-{tag}"),
            effect_id=request.effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    assert transition.disposition is VenueRecoveryDisposition.APPLIED
    return transition.book, request


def _discover(
    book: VenueRecoveryBook,
    request: RequestedEffect,
    tag: str,
):
    return _apply(
        book,
        DiscoverVenueLeg(
            input_id=VenueInputId(f"discover-{tag}"),
            effect_id=request.effect_id,
            leg_key=_leg(tag),
            observation_id=VenueObservationId(f"acceptance-{tag}"),
        ),
    )


def _terminal_observation(
    tag: str,
    *,
    status: VenueAttemptState = VenueAttemptState.FILLED,
    quantity: int = 10,
    suffix: str = "root",
) -> ObserveVenueStatus:
    return ObserveVenueStatus(
        input_id=VenueInputId(f"terminal-{tag}-{suffix}"),
        leg_key=_leg(tag),
        status=status,
        observation_id=VenueObservationId(f"terminal-observation-{tag}-{suffix}"),
        cumulative_quantity=Quantity(quantity),
        closure_id=ClosureId(f"closure-{tag}-{suffix}"),
        evidence_reference=EvidenceReference(f"evidence-{tag}-{suffix}"),
    )


def _acceptance_proof(
    book: VenueRecoveryBook,
    effect_id: EffectId,
    kind: AcceptanceProofKind,
    evidence: str,
) -> AcceptanceProof:
    effect = book.effect(effect_id)
    assert effect is not None
    return AcceptanceProof(
        kind=kind,
        effect_scope=effect.scope,
        claim_occurrence_id=(
            None
            if kind is AcceptanceProofKind.NEVER_DISPATCHED
            else effect.claim_occurrence_id
        ),
        evidence_reference=EvidenceReference(evidence),
        evidence_digest=b"\xa5" * 32,
    )


def test_requested_effect_starts_open_and_is_quantity_neutral() -> None:
    request = _request()
    original = VenueRecoveryBook.empty(VENUE_SCOPE)

    transition = _apply(original, request)

    effect = transition.book.effect(request.effect_id)
    assert transition.disposition is VenueRecoveryDisposition.APPLIED
    assert transition.execution == EXECUTION
    assert transition.quantity_delta == 0
    assert effect.state is BrokerEffectState.REQUESTED
    assert effect.acceptance_set_state is AcceptanceSetState.OPEN
    assert effect.claim_occurrence_id is None
    assert effect.acceptance_proof is None
    assert transition.book.owners == ()
    assert transition.book.active_attempts == ()
    assert transition.book.closure_heads == ()


def test_input_replay_is_exact_but_changed_payload_conflicts_without_mutation() -> None:
    book, request = _requested()

    replay = _apply(book, request)
    changed = _apply(book, replace(request, quantity=Quantity(11)))

    assert replay.disposition is VenueRecoveryDisposition.EXACT_REPLAY
    assert replay.book == book
    assert changed.disposition is VenueRecoveryDisposition.CONFLICT
    assert changed.book == book
    assert changed.execution == EXECUTION
    assert changed.quantity_delta == 0


def test_dispatch_claim_is_immutable_and_prevents_cancel_or_second_claim() -> None:
    book, request = _requested()
    claim = RecordDispatchClaim(
        input_id=VenueInputId("claim-submit-1"),
        effect_id=request.effect_id,
        claim_occurrence_id=ClaimOccurrenceId("claim-occurrence-submit-1"),
    )
    claimed = _apply(book, claim)
    claimed_effect = claimed.book.effect(request.effect_id)

    assert claimed_effect.state is BrokerEffectState.DISPATCH_CLAIMED
    assert claimed_effect.claim_occurrence_id == claim.claim_occurrence_id
    assert (
        _apply(claimed.book, claim).disposition is VenueRecoveryDisposition.EXACT_REPLAY
    )

    second_claim = _apply(
        claimed.book,
        replace(
            claim,
            input_id=VenueInputId("claim-submit-1-again"),
            claim_occurrence_id=ClaimOccurrenceId("different-claim"),
        ),
    )
    canceled = _apply(
        claimed.book,
        CancelBeforeDispatch(
            input_id=VenueInputId("cancel-after-claim"),
            effect_id=request.effect_id,
        ),
    )

    assert second_claim.disposition is VenueRecoveryDisposition.CONFLICT
    assert canceled.disposition is VenueRecoveryDisposition.REFUSED
    assert second_claim.book == canceled.book == claimed.book


def test_never_dispatched_requires_local_cancel_and_absent_claim() -> None:
    requested, request = _requested()
    premature = _apply(
        requested,
        CloseAcceptanceSet(
            input_id=VenueInputId("premature-never-dispatched"),
            effect_id=request.effect_id,
            proof=_acceptance_proof(
                requested,
                request.effect_id,
                AcceptanceProofKind.NEVER_DISPATCHED,
                "local-decision-only",
            ),
        ),
    )
    assert premature.disposition is VenueRecoveryDisposition.REFUSED
    assert (
        premature.book.effect(request.effect_id).acceptance_set_state
        is AcceptanceSetState.OPEN
    )

    canceled = _apply(
        requested,
        CancelBeforeDispatch(
            input_id=VenueInputId("cancel-before-dispatch"),
            effect_id=request.effect_id,
        ),
    )
    closed = _apply(
        canceled.book,
        CloseAcceptanceSet(
            input_id=VenueInputId("close-never-dispatched"),
            effect_id=request.effect_id,
            proof=_acceptance_proof(
                canceled.book,
                request.effect_id,
                AcceptanceProofKind.NEVER_DISPATCHED,
                "no-immutable-claim-row",
            ),
        ),
    )

    effect = closed.book.effect(request.effect_id)
    assert effect.state is BrokerEffectState.CANCELED_BEFORE_DISPATCH
    assert effect.acceptance_set_state is AcceptanceSetState.CLOSED
    assert effect.acceptance_proof.kind is AcceptanceProofKind.NEVER_DISPATCHED
    assert effect.acceptance_proof.evidence_reference == EvidenceReference(
        "no-immutable-claim-row"
    )


def test_late_acceptance_invalidates_closed_never_dispatched_proof() -> None:
    requested, request = _requested("late-never-dispatched")
    canceled = _apply(
        requested,
        CancelBeforeDispatch(
            input_id=VenueInputId("cancel-late-never-dispatched"),
            effect_id=request.effect_id,
        ),
    )
    close_input = CloseAcceptanceSet(
        input_id=VenueInputId("close-late-never-dispatched"),
        effect_id=request.effect_id,
        proof=_acceptance_proof(
            canceled.book,
            request.effect_id,
            AcceptanceProofKind.NEVER_DISPATCHED,
            "locally-proven-absence-before-late-acceptance",
        ),
    )
    closed = _apply(canceled.book, close_input)
    original_proof = closed.book.effect(request.effect_id).acceptance_proof

    late = _discover(closed.book, request, "late-never-dispatched")
    effect = late.book.effect(request.effect_id)

    assert late.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert effect.acceptance_set_state is AcceptanceSetState.INVALIDATED
    assert effect.acceptance_proof == original_proof
    assert effect.contradiction_evidence[-1].leg_key == _leg("late-never-dispatched")
    assert effect.contradiction_evidence[-1].observation_id == VenueObservationId(
        "acceptance-late-never-dispatched"
    )
    assert late.book.owner(_leg("late-never-dispatched")).effect_id == request.effect_id


def test_committed_claim_makes_never_dispatched_permanently_impossible() -> None:
    claimed, request = _claimed()
    close = CloseAcceptanceSet(
        input_id=VenueInputId("false-never-dispatched"),
        effect_id=request.effect_id,
        proof=_acceptance_proof(
            claimed,
            request.effect_id,
            AcceptanceProofKind.NEVER_DISPATCHED,
            "corrupt-effect-row-says-canceled",
        ),
    )

    refused = _apply(claimed, close)

    effect = refused.book.effect(request.effect_id)
    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert effect.state is BrokerEffectState.DISPATCH_CLAIMED
    assert effect.claim_occurrence_id is not None
    assert effect.acceptance_set_state is AcceptanceSetState.OPEN


def test_acceptance_proof_must_bind_exact_effect_scope_and_claim() -> None:
    claimed, request = _claimed("proof-binding")
    exact = _acceptance_proof(
        claimed,
        request.effect_id,
        AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
        "scope-bound-complete-response",
    )
    wrong_scope = replace(
        exact,
        effect_scope=replace(
            exact.effect_scope,
            request_occurrence_id=RequestOccurrenceId("wrong-proof-occurrence"),
        ),
    )
    wrong_claim = replace(
        exact,
        claim_occurrence_id=ClaimOccurrenceId("wrong-proof-claim"),
    )

    for suffix, proof in (("scope", wrong_scope), ("claim", wrong_claim)):
        refused = _apply(
            claimed,
            CloseAcceptanceSet(
                input_id=VenueInputId(f"wrong-{suffix}-proof"),
                effect_id=request.effect_id,
                proof=proof,
            ),
        )
        assert refused.disposition is VenueRecoveryDisposition.REFUSED
        assert refused.book == claimed


def test_checkpoint_construction_rejects_closed_effect_without_proof() -> None:
    requested, request = _requested("forged-closure")
    effect = requested.effect(request.effect_id)
    assert effect is not None
    forged = replace(effect, acceptance_set_state=AcceptanceSetState.CLOSED)

    with pytest.raises(ValueError, match="proof"):
        _rebuild_book(requested, effects=(forged,))


def test_restart_converts_stranded_claim_to_unknown_without_resend() -> None:
    claimed, request = _claimed()
    recovery = RecoverClaimedEffect(
        input_id=VenueInputId("restart-claimed-effect"),
        effect_id=request.effect_id,
    )

    recovered = _apply(claimed, recovery)

    effect = recovered.book.effect(request.effect_id)
    assert recovered.disposition is VenueRecoveryDisposition.APPLIED
    assert effect.state is BrokerEffectState.OUTCOME_UNKNOWN
    assert effect.claim_occurrence_id == ClaimOccurrenceId("claim-occurrence-submit-1")
    assert (
        _apply(recovered.book, recovery).disposition
        is VenueRecoveryDisposition.EXACT_REPLAY
    )
    assert (
        _apply(
            recovered.book,
            RecordDispatchClaim(
                input_id=VenueInputId("blind-resend"),
                effect_id=request.effect_id,
                claim_occurrence_id=ClaimOccurrenceId("resend-claim"),
            ),
        ).disposition
        is VenueRecoveryDisposition.REFUSED
    )


def test_transport_ack_is_quantity_neutral_and_does_not_create_attempt() -> None:
    claimed, request = _claimed()

    acknowledged = _apply(
        claimed,
        RecordTransportOutcome(
            input_id=VenueInputId("acknowledge-submit"),
            effect_id=request.effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )

    assert (
        acknowledged.book.effect(request.effect_id).state
        is BrokerEffectState.ACKNOWLEDGED
    )
    assert acknowledged.book.active_attempts == ()
    assert acknowledged.execution == EXECUTION
    assert acknowledged.quantity_delta == 0


def test_terminal_transport_outcome_cannot_regress() -> None:
    claimed, request = _claimed()
    rejected = _apply(
        claimed,
        RecordTransportOutcome(
            input_id=VenueInputId("definitive-rejection"),
            effect_id=request.effect_id,
            state=BrokerEffectState.REJECTED,
        ),
    )

    delayed_ack = _apply(
        rejected.book,
        RecordTransportOutcome(
            input_id=VenueInputId("delayed-ack"),
            effect_id=request.effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )

    assert delayed_ack.disposition is VenueRecoveryDisposition.REFUSED
    assert delayed_ack.book == rejected.book
    assert (
        delayed_ack.book.effect(request.effect_id).state is BrokerEffectState.REJECTED
    )


def test_one_effect_owns_multiple_concrete_acceptances_without_overwrite() -> None:
    book, request = _acknowledged()

    first = _discover(book, request, "a")
    second = _discover(first.book, request, "b")

    owner_a = second.book.owner(_leg("a"))
    owner_b = second.book.owner(_leg("b"))
    assert second.disposition is VenueRecoveryDisposition.APPLIED
    assert len(second.book.owners) == 2
    assert owner_a.leg_key != owner_b.leg_key
    assert owner_a.effect_scope == owner_b.effect_scope
    assert owner_a.effect_scope == second.book.effect(request.effect_id).scope
    assert second.book.active_attempt(_leg("a")).status is VenueAttemptState.WORKING
    assert second.book.active_attempt(_leg("b")).status is VenueAttemptState.WORKING


def test_venue_identity_owner_cannot_be_rebound_to_another_effect() -> None:
    book, first_request = _acknowledged("first")
    owned = _discover(book, first_request, "shared")
    second_request = _request("second")
    with_second = _apply(owned.book, second_request)

    rebind = _apply(
        with_second.book,
        DiscoverVenueLeg(
            input_id=VenueInputId("rebind-shared-leg"),
            effect_id=second_request.effect_id,
            leg_key=_leg("shared"),
            observation_id=VenueObservationId("second-effect-acceptance"),
        ),
    )

    assert rebind.disposition is VenueRecoveryDisposition.CONFLICT
    assert rebind.book == with_second.book
    assert (
        rebind.book.owner(_leg("shared")).effect_scope.effect_id
        == first_request.effect_id
    )


@pytest.mark.parametrize(
    "operation",
    [PendingVenueOperation.CANCEL, PendingVenueOperation.REPLACE],
)
def test_pending_cancel_or_replace_is_orthogonal_to_order_status(
    operation: PendingVenueOperation,
) -> None:
    book, request = _acknowledged()
    discovered = _discover(book, request, "orthogonal")
    pending = _apply(
        discovered.book,
        RecordPendingVenueOperation(
            input_id=VenueInputId(f"pending-{operation.name.lower()}"),
            leg_key=_leg("orthogonal"),
            operation=operation,
        ),
    )

    filled_during_ambiguity = _apply(
        pending.book,
        ObserveVenueStatus(
            input_id=VenueInputId(f"partial-during-{operation.name.lower()}"),
            leg_key=_leg("orthogonal"),
            status=VenueAttemptState.PARTIALLY_FILLED,
            observation_id=VenueObservationId(
                f"partial-observation-{operation.name.lower()}"
            ),
            cumulative_quantity=Quantity(3),
        ),
    )

    attempt = filled_during_ambiguity.book.active_attempt(_leg("orthogonal"))
    assert attempt.status is VenueAttemptState.PARTIALLY_FILLED
    assert attempt.pending_operation is operation
    assert attempt.cumulative_quantity == Quantity(3)
    assert filled_during_ambiguity.execution == EXECUTION
    assert filled_during_ambiguity.quantity_delta == 0


def test_operator_reconciled_cannot_enter_through_broker_status_ingestion() -> None:
    book, request = _acknowledged("operator-bypass")
    discovered = _discover(book, request, "operator-bypass")
    forged = ObserveVenueStatus(
        input_id=VenueInputId("forged-operator-terminal"),
        leg_key=_leg("operator-bypass"),
        status=VenueAttemptState.OPERATOR_RECONCILED,
        observation_id=VenueObservationId("forged-operator-observation"),
        cumulative_quantity=Quantity(0),
        closure_id=ClosureId("forged-operator-closure"),
        evidence_reference=EvidenceReference("forged-operator-evidence"),
    )

    refused = _apply(discovered.book, forged)

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.book == discovered.book
    assert refused.execution == EXECUTION


def test_new_semantic_owner_replay_still_consumes_its_input_identity() -> None:
    book, request = _acknowledged("owner-alias")
    discovered = _discover(book, request, "owner-alias")
    alias = DiscoverVenueLeg(
        input_id=VenueInputId("owner-alias-input"),
        effect_id=request.effect_id,
        leg_key=_leg("owner-alias"),
        observation_id=VenueObservationId("acceptance-owner-alias"),
    )

    accepted_alias = _apply(discovered.book, alias)

    assert accepted_alias.disposition is VenueRecoveryDisposition.APPLIED
    assert accepted_alias.book.owner(_leg("owner-alias")) == discovered.book.owner(
        _leg("owner-alias")
    )
    exact = _apply(accepted_alias.book, alias)
    assert exact.disposition is VenueRecoveryDisposition.EXACT_REPLAY
    assert exact.book == accepted_alias.book

    changed_same_input = replace(
        alias,
        leg_key=_leg("different-leg"),
        observation_id=VenueObservationId("different-observation"),
    )
    conflict = _apply(accepted_alias.book, changed_same_input)
    assert conflict.disposition is VenueRecoveryDisposition.CONFLICT
    assert conflict.book == accepted_alias.book


def test_request_occurrence_identity_is_generation_account_unique() -> None:
    first = _request("unique-first")
    first_book = _apply(VenueRecoveryBook.empty(VENUE_SCOPE), first).book
    duplicated_request = replace(
        _request("unique-second"),
        request_occurrence_id=first.request_occurrence_id,
    )

    request_conflict = _apply(first_book, duplicated_request)

    assert request_conflict.disposition is VenueRecoveryDisposition.CONFLICT
    assert request_conflict.book == first_book


def test_claim_occurrence_identity_is_generation_account_unique() -> None:
    first = _request("unique-first")
    first_book = _apply(VenueRecoveryBook.empty(VENUE_SCOPE), first).book
    second = _request("unique-second")
    two_effects = _apply(first_book, second)
    claim_id = ClaimOccurrenceId("globally-unique-claim")
    first_claim = _apply(
        two_effects.book,
        RecordDispatchClaim(
            input_id=VenueInputId("first-unique-claim"),
            effect_id=first.effect_id,
            claim_occurrence_id=claim_id,
        ),
    )
    duplicate_claim = _apply(
        first_claim.book,
        RecordDispatchClaim(
            input_id=VenueInputId("duplicate-claim"),
            effect_id=second.effect_id,
            claim_occurrence_id=claim_id,
        ),
    )

    assert duplicate_claim.disposition is VenueRecoveryDisposition.CONFLICT
    assert duplicate_claim.book == first_claim.book


def test_later_terminal_status_advances_observation_without_economics() -> None:
    book, request = _acknowledged("terminal-advance")
    discovered = _discover(book, request, "terminal-advance")
    canceled = _apply(
        discovered.book,
        _terminal_observation(
            "terminal-advance",
            status=VenueAttemptState.CANCELED,
            quantity=3,
            suffix="canceled",
        ),
    )
    later_fill = _apply(
        canceled.book,
        _terminal_observation(
            "terminal-advance",
            status=VenueAttemptState.FILLED,
            quantity=4,
            suffix="filled",
        ),
    )

    assert later_fill.disposition is VenueRecoveryDisposition.APPLIED
    closure = later_fill.book.closure_head(_leg("terminal-advance"))
    assert closure is not None
    assert closure.ordinal == 2
    assert closure.predecessor_closure_id == ClosureId(
        "closure-terminal-advance-canceled"
    )
    assert closure.status is VenueAttemptState.FILLED
    assert closure.cumulative_quantity == Quantity(0)
    assert closure.observed_cumulative_quantity == Quantity(4)


def test_pending_operation_has_one_canonical_absence_representation() -> None:
    book, request = _acknowledged("pending-none")
    discovered = _discover(book, request, "pending-none")
    clear_with_enum = RecordPendingVenueOperation(
        input_id=VenueInputId("pending-none-input"),
        leg_key=_leg("pending-none"),
        operation=PendingVenueOperation.NONE,
    )

    refused = _apply(discovered.book, clear_with_enum)

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.book == discovered.book


def test_terminal_leg_compacts_to_single_ordinal_one_closure_root() -> None:
    book, request = _acknowledged()
    discovered = _discover(book, request, "compact")

    terminal = _apply(discovered.book, _terminal_observation("compact"))

    head = terminal.book.closure_head(_leg("compact"))
    assert terminal.disposition is VenueRecoveryDisposition.APPLIED
    assert terminal.book.active_attempt(_leg("compact")) is None
    assert head.ordinal == 1
    assert head.predecessor_closure_id is None
    assert head.closure_id == ClosureId("closure-compact-root")
    assert head.status is VenueAttemptState.FILLED
    assert head.cumulative_quantity == Quantity(0)
    assert head.observed_cumulative_quantity == Quantity(10)
    assert (
        terminal.book.effect(request.effect_id).acceptance_set_state
        is AcceptanceSetState.OPEN
    )


def test_later_terminal_status_appends_immediate_same_owner_closure_successor() -> None:
    book, request = _acknowledged()
    root = _apply(
        _discover(book, request, "chain").book, _terminal_observation("chain")
    )

    successor = _apply(
        root.book,
        _terminal_observation("chain", quantity=11, suffix="successor"),
    )

    head = successor.book.closure_head(_leg("chain"))
    assert successor.disposition is VenueRecoveryDisposition.APPLIED
    assert head.ordinal == 2
    assert head.predecessor_closure_id == ClosureId("closure-chain-root")
    assert head.closure_id == ClosureId("closure-chain-successor")
    assert head.cumulative_quantity == Quantity(0)
    assert head.observed_cumulative_quantity == Quantity(11)
    assert len(successor.book.closure_heads) == 1
    assert successor.book.active_attempt(_leg("chain")) is None


def test_changed_terminal_replay_cannot_fork_closure_chain() -> None:
    book, request = _acknowledged()
    terminal_input = _terminal_observation("fork")
    terminal = _apply(_discover(book, request, "fork").book, terminal_input)

    changed_same_observation = _apply(
        terminal.book,
        replace(
            terminal_input,
            closure_id=ClosureId("competing-root"),
            evidence_reference=EvidenceReference("competing-evidence"),
        ),
    )

    assert changed_same_observation.disposition is VenueRecoveryDisposition.CONFLICT
    assert changed_same_observation.book == terminal.book
    assert terminal.book.closure_head(_leg("fork")).ordinal == 1


def test_delayed_status_cannot_reactivate_terminal_leg() -> None:
    book, request = _acknowledged()
    terminal = _apply(
        _discover(book, request, "non-regression").book,
        _terminal_observation("non-regression"),
    )

    stale = _apply(
        terminal.book,
        ObserveVenueStatus(
            input_id=VenueInputId("stale-working-status"),
            leg_key=_leg("non-regression"),
            status=VenueAttemptState.WORKING,
            observation_id=VenueObservationId("stale-working-observation"),
            cumulative_quantity=Quantity(0),
        ),
    )

    assert stale.disposition is VenueRecoveryDisposition.REFUSED
    assert stale.book == terminal.book
    assert stale.book.active_attempt(_leg("non-regression")) is None
    assert (
        stale.book.closure_head(_leg("non-regression")).status
        is VenueAttemptState.FILLED
    )


def test_ar02_terminal_known_leg_does_not_close_open_acceptance_set() -> None:
    book, request = _acknowledged()
    terminal = _apply(
        _discover(book, request, "known-a").book,
        _terminal_observation("known-a"),
    )

    effect = terminal.book.effect(request.effect_id)
    assert effect.acceptance_set_state is AcceptanceSetState.OPEN
    assert terminal.book.closure_head(_leg("known-a")) is not None

    closed = _apply(
        terminal.book,
        CloseAcceptanceSet(
            input_id=VenueInputId("covered-occurrence-close"),
            effect_id=request.effect_id,
            proof=_acceptance_proof(
                terminal.book,
                request.effect_id,
                AcceptanceProofKind.COVERED_RECONCILIATION,
                "exact-query-plus-complete-coverage",
            ),
        ),
    )
    assert (
        closed.book.effect(request.effect_id).acceptance_set_state
        is AcceptanceSetState.CLOSED
    )


def test_ar02_late_second_acceptance_invalidates_and_preserves_closure_proof() -> None:
    book, request = _acknowledged()
    first_terminal = _apply(
        _discover(book, request, "known-first").book,
        _terminal_observation("known-first"),
    )
    close_input = CloseAcceptanceSet(
        input_id=VenueInputId("certified-complete-response"),
        effect_id=request.effect_id,
        proof=_acceptance_proof(
            first_terminal.book,
            request.effect_id,
            AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
            "adapter-certified-response",
        ),
    )
    closed = _apply(first_terminal.book, close_input)
    original_proof = closed.book.effect(request.effect_id).acceptance_proof

    late = _discover(closed.book, request, "latent-second")
    effect = late.book.effect(request.effect_id)

    assert late.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert effect.acceptance_set_state is AcceptanceSetState.INVALIDATED
    assert effect.acceptance_proof == original_proof
    assert effect.contradiction_evidence[-1].leg_key == _leg("latent-second")
    assert effect.contradiction_evidence[-1].observation_id == VenueObservationId(
        "acceptance-latent-second"
    )
    assert (
        late.book.owner(_leg("latent-second")).effect_scope.effect_id
        == request.effect_id
    )

    impossible_reclose = _apply(
        late.book,
        replace(
            close_input,
            input_id=VenueInputId("attempted-reclose-after-invalidation"),
        ),
    )
    assert impossible_reclose.disposition is VenueRecoveryDisposition.REFUSED
    assert (
        impossible_reclose.book.effect(request.effect_id).acceptance_set_state
        is AcceptanceSetState.INVALIDATED
    )


def test_late_acceptance_invalidates_closed_rejected_effect_proof() -> None:
    claimed, request = _claimed("late-rejected")
    rejected = _apply(
        claimed,
        RecordTransportOutcome(
            input_id=VenueInputId("reject-before-late-acceptance"),
            effect_id=request.effect_id,
            state=BrokerEffectState.REJECTED,
        ),
    )
    close_input = CloseAcceptanceSet(
        input_id=VenueInputId("close-rejected-contract-complete"),
        effect_id=request.effect_id,
        proof=_acceptance_proof(
            rejected.book,
            request.effect_id,
            AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
            "contract-complete-before-late-rejected-acceptance",
        ),
    )
    closed = _apply(rejected.book, close_input)
    original_proof = closed.book.effect(request.effect_id).acceptance_proof

    late = _discover(closed.book, request, "late-rejected")
    effect = late.book.effect(request.effect_id)

    assert late.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert effect.state is BrokerEffectState.REJECTED
    assert effect.acceptance_set_state is AcceptanceSetState.INVALIDATED
    assert effect.acceptance_proof == original_proof
    assert effect.contradiction_evidence[-1].leg_key == _leg("late-rejected")
    assert effect.contradiction_evidence[-1].observation_id == VenueObservationId(
        "acceptance-late-rejected"
    )
    assert late.book.owner(_leg("late-rejected")).effect_id == request.effect_id


def test_closure_proof_refuses_while_a_known_leg_is_active() -> None:
    book, request = _acknowledged()
    discovered = _discover(book, request, "still-working")

    refused = _apply(
        discovered.book,
        CloseAcceptanceSet(
            input_id=VenueInputId("close-with-working-leg"),
            effect_id=request.effect_id,
            proof=_acceptance_proof(
                discovered.book,
                request.effect_id,
                AcceptanceProofKind.COVERED_RECONCILIATION,
                "coverage-cannot-erase-active-leg",
            ),
        ),
    )

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.book == discovered.book
    assert (
        refused.book.effect(request.effect_id).acceptance_set_state
        is AcceptanceSetState.OPEN
    )


def test_exact_types_and_full_scope_are_not_coerced() -> None:
    with pytest.raises(TypeError):
        VenueScope(
            generation="reset-generation-1",  # type: ignore[arg-type]
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
        )
    with pytest.raises(TypeError):
        VenueLegKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            order_id="venue-order",  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        replace(_request(), economic_scope=bytearray(b"economic"))
