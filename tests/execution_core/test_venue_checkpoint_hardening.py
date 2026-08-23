"""Failure-first checkpoint capability and ordered-provenance hardening pins."""

from __future__ import annotations

from copy import copy
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
import inspect
from unittest.mock import patch

import pytest

import app.execution_core.venue as venue_module
from app.execution_core.persistence import checkpoint_codec
from app.execution_core.fills import (
    BrokerFillFact,
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
from app.execution_core.recovery import (
    IngestHumanAttestedFill,
    RecordBrokerFillEvidence,
    ReleaseVenueLeg,
)
from app.execution_core.values import (
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
    BrokerEffect,
    BrokerEffectState,
    CancelBeforeDispatch,
    DiscoverVenueLeg,
    DispatchClaim,
    EffectKind,
    ObserveVenueStatus,
    PendingVenueOperation,
    RecordDispatchClaim,
    RecordTransportOutcome,
    RecoverClaimedEffect,
    RequestedEffect,
    VenueAttempt,
    VenueAttemptState,
    VenueEffectScope,
    VenueExecutionBinding,
    VenueIdentityOwner,
    VenueInputRecord,
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    VenueScope,
    _apply_venue_input,
    _audit_hydrate_book,
    apply_venue_recovery_input as _public_apply_venue_recovery_input,
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


def apply_venue_recovery_input(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
):
    reducer = (
        _apply_venue_input
        if type(item) in {RequestedEffect, RecordDispatchClaim, CancelBeforeDispatch}
        else _public_apply_venue_recovery_input
    )
    return reducer(book, execution, item)


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


def _broker_successor(
    *,
    input_suffix: str,
    closure_id: ClosureId,
) -> RecordBrokerFillEvidence:
    return RecordBrokerFillEvidence(
        input_id=VenueInputId(f"broker-successor-{input_suffix}"),
        effect_id=EFFECT,
        leg_key=LEG_A,
        prior_cumulative_quantity=Quantity(4),
        resulting_cumulative_quantity=Quantity(6),
        fact=BrokerFillFact(
            key=ExecutionFactKey(
                broker=BROKER,
                environment=ENVIRONMENT,
                account=ACCOUNT,
                source_event_id=SourceEventId(
                    f"broker-successor-source-{input_suffix}"
                ),
            ),
            scope=_execution_scope(LEG_A),
            root_fill_id=RootFillId(f"broker-successor-root-{input_suffix}"),
            quantity=Quantity(2),
            price=_price(),
        ),
        evidence_digest=b"\x72" * 32,
        closure_id=closure_id,
        evidence_reference=EvidenceReference(
            f"broker-successor-evidence-{input_suffix}"
        ),
    )


def _audit_history_trap(name: str) -> property:
    """Mutation tripwire: live reducers must use indexes, not slow audit views."""

    def fail(_book: VenueRecoveryBook) -> tuple[object, ...]:
        raise AssertionError(f"{name} audit history touched on a live transition")

    return property(fail)


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
    execution: ExecutionSnapshot,
    **changes: object,
) -> VenueRecoveryBook:
    return _audit_hydrate_book(book, execution, **changes)


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


def test_public_reducer_rejects_command_subclasses_before_property_access() -> None:
    request = RequestedEffect(
        input_id=VenueInputId("delayed-command-request"),
        effect_id=EffectId("delayed-command-effect"),
        request_occurrence_id=RequestOccurrenceId("delayed-command-occurrence"),
        mandate_id=MandateId("delayed-command-mandate"),
        kind=EffectKind.SUBMIT,
        client_order_id=ClientOrderId("delayed-command-client"),
        symbol_id=SYMBOL,
        side=ExecutionSide.BUY,
        quantity=Quantity(1),
        economic_scope=b"AAPL|BUY|delayed-command",
    )

    class DelayedRequestedEffect(RequestedEffect):
        trap_reads = False

        def __getattribute__(self, name: str) -> object:
            if name == "input_id" and type(self).trap_reads:
                raise AssertionError("input_id read before exact command type check")
            return super().__getattribute__(name)

    delayed = DelayedRequestedEffect(
        **{name: getattr(request, name) for name in request.__dataclass_fields__}
    )
    DelayedRequestedEffect.trap_reads = True

    with pytest.raises(TypeError, match="exact venue-recovery command type"):
        apply_venue_recovery_input(
            VenueRecoveryBook.empty(VENUE_SCOPE),
            ExecutionSnapshot.flat(POSITION_SCOPE),
            delayed,
        )


def test_audit_hydration_rejects_a_delayed_broker_effect_subclass() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    [effect] = book.effects

    class DelayedBrokerEffect(BrokerEffect):
        reported_scope = effect.scope

        def __getattribute__(self, name: str) -> object:
            if name == "scope":
                return type(self).reported_scope
            return super().__getattribute__(name)

    delayed = DelayedBrokerEffect(
        scope=effect.scope,
        state=effect.state,
        acceptance_set_state=effect.acceptance_set_state,
        claim_occurrence_id=effect.claim_occurrence_id,
        acceptance_proof=effect.acceptance_proof,
        contradiction_evidence=effect.contradiction_evidence,
    )

    with pytest.raises(TypeError, match=r"effect (?:append|entries)"):
        _audit_hydrate_book(book, execution, effects=(delayed,))


def test_retained_edges_reject_delayed_effect_scope_subclasses() -> None:
    book, _ = _seed_needs_review(effect_gate_first=False)
    [effect] = book.effects
    [owner] = book.owners

    class DelayedVenueEffectScope(VenueEffectScope):
        pass

    scope = effect.scope
    delayed_scope = DelayedVenueEffectScope(
        generation=scope.generation,
        broker=scope.broker,
        environment=scope.environment,
        account=scope.account,
        effect_id=scope.effect_id,
        request_occurrence_id=scope.request_occurrence_id,
        mandate_id=scope.mandate_id,
        kind=scope.kind,
        client_order_id=scope.client_order_id,
        symbol_id=scope.symbol_id,
        side=scope.side,
        quantity=scope.quantity,
        economic_scope=scope.economic_scope,
    )

    with pytest.raises(TypeError, match="effect_scope"):
        DispatchClaim(
            effect_scope=delayed_scope,
            claim_occurrence_id=CLAIM,
        )
    with pytest.raises(TypeError, match="effect_scope"):
        VenueIdentityOwner(
            leg_key=owner.leg_key,
            effect_scope=delayed_scope,
            observation_id=owner.observation_id,
        )


def test_hydration_rejects_binding_subclasses_before_property_access() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    [binding] = book.execution_bindings

    class DelayedVenueExecutionBinding(VenueExecutionBinding):
        trap_reads = False

        def __getattribute__(self, name: str) -> object:
            if name == "position_scope" and type(self).trap_reads:
                raise AssertionError("binding scope read before exact type check")
            return super().__getattribute__(name)

    delayed = DelayedVenueExecutionBinding(
        position_scope=binding.position_scope,
        position_commitment=binding.position_commitment,
        root_heads_commitment=binding.root_heads_commitment,
        integrity_bits=binding.integrity_bits,
    )
    DelayedVenueExecutionBinding.trap_reads = True

    with pytest.raises(TypeError, match="execution binding"):
        _audit_hydrate_book(book, execution, execution_bindings=(delayed,))


def test_hydration_validates_input_identity_before_hashing_or_value_access() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    [first, *remaining] = book.input_records

    class DelayedVenueInputId(VenueInputId):
        trap_reads = False

        def __getattribute__(self, name: str) -> object:
            if name == "value" and type(self).trap_reads:
                raise AssertionError("input identity read before exact type check")
            return super().__getattribute__(name)

    delayed_input_id = DelayedVenueInputId(first.input_id.value)
    DelayedVenueInputId.trap_reads = True
    delayed_record = VenueInputRecord(
        input_id=delayed_input_id,
        item=first.item,
        semantic_alias_of=first.semantic_alias_of,
    )

    with pytest.raises(TypeError, match="input record.input_id"):
        _audit_hydrate_book(
            book,
            execution,
            input_records=(delayed_record, *remaining),
        )


def test_hydration_validates_attempt_quantity_before_commitment_access() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    [attempt] = book.active_attempts

    class DelayedQuantity(Quantity):
        trap_reads = False

        def __getattribute__(self, name: str) -> object:
            if name == "value" and type(self).trap_reads:
                raise AssertionError("attempt quantity read before exact type check")
            return super().__getattribute__(name)

    delayed_quantity = DelayedQuantity(attempt.cumulative_quantity.value)
    DelayedQuantity.trap_reads = True
    delayed_attempt = VenueAttempt(
        leg_key=attempt.leg_key,
        status=attempt.status,
        pending_operation=attempt.pending_operation,
        cumulative_quantity=delayed_quantity,
        last_observation_id=attempt.last_observation_id,
    )

    with pytest.raises(TypeError, match="attempt.cumulative_quantity"):
        _audit_hydrate_book(book, execution, active_attempts=(delayed_attempt,))


def test_hydration_validates_closure_identity_before_indexing() -> None:
    book, execution, _, _ = _released_state()
    [closure] = book.closure_history

    class DelayedClosureId(ClosureId):
        trap_reads = False

        def __getattribute__(self, name: str) -> object:
            if name == "value" and type(self).trap_reads:
                raise AssertionError("closure identity read before exact type check")
            return super().__getattribute__(name)

    delayed_closure_id = DelayedClosureId(closure.closure_id.value)
    DelayedClosureId.trap_reads = True
    delayed_closure = replace(
        closure,
        closure_id=delayed_closure_id,
    )

    with pytest.raises(TypeError, match="closure.closure_id"):
        _audit_hydrate_book(
            book,
            execution,
            closure_heads=(delayed_closure,),
            closure_history=(delayed_closure,),
        )


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
            ingested.execution,
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
            ingested.execution,
            input_records=_move_record_before(
                ingested.book.input_records,
                human,
                leg_gate,
            ),
        )


