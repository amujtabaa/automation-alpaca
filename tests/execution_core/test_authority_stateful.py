"""Bounded generated histories for the pure WO-0147 authority boundary.

The three machines deliberately stay small.  Environmental authority is forged
only in test code; every effect, claim, kill, venue, and flatten transition then
uses the real pure reducers.  The symbol oracle materializes canonical records
and never calls the production classifier it checks.
"""

from __future__ import annotations

from copy import copy
from dataclasses import astuple, dataclass, replace
from decimal import Decimal
import importlib
from types import ModuleType

import pytest
from hypothesis import HealthCheck, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from app.execution_core.fills import (
    BrokerFillFact,
    ExecutionScope,
    ExecutionSide,
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
    SourceEventId,
    SymbolId,
    VenueInputId,
    VenueLegKey,
    VenueObservationId,
)
from app.execution_core.position import ExecutionSnapshot, apply_broker_execution_fact
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
    CancelBeforeDispatch,
    CloseAcceptanceSet,
    DiscoverVenueLeg,
    EffectKind,
    ObserveVenueStatus,
    PendingVenueOperation,
    RecordDispatchClaim,
    RecordTransportOutcome,
    RequestedEffect,
    VenueAttemptState,
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    VenueScope,
    apply_venue_recovery_input,
)
from tests.execution_core import test_venue_recovery as recovery_fixtures


BROKER = BrokerId("alpaca")
ENVIRONMENT = EnvironmentId("paper")
ACCOUNT = AccountId("authority-stateful-account")
GENERATION = ApplicationGenerationId("authority-stateful-generation")
SYMBOL = SymbolId("AAPL")
OTHER_SYMBOL = SymbolId("MSFT")
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
OTHER_EXECUTION = ExecutionSnapshot.flat(
    PositionScope(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        symbol_id=OTHER_SYMBOL,
    )
)
LEG = VenueLegKey(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    order_id=OrderId("authority-stateful-leg"),
)
LATE_LEG = VenueLegKey(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    order_id=OrderId("authority-stateful-late-leg"),
)
SECOND_LEG = VenueLegKey(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    order_id=OrderId("authority-stateful-second-leg"),
)
SHRINK_LEG = VenueLegKey(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    order_id=OrderId("authority-stateful-residual-shrink-leg"),
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


def _forge_authority(
    module: ModuleType,
    *,
    predecessor: object | None = None,
    phase: str = "SERVING",
    mode: str = "ACTIVE",
    fence: str = "PAPER_MUTATION_ELIGIBLE",
    kill_engaged: bool = False,
    remaining: int = 8,
    reserve: int = 2,
    session: str = "stateful-session",
) -> object:
    """Forge only the M2/M4 environmental proof unavailable in pure M1."""

    (
        phase_type,
        mode_type,
        fence_type,
        session_type,
        budget_type,
        genesis,
    ) = _required(
        module,
        "EnginePhase",
        "TradingMode",
        "SupervisorFence",
        "SessionId",
        "RequestBudget",
        "initial_execution_authority_state",
    )
    state = copy(predecessor if predecessor is not None else genesis(VENUE_SCOPE))
    object.__setattr__(state, "phase", getattr(phase_type, phase))
    object.__setattr__(state, "mode", getattr(mode_type, mode))
    object.__setattr__(state, "supervisor_fence", getattr(fence_type, fence))
    object.__setattr__(state, "kill_engaged", kill_engaged)
    object.__setattr__(state, "session_id", session_type(session))
    object.__setattr__(
        state,
        "budget",
        budget_type(remaining=remaining, safety_reserve=reserve),
    )
    return state


def _forge_venue(state: object, book: VenueRecoveryBook) -> object:
    forged = copy(state)
    object.__setattr__(forged, "venue", book)
    return forged


def _broker_fill(
    label: str,
    *,
    leg_key: VenueLegKey,
    quantity: int,
    side: ExecutionSide = ExecutionSide.BUY,
) -> BrokerFillFact:
    return BrokerFillFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId(f"{label}-source"),
        ),
        scope=ExecutionScope(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            order_id=leg_key.order_id,
            symbol_id=SYMBOL,
            side=side,
        ),
        root_fill_id=RootFillId(f"{label}-root"),
        quantity=Quantity(quantity),
        price=PRICE,
    )


