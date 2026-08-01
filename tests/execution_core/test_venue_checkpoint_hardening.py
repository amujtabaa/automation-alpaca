"""Failure-first checkpoint capability and ordered-provenance hardening pins."""

from __future__ import annotations

from decimal import Decimal

import pytest

import app.execution_core.venue as venue_module
from app.execution_core.fills import (
    ExecutionFactKey,
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
    MandateId,
    OrderId,
    RequestOccurrenceId,
    RootFillId,
    SourceEventId,
    SymbolId,
    VenueInputId,
    VenueLegKey,
    VenueObservationId,
)
from app.execution_core.position import ExecutionSnapshot
from app.execution_core.recovery import IngestHumanAttestedFill, ReleaseVenueLeg
from app.execution_core.values import (
    PriceScale,
    PriceUnits,
    Quantity,
    ReportedPrice,
    TickMetadata,
)
from app.execution_core.venue import (
    BrokerEffectState,
    DiscoverVenueLeg,
    EffectKind,
    ObserveVenueStatus,
    RecordDispatchClaim,
    RecordTransportOutcome,
    RequestedEffect,
    VenueAttemptState,
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    VenueScope,
    apply_venue_recovery_input,
)


BROKER = BrokerId("alpaca")
ENVIRONMENT = EnvironmentId("paper")
ACCOUNT = AccountId("account-checkpoint-hardening")
GENERATION = ApplicationGenerationId("reset-generation-checkpoint-hardening")
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
EFFECT = EffectId("effect-checkpoint-hardening")
REQUEST = RequestOccurrenceId("request-checkpoint-hardening")
CLAIM = ClaimOccurrenceId("claim-checkpoint-hardening")
CLIENT = ClientOrderId("client-checkpoint-hardening")
MANDATE = MandateId("mandate-checkpoint-hardening")
LEG_A = VenueLegKey(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    order_id=OrderId("venue-checkpoint-leg-a"),
)
LEG_B = VenueLegKey(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    order_id=OrderId("venue-checkpoint-leg-b"),
)
ACTOR = ActorId("checkpoint-operator")
SCALE = PriceScale(Decimal("1"))
TICK = TickMetadata(tick_units=PriceUnits(1), scale=SCALE)


_BOUND_MUTATION_HELPERS = (
    "_evolve",
    "_record_input",
    "_evolve_with_input",
    "_evolve_with_input_and_execution",
    "_evolve_to_execution",
    "_replace_effect",
    "_replace_attempt",
    "_close_attempt",
    "_next_execution_bindings",
    "_append_coverage",
    "_replace_coverage",
    "_append_broker_coverage",
    "_append_reconciliation",
)


def _price(units: int = 100) -> ReportedPrice:
    return ReportedPrice(units=PriceUnits(units), scale=SCALE, tick=TICK)


def _execution_scope(leg_key: VenueLegKey) -> ExecutionScope:
    return ExecutionScope(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        order_id=leg_key.order_id,
        symbol_id=SYMBOL,
        side=ExecutionSide.BUY,
    )


def _human_fill(leg_key: VenueLegKey, suffix: str) -> HumanAttestedFillFact:
    return HumanAttestedFillFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId(f"human-source-{suffix}"),
        ),
        scope=_execution_scope(leg_key),
        root_fill_id=RootFillId(f"human-root-{suffix}"),
        leg_key=leg_key,
        request_occurrence_id=REQUEST,
        claim_occurrence_id=CLAIM,
        quantity=Quantity(4),
        prior_cumulative_quantity=Quantity(0),
        resulting_cumulative_quantity=Quantity(4),
        price=_price(),
        actor=ACTOR,
        reason="paper evidence proves one omitted execution",
        evidence_reference=EvidenceReference(f"human-evidence-{suffix}"),
    )


def _apply(book: VenueRecoveryBook, execution: ExecutionSnapshot, item: object):
    transition = apply_venue_recovery_input(book, execution, item)
    assert transition.disposition is VenueRecoveryDisposition.APPLIED
    return transition.book, transition.execution


