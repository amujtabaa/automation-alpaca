"""RED-first contracts for the pure WO-0147 authority boundary.

Public M1 construction is permanently deny-only. Positive mechanism paths use a
test-local forged environmental predecessor and then exercise the real reducer;
production exposes no hydrate, promote, refill, grant, or test-state factory.
"""

from __future__ import annotations

from copy import copy
from dataclasses import fields, replace
from decimal import Decimal
import importlib
from types import ModuleType

import pytest

import app.execution_core as execution_core
from app.execution_core.fills import (
    BrokerFillFact,
    ExecutionScope,
    ExecutionSide,
    PositionScope,
    _PersistentKeyMap,
    _PersistentSequence,
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
    SourceEventId,
    SymbolId,
    VenueInputId,
    VenueLegKey,
    VenueObservationId,
)
from app.execution_core.position import (
    ExecutionSnapshot,
    _bind_execution_reconciliation_cursor,
    apply_broker_execution_fact,
)
from app.execution_core.recovery import RecordBrokerFillEvidence
from app.execution_core.values import (
    PriceScale,
    PriceUnits,
    Quantity,
    ReportedPrice,
    TickMetadata,
)
from app.execution_core.venue import (
    AcceptanceProof,
    AcceptanceProofKind,
    AcceptanceSetState,
    BrokerEffectState,
    CatchUpExecutionRegistry,
    CancelBeforeDispatch,
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
    VenueExecutionCheckpoint,
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    VenueScope,
    apply_venue_recovery_input,
)


BROKER = BrokerId("alpaca")
ENVIRONMENT = EnvironmentId("paper")
ACCOUNT = AccountId("authority-account")
GENERATION = ApplicationGenerationId("authority-generation")
SYMBOL = SymbolId("AAPL")
OTHER_SYMBOL = SymbolId("MSFT")
VENUE_SCOPE = VenueScope(
    generation=GENERATION,
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
)
EXECUTION = ExecutionSnapshot.flat(
    PositionScope(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        symbol_id=SYMBOL,
    )
)
LEG = VenueLegKey(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    order_id=OrderId("authority-leg"),
)
RESIDUAL_LEG = VenueLegKey(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    order_id=OrderId("authority-residual-leg"),
)
PRICE_SCALE = PriceScale(Decimal("1"))
PRICE = ReportedPrice(
    units=PriceUnits(100),
    scale=PRICE_SCALE,
    tick=TickMetadata(tick_units=PriceUnits(1), scale=PRICE_SCALE),
)


def _authority_module() -> ModuleType:
    try:
        return importlib.import_module("app.execution_core.authority")
    except ModuleNotFoundError as exc:
        pytest.fail(f"WO-0147 authority module is not implemented: {exc}")


def _required(module: ModuleType, *names: str) -> tuple[object, ...]:
    missing = tuple(name for name in names if not hasattr(module, name))
    assert not missing, f"missing WO-0147 authority API: {missing!r}"
    return tuple(getattr(module, name) for name in names)


def _authority_apply_twice(
    module: ModuleType,
    state: object,
    execution: ExecutionSnapshot,
    item: object,
) -> object:
    before = (state, execution, item)
    first = module.apply_execution_authority_input(state, execution, item)
    second = module.apply_execution_authority_input(state, execution, item)
    assert second == first
    assert before == (state, execution, item)
    return first


def _public_venue_apply_twice(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
) -> object:
    before = (book, execution, item)
    first = apply_venue_recovery_input(book, execution, item)
    second = apply_venue_recovery_input(book, execution, item)
    assert second == first
    assert before == (book, execution, item)
    return first


def _raw_request() -> RequestedEffect:
    return RequestedEffect(
        input_id=VenueInputId("raw-request-input"),
        effect_id=EffectId("raw-request-effect"),
        request_occurrence_id=RequestOccurrenceId("raw-request-occurrence"),
        mandate_id=MandateId("raw-request-mandate"),
        kind=EffectKind.SUBMIT,
        client_order_id=ClientOrderId("raw-request-client"),
        symbol_id=SYMBOL,
        side=ExecutionSide.BUY,
        quantity=Quantity(1),
        economic_scope=b"raw-request-scope",
    )


def _raw_claim() -> RecordDispatchClaim:
    return RecordDispatchClaim(
        input_id=VenueInputId("raw-claim-input"),
        effect_id=EffectId("raw-claim-effect"),
        claim_occurrence_id=ClaimOccurrenceId("raw-claim-occurrence"),
    )


def _genesis(module: ModuleType) -> object:
    (factory,) = _required(module, "initial_execution_authority_state")
    return factory(VENUE_SCOPE)  # type: ignore[operator]


def _forge_positive_predecessor(
    module: ModuleType,
    *,
    predecessor: object | None = None,
    mode: str = "ACTIVE",
    phase: str = "SERVING",
    fence: str = "PAPER_MUTATION_ELIGIBLE",
    kill_engaged: bool = False,
    remaining: int = 4,
    reserve: int = 1,
    session: str = "session-1",
) -> object:
    """Forge environment proof only; all effect work still uses the real reducer."""

    phase_type, mode_type, fence_type, session_type, budget_type = _required(
        module,
        "EnginePhase",
        "TradingMode",
        "SupervisorFence",
        "SessionId",
        "RequestBudget",
    )
    state = copy(predecessor if predecessor is not None else _genesis(module))
    object.__setattr__(state, "phase", getattr(phase_type, phase))
    object.__setattr__(state, "mode", getattr(mode_type, mode))
    object.__setattr__(
        state,
        "supervisor_fence",
        getattr(fence_type, fence),
    )
    object.__setattr__(state, "kill_engaged", kill_engaged)
    object.__setattr__(state, "session_id", session_type(session))
    object.__setattr__(
        state,
        "budget",
        budget_type(remaining=remaining, safety_reserve=reserve),
    )
    return state


def _effect_request(
    module: ModuleType,
    label: str,
    *,
    side: ExecutionSide,
    quantity: int,
    kind: EffectKind = EffectKind.SUBMIT,
    target_leg_key: VenueLegKey | None = None,
) -> object:
    (request_type,) = _required(module, "BrokerEffectRequest")
    return request_type(  # type: ignore[operator]
        effect_id=EffectId(f"{label}-effect"),
        request_occurrence_id=RequestOccurrenceId(f"{label}-occurrence"),
        mandate_id=MandateId(f"{label}-mandate"),
        kind=kind,
        client_order_id=(
            None if kind is EffectKind.CANCEL else ClientOrderId(f"{label}-client")
        ),
        symbol_id=SYMBOL,
        side=side,
        quantity=Quantity(quantity),
        economic_scope=f"{label}-scope".encode(),
        target_leg_key=target_leg_key,
    )


def _create_command(
    module: ModuleType,
    state: object,
    *,
    label: str,
    side: ExecutionSide,
    quantity: int = 1,
    kind: EffectKind = EffectKind.SUBMIT,
    target_leg_key: VenueLegKey | None = None,
    manual_flatten_id: object | None = None,
    emergency_grant_id: object | None = None,
) -> object:
    authority_input_type, create_type = _required(
        module,
        "AuthorityInputId",
        "CreateBrokerEffect",
    )
    return create_type(  # type: ignore[operator]
        input_id=authority_input_type(f"{label}-create-input"),
        session_id=state.session_id,
        request=_effect_request(
            module,
            label,
            side=side,
            quantity=quantity,
            kind=kind,
            target_leg_key=target_leg_key,
        ),
        manual_flatten_id=manual_flatten_id,
        emergency_grant_id=emergency_grant_id,
    )


def _create_effect(
    module: ModuleType,
    state: object,
    execution: ExecutionSnapshot,
    *,
    label: str,
    side: ExecutionSide,
    quantity: int = 1,
    kind: EffectKind = EffectKind.SUBMIT,
    target_leg_key: VenueLegKey | None = None,
    manual_flatten_id: object | None = None,
    emergency_grant_id: object | None = None,
) -> object:
    command = _create_command(
        module,
        state,
        label=label,
        side=side,
        quantity=quantity,
        kind=kind,
        target_leg_key=target_leg_key,
        manual_flatten_id=manual_flatten_id,
        emergency_grant_id=emergency_grant_id,
    )
    return _authority_apply_twice(module, state, execution, command)


def _create_buy(module: ModuleType, state: object, label: str = "buy") -> object:
    return _create_effect(
        module,
        state,
        EXECUTION,
        label=label,
        side=ExecutionSide.BUY,
    )


def _advanced_same_scope_execution(
    *,
    side: ExecutionSide = ExecutionSide.BUY,
    quantity: int = 1,
    label: str = "binding",
    symbol_id: SymbolId = SYMBOL,
) -> ExecutionSnapshot:
    base = ExecutionSnapshot.flat(
        PositionScope(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            symbol_id=symbol_id,
        )
    )
    fact = BrokerFillFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId(f"authority-{label}-fill"),
        ),
        scope=ExecutionScope(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            order_id=OrderId(f"authority-{label}-order"),
            symbol_id=symbol_id,
            side=side,
        ),
        root_fill_id=RootFillId(f"authority-{label}-root"),
        quantity=Quantity(quantity),
        price=PRICE,
    )
    transition = apply_broker_execution_fact(
        base.position,
        base.integrity,
        base.root_heads,
        base.seen_facts,
        fact,
    )
    return ExecutionSnapshot(
        position=transition.position,
        integrity=transition.integrity,
        root_heads=transition.root_heads,
        seen_facts=transition.seen_facts,
    )


def _private_venue_apply(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
) -> object:
    import app.execution_core.venue as venue

    assert hasattr(venue, "_apply_venue_input")
    before = (book, execution, item)
    first = venue._apply_venue_input(book, execution, item)
    second = venue._apply_venue_input(book, execution, item)
    assert second == first
    assert before == (book, execution, item)
    return first


def _seed_raw_cancellable_venue(
    *,
    label: str,
    execution: ExecutionSnapshot = EXECUTION,
    symbol_id: SymbolId = SYMBOL,
    leg_key: VenueLegKey = LEG,
    side: ExecutionSide = ExecutionSide.BUY,
    quantity: int = 1,
) -> tuple[VenueRecoveryBook, EffectId]:
    effect_id = EffectId(f"{label}-effect")
    requested = _private_venue_apply(
        VenueRecoveryBook.empty(VENUE_SCOPE),
        execution,
        RequestedEffect(
            input_id=VenueInputId(f"{label}-request-input"),
            effect_id=effect_id,
            request_occurrence_id=RequestOccurrenceId(f"{label}-occurrence"),
            mandate_id=MandateId(f"{label}-mandate"),
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId(f"{label}-client"),
            symbol_id=symbol_id,
            side=side,
            quantity=Quantity(quantity),
            economic_scope=f"{label}|{symbol_id.value}|{side.value}|{quantity}".encode(),
            target_leg_key=None,
        ),
    )
    claimed = _private_venue_apply(
        requested.book,
        execution,
        RecordDispatchClaim(
            input_id=VenueInputId(f"{label}-claim-input"),
            effect_id=effect_id,
            claim_occurrence_id=ClaimOccurrenceId(f"{label}-claim"),
        ),
    )
    book = claimed.book
    for item in (
        RecordTransportOutcome(
            input_id=VenueInputId(f"{label}-ack-input"),
            effect_id=effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
        DiscoverVenueLeg(
            input_id=VenueInputId(f"{label}-discover-input"),
            effect_id=effect_id,
            leg_key=leg_key,
            observation_id=VenueObservationId(f"{label}-discovery"),
        ),
    ):
        transition = _public_venue_apply_twice(book, execution, item)
        assert transition.disposition is VenueRecoveryDisposition.APPLIED
        book = transition.book
    return book, effect_id


def _append_closed_local_history(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    *,
    label: str,
    count: int = 32,
) -> VenueRecoveryBook:
    for ordinal in range(count):
        prefix = f"{label}-{ordinal}"
        effect_id = EffectId(f"{prefix}-effect")
        requested = _private_venue_apply(
            book,
            execution,
            RequestedEffect(
                input_id=VenueInputId(f"{prefix}-request-input"),
                effect_id=effect_id,
                request_occurrence_id=RequestOccurrenceId(f"{prefix}-occurrence"),
                mandate_id=MandateId(f"{prefix}-mandate"),
                kind=EffectKind.SUBMIT,
                client_order_id=ClientOrderId(f"{prefix}-client"),
                symbol_id=SYMBOL,
                side=ExecutionSide.BUY,
                quantity=Quantity(1),
                economic_scope=f"{prefix}|BUY|1".encode(),
                target_leg_key=None,
            ),
        )
        stood_down = _private_venue_apply(
            requested.book,
            execution,
            CancelBeforeDispatch(
                input_id=VenueInputId(f"{prefix}-stand-down-input"),
                effect_id=effect_id,
            ),
        )
        effect = stood_down.book.effect(effect_id)
        assert effect is not None
        closed = _public_venue_apply_twice(
            stood_down.book,
            execution,
            CloseAcceptanceSet(
                input_id=VenueInputId(f"{prefix}-close-input"),
                effect_id=effect_id,
                proof=AcceptanceProof(
                    kind=AcceptanceProofKind.NEVER_DISPATCHED,
                    effect_scope=effect.scope,
                    claim_occurrence_id=None,
                    evidence_reference=EvidenceReference(f"{prefix}-evidence"),
                    evidence_digest=bytes([(ordinal % 251) + 1]) * 32,
                ),
            ),
        )
        assert closed.disposition is VenueRecoveryDisposition.APPLIED
        book = closed.book
    return book


def _apply_closed_sell_fill(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    *,
    label: str,
    leg_key: VenueLegKey,
) -> tuple[VenueRecoveryBook, ExecutionSnapshot]:
    effect_id = EffectId(f"{label}-effect")
    claim_id = ClaimOccurrenceId(f"{label}-claim")
    requested = _private_venue_apply(
        book,
        execution,
        RequestedEffect(
            input_id=VenueInputId(f"{label}-request-input"),
            effect_id=effect_id,
            request_occurrence_id=RequestOccurrenceId(f"{label}-occurrence"),
            mandate_id=MandateId(f"{label}-mandate"),
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId(f"{label}-client"),
            symbol_id=SYMBOL,
            side=ExecutionSide.SELL,
            quantity=Quantity(1),
            economic_scope=f"{label}|SELL|1".encode(),
            target_leg_key=None,
        ),
    )
    claimed = _private_venue_apply(
        requested.book,
        execution,
        RecordDispatchClaim(
            input_id=VenueInputId(f"{label}-claim-input"),
            effect_id=effect_id,
            claim_occurrence_id=claim_id,
        ),
    )
    acknowledged = _public_venue_apply_twice(
        claimed.book,
        execution,
        RecordTransportOutcome(
            input_id=VenueInputId(f"{label}-ack-input"),
            effect_id=effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    discovered = _public_venue_apply_twice(
        acknowledged.book,
        execution,
        DiscoverVenueLeg(
            input_id=VenueInputId(f"{label}-discover-input"),
            effect_id=effect_id,
            leg_key=leg_key,
            observation_id=VenueObservationId(f"{label}-discovery"),
        ),
    )
    fact = BrokerFillFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId(f"{label}-fill-source"),
        ),
        scope=ExecutionScope(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            order_id=leg_key.order_id,
            symbol_id=SYMBOL,
            side=ExecutionSide.SELL,
        ),
        root_fill_id=RootFillId(f"{label}-fill-root"),
        quantity=Quantity(1),
        price=PRICE,
    )
    filled = _public_venue_apply_twice(
        discovered.book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId(f"{label}-fill-input"),
            effect_id=effect_id,
            leg_key=leg_key,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(1),
            fact=fact,
            evidence_digest=b"\x95" * 32,
            closure_id=None,
            evidence_reference=None,
        ),
    )
    terminal = _public_venue_apply_twice(
        filled.book,
        filled.execution,
        ObserveVenueStatus(
            input_id=VenueInputId(f"{label}-terminal-input"),
            leg_key=leg_key,
            status=VenueAttemptState.FILLED,
            observation_id=VenueObservationId(f"{label}-terminal-observation"),
            cumulative_quantity=Quantity(1),
            closure_id=ClosureId(f"{label}-fill-closure"),
            evidence_reference=EvidenceReference(f"{label}-fill-evidence"),
        ),
    )
    effect = terminal.book.effect(effect_id)
    assert effect is not None
    closed = _public_venue_apply_twice(
        terminal.book,
        terminal.execution,
        CloseAcceptanceSet(
            input_id=VenueInputId(f"{label}-close-input"),
            effect_id=effect_id,
            proof=AcceptanceProof(
                kind=AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
                effect_scope=effect.scope,
                claim_occurrence_id=claim_id,
                evidence_reference=EvidenceReference(f"{label}-close-evidence"),
                evidence_digest=b"\x96" * 32,
            ),
        ),
    )
    return closed.book, closed.execution