def _apply_fact(
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
    return ExecutionSnapshot(
        position=transition.position,
        integrity=transition.integrity,
        root_heads=transition.root_heads,
        seen_facts=transition.seen_facts,
    )


SEED_LEG = VenueLegKey(
    broker=BROKER,
    environment=ENVIRONMENT,
    account=ACCOUNT,
    order_id=OrderId("authority-stateful-position-seed"),
)
LONG_EXECUTION = _apply_fact(
    EXECUTION,
    _broker_fill("authority-stateful-position-seed", leg_key=SEED_LEG, quantity=5),
)


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
    return request_type(
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
        economic_scope=f"{label}|{kind.value}|{side.value}|{quantity}".encode(),
        target_leg_key=target_leg_key,
    )


def _create_effect(
    module: ModuleType,
    state: object,
    execution: ExecutionSnapshot,
    label: str,
    *,
    side: ExecutionSide,
    quantity: int,
    kind: EffectKind = EffectKind.SUBMIT,
    target_leg_key: VenueLegKey | None = None,
    manual_flatten_id: object | None = None,
) -> object:
    authority_input_type, create_type = _required(
        module,
        "AuthorityInputId",
        "CreateBrokerEffect",
    )
    item = create_type(
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
        emergency_grant_id=None,
    )
    before = (state, execution, item)
    first = module.apply_execution_authority_input(state, execution, item)
    second = module.apply_execution_authority_input(state, execution, item)
    assert second == first
    assert before == (state, execution, item)
    return first


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


def _private_venue_apply(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
) -> object:
    import app.execution_core.venue as venue

    assert hasattr(venue, "_apply_venue_input")
    if (
        type(item) is CloseAcceptanceSet
        and item.proof.kind is not AcceptanceProofKind.NEVER_DISPATCHED
    ):
        with recovery_fixtures._test_certified_external_closure():
            return venue._apply_venue_input(book, execution, item)
    return venue._apply_venue_input(book, execution, item)


def _venue_apply_twice(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
    *,
    internal: bool = False,
) -> object:
    reducer = (
        _private_venue_apply
        if internal or type(item) is CloseAcceptanceSet
        else apply_venue_recovery_input
    )
    before = (book, execution, item)
    first = reducer(book, execution, item)
    second = reducer(book, execution, item)
    assert second == first
    assert before == (book, execution, item)
    assert first.disposition is VenueRecoveryDisposition.APPLIED
    return first


def _seed_raw_effect(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    label: str,
    *,
    claim: bool,
    leg_key: VenueLegKey | None,
    side: ExecutionSide = ExecutionSide.BUY,
    quantity: int = 2,
    symbol_id: SymbolId = SYMBOL,
) -> tuple[VenueRecoveryBook, ExecutionSnapshot, EffectId]:
    effect_id = EffectId(f"{label}-effect")
    requested = _venue_apply_twice(
        book,
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
            economic_scope=f"{label}|{side.value}|{quantity}".encode(),
            target_leg_key=None,
        ),
        internal=True,
    )
    book = requested.book
    execution = requested.execution
    if not claim:
        assert leg_key is None
        return book, execution, effect_id

    claimed = _venue_apply_twice(
        book,
        execution,
        RecordDispatchClaim(
            input_id=VenueInputId(f"{label}-claim-input"),
            effect_id=effect_id,
            claim_occurrence_id=ClaimOccurrenceId(f"{label}-claim"),
        ),
        internal=True,
    )
    book = claimed.book
    execution = claimed.execution
    if leg_key is None:
        return book, execution, effect_id

    acknowledged = _venue_apply_twice(
        book,
        execution,
        RecordTransportOutcome(
            input_id=VenueInputId(f"{label}-ack-input"),
            effect_id=effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    discovered = _venue_apply_twice(
        acknowledged.book,
        acknowledged.execution,
        DiscoverVenueLeg(
            input_id=VenueInputId(f"{label}-discover-input"),
            effect_id=effect_id,
            leg_key=leg_key,
            observation_id=VenueObservationId(f"{label}-discovery"),
        ),
    )
    return discovered.book, discovered.execution, effect_id


def _manual_begin(
    module: ModuleType,
    state: object,
    flatten_id: object,
    label: str,
    *,
    session_id: object | None = None,
) -> object:
    authority_input_type, begin_type = _required(
        module,
        "AuthorityInputId",
        "BeginManualFlatten",
    )
    return begin_type(
        input_id=authority_input_type(f"{label}-begin-input"),
        flatten_id=flatten_id,
        session_id=state.session_id if session_id is None else session_id,
        symbol_id=SYMBOL,
        actor=ActorId(f"{label}-operator"),
        reason=f"{label} manual flatten",
        evidence_reference=EvidenceReference(f"{label}-evidence"),
        emergency_grant_id=None,
    )


def _manual_advance(module: ModuleType, flatten_id: object, label: str) -> object:
    authority_input_type, advance_type = _required(
        module,
        "AuthorityInputId",
        "AdvanceManualFlatten",
    )
    return advance_type(
        input_id=authority_input_type(f"{label}-advance-input"),
        flatten_id=flatten_id,
    )


def _begin_waiting_manual_flatten(
    module: ModuleType,
    label: str,
    *,
    leg_key: VenueLegKey = LEG,
) -> tuple[object, ExecutionSnapshot, object, EffectId, EffectId]:
    disposition_type, flatten_id_type = _required(
        module,
        "AuthorityDisposition",
        "ManualFlattenId",
    )
    book, execution, buy_effect_id = _seed_raw_effect(
        VenueRecoveryBook.empty(VENUE_SCOPE),
        LONG_EXECUTION,
        f"{label}-buy",
        claim=True,
        leg_key=leg_key,
    )
    state = _forge_authority(
        module,
        mode="REDUCING",
        remaining=8,
        reserve=2,
    )
    state = _forge_venue(state, book)
    flatten_id = flatten_id_type(f"{label}-flatten")
    begun = _authority_apply_twice(
        module,
        state,
        execution,
        _manual_begin(module, state, flatten_id, label),
    )
    assert begun.disposition is disposition_type.APPLIED
    assert len(begun.created_effect_ids) == 1
    return (
        begun.state,
        execution,
        flatten_id,
        buy_effect_id,
        begun.created_effect_ids[0],
    )


def _manual_advance_predecessor(
    module: ModuleType,
    label: str,
) -> tuple[object, ExecutionSnapshot, object]:
    disposition_type, authority_input_type, claim_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityInputId",
        "ClaimEffect",
    )
    state, execution, flatten_id, buy_effect_id, cancel_effect_id = (
        _begin_waiting_manual_flatten(module, label)
    )
    claimed = _authority_apply_twice(
        module,
        state,
        execution,
        claim_type(
            input_id=authority_input_type(f"{label}-cancel-claim-input"),
            effect_id=cancel_effect_id,
            claim_occurrence_id=ClaimOccurrenceId(f"{label}-cancel-claim"),
        ),
    )
    assert claimed.disposition is disposition_type.APPLIED
    acknowledged = _venue_apply_twice(
        claimed.state.venue,
        execution,
        RecordTransportOutcome(
            input_id=VenueInputId(f"{label}-cancel-ack-input"),
            effect_id=cancel_effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    terminal = _venue_apply_twice(
        acknowledged.book,
        acknowledged.execution,
        ObserveVenueStatus(
            input_id=VenueInputId(f"{label}-terminal-input"),
            leg_key=LEG,
            status=VenueAttemptState.CANCELED,
            observation_id=VenueObservationId(f"{label}-terminal"),
            cumulative_quantity=Quantity(0),
            closure_id=ClosureId(f"{label}-terminal-closure"),
            evidence_reference=EvidenceReference(f"{label}-terminal-evidence"),
        ),
    )
    book = terminal.book
    execution = terminal.execution
    for effect_id, suffix in (
        (cancel_effect_id, "cancel"),
        (buy_effect_id, "buy"),
    ):
        closed = _venue_apply_twice(
            book,
            execution,
            CloseAcceptanceSet(
                input_id=VenueInputId(f"{label}-{suffix}-close-input"),
                effect_id=effect_id,
                proof=_proof(
                    book,
                    effect_id,
                    f"{label}-{suffix}-close",
                ),
            ),
        )
        assert closed.disposition is VenueRecoveryDisposition.APPLIED
        book = closed.book
        execution = closed.execution
    return _forge_venue(claimed.state, book), execution, flatten_id


def _apply_closed_sell_fill(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    label: str,
    leg_key: VenueLegKey,
) -> tuple[VenueRecoveryBook, ExecutionSnapshot]:
    book, execution, effect_id = _seed_raw_effect(
        book,
        execution,
        label,
        claim=True,
        leg_key=leg_key,
        side=ExecutionSide.SELL,
        quantity=1,
    )
    filled = _venue_apply_twice(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId(f"{label}-fill-input"),
            effect_id=effect_id,
            leg_key=leg_key,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(1),
            fact=_broker_fill(
                f"{label}-fill",
                leg_key=leg_key,
                quantity=1,
                side=ExecutionSide.SELL,
            ),
            evidence_digest=bytes([len(label) % 251 + 1]) * 32,
            closure_id=None,
            evidence_reference=None,
        ),
    )
    terminal = _venue_apply_twice(
        filled.book,
        filled.execution,
        ObserveVenueStatus(
            input_id=VenueInputId(f"{label}-terminal-input"),
            leg_key=leg_key,
            status=VenueAttemptState.FILLED,
            observation_id=VenueObservationId(f"{label}-terminal"),
            cumulative_quantity=Quantity(1),
            closure_id=ClosureId(f"{label}-terminal-closure"),
            evidence_reference=EvidenceReference(f"{label}-terminal-evidence"),
        ),
    )
    closed = _venue_apply_twice(
        terminal.book,
        terminal.execution,
        CloseAcceptanceSet(
            input_id=VenueInputId(f"{label}-close-input"),
            effect_id=effect_id,
            proof=_proof(terminal.book, effect_id, f"{label}-close"),
        ),
    )
    assert closed.disposition is VenueRecoveryDisposition.APPLIED
    return closed.book, closed.execution


def _proof(
    book: VenueRecoveryBook,
    effect_id: EffectId,
    label: str,
    *,
    kind: AcceptanceProofKind = AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
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
        evidence_reference=EvidenceReference(f"{label}-evidence"),
        evidence_digest=bytes([len(label) % 251 + 1]) * 32,
    )


class ClaimAuthorityMachine(RuleBasedStateMachine):
    """Generate both orders of the final-claim versus kill race."""

    def __init__(self) -> None:
        super().__init__()
        self.module = _authority_module()
        (
            self.disposition_type,
            self.authority_input_type,
            self.claim_type,
            self.engage_kill_type,
            self.reducer,
        ) = _required(
            self.module,
            "AuthorityDisposition",
            "AuthorityInputId",
            "ClaimEffect",
            "EngageKill",
            "apply_execution_authority_input",
        )
        initial = _forge_authority(self.module, remaining=4, reserve=1)
        created = _create_effect(
            self.module,
            initial,
            EXECUTION,
            "claim-machine",
            side=ExecutionSide.BUY,
            quantity=1,
        )
        assert created.disposition is self.disposition_type.APPLIED
        self.state = created.state
        self.effect_id = EffectId("claim-machine-effect")
        self.claim = self.claim_type(
            input_id=self.authority_input_type("claim-machine-claim-input"),
            effect_id=self.effect_id,
            claim_occurrence_id=ClaimOccurrenceId("claim-machine-claim"),
        )
        self.claimed = False
        self.killed = False
        self._next_input = 0

    def _apply_twice(self, predecessor: object, item: object) -> object:
        before = (predecessor, EXECUTION, item)
        first = self.reducer(predecessor, EXECUTION, item)
        second = self.reducer(predecessor, EXECUTION, item)
        assert second == first
        assert before == (predecessor, EXECUTION, item)
        return first

    @precondition(lambda self: not self.claimed and not self.killed)
    @rule()
    def claim_wins(self) -> None:
        before_budget = self.state.budget.remaining
        transition = self._apply_twice(self.state, self.claim)
        assert transition.disposition is self.disposition_type.APPLIED
        assert transition.fresh_claim is not None
        assert transition.fresh_claim.effect_id == self.effect_id
        assert transition.state.budget.remaining == before_budget - 1
        self.state = transition.state
        self.claimed = True

    @precondition(lambda self: not self.killed)
    @rule()
    def kill_wins_or_follows_claim(self) -> None:
        effect_before = self.state.venue.effect(self.effect_id)
        assert effect_before is not None
        self._next_input += 1
        item = self.engage_kill_type(
            input_id=self.authority_input_type(
                f"claim-machine-kill-{self._next_input}"
            ),
            actor=ActorId("claim-machine-operator"),
            reason="generated kill race",
            evidence_reference=EvidenceReference("claim-machine-kill-evidence"),
        )
        before_budget = self.state.budget
        transition = self._apply_twice(self.state, item)
        assert transition.disposition is self.disposition_type.APPLIED
        assert transition.state.kill_engaged is True
        assert transition.state.budget == before_budget
        assert transition.fresh_claim is None
        effect_after = transition.state.venue.effect(self.effect_id)
        assert effect_after is not None
        if self.claimed:
            assert effect_after == effect_before
            assert effect_after.state is BrokerEffectState.DISPATCH_CLAIMED
            assert effect_after.claim_occurrence_id == ClaimOccurrenceId(
                "claim-machine-claim"
            )
        else:
            assert effect_before.state is BrokerEffectState.REQUESTED
            assert effect_before.claim_occurrence_id is None
            assert effect_after.state is BrokerEffectState.CANCELED_BEFORE_DISPATCH
            assert effect_after.acceptance_set_state is AcceptanceSetState.CLOSED
            assert effect_after.claim_occurrence_id is None
        self.state = transition.state
        self.killed = True

    @precondition(lambda self: self.killed and not self.claimed)
    @rule()
    def claim_after_kill_is_inert(self) -> None:
        before_budget = self.state.budget
        transition = self._apply_twice(self.state, self.claim)
        assert transition.disposition is self.disposition_type.REFUSED
        assert transition.state == self.state
        assert transition.state.budget == before_budget
        assert transition.fresh_claim is None

    @precondition(lambda self: self.claimed)
    @rule()
    def successful_claim_replay_and_conflict_are_inert(self) -> None:
        replay = self._apply_twice(self.state, self.claim)
        assert replay.disposition is self.disposition_type.EXACT_REPLAY
        assert replay.state == self.state
        assert replay.fresh_claim is None
        conflict = self._apply_twice(
            self.state,
            replace(
                self.claim,
                claim_occurrence_id=ClaimOccurrenceId(
                    "claim-machine-conflicting-claim"
                ),
            ),
        )
        assert conflict.disposition is self.disposition_type.CONFLICT
        assert conflict.state == self.state
        assert conflict.fresh_claim is None

    @precondition(lambda self: not self.claimed and not self.killed)
    @rule(
        axis=st.sampled_from(
            (
                "phase",
                "mode",
                "fence",
                "kill",
                "reserve",
                "session",
            )
        )
    )
    def every_final_gate_can_refuse(self, axis: str) -> None:
        changes: dict[str, object] = {"remaining": 4, "reserve": 1}
        if axis == "phase":
            changes["phase"] = "RECONCILING"
        elif axis == "mode":
            changes["mode"] = "REDUCING"
        elif axis == "fence":
            changes["fence"] = "RECONCILIATION_ONLY"
        elif axis == "kill":
            changes["kill_engaged"] = True
        elif axis == "reserve":
            changes.update(remaining=1, reserve=1)
        else:
            changes["session"] = "foreign-session"
        forged = _forge_authority(
            self.module,
            predecessor=self.state,
            **changes,  # type: ignore[arg-type]
        )
        transition = self._apply_twice(forged, self.claim)
        assert transition.disposition is self.disposition_type.REFUSED
        assert transition.state == forged
        assert transition.state.budget == forged.budget
        assert transition.fresh_claim is None

    @invariant()
    def claim_and_budget_remain_one_shot(self) -> None:
        effect = self.state.venue.effect(self.effect_id)
        assert effect is not None
        if self.claimed:
            assert effect.state is BrokerEffectState.DISPATCH_CLAIMED
            assert effect.acceptance_set_state is AcceptanceSetState.OPEN
            assert effect.claim_occurrence_id == ClaimOccurrenceId(
                "claim-machine-claim"
            )
            assert self.state.budget.remaining == 3
        elif self.killed:
            assert effect.state is BrokerEffectState.CANCELED_BEFORE_DISPATCH
            assert effect.acceptance_set_state is AcceptanceSetState.CLOSED
            assert effect.claim_occurrence_id is None
            assert self.state.budget.remaining == 4
        else:
            assert effect.state is BrokerEffectState.REQUESTED
            assert effect.acceptance_set_state is AcceptanceSetState.OPEN
            assert effect.claim_occurrence_id is None
            assert self.state.budget.remaining == 4


@dataclass(frozen=True)
class _SlowSymbolView:
    execution_binding_matches: bool
    account_reconciliation_clear: bool
    blocking_effect_count: int
    blocking_buy_effect_count: int
    target_exemptible_count: int
    stand_downable_buy_count: int
    known_cancellable_buy_leg_count: int
    known_cancel_pending_buy_leg_count: int
    waiting_buy_parent_count: int
    unknown_buy_effect_count: int


_SYMBOL_VIEW_FIELDS = tuple(_SlowSymbolView.__dataclass_fields__)


def _slow_symbol_view(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    target_effect_id: EffectId | None,
) -> _SlowSymbolView:
    """Fold audit-facing records without consulting any production gate/index."""

    effects = tuple(
        effect
        for effect in book.effects
        if effect.scope.position_scope == POSITION_SCOPE
    )
    owners_by_effect = {
        effect.effect_id: tuple(
            owner for owner in book.owners if owner.effect_id == effect.effect_id
        )
        for effect in effects
    }
    active_by_leg = {attempt.leg_key: attempt for attempt in book.active_attempts}
    closure_by_leg = {closure.leg_key: closure for closure in book.closure_heads}

    def has_reconciliation(effect_id: EffectId) -> bool:
        for record in book.reconciliations:
            retained = getattr(record, "effect_id", None)
            scope = getattr(record, "effect_scope", None)
            if retained == effect_id or getattr(scope, "effect_id", None) == effect_id:
                return True
        return False

    def fully_resolved(effect: object) -> bool:
        owners = owners_by_effect[effect.effect_id]
        return bool(
            effect.acceptance_set_state is AcceptanceSetState.CLOSED
            and not any(owner.leg_key in active_by_leg for owner in owners)
            and all(owner.leg_key in closure_by_leg for owner in owners)
            and not has_reconciliation(effect.effect_id)
        )

    def safely_local(effect: object) -> bool:
        return bool(
            effect.state is BrokerEffectState.REQUESTED
            and effect.claim_occurrence_id is None
            and not owners_by_effect[effect.effect_id]
            and not has_reconciliation(effect.effect_id)
        )

    def exposure_buy(effect: object) -> bool:
        return bool(
            effect.scope.kind in {EffectKind.SUBMIT, EffectKind.REPLACE}
            and effect.scope.side is ExecutionSide.BUY
        )

    unresolved = tuple(effect for effect in effects if not fully_resolved(effect))
    unresolved_buys = tuple(effect for effect in unresolved if exposure_buy(effect))
    cancellable_legs = []
    cancel_pending_legs = []
    unknown_buy_effects = []
    waiting_buy_parents = []
    for effect in unresolved_buys:
        owners = owners_by_effect[effect.effect_id]
        active = tuple(
            active_by_leg[owner.leg_key]
            for owner in owners
            if owner.leg_key in active_by_leg
        )
        known = tuple(
            attempt
            for attempt in active
            if effect.state is BrokerEffectState.ACKNOWLEDGED
            and attempt.status
            in {VenueAttemptState.WORKING, VenueAttemptState.PARTIALLY_FILLED}
        )
        cancellable_legs.extend(
            attempt for attempt in known if attempt.pending_operation is None
        )
        cancel_pending_legs.extend(
            attempt
            for attempt in known
            if attempt.pending_operation is PendingVenueOperation.CANCEL
        )
        if effect.acceptance_set_state in {
            AcceptanceSetState.OPEN,
            AcceptanceSetState.INVALIDATED,
        } and not safely_local(effect):
            waiting_buy_parents.append(effect)
        if not safely_local(effect) and not known:
            unknown_buy_effects.append(effect)

    binding = book.execution_binding(POSITION_SCOPE)
    if not effects:
        execution_binding_matches = bool(
            binding is None
            and book.execution_registry_count is None
            and book.execution_registry_commitment is None
        )
    else:
        execution_binding_matches = bool(
            binding is not None
            and binding.position_commitment == execution.position.commitment
            and binding.root_heads_commitment == execution.root_heads.commitment
            and binding.integrity_bits == execution.integrity.value
            and book.execution_registry_count == execution.seen_facts.count
            and book.execution_registry_commitment == execution.seen_facts.commitment
        )
    target = next(
        (effect for effect in effects if effect.effect_id == target_effect_id),
        None,
    )
    return _SlowSymbolView(
        execution_binding_matches=execution_binding_matches,
        account_reconciliation_clear=not any(
            not record.attribution_resolved for record in book.execution_reconciliations
        ),
        blocking_effect_count=len(unresolved),
        blocking_buy_effect_count=len(unresolved_buys),
        target_exemptible_count=(
            1 if target is not None and safely_local(target) else 0
        ),
        stand_downable_buy_count=sum(
            safely_local(effect) for effect in unresolved_buys
        ),
        known_cancellable_buy_leg_count=len(cancellable_legs),
        known_cancel_pending_buy_leg_count=len(cancel_pending_legs),
        waiting_buy_parent_count=len(waiting_buy_parents),
        unknown_buy_effect_count=len(unknown_buy_effects),
    )


class SymbolGateMachine(RuleBasedStateMachine):
    """Compare bounded venue indexes to an independent materialized fold."""

    def __init__(self) -> None:
        super().__init__()
        self.book = VenueRecoveryBook.empty(VENUE_SCOPE)
        self.execution = EXECUTION
        self.stage = "empty"
        self.target_effect_id: EffectId | None = None
        self.buy_effect_id = EffectId("symbol-machine-buy-effect")
        self.cancel_effect_id = EffectId("symbol-machine-cancel-effect")

    def _commit(
        self,
        item: object,
        *,
        internal: bool = False,
        expected: VenueRecoveryDisposition = VenueRecoveryDisposition.APPLIED,
    ) -> None:
        reducer = (
            _private_venue_apply
            if internal or type(item) is CloseAcceptanceSet
            else apply_venue_recovery_input
        )
        before = (self.book, self.execution, item)
        first = reducer(self.book, self.execution, item)
        second = reducer(self.book, self.execution, item)
        assert second == first
        assert before == (self.book, self.execution, item)
        assert first.disposition is expected
        self.book = first.book
        self.execution = first.execution

    def _assert_oracle(self) -> None:
        import app.execution_core.venue as venue

        assert hasattr(venue, "_venue_authority_view")
        actual = venue._venue_authority_view(
            self.book,
            self.execution,
            POSITION_SCOPE,
            self.target_effect_id,
        )
        actual_tuple = tuple(getattr(actual, field) for field in _SYMBOL_VIEW_FIELDS)
        assert actual_tuple == astuple(
            _slow_symbol_view(self.book, self.execution, self.target_effect_id)
        )

    @precondition(lambda self: self.stage == "empty")
    @rule()
    def request_safely_local_buy(self) -> None:
        self._commit(
            RequestedEffect(
                input_id=VenueInputId("symbol-machine-buy-request-input"),
                effect_id=self.buy_effect_id,
                request_occurrence_id=RequestOccurrenceId(
                    "symbol-machine-buy-occurrence"
                ),
                mandate_id=MandateId("symbol-machine-buy-mandate"),
                kind=EffectKind.SUBMIT,
                client_order_id=ClientOrderId("symbol-machine-buy-client"),
                symbol_id=SYMBOL,
                side=ExecutionSide.BUY,
                quantity=Quantity(2),
                economic_scope=b"symbol-machine|BUY|2",
                target_leg_key=None,
            ),
            internal=True,
        )
        self.target_effect_id = self.buy_effect_id
        self.stage = "requested"

    @precondition(lambda self: self.stage == "requested")
    @rule()
    def stand_down_safely_local_buy(self) -> None:
        self._commit(
            CancelBeforeDispatch(
                input_id=VenueInputId("symbol-machine-stand-down-input"),
                effect_id=self.buy_effect_id,
            ),
            internal=True,
        )
        self.target_effect_id = None
        self.stage = "stood-down"

    @precondition(lambda self: self.stage == "stood-down")
    @rule()
    def close_never_dispatched_buy(self) -> None:
        self._commit(
            CloseAcceptanceSet(
                input_id=VenueInputId("symbol-machine-local-close-input"),
                effect_id=self.buy_effect_id,
                proof=_proof(
                    self.book,
                    self.buy_effect_id,
                    "symbol-machine-local-close",
                    kind=AcceptanceProofKind.NEVER_DISPATCHED,
                ),
            )
        )
        self.stage = "local-closed"

    @precondition(lambda self: self.stage == "requested")
    @rule()
    def claim_buy_without_a_leg(self) -> None:
        self._commit(
            RecordDispatchClaim(
                input_id=VenueInputId("symbol-machine-buy-claim-input"),
                effect_id=self.buy_effect_id,
                claim_occurrence_id=ClaimOccurrenceId("symbol-machine-buy-claim"),
            ),
            internal=True,
        )
        self.target_effect_id = None
        self.stage = "claimed-no-leg"

    @precondition(lambda self: self.stage == "claimed-no-leg")
    @rule()
    def acknowledge_claimed_buy(self) -> None:
        self._commit(
            RecordTransportOutcome(
                input_id=VenueInputId("symbol-machine-buy-ack-input"),
                effect_id=self.buy_effect_id,
                state=BrokerEffectState.ACKNOWLEDGED,
            )
        )
        self.stage = "acknowledged-no-leg"

    @precondition(lambda self: self.stage == "acknowledged-no-leg")
    @rule()
    def discover_cancellable_buy_leg(self) -> None:
        self._commit(
            DiscoverVenueLeg(
                input_id=VenueInputId("symbol-machine-discover-input"),
                effect_id=self.buy_effect_id,
                leg_key=LEG,
                observation_id=VenueObservationId("symbol-machine-discovery"),
            )
        )
        self.stage = "working"

    @precondition(lambda self: self.stage == "working")
    @rule()
    def request_target_bound_cancel(self) -> None:
        self._commit(
            RequestedEffect(
                input_id=VenueInputId("symbol-machine-cancel-request-input"),
                effect_id=self.cancel_effect_id,
                request_occurrence_id=RequestOccurrenceId(
                    "symbol-machine-cancel-occurrence"
                ),
                mandate_id=MandateId("symbol-machine-cancel-mandate"),
                kind=EffectKind.CANCEL,
                client_order_id=None,
                symbol_id=SYMBOL,
                side=ExecutionSide.BUY,
                quantity=Quantity(2),
                economic_scope=b"symbol-machine|CANCEL|authority-stateful-leg",
                target_leg_key=LEG,
            ),
            internal=True,
        )
        assert all(
            owner.effect_id != self.cancel_effect_id for owner in self.book.owners
        )
        self.target_effect_id = self.cancel_effect_id
        self.stage = "cancel-requested"

    @precondition(lambda self: self.stage == "cancel-requested")
    @rule()
    def claim_target_bound_cancel(self) -> None:
        self._commit(
            RecordDispatchClaim(
                input_id=VenueInputId("symbol-machine-cancel-claim-input"),
                effect_id=self.cancel_effect_id,
                claim_occurrence_id=ClaimOccurrenceId("symbol-machine-cancel-claim"),
            ),
            internal=True,
        )
        self.target_effect_id = None
        self.stage = "cancel-claimed"

    @precondition(lambda self: self.stage == "cancel-claimed")
    @rule()
    def cancel_acknowledgement_is_nonterminal(self) -> None:
        self._commit(
            RecordTransportOutcome(
                input_id=VenueInputId("symbol-machine-cancel-ack-input"),
                effect_id=self.cancel_effect_id,
                state=BrokerEffectState.ACKNOWLEDGED,
            )
        )
        attempt = self.book.active_attempt(LEG)
        assert attempt is not None
        assert attempt.status is VenueAttemptState.WORKING
        assert attempt.pending_operation is PendingVenueOperation.CANCEL
        assert self.book.closure_head(LEG) is None
        self.stage = "cancel-acknowledged"

    @precondition(lambda self: self.stage == "cancel-acknowledged")
    @rule()
    def terminalize_target_leg(self) -> None:
        self._commit(
            ObserveVenueStatus(
                input_id=VenueInputId("symbol-machine-terminal-input"),
                leg_key=LEG,
                status=VenueAttemptState.CANCELED,
                observation_id=VenueObservationId("symbol-machine-terminal"),
                cumulative_quantity=Quantity(0),
                closure_id=ClosureId("symbol-machine-terminal-closure"),
                evidence_reference=EvidenceReference(
                    "symbol-machine-terminal-evidence"
                ),
            )
        )
        self.stage = "target-terminal-parent-open"

    @precondition(lambda self: self.stage == "target-terminal-parent-open")
    @rule()
    def close_cancel_occurrence(self) -> None:
        self._commit(
            CloseAcceptanceSet(
                input_id=VenueInputId("symbol-machine-cancel-close-input"),
                effect_id=self.cancel_effect_id,
                proof=_proof(
                    self.book,
                    self.cancel_effect_id,
                    "symbol-machine-cancel-close",
                ),
            )
        )
        self.stage = "cancel-closed-buy-open"

    @precondition(lambda self: self.stage == "cancel-closed-buy-open")
    @rule()
    def close_buy_occurrence(self) -> None:
        self._commit(
            CloseAcceptanceSet(
                input_id=VenueInputId("symbol-machine-buy-close-input"),
                effect_id=self.buy_effect_id,
                proof=_proof(
                    self.book,
                    self.buy_effect_id,
                    "symbol-machine-buy-close",
                ),
            )
        )
        self.stage = "resolved"

    @precondition(lambda self: self.stage == "resolved")
    @rule()
    def late_acceptance_invalidates_exact_parent(self) -> None:
        self._commit(
            DiscoverVenueLeg(
                input_id=VenueInputId("symbol-machine-late-discover-input"),
                effect_id=self.buy_effect_id,
                leg_key=LATE_LEG,
                observation_id=VenueObservationId("symbol-machine-late-discovery"),
            ),
            expected=VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
        )
        effect = self.book.effect(self.buy_effect_id)
        assert effect is not None
        assert effect.acceptance_set_state is AcceptanceSetState.INVALIDATED
        self.stage = "invalidated"

    @precondition(lambda self: self.stage in {"local-closed", "invalidated"})
    @rule()
    def terminal_symbol_history_remains_auditable(self) -> None:
        self._assert_oracle()

    @invariant()
    def cached_view_matches_slow_canonical_fold(self) -> None:
        self._assert_oracle()


class ManualFlattenMachine(RuleBasedStateMachine):
    """Generate bounded local, unknown, and targeted-cancel flatten histories."""

    def __init__(self) -> None:
        super().__init__()
        self.module = _authority_module()
        (
            self.disposition_type,
            self.reason_type,
            self.authority_input_type,
            self.flatten_id_type,
            self.claim_type,
            self.begin_type,
            self.advance_type,
            self.reducer,
        ) = _required(
            self.module,
            "AuthorityDisposition",
            "AuthorityReason",
            "AuthorityInputId",
            "ManualFlattenId",
            "ClaimEffect",
            "BeginManualFlatten",
            "AdvanceManualFlatten",
            "apply_execution_authority_input",
        )
        self.state = _forge_authority(self.module, remaining=12, reserve=2)
        self.execution = LONG_EXECUTION
        self.stage = "empty"
        self.flatten_id = self.flatten_id_type("manual-machine-flatten")
        self.buy_effect_id = EffectId("manual-machine-buy-effect")
        self.cancel_effect_id: EffectId | None = None
        self.sell_effect_id = EffectId("manual-machine-sell-effect")

    def _authority_commit(
        self,
        item: object,
        *,
        expected: object,
        update: bool = True,
    ) -> object:
        before = (self.state, self.execution, item)
        first = self.reducer(self.state, self.execution, item)
        second = self.reducer(self.state, self.execution, item)
        assert second == first
        assert before == (self.state, self.execution, item)
        assert first.disposition is expected
        if update:
            self.state = first.state
        else:
            assert first.state == self.state
        return first

    def _external_commit(
        self,
        item: object,
        *,
        expected: VenueRecoveryDisposition = VenueRecoveryDisposition.APPLIED,
    ) -> object:
        reducer = (
            _private_venue_apply
            if type(item) is CloseAcceptanceSet
            else apply_venue_recovery_input
        )
        before = (self.state.venue, self.execution, item)
        first = reducer(self.state.venue, self.execution, item)
        second = reducer(self.state.venue, self.execution, item)
        assert second == first
        assert before == (self.state.venue, self.execution, item)
        assert first.disposition is expected
        self.state = _forge_venue(self.state, first.book)
        self.execution = first.execution
        return first

    def _claim(self, label: str, effect_id: EffectId) -> object:
        return self.claim_type(
            input_id=self.authority_input_type(f"{label}-claim-input"),
            effect_id=effect_id,
            claim_occurrence_id=ClaimOccurrenceId(f"{label}-claim"),
        )

    def _begin(self, label: str) -> object:
        return self.begin_type(
            input_id=self.authority_input_type(f"{label}-begin-input"),
            flatten_id=self.flatten_id,
            session_id=self.state.session_id,
            symbol_id=SYMBOL,
            actor=ActorId("manual-machine-operator"),
            reason="generated manual flatten",
            evidence_reference=EvidenceReference("manual-machine-evidence"),
            emergency_grant_id=None,
        )

    def _advance(self, label: str) -> object:
        return self.advance_type(
            input_id=self.authority_input_type(f"{label}-advance-input"),
            flatten_id=self.flatten_id,
        )

    def _set_reducing(self) -> None:
        self.state = _forge_authority(
            self.module,
            predecessor=self.state,
            mode="REDUCING",
            remaining=self.state.budget.remaining,
            reserve=self.state.budget.safety_reserve,
        )

    @rule()
    def audit_current_stage_without_mutation(self) -> None:
        """Keep every generated stage observable without filtering rule selection."""

        assert self.stage in {
            "empty",
            "local-requested",
            "claimed-no-leg",
            "working-buy",
            "cancel-requested",
            "cancel-claimed",
            "cancel-acknowledged",
            "cancel-ack-checked",
            "target-terminal-parent-open",
            "parents-closed",
            "late-fill-applied",
            "ready",
            "sell-requested",
            "done",
        }
        assert self.state.budget.remaining >= 0
        assert self.state.budget.safety_reserve >= 0
        assert self.execution.position.raw_quantity >= 5

    def _seed_buy(self, label: str, *, claim: bool, discover: bool) -> None:
        created = _create_effect(
            self.module,
            self.state,
            self.execution,
            label,
            side=ExecutionSide.BUY,
            quantity=2,
        )
        assert created.disposition is self.disposition_type.APPLIED
        self.state = created.state
        self.buy_effect_id = EffectId(f"{label}-effect")
        if not claim:
            return
        claimed = self._authority_commit(
            self._claim(label, self.buy_effect_id),
            expected=self.disposition_type.APPLIED,
        )
        assert claimed.fresh_claim is not None
        if not discover:
            return
        self._external_commit(
            RecordTransportOutcome(
                input_id=VenueInputId(f"{label}-ack-input"),
                effect_id=self.buy_effect_id,
                state=BrokerEffectState.ACKNOWLEDGED,
            )
        )
        self._external_commit(
            DiscoverVenueLeg(
                input_id=VenueInputId(f"{label}-discover-input"),
                effect_id=self.buy_effect_id,
                leg_key=LEG,
                observation_id=VenueObservationId(f"{label}-discovery"),
            )
        )

    @precondition(lambda self: self.stage == "empty")
    @rule()
    def seed_safely_local_buy(self) -> None:
        self._seed_buy("manual-local", claim=False, discover=False)
        self.stage = "local-requested"

    @precondition(lambda self: self.stage == "local-requested")
    @rule()
    def local_buy_is_stood_down_atomically(self) -> None:
        self._set_reducing()
        transition = self._authority_commit(
            self._begin("manual-local"),
            expected=self.disposition_type.APPLIED,
        )
        effect = transition.state.venue.effect(self.buy_effect_id)
        assert effect is not None
        assert effect.state is BrokerEffectState.CANCELED_BEFORE_DISPATCH
        assert effect.acceptance_set_state is AcceptanceSetState.CLOSED
        assert transition.created_effect_ids == ()
        assert transition.fresh_claim is None
        self.stage = "done"

    @precondition(lambda self: self.stage == "empty")
    @rule()
    def seed_claimed_buy_without_leg(self) -> None:
        self._seed_buy("manual-unknown", claim=True, discover=False)
        self.stage = "claimed-no-leg"

    @precondition(lambda self: self.stage == "claimed-no-leg")
    @rule()
    def claimed_buy_without_leg_refuses_flatten(self) -> None:
        self._set_reducing()
        budget = self.state.budget
        transition = self._authority_commit(
            self._begin("manual-unknown"),
            expected=self.disposition_type.REFUSED,
            update=False,
        )
        assert transition.reason is self.reason_type.VENUE_UNCERTAIN
        assert transition.state.budget == budget
        assert transition.created_effect_ids == ()
        assert transition.fresh_claim is None
        self.stage = "done"

    @precondition(lambda self: self.stage == "empty")
    @rule()
    def seed_known_cancellable_buy(self) -> None:
        self._seed_buy("manual-machine-buy", claim=True, discover=True)
        self.stage = "working-buy"

    @precondition(lambda self: self.stage == "working-buy")
    @rule()
    def begin_cancellable_flatten(self) -> None:
        self._set_reducing()
        owners_before = self.state.venue.owners
        transition = self._authority_commit(
            self._begin("manual-machine"),
            expected=self.disposition_type.APPLIED,
        )
        assert len(transition.created_effect_ids) == 1
        self.cancel_effect_id = transition.created_effect_ids[0]
        cancel = transition.state.venue.effect(self.cancel_effect_id)
        assert cancel is not None
        assert cancel.scope.kind is EffectKind.CANCEL
        assert cancel.scope.client_order_id is None
        assert cancel.scope.target_leg_key == LEG
        assert transition.state.venue.owners == owners_before
        assert transition.fresh_claim is None
        self.stage = "cancel-requested"

    @precondition(lambda self: self.stage == "cancel-requested")
    @rule()
    def pre_ready_manual_sell_is_refused(self) -> None:
        budget = self.state.budget
        refused = _create_effect(
            self.module,
            self.state,
            self.execution,
            "manual-machine-premature-sell",
            side=ExecutionSide.SELL,
            quantity=self.execution.position.authorized_residual_sell.value,
            manual_flatten_id=self.flatten_id,
        )
        assert refused.disposition is self.disposition_type.REFUSED
        assert refused.reason is not None
        assert refused.state == self.state
        assert refused.state.budget == budget
        assert refused.created_effect_ids == ()
        assert refused.fresh_claim is None

    @precondition(lambda self: self.stage == "cancel-requested")
    @rule()
    def claim_cancel_from_reserved_capacity(self) -> None:
        assert self.cancel_effect_id is not None
        self.state = _forge_authority(
            self.module,
            predecessor=self.state,
            mode="REDUCING",
            remaining=2,
            reserve=2,
        )
        transition = self._authority_commit(
            self._claim("manual-machine-cancel", self.cancel_effect_id),
            expected=self.disposition_type.APPLIED,
        )
        assert transition.fresh_claim is not None
        assert transition.state.budget.remaining == 1
        self.stage = "cancel-claimed"

    @precondition(lambda self: self.stage == "cancel-claimed")
    @rule()
    def cancel_ack_is_not_terminal(self) -> None:
        assert self.cancel_effect_id is not None
        self._external_commit(
            RecordTransportOutcome(
                input_id=VenueInputId("manual-machine-cancel-ack-input"),
                effect_id=self.cancel_effect_id,
                state=BrokerEffectState.ACKNOWLEDGED,
            )
        )
        attempt = self.state.venue.active_attempt(LEG)
        assert attempt is not None
        assert attempt.status is VenueAttemptState.WORKING
        assert attempt.pending_operation is PendingVenueOperation.CANCEL
        assert self.state.venue.closure_head(LEG) is None
        self.stage = "cancel-acknowledged"

    @precondition(lambda self: self.stage == "cancel-acknowledged")
    @rule()
    def advance_refuses_cancel_ack_only(self) -> None:
        budget = self.state.budget
        transition = self._authority_commit(
            self._advance("manual-cancel-ack"),
            expected=self.disposition_type.REFUSED,
            update=False,
        )
        assert transition.reason is self.reason_type.VENUE_UNCERTAIN
        assert transition.state.budget == budget
        self.stage = "cancel-ack-checked"

    @precondition(lambda self: self.stage == "cancel-ack-checked")
    @rule()
    def terminal_leg_still_has_open_parent(self) -> None:
        self._external_commit(
            ObserveVenueStatus(
                input_id=VenueInputId("manual-machine-terminal-input"),
                leg_key=LEG,
                status=VenueAttemptState.CANCELED,
                observation_id=VenueObservationId("manual-machine-terminal"),
                cumulative_quantity=Quantity(0),
                closure_id=ClosureId("manual-machine-terminal-closure"),
                evidence_reference=EvidenceReference(
                    "manual-machine-terminal-evidence"
                ),
            )
        )
        transition = self._authority_commit(
            self._advance("manual-parent-open"),
            expected=self.disposition_type.REFUSED,
            update=False,
        )
        assert transition.reason is self.reason_type.VENUE_UNCERTAIN
        assert transition.created_effect_ids == ()
        self.stage = "target-terminal-parent-open"

    @precondition(lambda self: self.stage == "target-terminal-parent-open")
    @rule()
    def close_cancel_then_buy_occurrences(self) -> None:
        assert self.cancel_effect_id is not None
        for effect_id, label in (
            (self.cancel_effect_id, "manual-machine-cancel"),
            (self.buy_effect_id, "manual-machine-buy"),
        ):
            self._external_commit(
                CloseAcceptanceSet(
                    input_id=VenueInputId(f"{label}-close-input"),
                    effect_id=effect_id,
                    proof=_proof(self.state.venue, effect_id, f"{label}-close"),
                )
            )
        self.stage = "parents-closed"

    @precondition(lambda self: self.stage == "parents-closed")
    @rule()
    def late_correlated_buy_fill_is_applied_before_final_sell(self) -> None:
        before_quantity = self.execution.position.raw_quantity
        transition = self._external_commit(
            RecordBrokerFillEvidence(
                input_id=VenueInputId("manual-machine-late-fill-input"),
                effect_id=self.buy_effect_id,
                leg_key=LEG,
                prior_cumulative_quantity=Quantity(0),
                resulting_cumulative_quantity=Quantity(1),
                fact=_broker_fill(
                    "manual-machine-late-fill",
                    leg_key=LEG,
                    quantity=1,
                ),
                evidence_digest=b"\x91" * 32,
                closure_id=ClosureId("manual-machine-late-fill-closure"),
                evidence_reference=EvidenceReference(
                    "manual-machine-late-fill-evidence"
                ),
            )
        )
        assert transition.quantity_delta == 1
        assert self.execution.position.raw_quantity == before_quantity + 1
        self.stage = "late-fill-applied"

    @precondition(lambda self: self.stage == "late-fill-applied")
    @rule()
    def exact_closure_allows_flatten_progress(self) -> None:
        self.state = _forge_authority(
            self.module,
            predecessor=self.state,
            mode="REDUCING",
            remaining=4,
            reserve=2,
        )
        transition = self._authority_commit(
            self._advance("manual-ready"),
            expected=self.disposition_type.APPLIED,
        )
        assert transition.created_effect_ids == ()
        assert transition.fresh_claim is None
        self.stage = "ready"

    @precondition(lambda self: self.stage == "ready")
    @rule()
    def create_quantity_capped_manual_sell(self) -> None:
        residual = self.execution.position.authorized_residual_sell.value
        created = _create_effect(
            self.module,
            self.state,
            self.execution,
            "manual-machine-sell",
            side=ExecutionSide.SELL,
            quantity=residual,
            manual_flatten_id=self.flatten_id,
        )
        assert created.disposition is self.disposition_type.APPLIED
        assert created.created_effect_ids == (self.sell_effect_id,)
        self.state = created.state
        self.stage = "sell-requested"

    @precondition(lambda self: self.stage == "sell-requested")
    @rule()
    def second_manual_sell_for_same_flatten_is_refused(self) -> None:
        budget = self.state.budget
        refused = _create_effect(
            self.module,
            self.state,
            self.execution,
            "manual-machine-second-sell",
            side=ExecutionSide.SELL,
            quantity=self.execution.position.authorized_residual_sell.value,
            manual_flatten_id=self.flatten_id,
        )
        assert refused.disposition is self.disposition_type.REFUSED
        assert refused.reason is not None
        assert refused.state == self.state
        assert refused.state.budget == budget
        assert refused.created_effect_ids == ()
        assert refused.fresh_claim is None

    @precondition(lambda self: self.stage == "sell-requested")
    @rule()
    def final_sell_claim_succeeds_with_unchanged_canonical_residual(self) -> None:
        before = self.state.budget.remaining
        transition = self._authority_commit(
            self._claim("manual-machine-sell", self.sell_effect_id),
            expected=self.disposition_type.APPLIED,
        )
        assert transition.fresh_claim is not None
        assert transition.state.budget.remaining == before - 1
        assert (
            transition.fresh_claim.effect_scope.quantity
            == self.execution.position.authorized_residual_sell
        )
        self.stage = "done"

    @precondition(lambda self: self.stage == "sell-requested")
    @rule()
    def final_sell_claim_refuses_after_canonical_residual_shrink(self) -> None:
        book, execution, shrink_effect_id = _seed_raw_effect(
            self.state.venue,
            self.execution,
            "manual-shrink",
            claim=True,
            leg_key=SHRINK_LEG,
            side=ExecutionSide.SELL,
            quantity=1,
        )
        shrunk = _venue_apply_twice(
            book,
            execution,
            RecordBrokerFillEvidence(
                input_id=VenueInputId("manual-shrink-fill-input"),
                effect_id=shrink_effect_id,
                leg_key=SHRINK_LEG,
                prior_cumulative_quantity=Quantity(0),
                resulting_cumulative_quantity=Quantity(1),
                fact=_broker_fill(
                    "manual-shrink-fill",
                    leg_key=SHRINK_LEG,
                    quantity=1,
                    side=ExecutionSide.SELL,
                ),
                evidence_digest=b"\x92" * 32,
                closure_id=None,
                evidence_reference=None,
            ),
        )
        terminal = _venue_apply_twice(
            shrunk.book,
            shrunk.execution,
            ObserveVenueStatus(
                input_id=VenueInputId("manual-shrink-terminal-input"),
                leg_key=SHRINK_LEG,
                status=VenueAttemptState.FILLED,
                observation_id=VenueObservationId("manual-shrink-terminal"),
                cumulative_quantity=Quantity(1),
                closure_id=ClosureId("manual-shrink-fill-closure"),
                evidence_reference=EvidenceReference("manual-shrink-fill-evidence"),
            ),
        )
        closed = _venue_apply_twice(
            terminal.book,
            terminal.execution,
            CloseAcceptanceSet(
                input_id=VenueInputId("manual-shrink-close-input"),
                effect_id=shrink_effect_id,
                proof=_proof(
                    terminal.book,
                    shrink_effect_id,
                    "manual-shrink-close",
                ),
            ),
        )
        assert closed.execution.position.raw_quantity == (
            self.execution.position.raw_quantity - 1
        )
        self.state = _forge_venue(self.state, closed.book)
        self.execution = closed.execution
        before = self.state.budget.remaining
        retained = self.state.venue.effect(self.sell_effect_id)
        transition = self._authority_commit(
            self._claim("manual-machine-sell", self.sell_effect_id),
            expected=self.disposition_type.REFUSED,
            update=False,
        )
        assert transition.reason is self.reason_type.RESIDUAL_EXCEEDED
        assert transition.state.budget.remaining == before
        assert transition.state.venue.effect(self.sell_effect_id) == retained
        assert transition.fresh_claim is None
        self.stage = "done"

    @precondition(lambda self: self.stage == "done")
    @rule()
    def completed_history_remains_inert(self) -> None:
        assert self.state.budget.remaining >= 0
        assert self.execution.position.raw_quantity >= 5

    @invariant()
    def refusal_never_spends_below_zero_or_changes_execution(self) -> None:
        assert self.state.budget.remaining >= 0
        assert self.state.budget.safety_reserve >= 0
        assert self.execution.position.raw_quantity >= 5


def test_engage_kill_successor_replay_and_conflict_are_atomic() -> None:
    module = _authority_module()
    disposition_type, authority_input_type, engage_kill_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityInputId",
        "EngageKill",
    )
    predecessor = _forge_authority(module, remaining=5, reserve=2)
    command = engage_kill_type(
        input_id=authority_input_type("kill-replay-input"),
        actor=ActorId("kill-replay-operator"),
        reason="engage exact kill",
        evidence_reference=EvidenceReference("kill-replay-evidence"),
    )
    applied = _authority_apply_twice(module, predecessor, EXECUTION, command)
    assert applied.disposition is disposition_type.APPLIED
    assert applied.state.kill_engaged is True
    assert applied.state.budget == predecessor.budget
    assert applied.created_effect_ids == ()
    assert applied.fresh_claim is None

    replay = _authority_apply_twice(module, applied.state, EXECUTION, command)
    assert replay.disposition is disposition_type.EXACT_REPLAY
    assert replay.state == applied.state
    assert replay.state.budget == applied.state.budget
    assert replay.created_effect_ids == ()
    assert replay.fresh_claim is None

    conflict = _authority_apply_twice(
        module,
        applied.state,
        EXECUTION,
        replace(command, reason="changed kill payload"),
    )
    assert conflict.disposition is disposition_type.CONFLICT
    assert conflict.state == applied.state
    assert conflict.state.budget == applied.state.budget
    assert conflict.created_effect_ids == ()
    assert conflict.fresh_claim is None


def test_engage_kill_stands_down_all_unclaimed_account_effects_atomically() -> None:
    module = _authority_module()
    disposition_type, authority_input_type, engage_kill_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityInputId",
        "EngageKill",
    )
    book, _, first_unclaimed_id = _seed_raw_effect(
        VenueRecoveryBook.empty(VENUE_SCOPE),
        EXECUTION,
        "kill-account-aapl",
        claim=False,
        leg_key=None,
    )
    book, _, second_unclaimed_id = _seed_raw_effect(
        book,
        OTHER_EXECUTION,
        "kill-account-msft",
        claim=False,
        leg_key=None,
        symbol_id=OTHER_SYMBOL,
    )
    book, _, claimed_id = _seed_raw_effect(
        book,
        EXECUTION,
        "kill-account-claimed",
        claim=True,
        leg_key=None,
    )
    predecessor = _forge_venue(
        _forge_authority(module, remaining=7, reserve=2),
        book,
    )
    claimed_before = predecessor.venue.effect(claimed_id)
    owners_before = predecessor.venue.owners
    command = engage_kill_type(
        input_id=authority_input_type("kill-account-input"),
        actor=ActorId("kill-account-operator"),
        reason="stand down all unclaimed account work",
        evidence_reference=EvidenceReference("kill-account-evidence"),
    )
    applied = _authority_apply_twice(module, predecessor, EXECUTION, command)
    assert applied.disposition is disposition_type.APPLIED
    for effect_id in (first_unclaimed_id, second_unclaimed_id):
        effect = applied.state.venue.effect(effect_id)
        assert effect is not None
        assert effect.state is BrokerEffectState.CANCELED_BEFORE_DISPATCH
        assert effect.acceptance_set_state is AcceptanceSetState.CLOSED
        assert effect.claim_occurrence_id is None
    assert applied.state.venue.effect(claimed_id) == claimed_before
    assert applied.state.budget == predecessor.budget
    assert applied.state.venue.owners == owners_before
    assert applied.created_effect_ids == ()
    assert applied.fresh_claim is None

    replay = _authority_apply_twice(module, applied.state, EXECUTION, command)
    assert replay.disposition is disposition_type.EXACT_REPLAY
    assert replay.state == applied.state
    assert replay.created_effect_ids == ()
    assert replay.fresh_claim is None