def _seed_needs_review(
    *,
    effect_gate_first: bool,
    leg_keys: tuple[VenueLegKey, ...] = (LEG_A,),
) -> tuple[VenueRecoveryBook, ExecutionSnapshot]:
    book = VenueRecoveryBook.empty(VENUE_SCOPE)
    execution = ExecutionSnapshot.flat(POSITION_SCOPE)
    for item in (
        RequestedEffect(
            input_id=VenueInputId("request-checkpoint-effect"),
            effect_id=EFFECT,
            request_occurrence_id=REQUEST,
            mandate_id=MANDATE,
            kind=EffectKind.SUBMIT,
            client_order_id=CLIENT,
            symbol_id=SYMBOL,
            side=ExecutionSide.BUY,
            quantity=Quantity(10),
            economic_scope=b"AAPL|BUY|checkpoint-hardening",
        ),
        RecordDispatchClaim(
            input_id=VenueInputId("claim-checkpoint-effect"),
            effect_id=EFFECT,
            claim_occurrence_id=CLAIM,
        ),
        RecordTransportOutcome(
            input_id=VenueInputId("checkpoint-outcome-unknown"),
            effect_id=EFFECT,
            state=BrokerEffectState.OUTCOME_UNKNOWN,
        ),
    ):
        book, execution = _apply(book, execution, item)

    for index, leg_key in enumerate(leg_keys, start=1):
        book, execution = _apply(
            book,
            execution,
            DiscoverVenueLeg(
                input_id=VenueInputId(f"discover-checkpoint-leg-{index}"),
                effect_id=EFFECT,
                leg_key=leg_key,
                observation_id=VenueObservationId(
                    f"checkpoint-acceptance-observation-{index}"
                ),
            ),
        )

    effect_gate = RecordTransportOutcome(
        input_id=VenueInputId("checkpoint-effect-needs-review"),
        effect_id=EFFECT,
        state=BrokerEffectState.NEEDS_REVIEW,
    )
    leg_gates = tuple(
        ObserveVenueStatus(
            input_id=VenueInputId(f"checkpoint-leg-needs-review-{index}"),
            leg_key=leg_key,
            status=VenueAttemptState.NEEDS_REVIEW,
            observation_id=VenueObservationId(f"checkpoint-review-observation-{index}"),
            cumulative_quantity=Quantity(0),
        )
        for index, leg_key in enumerate(leg_keys, start=1)
    )
    ordered_gates = (
        (effect_gate, *leg_gates) if effect_gate_first else (*leg_gates, effect_gate)
    )
    for item in ordered_gates:
        book, execution = _apply(book, execution, item)
    return book, execution


def _ingest(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    fact: HumanAttestedFillFact,
    input_id: str,
):
    return apply_venue_recovery_input(
        book,
        execution,
        IngestHumanAttestedFill(
            input_id=VenueInputId(input_id),
            effect_id=EFFECT,
            fact=fact,
        ),
    )


def _released_state(
    *,
    target_leg: VenueLegKey = LEG_A,
    leg_keys: tuple[VenueLegKey, ...] = (LEG_A,),
    effect_gate_first: bool = False,
    suffix: str = "a",
):
    book, execution = _seed_needs_review(
        effect_gate_first=effect_gate_first,
        leg_keys=leg_keys,
    )
    fact = _human_fill(target_leg, suffix)
    ingested = _ingest(book, execution, fact, f"ingest-checkpoint-{suffix}")
    assert ingested.disposition is VenueRecoveryDisposition.APPLIED
    release = ReleaseVenueLeg(
        input_id=VenueInputId(f"release-checkpoint-{suffix}"),
        effect_id=EFFECT,
        leg_key=target_leg,
        claim_occurrence_id=CLAIM,
        venue_cumulative_quantity=Quantity(4),
        broker_terminal_state=VenueAttemptState.CANCELED,
        actor=ACTOR,
        reason="paper terminal report and exact checkpoint parity",
        evidence_reference=EvidenceReference(f"release-evidence-{suffix}"),
        closure_id=ClosureId(f"release-closure-{suffix}"),
        evidence_digest=bytes([0x40 + len(suffix)]) * 32,
    )
    released = apply_venue_recovery_input(
        ingested.book,
        ingested.execution,
        release,
    )
    assert released.disposition is VenueRecoveryDisposition.APPLIED
    return released.book, released.execution, fact, release


def _verified_internal_rebuild(
    book: VenueRecoveryBook,
    **changes: object,
) -> VenueRecoveryBook:
    rebuild = getattr(venue_module, "_rebuild_book", None)
    if rebuild is not None:
        assert callable(rebuild)
        return rebuild(book, **changes)

    legacy_rebuild = getattr(book, "_evolve", None)
    assert callable(legacy_rebuild), (
        "venue._rebuild_book must be the module-private verified rebuild path"
    )
    return legacy_rebuild(**changes)


def _move_record_before(
    records: tuple[object, ...],
    moving: object,
    anchor: object,
) -> tuple[object, ...]:
    reordered = list(records)
    reordered.remove(moving)
    reordered.insert(reordered.index(anchor), moving)
    return tuple(reordered)


@pytest.mark.parametrize("helper_name", _BOUND_MUTATION_HELPERS)
def test_checkpoint_exposes_no_bound_mutation_helpers(helper_name: str) -> None:
    book = VenueRecoveryBook.empty(VENUE_SCOPE)

    assert not hasattr(book, helper_name)