def _forge_venue_predecessor(state: object, book: VenueRecoveryBook) -> object:
    forged = copy(state)
    object.__setattr__(forged, "venue", book)
    return forged


def _seed_cancellable_buy(
    module: ModuleType,
    *,
    execution: ExecutionSnapshot = EXECUTION,
    mode: str = "REDUCING",
    fence: str = "PAPER_MUTATION_ELIGIBLE",
    kill_engaged: bool = False,
    remaining: int = 2,
    reserve: int = 1,
    label: str = "cancel-target",
) -> object:
    claim_type, authority_input_type = _required(
        module,
        "ClaimEffect",
        "AuthorityInputId",
    )
    initial = _forge_positive_predecessor(module, remaining=10, reserve=1)
    created = _create_effect(
        module,
        initial,
        execution,
        label=label,
        side=ExecutionSide.BUY,
    )
    claimed = _authority_apply_twice(
        module,
        created.state,
        execution,
        claim_type(  # type: ignore[operator]
            input_id=authority_input_type(f"{label}-claim-input"),
            effect_id=EffectId(f"{label}-effect"),
            claim_occurrence_id=ClaimOccurrenceId(f"{label}-claim"),
        ),
    )
    book = claimed.state.venue
    for item in (
        RecordTransportOutcome(
            input_id=VenueInputId(f"{label}-ack-input"),
            effect_id=EffectId(f"{label}-effect"),
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
        DiscoverVenueLeg(
            input_id=VenueInputId(f"{label}-discover-input"),
            effect_id=EffectId(f"{label}-effect"),
            leg_key=LEG,
            observation_id=VenueObservationId(f"{label}-discovery"),
        ),
    ):
        transition = _public_venue_apply_twice(book, execution, item)
        assert transition.disposition is VenueRecoveryDisposition.APPLIED
        book = transition.book
    seeded = _forge_venue_predecessor(claimed.state, book)
    return _forge_positive_predecessor(
        module,
        predecessor=seeded,
        mode=mode,
        fence=fence,
        kill_engaged=kill_engaged,
        remaining=remaining,
        reserve=reserve,
    )


def _forge_emergency_grant(
    module: ModuleType,
    state: object,
    *,
    label: str = "emergency",
    account: AccountId = ACCOUNT,
    symbol_id: SymbolId = SYMBOL,
    session: str = "session-1",
) -> tuple[object, object]:
    grant_id_type, session_type, grant_type = _required(
        module,
        "EmergencyGrantId",
        "SessionId",
        "_EmergencyGrant",
    )
    grant_id = grant_id_type(f"{label}-grant")  # type: ignore[operator]
    grant = grant_type(  # type: ignore[operator]
        grant_id=grant_id,
        account=account,
        symbol_id=symbol_id,
        session_id=session_type(session),
        actor=ActorId(f"{label}-operator"),
        reason=f"{label} emergency reduction",
        evidence_reference=EvidenceReference(f"{label}-evidence"),
    )
    forged = copy(state)
    object.__setattr__(forged, "_emergency_grant", grant)
    return forged, grant_id


def test_raw_venue_request_and_claim_are_not_public_capabilities() -> None:
    import app.execution_core.venue as venue

    for name in (
        "RequestedEffect",
        "RecordDispatchClaim",
        "CancelBeforeDispatch",
        "RecordPendingVenueOperation",
    ):
        assert name not in execution_core.__all__
        assert not hasattr(execution_core, name)
        assert name not in venue.__all__


@pytest.mark.parametrize(
    "item",
    [
        _raw_request(),
        _raw_claim(),
        CancelBeforeDispatch(
            input_id=VenueInputId("raw-stand-down-input"),
            effect_id=EffectId("raw-stand-down-effect"),
        ),
        RecordPendingVenueOperation(
            input_id=VenueInputId("raw-pending-input"),
            leg_key=LEG,
            operation=PendingVenueOperation.CANCEL,
        ),
    ],
)
def test_public_venue_reducer_rejects_raw_authority_inputs(item: object) -> None:
    with pytest.raises(TypeError, match="authority|internal|admitted"):
        apply_venue_recovery_input(
            VenueRecoveryBook.empty(VENUE_SCOPE),
            EXECUTION,
            item,
        )


@pytest.mark.parametrize(
    ("kind", "client_order_id", "target_leg_key", "message"),
    [
        (EffectKind.SUBMIT, None, None, "SUBMIT requires a client_order_id"),
        (
            EffectKind.SUBMIT,
            ClientOrderId("invalid-submit-client"),
            LEG,
            "SUBMIT cannot target a venue leg",
        ),
        (
            EffectKind.CANCEL,
            ClientOrderId("invalid-cancel-client"),
            LEG,
            "CANCEL cannot carry a client_order_id",
        ),
        (EffectKind.CANCEL, None, None, "CANCEL requires a target_leg_key"),
        (EffectKind.REPLACE, None, LEG, "REPLACE requires a client_order_id"),
        (
            EffectKind.REPLACE,
            ClientOrderId("invalid-replace-client"),
            None,
            "REPLACE requires a target_leg_key",
        ),
    ],
)
def test_effect_kind_requires_exact_creating_identity_and_target_shape(
    kind: EffectKind,
    client_order_id: ClientOrderId | None,
    target_leg_key: VenueLegKey | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        RequestedEffect(
            input_id=VenueInputId(f"invalid-{kind.value}-input"),
            effect_id=EffectId(f"invalid-{kind.value}-effect"),
            request_occurrence_id=RequestOccurrenceId(
                f"invalid-{kind.value}-occurrence"
            ),
            mandate_id=MandateId(f"invalid-{kind.value}-mandate"),
            kind=kind,
            client_order_id=client_order_id,
            symbol_id=SYMBOL,
            side=ExecutionSide.BUY,
            quantity=Quantity(1),
            economic_scope=f"invalid-{kind.value}-scope".encode(),
            target_leg_key=target_leg_key,
        )

    module = _authority_module()
    (request_type,) = _required(module, "BrokerEffectRequest")
    with pytest.raises(ValueError, match=message):
        request_type(  # type: ignore[operator]
            effect_id=EffectId(f"invalid-public-{kind.value}-effect"),
            request_occurrence_id=RequestOccurrenceId(
                f"invalid-public-{kind.value}-occurrence"
            ),
            mandate_id=MandateId(f"invalid-public-{kind.value}-mandate"),
            kind=kind,
            client_order_id=client_order_id,
            symbol_id=SYMBOL,
            side=ExecutionSide.BUY,
            quantity=Quantity(1),
            economic_scope=f"invalid-public-{kind.value}-scope".encode(),
            target_leg_key=target_leg_key,
        )


def test_target_bound_cancel_has_no_creating_identity_or_owner() -> None:
    book = VenueRecoveryBook.empty(VENUE_SCOPE)
    target = _raw_request()
    requested = _private_venue_apply(book, EXECUTION, target)
    claimed = _private_venue_apply(
        requested.book,
        EXECUTION,
        RecordDispatchClaim(
            input_id=VenueInputId("target-claim-input"),
            effect_id=target.effect_id,
            claim_occurrence_id=ClaimOccurrenceId("target-claim"),
        ),
    )
    acknowledged = _public_venue_apply_twice(
        claimed.book,
        EXECUTION,
        RecordTransportOutcome(
            input_id=VenueInputId("target-ack-input"),
            effect_id=target.effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    discovered = _public_venue_apply_twice(
        acknowledged.book,
        EXECUTION,
        DiscoverVenueLeg(
            input_id=VenueInputId("target-discover-input"),
            effect_id=target.effect_id,
            leg_key=LEG,
            observation_id=VenueObservationId("target-discovery"),
        ),
    )
    cancel = RequestedEffect(
        input_id=VenueInputId("cancel-request-input"),
        effect_id=EffectId("cancel-effect"),
        request_occurrence_id=RequestOccurrenceId("cancel-occurrence"),
        mandate_id=MandateId("cancel-mandate"),
        kind=EffectKind.CANCEL,
        client_order_id=None,
        symbol_id=SYMBOL,
        side=ExecutionSide.BUY,
        quantity=Quantity(1),
        economic_scope=b"cancel|authority-leg",
        target_leg_key=LEG,
    )

    canceled = _private_venue_apply(discovered.book, EXECUTION, cancel)
    effect = canceled.book.effect(cancel.effect_id)
    assert canceled.disposition is VenueRecoveryDisposition.APPLIED
    assert effect is not None
    assert effect.scope.client_order_id is None
    assert effect.scope.target_leg_key == LEG
    assert canceled.book.owners == discovered.book.owners
    requested_target = canceled.book.active_attempt(LEG)
    assert requested_target is not None
    assert requested_target.pending_operation is None

    cancel_claim = RecordDispatchClaim(
        input_id=VenueInputId("cancel-claim-input"),
        effect_id=cancel.effect_id,
        claim_occurrence_id=ClaimOccurrenceId("cancel-claim"),
    )
    claimed_cancel = _private_venue_apply(
        canceled.book,
        EXECUTION,
        cancel_claim,
    )
    claimed_target = claimed_cancel.book.active_attempt(LEG)
    assert claimed_target is not None
    assert claimed_target.pending_operation is None
    acknowledged_cancel = _public_venue_apply_twice(
        claimed_cancel.book,
        EXECUTION,
        RecordTransportOutcome(
            input_id=VenueInputId("cancel-ack-input"),
            effect_id=cancel.effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    target_attempt = acknowledged_cancel.book.active_attempt(LEG)
    assert acknowledged_cancel.disposition is VenueRecoveryDisposition.APPLIED
    assert target_attempt is not None
    assert target_attempt.status is VenueAttemptState.WORKING
    assert target_attempt.pending_operation is PendingVenueOperation.CANCEL
    replay = _public_venue_apply_twice(
        acknowledged_cancel.book,
        EXECUTION,
        RecordTransportOutcome(
            input_id=VenueInputId("cancel-ack-input"),
            effect_id=cancel.effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    assert replay.disposition is VenueRecoveryDisposition.EXACT_REPLAY
    assert replay.book == acknowledged_cancel.book

    false_owner = _public_venue_apply_twice(
        acknowledged_cancel.book,
        EXECUTION,
        DiscoverVenueLeg(
            input_id=VenueInputId("cancel-false-owner-input"),
            effect_id=cancel.effect_id,
            leg_key=VenueLegKey(
                broker=BROKER,
                environment=ENVIRONMENT,
                account=ACCOUNT,
                order_id=OrderId("cancel-false-owner"),
            ),
            observation_id=VenueObservationId("cancel-false-owner-observation"),
        ),
    )
    assert false_owner.disposition is VenueRecoveryDisposition.REFUSED
    assert false_owner.book == acknowledged_cancel.book


@pytest.mark.parametrize(
    ("case", "target_leg_key", "side", "quantity"),
    [
        (
            "unknown",
            VenueLegKey(
                broker=BROKER,
                environment=ENVIRONMENT,
                account=ACCOUNT,
                order_id=OrderId("unknown-cancel-target"),
            ),
            ExecutionSide.BUY,
            1,
        ),
        (
            "cross-account",
            VenueLegKey(
                broker=BROKER,
                environment=ENVIRONMENT,
                account=AccountId("other-cancel-account"),
                order_id=LEG.order_id,
            ),
            ExecutionSide.BUY,
            1,
        ),
        ("side-mismatch", LEG, ExecutionSide.SELL, 1),
        ("quantity-mismatch", LEG, ExecutionSide.BUY, 2),
    ],
)
def test_public_cancel_requires_one_exact_active_target(
    case: str,
    target_leg_key: VenueLegKey,
    side: ExecutionSide,
    quantity: int,
) -> None:
    module = _authority_module()
    disposition_type, reason_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
    )
    state = _seed_cancellable_buy(module, label=f"cancel-target-{case}")
    refused = _create_effect(
        module,
        state,
        EXECUTION,
        label=f"invalid-cancel-{case}",
        side=side,
        quantity=quantity,
        kind=EffectKind.CANCEL,
        target_leg_key=target_leg_key,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.VENUE_UNCERTAIN
    assert refused.state == state
    assert refused.state.budget == state.budget
    assert refused.created_effect_ids == ()
    assert refused.fresh_claim is None


@pytest.mark.parametrize(
    ("case", "target_leg_key", "side", "quantity"),
    [
        (
            "unknown",
            VenueLegKey(
                broker=BROKER,
                environment=ENVIRONMENT,
                account=ACCOUNT,
                order_id=OrderId("private-unknown-cancel-target"),
            ),
            ExecutionSide.BUY,
            1,
        ),
        (
            "cross-account",
            VenueLegKey(
                broker=BROKER,
                environment=ENVIRONMENT,
                account=AccountId("private-other-account"),
                order_id=LEG.order_id,
            ),
            ExecutionSide.BUY,
            1,
        ),
        ("side-mismatch", LEG, ExecutionSide.SELL, 1),
        ("quantity-mismatch", LEG, ExecutionSide.BUY, 2),
    ],
)
def test_private_cancel_refuses_missing_or_mismatched_target(
    case: str,
    target_leg_key: VenueLegKey,
    side: ExecutionSide,
    quantity: int,
) -> None:
    book, _ = _seed_raw_cancellable_venue(label=f"private-cancel-{case}")
    cancel = RequestedEffect(
        input_id=VenueInputId(f"private-invalid-cancel-{case}-input"),
        effect_id=EffectId(f"private-invalid-cancel-{case}-effect"),
        request_occurrence_id=RequestOccurrenceId(
            f"private-invalid-cancel-{case}-occurrence"
        ),
        mandate_id=MandateId(f"private-invalid-cancel-{case}-mandate"),
        kind=EffectKind.CANCEL,
        client_order_id=None,
        symbol_id=SYMBOL,
        side=side,
        quantity=Quantity(quantity),
        economic_scope=f"private-invalid-cancel-{case}".encode(),
        target_leg_key=target_leg_key,
    )
    refused = _private_venue_apply(book, EXECUTION, cancel)
    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.book == book
    assert refused.book.owners == book.owners


def test_private_cancel_refuses_a_cross_symbol_owner() -> None:
    msft_execution = ExecutionSnapshot.flat(
        PositionScope(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            symbol_id=OTHER_SYMBOL,
        )
    )
    book, _ = _seed_raw_cancellable_venue(
        label="private-cross-symbol-target",
        execution=msft_execution,
        symbol_id=OTHER_SYMBOL,
    )
    cancel = RequestedEffect(
        input_id=VenueInputId("private-cross-symbol-cancel-input"),
        effect_id=EffectId("private-cross-symbol-cancel-effect"),
        request_occurrence_id=RequestOccurrenceId(
            "private-cross-symbol-cancel-occurrence"
        ),
        mandate_id=MandateId("private-cross-symbol-cancel-mandate"),
        kind=EffectKind.CANCEL,
        client_order_id=None,
        symbol_id=SYMBOL,
        side=ExecutionSide.BUY,
        quantity=Quantity(1),
        economic_scope=b"private-cross-symbol-cancel",
        target_leg_key=LEG,
    )
    refused = _private_venue_apply(book, EXECUTION, cancel)
    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert refused.book == book
    assert refused.book.owners == book.owners


def test_cancel_refuses_a_terminal_target() -> None:
    module = _authority_module()
    disposition_type, reason_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
    )
    state = _seed_cancellable_buy(module, label="terminal-cancel-target")
    terminal = _public_venue_apply_twice(
        state.venue,
        EXECUTION,
        ObserveVenueStatus(
            input_id=VenueInputId("terminal-cancel-target-input"),
            leg_key=LEG,
            status=VenueAttemptState.CANCELED,
            observation_id=VenueObservationId("terminal-cancel-target-observation"),
            cumulative_quantity=Quantity(0),
            closure_id=ClosureId("terminal-cancel-target-closure"),
            evidence_reference=EvidenceReference("terminal-cancel-target-evidence"),
        ),
    )
    terminal_state = _forge_venue_predecessor(state, terminal.book)
    refused = _create_effect(
        module,
        terminal_state,
        terminal.execution,
        label="terminal-cancel",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.VENUE_UNCERTAIN
    assert refused.state == terminal_state
    assert refused.created_effect_ids == ()


@pytest.mark.parametrize(
    ("outcome", "expected_pending"),
    [
        (BrokerEffectState.REJECTED, None),
        (BrokerEffectState.OUTCOME_UNKNOWN, PendingVenueOperation.CANCEL),
    ],
)
def test_cancel_target_pending_state_follows_transport_uncertainty(
    outcome: BrokerEffectState,
    expected_pending: PendingVenueOperation | None,
) -> None:
    module = _authority_module()
    disposition_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "ClaimEffect",
        "AuthorityInputId",
    )
    label = f"cancel-{outcome.value.casefold()}"
    state = _seed_cancellable_buy(module, label=f"{label}-target")
    created = _create_effect(
        module,
        state,
        EXECUTION,
        label=label,
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    assert created.disposition is disposition_type.APPLIED
    owners_before = created.state.venue.owners
    claimed = _authority_apply_twice(
        module,
        created.state,
        EXECUTION,
        claim_type(  # type: ignore[operator]
            input_id=authority_input_type(f"{label}-claim-input"),
            effect_id=EffectId(f"{label}-effect"),
            claim_occurrence_id=ClaimOccurrenceId(f"{label}-claim"),
        ),
    )
    target_before = claimed.state.venue.active_attempt(LEG)
    assert target_before is not None
    assert target_before.pending_operation is None
    transitioned = _public_venue_apply_twice(
        claimed.state.venue,
        EXECUTION,
        RecordTransportOutcome(
            input_id=VenueInputId(f"{label}-outcome-input"),
            effect_id=EffectId(f"{label}-effect"),
            state=outcome,
        ),
    )
    assert transitioned.disposition is VenueRecoveryDisposition.APPLIED
    target_after = transitioned.book.active_attempt(LEG)
    assert target_after is not None
    assert target_after.pending_operation is expected_pending
    assert transitioned.book.owners == owners_before


def test_cancel_final_claim_rechecks_a_target_that_terminalized_after_creation() -> (
    None
):
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    state = _seed_cancellable_buy(module, label="cancel-claim-drift-target")
    created = _create_effect(
        module,
        state,
        EXECUTION,
        label="cancel-claim-drift",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    assert created.disposition is disposition_type.APPLIED
    terminal = _public_venue_apply_twice(
        created.state.venue,
        EXECUTION,
        ObserveVenueStatus(
            input_id=VenueInputId("cancel-claim-drift-terminal-input"),
            leg_key=LEG,
            status=VenueAttemptState.CANCELED,
            observation_id=VenueObservationId(
                "cancel-claim-drift-terminal-observation"
            ),
            cumulative_quantity=Quantity(0),
            closure_id=ClosureId("cancel-claim-drift-terminal-closure"),
            evidence_reference=EvidenceReference(
                "cancel-claim-drift-terminal-evidence"
            ),
        ),
    )
    drifted = _forge_venue_predecessor(created.state, terminal.book)
    before_budget = drifted.budget
    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("cancel-claim-drift-claim-input"),
        effect_id=EffectId("cancel-claim-drift-effect"),
        claim_occurrence_id=ClaimOccurrenceId("cancel-claim-drift-claim"),
    )
    refused = _authority_apply_twice(
        module,
        drifted,
        terminal.execution,
        claim,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.VENUE_UNCERTAIN
    assert refused.state == drifted
    assert refused.state.budget == before_budget
    retained = refused.state.venue.effect(EffectId("cancel-claim-drift-effect"))
    assert retained is not None
    assert retained.state is BrokerEffectState.REQUESTED
    assert retained.claim_occurrence_id is None
    assert refused.state.venue.active_attempt(LEG) is None
    assert refused.fresh_claim is None


def test_public_genesis_is_exactly_deny_only_and_account_scoped() -> None:
    module = _authority_module()
    state_type, phase_type, mode_type, fence_type = _required(
        module,
        "ExecutionAuthorityState",
        "EnginePhase",
        "TradingMode",
        "SupervisorFence",
    )
    state = _genesis(module)

    assert type(state) is state_type
    assert state.phase is phase_type.BOOTSTRAPPING
    assert state.mode is mode_type.HALTED
    assert state.supervisor_fence is fence_type.UNAUTHENTICATED
    assert state.kill_engaged is True
    assert state.session_id is None
    assert state.budget.remaining == 0
    assert state.budget.safety_reserve == 0
    assert state.venue == VenueRecoveryBook.empty(VENUE_SCOPE)
    assert not hasattr(state, "execution")


def test_authority_state_has_no_normal_constructor_replace_or_subclass() -> None:
    module = _authority_module()
    state_type, mode_type = _required(
        module,
        "ExecutionAuthorityState",
        "TradingMode",
    )
    state = _genesis(module)

    with pytest.raises(TypeError):
        state_type()  # type: ignore[operator]
    with pytest.raises(TypeError):
        replace(state, mode=mode_type.ACTIVE)
    with pytest.raises(TypeError):
        type("ForgedAuthorityState", (state_type,), {})


def test_public_api_has_no_promotion_or_positive_authority_mint() -> None:
    module = _authority_module()
    forbidden = (
        "authenticate",
        "promote",
        "clear_kill",
        "issue_emergency",
        "paper_mutation_eligible",
        "refill",
        "hydrate",
        "test_state",
        "set_active",
        "set_reducing",
    )
    names = {
        name.casefold()
        for name in (*getattr(module, "__all__", ()), *execution_core.__all__)
    }
    assert all(fragment not in name for fragment in forbidden for name in names)


def test_request_budget_allows_reserved_capacity_to_be_partly_consumed() -> None:
    module = _authority_module()
    (budget_type,) = _required(module, "RequestBudget")

    depleted = budget_type(remaining=0, safety_reserve=1)  # type: ignore[operator]
    assert depleted.remaining == 0
    assert depleted.safety_reserve == 1
    for kwargs in (
        {"remaining": True, "safety_reserve": 0},
        {"remaining": 0, "safety_reserve": True},
        {"remaining": -1, "safety_reserve": 0},
        {"remaining": 0, "safety_reserve": -1},
    ):
        with pytest.raises((TypeError, ValueError)):
            budget_type(**kwargs)  # type: ignore[operator]


def test_create_and_final_claim_are_one_real_reducer_path() -> None:
    module = _authority_module()
    disposition_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "ClaimEffect",
        "AuthorityInputId",
    )
    initial = _forge_positive_predecessor(module, remaining=3, reserve=1)

    command = _create_command(
        module,
        initial,
        label="buy",
        side=ExecutionSide.BUY,
    )
    first_created = module.apply_execution_authority_input(
        initial,
        EXECUTION,
        command,
    )
    second_created = module.apply_execution_authority_input(
        initial,
        EXECUTION,
        command,
    )
    assert second_created == first_created
    created = first_created
    assert created.disposition is disposition_type.APPLIED
    assert initial.venue == VenueRecoveryBook.empty(VENUE_SCOPE)
    assert initial.budget.remaining == 3
    assert created.created_effect_ids == (EffectId("buy-effect"),)
    assert created.fresh_claim is None
    assert created.state.budget.remaining == 3

    create_replay = _authority_apply_twice(
        module,
        created.state,
        EXECUTION,
        command,
    )
    assert create_replay.disposition is disposition_type.EXACT_REPLAY
    assert create_replay.state == created.state
    assert create_replay.created_effect_ids == ()

    changed = replace(
        command,
        request=replace(command.request, quantity=Quantity(2)),
    )
    conflict = _authority_apply_twice(
        module,
        created.state,
        EXECUTION,
        changed,
    )
    assert conflict.disposition is disposition_type.CONFLICT
    assert conflict.state == created.state
    assert conflict.created_effect_ids == ()
    assert conflict.fresh_claim is None

    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("buy-claim-input"),
        effect_id=EffectId("buy-effect"),
        claim_occurrence_id=ClaimOccurrenceId("buy-claim"),
    )
    first_claimed = module.apply_execution_authority_input(
        created.state,
        EXECUTION,
        claim,
    )
    second_claimed = module.apply_execution_authority_input(
        created.state,
        EXECUTION,
        claim,
    )
    assert second_claimed == first_claimed
    claimed = first_claimed

    assert claimed.disposition is disposition_type.APPLIED
    assert claimed.fresh_claim is not None
    assert claimed.fresh_claim.effect_id == EffectId("buy-effect")
    assert claimed.state.budget.remaining == 2

    replay = _authority_apply_twice(
        module,
        claimed.state,
        EXECUTION,
        claim,
    )
    assert replay.disposition is disposition_type.EXACT_REPLAY
    assert replay.fresh_claim is None
    assert replay.state == claimed.state
    assert replay.state.budget.remaining == 2

    changed_claim = replace(
        claim,
        claim_occurrence_id=ClaimOccurrenceId("buy-changed-claim"),
    )
    changed_claim_conflict = _authority_apply_twice(
        module,
        claimed.state,
        EXECUTION,
        changed_claim,
    )
    assert changed_claim_conflict.disposition is disposition_type.CONFLICT
    assert changed_claim_conflict.state == claimed.state
    assert changed_claim_conflict.state.budget.remaining == 2
    assert changed_claim_conflict.fresh_claim is None

    reused_occurrence = replace(
        claim,
        input_id=authority_input_type("buy-reused-claim-input"),
    )
    reused_claim_conflict = _authority_apply_twice(
        module,
        claimed.state,
        EXECUTION,
        reused_occurrence,
    )
    assert reused_claim_conflict.disposition is disposition_type.CONFLICT
    assert reused_claim_conflict.state == claimed.state
    assert reused_claim_conflict.state.budget.remaining == 2
    assert reused_claim_conflict.fresh_claim is None

    second_claim_for_effect = replace(
        claim,
        input_id=authority_input_type("buy-second-effect-claim-input"),
        claim_occurrence_id=ClaimOccurrenceId("buy-second-effect-claim"),
    )
    effect_conflict = _authority_apply_twice(
        module,
        claimed.state,
        EXECUTION,
        second_claim_for_effect,
    )
    assert effect_conflict.disposition is disposition_type.CONFLICT
    assert effect_conflict.state == claimed.state
    assert effect_conflict.state.budget.remaining == 2
    assert effect_conflict.fresh_claim is None

    acknowledged = _public_venue_apply_twice(
        claimed.state.venue,
        EXECUTION,
        RecordTransportOutcome(
            input_id=VenueInputId("buy-claim-ack-input"),
            effect_id=EffectId("buy-effect"),
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    blocked_successor = _forge_positive_predecessor(
        module,
        predecessor=_forge_venue_predecessor(claimed.state, acknowledged.book),
        fence="RECONCILIATION_ONLY",
        kill_engaged=True,
        remaining=0,
        reserve=0,
    )
    late_duplicate = replace(
        claim,
        input_id=authority_input_type("buy-late-duplicate-claim-input"),
        claim_occurrence_id=ClaimOccurrenceId("buy-late-duplicate-claim"),
    )
    late_conflict = _authority_apply_twice(
        module,
        blocked_successor,
        EXECUTION,
        late_duplicate,
    )
    assert late_conflict.disposition is disposition_type.CONFLICT
    assert late_conflict.state == blocked_successor
    assert late_conflict.fresh_claim is None


@pytest.mark.parametrize("reused_identity", ["request_occurrence", "client_order"])
def test_permanent_effect_identity_conflicts_precede_mutable_gate_drift(
    reused_identity: str,
) -> None:
    module = _authority_module()
    disposition_type, authority_input_type, create_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityInputId",
        "CreateBrokerEffect",
    )
    initial = _forge_positive_predecessor(module, remaining=4, reserve=1)
    created = _create_buy(module, initial, label="permanent-identity-source")
    assert created.disposition is disposition_type.APPLIED
    request = _effect_request(
        module,
        f"permanent-{reused_identity}",
        side=ExecutionSide.BUY,
        quantity=1,
    )
    if reused_identity == "request_occurrence":
        request = replace(
            request,
            request_occurrence_id=RequestOccurrenceId(
                "permanent-identity-source-occurrence"
            ),
        )
    else:
        request = replace(
            request,
            client_order_id=ClientOrderId("permanent-identity-source-client"),
        )
    drifted = _forge_positive_predecessor(
        module,
        predecessor=created.state,
        fence="RECONCILIATION_ONLY",
        kill_engaged=True,
        remaining=0,
        reserve=0,
    )
    command = create_type(
        input_id=authority_input_type(f"permanent-{reused_identity}-input"),
        session_id=drifted.session_id,
        request=request,
        manual_flatten_id=None,
        emergency_grant_id=None,
    )

    conflict = _authority_apply_twice(module, drifted, EXECUTION, command)
    assert conflict.disposition is disposition_type.CONFLICT
    assert conflict.state == drifted
    assert conflict.state.budget == drifted.budget
    assert conflict.created_effect_ids == ()
    assert conflict.fresh_claim is None


def test_first_authority_effect_for_a_later_account_symbol_is_admitted() -> None:
    module = _authority_module()
    disposition_type, authority_input_type, request_type, create_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityInputId",
        "BrokerEffectRequest",
        "CreateBrokerEffect",
    )
    initial = _forge_positive_predecessor(module, remaining=5, reserve=1)
    aapl = _create_buy(module, initial, label="first-account-symbol")
    assert aapl.disposition is disposition_type.APPLIED
    msft_execution = ExecutionSnapshot.flat(
        PositionScope(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            symbol_id=OTHER_SYMBOL,
        )
    )
    request = request_type(
        effect_id=EffectId("later-symbol-effect"),
        request_occurrence_id=RequestOccurrenceId("later-symbol-occurrence"),
        mandate_id=MandateId("later-symbol-mandate"),
        kind=EffectKind.SUBMIT,
        client_order_id=ClientOrderId("later-symbol-client"),
        symbol_id=OTHER_SYMBOL,
        side=ExecutionSide.BUY,
        quantity=Quantity(1),
        economic_scope=b"later-symbol|MSFT|BUY|1",
        target_leg_key=None,
    )
    command = create_type(
        input_id=authority_input_type("later-symbol-create-input"),
        session_id=aapl.state.session_id,
        request=request,
        manual_flatten_id=None,
        emergency_grant_id=None,
    )

    admitted = _authority_apply_twice(
        module,
        aapl.state,
        msft_execution,
        command,
    )
    assert admitted.disposition is disposition_type.APPLIED
    assert admitted.created_effect_ids == (EffectId("later-symbol-effect"),)
    assert admitted.state.budget == aapl.state.budget


def test_later_account_symbol_still_requires_exact_account_registry() -> None:
    module = _authority_module()
    (
        disposition_type,
        reason_type,
        authority_input_type,
        request_type,
        create_type,
    ) = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "AuthorityInputId",
        "BrokerEffectRequest",
        "CreateBrokerEffect",
    )
    initial = _forge_positive_predecessor(module, remaining=5, reserve=1)
    aapl = _create_buy(module, initial, label="registry-source-symbol")
    assert aapl.disposition is disposition_type.APPLIED
    msft_ahead = _advanced_same_scope_execution(
        label="later-symbol-registry-ahead",
        symbol_id=OTHER_SYMBOL,
    )
    request = request_type(
        effect_id=EffectId("later-symbol-registry-effect"),
        request_occurrence_id=RequestOccurrenceId("later-symbol-registry-occurrence"),
        mandate_id=MandateId("later-symbol-registry-mandate"),
        kind=EffectKind.SUBMIT,
        client_order_id=ClientOrderId("later-symbol-registry-client"),
        symbol_id=OTHER_SYMBOL,
        side=ExecutionSide.BUY,
        quantity=Quantity(1),
        economic_scope=b"later-symbol-registry|MSFT|BUY|1",
        target_leg_key=None,
    )
    command = create_type(
        input_id=authority_input_type("later-symbol-registry-create-input"),
        session_id=aapl.state.session_id,
        request=request,
        manual_flatten_id=None,
        emergency_grant_id=None,
    )

    refused = _authority_apply_twice(module, aapl.state, msft_ahead, command)
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.EXECUTION_BINDING_MISMATCH
    assert refused.state == aapl.state


def test_normal_claim_succeeds_exactly_above_reserve_and_refuses_at_reserve() -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    boundary = _forge_positive_predecessor(module, remaining=2, reserve=1)
    created = _create_buy(module, boundary, label="reserve-boundary-success")
    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("reserve-boundary-success-claim-input"),
        effect_id=EffectId("reserve-boundary-success-effect"),
        claim_occurrence_id=ClaimOccurrenceId("reserve-boundary-success-claim"),
    )
    claimed = _authority_apply_twice(module, created.state, EXECUTION, claim)
    assert claimed.disposition is disposition_type.APPLIED
    assert claimed.state.budget.remaining == claimed.state.budget.safety_reserve == 1
    assert claimed.fresh_claim is not None

    second_base = _forge_positive_predecessor(module, remaining=2, reserve=1)
    second_created = _create_buy(
        module,
        second_base,
        label="reserve-boundary-refusal",
    )
    at_reserve = _forge_positive_predecessor(
        module,
        predecessor=second_created.state,
        remaining=1,
        reserve=1,
    )
    second_claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("reserve-boundary-refusal-claim-input"),
        effect_id=EffectId("reserve-boundary-refusal-effect"),
        claim_occurrence_id=ClaimOccurrenceId("reserve-boundary-refusal-claim"),
    )
    refused = _authority_apply_twice(module, at_reserve, EXECUTION, second_claim)
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.SAFETY_RESERVE_PROTECTED
    assert refused.state == at_reserve
    assert refused.state.budget.remaining == 1
    assert refused.fresh_claim is None


@pytest.mark.parametrize(
    ("label", "changes", "expected_reason"),
    [
        ("bootstrapping", {"phase": "BOOTSTRAPPING"}, "PHASE_BLOCKED"),
        ("reconciling", {"phase": "RECONCILING"}, "PHASE_BLOCKED"),
        ("reducing", {"mode": "REDUCING"}, "MODE_BLOCKED"),
        ("halted", {"mode": "HALTED"}, "MODE_BLOCKED"),
        (
            "reconciliation-fence",
            {"fence": "RECONCILIATION_ONLY"},
            "SUPERVISOR_FENCE_BLOCKED",
        ),
        (
            "unauthenticated-fence",
            {"fence": "UNAUTHENTICATED"},
            "SUPERVISOR_FENCE_BLOCKED",
        ),
        ("kill", {"kill_engaged": True}, "KILL_ENGAGED"),
        (
            "reserve",
            {"remaining": 1, "reserve": 1},
            "SAFETY_RESERVE_PROTECTED",
        ),
        (
            "exhausted",
            {"remaining": 0, "reserve": 0},
            "REQUEST_BUDGET_EXHAUSTED",
        ),
        ("session", {"session": "session-2"}, "SESSION_MISMATCH"),
    ],
)
def test_final_claim_rechecks_every_mutation_gate_without_debit(
    label: str,
    changes: dict[str, object],
    expected_reason: str,
) -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    initial = _forge_positive_predecessor(module, remaining=3, reserve=1)
    created = _create_buy(module, initial, label=f"regate-{label}")
    assert created.disposition is disposition_type.APPLIED

    complete_changes: dict[str, object] = {"remaining": 3, "reserve": 1}
    complete_changes.update(changes)
    changed = _forge_positive_predecessor(  # type: ignore[arg-type]
        module,
        predecessor=created.state,
        **complete_changes,
    )
    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type(f"regate-{label}-claim-input"),
        effect_id=EffectId(f"regate-{label}-effect"),
        claim_occurrence_id=ClaimOccurrenceId(f"regate-{label}-claim"),
    )

    first = module.apply_execution_authority_input(changed, EXECUTION, claim)
    second = module.apply_execution_authority_input(changed, EXECUTION, claim)
    assert second == first
    refused = first
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is getattr(reason_type, expected_reason)
    assert refused.state == changed
    assert refused.state.budget == changed.budget
    retained = refused.state.venue.effect(EffectId(f"regate-{label}-effect"))
    assert retained is not None
    assert retained.state is BrokerEffectState.REQUESTED
    assert retained.claim_occurrence_id is None
    assert refused.created_effect_ids == ()
    assert refused.fresh_claim is None


def test_final_claim_rechecks_exact_execution_binding_without_debit() -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    initial = _forge_positive_predecessor(module, remaining=3, reserve=1)
    created = _create_buy(module, initial, label="stale-binding")
    advanced_execution = _advanced_same_scope_execution()
    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("stale-binding-claim-input"),
        effect_id=EffectId("stale-binding-effect"),
        claim_occurrence_id=ClaimOccurrenceId("stale-binding-claim"),
    )

    refused = _authority_apply_twice(
        module,
        created.state,
        advanced_execution,
        claim,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.EXECUTION_BINDING_MISMATCH
    assert refused.state == created.state
    assert refused.state.budget.remaining == 3
    assert refused.fresh_claim is None


def test_final_claim_rechecks_late_sibling_acceptance_uncertainty() -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    initial = _forge_positive_predecessor(module, remaining=6, reserve=1)
    prior = _create_buy(module, initial, label="prior")
    prior_claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("prior-claim-input"),
        effect_id=EffectId("prior-effect"),
        claim_occurrence_id=ClaimOccurrenceId("prior-claim"),
    )
    claimed = _authority_apply_twice(
        module,
        prior.state,
        EXECUTION,
        prior_claim,
    )
    assert claimed.disposition is disposition_type.APPLIED

    venue_steps = (
        RecordTransportOutcome(
            input_id=VenueInputId("prior-ack-input"),
            effect_id=EffectId("prior-effect"),
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
        DiscoverVenueLeg(
            input_id=VenueInputId("prior-discover-input"),
            effect_id=EffectId("prior-effect"),
            leg_key=LEG,
            observation_id=VenueObservationId("prior-discovery"),
        ),
        ObserveVenueStatus(
            input_id=VenueInputId("prior-terminal-input"),
            leg_key=LEG,
            status=VenueAttemptState.CANCELED,
            observation_id=VenueObservationId("prior-terminal"),
            cumulative_quantity=Quantity(0),
            closure_id=ClosureId("prior-closure"),
            evidence_reference=EvidenceReference("prior-terminal-evidence"),
        ),
    )
    book = claimed.state.venue
    execution = EXECUTION
    for item in venue_steps:
        transition = _public_venue_apply_twice(book, execution, item)
        assert transition.disposition is VenueRecoveryDisposition.APPLIED
        book, execution = transition.book, transition.execution

    prior_effect = book.effect(EffectId("prior-effect"))
    assert prior_effect is not None
    closed = _public_venue_apply_twice(
        book,
        execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("prior-close-input"),
            effect_id=EffectId("prior-effect"),
            proof=AcceptanceProof(
                kind=AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
                effect_scope=prior_effect.scope,
                claim_occurrence_id=ClaimOccurrenceId("prior-claim"),
                evidence_reference=EvidenceReference("prior-complete-evidence"),
                evidence_digest=b"\x8a" * 32,
            ),
        ),
    )
    assert closed.disposition is VenueRecoveryDisposition.APPLIED

    closed_state = _forge_venue_predecessor(claimed.state, closed.book)
    target = _create_buy(module, closed_state, label="target")
    assert target.disposition is disposition_type.APPLIED

    late = _public_venue_apply_twice(
        target.state.venue,
        closed.execution,
        DiscoverVenueLeg(
            input_id=VenueInputId("prior-late-discover-input"),
            effect_id=EffectId("prior-effect"),
            leg_key=VenueLegKey(
                broker=BROKER,
                environment=ENVIRONMENT,
                account=ACCOUNT,
                order_id=OrderId("authority-late-leg"),
            ),
            observation_id=VenueObservationId("prior-late-discovery"),
        ),
    )
    assert late.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    uncertain = _forge_venue_predecessor(target.state, late.book)
    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("target-with-sibling-claim-input"),
        effect_id=EffectId("target-effect"),
        claim_occurrence_id=ClaimOccurrenceId("target-with-sibling-claim"),
    )

    refused = _authority_apply_twice(
        module,
        uncertain,
        late.execution,
        claim,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.VENUE_UNCERTAIN
    assert refused.state == uncertain
    assert refused.state.budget.remaining == target.state.budget.remaining
    assert refused.fresh_claim is None


def test_target_exemption_never_hides_a_safely_local_sibling() -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    initial = _forge_positive_predecessor(module, remaining=4, reserve=1)
    target = _create_buy(module, initial, label="local-target")
    sibling = RequestedEffect(
        input_id=VenueInputId("local-sibling-request-input"),
        effect_id=EffectId("local-sibling-effect"),
        request_occurrence_id=RequestOccurrenceId("local-sibling-occurrence"),
        mandate_id=MandateId("local-sibling-mandate"),
        kind=EffectKind.SUBMIT,
        client_order_id=ClientOrderId("local-sibling-client"),
        symbol_id=SYMBOL,
        side=ExecutionSide.BUY,
        quantity=Quantity(1),
        economic_scope=b"local-sibling-scope",
        target_leg_key=None,
    )
    sibling_transition = _private_venue_apply(
        target.state.venue,
        EXECUTION,
        sibling,
    )
    with_sibling = _forge_venue_predecessor(
        target.state,
        sibling_transition.book,
    )
    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("local-target-claim-input"),
        effect_id=EffectId("local-target-effect"),
        claim_occurrence_id=ClaimOccurrenceId("local-target-claim"),
    )
    refused = _authority_apply_twice(
        module,
        with_sibling,
        EXECUTION,
        claim,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.VENUE_UNCERTAIN
    assert refused.state == with_sibling
    assert refused.state.budget.remaining == 4
    assert refused.fresh_claim is None


def test_different_symbol_reconciliation_epoch_blocks_final_claim_lazily() -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    initial = _forge_positive_predecessor(module, remaining=4, reserve=1)
    target = _create_buy(module, initial, label="epoch-target")
    msft_scope = PositionScope(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        symbol_id=OTHER_SYMBOL,
    )
    msft_execution = ExecutionSnapshot.flat(msft_scope)
    registered_msft = _private_venue_apply(
        target.state.venue,
        msft_execution,
        RequestedEffect(
            input_id=VenueInputId("epoch-msft-request-input"),
            effect_id=EffectId("epoch-msft-effect"),
            request_occurrence_id=RequestOccurrenceId("epoch-msft-occurrence"),
            mandate_id=MandateId("epoch-msft-mandate"),
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId("epoch-msft-client"),
            symbol_id=OTHER_SYMBOL,
            side=ExecutionSide.BUY,
            quantity=Quantity(1),
            economic_scope=b"epoch-msft-scope",
            target_leg_key=None,
        ),
    )
    msft_ahead = _advanced_same_scope_execution(
        label="epoch-msft-ahead",
        symbol_id=OTHER_SYMBOL,
    )
    before_epoch = registered_msft.book._account_authority_epoch
    caught_up = _public_venue_apply_twice(
        registered_msft.book,
        EXECUTION,
        CatchUpExecutionRegistry(
            input_id=VenueInputId("epoch-msft-catch-up-input"),
            target_checkpoint=VenueExecutionCheckpoint.from_execution(EXECUTION),
            prior_account_registry_count=(
                registered_msft.book.execution_registry_count
            ),
            prior_account_registry_commitment=(
                registered_msft.book.execution_registry_commitment
            ),
            prior_source_binding=registered_msft.book.execution_binding(msft_scope),
            source_execution=msft_ahead,
        ),
    )
    assert caught_up.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert caught_up.execution.position.scope == EXECUTION.position.scope
    assert caught_up.execution.account_reconciliation_required is True
    assert caught_up.book._account_authority_epoch == before_epoch + 1

    clean_execution = _bind_execution_reconciliation_cursor(
        EXECUTION,
        transition_count=caught_up.execution.reconciliation_transition_count,
        transition_head=caught_up.execution.reconciliation_transition_head,
        account_reconciliation_required=False,
    )
    assert clean_execution.account_reconciliation_required is False
    import app.execution_core.venue as venue

    cached_view = venue._venue_authority_view(
        caught_up.book,
        clean_execution,
        EXECUTION.position.scope,
        EffectId("epoch-target-effect"),
    )
    assert cached_view.account_reconciliation_clear is False

    restricted = _forge_venue_predecessor(target.state, caught_up.book)
    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("epoch-target-claim-input"),
        effect_id=EffectId("epoch-target-effect"),
        claim_occurrence_id=ClaimOccurrenceId("epoch-target-claim"),
    )
    refused = _authority_apply_twice(
        module,
        restricted,
        clean_execution,
        claim,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.ACCOUNT_RECONCILIATION_REQUIRED
    assert refused.state == restricted
    assert refused.state.budget.remaining == 4
    assert refused.fresh_claim is None


@pytest.mark.parametrize(
    (
        "label",
        "phase",
        "mode",
        "fence",
        "kill_engaged",
        "remaining",
        "reserve",
        "expected_reason",
    ),
    [
        (
            "bootstrapping",
            "BOOTSTRAPPING",
            "ACTIVE",
            "PAPER_MUTATION_ELIGIBLE",
            False,
            3,
            1,
            "PHASE_BLOCKED",
        ),
        (
            "reconciling",
            "RECONCILING",
            "ACTIVE",
            "PAPER_MUTATION_ELIGIBLE",
            False,
            3,
            1,
            "PHASE_BLOCKED",
        ),
        (
            "reducing",
            "SERVING",
            "REDUCING",
            "PAPER_MUTATION_ELIGIBLE",
            False,
            3,
            1,
            "MODE_BLOCKED",
        ),
        (
            "halted",
            "SERVING",
            "HALTED",
            "PAPER_MUTATION_ELIGIBLE",
            False,
            3,
            1,
            "MODE_BLOCKED",
        ),
        (
            "reconciliation-fence",
            "SERVING",
            "ACTIVE",
            "RECONCILIATION_ONLY",
            False,
            3,
            1,
            "SUPERVISOR_FENCE_BLOCKED",
        ),
        (
            "unauthenticated-fence",
            "SERVING",
            "ACTIVE",
            "UNAUTHENTICATED",
            False,
            3,
            1,
            "SUPERVISOR_FENCE_BLOCKED",
        ),
        (
            "kill",
            "SERVING",
            "ACTIVE",
            "PAPER_MUTATION_ELIGIBLE",
            True,
            3,
            1,
            "KILL_ENGAGED",
        ),
        (
            "reserve",
            "SERVING",
            "ACTIVE",
            "PAPER_MUTATION_ELIGIBLE",
            False,
            1,
            1,
            "SAFETY_RESERVE_PROTECTED",
        ),
    ],
)
def test_real_reducer_refuses_buy_when_mode_kill_or_reserve_blocks(
    label: str,
    phase: str,
    mode: str,
    fence: str,
    kill_engaged: bool,
    remaining: int,
    reserve: int,
    expected_reason: str,
) -> None:
    module = _authority_module()
    disposition_type, reason_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
    )
    state = _forge_positive_predecessor(
        module,
        phase=phase,
        mode=mode,
        fence=fence,
        kill_engaged=kill_engaged,
        remaining=remaining,
        reserve=reserve,
    )

    refused = _create_buy(module, state, label=f"blocked-{label}")
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is getattr(reason_type, expected_reason)
    assert refused.state == state
    assert refused.created_effect_ids == ()
    assert refused.fresh_claim is None


@pytest.mark.parametrize("mode", ["ACTIVE", "REDUCING"])
def test_quantity_capped_sell_is_admitted_and_claimed_in_permitted_modes(
    mode: str,
) -> None:
    module = _authority_module()
    disposition_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "ClaimEffect",
        "AuthorityInputId",
    )
    execution = _advanced_same_scope_execution(label=f"sell-{mode.lower()}")
    state = _forge_positive_predecessor(
        module,
        mode=mode,
        remaining=3,
        reserve=1,
    )
    created = _create_effect(
        module,
        state,
        execution,
        label=f"sell-{mode.lower()}",
        side=ExecutionSide.SELL,
    )
    assert created.disposition is disposition_type.APPLIED
    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type(f"sell-{mode.lower()}-claim-input"),
        effect_id=EffectId(f"sell-{mode.lower()}-effect"),
        claim_occurrence_id=ClaimOccurrenceId(f"sell-{mode.lower()}-claim"),
    )
    claimed = _authority_apply_twice(
        module,
        created.state,
        execution,
        claim,
    )
    assert claimed.disposition is disposition_type.APPLIED
    assert claimed.state.budget.remaining == 2
    assert claimed.fresh_claim is not None