def test_engage_kill_latches_when_atomic_stand_down_cannot_be_reconciled() -> None:
    module = _authority_module()
    disposition_type, authority_input_type, engage_kill_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityInputId",
        "EngageKill",
    )
    predecessor = _forge_authority(module, remaining=5, reserve=2)
    created = _create_effect(
        module,
        predecessor,
        EXECUTION,
        "kill-stale-binding",
        side=ExecutionSide.BUY,
        quantity=1,
    )
    assert created.disposition is disposition_type.APPLIED
    stale_execution = _apply_fact(
        EXECUTION,
        _broker_fill("kill-stale-binding", leg_key=LEG, quantity=1),
    )
    command = engage_kill_type(
        input_id=authority_input_type("kill-stale-binding-input"),
        actor=ActorId("kill-stale-binding-operator"),
        reason="kill must latch despite stale cleanup binding",
        evidence_reference=EvidenceReference("kill-stale-binding-evidence"),
    )

    applied = _authority_apply_twice(
        module,
        created.state,
        stale_execution,
        command,
    )
    assert applied.disposition is disposition_type.APPLIED
    assert applied.state.kill_engaged is True
    assert applied.state.venue == created.state.venue
    assert applied.state.budget == created.state.budget
    assert applied.created_effect_ids == ()
    assert applied.fresh_claim is None