def test_rebuild_rejects_removed_leg_gate_from_released_checkpoint() -> None:
    book, execution, _, _ = _released_state()
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
        _verified_internal_rebuild(book, execution, input_records=retained)


def test_rebuild_rejects_first_human_source_moved_after_release() -> None:
    book, execution, _, _ = _released_state()
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
        _verified_internal_rebuild(
            book,
            execution,
            input_records=tuple(reordered),
        )


def test_rebuild_rejects_sibling_leg_gate_substitution() -> None:
    book, execution, _, _ = _released_state(
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
        _verified_internal_rebuild(book, execution, input_records=retained)


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


@pytest.mark.parametrize("audit_name", ["closure_history", "input_records"])
def test_ordinary_transition_does_not_touch_audit_history(audit_name: str) -> None:
    book, execution, fact, _ = _released_state()

    with patch.object(
        VenueRecoveryBook,
        audit_name,
        _audit_history_trap(audit_name),
    ):
        replayed = _ingest(
            book,
            execution,
            fact,
            f"bounded-ordinary-replay-{audit_name}",
        )

    assert replayed.disposition is VenueRecoveryDisposition.APPLIED
    assert replayed.quantity_delta == 0
    assert replayed.execution == execution


def test_terminal_successor_append_uses_indexed_head_without_audit_history() -> None:
    book, execution, _, release = _released_state()
    successor_id = ClosureId("indexed-terminal-successor")

    with patch.object(
        VenueRecoveryBook,
        "closure_history",
        _audit_history_trap("closure_history"),
    ):
        successor = apply_venue_recovery_input(
            book,
            execution,
            _broker_successor(
                input_suffix="indexed-append",
                closure_id=successor_id,
            ),
        )

    assert successor.disposition is VenueRecoveryDisposition.APPLIED
    head = successor.book.closure_head(LEG_A)
    assert head is not None
    assert head.closure_id == successor_id
    assert head.ordinal == 2
    assert head.predecessor_closure_id == release.closure_id


def test_terminal_successor_duplicate_uses_index_without_audit_history() -> None:
    book, execution, _, release = _released_state()

    with (
        patch.object(
            VenueRecoveryBook,
            "closure_history",
            _audit_history_trap("closure_history"),
        ),
        pytest.raises(ValueError, match="closure identity already exists"),
    ):
        apply_venue_recovery_input(
            book,
            execution,
            _broker_successor(
                input_suffix="indexed-duplicate",
                closure_id=release.closure_id,
            ),
        )


def test_explicit_slow_audit_views_materialize_terminal_and_input_history() -> None:
    book, _, _, release = _released_state()

    closure_audit = tuple(book.closure_history)
    input_audit = tuple(book.input_records)

    assert [closure.closure_id for closure in closure_audit] == [release.closure_id]
    assert any(
        isinstance(record.item, ReleaseVenueLeg) and record.input_id == release.input_id
        for record in input_audit
    )


@pytest.mark.parametrize(
    ("scope_changes", "message"),
    [
        (
            {"account": AccountId("different-paper-account")},
            "effect scope must match the exact book scope",
        ),
        (
            {"quantity": Quantity(0)},
            "effect scope quantity must be positive",
        ),
        (
            {"economic_scope": b""},
            "effect scope economic_scope must be nonempty bytes",
        ),
    ],
)
def test_audit_rejects_invalid_effect_scope(
    scope_changes: dict[str, object],
    message: str,
) -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    effect = book.effects[0]
    corrupted = replace(
        effect,
        scope=replace(effect.scope, **scope_changes),
    )

    with pytest.raises(ValueError, match=message):
        _verified_internal_rebuild(book, execution, effects=(corrupted,))


def test_audit_rejects_effect_state_without_complete_lifecycle_provenance() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    corrupted = replace(book.effects[0], state=BrokerEffectState.ACKNOWLEDGED)

    with pytest.raises(
        ValueError,
        match="effect state requires complete lifecycle input provenance",
    ):
        _verified_internal_rebuild(book, execution, effects=(corrupted,))


def test_audit_rejects_claim_detached_from_canonical_effect_scope() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    claim = book.claims[0]
    corrupted = replace(
        claim,
        effect_scope=replace(claim.effect_scope, economic_scope=b"detached-claim"),
    )

    with pytest.raises(
        ValueError,
        match="claim must bind the registered canonical effect scope",
    ):
        _verified_internal_rebuild(book, execution, claims=(corrupted,))


def test_audit_rejects_owner_detached_from_canonical_effect_scope() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    owner = book.owners[0]
    corrupted = replace(
        owner,
        effect_scope=replace(owner.effect_scope, economic_scope=b"detached-owner"),
    )

    with pytest.raises(
        ValueError,
        match="owner must bind the canonical registered effect scope",
    ):
        _verified_internal_rebuild(book, execution, owners=(corrupted,))


@pytest.mark.parametrize(
    ("attempt_changes", "message"),
    [
        (
            {"status": VenueAttemptState.CANCELED},
            "active attempt cannot carry a terminal status",
        ),
        (
            {"pending_operation": PendingVenueOperation.NONE},
            "pending operation absence must be None",
        ),
        (
            {"last_observation_id": VenueObservationId("unproven-current-observation")},
            "active attempt requires exact observation and pending provenance",
        ),
    ],
)
def test_audit_rejects_invalid_or_unproven_active_attempt(
    attempt_changes: dict[str, object],
    message: str,
) -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    corrupted = replace(book.active_attempts[0], **attempt_changes)

    with pytest.raises(ValueError, match=message):
        _verified_internal_rebuild(
            book,
            execution,
            active_attempts=(corrupted,),
        )


@pytest.mark.parametrize(
    ("closure_changes", "message"),
    [
        (
            {"ordinal": 0},
            "closure ordinal must be a positive integer",
        ),
        (
            {"reason": "  "},
            "operator closure must carry an external broker terminal state",
        ),
        (
            {"evidence_digest": b"short"},
            "closure.evidence_digest must contain exactly 32 bytes",
        ),
    ],
)
def test_audit_rejects_invalid_terminal_closure(
    closure_changes: dict[str, object],
    message: str,
) -> None:
    book, execution, _, _ = _released_state()
    corrupted = replace(book.closure_history[0], **closure_changes)

    with pytest.raises(ValueError, match=message):
        _verified_internal_rebuild(
            book,
            execution,
            closure_history=(corrupted,),
            closure_heads=(corrupted,),
        )


def test_audit_rejects_closure_without_exact_source_input_provenance() -> None:
    book, execution, _, _ = _released_state()
    corrupted = replace(
        book.closure_history[0],
        evidence_reference=EvidenceReference("unproven-closure-evidence"),
    )

    with pytest.raises(
        ValueError,
        match="closure requires exact source-input provenance",
    ):
        _verified_internal_rebuild(
            book,
            execution,
            closure_history=(corrupted,),
            closure_heads=(corrupted,),
        )


@pytest.mark.parametrize(
    ("removed_type", "message"),
    [
        (
            RequestedEffect,
            "effect requires requested-effect input provenance",
        ),
        (
            RecordDispatchClaim,
            "claim edge requires dispatch-claim input provenance",
        ),
        (
            DiscoverVenueLeg,
            "owner edge requires leg-discovery input provenance",
        ),
    ],
)
def test_audit_rejects_missing_lifecycle_input_provenance(
    removed_type: type[object],
    message: str,
) -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    retained = tuple(
        record
        for record in book.input_records
        if not isinstance(record.item, removed_type)
    )

    with pytest.raises(ValueError, match=message):
        _verified_internal_rebuild(book, execution, input_records=retained)


def test_audit_rejects_claim_ordered_before_its_requested_predecessor() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    request = next(
        record
        for record in book.input_records
        if isinstance(record.item, RequestedEffect)
    )
    claim = next(
        record
        for record in book.input_records
        if isinstance(record.item, RecordDispatchClaim)
    )

    with pytest.raises(
        ValueError,
        match="claim lifecycle input has no requested predecessor",
    ):
        _verified_internal_rebuild(
            book,
            execution,
            input_records=_move_record_before(book.input_records, claim, request),
        )


def test_audit_rejects_input_record_identity_detached_from_item() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    original = book.input_records[0]
    corrupted = replace(
        original,
        input_id=VenueInputId("detached-input-record-identity"),
    )

    with pytest.raises(
        ValueError,
        match="input record identity must match its immutable item",
    ):
        _verified_internal_rebuild(
            book,
            execution,
            input_records=(corrupted, *book.input_records[1:]),
        )


def test_audit_rejects_semantic_alias_without_earlier_direct_source() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    original = book.input_records[0]
    corrupted = replace(
        original,
        semantic_alias_of=VenueInputId("missing-direct-semantic-source"),
    )

    with pytest.raises(
        ValueError,
        match="semantic input alias requires an earlier direct source",
    ):
        _verified_internal_rebuild(
            book,
            execution,
            input_records=(corrupted, *book.input_records[1:]),
        )


@pytest.mark.parametrize(
    ("changes", "exception", "message"),
    [
        (
            {"execution_registry_count": True},
            ValueError,
            "execution_registry_count",
        ),
        (
            {"execution_registry_count": -1},
            ValueError,
            "execution_registry_count",
        ),
        (
            {"execution_registry_commitment": b"short"},
            ValueError,
            "execution_registry_commitment",
        ),
        (
            {
                "execution_registry_count": None,
                "execution_registry_commitment": b"\x01" * 32,
            },
            ValueError,
            "retained together",
        ),
        (
            {"execution_bindings": ()},
            ValueError,
            "every effect symbol requires exactly one",
        ),
        (
            {"active_attempts": ()},
            ValueError,
            "one active attempt or closure head",
        ),
        (
            {"execution_reconciliations": (object(),)},
            TypeError,
            "execution reconciliation entries",
        ),
        (
            {"reconciliations": (object(),)},
            TypeError,
            "typed reconciliation record",
        ),
        (
            {"effects": (object(),)},
            TypeError,
            "effect append must be BrokerEffect",
        ),
    ],
)
def test_audit_rejects_registry_and_entry_shape_corruption(
    changes: dict[str, object],
    exception: type[Exception],
    message: str,
) -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)

    with pytest.raises(exception, match=message):
        _verified_internal_rebuild(book, execution, **changes)