@pytest.mark.parametrize(
    ("side", "quantity", "label"),
    [
        (ExecutionSide.BUY, 2, "oversized-long"),
        (ExecutionSide.SELL, 1, "negative-position"),
    ],
)
def test_sell_authority_never_uses_abs_or_silently_clamps_residual(
    side: ExecutionSide,
    quantity: int,
    label: str,
) -> None:
    module = _authority_module()
    disposition_type, reason_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
    )
    execution = _advanced_same_scope_execution(
        side=side,
        quantity=1,
        label=label,
    )
    state = _forge_positive_predecessor(
        module,
        mode="REDUCING",
        remaining=3,
        reserve=1,
    )
    requested_quantity = 2 if side is ExecutionSide.BUY else quantity
    refused = _create_effect(
        module,
        state,
        execution,
        label=label,
        side=ExecutionSide.SELL,
        quantity=requested_quantity,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.RESIDUAL_EXCEEDED
    assert refused.state == state
    assert refused.created_effect_ids == ()
    assert refused.fresh_claim is None


def test_final_sell_claim_rereads_a_legally_shrunk_canonical_residual() -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    execution = _advanced_same_scope_execution(
        quantity=5,
        label="residual-before",
    )
    initial = _forge_positive_predecessor(
        module,
        mode="REDUCING",
        remaining=4,
        reserve=1,
    )
    target = _create_effect(
        module,
        initial,
        execution,
        label="stale-residual-target",
        side=ExecutionSide.SELL,
        quantity=5,
    )
    assert target.disposition is disposition_type.APPLIED

    sibling = RequestedEffect(
        input_id=VenueInputId("residual-sibling-request-input"),
        effect_id=EffectId("residual-sibling-effect"),
        request_occurrence_id=RequestOccurrenceId("residual-sibling-occurrence"),
        mandate_id=MandateId("residual-sibling-mandate"),
        kind=EffectKind.SUBMIT,
        client_order_id=ClientOrderId("residual-sibling-client"),
        symbol_id=SYMBOL,
        side=ExecutionSide.SELL,
        quantity=Quantity(1),
        economic_scope=b"residual-sibling|SELL|1",
        target_leg_key=None,
    )
    requested_sibling = _private_venue_apply(
        target.state.venue,
        execution,
        sibling,
    )
    claimed_sibling = _private_venue_apply(
        requested_sibling.book,
        execution,
        RecordDispatchClaim(
            input_id=VenueInputId("residual-sibling-claim-input"),
            effect_id=sibling.effect_id,
            claim_occurrence_id=ClaimOccurrenceId("residual-sibling-claim"),
        ),
    )
    book = claimed_sibling.book
    for item in (
        RecordTransportOutcome(
            input_id=VenueInputId("residual-sibling-ack-input"),
            effect_id=sibling.effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
        DiscoverVenueLeg(
            input_id=VenueInputId("residual-sibling-discover-input"),
            effect_id=sibling.effect_id,
            leg_key=RESIDUAL_LEG,
            observation_id=VenueObservationId("residual-sibling-discovery"),
        ),
    ):
        transition = _public_venue_apply_twice(book, execution, item)
        assert transition.disposition is VenueRecoveryDisposition.APPLIED
        book = transition.book

    fill_fact = BrokerFillFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("residual-sibling-fill-source"),
        ),
        scope=ExecutionScope(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            order_id=RESIDUAL_LEG.order_id,
            symbol_id=SYMBOL,
            side=ExecutionSide.SELL,
        ),
        root_fill_id=RootFillId("residual-sibling-fill-root"),
        quantity=Quantity(1),
        price=PRICE,
    )
    filled = _public_venue_apply_twice(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("residual-sibling-fill-input"),
            effect_id=sibling.effect_id,
            leg_key=RESIDUAL_LEG,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(1),
            fact=fill_fact,
            evidence_digest=b"\x93" * 32,
            closure_id=None,
            evidence_reference=None,
        ),
    )
    assert filled.disposition is VenueRecoveryDisposition.APPLIED
    assert filled.execution.position.raw_quantity == 4
    terminal = _public_venue_apply_twice(
        filled.book,
        filled.execution,
        ObserveVenueStatus(
            input_id=VenueInputId("residual-sibling-terminal-input"),
            leg_key=RESIDUAL_LEG,
            status=VenueAttemptState.FILLED,
            observation_id=VenueObservationId("residual-sibling-terminal"),
            cumulative_quantity=Quantity(1),
            closure_id=ClosureId("residual-sibling-fill-closure"),
            evidence_reference=EvidenceReference("residual-sibling-fill-evidence"),
        ),
    )
    sibling_effect = terminal.book.effect(sibling.effect_id)
    assert sibling_effect is not None
    closed = _public_venue_apply_twice(
        terminal.book,
        terminal.execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("residual-sibling-close-input"),
            effect_id=sibling.effect_id,
            proof=AcceptanceProof(
                kind=AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
                effect_scope=sibling_effect.scope,
                claim_occurrence_id=ClaimOccurrenceId("residual-sibling-claim"),
                evidence_reference=EvidenceReference(
                    "residual-sibling-complete-evidence"
                ),
                evidence_digest=b"\x94" * 32,
            ),
        ),
    )
    current = _forge_venue_predecessor(target.state, closed.book)
    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("stale-residual-target-claim-input"),
        effect_id=EffectId("stale-residual-target-effect"),
        claim_occurrence_id=ClaimOccurrenceId("stale-residual-target-claim"),
    )
    refused = _authority_apply_twice(
        module,
        current,
        closed.execution,
        claim,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.RESIDUAL_EXCEEDED
    assert refused.state == current
    assert refused.state.budget.remaining == 4
    assert refused.fresh_claim is None


@pytest.mark.parametrize(
    ("mode", "kill_engaged", "expected_reason"),
    [
        ("HALTED", False, "MODE_BLOCKED"),
        ("ACTIVE", True, "KILL_ENGAGED"),
    ],
)
def test_ordinary_sell_cannot_bypass_halt_or_kill(
    mode: str,
    kill_engaged: bool,
    expected_reason: str,
) -> None:
    module = _authority_module()
    disposition_type, reason_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
    )
    execution = _advanced_same_scope_execution(label=f"blocked-sell-{mode.lower()}")
    state = _forge_positive_predecessor(
        module,
        mode=mode,
        kill_engaged=kill_engaged,
        remaining=3,
        reserve=1,
    )
    refused = _create_effect(
        module,
        state,
        execution,
        label=f"blocked-sell-{mode.lower()}",
        side=ExecutionSide.SELL,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is getattr(reason_type, expected_reason)
    assert refused.state == state


@pytest.mark.parametrize(
    ("mode", "fence", "kill_engaged"),
    [
        ("REDUCING", "PAPER_MUTATION_ELIGIBLE", False),
        ("HALTED", "PAPER_MUTATION_ELIGIBLE", False),
        ("ACTIVE", "PAPER_MUTATION_ELIGIBLE", True),
    ],
)
def test_target_bound_cancel_uses_reserved_budget_and_fresh_claim_once(
    mode: str,
    fence: str,
    kill_engaged: bool,
) -> None:
    module = _authority_module()
    disposition_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "ClaimEffect",
        "AuthorityInputId",
    )
    state = _seed_cancellable_buy(
        module,
        mode=mode,
        fence=fence,
        kill_engaged=kill_engaged,
        remaining=1,
        reserve=1,
        label=f"cancel-{mode.lower()}-{kill_engaged}",
    )
    command = _create_command(
        module,
        state,
        label=f"cancel-effect-{mode.lower()}-{kill_engaged}",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    first_create = module.apply_execution_authority_input(state, EXECUTION, command)
    second_create = module.apply_execution_authority_input(state, EXECUTION, command)
    assert second_create == first_create
    assert first_create.disposition is disposition_type.APPLIED
    assert first_create.state.budget.remaining == 1
    assert first_create.created_effect_ids == (command.request.effect_id,)
    assert first_create.state.venue.owners == state.venue.owners

    create_replay = _authority_apply_twice(
        module,
        first_create.state,
        EXECUTION,
        command,
    )
    assert create_replay.disposition is disposition_type.EXACT_REPLAY
    assert create_replay.state == first_create.state
    assert create_replay.created_effect_ids == ()

    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type(
            f"cancel-effect-{mode.lower()}-{kill_engaged}-claim-input"
        ),
        effect_id=command.request.effect_id,
        claim_occurrence_id=ClaimOccurrenceId(
            f"cancel-effect-{mode.lower()}-{kill_engaged}-claim"
        ),
    )
    first_claim = module.apply_execution_authority_input(
        first_create.state,
        EXECUTION,
        claim,
    )
    second_claim = module.apply_execution_authority_input(
        first_create.state,
        EXECUTION,
        claim,
    )
    assert second_claim == first_claim
    assert first_claim.disposition is disposition_type.APPLIED
    assert first_claim.state.budget.remaining == 0
    assert first_claim.fresh_claim is not None
    assert first_claim.fresh_claim.effect_id == command.request.effect_id

    claim_replay = _authority_apply_twice(
        module,
        first_claim.state,
        EXECUTION,
        claim,
    )
    assert claim_replay.disposition is disposition_type.EXACT_REPLAY
    assert claim_replay.state == first_claim.state
    assert claim_replay.fresh_claim is None

    acknowledged = _public_venue_apply_twice(
        first_claim.state.venue,
        EXECUTION,
        RecordTransportOutcome(
            input_id=VenueInputId(
                f"cancel-effect-{mode.lower()}-{kill_engaged}-ack-input"
            ),
            effect_id=command.request.effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    target_attempt = acknowledged.book.active_attempt(LEG)
    assert target_attempt is not None
    assert target_attempt.pending_operation is PendingVenueOperation.CANCEL


def test_cancel_request_conflict_and_exhaustion_are_atomic() -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    state = _seed_cancellable_buy(
        module,
        remaining=0,
        reserve=0,
        label="cancel-exhausted-target",
    )
    command = _create_command(
        module,
        state,
        label="cancel-exhausted",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    created = _authority_apply_twice(module, state, EXECUTION, command)
    assert created.disposition is disposition_type.APPLIED

    changed = replace(
        command,
        request=replace(
            command.request,
            target_leg_key=VenueLegKey(
                broker=BROKER,
                environment=ENVIRONMENT,
                account=ACCOUNT,
                order_id=OrderId("different-cancel-target"),
            ),
        ),
    )
    conflict = _authority_apply_twice(
        module,
        created.state,
        EXECUTION,
        changed,
    )
    assert conflict.disposition is disposition_type.CONFLICT
    assert conflict.state == created.state
    assert conflict.fresh_claim is None

    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("cancel-exhausted-claim-input"),
        effect_id=command.request.effect_id,
        claim_occurrence_id=ClaimOccurrenceId("cancel-exhausted-claim"),
    )
    refused = _authority_apply_twice(
        module,
        created.state,
        EXECUTION,
        claim,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.REQUEST_BUDGET_EXHAUSTED
    assert refused.state == created.state
    assert refused.state.budget.remaining == 0
    retained = refused.state.venue.effect(command.request.effect_id)
    assert retained is not None
    assert retained.state is BrokerEffectState.REQUESTED
    assert retained.claim_occurrence_id is None
    assert refused.fresh_claim is None


def test_one_live_target_accepts_only_one_cancel_intent_before_outcome() -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    state = _seed_cancellable_buy(
        module,
        remaining=4,
        reserve=1,
        label="single-cancel-target",
    )
    first = _create_effect(
        module,
        state,
        EXECUTION,
        label="single-cancel-first",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    assert first.disposition is disposition_type.APPLIED

    second_before_claim = _create_effect(
        module,
        first.state,
        EXECUTION,
        label="single-cancel-second-before-claim",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    assert second_before_claim.disposition is disposition_type.REFUSED
    assert second_before_claim.reason is reason_type.VENUE_UNCERTAIN
    assert second_before_claim.state == first.state

    claimed = _authority_apply_twice(
        module,
        first.state,
        EXECUTION,
        claim_type(
            input_id=authority_input_type("single-cancel-first-claim-input"),
            effect_id=EffectId("single-cancel-first-effect"),
            claim_occurrence_id=ClaimOccurrenceId("single-cancel-first-claim"),
        ),
    )
    assert claimed.disposition is disposition_type.APPLIED
    second_after_claim = _create_effect(
        module,
        claimed.state,
        EXECUTION,
        label="single-cancel-second-after-claim",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    assert second_after_claim.disposition is disposition_type.REFUSED
    assert second_after_claim.reason is reason_type.VENUE_UNCERTAIN
    assert second_after_claim.state == claimed.state


def test_definitively_rejected_cancel_releases_its_exact_target() -> None:
    module = _authority_module()
    disposition_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "ClaimEffect",
        "AuthorityInputId",
    )
    state = _seed_cancellable_buy(
        module,
        remaining=4,
        reserve=1,
        label="rejected-cancel-target",
    )
    first = _create_effect(
        module,
        state,
        EXECUTION,
        label="rejected-cancel-first",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    claimed = _authority_apply_twice(
        module,
        first.state,
        EXECUTION,
        claim_type(
            input_id=authority_input_type("rejected-cancel-first-claim-input"),
            effect_id=EffectId("rejected-cancel-first-effect"),
            claim_occurrence_id=ClaimOccurrenceId("rejected-cancel-first-claim"),
        ),
    )
    rejected = _public_venue_apply_twice(
        claimed.state.venue,
        EXECUTION,
        RecordTransportOutcome(
            input_id=VenueInputId("rejected-cancel-first-outcome-input"),
            effect_id=EffectId("rejected-cancel-first-effect"),
            state=BrokerEffectState.REJECTED,
        ),
    )
    current = _forge_venue_predecessor(claimed.state, rejected.book)

    retry = _create_effect(
        module,
        current,
        EXECUTION,
        label="rejected-cancel-retry",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    assert retry.disposition is disposition_type.APPLIED
    assert retry.created_effect_ids == (EffectId("rejected-cancel-retry-effect"),)


def test_native_replace_remains_disabled_after_valid_target_binding() -> None:
    module = _authority_module()
    disposition_type, reason_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
    )
    state = _seed_cancellable_buy(module, label="replace-target")
    refused = _create_effect(
        module,
        state,
        EXECUTION,
        label="replace-disabled",
        side=ExecutionSide.BUY,
        kind=EffectKind.REPLACE,
        target_leg_key=LEG,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.NATIVE_REPLACE_DISABLED
    assert refused.state == state


def test_exact_emergency_sell_consumes_one_grant_and_reserved_request_once() -> None:
    module = _authority_module()
    disposition_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "ClaimEffect",
        "AuthorityInputId",
    )
    execution = _advanced_same_scope_execution(label="emergency-success")
    halted = _forge_positive_predecessor(
        module,
        mode="HALTED",
        kill_engaged=True,
        remaining=1,
        reserve=1,
    )
    state, grant_id = _forge_emergency_grant(
        module,
        halted,
        label="emergency-success",
    )
    created = _create_effect(
        module,
        state,
        execution,
        label="emergency-success",
        side=ExecutionSide.SELL,
        emergency_grant_id=grant_id,
    )
    assert created.disposition is disposition_type.APPLIED
    assert created.state.budget.remaining == 1
    assert not created.state._grant_consumed(grant_id)

    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("emergency-success-claim-input"),
        effect_id=EffectId("emergency-success-effect"),
        claim_occurrence_id=ClaimOccurrenceId("emergency-success-claim"),
    )
    first = module.apply_execution_authority_input(
        created.state,
        execution,
        claim,
    )
    second = module.apply_execution_authority_input(
        created.state,
        execution,
        claim,
    )
    assert second == first
    assert first.disposition is disposition_type.APPLIED
    assert first.state.budget.remaining == 0
    assert first.state._grant_consumed(grant_id)
    assert first.state._emergency_grant is None
    assert first.fresh_claim is not None

    replay = _authority_apply_twice(module, first.state, execution, claim)
    assert replay.disposition is disposition_type.EXACT_REPLAY
    assert replay.state == first.state
    assert replay.state.budget.remaining == 0
    assert replay.state._grant_consumed(grant_id)
    assert replay.fresh_claim is None


def test_cancel_cannot_carry_or_consume_an_emergency_sell_grant() -> None:
    module = _authority_module()
    disposition_type, reason_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
    )
    base = _seed_cancellable_buy(
        module,
        remaining=2,
        reserve=1,
        label="cancel-grant-target",
    )
    state, grant_id = _forge_emergency_grant(
        module,
        base,
        label="cancel-grant",
    )
    refused = _create_effect(
        module,
        state,
        EXECUTION,
        label="cancel-with-grant",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
        emergency_grant_id=grant_id,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.EMERGENCY_GRANT_REDUCE_ONLY
    assert refused.state == state
    assert refused.state._emergency_grant == state._emergency_grant
    assert not refused.state._grant_consumed(grant_id)
    assert refused.state.budget == state.budget
    assert refused.created_effect_ids == ()
    assert refused.fresh_claim is None


@pytest.mark.parametrize(
    ("case", "grant_changes", "command_grant"),
    [
        ("ambient", {}, None),
        ("account", {"account": AccountId("other-account")}, "stored"),
        ("symbol", {"symbol_id": OTHER_SYMBOL}, "stored"),
        ("session", {"session": "other-session"}, "stored"),
        ("id", {}, "different"),
    ],
)
def test_emergency_grant_must_match_exact_command_scope_without_consumption(
    case: str,
    grant_changes: dict[str, object],
    command_grant: str | None,
) -> None:
    module = _authority_module()
    disposition_type, reason_type, grant_id_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "EmergencyGrantId",
    )
    execution = _advanced_same_scope_execution(label=f"grant-{case}")
    halted = _forge_positive_predecessor(
        module,
        mode="HALTED",
        kill_engaged=True,
        remaining=1,
        reserve=1,
    )
    state, stored_grant_id = _forge_emergency_grant(  # type: ignore[arg-type]
        module,
        halted,
        label=f"grant-{case}",
        **grant_changes,
    )
    selected_grant = (
        stored_grant_id
        if command_grant == "stored"
        else (
            grant_id_type(f"grant-{case}-different")
            if command_grant == "different"
            else None
        )
    )
    refused = _create_effect(
        module,
        state,
        execution,
        label=f"grant-{case}",
        side=ExecutionSide.SELL,
        emergency_grant_id=selected_grant,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason in {
        reason_type.EMERGENCY_GRANT_REQUIRED,
        reason_type.EMERGENCY_GRANT_MISMATCH,
    }
    assert refused.state == state
    assert refused.state.budget.remaining == 1
    assert not refused.state._grant_consumed(stored_grant_id)


def test_emergency_grant_is_reduce_only_and_cannot_bypass_venue_uncertainty() -> None:
    module = _authority_module()
    disposition_type, reason_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
    )
    execution = _advanced_same_scope_execution(label="grant-boundary")
    halted = _forge_positive_predecessor(
        module,
        mode="HALTED",
        kill_engaged=True,
        remaining=2,
        reserve=1,
    )
    state, grant_id = _forge_emergency_grant(
        module,
        halted,
        label="grant-buy",
    )
    buy = _create_effect(
        module,
        state,
        execution,
        label="grant-buy",
        side=ExecutionSide.BUY,
        emergency_grant_id=grant_id,
    )
    assert buy.disposition is disposition_type.REFUSED
    assert buy.reason is reason_type.EMERGENCY_GRANT_REDUCE_ONLY
    assert not buy.state._grant_consumed(grant_id)

    uncertain_base = _seed_cancellable_buy(
        module,
        execution=execution,
        mode="HALTED",
        kill_engaged=True,
        remaining=2,
        reserve=1,
        label="grant-uncertain-target",
    )
    uncertain, uncertain_grant_id = _forge_emergency_grant(
        module,
        uncertain_base,
        label="grant-uncertain",
    )
    sell = _create_effect(
        module,
        uncertain,
        execution,
        label="grant-uncertain",
        side=ExecutionSide.SELL,
        emergency_grant_id=uncertain_grant_id,
    )
    assert sell.disposition is disposition_type.REFUSED
    assert sell.reason is reason_type.VENUE_UNCERTAIN
    assert sell.state == uncertain
    assert sell.state.budget.remaining == 2
    assert not sell.state._grant_consumed(uncertain_grant_id)


def test_final_claim_rechecks_emergency_grant_without_partial_consumption() -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    execution = _advanced_same_scope_execution(label="grant-regate")
    halted = _forge_positive_predecessor(
        module,
        mode="HALTED",
        kill_engaged=True,
        remaining=1,
        reserve=1,
    )
    state, grant_id = _forge_emergency_grant(
        module,
        halted,
        label="grant-regate",
    )
    created = _create_effect(
        module,
        state,
        execution,
        label="grant-regate",
        side=ExecutionSide.SELL,
        emergency_grant_id=grant_id,
    )
    drifted, drifted_grant_id = _forge_emergency_grant(
        module,
        created.state,
        label="grant-regate-drifted",
    )
    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("grant-regate-claim-input"),
        effect_id=EffectId("grant-regate-effect"),
        claim_occurrence_id=ClaimOccurrenceId("grant-regate-claim"),
    )
    refused = _authority_apply_twice(
        module,
        drifted,
        execution,
        claim,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.EMERGENCY_GRANT_MISMATCH
    assert refused.state == drifted
    assert refused.state.budget.remaining == 1
    assert not refused.state._grant_consumed(grant_id)
    assert not refused.state._grant_consumed(drifted_grant_id)
    assert refused.fresh_claim is None


def test_emergency_final_claim_rechecks_late_venue_uncertainty() -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    execution = _advanced_same_scope_execution(
        quantity=3,
        label="emergency-late-uncertainty",
    )
    halted = _forge_positive_predecessor(
        module,
        mode="HALTED",
        kill_engaged=True,
        remaining=2,
        reserve=1,
    )
    state, grant_id = _forge_emergency_grant(
        module,
        halted,
        label="emergency-late-uncertainty",
    )
    created = _create_effect(
        module,
        state,
        execution,
        label="emergency-late-uncertainty",
        side=ExecutionSide.SELL,
        quantity=3,
        emergency_grant_id=grant_id,
    )
    assert created.disposition is disposition_type.APPLIED
    sibling = _private_venue_apply(
        created.state.venue,
        execution,
        RequestedEffect(
            input_id=VenueInputId("emergency-late-sibling-input"),
            effect_id=EffectId("emergency-late-sibling-effect"),
            request_occurrence_id=RequestOccurrenceId(
                "emergency-late-sibling-occurrence"
            ),
            mandate_id=MandateId("emergency-late-sibling-mandate"),
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId("emergency-late-sibling-client"),
            symbol_id=SYMBOL,
            side=ExecutionSide.BUY,
            quantity=Quantity(1),
            economic_scope=b"emergency-late-sibling|BUY|1",
            target_leg_key=None,
        ),
    )
    drifted = _forge_venue_predecessor(created.state, sibling.book)
    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("emergency-late-uncertainty-claim-input"),
        effect_id=EffectId("emergency-late-uncertainty-effect"),
        claim_occurrence_id=ClaimOccurrenceId("emergency-late-uncertainty-claim"),
    )
    refused = _authority_apply_twice(module, drifted, execution, claim)
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.VENUE_UNCERTAIN
    assert refused.state == drifted
    assert refused.state.budget.remaining == 2
    assert not refused.state._grant_consumed(grant_id)
    assert refused.fresh_claim is None


def test_emergency_final_claim_rechecks_a_canonically_shrunk_residual() -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    execution = _advanced_same_scope_execution(
        quantity=3,
        label="emergency-residual-before",
    )
    halted = _forge_positive_predecessor(
        module,
        mode="HALTED",
        kill_engaged=True,
        remaining=2,
        reserve=1,
    )
    state, grant_id = _forge_emergency_grant(
        module,
        halted,
        label="emergency-residual",
    )
    created = _create_effect(
        module,
        state,
        execution,
        label="emergency-residual",
        side=ExecutionSide.SELL,
        quantity=3,
        emergency_grant_id=grant_id,
    )
    assert created.disposition is disposition_type.APPLIED
    book, shrunk_execution = _apply_closed_sell_fill(
        created.state.venue,
        execution,
        label="emergency-residual-shrink",
        leg_key=RESIDUAL_LEG,
    )
    assert shrunk_execution.position.raw_quantity == 2
    drifted = _forge_venue_predecessor(created.state, book)
    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("emergency-residual-claim-input"),
        effect_id=EffectId("emergency-residual-effect"),
        claim_occurrence_id=ClaimOccurrenceId("emergency-residual-claim"),
    )
    refused = _authority_apply_twice(
        module,
        drifted,
        shrunk_execution,
        claim,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.RESIDUAL_EXCEEDED
    assert refused.state == drifted
    assert refused.state.budget.remaining == 2
    assert not refused.state._grant_consumed(grant_id)
    assert refused.fresh_claim is None


@pytest.mark.parametrize(
    "fence",
    ["RECONCILIATION_ONLY", "PAPER_MUTATION_ELIGIBLE"],
)
def test_query_claim_uses_shared_reserved_budget_without_creating_effect(
    fence: str,
) -> None:
    module = _authority_module()
    (
        disposition_type,
        authority_input_type,
        query_id_type,
        query_kind_type,
        query_type,
    ) = _required(
        module,
        "AuthorityDisposition",
        "AuthorityInputId",
        "QueryClaimId",
        "AuthorityQueryKind",
        "ClaimBrokerQuery",
    )
    state = _forge_positive_predecessor(
        module,
        phase="RECONCILING",
        mode="HALTED",
        fence=fence,
        kill_engaged=True,
        remaining=1,
        reserve=1,
    )
    query = query_type(  # type: ignore[operator]
        input_id=authority_input_type("query-input"),
        query_claim_id=query_id_type("query-1"),
        symbol_id=SYMBOL,
        kind=query_kind_type.QUERY,
    )
    venue_before = state.venue

    first_claimed = module.apply_execution_authority_input(state, EXECUTION, query)
    second_claimed = module.apply_execution_authority_input(state, EXECUTION, query)
    assert second_claimed == first_claimed
    claimed = first_claimed
    assert claimed.disposition is disposition_type.APPLIED
    assert claimed.created_effect_ids == ()
    assert claimed.fresh_claim is not None
    assert claimed.fresh_claim.query_claim_id == query.query_claim_id
    assert claimed.state.budget.remaining == 0
    assert claimed.state.venue == venue_before
    assert claimed.state.venue.effects == ()
    assert claimed.state.venue.owners == ()
    assert claimed.state.venue.active_attempts == ()

    replay = _authority_apply_twice(
        module,
        claimed.state,
        EXECUTION,
        query,
    )
    assert replay.disposition is disposition_type.EXACT_REPLAY
    assert replay.fresh_claim is None
    assert replay.state == claimed.state
    assert replay.state.venue == venue_before


def test_query_exhaustion_and_identity_conflicts_are_atomic() -> None:
    module = _authority_module()
    (
        disposition_type,
        reason_type,
        authority_input_type,
        query_id_type,
        query_kind_type,
        query_type,
    ) = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "AuthorityInputId",
        "QueryClaimId",
        "AuthorityQueryKind",
        "ClaimBrokerQuery",
    )
    exhausted = _forge_positive_predecessor(
        module,
        phase="RECONCILING",
        mode="HALTED",
        fence="RECONCILIATION_ONLY",
        kill_engaged=True,
        remaining=0,
        reserve=0,
    )
    query = query_type(  # type: ignore[operator]
        input_id=authority_input_type("query-atomic-input"),
        query_claim_id=query_id_type("query-atomic"),
        symbol_id=SYMBOL,
        kind=query_kind_type.QUERY,
    )
    refused = _authority_apply_twice(module, exhausted, EXECUTION, query)
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.REQUEST_BUDGET_EXHAUSTED
    assert refused.state == exhausted
    assert refused.state.venue == exhausted.venue
    assert refused.fresh_claim is None

    eligible = _forge_positive_predecessor(
        module,
        phase="RECONCILING",
        mode="HALTED",
        fence="RECONCILIATION_ONLY",
        kill_engaged=True,
        remaining=1,
        reserve=1,
    )
    applied = _authority_apply_twice(module, eligible, EXECUTION, query)
    assert applied.disposition is disposition_type.APPLIED
    assert applied.state.budget.remaining == 0
    assert applied.state.venue == eligible.venue

    changed_payload = replace(query, kind=query_kind_type.RECONCILE)
    input_conflict = _authority_apply_twice(
        module,
        applied.state,
        EXECUTION,
        changed_payload,
    )
    assert input_conflict.disposition is disposition_type.CONFLICT
    assert input_conflict.state == applied.state
    assert input_conflict.fresh_claim is None

    reused_claim = replace(
        query,
        input_id=authority_input_type("query-atomic-reused-claim-input"),
    )
    claim_conflict = _authority_apply_twice(
        module,
        applied.state,
        EXECUTION,
        reused_claim,
    )
    assert claim_conflict.disposition is disposition_type.CONFLICT
    assert claim_conflict.state == applied.state
    assert claim_conflict.state.budget.remaining == 0
    assert claim_conflict.state.venue == eligible.venue
    assert claim_conflict.fresh_claim is None


def test_unauthenticated_fence_refuses_query_without_debit() -> None:
    module = _authority_module()
    (
        disposition_type,
        reason_type,
        authority_input_type,
        query_id_type,
        query_kind_type,
        query_type,
    ) = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "AuthorityInputId",
        "QueryClaimId",
        "AuthorityQueryKind",
        "ClaimBrokerQuery",
    )
    state = _forge_positive_predecessor(
        module,
        phase="RECONCILING",
        mode="HALTED",
        fence="UNAUTHENTICATED",
        kill_engaged=True,
        remaining=1,
        reserve=1,
    )
    query = query_type(  # type: ignore[operator]
        input_id=authority_input_type("unauthenticated-query-input"),
        query_claim_id=query_id_type("unauthenticated-query"),
        symbol_id=SYMBOL,
        kind=query_kind_type.RECONCILE,
    )

    first = module.apply_execution_authority_input(state, EXECUTION, query)
    second = module.apply_execution_authority_input(state, EXECUTION, query)
    assert second == first
    assert first.disposition is disposition_type.REFUSED
    assert first.reason is reason_type.SUPERVISOR_FENCE_BLOCKED
    assert first.state == state
    assert first.state.budget.remaining == 1
    assert first.fresh_claim is None


def test_reconciliation_only_fence_refuses_mutation_creation_and_final_claim() -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    mutation_state = _forge_positive_predecessor(
        module,
        fence="RECONCILIATION_ONLY",
        remaining=3,
        reserve=1,
    )
    refused_create = _create_buy(module, mutation_state, label="reconcile-fence")
    assert refused_create.disposition is disposition_type.REFUSED
    assert refused_create.state == mutation_state

    cancel_base = _seed_cancellable_buy(
        module,
        mode="REDUCING",
        remaining=3,
        reserve=1,
        label="reconciliation-fence-cancel-target",
    )
    reconciliation_cancel = _forge_positive_predecessor(
        module,
        predecessor=cancel_base,
        mode="REDUCING",
        fence="RECONCILIATION_ONLY",
        remaining=3,
        reserve=1,
    )
    refused_cancel = _create_effect(
        module,
        reconciliation_cancel,
        EXECUTION,
        label="reconciliation-fence-cancel",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    assert refused_cancel.disposition is disposition_type.REFUSED
    assert refused_cancel.reason is reason_type.SUPERVISOR_FENCE_BLOCKED
    assert refused_cancel.state == reconciliation_cancel

    eligible_cancel = _create_effect(
        module,
        cancel_base,
        EXECUTION,
        label="reconciliation-fence-cancel-regate",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    assert eligible_cancel.disposition is disposition_type.APPLIED
    cancel_regated = _forge_positive_predecessor(
        module,
        predecessor=eligible_cancel.state,
        mode="REDUCING",
        fence="RECONCILIATION_ONLY",
        remaining=3,
        reserve=1,
    )
    cancel_claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("reconciliation-fence-cancel-regate-claim-input"),
        effect_id=EffectId("reconciliation-fence-cancel-regate-effect"),
        claim_occurrence_id=ClaimOccurrenceId(
            "reconciliation-fence-cancel-regate-claim"
        ),
    )
    target_before = cancel_regated.venue.active_attempt(LEG)
    refused_cancel_claim = _authority_apply_twice(
        module,
        cancel_regated,
        EXECUTION,
        cancel_claim,
    )
    assert refused_cancel_claim.disposition is disposition_type.REFUSED
    assert refused_cancel_claim.reason is reason_type.SUPERVISOR_FENCE_BLOCKED
    assert refused_cancel_claim.state == cancel_regated
    assert refused_cancel_claim.state.budget.remaining == 3
    assert refused_cancel_claim.state.venue.active_attempt(LEG) == target_before
    assert refused_cancel_claim.fresh_claim is None

    eligible = _forge_positive_predecessor(module, remaining=3, reserve=1)
    created = _create_buy(module, eligible, label="fence-regate")
    regated = _forge_positive_predecessor(
        module,
        predecessor=created.state,
        fence="RECONCILIATION_ONLY",
        remaining=3,
        reserve=1,
    )
    claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("fence-regate-claim-input"),
        effect_id=EffectId("fence-regate-effect"),
        claim_occurrence_id=ClaimOccurrenceId("fence-regate-claim"),
    )
    refused_claim = _authority_apply_twice(
        module,
        regated,
        EXECUTION,
        claim,
    )
    assert refused_claim.disposition is disposition_type.REFUSED
    assert refused_claim.state == regated
    assert refused_claim.state.budget.remaining == 3
    assert refused_claim.fresh_claim is None


def test_public_genesis_cannot_claim_query_or_effect() -> None:
    module = _authority_module()
    (
        disposition_type,
        authority_input_type,
        query_id_type,
        query_kind_type,
        query_type,
        claim_type,
    ) = _required(
        module,
        "AuthorityDisposition",
        "AuthorityInputId",
        "QueryClaimId",
        "AuthorityQueryKind",
        "ClaimBrokerQuery",
        "ClaimEffect",
    )
    state = _genesis(module)
    commands = (
        query_type(  # type: ignore[operator]
            input_id=authority_input_type("genesis-query-input"),
            query_claim_id=query_id_type("genesis-query"),
            symbol_id=SYMBOL,
            kind=query_kind_type.QUERY,
        ),
        claim_type(  # type: ignore[operator]
            input_id=authority_input_type("genesis-claim-input"),
            effect_id=EffectId("missing-effect"),
            claim_occurrence_id=ClaimOccurrenceId("missing-claim"),
        ),
    )
    for command in commands:
        first = module.apply_execution_authority_input(state, EXECUTION, command)
        second = module.apply_execution_authority_input(state, EXECUTION, command)
        assert first.disposition is disposition_type.REFUSED
        assert second == first
        assert first.state == state
        assert first.fresh_claim is None


def test_manual_control_commands_have_exact_attribution_shape() -> None:
    module = _authority_module()
    (
        authority_input_type,
        session_type,
        flatten_id_type,
        engage_kill_type,
        begin_flatten_type,
        advance_flatten_type,
    ) = _required(
        module,
        "AuthorityInputId",
        "SessionId",
        "ManualFlattenId",
        "EngageKill",
        "BeginManualFlatten",
        "AdvanceManualFlatten",
    )
    actor = ActorId("operator")
    evidence = EvidenceReference("ticket-1")
    kill = engage_kill_type(  # type: ignore[operator]
        input_id=authority_input_type("kill-input"),
        actor=actor,
        reason="operator halt",
        evidence_reference=evidence,
    )
    begin = begin_flatten_type(  # type: ignore[operator]
        input_id=authority_input_type("flatten-input"),
        flatten_id=flatten_id_type("flatten-1"),
        session_id=session_type("session-1"),
        symbol_id=SYMBOL,
        actor=actor,
        reason="manual flatten",
        evidence_reference=evidence,
        emergency_grant_id=None,
    )
    advance = advance_flatten_type(  # type: ignore[operator]
        input_id=authority_input_type("advance-input"),
        flatten_id=flatten_id_type("flatten-1"),
    )
    assert kill.actor == actor
    assert begin.symbol_id == SYMBOL
    assert advance.flatten_id == begin.flatten_id


def test_authority_safety_enums_are_explicitly_total() -> None:
    module = _authority_module()
    (
        engine_phase_type,
        trading_mode_type,
        supervisor_fence_type,
        query_kind_type,
        disposition_type,
        reason_type,
        flatten_phase_type,
    ) = _required(
        module,
        "EnginePhase",
        "TradingMode",
        "SupervisorFence",
        "AuthorityQueryKind",
        "AuthorityDisposition",
        "AuthorityReason",
        "_FlattenPhase",
    )
    contracts = (
        (engine_phase_type, {"BOOTSTRAPPING", "RECONCILING", "SERVING"}),
        (trading_mode_type, {"ACTIVE", "REDUCING", "HALTED"}),
        (
            supervisor_fence_type,
            {
                "UNAUTHENTICATED",
                "RECONCILIATION_ONLY",
                "PAPER_MUTATION_ELIGIBLE",
            },
        ),
        (query_kind_type, {"QUERY", "RECONCILE"}),
        (disposition_type, {"APPLIED", "REFUSED", "EXACT_REPLAY", "CONFLICT"}),
        (
            reason_type,
            {
                "PHASE_BLOCKED",
                "MODE_BLOCKED",
                "SUPERVISOR_FENCE_BLOCKED",
                "KILL_ENGAGED",
                "SAFETY_RESERVE_PROTECTED",
                "REQUEST_BUDGET_EXHAUSTED",
                "SESSION_MISMATCH",
                "EXECUTION_BINDING_MISMATCH",
                "ACCOUNT_RECONCILIATION_REQUIRED",
                "VENUE_UNCERTAIN",
                "RESIDUAL_EXCEEDED",
                "NATIVE_REPLACE_DISABLED",
                "EMERGENCY_GRANT_REQUIRED",
                "EMERGENCY_GRANT_MISMATCH",
                "EMERGENCY_GRANT_REDUCE_ONLY",
                "EFFECT_UNKNOWN",
                "MANUAL_FLATTEN_INVALID",
            },
        ),
        (flatten_phase_type, {"WAITING", "READY", "SELL_CREATED"}),
        (ExecutionSide, {"BUY", "SELL"}),
        (EffectKind, {"SUBMIT", "CANCEL", "REPLACE"}),
        (AcceptanceSetState, {"OPEN", "CLOSED", "INVALIDATED"}),
        (
            VenueRecoveryDisposition,
            {
                "APPLIED",
                "EXACT_REPLAY",
                "CONFLICT",
                "RECONCILIATION_REQUIRED",
                "REFUSED",
            },
        ),
    )

    for enum_type, expected_names in contracts:
        assert set(enum_type.__members__) == expected_names


def test_authority_value_objects_reject_invalid_exact_fields() -> None:
    module = _authority_module()
    authority_input_type, create_type, kill_type = _required(
        module,
        "AuthorityInputId",
        "CreateBrokerEffect",
        "EngageKill",
    )
    state = _forge_positive_predecessor(module)
    request = _effect_request(
        module,
        "invalid-exact-fields",
        side=ExecutionSide.BUY,
        quantity=1,
    )
    kill_kwargs = {
        "actor": ActorId("invalid-exact-fields-operator"),
        "reason": "exact validation",
        "evidence_reference": EvidenceReference("invalid-exact-fields-evidence"),
    }

    with pytest.raises(
        TypeError,
        match="input_id must be the exact AuthorityInputId type",
    ):
        kill_type(input_id="wrong-input-type", **kill_kwargs)  # type: ignore[operator]

    with pytest.raises(
        TypeError,
        match="manual_flatten_id must be ManualFlattenId or None",
    ):
        create_type(  # type: ignore[operator]
            input_id=authority_input_type("invalid-optional-type-input"),
            session_id=state.session_id,
            request=request,
            manual_flatten_id="wrong-flatten-type",
            emergency_grant_id=None,
        )

    with pytest.raises(TypeError, match="reason must be a string"):
        kill_type(  # type: ignore[operator]
            input_id=authority_input_type("invalid-reason-type-input"),
            **{**kill_kwargs, "reason": 7},
        )

    with pytest.raises(ValueError, match="reason must be nonblank"):
        kill_type(  # type: ignore[operator]
            input_id=authority_input_type("invalid-blank-reason-input"),
            **{**kill_kwargs, "reason": "   "},
        )

    with pytest.raises(ValueError, match="quantity must be positive"):
        replace(request, quantity=Quantity(0))

    with pytest.raises(TypeError, match="economic_scope must be bytes"):
        replace(request, economic_scope=bytearray(b"wrong-type"))

    with pytest.raises(ValueError, match="economic_scope must be nonempty"):
        replace(request, economic_scope=b"")


def test_create_and_query_refuse_scope_or_session_mismatch() -> None:
    module = _authority_module()
    (
        disposition_type,
        reason_type,
        authority_input_type,
        session_type,
        create_type,
        query_claim_id_type,
        query_kind_type,
        query_type,
    ) = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "AuthorityInputId",
        "SessionId",
        "CreateBrokerEffect",
        "QueryClaimId",
        "AuthorityQueryKind",
        "ClaimBrokerQuery",
    )
    state = _forge_positive_predecessor(module, remaining=4, reserve=1)

    other_symbol_request = replace(
        _effect_request(
            module,
            "scope-mismatch-create",
            side=ExecutionSide.BUY,
            quantity=1,
        ),
        symbol_id=OTHER_SYMBOL,
    )
    scope_command = create_type(  # type: ignore[operator]
        input_id=authority_input_type("scope-mismatch-create-input"),
        session_id=state.session_id,
        request=other_symbol_request,
        manual_flatten_id=None,
        emergency_grant_id=None,
    )
    scope_refused = _authority_apply_twice(module, state, EXECUTION, scope_command)
    assert scope_refused.disposition is disposition_type.REFUSED
    assert scope_refused.reason is reason_type.EXECUTION_BINDING_MISMATCH
    assert scope_refused.state == state
    assert scope_refused.created_effect_ids == ()

    session_command = replace(
        _create_command(
            module,
            state,
            label="session-mismatch-create",
            side=ExecutionSide.BUY,
        ),
        session_id=session_type("other-session"),
    )
    session_refused = _authority_apply_twice(module, state, EXECUTION, session_command)
    assert session_refused.disposition is disposition_type.REFUSED
    assert session_refused.reason is reason_type.SESSION_MISMATCH
    assert session_refused.state == state
    assert session_refused.created_effect_ids == ()

    query = query_type(  # type: ignore[operator]
        input_id=authority_input_type("scope-mismatch-query-input"),
        query_claim_id=query_claim_id_type("scope-mismatch-query"),
        symbol_id=OTHER_SYMBOL,
        kind=query_kind_type.QUERY,
    )
    query_refused = _authority_apply_twice(module, state, EXECUTION, query)
    assert query_refused.disposition is disposition_type.REFUSED
    assert query_refused.reason is reason_type.EXECUTION_BINDING_MISMATCH
    assert query_refused.state == state
    assert query_refused.fresh_claim is None