def test_begin_manual_flatten_successor_replay_and_conflict_are_atomic() -> None:
    module = _authority_module()
    disposition_type, flatten_id_type = _required(
        module,
        "AuthorityDisposition",
        "ManualFlattenId",
    )
    book, execution, buy_effect_id = _seed_raw_effect(
        VenueRecoveryBook.empty(VENUE_SCOPE),
        LONG_EXECUTION,
        "begin-replay-local",
        claim=False,
        leg_key=None,
    )
    predecessor = _forge_authority(
        module,
        mode="REDUCING",
        remaining=5,
        reserve=2,
    )
    predecessor = _forge_venue(predecessor, book)
    flatten_id = flatten_id_type("begin-replay-flatten")
    command = _manual_begin(module, predecessor, flatten_id, "begin-replay")
    applied = _authority_apply_twice(module, predecessor, execution, command)
    assert applied.disposition is disposition_type.APPLIED
    stood_down = applied.state.venue.effect(buy_effect_id)
    assert stood_down is not None
    assert stood_down.state is BrokerEffectState.CANCELED_BEFORE_DISPATCH
    assert stood_down.acceptance_set_state is AcceptanceSetState.CLOSED
    assert applied.state.budget == predecessor.budget
    assert applied.created_effect_ids == ()
    assert applied.fresh_claim is None

    replay = _authority_apply_twice(module, applied.state, execution, command)
    assert replay.disposition is disposition_type.EXACT_REPLAY
    assert replay.state == applied.state
    assert replay.state.venue.effect(buy_effect_id) == stood_down
    assert replay.state.budget == applied.state.budget
    assert replay.created_effect_ids == ()
    assert replay.fresh_claim is None

    conflict = _authority_apply_twice(
        module,
        applied.state,
        execution,
        replace(command, reason="changed flatten payload"),
    )
    assert conflict.disposition is disposition_type.CONFLICT
    assert conflict.state == applied.state
    assert conflict.state.venue.effect(buy_effect_id) == stood_down
    assert conflict.state.budget == applied.state.budget
    assert conflict.created_effect_ids == ()
    assert conflict.fresh_claim is None