def test_audit_rejects_orphan_and_negative_active_attempts() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    attempt = book.active_attempts[0]

    with pytest.raises(ValueError, match="require retained owners"):
        _verified_internal_rebuild(
            book,
            execution,
            active_attempts=(replace(attempt, leg_key=LEG_B),),
        )

    negative = object.__new__(Quantity)
    object.__setattr__(negative, "value", -1)
    with pytest.raises(ValueError, match="cannot be negative"):
        _verified_internal_rebuild(
            book,
            execution,
            active_attempts=(replace(attempt, cumulative_quantity=negative),),
        )


def test_audit_rejects_terminal_history_gaps_branches_and_active_coexistence() -> None:
    released, execution, _, _ = _released_state()
    [closure] = released.closure_history

    with pytest.raises(ValueError, match="current closure history heads"):
        _verified_internal_rebuild(
            released,
            execution,
            closure_heads=(),
        )

    active_book, _ = _seed_needs_review(effect_gate_first=False)
    with pytest.raises(ValueError, match="cannot coexist with an active attempt"):
        _verified_internal_rebuild(
            released,
            execution,
            active_attempts=active_book.active_attempts,
        )

    ordinal_gap = replace(closure, ordinal=2)
    with pytest.raises(ValueError, match="ordinals must be contiguous"):
        _verified_internal_rebuild(
            released,
            execution,
            closure_history=(ordinal_gap,),
            closure_heads=(ordinal_gap,),
        )

    wrong_predecessor = replace(
        closure,
        predecessor_closure_id=ClosureId("unrelated-predecessor"),
    )
    with pytest.raises(ValueError, match="immediate predecessor"):
        _verified_internal_rebuild(
            released,
            execution,
            closure_history=(wrong_predecessor,),
            closure_heads=(wrong_predecessor,),
        )

    advanced = apply_venue_recovery_input(
        released,
        execution,
        _broker_successor(
            input_suffix="audit-chain",
            closure_id=ClosureId("audit-chain-successor"),
        ),
    )
    assert advanced.disposition is VenueRecoveryDisposition.APPLIED
    first, second = advanced.book.closure_history
    economic_root = replace(second, ordinal=1, predecessor_closure_id=None)
    with pytest.raises(ValueError, match="must succeed a terminal closure"):
        _verified_internal_rebuild(
            advanced.book,
            advanced.execution,
            closure_history=(economic_root,),
            closure_heads=(economic_root,),
        )

    changed_terminal = replace(second, status=VenueAttemptState.CANCELED)
    with pytest.raises(ValueError, match="preserve terminal identity"):
        _verified_internal_rebuild(
            advanced.book,
            advanced.execution,
            closure_history=(first, changed_terminal),
            closure_heads=(changed_terminal,),
        )