def test_consumed_emergency_grant_cannot_be_reintroduced() -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    execution = _advanced_same_scope_execution(label="consumed-grant")
    halted = _forge_positive_predecessor(
        module,
        mode="HALTED",
        kill_engaged=True,
        remaining=2,
        reserve=1,
    )
    granted, grant_id = _forge_emergency_grant(
        module,
        halted,
        label="consumed-grant",
    )
    retained_grant = granted._emergency_grant
    created = _create_effect(
        module,
        granted,
        execution,
        label="consumed-grant-first",
        side=ExecutionSide.SELL,
        emergency_grant_id=grant_id,
    )
    claimed = _authority_apply_twice(
        module,
        created.state,
        execution,
        claim_type(  # type: ignore[operator]
            input_id=authority_input_type("consumed-grant-claim-input"),
            effect_id=EffectId("consumed-grant-first-effect"),
            claim_occurrence_id=ClaimOccurrenceId("consumed-grant-claim"),
        ),
    )
    assert claimed.disposition is disposition_type.APPLIED
    assert claimed.state._grant_consumed(grant_id)

    reintroduced = copy(claimed.state)
    object.__setattr__(reintroduced, "_emergency_grant", retained_grant)
    refused = _create_effect(
        module,
        reintroduced,
        execution,
        label="consumed-grant-second",
        side=ExecutionSide.SELL,
        emergency_grant_id=grant_id,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.EMERGENCY_GRANT_MISMATCH
    assert refused.state == reintroduced
    assert refused.created_effect_ids == ()


@pytest.mark.parametrize(
    ("mode", "kill_engaged", "expected_reason"),
    [
        ("HALTED", False, "MODE_BLOCKED"),
        ("ACTIVE", True, "KILL_ENGAGED"),
    ],
)
def test_final_ordinary_sell_rechecks_mode_and_kill(
    mode: str,
    kill_engaged: bool,
    expected_reason: str,
) -> None:
    module = _authority_module()
    disposition_type, reason_type, claim_type, authority_input_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ClaimEffect",
        "AuthorityInputId",
    )
    label = f"ordinary-sell-{mode.lower()}-{kill_engaged}"
    execution = _advanced_same_scope_execution(label=label)
    initial = _forge_positive_predecessor(module, remaining=3, reserve=1)
    created = _create_effect(
        module,
        initial,
        execution,
        label=label,
        side=ExecutionSide.SELL,
    )
    assert created.disposition is disposition_type.APPLIED
    drifted = _forge_positive_predecessor(
        module,
        predecessor=created.state,
        mode=mode,
        kill_engaged=kill_engaged,
        remaining=3,
        reserve=1,
    )
    refused = _authority_apply_twice(
        module,
        drifted,
        execution,
        claim_type(  # type: ignore[operator]
            input_id=authority_input_type(f"{label}-claim-input"),
            effect_id=EffectId(f"{label}-effect"),
            claim_occurrence_id=ClaimOccurrenceId(f"{label}-claim"),
        ),
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is getattr(reason_type, expected_reason)
    assert refused.state == drifted
    assert refused.state.budget.remaining == 3
    retained = refused.state.venue.effect(EffectId(f"{label}-effect"))
    assert retained is not None
    assert retained.state is BrokerEffectState.REQUESTED
    assert retained.claim_occurrence_id is None


def test_manual_flatten_identity_grant_and_phase_guards() -> None:
    module = _authority_module()
    (
        disposition_type,
        reason_type,
        authority_input_type,
        flatten_id_type,
        emergency_grant_id_type,
        begin_type,
        advance_type,
    ) = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "AuthorityInputId",
        "ManualFlattenId",
        "EmergencyGrantId",
        "BeginManualFlatten",
        "AdvanceManualFlatten",
    )
    state = _forge_positive_predecessor(
        module,
        mode="REDUCING",
        remaining=4,
        reserve=1,
    )
    flatten_id = flatten_id_type("guarded-flatten")
    begin = begin_type(  # type: ignore[operator]
        input_id=authority_input_type("guarded-flatten-begin-input"),
        flatten_id=flatten_id,
        session_id=state.session_id,
        symbol_id=SYMBOL,
        actor=ActorId("guarded-flatten-operator"),
        reason="guarded manual flatten",
        evidence_reference=EvidenceReference("guarded-flatten-evidence"),
        emergency_grant_id=None,
    )
    applied = _authority_apply_twice(module, state, EXECUTION, begin)
    assert applied.disposition is disposition_type.APPLIED

    duplicate = _authority_apply_twice(
        module,
        applied.state,
        EXECUTION,
        replace(
            begin,
            input_id=authority_input_type("guarded-flatten-duplicate-input"),
        ),
    )
    assert duplicate.disposition is disposition_type.CONFLICT
    assert duplicate.state == applied.state

    grant_refused = _authority_apply_twice(
        module,
        state,
        EXECUTION,
        replace(
            begin,
            input_id=authority_input_type("guarded-flatten-grant-input"),
            flatten_id=flatten_id_type("guarded-flatten-with-grant"),
            emergency_grant_id=emergency_grant_id_type("ordinary-flatten-grant"),
        ),
    )
    assert grant_refused.disposition is disposition_type.REFUSED
    assert grant_refused.reason is reason_type.MANUAL_FLATTEN_INVALID
    assert grant_refused.state == state
    assert grant_refused.created_effect_ids == ()

    unknown_advance = advance_type(  # type: ignore[operator]
        input_id=authority_input_type("unknown-flatten-advance-input"),
        flatten_id=flatten_id_type("unknown-flatten"),
    )
    advance_refused = _authority_apply_twice(
        module,
        state,
        EXECUTION,
        unknown_advance,
    )
    assert advance_refused.disposition is disposition_type.REFUSED
    assert advance_refused.reason is reason_type.MANUAL_FLATTEN_INVALID
    assert advance_refused.state == state
    assert advance_refused.created_effect_ids == ()