def test_advance_manual_flatten_successor_replay_and_conflict_are_atomic() -> None:
    module = _authority_module()
    disposition_type, flatten_id_type = _required(
        module,
        "AuthorityDisposition",
        "ManualFlattenId",
    )
    predecessor, execution, flatten_id = _manual_advance_predecessor(
        module,
        "advance-replay",
    )
    command = _manual_advance(module, flatten_id, "advance-replay")
    applied = _authority_apply_twice(module, predecessor, execution, command)
    assert applied.disposition is disposition_type.APPLIED
    assert applied.state.budget == predecessor.budget
    assert applied.created_effect_ids == ()
    assert applied.fresh_claim is None

    replay = _authority_apply_twice(module, applied.state, execution, command)
    assert replay.disposition is disposition_type.EXACT_REPLAY
    assert replay.state == applied.state
    assert replay.state.budget == applied.state.budget
    assert replay.created_effect_ids == ()
    assert replay.fresh_claim is None

    conflict = _authority_apply_twice(
        module,
        applied.state,
        execution,
        replace(
            command,
            flatten_id=flatten_id_type("advance-replay-different-flatten"),
        ),
    )
    assert conflict.disposition is disposition_type.CONFLICT
    assert conflict.state == applied.state
    assert conflict.state.budget == applied.state.budget
    assert conflict.created_effect_ids == ()
    assert conflict.fresh_claim is None