def test_audit_rejects_duplicate_and_reordered_lifecycle_inputs() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    request_record = next(
        record
        for record in book.input_records
        if isinstance(record.item, RequestedEffect)
    )
    claim_record = next(
        record
        for record in book.input_records
        if isinstance(record.item, RecordDispatchClaim)
    )
    discovery_record = next(
        record
        for record in book.input_records
        if isinstance(record.item, DiscoverVenueLeg)
    )
    review_record = next(
        record
        for record in book.input_records
        if isinstance(record.item, ObserveVenueStatus)
    )

    changed_request = replace(
        request_record.item,
        economic_scope=b"changed-request-scope",
    )
    with pytest.raises(ValueError, match="requested-effect input provenance"):
        _verified_internal_rebuild(
            book,
            execution,
            input_records=(
                replace(request_record, item=changed_request),
                *book.input_records[1:],
            ),
        )

    changed_claim = replace(
        claim_record.item,
        claim_occurrence_id=ClaimOccurrenceId("changed-claim-occurrence"),
    )
    with pytest.raises(ValueError, match="dispatch-claim input provenance"):
        _verified_internal_rebuild(
            book,
            execution,
            input_records=tuple(
                replace(record, item=changed_claim)
                if record is claim_record
                else record
                for record in book.input_records
            ),
        )

    duplicate_request = replace(
        request_record.item,
        input_id=VenueInputId("duplicate-request-input"),
    )
    duplicate_record = replace(
        request_record,
        input_id=duplicate_request.input_id,
        item=duplicate_request,
    )
    with pytest.raises(ValueError, match="duplicate direct semantic input"):
        _verified_internal_rebuild(
            book,
            execution,
            input_records=(request_record, duplicate_record, *book.input_records[1:]),
        )

    with pytest.raises(ValueError, match="observation precedes leg discovery"):
        _verified_internal_rebuild(
            book,
            execution,
            input_records=_move_record_before(
                book.input_records,
                review_record,
                discovery_record,
            ),
        )

    regressed_item = replace(
        review_record.item,
        input_id=VenueInputId("regressed-working-observation"),
        status=VenueAttemptState.WORKING,
        observation_id=VenueObservationId("regressed-working-observation"),
    )
    regressed_record = replace(
        review_record,
        input_id=regressed_item.input_id,
        item=regressed_item,
    )
    with pytest.raises(ValueError, match="status history cannot regress"):
        _verified_internal_rebuild(
            book,
            execution,
            input_records=(*book.input_records, regressed_record),
        )


