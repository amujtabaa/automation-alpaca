"""RED-first examples for WO-0146 human-attested venue recovery.

These tests own no broker, database, clock, or runtime fixture.  Every identity,
economic value, observation, and proof is explicit.  The suite deliberately
imports the not-yet-implemented recovery vocabulary so collection is the first
RED gate.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from fractions import Fraction

import pytest

import app.execution_core.recovery as recovery_module
from app.execution_core.fills import (
    BrokerFillFact,
    BrokerTradeBustFact,
    BrokerTradeCorrectFact,
    ExecutionAuthority,
    ExecutionScope,
    ExecutionSide,
    HumanAttestedFillFact,
    PositionScope,
    RootHeadIndex,
)
from app.execution_core.identity import (
    AccountId,
    ActorId,
    ApplicationGenerationId,
    BrokerId,
    ClaimOccurrenceId,
    ClientOrderId,
    ClosureId,
    EffectId,
    EnvironmentId,
    EvidenceReference,
    ExecutionFactKey,
    MandateId,
    OrderId,
    RequestOccurrenceId,
    RootFillId,
    RootFillKey,
    SourceEventId,
    SymbolId,
    VenueInputId,
    VenueLegKey,
    VenueObservationId,
)
from app.execution_core.position import (
    ExecutionSnapshot,
    PositionIntegrity,
    PositionState,
    TransitionDisposition,
    apply_broker_execution_fact,
)
from app.execution_core.recovery import (
    IngestHumanAttestedFill,
    RecordBrokerFillEvidence,
    RecordBrokerRevisionEvidence,
    ReleaseVenueLeg,
)
from app.execution_core.values import (
    ExactBasis,
    PriceScale,
    PriceUnits,
    Quantity,
    ReportedPrice,
    TickMetadata,
)
from app.execution_core.venue import (
    AcceptanceContradiction,
    AcceptanceProof,
    AcceptanceProofKind,
    AcceptanceSetState,
    BrokerEffectState,
    CloseAcceptanceSet,
    DiscoverVenueLeg,
    EffectKind,
    ObserveVenueStatus,
    PendingVenueOperation,
    RecordDispatchClaim,
    RecordPendingVenueOperation,
    RecordTransportOutcome,
    RequestedEffect,
    VenueAttemptState,
    VenueClosureKind,
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    VenueScope,
    _apply_venue_input,
    _audit_hydrate_book,
    apply_venue_recovery_input as _public_apply_venue_recovery_input,
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


def apply_venue_recovery_input(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
):
    reducer = (
        _apply_venue_input
        if type(item)
        in {RequestedEffect, RecordDispatchClaim, RecordPendingVenueOperation}
        else _public_apply_venue_recovery_input
    )
    return reducer(book, execution, item)


EFFECT = EffectId("effect-submit-1")
REQUEST = RequestOccurrenceId("request-occurrence-1")
CLAIM = ClaimOccurrenceId("claim-occurrence-1")
CLIENT = ClientOrderId("client-order-reset-1")
MANDATE = MandateId("mandate-1")
LEG_A = VenueLegKey(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    order_id=OrderId("venue-order-a"),
)
LEG_B = VenueLegKey(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    order_id=OrderId("venue-order-b"),
)
ACTOR = ActorId("operator-a")
EVIDENCE = EvidenceReference("paper-order-report-1")
SCALE = PriceScale(Decimal("1"))
TICK = TickMetadata(tick_units=PriceUnits(1), scale=SCALE)


def _price(units: int) -> ReportedPrice:
    return ReportedPrice(units=PriceUnits(units), scale=SCALE, tick=TICK)


def _execution_scope(
    *,
    leg_key: VenueLegKey = LEG_A,
    side: ExecutionSide = ExecutionSide.BUY,
    symbol: SymbolId = SYMBOL,
) -> ExecutionScope:
    return ExecutionScope(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        order_id=leg_key.order_id,
        symbol_id=symbol,
        side=side,
    )


def _human_fill(
    *,
    input_suffix: str = "1",
    leg_key: VenueLegKey = LEG_A,
    side: ExecutionSide = ExecutionSide.BUY,
    quantity: int = 4,
    prior: int = 0,
    resulting: int = 4,
    units: int = 100,
    request_occurrence_id: RequestOccurrenceId = REQUEST,
    claim_occurrence_id: ClaimOccurrenceId = CLAIM,
    actor: ActorId = ACTOR,
    reason: str = "paper report proves an omitted execution",
    evidence_reference: EvidenceReference = EVIDENCE,
) -> HumanAttestedFillFact:
    return HumanAttestedFillFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId(f"human-source-{input_suffix}"),
        ),
        scope=_execution_scope(leg_key=leg_key, side=side),
        root_fill_id=RootFillId(f"human-root-{input_suffix}"),
        leg_key=leg_key,
        request_occurrence_id=request_occurrence_id,
        claim_occurrence_id=claim_occurrence_id,
        quantity=Quantity(quantity),
        prior_cumulative_quantity=Quantity(prior),
        resulting_cumulative_quantity=Quantity(resulting),
        price=_price(units),
        actor=actor,
        reason=reason,
        evidence_reference=evidence_reference,
    )


def _broker_fill(
    source: str,
    root: str,
    *,
    leg_key: VenueLegKey = LEG_A,
    side: ExecutionSide = ExecutionSide.BUY,
    quantity: int,
    units: int = 100,
) -> BrokerFillFact:
    return BrokerFillFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId(source),
        ),
        scope=_execution_scope(leg_key=leg_key, side=side),
        root_fill_id=RootFillId(root),
        quantity=Quantity(quantity),
        price=_price(units),
    )


def _apply_broker(
    execution: ExecutionSnapshot,
    fact: BrokerFillFact,
) -> ExecutionSnapshot:
    transition = apply_broker_execution_fact(
        execution.position,
        execution.integrity,
        execution.root_heads,
        execution.seen_facts,
        fact,
    )
    assert transition.disposition is TransitionDisposition.APPLIED
    return ExecutionSnapshot(
        position=transition.position,
        integrity=transition.integrity,
        root_heads=transition.root_heads,
        seen_facts=transition.seen_facts,
    )


def _seed_needs_review(
    *,
    side: ExecutionSide = ExecutionSide.BUY,
    capacity: int = 10,
    leg_keys: tuple[VenueLegKey, ...] = (LEG_A,),
    execution: ExecutionSnapshot | None = None,
) -> tuple[VenueRecoveryBook, ExecutionSnapshot]:
    book = VenueRecoveryBook.empty(VENUE_SCOPE)
    current_execution = execution or ExecutionSnapshot.flat(POSITION_SCOPE)
    inputs: list[object] = [
        RequestedEffect(
            input_id=VenueInputId("request-effect"),
            effect_id=EFFECT,
            request_occurrence_id=REQUEST,
            mandate_id=MANDATE,
            kind=EffectKind.SUBMIT,
            client_order_id=CLIENT,
            symbol_id=SYMBOL,
            side=side,
            quantity=Quantity(capacity),
            economic_scope=b"AAPL|BUY-or-SELL|fixed-order-capacity",
        ),
        RecordDispatchClaim(
            input_id=VenueInputId("claim-effect"),
            effect_id=EFFECT,
            claim_occurrence_id=CLAIM,
        ),
        RecordTransportOutcome(
            input_id=VenueInputId("transport-unknown"),
            effect_id=EFFECT,
            state=BrokerEffectState.OUTCOME_UNKNOWN,
        ),
    ]
    for index, leg_key in enumerate(leg_keys, start=1):
        inputs.extend(
            (
                DiscoverVenueLeg(
                    input_id=VenueInputId(f"discover-leg-{index}"),
                    effect_id=EFFECT,
                    leg_key=leg_key,
                    observation_id=VenueObservationId(
                        f"acceptance-observation-{index}"
                    ),
                ),
                ObserveVenueStatus(
                    input_id=VenueInputId(f"needs-review-leg-{index}"),
                    leg_key=leg_key,
                    status=VenueAttemptState.NEEDS_REVIEW,
                    observation_id=VenueObservationId(f"review-observation-{index}"),
                    cumulative_quantity=Quantity(0),
                ),
            )
        )
    inputs.append(
        RecordTransportOutcome(
            input_id=VenueInputId("transport-needs-review"),
            effect_id=EFFECT,
            state=BrokerEffectState.NEEDS_REVIEW,
        )
    )
    for item in inputs:
        transition = apply_venue_recovery_input(book, current_execution, item)
        assert transition.disposition is VenueRecoveryDisposition.APPLIED
        assert transition.quantity_delta == 0
        book = transition.book
        current_execution = transition.execution
    return book, current_execution


def _ingest(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    fact: HumanAttestedFillFact,
    *,
    input_id: str = "ingest-human-1",
    effect_id: EffectId = EFFECT,
):
    return apply_venue_recovery_input(
        book,
        execution,
        IngestHumanAttestedFill(
            input_id=VenueInputId(input_id),
            effect_id=effect_id,
            fact=fact,
        ),
    )


def _released_state(
    *,
    leg_keys: tuple[VenueLegKey, ...] = (LEG_A,),
    execution: ExecutionSnapshot | None = None,
) -> tuple[VenueRecoveryBook, ExecutionSnapshot, ReleaseVenueLeg]:
    book, current = _seed_needs_review(leg_keys=leg_keys, execution=execution)
    attested = _ingest(book, current, _human_fill())
    assert attested.disposition is VenueRecoveryDisposition.APPLIED
    release = ReleaseVenueLeg(
        input_id=VenueInputId("release-leg-a"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        claim_occurrence_id=CLAIM,
        venue_cumulative_quantity=Quantity(4),
        broker_terminal_state=VenueAttemptState.CANCELED,
        actor=ACTOR,
        reason="paper terminal report and exact fill parity",
        evidence_reference=EVIDENCE,
        closure_id=ClosureId("operator-release-a"),
        evidence_digest=b"\x11" * 32,
    )
    released = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        release,
    )
    assert released.disposition is VenueRecoveryDisposition.APPLIED
    return released.book, released.execution, release


def _root_key(root: str) -> RootFillKey:
    return RootFillKey(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        root_fill_id=RootFillId(root),
    )


def _acceptance_proof(
    book: VenueRecoveryBook,
    kind: AcceptanceProofKind,
    evidence: str,
) -> AcceptanceProof:
    effect = book.effect(EFFECT)
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
        evidence_digest=b"\xa7" * 32,
    )


def test_attested_fill_uses_the_canonical_root_fold_and_exact_replay_is_a_noop() -> (
    None
):
    book, execution = _seed_needs_review()
    fact = _human_fill()
    command = IngestHumanAttestedFill(
        input_id=VenueInputId("ingest-human-1"),
        effect_id=EFFECT,
        fact=fact,
    )

    applied = apply_venue_recovery_input(book, execution, command)

    assert applied.disposition is VenueRecoveryDisposition.APPLIED
    assert applied.quantity_delta == 4
    assert applied.execution.position.raw_quantity == 4
    assert applied.execution.position.cost_basis == ExactBasis(Fraction(400))
    head = applied.execution.root_heads.get(_root_key("human-root-1"))
    assert head is not None
    assert head.authority is ExecutionAuthority.HUMAN_ATTESTED
    coverages = applied.book.coverage_for_leg(LEG_A)
    assert len(coverages) == 1
    assert coverages[0].effect_id == EFFECT
    assert coverages[0].fact == fact
    assert coverages[0].broker_corroborated is False

    replay = apply_venue_recovery_input(applied.book, applied.execution, command)
    assert replay.disposition is VenueRecoveryDisposition.EXACT_REPLAY
    assert replay.quantity_delta == 0
    assert replay.book == applied.book
    assert replay.execution == applied.execution


def test_attested_fill_advances_the_exact_active_leg_cumulative_checkpoint() -> None:
    book, execution = _seed_needs_review()

    applied = _ingest(book, execution, _human_fill())

    assert applied.disposition is VenueRecoveryDisposition.APPLIED
    attempt = applied.book.active_attempt(LEG_A)
    assert attempt is not None
    assert attempt.status is VenueAttemptState.NEEDS_REVIEW
    assert attempt.cumulative_quantity == Quantity(4)


def test_identical_human_fact_under_a_new_command_is_a_recorded_zero_delta() -> None:
    book, execution = _seed_needs_review()
    fact = _human_fill()
    first = _ingest(book, execution, fact)
    duplicate_command = IngestHumanAttestedFill(
        input_id=VenueInputId("same-human-fact-new-command"),
        effect_id=EFFECT,
        fact=fact,
    )

    duplicate = apply_venue_recovery_input(
        first.book,
        first.execution,
        duplicate_command,
    )

    assert duplicate.disposition is VenueRecoveryDisposition.APPLIED
    assert duplicate.quantity_delta == 0
    assert duplicate.execution == first.execution
    assert duplicate.book.coverage_for_leg(LEG_A) == first.book.coverage_for_leg(LEG_A)
    replay = apply_venue_recovery_input(
        duplicate.book,
        duplicate.execution,
        duplicate_command,
    )
    assert replay.disposition is VenueRecoveryDisposition.EXACT_REPLAY
    assert replay.book == duplicate.book


def test_changed_human_payload_for_a_seen_fact_latches_conflict() -> None:
    book, execution = _seed_needs_review()
    first = _ingest(book, execution, _human_fill())
    changed = replace(
        _human_fill(), reason="changed payload under seen source identity"
    )

    conflict = _ingest(
        first.book,
        first.execution,
        changed,
        input_id="changed-seen-human-fact",
    )

    assert conflict.disposition is VenueRecoveryDisposition.CONFLICT
    assert conflict.quantity_delta == 0
    assert conflict.execution.position.raw_quantity == 4
    assert conflict.execution.integrity & PositionIntegrity.EXECUTION_FACT_CONFLICT
    assert conflict.book.effects == first.book.effects
    assert conflict.book.owners == first.book.owners
    assert conflict.book.active_attempts == first.book.active_attempts
    assert conflict.book.human_coverages == first.book.human_coverages
    assert conflict.book.input_records == first.book.input_records
    binding = conflict.book.execution_binding(POSITION_SCOPE)
    assert binding is not None
    assert conflict.book._execution_matches(conflict.execution, POSITION_SCOPE)


@pytest.mark.parametrize(
    "changed_field",
    [
        "source_event_id",
        "root_fill_id",
        "leg_key",
        "request_occurrence_id",
        "claim_occurrence_id",
        "quantity",
        "interval",
        "price",
        "actor",
        "reason",
        "evidence_reference",
    ],
)
def test_same_human_input_identity_with_any_changed_payload_conflicts(
    changed_field: str,
) -> None:
    book, execution = _seed_needs_review()
    fact = _human_fill()
    first = _ingest(book, execution, fact)
    assert first.disposition is VenueRecoveryDisposition.APPLIED

    if changed_field == "source_event_id":
        changed = replace(
            fact,
            key=replace(fact.key, source_event_id=SourceEventId("changed-source")),
        )
    elif changed_field == "root_fill_id":
        changed = replace(fact, root_fill_id=RootFillId("changed-root"))
    elif changed_field == "leg_key":
        changed = replace(fact, leg_key=LEG_B)
    elif changed_field == "request_occurrence_id":
        changed = replace(
            fact,
            request_occurrence_id=RequestOccurrenceId("changed-request"),
        )
    elif changed_field == "claim_occurrence_id":
        changed = replace(
            fact,
            claim_occurrence_id=ClaimOccurrenceId("changed-claim"),
        )
    elif changed_field == "quantity":
        changed = replace(fact, quantity=Quantity(3))
    elif changed_field == "interval":
        changed = replace(fact, resulting_cumulative_quantity=Quantity(5))
    elif changed_field == "price":
        changed = replace(fact, price=_price(101))
    elif changed_field == "actor":
        changed = replace(fact, actor=ActorId("operator-b"))
    elif changed_field == "reason":
        changed = replace(fact, reason="changed reason")
    else:
        changed = replace(
            fact,
            evidence_reference=EvidenceReference("changed-evidence"),
        )

    conflict = _ingest(first.book, first.execution, changed)
    assert conflict.disposition is VenueRecoveryDisposition.CONFLICT
    assert conflict.quantity_delta == 0
    assert conflict.book == first.book
    assert conflict.execution == first.execution


@pytest.mark.parametrize(
    "fact",
    [
        _human_fill(leg_key=LEG_B),
        _human_fill(request_occurrence_id=RequestOccurrenceId("other-request")),
        _human_fill(claim_occurrence_id=ClaimOccurrenceId("other-claim")),
        replace(
            _human_fill(),
            scope=replace(_human_fill().scope, symbol_id=SymbolId("MSFT")),
        ),
        replace(
            _human_fill(),
            scope=replace(_human_fill().scope, order_id=OrderId("other-order")),
        ),
    ],
)
def test_attestation_refuses_any_unbound_leg_occurrence_claim_or_scope(
    fact: HumanAttestedFillFact,
) -> None:
    book, execution = _seed_needs_review()

    refused = _ingest(book, execution, fact, input_id="invalid-binding")

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.quantity_delta == 0
    assert refused.book == book
    assert refused.execution == execution


def test_attestation_refuses_wrong_effect_or_account_identity() -> None:
    book, execution = _seed_needs_review()
    exact = _human_fill()
    other_account = AccountId("account-002")
    wrong_account = replace(
        exact,
        key=replace(exact.key, account=other_account),
        scope=replace(exact.scope, account=other_account),
    )

    wrong_effect = _ingest(
        book,
        execution,
        exact,
        input_id="invalid-effect",
        effect_id=EffectId("other-effect"),
    )
    wrong_scope = _ingest(
        book,
        execution,
        wrong_account,
        input_id="invalid-account",
    )

    for refused in (wrong_effect, wrong_scope):
        assert refused.disposition is VenueRecoveryDisposition.REFUSED
        assert refused.quantity_delta == 0
        assert refused.book == book
        assert refused.execution == execution


def test_checkpoint_construction_cannot_drop_the_immutable_claim_edge() -> None:
    book, execution = _seed_needs_review()

    with pytest.raises(ValueError, match="claim"):
        _audit_hydrate_book(book, execution, claims=())


def test_checkpoint_cannot_be_rebuilt_outside_verified_provenance_path() -> None:
    book, _ = _seed_needs_review()

    with pytest.raises(TypeError, match="opaque|verified|reducer"):
        replace(book, input_records=())


@pytest.mark.parametrize(
    "source_type",
    [RequestedEffect, RecordDispatchClaim, DiscoverVenueLeg],
)
def test_checkpoint_edges_require_their_exact_source_input(
    source_type: type[object],
) -> None:
    book, execution = _seed_needs_review()
    retained = tuple(
        record
        for record in book.input_records
        if not isinstance(record.item, source_type)
    )

    with pytest.raises(ValueError, match="input|provenance"):
        _audit_hydrate_book(book, execution, input_records=retained)


def test_checkpoint_human_coverage_requires_its_source_input() -> None:
    book, execution = _seed_needs_review()
    attested = _ingest(book, execution, _human_fill())
    retained = tuple(
        record
        for record in attested.book.input_records
        if not isinstance(record.item, IngestHumanAttestedFill)
    )

    with pytest.raises(ValueError, match="coverage|input|provenance"):
        _audit_hydrate_book(
            attested.book,
            attested.execution,
            input_records=retained,
        )


def test_checkpoint_operator_closure_requires_its_release_input() -> None:
    book, execution, _ = _released_state()
    retained = tuple(
        record
        for record in book.input_records
        if not isinstance(record.item, ReleaseVenueLeg)
    )

    with pytest.raises(ValueError, match="closure|input|provenance"):
        _audit_hydrate_book(book, execution, input_records=retained)


def test_checkpoint_effect_state_requires_complete_lifecycle_input_history() -> None:
    book, execution = _seed_needs_review()
    retained = tuple(
        record
        for record in book.input_records
        if not isinstance(record.item, RecordTransportOutcome)
    )

    with pytest.raises(ValueError, match="lifecycle|state|provenance"):
        _audit_hydrate_book(book, execution, input_records=retained)


def test_checkpoint_attempt_state_requires_its_observation_input() -> None:
    book, execution = _seed_needs_review()
    retained = tuple(
        record
        for record in book.input_records
        if not isinstance(record.item, ObserveVenueStatus)
    )

    with pytest.raises(ValueError, match="attempt|observation|provenance"):
        _audit_hydrate_book(book, execution, input_records=retained)


def test_checkpoint_pending_operation_requires_its_source_input() -> None:
    book, execution = _seed_needs_review()
    pending = apply_venue_recovery_input(
        book,
        execution,
        RecordPendingVenueOperation(
            input_id=VenueInputId("record-pending-cancel"),
            leg_key=LEG_A,
            operation=PendingVenueOperation.CANCEL,
        ),
    )
    retained = tuple(
        record
        for record in pending.book.input_records
        if not isinstance(record.item, RecordPendingVenueOperation)
    )

    with pytest.raises(ValueError, match="pending|attempt|provenance"):
        _audit_hydrate_book(
            pending.book,
            pending.execution,
            input_records=retained,
        )


def test_attestation_requires_typed_nonblank_actor_reason_and_evidence() -> None:
    with pytest.raises(ValueError):
        ActorId(" ")
    with pytest.raises(ValueError):
        EvidenceReference("")
    with pytest.raises(ValueError):
        _human_fill(reason="\t")


@pytest.mark.parametrize(
    ("quantity", "prior", "resulting"),
    [
        (6, 0, 6),  # exceeds the immutable order capacity of five
        (2, 0, 3),  # incremental quantity does not equal the interval width
        (2, 1, 3),  # first coverage does not begin at zero
    ],
)
def test_attestation_refuses_capacity_or_cumulative_interval_violations(
    quantity: int,
    prior: int,
    resulting: int,
) -> None:
    book, execution = _seed_needs_review(capacity=5)
    fact = _human_fill(quantity=quantity, prior=prior, resulting=resulting)

    refused = _ingest(book, execution, fact, input_id="invalid-arithmetic")

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.quantity_delta == 0
    assert refused.book == book
    assert refused.execution == execution


@pytest.mark.parametrize(
    ("quantity", "prior", "resulting"),
    [
        (1, 4, 5),  # gap after committed (0, 3]
        (2, 2, 4),  # overlap with committed (0, 3]
        (3, 3, 6),  # exact continuation exceeds capacity five
    ],
)
def test_later_attestation_must_exactly_continue_committed_leg_coverage(
    quantity: int,
    prior: int,
    resulting: int,
) -> None:
    book, execution = _seed_needs_review(capacity=5)
    first = _ingest(
        book,
        execution,
        _human_fill(quantity=3, prior=0, resulting=3),
    )
    assert first.disposition is VenueRecoveryDisposition.APPLIED
    later = _human_fill(
        input_suffix="2",
        quantity=quantity,
        prior=prior,
        resulting=resulting,
    )

    refused = _ingest(
        first.book,
        first.execution,
        later,
        input_id="invalid-continuation",
    )

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.quantity_delta == 0
    assert refused.book == first.book
    assert refused.execution == first.execution


def test_stale_execution_snapshot_cannot_advance_book_coverage() -> None:
    book, execution = _seed_needs_review()
    first = _ingest(
        book,
        execution,
        _human_fill(quantity=4, prior=0, resulting=4),
    )

    refused = _ingest(
        first.book,
        execution,
        _human_fill(
            input_suffix="stale-second",
            quantity=4,
            prior=4,
            resulting=8,
        ),
        input_id="ingest-against-stale-execution",
    )

    assert refused.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert refused.quantity_delta == 0
    assert refused.book == first.book
    assert refused.execution == execution


def test_ahead_execution_snapshot_cannot_be_paired_with_an_older_book() -> None:
    book, execution = _seed_needs_review()
    ahead = _ingest(
        book,
        execution,
        _human_fill(input_suffix="ahead-snapshot", quantity=4, prior=0, resulting=4),
        input_id="create-ahead-execution",
    )

    refused = _ingest(
        book,
        ahead.execution,
        _human_fill(input_suffix="alternate-root", quantity=4, prior=0, resulting=4),
        input_id="ingest-against-older-book",
    )

    assert refused.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert refused.quantity_delta == 0
    assert refused.book == book
    assert refused.execution == ahead.execution


def test_human_attested_sell_cannot_cross_long_quantity_below_zero() -> None:
    book, execution = _seed_needs_review(side=ExecutionSide.SELL, capacity=5)
    sell = _human_fill(
        side=ExecutionSide.SELL,
        quantity=1,
        prior=0,
        resulting=1,
    )

    refused = _ingest(book, execution, sell)

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.quantity_delta == 0
    assert refused.execution.position.raw_quantity == 0
    assert refused.execution.integrity is PositionIntegrity.CONSISTENT


def test_known_matching_broker_economics_prevent_a_second_human_delta() -> None:
    book, execution = _seed_needs_review()
    broker_first = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("known-broker-evidence"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=_broker_fill(
                "known-broker-source",
                "known-broker-root",
                quantity=4,
                units=100,
            ),
            evidence_digest=b"\x89" * 32,
        ),
    )
    assert broker_first.disposition is VenueRecoveryDisposition.APPLIED
    assert broker_first.quantity_delta == 4

    refused = _ingest(
        broker_first.book,
        broker_first.execution,
        _human_fill(),
    )

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.quantity_delta == 0
    assert refused.book == broker_first.book
    assert refused.execution == broker_first.execution


def test_release_is_non_economic_leg_local_and_exactly_replayable() -> None:
    book, execution, command = _released_state(leg_keys=(LEG_A, LEG_B))

    assert book.active_attempt(LEG_A) is None
    closure = book.closure_head(LEG_A)
    assert closure is not None
    assert closure.kind is VenueClosureKind.OPERATOR_RECONCILED
    assert closure.status is VenueAttemptState.OPERATOR_RECONCILED
    sibling = book.active_attempt(LEG_B)
    assert sibling is not None
    assert sibling.status is VenueAttemptState.NEEDS_REVIEW
    assert book.owner(LEG_A) is not None
    assert book.owner(LEG_B) is not None
    assert book.effect(EFFECT).state is BrokerEffectState.NEEDS_REVIEW
    assert book.effect(EFFECT).acceptance_set_state is AcceptanceSetState.OPEN
    assert execution.position.raw_quantity == 4
    assert execution.position.cost_basis == ExactBasis(Fraction(400))

    replay = apply_venue_recovery_input(book, execution, command)
    assert replay.disposition is VenueRecoveryDisposition.EXACT_REPLAY
    assert replay.quantity_delta == 0
    assert replay.book == book
    assert replay.execution == execution


def test_release_refuses_a_mixed_execution_snapshot_without_committed_coverage() -> (
    None
):
    book, execution = _seed_needs_review()
    attested = _ingest(book, execution, _human_fill())
    mixed_execution = ExecutionSnapshot.flat(POSITION_SCOPE)
    release = ReleaseVenueLeg(
        input_id=VenueInputId("release-against-mixed-snapshot"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        claim_occurrence_id=CLAIM,
        venue_cumulative_quantity=Quantity(4),
        broker_terminal_state=VenueAttemptState.CANCELED,
        actor=ACTOR,
        reason="mixed execution checkpoint must fail closed",
        evidence_reference=EVIDENCE,
        closure_id=ClosureId("mixed-snapshot-release"),
        evidence_digest=b"\x83" * 32,
    )

    refused = apply_venue_recovery_input(
        attested.book,
        mixed_execution,
        release,
    )

    assert refused.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert refused.quantity_delta == 0
    assert refused.book == attested.book
    assert refused.execution == mixed_execution


def test_late_broker_terminal_supersedes_operator_release_as_broker_evidence() -> None:
    book, execution, _ = _released_state()

    observed = apply_venue_recovery_input(
        book,
        execution,
        ObserveVenueStatus(
            input_id=VenueInputId("late-broker-terminal-after-release"),
            leg_key=LEG_A,
            status=VenueAttemptState.FILLED,
            observation_id=VenueObservationId("late-broker-terminal-observation"),
            cumulative_quantity=Quantity(5),
            closure_id=ClosureId("late-broker-terminal-closure"),
            evidence_reference=EvidenceReference("late-broker-terminal-evidence"),
        ),
    )

    assert observed.disposition is VenueRecoveryDisposition.APPLIED
    assert observed.quantity_delta == 0
    head = observed.book.closure_head(LEG_A)
    assert head is not None
    assert head.kind is VenueClosureKind.BROKER_TERMINAL
    assert head.status is VenueAttemptState.FILLED
    assert head.broker_terminal_state is VenueAttemptState.FILLED
    assert head.predecessor_closure_id == ClosureId("operator-release-a")
    assert observed.execution == execution


@pytest.mark.parametrize(
    "change",
    ["claim", "cumulative", "terminal", "actor", "reason", "evidence", "digest"],
)
def test_changed_release_retry_conflicts_without_global_or_economic_mutation(
    change: str,
) -> None:
    book, execution, command = _released_state(leg_keys=(LEG_A, LEG_B))
    if change == "claim":
        changed = replace(
            command,
            claim_occurrence_id=ClaimOccurrenceId("changed-claim"),
        )
    elif change == "cumulative":
        changed = replace(command, venue_cumulative_quantity=Quantity(3))
    elif change == "terminal":
        changed = replace(command, broker_terminal_state=VenueAttemptState.REJECTED)
    elif change == "actor":
        changed = replace(command, actor=ActorId("operator-b"))
    elif change == "reason":
        changed = replace(command, reason="changed release reason")
    elif change == "evidence":
        changed = replace(
            command,
            evidence_reference=EvidenceReference("changed-release-evidence"),
        )
    else:
        changed = replace(command, evidence_digest=b"\x22" * 32)

    conflict = apply_venue_recovery_input(book, execution, changed)
    assert conflict.disposition is VenueRecoveryDisposition.CONFLICT
    assert conflict.quantity_delta == 0
    assert conflict.book == book
    assert conflict.execution == execution


@pytest.mark.parametrize(
    "change",
    ["wrong_claim", "wrong_leg", "wrong_cumulative", "nonterminal"],
)
def test_release_requires_exact_owner_terminal_evidence_and_fill_parity(
    change: str,
) -> None:
    book, execution = _seed_needs_review(leg_keys=(LEG_A, LEG_B))
    attested = _ingest(book, execution, _human_fill())
    assert attested.disposition is VenueRecoveryDisposition.APPLIED
    command = ReleaseVenueLeg(
        input_id=VenueInputId(f"release-refused-{change}"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        claim_occurrence_id=CLAIM,
        venue_cumulative_quantity=Quantity(4),
        broker_terminal_state=VenueAttemptState.CANCELED,
        actor=ACTOR,
        reason="terminal report",
        evidence_reference=EVIDENCE,
        closure_id=ClosureId(f"release-refused-{change}"),
        evidence_digest=b"\x33" * 32,
    )
    if change == "wrong_claim":
        command = replace(
            command,
            claim_occurrence_id=ClaimOccurrenceId("wrong-claim"),
        )
    elif change == "wrong_leg":
        command = replace(command, leg_key=LEG_B)
    elif change == "wrong_cumulative":
        command = replace(command, venue_cumulative_quantity=Quantity(3))
    else:
        command = replace(
            command,
            broker_terminal_state=VenueAttemptState.WORKING,
        )

    refused = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        command,
    )
    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.quantity_delta == 0
    assert refused.book == attested.book
    assert refused.execution == attested.execution


def test_release_preserves_a_preexisting_overfill_quarantine_latch() -> None:
    book, execution = _seed_needs_review(capacity=4)
    overfill = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("pre-release-overfill"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(5),
            fact=_broker_fill(
                "pre-release-overfill-source",
                "pre-release-overfill-root",
                quantity=5,
            ),
            evidence_digest=b"\x8a" * 32,
        ),
    )
    assert overfill.disposition is VenueRecoveryDisposition.APPLIED
    assert overfill.execution.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    released = apply_venue_recovery_input(
        overfill.book,
        overfill.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("release-after-overfill"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            claim_occurrence_id=CLAIM,
            venue_cumulative_quantity=Quantity(5),
            broker_terminal_state=VenueAttemptState.CANCELED,
            actor=ACTOR,
            reason="terminal report closes an overfilled broker leg",
            evidence_reference=EVIDENCE,
            closure_id=ClosureId("release-after-overfill-closure"),
            evidence_digest=b"\x8b" * 32,
        ),
    )

    assert released.disposition is VenueRecoveryDisposition.APPLIED
    assert released.execution.position.raw_quantity == 5
    assert released.execution.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert (
        released.execution.position.integrity_floor
        & PositionIntegrity.OVERFILL_QUARANTINE
    )
    assert released.book.effect(EFFECT).acceptance_set_state is AcceptanceSetState.OPEN


def test_human_fill_cannot_be_appended_after_the_leg_was_released() -> None:
    book, execution, _ = _released_state(leg_keys=(LEG_A, LEG_B))

    refused = _ingest(
        book,
        execution,
        _human_fill(input_suffix="after-release", quantity=1, prior=4, resulting=5),
        input_id="human-after-release",
    )

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.quantity_delta == 0
    assert refused.book == book
    assert refused.execution == execution


def test_release_requires_exact_active_attempt_and_coverage_cumulative_parity() -> None:
    book, execution = _seed_needs_review()
    attested = _ingest(book, execution, _human_fill())
    assert attested.disposition is VenueRecoveryDisposition.APPLIED
    observed = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        ObserveVenueStatus(
            input_id=VenueInputId("later-cumulative-observation"),
            leg_key=LEG_A,
            status=VenueAttemptState.NEEDS_REVIEW,
            observation_id=VenueObservationId("later-cumulative-five"),
            cumulative_quantity=Quantity(5),
        ),
    )
    assert observed.disposition is VenueRecoveryDisposition.APPLIED
    release = ReleaseVenueLeg(
        input_id=VenueInputId("release-stale-cumulative"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        claim_occurrence_id=CLAIM,
        venue_cumulative_quantity=Quantity(4),
        broker_terminal_state=VenueAttemptState.CANCELED,
        actor=ACTOR,
        reason="stale cumulative must not release",
        evidence_reference=EVIDENCE,
        closure_id=ClosureId("release-stale-cumulative"),
        evidence_digest=b"\x77" * 32,
    )

    refused = apply_venue_recovery_input(
        observed.book,
        observed.execution,
        release,
    )

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.book == observed.book
    assert refused.execution == observed.execution


def test_partial_cumulative_cannot_be_described_as_filled_for_release() -> None:
    book, execution = _seed_needs_review(capacity=10)
    attested = _ingest(book, execution, _human_fill())
    release = ReleaseVenueLeg(
        input_id=VenueInputId("release-partial-as-filled"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        claim_occurrence_id=CLAIM,
        venue_cumulative_quantity=Quantity(4),
        broker_terminal_state=VenueAttemptState.FILLED,
        actor=ACTOR,
        reason="incomplete filled report",
        evidence_reference=EVIDENCE,
        closure_id=ClosureId("release-partial-as-filled"),
        evidence_digest=b"\x78" * 32,
    )

    refused = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        release,
    )

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.book == attested.book
    assert refused.execution == attested.execution


@pytest.mark.parametrize(
    "terminal",
    [
        VenueAttemptState.FILLED,
        VenueAttemptState.CANCELED,
        VenueAttemptState.REJECTED,
        VenueAttemptState.EXPIRED,
        VenueAttemptState.REPLACED,
    ],
)
def test_release_accepts_every_exact_broker_terminal_state(
    terminal: VenueAttemptState,
) -> None:
    book, execution = _seed_needs_review(capacity=4)
    attested = _ingest(book, execution, _human_fill())
    release = ReleaseVenueLeg(
        input_id=VenueInputId(f"release-terminal-{terminal.value.lower()}"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        claim_occurrence_id=CLAIM,
        venue_cumulative_quantity=Quantity(4),
        broker_terminal_state=terminal,
        actor=ACTOR,
        reason="exact terminal report",
        evidence_reference=EVIDENCE,
        closure_id=ClosureId(f"release-terminal-{terminal.value.lower()}"),
        evidence_digest=b"\x79" * 32,
    )

    released = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        release,
    )

    assert released.disposition is VenueRecoveryDisposition.APPLIED
    closure = released.book.closure_head(LEG_A)
    assert closure is not None
    assert closure.broker_terminal_state is terminal


def test_effect_finalizes_only_after_acceptance_and_all_owned_legs_close() -> None:
    book, execution = _seed_needs_review(capacity=4)
    attested = _ingest(book, execution, _human_fill())
    release = ReleaseVenueLeg(
        input_id=VenueInputId("release-before-parent-close"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        claim_occurrence_id=CLAIM,
        venue_cumulative_quantity=Quantity(4),
        broker_terminal_state=VenueAttemptState.CANCELED,
        actor=ACTOR,
        reason="exact terminal report",
        evidence_reference=EVIDENCE,
        closure_id=ClosureId("release-before-parent-close"),
        evidence_digest=b"\x7a" * 32,
    )
    released = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        release,
    )
    assert released.disposition is VenueRecoveryDisposition.APPLIED
    assert released.book.effect(EFFECT).state is BrokerEffectState.NEEDS_REVIEW

    closed = apply_venue_recovery_input(
        released.book,
        released.execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("close-parent-after-release"),
            effect_id=EFFECT,
            proof=_acceptance_proof(
                released.book,
                AcceptanceProofKind.COVERED_RECONCILIATION,
                "covered-parent-proof",
            ),
        ),
    )

    assert closed.disposition is VenueRecoveryDisposition.APPLIED
    assert closed.book.effect(EFFECT).acceptance_set_state is AcceptanceSetState.CLOSED
    assert closed.book.effect(EFFECT).state is BrokerEffectState.OPERATOR_RECONCILED


def test_parent_close_cannot_finalize_against_a_mixed_execution_snapshot() -> None:
    book, _, _ = _released_state()
    mixed_execution = ExecutionSnapshot.flat(POSITION_SCOPE)

    closed = apply_venue_recovery_input(
        book,
        mixed_execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("close-parent-against-mixed-snapshot"),
            effect_id=EFFECT,
            proof=_acceptance_proof(
                book,
                AcceptanceProofKind.COVERED_RECONCILIATION,
                "mixed-snapshot-parent-proof",
            ),
        ),
    )

    assert closed.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert closed.book.effect(EFFECT).acceptance_set_state is AcceptanceSetState.OPEN
    assert closed.book.effect(EFFECT).state is BrokerEffectState.NEEDS_REVIEW
    assert closed.book == book
    assert closed.execution == mixed_execution


def test_late_acceptance_invalidates_and_demotes_a_finalized_parent() -> None:
    book, execution, _ = _released_state()
    closed = apply_venue_recovery_input(
        book,
        execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("close-before-late-acceptance"),
            effect_id=EFFECT,
            proof=_acceptance_proof(
                book,
                AcceptanceProofKind.COVERED_RECONCILIATION,
                "proof-before-late-acceptance",
            ),
        ),
    )
    effect_before = closed.book.effect(EFFECT)
    assert effect_before is not None
    assert effect_before.state is BrokerEffectState.OPERATOR_RECONCILED
    assert effect_before.acceptance_set_state is AcceptanceSetState.CLOSED

    late = apply_venue_recovery_input(
        closed.book,
        closed.execution,
        DiscoverVenueLeg(
            input_id=VenueInputId("discover-after-finalization"),
            effect_id=EFFECT,
            leg_key=LEG_B,
            observation_id=VenueObservationId("late-acceptance-after-finalization"),
        ),
    )

    assert late.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    effect_after = late.book.effect(EFFECT)
    assert effect_after is not None
    assert effect_after.state is BrokerEffectState.NEEDS_REVIEW
    assert effect_after.acceptance_set_state is AcceptanceSetState.INVALIDATED
    assert effect_after.acceptance_proof == effect_before.acceptance_proof
    assert effect_after.contradiction_evidence == (
        AcceptanceContradiction(
            leg_key=LEG_B,
            observation_id=VenueObservationId("late-acceptance-after-finalization"),
        ),
    )
    assert late.book.owner(LEG_B) is not None
    assert late.book.active_attempt(LEG_B) is not None


def test_terminal_status_without_canonical_fill_parity_cannot_finalize_effect() -> None:
    book, execution = _seed_needs_review(capacity=4)
    terminal = apply_venue_recovery_input(
        book,
        execution,
        ObserveVenueStatus(
            input_id=VenueInputId("status-only-filled"),
            leg_key=LEG_A,
            status=VenueAttemptState.FILLED,
            observation_id=VenueObservationId("status-only-filled-observation"),
            cumulative_quantity=Quantity(4),
            closure_id=ClosureId("status-only-filled-closure"),
            evidence_reference=EvidenceReference("status-only-filled-evidence"),
        ),
    )
    assert terminal.disposition is VenueRecoveryDisposition.APPLIED
    assert terminal.execution.position.raw_quantity == 0

    closed = apply_venue_recovery_input(
        terminal.book,
        terminal.execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("close-status-only-filled"),
            effect_id=EFFECT,
            proof=_acceptance_proof(
                terminal.book,
                AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
                "status-only-complete-response",
            ),
        ),
    )

    assert closed.disposition is VenueRecoveryDisposition.APPLIED
    assert closed.book.effect(EFFECT).acceptance_set_state is AcceptanceSetState.CLOSED
    assert closed.book.effect(EFFECT).state is BrokerEffectState.NEEDS_REVIEW
    assert closed.execution.position.raw_quantity == 0


def test_late_exact_fill_finalizes_a_closed_status_only_effect() -> None:
    book, execution = _seed_needs_review(capacity=4)
    terminal = apply_venue_recovery_input(
        book,
        execution,
        ObserveVenueStatus(
            input_id=VenueInputId("status-before-late-exact-fill"),
            leg_key=LEG_A,
            status=VenueAttemptState.FILLED,
            observation_id=VenueObservationId("status-before-late-fill-observation"),
            cumulative_quantity=Quantity(4),
            closure_id=ClosureId("status-before-late-fill-closure"),
            evidence_reference=EvidenceReference("status-before-late-fill-evidence"),
        ),
    )
    closed = apply_venue_recovery_input(
        terminal.book,
        terminal.execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("close-before-late-exact-fill"),
            effect_id=EFFECT,
            proof=_acceptance_proof(
                terminal.book,
                AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
                "proof-before-late-exact-fill",
            ),
        ),
    )
    assert closed.book.effect(EFFECT).state is BrokerEffectState.NEEDS_REVIEW

    filled = apply_venue_recovery_input(
        closed.book,
        closed.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("late-exact-fill-after-parent-close"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=_broker_fill(
                "late-exact-fill-source", "late-exact-fill-root", quantity=4
            ),
            evidence_digest=b"\xa0" * 32,
            closure_id=ClosureId("late-exact-fill-successor"),
            evidence_reference=EvidenceReference("late-exact-fill-evidence"),
        ),
    )

    assert filled.disposition is VenueRecoveryDisposition.APPLIED
    assert filled.quantity_delta == 4
    assert filled.book._leg_summary(EFFECT).finalization_ready_count == 1
    assert filled.book.effect(EFFECT).state is BrokerEffectState.OPERATOR_RECONCILED
    assert _audit_hydrate_book(filled.book, filled.execution) == filled.book


def test_invalidated_acceptance_set_permanently_refuses_operator_release() -> None:
    execution = ExecutionSnapshot.flat(POSITION_SCOPE)
    book = VenueRecoveryBook.empty(VENUE_SCOPE)
    setup = (
        RequestedEffect(
            input_id=VenueInputId("invalidated-request"),
            effect_id=EFFECT,
            request_occurrence_id=REQUEST,
            mandate_id=MANDATE,
            kind=EffectKind.SUBMIT,
            client_order_id=CLIENT,
            symbol_id=SYMBOL,
            side=ExecutionSide.BUY,
            quantity=Quantity(4),
            economic_scope=b"invalidated-release-scope",
        ),
        RecordDispatchClaim(
            input_id=VenueInputId("invalidated-claim"),
            effect_id=EFFECT,
            claim_occurrence_id=CLAIM,
        ),
        RecordTransportOutcome(
            input_id=VenueInputId("invalidated-unknown"),
            effect_id=EFFECT,
            state=BrokerEffectState.OUTCOME_UNKNOWN,
        ),
    )
    for item in setup:
        transition = apply_venue_recovery_input(book, execution, item)
        assert transition.disposition is VenueRecoveryDisposition.APPLIED
        book = transition.book
    closed = apply_venue_recovery_input(
        book,
        execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("invalidated-close"),
            effect_id=EFFECT,
            proof=_acceptance_proof(
                book,
                AcceptanceProofKind.COVERED_RECONCILIATION,
                "invalidated-close-proof",
            ),
        ),
    )
    assert closed.disposition is VenueRecoveryDisposition.APPLIED
    book = closed.book

    late = apply_venue_recovery_input(
        book,
        execution,
        DiscoverVenueLeg(
            input_id=VenueInputId("invalidated-late-leg"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            observation_id=VenueObservationId("invalidated-late-observation"),
        ),
    )
    assert late.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    needs_review_leg = apply_venue_recovery_input(
        late.book,
        execution,
        ObserveVenueStatus(
            input_id=VenueInputId("invalidated-leg-needs-review"),
            leg_key=LEG_A,
            status=VenueAttemptState.NEEDS_REVIEW,
            observation_id=VenueObservationId("invalidated-review-observation"),
            cumulative_quantity=Quantity(0),
        ),
    )
    needs_review_effect = apply_venue_recovery_input(
        needs_review_leg.book,
        execution,
        RecordTransportOutcome(
            input_id=VenueInputId("invalidated-effect-needs-review"),
            effect_id=EFFECT,
            state=BrokerEffectState.NEEDS_REVIEW,
        ),
    )
    attested = _ingest(
        needs_review_effect.book,
        execution,
        _human_fill(quantity=4, prior=0, resulting=4),
        input_id="invalidated-attestation",
    )
    assert attested.disposition is VenueRecoveryDisposition.APPLIED
    release = ReleaseVenueLeg(
        input_id=VenueInputId("invalidated-release"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        claim_occurrence_id=CLAIM,
        venue_cumulative_quantity=Quantity(4),
        broker_terminal_state=VenueAttemptState.CANCELED,
        actor=ACTOR,
        reason="must remain blocked after proof invalidation",
        evidence_reference=EVIDENCE,
        closure_id=ClosureId("invalidated-release"),
        evidence_digest=b"\x7b" * 32,
    )

    refused = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        release,
    )

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.book == attested.book
    assert refused.execution == attested.execution


def test_matching_later_broker_interval_corroborates_with_zero_second_delta() -> None:
    book, execution = _seed_needs_review()
    attested = _ingest(book, execution, _human_fill())
    assert attested.disposition is VenueRecoveryDisposition.APPLIED
    broker_fact = _broker_fill(
        "broker-match",
        "broker-match-root",
        quantity=4,
        units=100,
    )
    command = RecordBrokerFillEvidence(
        input_id=VenueInputId("broker-evidence-match"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_cumulative_quantity=Quantity(0),
        resulting_cumulative_quantity=Quantity(4),
        fact=broker_fact,
        evidence_digest=b"\x44" * 32,
    )

    matched = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        command,
    )

    assert matched.disposition is VenueRecoveryDisposition.APPLIED
    assert matched.quantity_delta == 0
    assert matched.execution.position == attested.execution.position
    assert matched.execution.integrity == attested.execution.integrity
    assert matched.execution.root_heads == attested.execution.root_heads
    reserved = matched.execution.seen_facts.get(broker_fact.key)
    assert reserved is not None
    assert reserved.fact == broker_fact
    coverage = matched.book.coverage_for_leg(LEG_A)
    assert len(coverage) == 1
    assert coverage[0].broker_corroborated is True
    assert matched.book.reconciliations == ()

    public_retry = apply_broker_execution_fact(
        matched.execution.position,
        matched.execution.integrity,
        matched.execution.root_heads,
        matched.execution.seen_facts,
        broker_fact,
    )
    assert public_retry.disposition is TransitionDisposition.EXACT_REPLAY
    assert public_retry.quantity_delta == 0
    assert public_retry.position.raw_quantity == 4


def test_same_broker_economics_under_a_fresh_command_is_zero_delta_then_exact_replay() -> (
    None
):
    book, execution = _seed_needs_review(capacity=4)
    broker_fact = _broker_fill(
        "broker-semantic-replay-source",
        "broker-semantic-replay-root",
        quantity=2,
    )
    first_command = RecordBrokerFillEvidence(
        input_id=VenueInputId("broker-semantic-replay-first-command"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_cumulative_quantity=Quantity(0),
        resulting_cumulative_quantity=Quantity(2),
        fact=broker_fact,
        evidence_digest=b"\x8a" * 32,
    )
    first = apply_venue_recovery_input(book, execution, first_command)
    assert first.disposition is VenueRecoveryDisposition.APPLIED
    assert first.quantity_delta == 2
    assert first.execution.position.raw_quantity == 2

    fresh_command = replace(
        first_command,
        input_id=VenueInputId("broker-semantic-replay-fresh-command"),
    )
    semantic_replay = apply_venue_recovery_input(
        first.book,
        first.execution,
        fresh_command,
    )

    assert semantic_replay.disposition is VenueRecoveryDisposition.APPLIED
    assert semantic_replay.quantity_delta == 0
    assert semantic_replay.execution == first.execution
    assert semantic_replay.book.broker_coverage_for_leg(
        LEG_A
    ) == first.book.broker_coverage_for_leg(LEG_A)
    assert semantic_replay.book.reconciliations == ()
    assert len(semantic_replay.book.input_records) == len(first.book.input_records) + 1

    exact_replay = apply_venue_recovery_input(
        semantic_replay.book,
        semantic_replay.execution,
        fresh_command,
    )

    assert exact_replay.disposition is VenueRecoveryDisposition.EXACT_REPLAY
    assert exact_replay.quantity_delta == 0
    assert exact_replay.book == semantic_replay.book
    assert exact_replay.execution == semantic_replay.execution


@pytest.mark.parametrize(
    ("prior", "resulting", "evidence_digest"),
    [
        pytest.param(1, 3, b"\x8a" * 32, id="changed-interval"),
        pytest.param(0, 2, b"\x8b" * 32, id="changed-evidence"),
    ],
)
def test_changed_interval_or_evidence_for_a_seen_broker_fact_reconciles_without_delta(
    prior: int,
    resulting: int,
    evidence_digest: bytes,
) -> None:
    book, execution = _seed_needs_review(capacity=4)
    broker_fact = _broker_fill(
        "broker-semantic-conflict-source",
        "broker-semantic-conflict-root",
        quantity=2,
    )
    first = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("broker-semantic-conflict-first-command"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(2),
            fact=broker_fact,
            evidence_digest=b"\x8a" * 32,
        ),
    )
    assert first.disposition is VenueRecoveryDisposition.APPLIED
    assert first.quantity_delta == 2

    changed = apply_venue_recovery_input(
        first.book,
        first.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId(
                f"broker-semantic-conflict-{prior}-{resulting}-{evidence_digest[0]}"
            ),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(prior),
            resulting_cumulative_quantity=Quantity(resulting),
            fact=broker_fact,
            evidence_digest=evidence_digest,
        ),
    )

    assert changed.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert changed.quantity_delta == 0
    assert (
        changed.execution.position.raw_quantity,
        changed.execution.position.basis_authority,
        changed.execution.position.cost_basis,
        changed.execution.position.root_fill_sequence,
        changed.execution.position.effective_head_ids,
        changed.execution.position.basis_price_metadata,
        changed.execution.position.tail_fold_input,
    ) == (
        first.execution.position.raw_quantity,
        first.execution.position.basis_authority,
        first.execution.position.cost_basis,
        first.execution.position.root_fill_sequence,
        first.execution.position.effective_head_ids,
        first.execution.position.basis_price_metadata,
        first.execution.position.tail_fold_input,
    )
    assert changed.execution.root_heads == first.execution.root_heads
    assert changed.book.broker_coverage_for_leg(
        LEG_A
    ) == first.book.broker_coverage_for_leg(LEG_A)
    assert len(changed.book.reconciliations) == len(first.book.reconciliations) + 1


def test_status_high_water_does_not_block_the_missing_human_economic_interval() -> None:
    book, execution = _seed_needs_review(capacity=4)
    observed = apply_venue_recovery_input(
        book,
        execution,
        ObserveVenueStatus(
            input_id=VenueInputId("human-status-high-water"),
            leg_key=LEG_A,
            status=VenueAttemptState.NEEDS_REVIEW,
            observation_id=VenueObservationId("human-status-high-water-observation"),
            cumulative_quantity=Quantity(4),
        ),
    )
    assert observed.disposition is VenueRecoveryDisposition.APPLIED
    assert observed.execution == execution
    assert observed.book.active_attempt(LEG_A).cumulative_quantity == Quantity(4)

    attested = _ingest(
        observed.book,
        observed.execution,
        _human_fill(
            input_suffix="after-status-high-water",
            quantity=4,
            prior=0,
            resulting=4,
        ),
        input_id="ingest-after-status-high-water",
    )

    assert attested.disposition is VenueRecoveryDisposition.APPLIED
    assert attested.quantity_delta == 4
    assert attested.execution.position.raw_quantity == 4
    assert len(attested.book.coverage_for_leg(LEG_A)) == 1
    assert attested.book.active_attempt(LEG_A).cumulative_quantity == Quantity(4)


def test_status_high_water_does_not_block_the_missing_broker_economic_interval() -> (
    None
):
    book, execution = _seed_needs_review(capacity=4)
    observed = apply_venue_recovery_input(
        book,
        execution,
        ObserveVenueStatus(
            input_id=VenueInputId("broker-status-high-water"),
            leg_key=LEG_A,
            status=VenueAttemptState.NEEDS_REVIEW,
            observation_id=VenueObservationId("broker-status-high-water-observation"),
            cumulative_quantity=Quantity(4),
        ),
    )
    assert observed.disposition is VenueRecoveryDisposition.APPLIED
    assert observed.execution == execution
    assert observed.book.active_attempt(LEG_A).cumulative_quantity == Quantity(4)

    recovered = apply_venue_recovery_input(
        observed.book,
        observed.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("broker-fill-after-status-high-water"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=_broker_fill(
                "broker-fill-after-status-high-water-source",
                "broker-fill-after-status-high-water-root",
                quantity=4,
            ),
            evidence_digest=b"\x8c" * 32,
        ),
    )

    assert recovered.disposition is VenueRecoveryDisposition.APPLIED
    assert recovered.quantity_delta == 4
    assert recovered.execution.position.raw_quantity == 4
    assert len(recovered.book.broker_coverage_for_leg(LEG_A)) == 1
    assert recovered.book.active_attempt(LEG_A).cumulative_quantity == Quantity(4)


def test_one_broker_fact_cannot_corroborate_two_human_intervals() -> None:
    book, execution = _seed_needs_review(capacity=2)
    first_human = _ingest(
        book,
        execution,
        _human_fill(input_suffix="interval-one", quantity=1, prior=0, resulting=1),
        input_id="ingest-interval-one",
    )
    second_human = _ingest(
        first_human.book,
        first_human.execution,
        _human_fill(input_suffix="interval-two", quantity=1, prior=1, resulting=2),
        input_id="ingest-interval-two",
    )
    broker_fact = _broker_fill(
        "single-broker-source",
        "single-broker-root",
        quantity=1,
        units=100,
    )
    first_mapping = apply_venue_recovery_input(
        second_human.book,
        second_human.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("map-broker-to-interval-one"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(1),
            fact=broker_fact,
            evidence_digest=b"\x81" * 32,
        ),
    )
    assert first_mapping.disposition is VenueRecoveryDisposition.APPLIED

    second_mapping = apply_venue_recovery_input(
        first_mapping.book,
        first_mapping.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("map-broker-to-interval-two"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(1),
            resulting_cumulative_quantity=Quantity(2),
            fact=broker_fact,
            evidence_digest=b"\x82" * 32,
        ),
    )

    assert (
        second_mapping.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    )
    assert second_mapping.quantity_delta == 0
    coverages = second_mapping.book.coverage_for_leg(LEG_A)
    assert coverages[0].broker_corroborated is True
    assert coverages[1].broker_corroborated is False


def test_one_broker_root_cannot_corroborate_two_human_intervals() -> None:
    book, execution = _seed_needs_review(capacity=2)
    first = _ingest(
        book,
        execution,
        _human_fill(input_suffix="root-interval-one", quantity=1, prior=0, resulting=1),
        input_id="ingest-root-interval-one",
    )
    second = _ingest(
        first.book,
        first.execution,
        _human_fill(input_suffix="root-interval-two", quantity=1, prior=1, resulting=2),
        input_id="ingest-root-interval-two",
    )
    first_mapping = apply_venue_recovery_input(
        second.book,
        second.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("map-shared-root-one"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(1),
            fact=_broker_fill("shared-root-source-one", "shared-root", quantity=1),
            evidence_digest=b"\x84" * 32,
        ),
    )

    second_mapping = apply_venue_recovery_input(
        first_mapping.book,
        first_mapping.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("map-shared-root-two"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(1),
            resulting_cumulative_quantity=Quantity(2),
            fact=_broker_fill("shared-root-source-two", "shared-root", quantity=1),
            evidence_digest=b"\x85" * 32,
        ),
    )

    assert (
        second_mapping.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    )
    assert second_mapping.quantity_delta == 0
    coverages = second_mapping.book.coverage_for_leg(LEG_A)
    assert coverages[0].broker_corroborated is True
    assert coverages[1].broker_corroborated is False


def test_broker_corroboration_cannot_reuse_a_human_economic_root() -> None:
    book, execution = _seed_needs_review(capacity=2)
    first = _ingest(
        book,
        execution,
        _human_fill(input_suffix="human-root-owner", quantity=1, prior=0, resulting=1),
        input_id="ingest-human-root-owner",
    )
    second = _ingest(
        first.book,
        first.execution,
        _human_fill(input_suffix="human-root-target", quantity=1, prior=1, resulting=2),
        input_id="ingest-human-root-target",
    )

    mapped = apply_venue_recovery_input(
        second.book,
        second.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("map-broker-over-human-root"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(1),
            resulting_cumulative_quantity=Quantity(2),
            fact=_broker_fill(
                "broker-over-human-root-source",
                "human-root-human-root-owner",
                quantity=1,
            ),
            evidence_digest=b"\x86" * 32,
        ),
    )

    assert mapped.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert mapped.quantity_delta == 0
    assert mapped.book.coverage_for_leg(LEG_A)[1].broker_corroborated is False


def test_broker_authoritative_overfill_applies_exactly_and_latches_quarantine() -> None:
    book, execution = _seed_needs_review(capacity=4)
    overfill = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("broker-authoritative-overfill"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(5),
            fact=_broker_fill(
                "broker-overfill-source", "broker-overfill-root", quantity=5
            ),
            evidence_digest=b"\x87" * 32,
        ),
    )

    assert overfill.disposition is VenueRecoveryDisposition.APPLIED
    assert overfill.quantity_delta == 5
    assert overfill.execution.position.raw_quantity == 5
    assert overfill.execution.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert overfill.book.broker_coverage_for_leg(LEG_A)[
        0
    ].resulting_cumulative_quantity == Quantity(5)


def test_disjoint_later_broker_interval_enters_the_broker_fact_reducer() -> None:
    book, execution = _seed_needs_review()
    attested = _ingest(book, execution, _human_fill())
    assert attested.disposition is VenueRecoveryDisposition.APPLIED
    broker_fact = _broker_fill(
        "broker-disjoint",
        "broker-disjoint-root",
        quantity=2,
        units=105,
    )
    command = RecordBrokerFillEvidence(
        input_id=VenueInputId("broker-evidence-disjoint"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_cumulative_quantity=Quantity(4),
        resulting_cumulative_quantity=Quantity(6),
        fact=broker_fact,
        evidence_digest=b"\x55" * 32,
    )

    applied = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        command,
    )

    assert applied.disposition is VenueRecoveryDisposition.APPLIED
    assert applied.quantity_delta == 2
    assert applied.execution.position.raw_quantity == 6
    broker_head = applied.execution.root_heads.get(_root_key("broker-disjoint-root"))
    assert broker_head is not None
    assert broker_head.authority is ExecutionAuthority.BROKER_AUTHORITATIVE
    assert applied.book.reconciliations == ()


def test_disjoint_broker_interval_after_terminal_release_applies_and_advances_closure() -> (
    None
):
    book, execution, _ = _released_state()
    before_quantity = execution.position.raw_quantity
    command = RecordBrokerFillEvidence(
        input_id=VenueInputId("broker-disjoint-after-release"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_cumulative_quantity=Quantity(4),
        resulting_cumulative_quantity=Quantity(6),
        fact=_broker_fill(
            "broker-disjoint-after-release-source",
            "broker-disjoint-after-release-root",
            quantity=2,
            units=105,
        ),
        evidence_digest=b"\x7c" * 32,
        closure_id=ClosureId("broker-economic-successor"),
        evidence_reference=EvidenceReference("late-broker-fill-evidence"),
    )

    applied = apply_venue_recovery_input(book, execution, command)

    assert applied.disposition is VenueRecoveryDisposition.APPLIED
    assert applied.quantity_delta == 2
    assert applied.execution.position.raw_quantity == before_quantity + 2
    head = applied.book.closure_head(LEG_A)
    assert head is not None
    assert head.kind is VenueClosureKind.BROKER_ECONOMIC
    assert head.ordinal == 2
    assert head.predecessor_closure_id == ClosureId("operator-release-a")
    assert head.cumulative_quantity == Quantity(6)


@pytest.mark.parametrize(
    ("prior", "resulting", "quantity", "units"),
    [
        (3, 6, 3, 100),  # partial overlap with human interval (0, 4]
        (0, 4, 4, 101),  # exact interval but changed committed price
        (0, 4, 3, 100),  # cumulative interval and broker quantity disagree
    ],
)
def test_overlapping_or_mismatching_broker_evidence_requires_reconciliation(
    prior: int,
    resulting: int,
    quantity: int,
    units: int,
) -> None:
    book, execution = _seed_needs_review()
    attested = _ingest(book, execution, _human_fill())
    assert attested.disposition is VenueRecoveryDisposition.APPLIED
    before_reconciliations = attested.book.reconciliations
    command = RecordBrokerFillEvidence(
        input_id=VenueInputId(
            f"broker-reconcile-{prior}-{resulting}-{quantity}-{units}"
        ),
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_cumulative_quantity=Quantity(prior),
        resulting_cumulative_quantity=Quantity(resulting),
        fact=_broker_fill(
            f"broker-reconcile-source-{prior}-{quantity}-{units}",
            f"broker-reconcile-root-{prior}-{quantity}-{units}",
            quantity=quantity,
            units=units,
        ),
        evidence_digest=b"\x66" * 32,
    )

    reconciled = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        command,
    )

    assert reconciled.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert reconciled.quantity_delta == 0
    assert (
        reconciled.execution.position.scope,
        reconciled.execution.position.raw_quantity,
        reconciled.execution.position.basis_authority,
        reconciled.execution.position.cost_basis,
        reconciled.execution.position.root_fill_sequence,
        reconciled.execution.position.effective_head_ids,
        reconciled.execution.position.basis_price_metadata,
        reconciled.execution.position.tail_fold_input,
    ) == (
        attested.execution.position.scope,
        attested.execution.position.raw_quantity,
        attested.execution.position.basis_authority,
        attested.execution.position.cost_basis,
        attested.execution.position.root_fill_sequence,
        attested.execution.position.effective_head_ids,
        attested.execution.position.basis_price_metadata,
        attested.execution.position.tail_fold_input,
    )
    assert reconciled.execution.root_heads == attested.execution.root_heads
    assert (
        reconciled.execution.integrity
        & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    assert (
        reconciled.execution.position.integrity_floor
        & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    assert len(reconciled.book.reconciliations) == len(before_reconciliations) + 1


def test_unresolved_broker_contradiction_blocks_release_and_parent_finalization() -> (
    None
):
    book, execution = _seed_needs_review(capacity=4)
    attested = _ingest(book, execution, _human_fill(quantity=4, prior=0, resulting=4))
    contradicted = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("contradict-human-economics"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=_broker_fill(
                "contradict-human-source",
                "contradict-human-root",
                quantity=4,
                units=101,
            ),
            evidence_digest=b"\x88" * 32,
        ),
    )
    assert contradicted.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED

    release = apply_venue_recovery_input(
        contradicted.book,
        contradicted.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("release-with-unresolved-contradiction"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            claim_occurrence_id=CLAIM,
            venue_cumulative_quantity=Quantity(4),
            broker_terminal_state=VenueAttemptState.CANCELED,
            actor=ACTOR,
            reason="contradiction must remain blocking",
            evidence_reference=EVIDENCE,
            closure_id=ClosureId("blocked-contradiction-release"),
            evidence_digest=b"\x89" * 32,
        ),
    )
    assert release.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert release.book == contradicted.book

    terminal = apply_venue_recovery_input(
        contradicted.book,
        contradicted.execution,
        ObserveVenueStatus(
            input_id=VenueInputId("terminal-with-unresolved-contradiction"),
            leg_key=LEG_A,
            status=VenueAttemptState.CANCELED,
            observation_id=VenueObservationId("contradicted-terminal-observation"),
            cumulative_quantity=Quantity(4),
            closure_id=ClosureId("contradicted-terminal-closure"),
            evidence_reference=EvidenceReference("contradicted-terminal-evidence"),
        ),
    )
    closed = apply_venue_recovery_input(
        terminal.book,
        terminal.execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("close-with-unresolved-contradiction"),
            effect_id=EFFECT,
            proof=_acceptance_proof(
                terminal.book,
                AcceptanceProofKind.COVERED_RECONCILIATION,
                "unresolved-contradiction-proof",
            ),
        ),
    )

    assert closed.disposition is VenueRecoveryDisposition.APPLIED
    assert closed.book.effect(EFFECT).acceptance_set_state is AcceptanceSetState.CLOSED
    assert closed.book.effect(EFFECT).state is BrokerEffectState.NEEDS_REVIEW


def test_broker_fact_reducer_remains_structurally_broker_only() -> None:
    execution = ExecutionSnapshot.flat(POSITION_SCOPE)

    with pytest.raises(TypeError):
        apply_broker_execution_fact(
            execution.position,
            execution.integrity,
            execution.root_heads,
            execution.seen_facts,
            _human_fill(),  # type: ignore[arg-type]
        )

    assert execution == ExecutionSnapshot.flat(POSITION_SCOPE)


@pytest.mark.parametrize("kind", ["correct", "bust"])
def test_broker_correction_or_bust_cannot_revise_a_human_root(kind: str) -> None:
    book, execution = _seed_needs_review()
    attested = _ingest(book, execution, _human_fill())
    assert attested.disposition is VenueRecoveryDisposition.APPLIED
    key = ExecutionFactKey(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        source_event_id=SourceEventId(f"broker-{kind}"),
    )
    if kind == "correct":
        fact = BrokerTradeCorrectFact(
            key=key,
            scope=_execution_scope(),
            root_fill_id=RootFillId("human-root-1"),
            predecessor_source_event_id=SourceEventId("human-source-1"),
            revised_quantity=Quantity(3),
            revised_price=_price(101),
        )
    else:
        fact = BrokerTradeBustFact(
            key=key,
            scope=_execution_scope(),
            root_fill_id=RootFillId("human-root-1"),
            predecessor_source_event_id=SourceEventId("human-source-1"),
            reported_price=_price(100),
        )

    transition = apply_broker_execution_fact(
        attested.execution.position,
        attested.execution.integrity,
        attested.execution.root_heads,
        attested.execution.seen_facts,
        fact,
    )

    assert transition.disposition is TransitionDisposition.RECONCILIATION_REQUIRED
    assert transition.quantity_delta == 0
    assert transition.position.raw_quantity == 4
    head = transition.root_heads.get(_root_key("human-root-1"))
    assert head is not None
    assert head.authority is ExecutionAuthority.HUMAN_ATTESTED


def test_broker_correction_applies_through_the_bound_active_leg() -> None:
    book, execution = _seed_needs_review(capacity=8)
    filled = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("broker-root-before-correction"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=_broker_fill("broker-root-source", "broker-revision-root", quantity=4),
            evidence_digest=b"\x91" * 32,
        ),
    )
    correction = BrokerTradeCorrectFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("broker-correction-source"),
        ),
        scope=_execution_scope(),
        root_fill_id=RootFillId("broker-revision-root"),
        predecessor_source_event_id=SourceEventId("broker-root-source"),
        revised_quantity=Quantity(3),
        revised_price=_price(101),
    )

    corrected = apply_venue_recovery_input(
        filled.book,
        filled.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("apply-bound-broker-correction"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_root_quantity=Quantity(4),
            prior_venue_cumulative_quantity=Quantity(4),
            resulting_venue_cumulative_quantity=Quantity(3),
            fact=correction,
            evidence_digest=b"\x92" * 32,
        ),
    )

    assert corrected.disposition is VenueRecoveryDisposition.APPLIED
    assert corrected.quantity_delta == -1
    assert corrected.execution.position.raw_quantity == 3
    coverage = corrected.book.broker_coverage_for_leg(LEG_A)[0]
    assert coverage.resulting_cumulative_quantity == Quantity(3)
    assert coverage.head_fact == correction
    assert corrected.book._execution_matches(corrected.execution, POSITION_SCOPE)


def test_broker_bust_after_release_applies_and_appends_a_closure_successor() -> None:
    book, execution = _seed_needs_review(capacity=4)
    filled = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("broker-root-before-bust"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=_broker_fill(
                "broker-bust-root-source", "broker-bust-root", quantity=4
            ),
            evidence_digest=b"\x93" * 32,
        ),
    )
    released = apply_venue_recovery_input(
        filled.book,
        filled.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("release-before-broker-bust"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            claim_occurrence_id=CLAIM,
            venue_cumulative_quantity=Quantity(4),
            broker_terminal_state=VenueAttemptState.CANCELED,
            actor=ACTOR,
            reason="exact broker fill is covered before later bust",
            evidence_reference=EVIDENCE,
            closure_id=ClosureId("release-before-bust"),
            evidence_digest=b"\x94" * 32,
        ),
    )
    bust = BrokerTradeBustFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("broker-bust-source"),
        ),
        scope=_execution_scope(),
        root_fill_id=RootFillId("broker-bust-root"),
        predecessor_source_event_id=SourceEventId("broker-bust-root-source"),
        reported_price=_price(100),
    )

    busted = apply_venue_recovery_input(
        released.book,
        released.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("apply-bound-broker-bust"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_root_quantity=Quantity(4),
            prior_venue_cumulative_quantity=Quantity(4),
            resulting_venue_cumulative_quantity=Quantity(0),
            fact=bust,
            evidence_digest=b"\x95" * 32,
            closure_id=ClosureId("broker-bust-successor"),
            evidence_reference=EvidenceReference("broker-bust-evidence"),
        ),
    )

    assert busted.disposition is VenueRecoveryDisposition.APPLIED
    assert busted.quantity_delta == -4
    assert busted.execution.position.raw_quantity == 0
    head = busted.book.closure_head(LEG_A)
    assert head is not None
    assert head.kind is VenueClosureKind.BROKER_ECONOMIC
    assert head.ordinal == 2
    assert head.predecessor_closure_id == ClosureId("release-before-bust")
    assert head.cumulative_quantity == Quantity(0)
    assert head.source_event_id == SourceEventId("broker-bust-source")


def test_broker_bust_after_finalization_demotes_stale_operator_authority() -> None:
    book, execution = _seed_needs_review(capacity=4)
    filled = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("broker-root-before-finalized-bust"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=_broker_fill(
                "finalized-bust-root-source", "finalized-bust-root", quantity=4
            ),
            evidence_digest=b"\xa3" * 32,
        ),
    )
    released = apply_venue_recovery_input(
        filled.book,
        filled.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("release-before-finalized-bust"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            claim_occurrence_id=CLAIM,
            venue_cumulative_quantity=Quantity(4),
            broker_terminal_state=VenueAttemptState.FILLED,
            actor=ACTOR,
            reason="exact filled terminal report",
            evidence_reference=EVIDENCE,
            closure_id=ClosureId("release-before-finalized-bust"),
            evidence_digest=b"\xa4" * 32,
        ),
    )
    finalized = apply_venue_recovery_input(
        released.book,
        released.execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("close-before-finalized-bust"),
            effect_id=EFFECT,
            proof=_acceptance_proof(
                released.book,
                AcceptanceProofKind.COVERED_RECONCILIATION,
                "proof-before-finalized-bust",
            ),
        ),
    )
    assert finalized.book.effect(EFFECT).state is BrokerEffectState.OPERATOR_RECONCILED

    busted = apply_venue_recovery_input(
        finalized.book,
        finalized.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("apply-finalized-broker-bust"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_root_quantity=Quantity(4),
            prior_venue_cumulative_quantity=Quantity(4),
            resulting_venue_cumulative_quantity=Quantity(0),
            fact=BrokerTradeBustFact(
                key=ExecutionFactKey(
                    broker=BROKER,
                    environment=ENVIRONMENT,
                    account=ACCOUNT,
                    source_event_id=SourceEventId("finalized-bust-source"),
                ),
                scope=_execution_scope(),
                root_fill_id=RootFillId("finalized-bust-root"),
                predecessor_source_event_id=SourceEventId("finalized-bust-root-source"),
                reported_price=_price(100),
            ),
            evidence_digest=b"\xa5" * 32,
            closure_id=ClosureId("finalized-bust-successor"),
            evidence_reference=EvidenceReference("finalized-bust-evidence"),
        ),
    )

    assert busted.disposition is VenueRecoveryDisposition.APPLIED
    assert busted.quantity_delta == -4
    assert busted.book.effect(EFFECT).state is BrokerEffectState.NEEDS_REVIEW
    assert busted.book.effect(EFFECT).acceptance_set_state is AcceptanceSetState.CLOSED
    assert busted.book._leg_summary(EFFECT).finalization_ready_count == 0
    hydrated = _audit_hydrate_book(busted.book, busted.execution)
    assert hydrated.effect(EFFECT).state is BrokerEffectState.NEEDS_REVIEW
    assert hydrated._leg_summary(EFFECT).finalization_ready_count == 0


def test_bound_revision_of_a_human_root_requires_reconciliation_without_delta() -> None:
    book, execution = _seed_needs_review()
    attested = _ingest(book, execution, _human_fill())
    correction = BrokerTradeCorrectFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("human-root-bound-correction"),
        ),
        scope=_execution_scope(),
        root_fill_id=RootFillId("human-root-1"),
        predecessor_source_event_id=SourceEventId("human-source-1"),
        revised_quantity=Quantity(3),
        revised_price=_price(101),
    )

    refused = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("reject-bound-human-root-correction"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_root_quantity=Quantity(4),
            prior_venue_cumulative_quantity=Quantity(4),
            resulting_venue_cumulative_quantity=Quantity(3),
            fact=correction,
            evidence_digest=b"\x96" * 32,
        ),
    )

    assert refused.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert refused.quantity_delta == 0
    assert refused.execution.position.raw_quantity == 4
    assert (
        refused.execution.integrity
        & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    assert refused.book._execution_matches(refused.execution, POSITION_SCOPE)


def test_non_tail_broker_revision_commits_truth_but_keeps_mapping_unresolved() -> None:
    book, execution = _seed_needs_review(capacity=8)
    first = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("non-tail-first-root"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(2),
            fact=_broker_fill("non-tail-first-source", "non-tail-first", quantity=2),
            evidence_digest=b"\x97" * 32,
        ),
    )
    second = apply_venue_recovery_input(
        first.book,
        first.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("non-tail-second-root"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(2),
            resulting_cumulative_quantity=Quantity(4),
            fact=_broker_fill("non-tail-second-source", "non-tail-second", quantity=2),
            evidence_digest=b"\x98" * 32,
        ),
    )
    correction = BrokerTradeCorrectFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("non-tail-correction-source"),
        ),
        scope=_execution_scope(),
        root_fill_id=RootFillId("non-tail-first"),
        predecessor_source_event_id=SourceEventId("non-tail-first-source"),
        revised_quantity=Quantity(1),
        revised_price=_price(101),
    )

    corrected = apply_venue_recovery_input(
        second.book,
        second.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("apply-non-tail-correction"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_root_quantity=Quantity(2),
            prior_venue_cumulative_quantity=Quantity(4),
            resulting_venue_cumulative_quantity=Quantity(3),
            fact=correction,
            evidence_digest=b"\x99" * 32,
        ),
    )

    assert corrected.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert corrected.quantity_delta == -1
    assert corrected.execution.position.raw_quantity == 3
    first_coverage = corrected.book.broker_coverage_for_leg(LEG_A)[0]
    assert first_coverage.head_fact == correction
    assert first_coverage.mapping_exact is False
    assert corrected.book.reconciliations[-1].canonical_applied is True
    assert corrected.book._execution_matches(corrected.execution, POSITION_SCOPE)


def test_broker_correction_after_a_tail_bust_reexpands_the_tombstone() -> None:
    book, execution = _seed_needs_review(capacity=4)
    filled = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("fill-before-active-bust"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=_broker_fill(
                "active-bust-root-source", "active-bust-root", quantity=4
            ),
            evidence_digest=b"\x9a" * 32,
        ),
    )
    bust = BrokerTradeBustFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("active-bust-source"),
        ),
        scope=_execution_scope(),
        root_fill_id=RootFillId("active-bust-root"),
        predecessor_source_event_id=SourceEventId("active-bust-root-source"),
    )
    busted = apply_venue_recovery_input(
        filled.book,
        filled.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("apply-active-bust"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_root_quantity=Quantity(4),
            prior_venue_cumulative_quantity=Quantity(4),
            resulting_venue_cumulative_quantity=Quantity(0),
            fact=bust,
            evidence_digest=b"\x9b" * 32,
        ),
    )
    correction = BrokerTradeCorrectFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("correct-after-bust-source"),
        ),
        scope=_execution_scope(),
        root_fill_id=RootFillId("active-bust-root"),
        predecessor_source_event_id=SourceEventId("active-bust-source"),
        revised_quantity=Quantity(2),
        revised_price=_price(102),
    )

    corrected = apply_venue_recovery_input(
        busted.book,
        busted.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("apply-correction-after-bust"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_root_quantity=Quantity(0),
            prior_venue_cumulative_quantity=Quantity(0),
            resulting_venue_cumulative_quantity=Quantity(2),
            fact=correction,
            evidence_digest=b"\x9c" * 32,
        ),
    )

    assert busted.disposition is VenueRecoveryDisposition.APPLIED
    assert corrected.disposition is VenueRecoveryDisposition.APPLIED
    assert corrected.quantity_delta == 2
    coverage = corrected.book.broker_coverage_for_leg(LEG_A)[0]
    assert coverage.prior_cumulative_quantity == Quantity(0)
    assert coverage.resulting_cumulative_quantity == Quantity(2)
    assert coverage.head_fact == correction


def test_exact_revision_replay_does_not_append_a_second_closure() -> None:
    book, execution = _seed_needs_review(capacity=4)
    filled = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("fill-before-replayed-bust"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=_broker_fill(
                "replayed-bust-root-source", "replayed-bust-root", quantity=4
            ),
            evidence_digest=b"\x9d" * 32,
        ),
    )
    released = apply_venue_recovery_input(
        filled.book,
        filled.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("release-before-replayed-bust"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            claim_occurrence_id=CLAIM,
            venue_cumulative_quantity=Quantity(4),
            broker_terminal_state=VenueAttemptState.CANCELED,
            actor=ACTOR,
            reason="freeze one terminal closure before semantic replay",
            evidence_reference=EVIDENCE,
            closure_id=ClosureId("release-before-replayed-bust"),
            evidence_digest=b"\x9e" * 32,
        ),
    )
    fact = BrokerTradeBustFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("replayed-bust-source"),
        ),
        scope=_execution_scope(),
        root_fill_id=RootFillId("replayed-bust-root"),
        predecessor_source_event_id=SourceEventId("replayed-bust-root-source"),
    )
    command = RecordBrokerRevisionEvidence(
        input_id=VenueInputId("first-replayed-bust-command"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_root_quantity=Quantity(4),
        prior_venue_cumulative_quantity=Quantity(4),
        resulting_venue_cumulative_quantity=Quantity(0),
        fact=fact,
        evidence_digest=b"\x9f" * 32,
        closure_id=ClosureId("one-bust-successor"),
        evidence_reference=EvidenceReference("one-bust-successor-evidence"),
    )
    first = apply_venue_recovery_input(released.book, released.execution, command)
    semantic_replay = apply_venue_recovery_input(
        first.book,
        first.execution,
        replace(command, input_id=VenueInputId("fresh-replayed-bust-command")),
    )
    exact_replay = apply_venue_recovery_input(
        semantic_replay.book,
        semantic_replay.execution,
        replace(command, input_id=VenueInputId("fresh-replayed-bust-command")),
    )

    assert semantic_replay.disposition is VenueRecoveryDisposition.APPLIED
    assert semantic_replay.quantity_delta == 0
    assert exact_replay.disposition is VenueRecoveryDisposition.EXACT_REPLAY
    assert len(semantic_replay.book.closure_history) == 2


def test_account_registry_and_per_symbol_bindings_advance_independently() -> None:
    book, execution = _seed_needs_review(capacity=4)
    other_symbol = SymbolId("MSFT")
    other_scope = PositionScope(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        symbol_id=other_symbol,
    )
    other_execution = ExecutionSnapshot.bind_verified(
        PositionState.flat(other_scope),
        PositionIntegrity.CONSISTENT,
        RootHeadIndex.empty(other_scope),
        execution.seen_facts,
    )
    other_effect = EffectId("effect-submit-msft")
    registered = apply_venue_recovery_input(
        book,
        other_execution,
        RequestedEffect(
            input_id=VenueInputId("request-msft-effect"),
            effect_id=other_effect,
            request_occurrence_id=RequestOccurrenceId("request-msft"),
            mandate_id=MandateId("mandate-msft"),
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId("client-msft"),
            symbol_id=other_symbol,
            side=ExecutionSide.BUY,
            quantity=Quantity(4),
            economic_scope=b"MSFT|BUY|four",
        ),
    )
    assert registered.disposition is VenueRecoveryDisposition.APPLIED

    aapl_fill = apply_venue_recovery_input(
        registered.book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("aapl-fill-after-msft-register"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(2),
            fact=_broker_fill(
                "aapl-cross-symbol-source", "aapl-cross-symbol-root", quantity=2
            ),
            evidence_digest=b"\xa0" * 32,
        ),
    )
    assert aapl_fill.disposition is VenueRecoveryDisposition.APPLIED

    stale_other = apply_venue_recovery_input(
        aapl_fill.book,
        other_execution,
        RecordDispatchClaim(
            input_id=VenueInputId("stale-msft-claim"),
            effect_id=other_effect,
            claim_occurrence_id=ClaimOccurrenceId("claim-msft"),
        ),
    )
    assert stale_other.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED

    rebound_other = ExecutionSnapshot.bind_verified(
        PositionState.flat(other_scope),
        PositionIntegrity.CONSISTENT,
        RootHeadIndex.empty(other_scope),
        aapl_fill.execution.seen_facts,
    )
    claimed = apply_venue_recovery_input(
        aapl_fill.book,
        rebound_other,
        RecordDispatchClaim(
            input_id=VenueInputId("current-msft-claim"),
            effect_id=other_effect,
            claim_occurrence_id=ClaimOccurrenceId("claim-msft"),
        ),
    )

    assert claimed.disposition is VenueRecoveryDisposition.APPLIED
    assert claimed.book.effect(other_effect).state is BrokerEffectState.DISPATCH_CLAIMED
    assert claimed.book._execution_matches(rebound_other, other_scope)


def test_new_same_symbol_effect_cannot_rewind_an_existing_execution_binding() -> None:
    book, execution = _seed_needs_review(capacity=4)
    filled = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("fill-before-same-symbol-rewind"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(2),
            fact=_broker_fill("rewind-source", "rewind-root", quantity=2),
            evidence_digest=b"\xa1" * 32,
        ),
    )
    stale = ExecutionSnapshot.flat(POSITION_SCOPE)

    refused = apply_venue_recovery_input(
        filled.book,
        stale,
        RequestedEffect(
            input_id=VenueInputId("stale-same-symbol-request"),
            effect_id=EffectId("second-aapl-effect"),
            request_occurrence_id=RequestOccurrenceId("second-aapl-request"),
            mandate_id=MandateId("second-aapl-mandate"),
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId("second-aapl-client"),
            symbol_id=SYMBOL,
            side=ExecutionSide.BUY,
            quantity=Quantity(2),
            economic_scope=b"AAPL|BUY|second-effect",
        ),
    )

    assert refused.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert filled.book.effect(EffectId("second-aapl-effect")) is None


def test_wo0146_red_sibling_broker_fills_latch_effect_wide_overfill() -> None:
    book, execution = _seed_needs_review(
        capacity=4,
        leg_keys=(LEG_A, LEG_B),
    )

    for index, leg_key in enumerate((LEG_A, LEG_B), start=1):
        applied = apply_venue_recovery_input(
            book,
            execution,
            RecordBrokerFillEvidence(
                input_id=VenueInputId(f"aggregate-broker-fill-{index}"),
                effect_id=EFFECT,
                leg_key=leg_key,
                prior_cumulative_quantity=Quantity(0),
                resulting_cumulative_quantity=Quantity(4),
                fact=_broker_fill(
                    f"aggregate-broker-source-{index}",
                    f"aggregate-broker-root-{index}",
                    leg_key=leg_key,
                    quantity=4,
                ),
                evidence_digest=bytes((0xB0 + index,)) * 32,
            ),
        )
        assert applied.disposition is VenueRecoveryDisposition.APPLIED
        assert applied.quantity_delta == 4
        book = applied.book
        execution = applied.execution

    assert execution.position.raw_quantity == 8
    assert execution.integrity & PositionIntegrity.OVERFILL_QUARANTINE


def test_wo0146_red_sibling_human_fills_cannot_exceed_effect_capacity() -> None:
    book, execution = _seed_needs_review(
        capacity=4,
        leg_keys=(LEG_A, LEG_B),
    )
    first = _ingest(
        book,
        execution,
        _human_fill(
            input_suffix="aggregate-human-a",
            leg_key=LEG_A,
            quantity=4,
            prior=0,
            resulting=4,
        ),
        input_id="aggregate-human-fill-a",
    )
    assert first.disposition is VenueRecoveryDisposition.APPLIED

    second = _ingest(
        first.book,
        first.execution,
        _human_fill(
            input_suffix="aggregate-human-b",
            leg_key=LEG_B,
            quantity=4,
            prior=0,
            resulting=4,
        ),
        input_id="aggregate-human-fill-b",
    )

    assert second.disposition is VenueRecoveryDisposition.REFUSED
    assert second.quantity_delta == 0
    assert second.execution.position.raw_quantity == 4
    assert second.book == first.book


def test_wo0146_red_tail_revision_after_non_tail_mapping_applies_canonical_truth() -> (
    None
):
    book, execution = _seed_needs_review(capacity=8)
    first_fill = _broker_fill(
        "mapping-first-source",
        "mapping-first-root",
        quantity=2,
    )
    first = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("mapping-first-fill"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(2),
            fact=first_fill,
            evidence_digest=b"\xb3" * 32,
        ),
    )
    second_fill = _broker_fill(
        "mapping-second-source",
        "mapping-second-root",
        quantity=2,
    )
    second = apply_venue_recovery_input(
        first.book,
        first.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("mapping-second-fill"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(2),
            resulting_cumulative_quantity=Quantity(4),
            fact=second_fill,
            evidence_digest=b"\xb4" * 32,
        ),
    )
    non_tail_correction = BrokerTradeCorrectFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("mapping-first-correction"),
        ),
        scope=_execution_scope(),
        root_fill_id=first_fill.root_fill_id,
        predecessor_source_event_id=first_fill.key.source_event_id,
        revised_quantity=Quantity(1),
        revised_price=_price(101),
    )
    first_corrected = apply_venue_recovery_input(
        second.book,
        second.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("mapping-first-correction-input"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_root_quantity=Quantity(2),
            prior_venue_cumulative_quantity=Quantity(4),
            resulting_venue_cumulative_quantity=Quantity(3),
            fact=non_tail_correction,
            evidence_digest=b"\xb5" * 32,
        ),
    )
    assert (
        first_corrected.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    )
    assert first_corrected.quantity_delta == -1

    tail_correction = BrokerTradeCorrectFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("mapping-second-correction"),
        ),
        scope=_execution_scope(),
        root_fill_id=second_fill.root_fill_id,
        predecessor_source_event_id=second_fill.key.source_event_id,
        revised_quantity=Quantity(3),
        revised_price=_price(102),
    )
    tail_corrected = apply_venue_recovery_input(
        first_corrected.book,
        first_corrected.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("mapping-second-correction-input"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_root_quantity=Quantity(2),
            prior_venue_cumulative_quantity=Quantity(3),
            resulting_venue_cumulative_quantity=Quantity(4),
            fact=tail_correction,
            evidence_digest=b"\xb6" * 32,
        ),
    )

    assert (
        tail_corrected.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    )
    assert tail_corrected.quantity_delta == 1
    assert tail_corrected.execution.position.raw_quantity == 4
    tail_coverage = tail_corrected.book.broker_coverage_for_leg(LEG_A)[1]
    assert tail_coverage.head_fact == tail_correction
    assert tail_coverage.mapping_exact is False
    assert tail_corrected.book.reconciliations[-1].canonical_applied is True


def test_wo0146_red_stale_terminal_after_bust_cannot_block_later_broker_fill() -> None:
    book, execution = _seed_needs_review(capacity=4)
    root_fill = _broker_fill(
        "stale-terminal-root-source",
        "stale-terminal-root",
        quantity=4,
    )
    filled = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("stale-terminal-root-input"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=root_fill,
            evidence_digest=b"\xb7" * 32,
        ),
    )
    released = apply_venue_recovery_input(
        filled.book,
        filled.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("stale-terminal-release"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            claim_occurrence_id=CLAIM,
            venue_cumulative_quantity=Quantity(4),
            broker_terminal_state=VenueAttemptState.FILLED,
            actor=ACTOR,
            reason="exact broker root is covered before its later bust",
            evidence_reference=EVIDENCE,
            closure_id=ClosureId("stale-terminal-release-closure"),
            evidence_digest=b"\xb8" * 32,
        ),
    )
    bust = BrokerTradeBustFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("stale-terminal-bust-source"),
        ),
        scope=_execution_scope(),
        root_fill_id=root_fill.root_fill_id,
        predecessor_source_event_id=root_fill.key.source_event_id,
    )
    busted = apply_venue_recovery_input(
        released.book,
        released.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("stale-terminal-bust-input"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_root_quantity=Quantity(4),
            prior_venue_cumulative_quantity=Quantity(4),
            resulting_venue_cumulative_quantity=Quantity(0),
            fact=bust,
            evidence_digest=b"\xb9" * 32,
            closure_id=ClosureId("stale-terminal-bust-closure"),
            evidence_reference=EvidenceReference("stale-terminal-bust-proof"),
        ),
    )
    assert busted.disposition is VenueRecoveryDisposition.APPLIED
    assert busted.quantity_delta == -4

    stale_status = apply_venue_recovery_input(
        busted.book,
        busted.execution,
        ObserveVenueStatus(
            input_id=VenueInputId("stale-terminal-status-input"),
            leg_key=LEG_A,
            status=VenueAttemptState.FILLED,
            observation_id=VenueObservationId("stale-terminal-status-observation"),
            cumulative_quantity=Quantity(4),
            closure_id=ClosureId("stale-terminal-status-closure"),
            evidence_reference=EvidenceReference("stale-terminal-status-proof"),
        ),
    )
    late_fill = _broker_fill(
        "post-bust-late-fill-source",
        "post-bust-late-fill-root",
        quantity=4,
    )
    applied_late = apply_venue_recovery_input(
        stale_status.book,
        stale_status.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("post-bust-late-fill-input"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=late_fill,
            evidence_digest=b"\xba" * 32,
            closure_id=ClosureId("post-bust-late-fill-closure"),
            evidence_reference=EvidenceReference("post-bust-late-fill-proof"),
        ),
    )

    assert applied_late.quantity_delta == 4
    assert applied_late.execution.position.raw_quantity == 4
    seen = applied_late.execution.seen_facts.get(late_fill.key)
    assert seen is not None
    assert seen.fact == late_fill
    assert applied_late.book._execution_matches(
        applied_late.execution,
        POSITION_SCOPE,
    )


def test_wo0146_red_active_bust_can_release_at_current_canonical_quantity() -> None:
    book, execution = _seed_needs_review(capacity=4)
    root_fill = _broker_fill(
        "active-release-root-source",
        "active-release-root",
        quantity=4,
    )
    filled = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("active-release-root-input"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=root_fill,
            evidence_digest=b"\xbb" * 32,
        ),
    )
    bust = BrokerTradeBustFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("active-release-bust-source"),
        ),
        scope=_execution_scope(),
        root_fill_id=root_fill.root_fill_id,
        predecessor_source_event_id=root_fill.key.source_event_id,
    )
    busted = apply_venue_recovery_input(
        filled.book,
        filled.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("active-release-bust-input"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_root_quantity=Quantity(4),
            prior_venue_cumulative_quantity=Quantity(4),
            resulting_venue_cumulative_quantity=Quantity(0),
            fact=bust,
            evidence_digest=b"\xbc" * 32,
        ),
    )
    assert busted.disposition is VenueRecoveryDisposition.APPLIED
    assert busted.quantity_delta == -4

    released = apply_venue_recovery_input(
        busted.book,
        busted.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("active-release-after-bust"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            claim_occurrence_id=CLAIM,
            venue_cumulative_quantity=Quantity(0),
            broker_terminal_state=VenueAttemptState.CANCELED,
            actor=ACTOR,
            reason="broker-authoritative bust leaves zero canonical coverage",
            evidence_reference=EVIDENCE,
            closure_id=ClosureId("active-release-after-bust-closure"),
            evidence_digest=b"\xbd" * 32,
        ),
    )

    assert released.disposition is VenueRecoveryDisposition.APPLIED
    assert released.quantity_delta == 0
    assert released.book.active_attempt(LEG_A) is None
    head = released.book.closure_head(LEG_A)
    assert head is not None
    assert head.cumulative_quantity == Quantity(0)


@pytest.mark.parametrize(
    ("changed_evidence", "expected_disposition", "expected_reconciliations"),
    [
        (False, VenueRecoveryDisposition.APPLIED, 0),
        (True, VenueRecoveryDisposition.RECONCILIATION_REQUIRED, 1),
    ],
    ids=("semantic-replay", "changed-evidence"),
)
def test_wo0146_red_active_revision_replay_is_classified_after_leg_closure(
    changed_evidence: bool,
    expected_disposition: VenueRecoveryDisposition,
    expected_reconciliations: int,
) -> None:
    book, execution = _seed_needs_review(capacity=4)
    root_fill = _broker_fill(
        "closed-replay-root-source",
        "closed-replay-root",
        quantity=4,
    )
    filled = apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("closed-replay-root-input"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=root_fill,
            evidence_digest=b"\xbe" * 32,
        ),
    )
    correction = BrokerTradeCorrectFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("closed-replay-correction-source"),
        ),
        scope=_execution_scope(),
        root_fill_id=root_fill.root_fill_id,
        predecessor_source_event_id=root_fill.key.source_event_id,
        revised_quantity=Quantity(4),
        revised_price=_price(101),
    )
    command = RecordBrokerRevisionEvidence(
        input_id=VenueInputId("closed-replay-correction-input"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_root_quantity=Quantity(4),
        prior_venue_cumulative_quantity=Quantity(4),
        resulting_venue_cumulative_quantity=Quantity(4),
        fact=correction,
        evidence_digest=b"\xbf" * 32,
    )
    corrected = apply_venue_recovery_input(
        filled.book,
        filled.execution,
        command,
    )
    assert corrected.disposition is VenueRecoveryDisposition.APPLIED
    released = apply_venue_recovery_input(
        corrected.book,
        corrected.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("closed-replay-release-input"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            claim_occurrence_id=CLAIM,
            venue_cumulative_quantity=Quantity(4),
            broker_terminal_state=VenueAttemptState.FILLED,
            actor=ACTOR,
            reason="close after an exact active-leg correction",
            evidence_reference=EVIDENCE,
            closure_id=ClosureId("closed-replay-release-closure"),
            evidence_digest=b"\xc0" * 32,
        ),
    )
    assert released.disposition is VenueRecoveryDisposition.APPLIED

    replay = replace(
        command,
        input_id=VenueInputId(
            "closed-replay-changed-input"
            if changed_evidence
            else "closed-replay-semantic-input"
        ),
        evidence_digest=b"\xc1" * 32 if changed_evidence else command.evidence_digest,
    )
    classified = apply_venue_recovery_input(
        released.book,
        released.execution,
        replay,
    )

    assert classified.disposition is expected_disposition
    assert classified.quantity_delta == 0
    assert classified.execution.position.raw_quantity == 4
    assert len(classified.book.reconciliations) == expected_reconciliations
    assert len(classified.book.closure_history) == 1


def _recovery_value_object_facts():
    fill = _broker_fill(
        "recovery-value-object-fill-source",
        "recovery-value-object-root",
        quantity=4,
    )
    correction = BrokerTradeCorrectFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("recovery-value-object-correct-source"),
        ),
        scope=fill.scope,
        root_fill_id=fill.root_fill_id,
        predecessor_source_event_id=fill.key.source_event_id,
        revised_quantity=Quantity(3),
        revised_price=_price(101),
    )
    bust = BrokerTradeBustFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("recovery-value-object-bust-source"),
        ),
        scope=fill.scope,
        root_fill_id=fill.root_fill_id,
        predecessor_source_event_id=fill.key.source_event_id,
    )
    return fill, correction, bust


def test_recovery_commands_reject_incomplete_evidence_and_invalid_equations() -> None:
    fill, correction, _ = _recovery_value_object_facts()
    release = ReleaseVenueLeg(
        input_id=VenueInputId("recovery-value-object-release"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        claim_occurrence_id=CLAIM,
        venue_cumulative_quantity=Quantity(4),
        broker_terminal_state=VenueAttemptState.FILLED,
        actor=ACTOR,
        reason="exact terminal evidence closes one reconciled leg",
        evidence_reference=EVIDENCE,
        closure_id=ClosureId("recovery-value-object-release-closure"),
        evidence_digest=b"\xd1" * 32,
    )
    for field_name, value, exception, message in (
        ("reason", 1, TypeError, "reason must be a string"),
        ("reason", " ", ValueError, "reason must be nonblank"),
        ("evidence_digest", "digest", TypeError, "evidence_digest must be bytes"),
        ("evidence_digest", b"short", ValueError, "exactly 32 bytes"),
    ):
        with pytest.raises(exception, match=message):
            replace(release, **{field_name: value})

    fill_command = RecordBrokerFillEvidence(
        input_id=VenueInputId("recovery-value-object-fill"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_cumulative_quantity=Quantity(0),
        resulting_cumulative_quantity=Quantity(4),
        fact=fill,
        evidence_digest=b"\xd2" * 32,
    )
    with pytest.raises(ValueError, match="supplied together"):
        replace(
            fill_command,
            closure_id=ClosureId("recovery-value-object-fill-closure"),
        )
    with pytest.raises(ValueError, match="supplied together"):
        replace(fill_command, evidence_reference=EVIDENCE)

    revision = RecordBrokerRevisionEvidence(
        input_id=VenueInputId("recovery-value-object-revision"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_root_quantity=Quantity(4),
        prior_venue_cumulative_quantity=Quantity(4),
        resulting_venue_cumulative_quantity=Quantity(3),
        fact=correction,
        evidence_digest=b"\xd3" * 32,
    )
    with pytest.raises(TypeError, match="BrokerTradeCorrectFact"):
        replace(revision, fact=fill)
    with pytest.raises(ValueError, match="supplied together"):
        replace(
            revision,
            closure_id=ClosureId("recovery-value-object-revision-closure"),
        )
    with pytest.raises(ValueError, match="resulting venue cumulative"):
        replace(revision, resulting_venue_cumulative_quantity=Quantity(2))
    with pytest.raises(ValueError, match="resulting venue cumulative"):
        replace(
            revision,
            prior_root_quantity=Quantity(5),
            prior_venue_cumulative_quantity=Quantity(4),
            resulting_venue_cumulative_quantity=Quantity(0),
        )


@pytest.mark.parametrize("revision_kind", ["correct", "bust"])
def test_revision_records_reject_fact_subclasses(revision_kind: str) -> None:
    fill, correction, bust = _recovery_value_object_facts()
    fact = correction if revision_kind == "correct" else bust
    subclass_type = type(f"{type(fact).__name__}Subclass", (type(fact),), {})
    subclass_fact = subclass_type(
        **{name: getattr(fact, name) for name in fact.__dataclass_fields__}
    )
    resulting_quantity = Quantity(3 if revision_kind == "correct" else 0)

    with pytest.raises(TypeError, match="exact|BrokerTradeCorrectFact"):
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId(f"subclass-{revision_kind}-revision"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_root_quantity=Quantity(4),
            prior_venue_cumulative_quantity=Quantity(4),
            resulting_venue_cumulative_quantity=resulting_quantity,
            fact=subclass_fact,
            evidence_digest=b"\xdc" * 32,
        )

    reconciliation = recovery_module.RevisionReconciliationRecord(
        input_id=VenueInputId(f"exact-{revision_kind}-reconciliation"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_root_quantity=Quantity(4),
        prior_venue_cumulative_quantity=Quantity(4),
        resulting_venue_cumulative_quantity=resulting_quantity,
        fact=fact,
        evidence_digest=b"\xdd" * 32,
        canonical_applied=False,
        reason="exact revision evidence remains quarantined",
    )
    with pytest.raises(TypeError, match="exact|BrokerTradeCorrectFact"):
        replace(reconciliation, fact=subclass_fact)

    coverage = recovery_module._BrokerCoverage(
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_cumulative_quantity=Quantity(0),
        resulting_cumulative_quantity=Quantity(4),
        fact=fill,
        evidence_digest=b"\xde" * 32,
        root_source_input_id=VenueInputId("exact-revision-root-input"),
        head_fact=fill,
        head_evidence_digest=b"\xdf" * 32,
        head_source_input_id=VenueInputId("exact-revision-head-input"),
    )
    with pytest.raises(TypeError, match="exact|canonical broker execution fact"):
        replace(coverage, head_fact=subclass_fact)


def test_recovery_coverage_records_reject_incomplete_or_cross_root_provenance() -> None:
    fill, correction, bust = _recovery_value_object_facts()
    human = recovery_module.HumanCoverage(
        effect_id=EFFECT,
        leg_key=LEG_A,
        fact=_human_fill(input_suffix="recovery-value-object-human"),
        source_input_id=VenueInputId("recovery-value-object-human-input"),
    )
    with pytest.raises(TypeError, match="broker_corroborated"):
        replace(human, broker_corroborated=1)
    with pytest.raises(ValueError, match="broker corroboration"):
        replace(human, broker_corroborated=True)
    with pytest.raises(ValueError, match="broker corroboration"):
        replace(human, broker_fact=fill)

    coverage = recovery_module._BrokerCoverage(
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_cumulative_quantity=Quantity(0),
        resulting_cumulative_quantity=Quantity(4),
        fact=fill,
        evidence_digest=b"\xd4" * 32,
        root_source_input_id=VenueInputId("recovery-value-object-root-input"),
        head_fact=fill,
        head_evidence_digest=b"\xd5" * 32,
        head_source_input_id=VenueInputId("recovery-value-object-head-input"),
    )
    with pytest.raises(TypeError, match="canonical broker execution fact"):
        replace(coverage, head_fact=object())
    with pytest.raises(TypeError, match="mapping_exact"):
        replace(coverage, mapping_exact=1)
    other_fill = _broker_fill(
        "recovery-value-object-other-source",
        "recovery-value-object-other-root",
        quantity=1,
    )
    with pytest.raises(ValueError, match="immutable root"):
        replace(coverage, head_fact=other_fill)

    reconciliation = recovery_module.RevisionReconciliationRecord(
        input_id=VenueInputId("recovery-value-object-reconciliation"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_root_quantity=Quantity(4),
        prior_venue_cumulative_quantity=Quantity(4),
        resulting_venue_cumulative_quantity=Quantity(3),
        fact=correction,
        evidence_digest=b"\xd6" * 32,
        canonical_applied=False,
        reason="the revision cannot be attributed without guessing",
    )
    with pytest.raises(TypeError, match="BrokerTradeCorrectFact"):
        replace(reconciliation, fact=fill)
    with pytest.raises(TypeError, match="canonical_applied"):
        replace(reconciliation, canonical_applied=1)

    assert recovery_module._revision_root_quantity(fill) == 4
    assert recovery_module._revision_root_quantity(correction) == 3
    assert recovery_module._revision_root_quantity(bust) == 0