def test_manual_flatten_waits_for_its_cancel_acceptance_parent_to_close() -> None:
    module = _authority_module()
    disposition_type, reason_type, authority_input_type, claim_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "AuthorityInputId",
        "ClaimEffect",
    )
    state, execution, flatten_id, buy_effect_id, cancel_effect_id = (
        _begin_waiting_manual_flatten(module, "cancel-parent-open")
    )
    claimed = _authority_apply_twice(
        module,
        state,
        execution,
        claim_type(
            input_id=authority_input_type("cancel-parent-open-claim-input"),
            effect_id=cancel_effect_id,
            claim_occurrence_id=ClaimOccurrenceId("cancel-parent-open-claim"),
        ),
    )
    acknowledged = _venue_apply_twice(
        claimed.state.venue,
        execution,
        RecordTransportOutcome(
            input_id=VenueInputId("cancel-parent-open-ack-input"),
            effect_id=cancel_effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    terminal = _venue_apply_twice(
        acknowledged.book,
        execution,
        ObserveVenueStatus(
            input_id=VenueInputId("cancel-parent-open-terminal-input"),
            leg_key=LEG,
            status=VenueAttemptState.CANCELED,
            observation_id=VenueObservationId("cancel-parent-open-terminal"),
            cumulative_quantity=Quantity(0),
            closure_id=ClosureId("cancel-parent-open-terminal-closure"),
            evidence_reference=EvidenceReference(
                "cancel-parent-open-terminal-evidence"
            ),
        ),
    )
    buy_closed = _venue_apply_twice(
        terminal.book,
        terminal.execution,
        CloseAcceptanceSet(
            input_id=VenueInputId("cancel-parent-open-buy-close-input"),
            effect_id=buy_effect_id,
            proof=_proof(
                terminal.book,
                buy_effect_id,
                "cancel-parent-open-buy-close",
            ),
        ),
    )
    predecessor = _forge_venue(claimed.state, buy_closed.book)

    refused = _authority_apply_twice(
        module,
        predecessor,
        buy_closed.execution,
        _manual_advance(module, flatten_id, "cancel-parent-open"),
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.VENUE_UNCERTAIN
    assert refused.state == predecessor
    cancel = refused.state.venue.effect(cancel_effect_id)
    assert cancel is not None
    assert cancel.acceptance_set_state is AcceptanceSetState.OPEN


def test_manual_flatten_atomically_cancels_every_known_buy_leg() -> None:
    module = _authority_module()
    disposition_type, flatten_id_type = _required(
        module,
        "AuthorityDisposition",
        "ManualFlattenId",
    )
    book = VenueRecoveryBook.empty(VENUE_SCOPE)
    execution = LONG_EXECUTION
    book, execution, local_effect_id = _seed_raw_effect(
        book,
        execution,
        "multi-known-local",
        claim=False,
        leg_key=None,
    )
    book, execution, known_effect_id = _seed_raw_effect(
        book,
        execution,
        "multi-known",
        claim=True,
        leg_key=LEG,
    )
    second_leg = _venue_apply_twice(
        book,
        execution,
        DiscoverVenueLeg(
            input_id=VenueInputId("multi-known-second-discover-input"),
            effect_id=known_effect_id,
            leg_key=SECOND_LEG,
            observation_id=VenueObservationId("multi-known-second-discovery"),
        ),
    )
    book = second_leg.book
    execution = second_leg.execution
    predecessor = _forge_authority(
        module,
        mode="REDUCING",
        remaining=8,
        reserve=2,
    )
    predecessor = _forge_venue(predecessor, book)
    owners_before = predecessor.venue.owners
    command = _manual_begin(
        module,
        predecessor,
        flatten_id_type("multi-known-flatten"),
        "multi-known",
    )
    applied = _authority_apply_twice(module, predecessor, execution, command)
    assert applied.disposition is disposition_type.APPLIED
    assert len(applied.created_effect_ids) == 2
    cancel_effects = tuple(
        applied.state.venue.effect(effect_id)
        for effect_id in applied.created_effect_ids
    )
    assert all(effect is not None for effect in cancel_effects)
    assert {
        effect.scope.target_leg_key for effect in cancel_effects if effect is not None
    } == {LEG, SECOND_LEG}
    assert all(
        effect is not None
        and effect.scope.kind is EffectKind.CANCEL
        and effect.scope.client_order_id is None
        for effect in cancel_effects
    )
    stood_down = applied.state.venue.effect(local_effect_id)
    assert stood_down is not None
    assert stood_down.state is BrokerEffectState.CANCELED_BEFORE_DISPATCH
    assert stood_down.acceptance_set_state is AcceptanceSetState.CLOSED
    assert applied.state.venue.owners == owners_before
    assert applied.state.budget == predecessor.budget
    assert applied.fresh_claim is None


def test_two_manual_flattens_cannot_reserve_the_same_buy_leg() -> None:
    module = _authority_module()
    disposition_type, reason_type, flatten_id_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ManualFlattenId",
    )
    book, execution, _ = _seed_raw_effect(
        VenueRecoveryBook.empty(VENUE_SCOPE),
        LONG_EXECUTION,
        "duplicate-flatten-target",
        claim=True,
        leg_key=LEG,
    )
    predecessor = _forge_venue(
        _forge_authority(
            module,
            mode="REDUCING",
            remaining=8,
            reserve=2,
        ),
        book,
    )
    first = _authority_apply_twice(
        module,
        predecessor,
        execution,
        _manual_begin(
            module,
            predecessor,
            flatten_id_type("duplicate-flatten-first"),
            "duplicate-flatten-first",
        ),
    )
    assert first.disposition is disposition_type.APPLIED
    assert len(first.created_effect_ids) == 1

    second = _authority_apply_twice(
        module,
        first.state,
        execution,
        _manual_begin(
            module,
            first.state,
            flatten_id_type("duplicate-flatten-second"),
            "duplicate-flatten-second",
        ),
    )
    assert second.disposition is disposition_type.REFUSED
    assert second.reason is reason_type.VENUE_UNCERTAIN
    assert second.state == first.state
    assert second.created_effect_ids == ()
    assert second.fresh_claim is None


def test_manual_flatten_mixed_local_and_unknown_buy_refuses_all_or_none() -> None:
    module = _authority_module()
    disposition_type, reason_type, flatten_id_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ManualFlattenId",
    )
    book, execution, local_effect_id = _seed_raw_effect(
        VenueRecoveryBook.empty(VENUE_SCOPE),
        LONG_EXECUTION,
        "mixed-local",
        claim=False,
        leg_key=None,
    )
    book, execution, known_effect_id = _seed_raw_effect(
        book,
        execution,
        "mixed-known",
        claim=True,
        leg_key=LEG,
    )
    book, execution, unknown_effect_id = _seed_raw_effect(
        book,
        execution,
        "mixed-unknown",
        claim=True,
        leg_key=None,
    )
    predecessor = _forge_authority(
        module,
        mode="REDUCING",
        remaining=8,
        reserve=2,
    )
    predecessor = _forge_venue(predecessor, book)
    local_before = predecessor.venue.effect(local_effect_id)
    known_before = predecessor.venue.effect(known_effect_id)
    unknown_before = predecessor.venue.effect(unknown_effect_id)
    owners_before = predecessor.venue.owners
    effect_count = len(predecessor.venue.effects)
    command = _manual_begin(
        module,
        predecessor,
        flatten_id_type("mixed-history-flatten"),
        "mixed-history",
    )
    refused = _authority_apply_twice(module, predecessor, execution, command)
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.VENUE_UNCERTAIN
    assert refused.state == predecessor
    assert refused.state.budget == predecessor.budget
    assert len(refused.state.venue.effects) == effect_count
    assert refused.state.venue.effect(local_effect_id) == local_before
    assert refused.state.venue.effect(known_effect_id) == known_before
    assert refused.state.venue.effect(unknown_effect_id) == unknown_before
    assert refused.state.venue.owners == owners_before
    assert refused.created_effect_ids == ()
    assert refused.fresh_claim is None


@pytest.mark.parametrize(
    ("mode", "kill_engaged", "expected_reason"),
    [
        ("HALTED", False, "MODE_BLOCKED"),
        ("REDUCING", True, "KILL_ENGAGED"),
    ],
)
def test_ordinary_manual_flatten_refuses_halt_or_kill_without_partial_mutation(
    mode: str,
    kill_engaged: bool,
    expected_reason: str,
) -> None:
    module = _authority_module()
    disposition_type, reason_type, flatten_id_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "ManualFlattenId",
    )
    label = f"blocked-flatten-{mode.lower()}-{kill_engaged}"
    book, execution, local_effect_id = _seed_raw_effect(
        VenueRecoveryBook.empty(VENUE_SCOPE),
        LONG_EXECUTION,
        label,
        claim=False,
        leg_key=None,
    )
    predecessor = _forge_authority(
        module,
        mode=mode,
        kill_engaged=kill_engaged,
        remaining=6,
        reserve=2,
    )
    predecessor = _forge_venue(predecessor, book)
    local_before = predecessor.venue.effect(local_effect_id)
    refused = _authority_apply_twice(
        module,
        predecessor,
        execution,
        _manual_begin(
            module,
            predecessor,
            flatten_id_type(f"{label}-id"),
            label,
        ),
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is getattr(reason_type, expected_reason)
    assert refused.state == predecessor
    assert refused.state.venue.effect(local_effect_id) == local_before
    assert refused.state.budget == predecessor.budget
    assert refused.created_effect_ids == ()
    assert refused.fresh_claim is None


def test_manual_flatten_session_mismatch_is_inert() -> None:
    module = _authority_module()
    disposition_type, reason_type, session_type, flatten_id_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "SessionId",
        "ManualFlattenId",
    )
    book, execution, local_effect_id = _seed_raw_effect(
        VenueRecoveryBook.empty(VENUE_SCOPE),
        LONG_EXECUTION,
        "session-mismatch-local",
        claim=False,
        leg_key=None,
    )
    predecessor = _forge_authority(
        module,
        mode="REDUCING",
        remaining=6,
        reserve=2,
    )
    predecessor = _forge_venue(predecessor, book)
    local_before = predecessor.venue.effect(local_effect_id)
    command = _manual_begin(
        module,
        predecessor,
        flatten_id_type("session-mismatch-flatten"),
        "session-mismatch",
        session_id=session_type("foreign-session"),
    )
    refused = _authority_apply_twice(
        module,
        predecessor,
        execution,
        command,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.SESSION_MISMATCH
    assert refused.state == predecessor
    assert refused.state.venue.effect(local_effect_id) == local_before
    assert refused.state.budget == predecessor.budget
    assert refused.created_effect_ids == ()
    assert refused.fresh_claim is None


def test_manual_sell_requires_known_ready_unused_flatten() -> None:
    module = _authority_module()
    disposition_type, flatten_id_type = _required(
        module,
        "AuthorityDisposition",
        "ManualFlattenId",
    )
    unknown_state = _forge_authority(
        module,
        mode="REDUCING",
        remaining=8,
        reserve=2,
    )
    unknown = _create_effect(
        module,
        unknown_state,
        LONG_EXECUTION,
        "unknown-flatten-sell",
        side=ExecutionSide.SELL,
        quantity=LONG_EXECUTION.position.authorized_residual_sell.value,
        manual_flatten_id=flatten_id_type("unknown-flatten"),
    )
    assert unknown.disposition is disposition_type.REFUSED
    assert unknown.reason is not None
    assert unknown.state == unknown_state
    assert unknown.created_effect_ids == ()

    waiting_state, waiting_execution, waiting_id, _, _ = _begin_waiting_manual_flatten(
        module, "pre-ready-sell"
    )
    premature = _create_effect(
        module,
        waiting_state,
        waiting_execution,
        "pre-ready-sell",
        side=ExecutionSide.SELL,
        quantity=waiting_execution.position.authorized_residual_sell.value,
        manual_flatten_id=waiting_id,
    )
    assert premature.disposition is disposition_type.REFUSED
    assert premature.reason is not None
    assert premature.state == waiting_state
    assert premature.created_effect_ids == ()

    ready_predecessor, ready_execution, ready_id = _manual_advance_predecessor(
        module, "single-final-sell"
    )
    advanced = _authority_apply_twice(
        module,
        ready_predecessor,
        ready_execution,
        _manual_advance(module, ready_id, "single-final-sell"),
    )
    assert advanced.disposition is disposition_type.APPLIED
    first = _create_effect(
        module,
        advanced.state,
        ready_execution,
        "single-final-sell-first",
        side=ExecutionSide.SELL,
        quantity=ready_execution.position.authorized_residual_sell.value,
        manual_flatten_id=ready_id,
    )
    assert first.disposition is disposition_type.APPLIED
    second = _create_effect(
        module,
        first.state,
        ready_execution,
        "single-final-sell-second",
        side=ExecutionSide.SELL,
        quantity=ready_execution.position.authorized_residual_sell.value,
        manual_flatten_id=ready_id,
    )
    assert second.disposition is disposition_type.REFUSED
    assert second.reason is not None
    assert second.state == first.state
    assert second.state.budget == first.state.budget
    assert second.created_effect_ids == ()
    assert second.fresh_claim is None


def test_manual_sell_final_claim_rechecks_a_changed_supervisor_fence() -> None:
    module = _authority_module()
    disposition_type, reason_type, authority_input_type, claim_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "AuthorityInputId",
        "ClaimEffect",
    )
    ready_predecessor, execution, flatten_id = _manual_advance_predecessor(
        module,
        "manual-fence-regate",
    )
    advanced = _authority_apply_twice(
        module,
        ready_predecessor,
        execution,
        _manual_advance(module, flatten_id, "manual-fence-regate"),
    )
    assert advanced.disposition is disposition_type.APPLIED
    created = _create_effect(
        module,
        advanced.state,
        execution,
        "manual-fence-regate-sell",
        side=ExecutionSide.SELL,
        quantity=execution.position.authorized_residual_sell.value,
        manual_flatten_id=flatten_id,
    )
    assert created.disposition is disposition_type.APPLIED
    regated = _forge_authority(
        module,
        predecessor=created.state,
        mode="REDUCING",
        fence="RECONCILIATION_ONLY",
        remaining=created.state.budget.remaining,
        reserve=created.state.budget.safety_reserve,
    )
    claim = claim_type(
        input_id=authority_input_type("manual-fence-regate-claim-input"),
        effect_id=EffectId("manual-fence-regate-sell-effect"),
        claim_occurrence_id=ClaimOccurrenceId("manual-fence-regate-claim"),
    )
    refused = _authority_apply_twice(module, regated, execution, claim)
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.SUPERVISOR_FENCE_BLOCKED
    assert refused.state == regated
    assert refused.state.budget == regated.budget
    assert refused.fresh_claim is None