def _corroborated_human_state():
    book, execution = _seed_needs_review(effect_gate_first=False)
    human_fact = _human_fill(LEG_A, "audit-corroboration")
    attested = _ingest(
        book,
        execution,
        human_fact,
        "audit-corroboration-human-input",
    )
    assert attested.disposition is VenueRecoveryDisposition.APPLIED
    broker_fact = BrokerFillFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("audit-corroboration-broker-source"),
        ),
        scope=human_fact.scope,
        root_fill_id=RootFillId("audit-corroboration-broker-root"),
        quantity=human_fact.quantity,
        price=human_fact.price,
    )
    corroborated = apply_venue_recovery_input(
        attested.book,
        attested.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("audit-corroboration-broker-input"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=broker_fact,
            evidence_digest=b"\xe1" * 32,
        ),
    )
    assert corroborated.disposition is VenueRecoveryDisposition.APPLIED
    released = apply_venue_recovery_input(
        corroborated.book,
        corroborated.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("audit-corroboration-release-input"),
            effect_id=EFFECT,
            leg_key=LEG_A,
            claim_occurrence_id=CLAIM,
            venue_cumulative_quantity=Quantity(4),
            broker_terminal_state=VenueAttemptState.CANCELED,
            actor=ACTOR,
            reason="exact corroborated economics and terminal broker evidence",
            evidence_reference=EvidenceReference("audit-corroboration-release"),
            closure_id=ClosureId("audit-corroboration-release-closure"),
            evidence_digest=b"\xe2" * 32,
        ),
    )
    assert released.disposition is VenueRecoveryDisposition.APPLIED
    return released.book, released.execution


def test_audit_rejects_corrupted_human_coverage_authority_and_provenance() -> None:
    book, execution = _corroborated_human_state()
    [coverage] = book.human_coverages

    cases = (
        (
            replace(coverage, effect_id=EffectId("missing-coverage-effect")),
            "owned canonical effect",
        ),
        (
            replace(
                coverage,
                fact=replace(
                    coverage.fact,
                    scope=replace(
                        coverage.fact.scope,
                        symbol_id=SymbolId("MSFT"),
                    ),
                ),
            ),
            "owner economic scope",
        ),
        (
            replace(
                coverage,
                fact=replace(
                    coverage.fact,
                    quantity=Quantity(11),
                    resulting_cumulative_quantity=Quantity(11),
                ),
            ),
            "cannot exceed immutable effect capacity",
        ),
        (
            replace(
                coverage,
                fact=replace(
                    coverage.fact,
                    claim_occurrence_id=ClaimOccurrenceId("wrong-coverage-claim"),
                ),
            ),
            "exact claim occurrence",
        ),
        (
            replace(
                coverage,
                source_input_id=VenueInputId("missing-human-source-input"),
            ),
            "prior ordered review authority",
        ),
        (
            replace(
                coverage,
                broker_fact=replace(coverage.broker_fact, price=_price(101)),
            ),
            "match committed human economics",
        ),
        (
            replace(
                coverage,
                broker_source_input_id=VenueInputId("missing-broker-source-input"),
            ),
            "exact source-input provenance",
        ),
    )
    for corrupted, message in cases:
        with pytest.raises(ValueError, match=message):
            _verified_internal_rebuild(
                book,
                execution,
                human_coverages=(corrupted,),
            )


def _acceptance_proof_for_effect(effect, kind: AcceptanceProofKind):
    return AcceptanceProof(
        kind=kind,
        effect_scope=effect.scope,
        claim_occurrence_id=(
            None if kind is AcceptanceProofKind.NEVER_DISPATCHED else CLAIM
        ),
        evidence_reference=EvidenceReference(
            f"checkpoint-edge-proof-{kind.value.lower()}"
        ),
        evidence_digest=b"\xf1" * 32,
    )


