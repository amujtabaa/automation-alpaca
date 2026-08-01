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

from app.execution_core.fills import (
    BrokerFillFact,
    BrokerTradeBustFact,
    BrokerTradeCorrectFact,
    ExecutionAuthority,
    ExecutionScope,
    ExecutionSide,
    HumanAttestedFillFact,
    PositionScope,
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
    TransitionDisposition,
    apply_broker_execution_fact,
)
from app.execution_core.recovery import (
    IngestHumanAttestedFill,
    RecordBrokerFillEvidence,
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
    AcceptanceProofKind,
    AcceptanceSetState,
    BrokerEffectState,
    CloseAcceptanceSet,
    DiscoverVenueLeg,
    EffectKind,
    ObserveVenueStatus,
    RecordDispatchClaim,
    RecordTransportOutcome,
    RequestedEffect,
    VenueAttemptState,
    VenueClosureKind,
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    VenueScope,
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
    assert conflict.book == first.book


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
    book, _ = _seed_needs_review()

    with pytest.raises(ValueError, match="claim"):
        replace(book, claims=())


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
    broker_execution = _apply_broker(
        ExecutionSnapshot.flat(POSITION_SCOPE),
        _broker_fill(
            "known-broker-source",
            "known-broker-root",
            quantity=4,
            units=100,
        ),
    )
    book, execution = _seed_needs_review(execution=broker_execution)

    refused = _ingest(book, execution, _human_fill())

    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.quantity_delta == 0
    assert refused.book == book
    assert refused.execution == execution


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
    execution = _apply_broker(
        ExecutionSnapshot.flat(POSITION_SCOPE),
        _broker_fill(
            "prior-broker-sell",
            "prior-broker-sell-root",
            side=ExecutionSide.SELL,
            quantity=2,
        ),
    )
    assert execution.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    book, released, _ = _released_state(execution=execution)

    assert released.position.raw_quantity == 2
    assert released.integrity & PositionIntegrity.OVERFILL_QUARANTINE
    assert released.position.integrity_floor & PositionIntegrity.OVERFILL_QUARANTINE
    assert book.effect(EFFECT).acceptance_set_state is AcceptanceSetState.OPEN


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
            proof_kind=AcceptanceProofKind.COVERED_RECONCILIATION,
            evidence_reference=EvidenceReference("covered-parent-proof"),
        ),
    )

    assert closed.disposition is VenueRecoveryDisposition.APPLIED
    assert closed.book.effect(EFFECT).acceptance_set_state is AcceptanceSetState.CLOSED
    assert closed.book.effect(EFFECT).state is BrokerEffectState.OPERATOR_RECONCILED


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
        CloseAcceptanceSet(
            input_id=VenueInputId("invalidated-close"),
            effect_id=EFFECT,
            proof_kind=AcceptanceProofKind.COVERED_RECONCILIATION,
            evidence_reference=EvidenceReference("invalidated-close-proof"),
        ),
    )
    for item in setup:
        transition = apply_venue_recovery_input(book, execution, item)
        assert transition.disposition is VenueRecoveryDisposition.APPLIED
        book = transition.book

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


def test_disjoint_broker_interval_after_terminal_release_is_reconciliation_only() -> (
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
    )

    reconciled = apply_venue_recovery_input(book, execution, command)

    assert reconciled.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert reconciled.quantity_delta == 0
    assert reconciled.execution.position.raw_quantity == before_quantity
    assert reconciled.execution.root_heads == execution.root_heads
    assert (
        reconciled.execution.integrity
        & PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )


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