def test_manual_flatten_late_residual_retry_retires_and_replaces_exactly_once() -> None:
    module = _authority_module()
    (
        disposition_type,
        reason_type,
        authority_input_type,
        claim_type,
        manual_key,
        effect_key,
        flatten_phase_type,
    ) = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
        "AuthorityInputId",
        "ClaimEffect",
        "_manual_key",
        "_effect_key",
        "_FlattenPhase",
    )
    predecessor, execution, flatten_id = _manual_advance_predecessor(
        module,
        "manual-residual-retry",
    )
    ready = _authority_apply_twice(
        module,
        predecessor,
        execution,
        _manual_advance(module, flatten_id, "manual-residual-retry-ready"),
    )
    assert ready.disposition is disposition_type.APPLIED
    stale = _create_effect(
        module,
        ready.state,
        execution,
        "manual-residual-retry-stale",
        side=ExecutionSide.SELL,
        quantity=execution.position.authorized_residual_sell.value,
        manual_flatten_id=flatten_id,
    )
    assert stale.disposition is disposition_type.APPLIED
    stale_effect_id = EffectId("manual-residual-retry-stale-effect")

    unchanged = _authority_apply_twice(
        module,
        stale.state,
        execution,
        _manual_advance(module, flatten_id, "manual-residual-retry-unchanged"),
    )
    assert unchanged.disposition is disposition_type.REFUSED
    assert unchanged.reason is reason_type.MANUAL_FLATTEN_INVALID
    assert unchanged.state == stale.state
    assert unchanged.state.budget == stale.state.budget
    assert unchanged.fresh_claim is None

    drifted_book, drifted_execution = _apply_closed_sell_fill(
        stale.state.venue,
        execution,
        "manual-residual-retry-shrink",
        SHRINK_LEG,
    )
    assert drifted_execution.position.authorized_residual_sell.value == (
        execution.position.authorized_residual_sell.value - 1
    )
    drifted = _forge_venue(stale.state, drifted_book)
    budget_before_retry = drifted.budget
    authorization_before_retry = drifted._effect_authority_by_id.get(
        effect_key(stale_effect_id)
    )
    assert authorization_before_retry is not None
    stale_claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("manual-residual-retry-stale-claim-input"),
        effect_id=stale_effect_id,
        claim_occurrence_id=ClaimOccurrenceId("manual-residual-retry-stale-claim"),
    )
    refused = _authority_apply_twice(
        module,
        drifted,
        drifted_execution,
        stale_claim,
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.RESIDUAL_EXCEEDED
    assert refused.state == drifted
    assert refused.state.budget == budget_before_retry
    assert refused.fresh_claim is None

    retry_command = _manual_advance(
        module,
        flatten_id,
        "manual-residual-retry-refresh",
    )
    retried = _authority_apply_twice(
        module,
        drifted,
        drifted_execution,
        retry_command,
    )
    assert retried.disposition is disposition_type.APPLIED
    assert retried.state.budget == budget_before_retry
    assert (
        retried.state._effect_authority_by_id.get(effect_key(stale_effect_id))
        == authorization_before_retry
    )
    assert retried.created_effect_ids == ()
    assert retried.fresh_claim is None
    retired = retried.state.venue.effect(stale_effect_id)
    assert retired is not None
    assert retired.state is BrokerEffectState.CANCELED_BEFORE_DISPATCH
    assert retired.acceptance_set_state is AcceptanceSetState.CLOSED
    assert retired.claim_occurrence_id is None
    manual = retried.state._manual_by_id.get(manual_key(flatten_id))
    assert manual is not None
    assert manual.phase is flatten_phase_type.READY
    assert manual.sell_effect_id is None

    retry_replay = _authority_apply_twice(
        module,
        retried.state,
        drifted_execution,
        retry_command,
    )
    assert retry_replay.disposition is disposition_type.EXACT_REPLAY
    assert retry_replay.state == retried.state
    assert retry_replay.state.budget == budget_before_retry
    assert retry_replay.fresh_claim is None

    replacement = _create_effect(
        module,
        retried.state,
        drifted_execution,
        "manual-residual-retry-replacement",
        side=ExecutionSide.SELL,
        quantity=drifted_execution.position.authorized_residual_sell.value,
        manual_flatten_id=flatten_id,
    )
    assert replacement.disposition is disposition_type.APPLIED
    assert replacement.state.budget == budget_before_retry
    replacement_effect_id = EffectId("manual-residual-retry-replacement-effect")
    replacement_claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type("manual-residual-retry-replacement-claim-input"),
        effect_id=replacement_effect_id,
        claim_occurrence_id=ClaimOccurrenceId(
            "manual-residual-retry-replacement-claim"
        ),
    )
    claimed = _authority_apply_twice(
        module,
        replacement.state,
        drifted_execution,
        replacement_claim,
    )
    assert claimed.disposition is disposition_type.APPLIED
    assert claimed.fresh_claim is not None
    assert claimed.fresh_claim.effect_id == replacement_effect_id
    assert claimed.fresh_claim.effect_scope.quantity == (
        drifted_execution.position.authorized_residual_sell
    )
    assert claimed.state.budget.remaining == budget_before_retry.remaining - 1

    claim_replay = _authority_apply_twice(
        module,
        claimed.state,
        drifted_execution,
        replacement_claim,
    )
    assert claim_replay.disposition is disposition_type.EXACT_REPLAY
    assert claim_replay.state == claimed.state
    assert claim_replay.fresh_claim is None
    second_claim = claim_type(  # type: ignore[operator]
        input_id=authority_input_type(
            "manual-residual-retry-replacement-second-claim-input"
        ),
        effect_id=replacement_effect_id,
        claim_occurrence_id=ClaimOccurrenceId(
            "manual-residual-retry-replacement-second-claim"
        ),
    )
    conflicted = _authority_apply_twice(
        module,
        claimed.state,
        drifted_execution,
        second_claim,
    )
    assert conflicted.disposition is disposition_type.CONFLICT
    assert conflicted.state == claimed.state
    assert conflicted.state.budget == claimed.state.budget
    assert conflicted.fresh_claim is None