def test_acceptance_proof_constructor_rejects_claim_kind_mismatch() -> None:
    book, _ = _seed_needs_review(effect_gate_first=False)
    effect = book.effects[0]
    external = _acceptance_proof_for_effect(
        effect,
        AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
    )

    with pytest.raises(ValueError, match="never-dispatched proof cannot name a claim"):
        replace(external, kind=AcceptanceProofKind.NEVER_DISPATCHED)
    with pytest.raises(ValueError, match="external completeness proof must name"):
        AcceptanceProof(
            kind=AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
            effect_scope=effect.scope,
            claim_occurrence_id=None,
            evidence_reference=external.evidence_reference,
            evidence_digest=external.evidence_digest,
        )


def test_effect_edge_validator_rejects_claim_and_acceptance_contradictions() -> None:
    book, _ = _seed_needs_review(effect_gate_first=False)
    effect = book.effects[0]
    claim = book.claims[0]
    owner = book.owners[0]
    effects = {EFFECT: effect}
    claims = {EFFECT: claim}
    owners = {LEG_A: owner}
    external = _acceptance_proof_for_effect(
        effect,
        AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
    )

    book._validate_effect_edges(effects, claims, owners, {})

    with pytest.raises(ValueError, match="state and immutable claim edge disagree"):
        book._validate_effect_edges(
            {EFFECT: replace(effect, state=BrokerEffectState.REQUESTED)},
            claims,
            owners,
            {},
        )
    with pytest.raises(ValueError, match="exactly one claim record"):
        book._validate_effect_edges(effects, {}, owners, {})
    with pytest.raises(ValueError, match="match the effect claim occurrence"):
        book._validate_effect_edges(
            effects,
            {
                EFFECT: replace(
                    claim,
                    claim_occurrence_id=ClaimOccurrenceId(
                        "checkpoint-edge-wrong-claim"
                    ),
                )
            },
            owners,
            {},
        )
    with pytest.raises(ValueError, match="open acceptance set cannot carry proof"):
        book._validate_effect_edges(
            {EFFECT: replace(effect, acceptance_proof=external)},
            claims,
            owners,
            {},
        )
    with pytest.raises(ValueError, match="requires proof"):
        book._validate_effect_edges(
            {
                EFFECT: replace(
                    effect,
                    acceptance_set_state=AcceptanceSetState.CLOSED,
                )
            },
            claims,
            owners,
            {},
        )
    with pytest.raises(ValueError, match="bind exact effect scope and claim"):
        book._validate_effect_edges(
            {
                EFFECT: replace(
                    effect,
                    acceptance_set_state=AcceptanceSetState.CLOSED,
                    acceptance_proof=replace(
                        external,
                        effect_scope=replace(
                            external.effect_scope,
                            economic_scope=b"checkpoint-edge-wrong-scope",
                        ),
                    ),
                )
            },
            claims,
            owners,
            {},
        )

    never_dispatched = _acceptance_proof_for_effect(
        effect,
        AcceptanceProofKind.NEVER_DISPATCHED,
    )
    with pytest.raises(ValueError, match="requires local cancellation"):
        book._validate_effect_edges(
            {
                EFFECT: replace(
                    effect,
                    state=BrokerEffectState.REQUESTED,
                    claim_occurrence_id=None,
                    acceptance_set_state=AcceptanceSetState.CLOSED,
                    acceptance_proof=never_dispatched,
                )
            },
            {},
            owners,
            {},
        )

    forged_external = object.__new__(AcceptanceProof)
    for name, value in (
        ("kind", AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE),
        ("effect_scope", effect.scope),
        ("claim_occurrence_id", None),
        ("evidence_reference", external.evidence_reference),
        ("evidence_digest", external.evidence_digest),
    ):
        object.__setattr__(forged_external, name, value)
    with pytest.raises(ValueError, match="requires an immutable claim"):
        book._validate_effect_edges(
            {
                EFFECT: replace(
                    effect,
                    state=BrokerEffectState.CANCELED_BEFORE_DISPATCH,
                    claim_occurrence_id=None,
                    acceptance_set_state=AcceptanceSetState.CLOSED,
                    acceptance_proof=forged_external,
                )
            },
            {},
            owners,
            {},
        )

    with pytest.raises(ValueError, match="requires contradiction evidence"):
        book._validate_effect_edges(
            {
                EFFECT: replace(
                    effect,
                    acceptance_set_state=AcceptanceSetState.INVALIDATED,
                    acceptance_proof=external,
                )
            },
            claims,
            owners,
            {},
        )
    wrong_owner = AcceptanceContradiction(
        leg_key=LEG_B,
        observation_id=VenueObservationId("checkpoint-edge-wrong-owner"),
    )
    with pytest.raises(ValueError, match="owned leg of its effect"):
        book._validate_effect_edges(
            {
                EFFECT: replace(
                    effect,
                    acceptance_set_state=AcceptanceSetState.INVALIDATED,
                    acceptance_proof=external,
                    contradiction_evidence=(wrong_owner,),
                )
            },
            claims,
            owners,
            {},
        )
    wrong_observation = AcceptanceContradiction(
        leg_key=LEG_A,
        observation_id=VenueObservationId("checkpoint-edge-wrong-observation"),
    )
    with pytest.raises(ValueError, match="owner observation"):
        book._validate_effect_edges(
            {
                EFFECT: replace(
                    effect,
                    acceptance_set_state=AcceptanceSetState.INVALIDATED,
                    acceptance_proof=external,
                    contradiction_evidence=(wrong_observation,),
                )
            },
            claims,
            owners,
            {},
        )