def test_kill_releases_unclaimed_cancel_reservation_and_allows_retry() -> None:
    module = _authority_module()
    disposition_type, authority_input_type, kill_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityInputId",
        "EngageKill",
    )
    state = _seed_cancellable_buy(
        module,
        mode="REDUCING",
        remaining=3,
        reserve=1,
        label="kill-cancel-target",
    )
    first = _create_effect(
        module,
        state,
        EXECUTION,
        label="kill-cancel-first",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    assert first.disposition is disposition_type.APPLIED
    assert first.state.budget == state.budget

    kill = kill_type(  # type: ignore[operator]
        input_id=authority_input_type("kill-cancel-input"),
        actor=ActorId("kill-cancel-operator"),
        reason="stand down the unclaimed cancel and release its target",
        evidence_reference=EvidenceReference("kill-cancel-evidence"),
    )
    killed = _authority_apply_twice(module, first.state, EXECUTION, kill)
    assert killed.disposition is disposition_type.APPLIED
    assert killed.state.kill_engaged is True
    assert killed.state.budget == first.state.budget
    stood_down = killed.state.venue.effect(EffectId("kill-cancel-first-effect"))
    assert stood_down is not None
    assert stood_down.state is BrokerEffectState.CANCELED_BEFORE_DISPATCH
    assert stood_down.acceptance_set_state is AcceptanceSetState.CLOSED
    assert stood_down.claim_occurrence_id is None

    replay = _authority_apply_twice(module, killed.state, EXECUTION, kill)
    assert replay.disposition is disposition_type.EXACT_REPLAY
    assert replay.state == killed.state
    conflict = _authority_apply_twice(
        module,
        killed.state,
        EXECUTION,
        replace(kill, reason="changed kill payload"),
    )
    assert conflict.disposition is disposition_type.CONFLICT
    assert conflict.state == killed.state

    retry = _create_effect(
        module,
        killed.state,
        EXECUTION,
        label="kill-cancel-retry",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    assert retry.disposition is disposition_type.APPLIED
    assert retry.state.kill_engaged is True
    assert retry.state.budget == killed.state.budget
    assert retry.created_effect_ids == (EffectId("kill-cancel-retry-effect"),)
    retained = retry.state.venue.effect(EffectId("kill-cancel-retry-effect"))
    assert retained is not None
    assert retained.state is BrokerEffectState.REQUESTED
    assert retained.acceptance_set_state is AcceptanceSetState.OPEN
    assert retained.claim_occurrence_id is None


def test_caller_boolean_or_diagnostic_object_is_never_an_input() -> None:
    module = _authority_module()
    state = _genesis(module)
    with pytest.raises(TypeError):
        module.apply_execution_authority_input(state, EXECUTION, True)


def test_authority_reducer_rejects_every_command_subclass_exactly() -> None:
    module = _authority_module()
    (
        authority_input_type,
        query_id_type,
        query_kind_type,
        flatten_id_type,
        create_type,
        claim_type,
        query_type,
        kill_type,
        begin_type,
        advance_type,
    ) = _required(
        module,
        "AuthorityInputId",
        "QueryClaimId",
        "AuthorityQueryKind",
        "ManualFlattenId",
        "CreateBrokerEffect",
        "ClaimEffect",
        "ClaimBrokerQuery",
        "EngageKill",
        "BeginManualFlatten",
        "AdvanceManualFlatten",
    )
    state = _forge_positive_predecessor(module, remaining=3, reserve=1)
    request = _effect_request(
        module,
        "exact-type",
        side=ExecutionSide.BUY,
        quantity=1,
    )
    commands = (
        create_type(  # type: ignore[operator]
            input_id=authority_input_type("exact-type-create-input"),
            session_id=state.session_id,
            request=request,
            manual_flatten_id=None,
            emergency_grant_id=None,
        ),
        claim_type(  # type: ignore[operator]
            input_id=authority_input_type("exact-type-claim-input"),
            effect_id=EffectId("exact-type-effect"),
            claim_occurrence_id=ClaimOccurrenceId("exact-type-claim"),
        ),
        query_type(  # type: ignore[operator]
            input_id=authority_input_type("exact-type-query-input"),
            query_claim_id=query_id_type("exact-type-query"),
            symbol_id=SYMBOL,
            kind=query_kind_type.QUERY,
        ),
        kill_type(  # type: ignore[operator]
            input_id=authority_input_type("exact-type-kill-input"),
            actor=ActorId("exact-type-operator"),
            reason="exact type test",
            evidence_reference=EvidenceReference("exact-type-kill-evidence"),
        ),
        begin_type(  # type: ignore[operator]
            input_id=authority_input_type("exact-type-begin-input"),
            flatten_id=flatten_id_type("exact-type-flatten"),
            session_id=state.session_id,
            symbol_id=SYMBOL,
            actor=ActorId("exact-type-operator"),
            reason="exact type test",
            evidence_reference=EvidenceReference("exact-type-begin-evidence"),
            emergency_grant_id=None,
        ),
        advance_type(  # type: ignore[operator]
            input_id=authority_input_type("exact-type-advance-input"),
            flatten_id=flatten_id_type("exact-type-flatten"),
        ),
    )

    def derived_instance(value: object, name: str) -> object | None:
        try:
            derived_type = type(name, (type(value),), {})
            return derived_type(
                **{field.name: getattr(value, field.name) for field in fields(value)}
            )
        except TypeError:
            return None

    for command in commands:
        derived = derived_instance(
            command,
            f"Derived{type(command).__name__}",
        )
        if derived is None:
            continue
        with pytest.raises(TypeError, match="exact|type|admitted"):
            module.apply_execution_authority_input(state, EXECUTION, derived)

    derived_request = derived_instance(
        request,
        "DerivedBrokerEffectRequest",
    )
    if derived_request is not None:
        with pytest.raises(TypeError, match="request|exact|type"):
            create_type(  # type: ignore[operator]
                input_id=authority_input_type("derived-request-create-input"),
                session_id=state.session_id,
                request=derived_request,
                manual_flatten_id=None,
                emergency_grant_id=None,
            )


def test_hot_authority_paths_never_materialize_audit_history(monkeypatch) -> None:
    module = _authority_module()
    (
        disposition_type,
        claim_type,
        authority_input_type,
        query_id_type,
        query_kind_type,
        query_type,
        flatten_id_type,
        begin_flatten_type,
    ) = _required(
        module,
        "AuthorityDisposition",
        "ClaimEffect",
        "AuthorityInputId",
        "QueryClaimId",
        "AuthorityQueryKind",
        "ClaimBrokerQuery",
        "ManualFlattenId",
        "BeginManualFlatten",
    )
    normal_base = _forge_positive_predecessor(module, remaining=5, reserve=1)
    normal_created = _create_buy(module, normal_base, label="no-scan-normal")
    normal_claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("no-scan-normal-claim-input"),
        effect_id=EffectId("no-scan-normal-effect"),
        claim_occurrence_id=ClaimOccurrenceId("no-scan-normal-claim"),
    )

    cancel_base = _seed_cancellable_buy(
        module,
        remaining=2,
        reserve=1,
        label="no-scan-cancel-target",
    )
    cancel_created = _create_effect(
        module,
        cancel_base,
        EXECUTION,
        label="no-scan-cancel",
        side=ExecutionSide.BUY,
        kind=EffectKind.CANCEL,
        target_leg_key=LEG,
    )
    cancel_claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("no-scan-cancel-claim-input"),
        effect_id=EffectId("no-scan-cancel-effect"),
        claim_occurrence_id=ClaimOccurrenceId("no-scan-cancel-claim"),
    )

    query_state = _forge_positive_predecessor(
        module,
        phase="RECONCILING",
        mode="HALTED",
        fence="RECONCILIATION_ONLY",
        kill_engaged=True,
        remaining=1,
        reserve=1,
    )
    query = query_type(  # type: ignore[operator]
        input_id=authority_input_type("no-scan-query-input"),
        query_claim_id=query_id_type("no-scan-query"),
        symbol_id=SYMBOL,
        kind=query_kind_type.RECONCILE,
    )

    flatten_base = _forge_positive_predecessor(
        module,
        mode="REDUCING",
        remaining=3,
        reserve=1,
    )
    flatten_local = _create_buy(module, flatten_base, label="no-scan-flatten")
    begin_flatten = begin_flatten_type(  # type: ignore[operator]
        input_id=authority_input_type("no-scan-flatten-input"),
        flatten_id=flatten_id_type("no-scan-flatten"),
        session_id=flatten_local.state.session_id,
        symbol_id=SYMBOL,
        actor=ActorId("no-scan-operator"),
        reason="prove bounded hot paths",
        evidence_reference=EvidenceReference("no-scan-evidence"),
        emergency_grant_id=None,
    )

    normal_state = _forge_venue_predecessor(
        normal_created.state,
        _append_closed_local_history(
            normal_created.state.venue,
            EXECUTION,
            label="no-scan-normal-history",
        ),
    )
    cancel_state = _forge_venue_predecessor(
        cancel_created.state,
        _append_closed_local_history(
            cancel_created.state.venue,
            EXECUTION,
            label="no-scan-cancel-history",
        ),
    )
    query_state = _forge_venue_predecessor(
        query_state,
        _append_closed_local_history(
            query_state.venue,
            EXECUTION,
            label="no-scan-query-history",
        ),
    )
    flatten_state = _forge_venue_predecessor(
        flatten_local.state,
        _append_closed_local_history(
            flatten_local.state.venue,
            EXECUTION,
            label="no-scan-flatten-history",
        ),
    )

    def fail_materialization(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("hot authority path materialized audit history")

    for name in (
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
    ):
        monkeypatch.setattr(
            VenueRecoveryBook,
            name,
            property(fail_materialization),
        )
    original_sequence_get = _PersistentSequence.get
    sequence_reads = 0

    def bounded_sequence_get(self: object, index: int) -> object:
        nonlocal sequence_reads
        sequence_reads += 1
        return original_sequence_get(self, index)  # type: ignore[arg-type]

    monkeypatch.setattr(_PersistentSequence, "get", bounded_sequence_get)
    monkeypatch.setattr(_PersistentSequence, "to_tuple", fail_materialization)

    before = sequence_reads
    normal = _authority_apply_twice(
        module,
        normal_state,
        EXECUTION,
        normal_claim,
    )
    assert sequence_reads - before <= 16
    before = sequence_reads
    cancel = _authority_apply_twice(
        module,
        cancel_state,
        EXECUTION,
        cancel_claim,
    )
    assert sequence_reads - before <= 16
    before = sequence_reads
    query_claimed = _authority_apply_twice(
        module,
        query_state,
        EXECUTION,
        query,
    )
    assert sequence_reads - before <= 16
    before = sequence_reads
    flattened = _authority_apply_twice(
        module,
        flatten_state,
        EXECUTION,
        begin_flatten,
    )
    assert sequence_reads - before <= 16
    assert normal.disposition is disposition_type.APPLIED
    assert cancel.disposition is disposition_type.APPLIED
    assert query_claimed.disposition is disposition_type.APPLIED
    assert flattened.disposition is disposition_type.APPLIED


def test_authority_identity_indexes_are_structurally_shared_and_bounded(
    monkeypatch,
) -> None:
    module = _authority_module()
    (
        disposition_type,
        authority_input_type,
        query_id_type,
        query_kind_type,
        query_type,
    ) = _required(
        module,
        "AuthorityDisposition",
        "AuthorityInputId",
        "QueryClaimId",
        "AuthorityQueryKind",
        "ClaimBrokerQuery",
    )
    state = _forge_positive_predecessor(
        module,
        phase="RECONCILING",
        mode="HALTED",
        fence="RECONCILIATION_ONLY",
        kill_engaged=True,
        remaining=40,
        reserve=1,
    )
    for ordinal in range(32):
        transition = _authority_apply_twice(
            module,
            state,
            EXECUTION,
            query_type(
                input_id=authority_input_type(f"persistent-query-input-{ordinal}"),
                query_claim_id=query_id_type(f"persistent-query-{ordinal}"),
                symbol_id=SYMBOL,
                kind=query_kind_type.QUERY,
            ),
        )
        assert transition.disposition is disposition_type.APPLIED
        state = transition.state

    index_names = (
        "_input_by_id",
        "_effect_authority_by_id",
        "_claim_by_effect",
        "_claim_by_occurrence",
        "_query_by_id",
        "_manual_by_id",
        "_consumed_grant_ids",
    )
    assert all(type(getattr(state, name)) is _PersistentKeyMap for name in index_names)
    assert state._input_by_id.size == 32
    assert state._query_by_id.size == 32

    original_get = _PersistentKeyMap.get
    original_insert = _PersistentKeyMap.insert_new
    operations = 0

    def counted_get(self: object, key: bytes) -> object:
        nonlocal operations
        operations += 1
        return original_get(self, key)  # type: ignore[arg-type]

    def counted_insert(
        self: object,
        key: bytes,
        value: object,
        value_commitment: bytes,
    ) -> object:
        nonlocal operations
        operations += 1
        return original_insert(  # type: ignore[arg-type]
            self,
            key,
            value,
            value_commitment,
        )

    monkeypatch.setattr(_PersistentKeyMap, "get", counted_get)
    monkeypatch.setattr(_PersistentKeyMap, "insert_new", counted_insert)
    predecessor = state
    next_transition = _authority_apply_twice(
        module,
        predecessor,
        EXECUTION,
        query_type(
            input_id=authority_input_type("persistent-query-input-final"),
            query_claim_id=query_id_type("persistent-query-final"),
            symbol_id=SYMBOL,
            kind=query_kind_type.RECONCILE,
        ),
    )
    assert next_transition.disposition is disposition_type.APPLIED
    assert operations <= 16
    assert predecessor._input_by_id.size == 32
    assert predecessor._query_by_id.size == 32
    assert next_transition.state._input_by_id.size == 33
    assert next_transition.state._query_by_id.size == 33