def test_manual_flatten_retry_never_retires_a_claimed_sell() -> None:
    module = _authority_module()
    disposition_type, authority_input_type, claim_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityInputId",
        "ClaimEffect",
    )
    predecessor, execution, flatten_id = _manual_advance_predecessor(
        module,
        "manual-claimed-retry",
    )
    ready = _authority_apply_twice(
        module,
        predecessor,
        execution,
        _manual_advance(module, flatten_id, "manual-claimed-retry-ready"),
    )
    assert ready.disposition is disposition_type.APPLIED
    created = _create_effect(
        module,
        ready.state,
        execution,
        "manual-claimed-retry-sell",
        side=ExecutionSide.SELL,
        quantity=execution.position.authorized_residual_sell.value,
        manual_flatten_id=flatten_id,
    )
    assert created.disposition is disposition_type.APPLIED
    sell_effect_id = EffectId("manual-claimed-retry-sell-effect")
    claimed = _authority_apply_twice(
        module,
        created.state,
        execution,
        claim_type(  # type: ignore[operator]
            input_id=authority_input_type("manual-claimed-retry-claim-input"),
            effect_id=sell_effect_id,
            claim_occurrence_id=ClaimOccurrenceId("manual-claimed-retry-claim"),
        ),
    )
    assert claimed.disposition is disposition_type.APPLIED
    drifted_book, drifted_execution = _apply_closed_sell_fill(
        claimed.state.venue,
        execution,
        "manual-claimed-retry-shrink",
        SHRINK_LEG,
    )
    drifted = _forge_venue(claimed.state, drifted_book)
    effect_before = drifted.venue.effect(sell_effect_id)
    budget_before = drifted.budget

    refused = _authority_apply_twice(
        module,
        drifted,
        drifted_execution,
        _manual_advance(module, flatten_id, "manual-claimed-retry-refresh"),
    )
    assert refused.disposition is disposition_type.REFUSED
    assert refused.state == drifted
    assert refused.state.venue.effect(sell_effect_id) == effect_before
    assert refused.state.budget == budget_before
    assert refused.created_effect_ids == ()
    assert refused.fresh_claim is None


def test_manual_flatten_retry_refuses_unresolved_sibling_uncertainty() -> None:
    module = _authority_module()
    disposition_type, reason_type = _required(
        module,
        "AuthorityDisposition",
        "AuthorityReason",
    )
    predecessor, execution, flatten_id = _manual_advance_predecessor(
        module,
        "manual-sibling-retry",
    )
    ready = _authority_apply_twice(
        module,
        predecessor,
        execution,
        _manual_advance(module, flatten_id, "manual-sibling-retry-ready"),
    )
    assert ready.disposition is disposition_type.APPLIED
    stale = _create_effect(
        module,
        ready.state,
        execution,
        "manual-sibling-retry-sell",
        side=ExecutionSide.SELL,
        quantity=execution.position.authorized_residual_sell.value,
        manual_flatten_id=flatten_id,
    )
    assert stale.disposition is disposition_type.APPLIED
    stale_effect_id = EffectId("manual-sibling-retry-sell-effect")
    drifted_book, drifted_execution = _apply_closed_sell_fill(
        stale.state.venue,
        execution,
        "manual-sibling-retry-shrink",
        SHRINK_LEG,
    )
    uncertain_book, uncertain_execution, _ = _seed_raw_effect(
        drifted_book,
        drifted_execution,
        "manual-sibling-retry-unknown-buy",
        claim=True,
        leg_key=None,
        side=ExecutionSide.BUY,
    )
    uncertain = _forge_venue(stale.state, uncertain_book)
    stale_before = uncertain.venue.effect(stale_effect_id)

    refused = _authority_apply_twice(
        module,
        uncertain,
        uncertain_execution,
        _manual_advance(module, flatten_id, "manual-sibling-retry-refresh"),
    )

    assert refused.disposition is disposition_type.REFUSED
    assert refused.reason is reason_type.VENUE_UNCERTAIN
    assert refused.state == uncertain
    assert refused.state.venue.effect(stale_effect_id) == stale_before
    assert refused.state.budget == uncertain.budget
    assert refused.created_effect_ids == ()
    assert refused.fresh_claim is None


TestClaimAuthorityMachine = ClaimAuthorityMachine.TestCase
TestClaimAuthorityMachine.settings = settings(
    max_examples=16,
    stateful_step_count=10,
    deadline=None,
)

TestSymbolGateMachine = SymbolGateMachine.TestCase
TestSymbolGateMachine.settings = settings(
    max_examples=18,
    stateful_step_count=12,
    deadline=None,
    suppress_health_check=[HealthCheck.filter_too_much],
)

TestManualFlattenMachine = ManualFlattenMachine.TestCase
TestManualFlattenMachine.settings = settings(
    max_examples=18,
    stateful_step_count=14,
    deadline=None,
)