def test_operator_reconciled_edge_requires_closed_complete_clean_legs() -> None:
    book, _, _, _ = _released_state()
    effect = book.effects[0]
    claim = book.claims[0]
    owner = book.owners[0]
    head = book.closure_heads[0]
    proof = _acceptance_proof_for_effect(
        effect,
        AcceptanceProofKind.COVERED_RECONCILIATION,
    )
    operator = replace(
        effect,
        state=BrokerEffectState.OPERATOR_RECONCILED,
        acceptance_set_state=AcceptanceSetState.CLOSED,
        acceptance_proof=proof,
    )
    claims = {EFFECT: claim}
    owners = {LEG_A: owner}
    heads = {LEG_A: head}

    book._validate_effect_edges({EFFECT: operator}, claims, owners, heads)

    with pytest.raises(ValueError, match="at least one owned leg"):
        book._validate_effect_edges({EFFECT: operator}, claims, {}, {})

    valid_contradiction = AcceptanceContradiction(
        leg_key=LEG_A,
        observation_id=owner.observation_id,
    )
    with pytest.raises(ValueError, match="requires closed acceptance"):
        book._validate_effect_edges(
            {
                EFFECT: replace(
                    operator,
                    acceptance_set_state=AcceptanceSetState.INVALIDATED,
                    contradiction_evidence=(valid_contradiction,),
                )
            },
            claims,
            owners,
            heads,
        )
    with pytest.raises(ValueError, match="every leg closed"):
        book._validate_effect_edges({EFFECT: operator}, claims, owners, {})

    mismatched_head = replace(head, cumulative_quantity=Quantity(3))
    with pytest.raises(ValueError, match="canonical covered quantity"):
        book._validate_effect_edges(
            {EFFECT: operator},
            claims,
            owners,
            {LEG_A: mismatched_head},
        )

    short_filled_head = replace(
        head,
        status=VenueAttemptState.FILLED,
        broker_terminal_state=VenueAttemptState.FILLED,
    )
    with pytest.raises(ValueError, match="filled operator closure"):
        book._validate_effect_edges(
            {EFFECT: operator},
            claims,
            owners,
            {LEG_A: short_filled_head},
        )


def test_venue_canonical_helpers_cover_every_admitted_shape_and_reject_others() -> None:
    book, execution = _seed_needs_review(effect_gate_first=False)
    request = next(
        record.item
        for record in book.input_records
        if isinstance(record.item, RequestedEffect)
    )

    with pytest.raises(TypeError, match="must be a tuple"):
        venue_module._require_tuple("audit tuple", [])
    with pytest.raises(TypeError, match="must be bytes"):
        venue_module._require_digest("audit digest", "not-bytes")
    with pytest.raises(TypeError, match="must be VenueInputId"):
        venue_module._require_input_id("audit input", object())
    assert not venue_module._execution_head_matches_fact(object(), object())

    human_fact = _human_fill(LEG_A, "canonical-helper")
    ingested = _ingest(
        book,
        execution,
        human_fact,
        "canonical-helper-human-input",
    )
    assert ingested.disposition is VenueRecoveryDisposition.APPLIED
    head = ingested.execution.root_heads.get(human_fact.root_key)
    assert head is not None
    assert venue_module._execution_head_matches_fact(head, human_fact)
    assert not venue_module._execution_head_matches_fact(
        replace(
            head,
            current_source_event_id=SourceEventId("canonical-helper-other-source"),
        ),
        human_fact,
    )

    admitted_values = (
        None,
        True,
        7,
        "canonical text",
        b"canonical bytes",
        Decimal("1.25"),
        Fraction(5, 4),
        BrokerEffectState.REQUESTED,
        execution,
        request,
    )
    commitments = tuple(
        venue_module._canonical_value_commitment(value) for value in admitted_values
    )
    assert all(
        type(commitment) is bytes and len(commitment) == 32
        for commitment in commitments
    )
    assert len(set(commitments)) == len(commitments)

    with pytest.raises(TypeError, match="unsupported canonical audit value"):
        venue_module._canonical_value_commitment(object())
    with pytest.raises(TypeError, match="exact venue-recovery command type"):
        venue_module._input_command_identity(object(), include_input_id=True)

    with pytest.raises(ValueError, match="quantity must be positive"):
        replace(request, quantity=Quantity(0))
    with pytest.raises(ValueError, match="economic_scope must be nonempty"):
        replace(request, economic_scope=b"")


def _book_with_audit_input_records(
    book: VenueRecoveryBook,
    records: tuple[object, ...],
) -> VenueRecoveryBook:
    forged = copy(book)
    ledger = venue_module._PersistentSequence.from_values(
        records,
        venue_module._input_record_commitment,
    )
    object.__setattr__(forged, "_input_ledger", ledger)
    return forged


def _run_input_fold(book: VenueRecoveryBook) -> dict[VenueInputId, object]:
    return book._validated_inputs(
        {effect.effect_id: effect for effect in book.effects},
        {claim.effect_id: claim for claim in book.claims},
        {owner.leg_key: owner for owner in book.owners},
    )


def test_ordered_input_fold_rejects_missing_lifecycle_predecessors() -> None:
    book, _ = _seed_needs_review(effect_gate_first=False)
    first_record = book.input_records[0]
    invalid_commands = (
        (
            CancelBeforeDispatch(
                input_id=VenueInputId("fold-cancel-without-request"),
                effect_id=EFFECT,
            ),
            "cancel lifecycle input has no requested predecessor",
        ),
        (
            RecoverClaimedEffect(
                input_id=VenueInputId("fold-recover-without-claim"),
                effect_id=EFFECT,
            ),
            "recovery lifecycle input has no claimed predecessor",
        ),
        (
            RecordTransportOutcome(
                input_id=VenueInputId("fold-transport-without-claim"),
                effect_id=EFFECT,
                state=BrokerEffectState.OUTCOME_UNKNOWN,
            ),
            "transport lifecycle input has no valid predecessor",
        ),
    )
    for command, message in invalid_commands:
        record = replace(
            first_record,
            input_id=command.input_id,
            item=command,
        )
        forged = _book_with_audit_input_records(
            book,
            (record, *book.input_records),
        )
        with pytest.raises(ValueError, match=message):
            _run_input_fold(forged)