@pytest.mark.parametrize("effect_gate_first", [False, True])
def test_human_source_is_valid_after_both_gate_orderings(
    effect_gate_first: bool,
) -> None:
    book, execution = _seed_needs_review(effect_gate_first=effect_gate_first)

    ingested = _ingest(
        book,
        execution,
        _human_fill(LEG_A, f"positive-{effect_gate_first}"),
        f"ingest-positive-{effect_gate_first}",
    )

    assert ingested.disposition is VenueRecoveryDisposition.APPLIED
    assert ingested.quantity_delta == 4


def test_rebuild_rejects_first_human_source_before_effect_needs_review() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    ingested = _ingest(
        book,
        execution,
        _human_fill(LEG_A, "before-effect-gate"),
        "ingest-before-effect-gate",
    )
    assert ingested.disposition is VenueRecoveryDisposition.APPLIED
    human = next(
        record
        for record in ingested.book.input_records
        if isinstance(record.item, IngestHumanAttestedFill)
    )
    effect_gate = next(
        record
        for record in ingested.book.input_records
        if isinstance(record.item, RecordTransportOutcome)
        and record.item.state is BrokerEffectState.NEEDS_REVIEW
    )

    with pytest.raises(ValueError):
        _verified_internal_rebuild(
            ingested.book,
            input_records=_move_record_before(
                ingested.book.input_records,
                human,
                effect_gate,
            ),
        )


def test_rebuild_rejects_first_human_source_before_leg_needs_review() -> None:
    book, execution = _seed_needs_review(effect_gate_first=True)
    ingested = _ingest(
        book,
        execution,
        _human_fill(LEG_A, "before-leg-gate"),
        "ingest-before-leg-gate",
    )
    assert ingested.disposition is VenueRecoveryDisposition.APPLIED
    human = next(
        record
        for record in ingested.book.input_records
        if isinstance(record.item, IngestHumanAttestedFill)
    )
    leg_gate = next(
        record
        for record in ingested.book.input_records
        if isinstance(record.item, ObserveVenueStatus)
        and record.item.leg_key == LEG_A
        and record.item.status is VenueAttemptState.NEEDS_REVIEW
    )

    with pytest.raises(ValueError):
        _verified_internal_rebuild(
            ingested.book,
            input_records=_move_record_before(
                ingested.book.input_records,
                human,
                leg_gate,
            ),
        )


def test_rebuild_rejects_removed_leg_gate_from_released_checkpoint() -> None:
    book, _, _, _ = _released_state()
    retained = tuple(
        record
        for record in book.input_records
        if not (
            isinstance(record.item, ObserveVenueStatus)
            and record.item.leg_key == LEG_A
            and record.item.status is VenueAttemptState.NEEDS_REVIEW
        )
    )

    with pytest.raises(ValueError):
        _verified_internal_rebuild(book, input_records=retained)


def test_rebuild_rejects_first_human_source_moved_after_release() -> None:
    book, _, _, _ = _released_state()
    human = next(
        record
        for record in book.input_records
        if isinstance(record.item, IngestHumanAttestedFill)
    )
    release = next(
        record
        for record in book.input_records
        if isinstance(record.item, ReleaseVenueLeg)
    )
    reordered = list(book.input_records)
    reordered.remove(human)
    reordered.insert(reordered.index(release) + 1, human)

    with pytest.raises(ValueError):
        _verified_internal_rebuild(book, input_records=tuple(reordered))


def test_rebuild_rejects_sibling_leg_gate_substitution() -> None:
    book, _, _, _ = _released_state(
        target_leg=LEG_B,
        leg_keys=(LEG_A, LEG_B),
        suffix="b",
    )
    retained = tuple(
        record
        for record in book.input_records
        if not (
            isinstance(record.item, ObserveVenueStatus)
            and record.item.leg_key == LEG_B
            and record.item.status is VenueAttemptState.NEEDS_REVIEW
        )
    )
    assert any(
        isinstance(record.item, ObserveVenueStatus)
        and record.item.leg_key == LEG_A
        and record.item.status is VenueAttemptState.NEEDS_REVIEW
        for record in retained
    )

    with pytest.raises(ValueError):
        _verified_internal_rebuild(book, input_records=retained)


def test_exact_semantic_human_replay_after_release_remains_zero_economic() -> None:
    book, execution, fact, _ = _released_state()

    replayed = _ingest(
        book,
        execution,
        fact,
        "semantic-human-replay-after-release",
    )

    assert replayed.disposition is VenueRecoveryDisposition.APPLIED
    assert replayed.quantity_delta == 0
    assert replayed.execution == execution
    assert replayed.book.coverage_for_leg(LEG_A) == book.coverage_for_leg(LEG_A)