def test_ordered_input_fold_rejects_owner_and_closed_leg_history_rewrites() -> None:
    book, _ = _seed_needs_review(effect_gate_first=False)
    discovery = next(
        record
        for record in book.input_records
        if isinstance(record.item, DiscoverVenueLeg)
    )
    changed_discovery = replace(
        discovery.item,
        observation_id=VenueObservationId("fold-detached-owner-observation"),
    )
    detached_records = tuple(
        replace(record, item=changed_discovery) if record is discovery else record
        for record in book.input_records
    )
    with pytest.raises(ValueError, match="leg-discovery input provenance"):
        _run_input_fold(_book_with_audit_input_records(book, detached_records))

    review = next(
        record
        for record in book.input_records
        if isinstance(record.item, ObserveVenueStatus)
    )
    terminal = replace(
        review.item,
        input_id=VenueInputId("fold-terminal-observation"),
        status=VenueAttemptState.CANCELED,
        observation_id=VenueObservationId("fold-terminal-observation"),
        closure_id=ClosureId("fold-terminal-closure"),
        evidence_reference=EvidenceReference("fold-terminal-evidence"),
    )
    reactivated = replace(
        review.item,
        input_id=VenueInputId("fold-reactivated-observation"),
        status=VenueAttemptState.WORKING,
        observation_id=VenueObservationId("fold-reactivated-observation"),
    )
    terminal_record = replace(
        review,
        input_id=terminal.input_id,
        item=terminal,
    )
    reactivated_record = replace(
        review,
        input_id=reactivated.input_id,
        item=reactivated,
    )
    with pytest.raises(ValueError, match="closed venue leg cannot become active"):
        _run_input_fold(
            _book_with_audit_input_records(
                book,
                (*book.input_records, terminal_record, reactivated_record),
            )
        )


def test_ordered_input_fold_accepts_valid_cancel_and_claim_recovery_histories() -> None:
    request = RequestedEffect(
        input_id=VenueInputId("fold-valid-request"),
        effect_id=EffectId("fold-valid-effect"),
        request_occurrence_id=RequestOccurrenceId("fold-valid-request-occurrence"),
        mandate_id=MandateId("fold-valid-mandate"),
        kind=EffectKind.SUBMIT,
        client_order_id=ClientOrderId("fold-valid-client"),
        symbol_id=SYMBOL,
        side=ExecutionSide.BUY,
        quantity=Quantity(1),
        economic_scope=b"AAPL|BUY|fold-valid",
    )
    base_book = VenueRecoveryBook.empty(VENUE_SCOPE)
    base_execution = ExecutionSnapshot.flat(POSITION_SCOPE)

    requested_book, requested_execution = _apply(base_book, base_execution, request)
    canceled_book, _ = _apply(
        requested_book,
        requested_execution,
        CancelBeforeDispatch(
            input_id=VenueInputId("fold-valid-cancel"),
            effect_id=request.effect_id,
        ),
    )
    assert set(_run_input_fold(canceled_book)) == {
        request.input_id,
        VenueInputId("fold-valid-cancel"),
    }

    claimed_book, claimed_execution = _apply(
        requested_book,
        requested_execution,
        RecordDispatchClaim(
            input_id=VenueInputId("fold-valid-claim"),
            effect_id=request.effect_id,
            claim_occurrence_id=ClaimOccurrenceId("fold-valid-claim-occurrence"),
        ),
    )
    recovered_book, _ = _apply(
        claimed_book,
        claimed_execution,
        RecoverClaimedEffect(
            input_id=VenueInputId("fold-valid-recovery"),
            effect_id=request.effect_id,
        ),
    )
    assert set(_run_input_fold(recovered_book)) == {
        request.input_id,
        VenueInputId("fold-valid-claim"),
        VenueInputId("fold-valid-recovery"),
    }


def test_r19_checkpoint_projection_has_no_source_order_or_rank_dependency() -> None:
    source = "\n".join(
        inspect.getsource(member)
        for member in (
            checkpoint_codec._project_runtime_checkpoint,
            checkpoint_codec._encode_runtime_checkpoint_venue,
            checkpoint_codec._encode_runtime_checkpoint_authority,
        )
    )

    for forbidden in (
        "_effect_order",
        "_owner_order",
        "source_ordinal",
        "source_rank",
        "rank_map",
    ):
        assert forbidden not in source
    assert "checkpoint_ordinal" in inspect.getsource(checkpoint_codec)


def test_r19_selected_authority_families_do_not_require_whole_superset_cardinality() -> (
    None
):
    source = inspect.getsource(checkpoint_codec._project_runtime_checkpoint)
    module_source = inspect.getsource(checkpoint_codec)

    for family in (
        "_effect_authority_by_id",
        "_claim_by_effect",
        "_claim_by_occurrence",
        "_acquisition_descriptor_by_effect",
    ):
        assert family in module_source
        assert f"{family}.size" not in source
    for family_marker in (
        "effect_authorization",
        "claim_by_effect",
        "descriptor_by_effect",
    ):
        assert family_marker in module_source


def test_r19_projector_source_contains_failure_capable_scope_relation_checks() -> None:
    source = inspect.getsource(checkpoint_codec._project_runtime_checkpoint)
    required_relations = (
        "aggregate_quantity",
        "raw_quantity",
        "expected_controller_head_ordinal",
        "currentness_head_ordinal",
        "state_commitment_sha256",
        "version_ordinal",
        "selection_proof",
    )
    for relation in required_relations:
        assert relation in source
