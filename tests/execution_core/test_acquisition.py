"""RED controls for WO-0150 R1's narrow, pure E1 acquisition foundation.

E1 deliberately exposes deterministic identity data, opaque read declarations,
empty readers, and a bounded venue-derived read projection.  It does not admit,
register, bind, route, or update acquisition state; those operations remain
exclusive to WO-0151's authenticated E2 composite transition.
"""

from __future__ import annotations

import ast
from copy import copy
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from fractions import Fraction
from hashlib import sha256
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import app.execution_core as kernel
import app.execution_core.acquisition as acquisition
import app.execution_core.venue as venue
from app.execution_core.fills import (
    BrokerFillFact,
    BrokerTradeBustFact,
    BrokerTradeCorrectFact,
    ExecutionScope,
    ExecutionSide,
    PositionScope,
)
from app.execution_core.identity import (
    AccountId,
    AcquisitionMandateId,
    AcquisitionGenerationId,
    ApplicationGenerationId,
    BrokerId,
    ClosureId,
    EmergencyRecoveryCompatibilityId,
    EffectId,
    EnvironmentId,
    EvidenceReference,
    ExecutionFactKey,
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
from app.execution_core.recovery import (
    RecordBrokerFillEvidence,
    RecordBrokerRevisionEvidence,
)
from app.execution_core.venue import (
    BrokerEffectState,
    DiscoverVenueLeg,
    ObserveVenueStatus,
    RecordTransportOutcome,
    VenueAcquisitionCorrelation,
    VenueAttemptState,
    VenueRecoveryBook,
)
from tests.execution_core import test_authority as authority_fixtures
from tests.execution_core import test_protection as protection_fixtures
from tests.execution_core import test_venue_recovery as recovery_fixtures


_APP = ApplicationGenerationId("reset-app-0")
_BROKER = BrokerId("broker")
_ENVIRONMENT = EnvironmentId("paper")
_ACCOUNT = AccountId("acct-1")
_SCOPE = PositionScope(
    broker=_BROKER,
    environment=_ENVIRONMENT,
    account=_ACCOUNT,
    symbol_id=SymbolId("AAPL"),
)


def _commitment(label: str) -> bytes:
    return sha256(label.encode("ascii")).digest()


def _different_retained_value(value: object) -> object:
    """Return one deterministic, single-leaf forgery for a retained value."""

    value_type = type(value)
    if value is None:
        return object()
    if value_type is bool:
        return not value
    if value_type is int:
        return value + 1
    if value_type is str:
        return f"{value}-forged"
    if value_type is bytes:
        if not value:
            return b"forged"
        return bytes([value[0] ^ 1]) + value[1:]
    if value_type is Fraction:
        return value + 1
    members = getattr(value_type, "__members__", None)
    if members is not None:
        alternate = next(
            (member for member in members.values() if member is not value), None
        )
        return object() if alternate is None else alternate
    if value_type is tuple:
        if not value:
            return (object(),)
        changed = list(value)
        changed[0] = _different_retained_value(changed[0])
        return tuple(changed)
    if value_type is frozenset:
        if not value:
            return frozenset({object()})
        changed = list(value)
        changed[0] = _different_retained_value(changed[0])
        return frozenset(changed)
    if value_type.__name__ == "_PersistentKeyMap":
        return value_type.empty()
    if is_dataclass(value) and not isinstance(value, type):
        retained = fields(value)
        if retained:
            forged = copy(value)
            first = retained[0]
            object.__setattr__(
                forged,
                first.name,
                _different_retained_value(object.__getattribute__(value, first.name)),
            )
            return forged
    return object()


def _assert_every_retained_field_is_authenticated(
    value: object,
    checker: object,
    *,
    type_only_fields: frozenset[str] = frozenset(),
) -> None:
    """Prove every retained field participates in one owner authenticity gate."""

    assert callable(checker)
    assert checker(value)
    retained = fields(value)
    assert retained
    for item in retained:
        changed = _different_retained_value(object.__getattribute__(value, item.name))
        replacements = (
            (object(),)
            if item.name in type_only_fields
            else (changed,)
            if type(changed) is object
            else (changed, object())
        )
        for replacement in replacements:
            forged = copy(value)
            object.__setattr__(forged, item.name, replacement)
            try:
                accepted = checker(forged)
            except (AttributeError, TypeError, ValueError):
                accepted = False
            assert not accepted, (type(value).__name__, item.name)


def _request(label: str) -> RequestOccurrenceId:
    return RequestOccurrenceId(f"request-{label}")


def _effect(label: str) -> EffectId:
    return EffectId(f"effect-{label}")


def _leg(label: str) -> VenueLegKey:
    return VenueLegKey(
        broker=_BROKER,
        environment=_ENVIRONMENT,
        account=_ACCOUNT,
        order_id=OrderId(f"order-{label}"),
    )


def _root(label: str) -> RootFillKey:
    return RootFillKey(
        broker=_BROKER,
        environment=_ENVIRONMENT,
        account=_ACCOUNT,
        root_fill_id=RootFillId(f"root-{label}"),
    )


def _fact(label: str) -> ExecutionFactKey:
    return ExecutionFactKey(
        broker=_BROKER,
        environment=_ENVIRONMENT,
        account=_ACCOUNT,
        source_event_id=SourceEventId(f"fact-{label}"),
    )


def _generation_id() -> AcquisitionGenerationId:
    return acquisition._derive_acquisition_generation_id(
        application_generation_id=_APP,
        position_scope=_SCOPE,
        successor_ordinal=0,
        dual_mandate_binding_commitment=_commitment("dual-a"),
        predecessor_or_genesis_head_commitment=(
            acquisition._acquisition_controller_genesis_head(_APP, _SCOPE)
        ),
        emergency_recovery_compatibility_commitment=_commitment("compatibility"),
    )


def _approved_acquisition_mandate(
    *,
    position_scope: PositionScope,
    session_id: object,
    protection_mandate: object,
    label: str = "r8",
) -> object:
    """Build one exact operator-approved dual mandate for E2 controls only."""

    acquisition_mandate_id = AcquisitionMandateId(f"wo0151-{label}-acquisition-mandate")
    configuration_version = f"wo0151-{label}-acquisition-v1"
    binding = acquisition._mint_dual_mandate_binding(
        acquisition_mandate_id=acquisition_mandate_id,
        position_scope=position_scope,
        session_id=session_id,
        configuration_version=configuration_version,
        maximum_quantity=authority_fixtures.Quantity(5),
        maximum_notional=Fraction(1_000),
        maximum_entry_price=authority_fixtures.PRICE,
        allowed_order_types=(acquisition.AcquisitionOrderType.LIMIT,),
        expiry=1_000,
        deadline=900,
        fixed_child_cap=authority_fixtures.Quantity(1),
        certified_participation_cap=Fraction(1, 2),
        cancel_reprice_budget=2,
        protection_mandate=protection_mandate,
    )
    return acquisition.AcquisitionMandate(
        acquisition_mandate_id=acquisition_mandate_id,
        position_scope=position_scope,
        session_id=session_id,
        configuration_version=configuration_version,
        maximum_quantity=authority_fixtures.Quantity(5),
        maximum_notional=Fraction(1_000),
        maximum_entry_price=authority_fixtures.PRICE,
        allowed_order_types=(acquisition.AcquisitionOrderType.LIMIT,),
        expiry=1_000,
        deadline=900,
        fixed_child_cap=authority_fixtures.Quantity(1),
        certified_participation_cap=Fraction(1, 2),
        cancel_reprice_budget=2,
        protection_mandate=protection_mandate,
        binding=binding,
    )


def _r8_initialized_controller():
    """Return one exact initialized-unused controller and its authority pair."""

    authority = authority_fixtures._authority_module()
    protection = protection_fixtures._protection_module()
    source_authority = authority_fixtures._forge_positive_predecessor(authority)
    source_execution = authority_fixtures.EXECUTION
    scope = source_execution.position.scope
    bootstrap_refresh = authority.refresh_acquisition_context(
        source_authority,
        source_execution,
        scope,
    )
    assert bootstrap_refresh.authority is not None
    assert bootstrap_refresh.execution is not None
    bootstrap = bootstrap_refresh.authority.venue.project_acquisition_bootstrap(
        bootstrap_refresh.execution,
        scope,
    )
    admission = authority.project_acquisition_admission(
        bootstrap_refresh.authority,
        bootstrap_refresh.execution,
        scope,
    )
    protection_mandate = protection_fixtures._mandate(
        protection,
        position_scope=scope,
        session_id=bootstrap_refresh.authority.session_id,
    )
    mandate = _approved_acquisition_mandate(
        position_scope=scope,
        session_id=bootstrap_refresh.authority.session_id,
        protection_mandate=protection_mandate,
    )
    initialized = acquisition.initialize_acquisition_controller(
        authority_fixtures.GENERATION,
        mandate,
        bootstrap,
        admission,
        bootstrap_refresh,
        None,
    )
    return authority, scope, initialized


def _successor_mandate(
    prior: object,
    label: str,
    *,
    stream_generation: kernel.MarketStreamGenerationId | None = None,
) -> object:
    """Mint one distinct mandate/stream with the retained recovery contract."""

    protection = protection_fixtures._protection_module()
    protection_mandate = protection_fixtures._mandate(
        protection,
        mandate_id=kernel.MandateId(f"wo0151-{label}-protection-mandate"),
        position_scope=prior.position_scope,
        session_id=prior.session_id,
        stream_generation=(
            kernel.MarketStreamGenerationId(
                sha256(f"wo0151-{label}-stream".encode("ascii")).hexdigest()
            )
            if stream_generation is None
            else stream_generation
        ),
        configuration_version=f"wo0151-{label}-protection-v1",
        emergency_recovery_compatibility=(
            prior.protection_mandate.emergency_recovery_compatibility
        ),
    )
    return _approved_acquisition_mandate(
        position_scope=prior.position_scope,
        session_id=prior.session_id,
        protection_mandate=protection_mandate,
        label=label,
    )


def _r8_created_first_effect():
    """Return one exact initialized controller with its first BUY requested."""

    authority, scope, initialized = _r8_initialized_controller()
    refresh = authority.refresh_acquisition_context(
        initialized.authority,
        initialized.execution,
        scope,
    )
    created = acquisition.create_acquisition_effect(
        initialized.state,
        refresh,
        None,
        acquisition.AcquisitionEffectTerms(
            quantity=authority_fixtures.Quantity(1),
            limit_price=authority_fixtures.PRICE,
            order_type=acquisition.AcquisitionOrderType.LIMIT,
            evaluation_time=1,
        ),
        authority.AuthorityInputId("wo0151-r8-specialized-claim-create"),
    )
    assert created.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert created.created_effect_id is not None
    return authority, scope, created


def _r8_claimed_first_effect():
    """Return the exact first specialized BUY after its sole final claim."""

    authority, scope, created = _r8_created_first_effect()
    assert created.created_effect_id is not None
    refresh = authority.refresh_acquisition_context(
        created.authority,
        created.execution,
        scope,
    )
    claimed = acquisition.claim_acquisition_effect(
        created.state,
        refresh,
        None,
        created.created_effect_id,
        authority.ClaimOccurrenceId("wo0151-r8-first-fill-claim-occurrence"),
        authority.AuthorityInputId("wo0151-r8-first-fill-claim"),
    )
    assert claimed.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert claimed.fresh_claim is not None
    return authority, scope, claimed


def _r8_current_generation_fill_transition(
    *,
    acknowledged: bool = False,
    prefill_needs_review: bool = True,
    fill_quantity: int = 1,
):
    """Produce one canonical first-BUY fill through normal venue lifecycle facts."""

    authority, scope, claimed = _r8_claimed_first_effect()
    effect_id = claimed.fresh_claim.effect_id
    leg_key = VenueLegKey(
        broker=scope.broker,
        environment=scope.environment,
        account=scope.account,
        order_id=OrderId("wo0151-r8-current-generation-fill-order"),
    )
    book = claimed.venue
    execution = claimed.execution
    lifecycle = [
        RecordTransportOutcome(
            input_id=VenueInputId("wo0151-r8-first-fill-outcome-unknown"),
            effect_id=effect_id,
            state=(
                BrokerEffectState.ACKNOWLEDGED
                if acknowledged
                else BrokerEffectState.OUTCOME_UNKNOWN
            ),
        ),
        DiscoverVenueLeg(
            input_id=VenueInputId("wo0151-r8-first-fill-discover"),
            effect_id=effect_id,
            leg_key=leg_key,
            observation_id=VenueObservationId(
                "wo0151-r8-first-fill-discover-observation"
            ),
        ),
    ]
    if prefill_needs_review:
        lifecycle.append(
            ObserveVenueStatus(
                input_id=VenueInputId("wo0151-r8-first-fill-needs-review"),
                leg_key=leg_key,
                status=VenueAttemptState.NEEDS_REVIEW,
                observation_id=VenueObservationId(
                    "wo0151-r8-first-fill-review-observation"
                ),
                cumulative_quantity=authority_fixtures.Quantity(0),
            )
        )
    if not acknowledged and prefill_needs_review:
        lifecycle.append(
            RecordTransportOutcome(
                input_id=VenueInputId("wo0151-r8-first-fill-needs-review-outcome"),
                effect_id=effect_id,
                state=BrokerEffectState.NEEDS_REVIEW,
            )
        )
    for item in lifecycle:
        next_transition = recovery_fixtures.apply_venue_recovery_input(
            book,
            execution,
            item,
        )
        assert next_transition.disposition is venue.VenueRecoveryDisposition.APPLIED, (
            type(item).__name__
        )
        assert next_transition.quantity_delta == 0
        book = next_transition.book
        execution = next_transition.execution
    fact = replace(
        recovery_fixtures._broker_fill(
            "wo0151-r8-current-generation-fill-source",
            "wo0151-r8-current-generation-fill-root",
            leg_key=leg_key,
            quantity=fill_quantity,
        ),
        key=ExecutionFactKey(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            source_event_id=SourceEventId("wo0151-r8-current-generation-fill-source"),
        ),
        scope=ExecutionScope(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            order_id=leg_key.order_id,
            symbol_id=scope.symbol_id,
            side=ExecutionSide.BUY,
        ),
    )
    filled = recovery_fixtures.apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("wo0151-r8-current-generation-fill-input"),
            effect_id=effect_id,
            leg_key=leg_key,
            prior_cumulative_quantity=authority_fixtures.Quantity(0),
            resulting_cumulative_quantity=authority_fixtures.Quantity(fill_quantity),
            fact=fact,
            evidence_digest=bytes([0xA5]) * 32,
        ),
    )
    assert filled.disposition is venue.VenueRecoveryDisposition.APPLIED
    assert filled.quantity_delta == fill_quantity
    projection = filled.book.project_acquisition_fact(filled)
    assert projection.matches_fact_transition(filled, scope)
    assert projection.fact_relation() is not None
    return authority, scope, claimed, filled


def _r10_semantic_rebase_fixture():
    """Return one current controller and a protection-owned semantic rebase."""

    authority, scope, claimed, filled = _r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    applied = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert applied.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert applied.protection is not None

    protection = protection_fixtures._protection_module()
    refresh = authority.refresh_acquisition_context(
        applied.authority,
        applied.execution,
        scope,
    )
    assert refresh.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    assert refresh.venue_context is not None

    predecessor_context = protection.project_acquisition_protection_context(
        applied.protection,
        applied.venue,
        applied.execution,
        refresh.venue_context,
    )
    assert predecessor_context is not None
    protection_venue = protection.project_protection_venue(
        filled,
        applied.state._mandate.protection_mandate,
    )
    mandate = applied.state._mandate.protection_mandate
    occurrence = protection_fixtures._occurrence(
        protection,
        "wo0151-r10-controller-semantic-rebase",
        bid=101,
        ask=102,
        sequence=0,
        source_time=0,
        evaluation_time=0,
        market_epoch=0,
        source_id=mandate.evidence_policy.source_id,
        stream_generation=mandate.evidence_policy.stream_generation,
        position_scope=scope,
        session_id=mandate.session_id,
    )
    protection_transition = protection_fixtures._reduce_market(
        protection,
        applied.protection,
        protection_venue,
        occurrence,
    )
    assert protection_transition.disposition is protection.ProtectionDisposition.APPLIED
    current_context = protection.project_acquisition_protection_context(
        protection_transition.state,
        applied.venue,
        applied.execution,
        refresh.venue_context,
    )
    assert current_context is not None
    assert (
        current_context.scope_protection_commitment
        != predecessor_context.scope_protection_commitment
    )
    projection = protection.project_acquisition_protection_rebase(
        applied.protection,
        protection_transition,
        predecessor_context,
        current_context,
    )
    assert projection is not None
    assert projection.kind is protection.AcquisitionProtectionRebaseKind.SEMANTIC_REBASE
    return authority, scope, applied, refresh, predecessor_context, projection


def _r11_waiting_preemption_fixture():
    """Produce one current controller whose acknowledged BUY must be cancelled."""

    authority, scope, claimed, filled = _r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    current = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert current.protection is not None
    protection = protection_fixtures._protection_module()
    mandate = current.state._mandate.protection_mandate
    protection_venue = protection.project_protection_venue(filled, mandate)

    for sequence, bid in enumerate((120, 110, 109), start=1):
        refresh = authority.refresh_acquisition_context(
            current.authority,
            current.execution,
            scope,
        )
        assert (
            refresh.disposition
            is authority.AcquisitionContextRefreshDisposition.CURRENT
        )
        assert refresh.venue_context is not None
        predecessor_context = protection.project_acquisition_protection_context(
            current.protection,
            current.venue,
            current.execution,
            refresh.venue_context,
        )
        assert predecessor_context is not None
        reduced = protection_fixtures._reduce_market(
            protection,
            current.protection,
            protection_venue,
            protection_fixtures._occurrence(
                protection,
                f"wo0151-r11-preempt-market-{sequence}",
                bid=bid,
                ask=bid + 1,
                sequence=sequence,
                source_time=94 + sequence * 6,
                evaluation_time=98 + sequence * 6,
                market_epoch=0,
                source_id=mandate.evidence_policy.source_id,
                stream_generation=mandate.evidence_policy.stream_generation,
                position_scope=scope,
                session_id=mandate.session_id,
            ),
        )
        assert reduced.disposition is protection.ProtectionDisposition.APPLIED
        current_context = protection.project_acquisition_protection_context(
            reduced.state,
            current.venue,
            current.execution,
            refresh.venue_context,
        )
        assert current_context is not None
        projection = protection.project_acquisition_protection_rebase(
            current.protection,
            reduced,
            predecessor_context,
            current_context,
        )
        assert projection is not None
        current = acquisition.rebase_acquisition_protection(
            current.state,
            refresh,
            projection,
        )
        assert (
            current.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
        )
        assert current.protection is reduced.state

    assert current.protection is not None
    assert current.protection.policy is protection.ProtectionPolicy.EXIT_NORMAL
    assert current.protection.waiting_buy_resolution
    relation = filled.book.project_acquisition_fact(filled).fact_relation()
    assert relation is not None
    return authority, scope, current, relation


def _r11_protection_exit_fixture():
    """Produce one current goal-bearing transition after exact BUY closure."""

    authority, scope, current, relation = _r11_waiting_preemption_fixture()
    protection = protection_fixtures._protection_module()
    mandate = current.state._mandate.protection_mandate
    carrier = SimpleNamespace(book=current.venue, execution=current.execution)
    _, terminal = protection_fixtures._terminal_fixture(
        carrier,
        effect_id=relation.effect_id,
        leg_key=relation.leg_key,
        label="wo0151-r11-r1-exit",
        cumulative_quantity=1,
    )
    _, closed = protection_fixtures._close_parent_fixture(
        terminal,
        effect_id=relation.effect_id,
        label="wo0151-r11-r1-exit",
    )
    assert current.protection is not None
    terminal_only = protection.reduce_position_protection(
        current.protection,
        protection.project_protection_venue(terminal, mandate),
    )
    assert terminal_only.disposition is protection.ProtectionDisposition.APPLIED
    assert terminal_only.goal is None
    terminal_venue_context = terminal.book.project_acquisition_context(
        terminal.execution,
        scope,
    )
    predecessor_context = protection.project_acquisition_protection_context(
        terminal_only.state,
        terminal.book,
        terminal.execution,
        terminal_venue_context,
    )
    assert predecessor_context is not None
    released = protection.reduce_position_protection(
        terminal_only.state,
        protection.project_protection_venue(closed, mandate),
    )
    assert released.disposition is protection.ProtectionDisposition.APPLIED
    assert released.goal is not None
    next_authority = copy(current.authority)
    object.__setattr__(next_authority, "venue", closed.book)
    refresh = authority.refresh_acquisition_context(
        next_authority,
        closed.execution,
        scope,
    )
    assert refresh.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    assert refresh.venue_context is not None
    current_context = protection.project_acquisition_protection_context(
        released.state,
        closed.book,
        closed.execution,
        refresh.venue_context,
    )
    assert current_context is not None
    assert not released.state.waiting_buy_resolution
    assert current_context.source_protection_commitment == released.state.commitment
    return authority, scope, current, released, next_authority, refresh


def test_wo0151_r10_semantic_rebase_advances_one_current_controller_head() -> None:
    """One sealed semantic change re-registers currentness without other effects."""

    (
        authority,
        scope,
        applied,
        refresh,
        predecessor_context,
        projection,
    ) = _r10_semantic_rebase_fixture()

    assert applied.state.protection_commitment is not None
    assert projection.matches_predecessor_scope_protection_commitment(
        applied.state.protection_commitment
    )
    result = acquisition.rebase_acquisition_protection(
        applied.state,
        refresh,
        projection,
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.protection is projection.resulting_state
    assert result.execution is applied.execution
    assert result.venue is applied.venue
    assert result.created_effect_id is None
    assert result.fresh_claim is None

    assert result.state.registry is applied.state.registry
    assert result.state.lineage is applied.state.lineage
    assert result.state.protection_commitment != applied.state.protection_commitment
    assert (
        acquisition.project_acquisition_controller(result.state).controller_head
        != acquisition.project_acquisition_controller(applied.state).controller_head
    )
    receipt = result._registration_receipt
    assert receipt is not None
    assert receipt.operation is authority.AcquisitionAuthorityOperation.REGISTER
    assert receipt.predecessor_controller_head == (
        acquisition.project_acquisition_controller(applied.state).controller_head
    )
    assert (
        receipt.controller_head
        == acquisition.project_acquisition_controller(result.state).controller_head
    )
    assert receipt.predecessor_scope_execution_commitment == (
        applied.state.scope_execution_commitment
    )
    assert receipt.scope_execution_commitment == result.state.scope_execution_commitment
    assert receipt.predecessor_venue_commitment == applied.state.venue_commitment
    assert receipt.venue_commitment == result.state.venue_commitment
    assert receipt.ordered_venue_transition_commitments == ()

    current = authority.refresh_acquisition_context(
        result.authority,
        result.execution,
        scope,
    )
    assert current.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    assert current.venue_context is not None
    context = (
        protection_fixtures._protection_module().project_acquisition_protection_context(
            result.protection,
            result.venue,
            result.execution,
            current.venue_context,
        )
    )
    assert context is not None
    assert context.scope_protection_commitment == result.state.protection_commitment
    assert context.scope_protection_commitment != (
        predecessor_context.scope_protection_commitment
    )


def test_wo0151_r10_exact_immutable_rebase_replay_cannot_register_twice() -> None:
    """R10 replay is the same proof relation, never a second currentness source."""

    authority, scope, applied, refresh, _, projection = _r10_semantic_rebase_fixture()
    first = acquisition.rebase_acquisition_protection(
        applied.state,
        refresh,
        projection,
    )
    replay_projection = copy(projection)
    assert replay_projection.matches_predecessor_scope_protection_commitment(
        applied.state.protection_commitment
    )
    replay_refresh = authority.refresh_acquisition_context(
        first.authority,
        first.execution,
        scope,
    )
    assert (
        replay_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.CURRENT
    )

    replay = acquisition.rebase_acquisition_protection(
        first.state,
        replay_refresh,
        replay_projection,
    )

    assert replay.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert replay.state is first.state
    assert replay.authority is first.authority
    assert replay.protection is replay_projection.resulting_state
    assert replay.created_effect_id is None
    assert replay.fresh_claim is None
    assert replay._registration_receipt is None


def test_wo0151_r11_semantic_rebase_requires_the_protection_owner_matcher() -> None:
    """Authority-shaped fields cannot replace the protection owner's seal proof."""

    _, _, applied, refresh, _, projection = _r10_semantic_rebase_fixture()
    forged = copy(projection)
    object.__setattr__(forged, "predecessor_context_commitment", b"\x91" * 32)
    assert not forged.matches_predecessor_scope_protection_commitment(
        applied.state.protection_commitment
    )

    refused = acquisition.rebase_acquisition_protection(
        applied.state,
        refresh,
        forged,
    )

    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.state is applied.state
    assert refused.authority is applied.authority
    assert refused._registration_receipt is None


def test_wo0151_r10_semantic_rebase_refuses_a_newer_authority_context() -> None:
    """A valid projection cannot cross a changed authority-currentness fence."""

    authority, scope, applied, _, _, projection = _r10_semantic_rebase_fixture()
    reducing = copy(applied.authority)
    object.__setattr__(reducing, "mode", authority.TradingMode.REDUCING)
    flattened = authority_fixtures._authority_apply_twice(
        authority,
        reducing,
        applied.execution,
        authority.BeginManualFlatten(
            input_id=authority.AuthorityInputId(
                "wo0151-r10-rebase-stale-authority-input"
            ),
            flatten_id=authority.ManualFlattenId(
                "wo0151-r10-rebase-stale-authority-flatten"
            ),
            session_id=reducing.session_id,
            symbol_id=scope.symbol_id,
            actor=authority_fixtures.ActorId("wo0151-r10-rebase-operator"),
            reason="prove a changed authority context refuses semantic rebase",
            evidence_reference=authority_fixtures.EvidenceReference(
                "wo0151-r10-rebase-evidence"
            ),
            emergency_grant_id=None,
        ),
    )
    assert flattened.disposition is authority.AuthorityDisposition.APPLIED
    fresh = authority.refresh_acquisition_context(
        flattened.state,
        applied.execution,
        scope,
    )
    assert fresh.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    assert fresh.authority_context is not None
    assert (
        fresh.authority_context.authority_commitment
        != applied.state.authority_context_commitment
    )

    refused = acquisition.rebase_acquisition_protection(
        applied.state,
        fresh,
        projection,
    )

    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.state is applied.state
    assert refused.authority is flattened.state
    assert refused.protection is projection.resulting_state
    assert refused.created_effect_id is None
    assert refused.fresh_claim is None
    assert refused._registration_receipt is None


def test_wo0151_r10_preminted_rebase_registration_refuses_newer_authority() -> None:
    """A sealed pre-mint cannot bypass a subsequent authority transition."""

    authority, scope, applied, refresh, _, projection = _r10_semantic_rebase_fixture()
    assert refresh.authority is applied.authority
    assert refresh.execution is applied.execution
    assert refresh.venue_context is not None
    protection_context = (
        protection_fixtures._protection_module().project_acquisition_protection_context(
            projection.resulting_state,
            refresh.authority.venue,
            refresh.execution,
            refresh.venue_context,
        )
    )
    assert protection_context is not None
    assert protection_context.scope_protection_commitment is not None
    mandate = applied.state._mandate
    controller = applied.state._controller
    registration = authority._mint_acquisition_currentness_registration(
        application_generation_id=applied.state.application_generation_id,
        position_scope=applied.state.position_scope,
        session_id=mandate.session_id,
        generation_id=controller.live_generation_id,
        acquisition_mandate_id=mandate.acquisition_mandate_id,
        protection_mandate_id=mandate.protection_mandate.mandate_id,
        binding_commitment=mandate.binding.commitment,
        emergency_recovery_compatibility_commitment=(
            mandate.protection_mandate.emergency_recovery_compatibility.commitment
        ),
        controller_head=acquisition._controller_head_after_protection_rebase(
            applied.state,
            projection,
        ),
        successor_ordinal=controller.successor_ordinal,
        protection_commitment=protection_context.scope_protection_commitment,
        authority=applied.authority,
        refresh=refresh,
        predecessor_authority_context_commitment=(
            applied.state.authority_context_commitment
        ),
        protection_rebase=projection,
    )
    command = authority.RegisterAcquisitionCurrentness.from_registration(registration)
    _assert_every_retained_field_is_authenticated(
        registration,
        authority._protection_rebase_currentness_registration_is_authentic,
        type_only_fields=frozenset({"_projection"}),
    )
    _assert_every_retained_field_is_authenticated(
        command,
        authority._register_protection_rebase_currentness_command_is_authentic,
        type_only_fields=frozenset({"registration"}),
    )

    reducing = copy(applied.authority)
    object.__setattr__(reducing, "mode", authority.TradingMode.REDUCING)
    flattened = authority_fixtures._authority_apply_twice(
        authority,
        reducing,
        applied.execution,
        authority.BeginManualFlatten(
            input_id=authority.AuthorityInputId(
                "wo0151-r10-premint-stale-authority-input"
            ),
            flatten_id=authority.ManualFlattenId(
                "wo0151-r10-premint-stale-authority-flatten"
            ),
            session_id=reducing.session_id,
            symbol_id=scope.symbol_id,
            actor=authority_fixtures.ActorId("wo0151-r10-premint-operator"),
            reason="prove a pre-minted rebase cannot cross a newer authority",
            evidence_reference=authority_fixtures.EvidenceReference(
                "wo0151-r10-premint-evidence"
            ),
            emergency_grant_id=None,
        ),
    )
    assert flattened.disposition is authority.AuthorityDisposition.APPLIED
    before = authority_fixtures._iterative_value_fingerprint(
        flattened.state,
        applied.execution,
        command,
    )

    refused = authority.apply_execution_authority_input(
        flattened.state,
        applied.execution,
        command,
    )

    assert refused.disposition is authority.AuthorityDisposition.REFUSED
    assert refused.state is flattened.state
    assert refused.acquisition_receipt is None
    assert refused.acquisition_claim_receipt is None
    assert refused.created_effect_ids == ()
    assert refused.fresh_claim is None
    assert refused.venue_transitions == ()
    assert before == authority_fixtures._iterative_value_fingerprint(
        flattened.state,
        applied.execution,
        command,
    )


def test_wo0151_r8_unbound_bootstrap_refuses_protection_rebase() -> None:
    """A real bootstrap refresh cannot be repurposed as rebase authority."""

    authority, _, applied, _, _, projection = _r10_semantic_rebase_fixture()
    bootstrap_authority = authority_fixtures._forge_positive_predecessor(authority)
    bootstrap_execution = authority_fixtures.EXECUTION
    bootstrap = authority.refresh_acquisition_context(
        bootstrap_authority,
        bootstrap_execution,
        bootstrap_execution.position.scope,
    )
    assert (
        bootstrap.disposition
        is authority.AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP
    )

    refused = acquisition.rebase_acquisition_protection(
        applied.state,
        bootstrap,
        projection,
    )

    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.state is applied.state
    assert bootstrap.authority is not None
    assert bootstrap.execution is not None
    assert refused.authority is bootstrap.authority
    assert refused.execution is bootstrap.execution
    assert refused.protection is projection.resulting_state
    assert refused.created_effect_id is None
    assert refused.fresh_claim is None
    assert refused._registration_receipt is None


def _r11_neutral_reprojection_fixture():
    """Return one target controller plus one exact sibling-driven refresh."""

    authority, scope, applied, _, _, semantic_projection = (
        _r10_semantic_rebase_fixture()
    )
    other_scope = PositionScope(
        broker=scope.broker,
        environment=scope.environment,
        account=scope.account,
        symbol_id=SymbolId("MSFT"),
    )
    other = authority.refresh_acquisition_context(
        applied.authority,
        applied.execution,
        other_scope,
    )
    assert (
        other.disposition
        is authority.AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP
    )
    assert other.authority is not None
    assert other.execution is not None
    other_bootstrap = other.authority.venue.project_acquisition_bootstrap(
        other.execution,
        other_scope,
    )
    other_admission = authority.project_acquisition_admission(
        other.authority,
        other.execution,
        other_scope,
    )
    protection = protection_fixtures._protection_module()
    other_protection_mandate = protection_fixtures._mandate(
        protection,
        position_scope=other_scope,
        session_id=other.authority.session_id,
    )
    other_mandate = _approved_acquisition_mandate(
        position_scope=other_scope,
        session_id=other.authority.session_id,
        protection_mandate=other_protection_mandate,
    )
    initialized_other = acquisition.initialize_acquisition_controller(
        authority_fixtures.GENERATION,
        other_mandate,
        other_bootstrap,
        other_admission,
        other,
        None,
    )
    current_other = authority.refresh_acquisition_context(
        initialized_other.authority,
        initialized_other.execution,
        other_scope,
    )
    created_other = acquisition.create_acquisition_effect(
        initialized_other.state,
        current_other,
        None,
        acquisition.AcquisitionEffectTerms(
            quantity=authority_fixtures.Quantity(1),
            limit_price=authority_fixtures.PRICE,
            order_type=acquisition.AcquisitionOrderType.LIMIT,
            evaluation_time=2,
        ),
        authority.AuthorityInputId("wo0151-r11-neutral-other-create"),
    )
    assert created_other.created_effect_id is not None
    claim_id = authority.ClaimOccurrenceId("wo0151-r11-neutral-other-claim")
    claimed_other = acquisition.claim_acquisition_effect(
        created_other.state,
        authority.refresh_acquisition_context(
            created_other.authority,
            created_other.execution,
            other_scope,
        ),
        None,
        created_other.created_effect_id,
        claim_id,
        authority.AuthorityInputId("wo0151-r11-neutral-other-claim-input"),
    )
    leg_key = VenueLegKey(
        broker=scope.broker,
        environment=scope.environment,
        account=scope.account,
        order_id=OrderId("wo0151-r11-neutral-other-symbol-leg"),
    )
    book = claimed_other.venue
    other_execution = claimed_other.execution
    for item in (
        RecordTransportOutcome(
            input_id=VenueInputId("wo0151-r11-neutral-other-ack"),
            effect_id=created_other.created_effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
        DiscoverVenueLeg(
            input_id=VenueInputId("wo0151-r11-neutral-other-discover"),
            effect_id=created_other.created_effect_id,
            leg_key=leg_key,
            observation_id=VenueObservationId("wo0151-r11-neutral-other-discovery"),
        ),
    ):
        advanced = recovery_fixtures.apply_venue_recovery_input(
            book,
            other_execution,
            item,
        )
        assert advanced.disposition is venue.VenueRecoveryDisposition.APPLIED
        book = advanced.book
        other_execution = advanced.execution
    fact = replace(
        recovery_fixtures._broker_fill(
            "wo0151-r11-neutral-other-source",
            "wo0151-r11-neutral-other-root",
            leg_key=leg_key,
            quantity=1,
        ),
        key=ExecutionFactKey(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            source_event_id=SourceEventId("wo0151-r11-neutral-other-source"),
        ),
        scope=ExecutionScope(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            order_id=leg_key.order_id,
            symbol_id=other_scope.symbol_id,
            side=ExecutionSide.BUY,
        ),
    )
    advanced = recovery_fixtures.apply_venue_recovery_input(
        book,
        other_execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("wo0151-r11-neutral-other-fill"),
            effect_id=created_other.created_effect_id,
            leg_key=leg_key,
            prior_cumulative_quantity=authority_fixtures.Quantity(0),
            resulting_cumulative_quantity=authority_fixtures.Quantity(1),
            fact=fact,
            evidence_digest=b"\xb7" * 32,
        ),
    )
    assert advanced.disposition is venue.VenueRecoveryDisposition.APPLIED
    advanced_book = advanced.book
    advanced_other = advanced.execution
    predecessor = authority_fixtures._forge_venue_predecessor(
        claimed_other.authority,
        advanced_book,
    )
    refresh = authority.refresh_acquisition_context(
        predecessor,
        advanced_other,
        scope,
    )
    assert (
        refresh.disposition is authority.AcquisitionContextRefreshDisposition.REFRESHED
    )
    assert refresh.predecessor_execution == applied.execution
    assert refresh.execution is not None
    assert len(refresh.venue_transitions) == 1
    assert refresh.venue_transitions[0].quantity_delta == 0
    return authority, scope, applied, refresh, semantic_projection


def test_wo0151_r11_neutral_reprojection_transports_only_fresh_raw_state() -> None:
    """Sibling catch-up changes raw transport state and no controller authority."""

    authority, scope, applied, refresh, semantic_projection = (
        _r11_neutral_reprojection_fixture()
    )
    assert applied.protection is not None
    before = acquisition.project_acquisition_controller(applied.state)

    result = acquisition.rebase_acquisition_protection(
        applied.state,
        refresh,
        applied.protection,
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.state is applied.state
    assert result.state.registry is applied.state.registry
    assert result.state.lineage is applied.state.lineage
    assert result.protection is not applied.protection
    assert result.protection.commitment != applied.protection.commitment
    assert result.authority is refresh.authority
    assert result.execution is refresh.execution
    assert result.venue is refresh.authority.venue
    assert result.created_effect_id is None
    assert result.fresh_claim is None
    assert result._registration_receipt is None
    assert acquisition.project_acquisition_controller(result.state) == before

    current = authority.refresh_acquisition_context(
        result.authority,
        result.execution,
        scope,
    )
    assert current.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    replay = acquisition.rebase_acquisition_protection(
        result.state,
        current,
        result.protection,
    )
    assert replay.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert replay.state is result.state
    assert replay.protection is result.protection
    assert replay._registration_receipt is None

    wrong_branch = acquisition.rebase_acquisition_protection(
        applied.state,
        refresh,
        semantic_projection,
    )
    assert (
        wrong_branch.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    )
    with pytest.raises(TypeError, match="source must be"):
        acquisition.rebase_acquisition_protection(applied.state, refresh, None)


def test_wo0151_r8_unbound_bootstrap_initializes_one_controller_composite() -> None:
    """Only the authenticated R8 handoff may atomically install first currentness."""

    authority = authority_fixtures._authority_module()
    protection = protection_fixtures._protection_module()
    source_authority = authority_fixtures._forge_positive_predecessor(authority)
    source_execution = authority_fixtures.EXECUTION
    scope = source_execution.position.scope
    before = authority_fixtures._iterative_value_fingerprint(
        source_authority,
        source_execution,
    )

    refresh = authority.refresh_acquisition_context(
        source_authority,
        source_execution,
        scope,
    )
    assert (
        refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP
    )
    assert refresh.authority is not None
    assert refresh.execution is not None
    assert refresh.matches_current(
        refresh.authority,
        authority_fixtures.GENERATION,
        scope,
    )
    bootstrap = refresh.authority.venue.project_acquisition_bootstrap(
        refresh.execution,
        scope,
    )
    admission = authority.project_acquisition_admission(
        refresh.authority,
        refresh.execution,
        scope,
    )
    protection_mandate = protection_fixtures._mandate(
        protection,
        position_scope=scope,
        session_id=refresh.authority.session_id,
    )
    mandate = _approved_acquisition_mandate(
        position_scope=scope,
        session_id=refresh.authority.session_id,
        protection_mandate=protection_mandate,
    )

    result = acquisition.initialize_acquisition_controller(
        authority_fixtures.GENERATION,
        mandate,
        bootstrap,
        admission,
        refresh,
        None,
    )

    head = acquisition._acquisition_controller_genesis_head(
        authority_fixtures.GENERATION,
        scope,
    )
    generation_id = acquisition._derive_acquisition_generation_id(
        authority_fixtures.GENERATION,
        scope,
        0,
        mandate.binding.commitment,
        head,
        mandate.protection_mandate.emergency_recovery_compatibility.commitment,
    )
    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.execution is refresh.execution
    assert result.authority is not refresh.authority
    assert result.venue is result.authority.venue
    assert result.protection is None
    assert result.created_effect_id is None
    assert result.fresh_claim is None
    assert result._refresh is refresh
    assert (
        result._registration_receipt.operation
        is authority.AcquisitionAuthorityOperation.REGISTER
    )
    assert result._registration_receipt.ordered_venue_transition_commitments == ()

    status = acquisition.project_acquisition_controller(result.state)
    assert status.position_scope == scope
    assert status.controller_head == head
    assert status.successor_ordinal == 0
    assert status.live_generation_id == generation_id
    assert status.protection_commitment is None
    post_admission = authority.project_acquisition_admission(
        result.authority,
        result.execution,
        scope,
    )
    assert post_admission.kind is authority.AcquisitionAdmissionKind.SUCCESSOR
    assert not post_admission.permits_genesis(
        authority_fixtures.GENERATION,
        result.execution,
        scope,
    )
    assert before == authority_fixtures._iterative_value_fingerprint(
        source_authority,
        source_execution,
    )


def test_wo0151_r11_serial_aborted_successors_advance_a_to_b_to_c() -> None:
    """Initialized-unused generations retire one at a time with bounded state."""

    authority, scope, initialized = _r8_initialized_controller()

    def advance(current: object, label: str) -> object:
        refresh = authority.refresh_acquisition_context(
            current.authority,
            current.execution,
            scope,
        )
        assert (
            refresh.disposition
            is authority.AcquisitionContextRefreshDisposition.CURRENT
        )
        assert refresh.authority is current.authority
        assert refresh.execution is current.execution
        bootstrap = current.venue.project_acquisition_bootstrap(
            current.execution,
            scope,
        )
        admission = authority.project_acquisition_admission(
            current.authority,
            current.execution,
            scope,
        )
        assert admission.kind is authority.AcquisitionAdmissionKind.SUCCESSOR
        mandate = _successor_mandate(current.state._mandate, label)
        return acquisition.begin_acquisition_generation(
            current.state,
            mandate,
            bootstrap,
            admission,
            refresh,
            current.protection,
        )

    a_id = initialized.state._controller.live_generation_id
    assert a_id is not None
    b = advance(initialized, "r11-successor-b")
    assert b.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert b.protection is None
    assert b.state.lineage is initialized.state.lineage
    assert b.state._controller.successor_ordinal == 1
    assert b.state._controller.controller_head != (
        initialized.state._controller.controller_head
    )
    b_id = b.state._controller.live_generation_id
    assert b_id is not None and b_id != a_id
    assert (
        b.state.registry.record(a_id).serving_class
        is acquisition.GenerationServingClass.RETIRED_UNSERVING
    )
    assert (
        b.state.registry.record(b_id).serving_class
        is acquisition.GenerationServingClass.LIVE
    )

    c = advance(b, "r11-successor-c")
    assert c.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert c.protection is None
    assert c.state.lineage is b.state.lineage
    assert c.state._controller.successor_ordinal == 2
    c_id = c.state._controller.live_generation_id
    assert c_id is not None and c_id not in (a_id, b_id)
    assert (
        c.state.registry.record(a_id).serving_class
        is acquisition.GenerationServingClass.RETIRED_UNSERVING
    )
    assert (
        c.state.registry.record(b_id).serving_class
        is acquisition.GenerationServingClass.RETIRED_UNSERVING
    )
    assert (
        c.state.registry.record(c_id).serving_class
        is acquisition.GenerationServingClass.LIVE
    )
    assert c._registration_receipt is not None
    assert c._registration_receipt.ordered_venue_transition_commitments == ()
    current = authority.refresh_acquisition_context(
        c.authority,
        c.execution,
        scope,
    )
    assert current.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT


def _r12_successor_attempt(
    authority: object,
    current: object,
    scope: PositionScope,
    mandate: object,
) -> object:
    """Use the one ordinary public successor path for focused R12 controls."""

    refresh = authority.refresh_acquisition_context(
        current.authority,
        current.execution,
        scope,
    )
    assert refresh.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    bootstrap = current.venue.project_acquisition_bootstrap(current.execution, scope)
    admission = authority.project_acquisition_admission(
        current.authority,
        current.execution,
        scope,
    )
    assert admission.kind is authority.AcquisitionAdmissionKind.SUCCESSOR
    return acquisition.begin_acquisition_generation(
        current.state,
        mandate,
        bootstrap,
        admission,
        refresh,
        current.protection,
    )


def _r12_state_with_resealed_registry(
    state: object,
    *,
    records: object,
    market_stream_routes: object,
) -> object:
    """Forge only a test-owned sealed registry relation for R12 negatives."""

    registry = object.__new__(acquisition.GenerationRegistry)
    object.__setattr__(registry, "_records", records)
    object.__setattr__(registry, "_market_stream_routes", market_stream_routes)
    object.__setattr__(
        registry,
        "_seal",
        acquisition._registry_seal(records, market_stream_routes),
    )
    assert acquisition._registry_is_authentic(registry)
    return acquisition._new_acquisition_controller_state(
        controller=state._controller,
        mandate=state._mandate,
        registry=registry,
        lineage=state.lineage,
    )


def test_wo0151_r12_refuses_nonadjacent_market_stream_reuse() -> None:
    """A distinct successor cannot reuse any retired generation's stream."""

    authority, scope, initialized = _r8_initialized_controller()

    def advance(
        current: object,
        label: str,
        *,
        stream_generation: kernel.MarketStreamGenerationId | None = None,
    ) -> object:
        refresh = authority.refresh_acquisition_context(
            current.authority,
            current.execution,
            scope,
        )
        assert (
            refresh.disposition
            is authority.AcquisitionContextRefreshDisposition.CURRENT
        )
        bootstrap = current.venue.project_acquisition_bootstrap(
            current.execution,
            scope,
        )
        admission = authority.project_acquisition_admission(
            current.authority,
            current.execution,
            scope,
        )
        assert admission.kind is authority.AcquisitionAdmissionKind.SUCCESSOR
        mandate = _successor_mandate(
            current.state._mandate,
            label,
            stream_generation=stream_generation,
        )
        return acquisition.begin_acquisition_generation(
            current.state,
            mandate,
            bootstrap,
            admission,
            refresh,
            current.protection,
        )

    a_stream = (
        initialized.state._mandate.protection_mandate.evidence_policy.stream_generation
    )
    b = advance(initialized, "r12-successor-b")
    assert b.disposition is acquisition.AcquisitionControllerDisposition.APPLIED

    refused = advance(
        b,
        "r12-fresh-binding-with-retired-a-stream",
        stream_generation=a_stream,
    )

    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.state is b.state
    assert refused.authority is b.authority
    assert refused.execution is b.execution
    assert refused.venue is b.venue
    assert refused.protection is b.protection
    assert refused.created_effect_id is None
    assert refused.fresh_claim is None
    assert refused._registration_receipt is None


@pytest.mark.parametrize(
    "malformed_kind",
    ("present-none", "wrong-key-route", "wrong-runtime-type"),
)
def test_wo0151_r12_r1_refuses_a_present_malformed_candidate_stream_route(
    malformed_kind: str,
) -> None:
    """Only absence is fresh; a malformed retained candidate route is refused."""

    authority, scope, initialized = _r8_initialized_controller()
    b = _r12_successor_attempt(
        authority,
        initialized,
        scope,
        _successor_mandate(initialized.state._mandate, "r12-r1-successor-b"),
    )
    assert b.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    retired_a_stream = (
        initialized.state._mandate.protection_mandate.evidence_policy.stream_generation
    )
    candidate = _successor_mandate(
        b.state._mandate,
        "r12-r1-fresh-binding-with-retired-a-stream",
        stream_generation=retired_a_stream,
    )
    candidate_stream = candidate.protection_mandate.evidence_policy.stream_generation
    candidate_key = acquisition._market_stream_route_key(candidate_stream)
    if malformed_kind == "present-none":
        route_value = None
        route_commitment = b"\x96" * 32
    elif malformed_kind == "wrong-key-route":
        current_stream = (
            b.state._mandate.protection_mandate.evidence_policy.stream_generation
        )
        current_route = b.state.registry._market_stream_routes.get(
            acquisition._market_stream_route_key(current_stream)
        )
        assert current_route is not None
        route_value = current_route
        route_commitment = current_route._seal
    else:
        route_value = object()
        route_commitment = b"\x99" * 32
    routes = b.state.registry._market_stream_routes.replace_existing(
        candidate_key,
        route_value,
        route_commitment,
    )
    forged_state = _r12_state_with_resealed_registry(
        b.state,
        records=b.state.registry._records,
        market_stream_routes=routes,
    )
    assert acquisition._controller_state_is_authentic(forged_state)

    refresh = authority.refresh_acquisition_context(b.authority, b.execution, scope)
    assert refresh.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    bootstrap = b.venue.project_acquisition_bootstrap(b.execution, scope)
    admission = authority.project_acquisition_admission(b.authority, b.execution, scope)
    assert admission.kind is authority.AcquisitionAdmissionKind.SUCCESSOR
    refused = acquisition.begin_acquisition_generation(
        forged_state,
        candidate,
        bootstrap,
        admission,
        refresh,
        b.protection,
    )

    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.state is forged_state
    assert refused.authority is b.authority
    assert refused.execution is b.execution
    assert refused.venue is b.venue
    assert refused.protection is b.protection
    assert refused.created_effect_id is None
    assert refused.fresh_claim is None
    assert refused._registration_receipt is None


def test_wo0151_r12_r1_rejects_a_malformed_current_stream_route_as_input() -> None:
    """The retained live stream relation is an authenticity fence, not REFUSED."""

    authority, scope, initialized = _r8_initialized_controller()
    current_stream = (
        initialized.state._mandate.protection_mandate.evidence_policy.stream_generation
    )
    current_key = acquisition._market_stream_route_key(current_stream)
    routes = initialized.state.registry._market_stream_routes.replace_existing(
        current_key,
        None,
        b"\x97" * 32,
    )
    forged_state = _r12_state_with_resealed_registry(
        initialized.state,
        records=initialized.state.registry._records,
        market_stream_routes=routes,
    )
    assert not acquisition._controller_state_is_authentic(forged_state)
    candidate = _successor_mandate(
        initialized.state._mandate,
        "r12-r1-current-route-invalid-candidate",
    )
    refresh = authority.refresh_acquisition_context(
        initialized.authority,
        initialized.execution,
        scope,
    )
    bootstrap = initialized.venue.project_acquisition_bootstrap(
        initialized.execution,
        scope,
    )
    admission = authority.project_acquisition_admission(
        initialized.authority,
        initialized.execution,
        scope,
    )

    with pytest.raises(ValueError, match="incompatible components"):
        acquisition.begin_acquisition_generation(
            forged_state,
            candidate,
            bootstrap,
            admission,
            refresh,
            initialized.protection,
        )


def test_wo0151_r12_r1_accepts_a_value_equivalent_current_stream_route() -> None:
    """Immutable sealed route values authenticate by relation, not object identity."""

    authority, scope, initialized = _r8_initialized_controller()
    current_stream = (
        initialized.state._mandate.protection_mandate.evidence_policy.stream_generation
    )
    current_key = acquisition._market_stream_route_key(current_stream)
    route = initialized.state.registry._market_stream_routes.get(current_key)
    assert route is not None
    copied_route = copy(route)
    assert copied_route is not route
    assert copied_route == route
    routes = initialized.state.registry._market_stream_routes.replace_existing(
        current_key,
        copied_route,
        copied_route._seal,
    )
    copied_state = _r12_state_with_resealed_registry(
        initialized.state,
        records=initialized.state.registry._records,
        market_stream_routes=routes,
    )
    assert acquisition._controller_state_is_authentic(copied_state)
    assert (
        acquisition._registry_market_stream_route(
            copied_state.registry,
            current_stream,
        )
        is copied_route
    )

    applied = _r12_successor_attempt(
        authority,
        SimpleNamespace(
            state=copied_state,
            authority=initialized.authority,
            execution=initialized.execution,
            venue=initialized.venue,
            protection=initialized.protection,
        ),
        scope,
        _successor_mandate(copied_state._mandate, "r12-r1-value-equivalent-b"),
    )

    assert applied.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert applied._registration_receipt is not None


def test_wo0151_r12_r1_stream_route_lookup_cannot_fall_back_to_get() -> None:
    """Successor admission uses exact presence, not legacy ``None`` reads."""

    authority, scope, initialized = _r8_initialized_controller()
    b = _r12_successor_attempt(
        authority,
        initialized,
        scope,
        _successor_mandate(initialized.state._mandate, "r12-r1-get-trap-b"),
    )
    assert b.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    stream_routes = b.state.registry._market_stream_routes
    original_get = acquisition._PersistentKeyMap.get

    def _forbid_stream_route_get(self: object, key: bytes) -> object:
        if self is stream_routes:
            raise AssertionError("stream-route lookup fell back to legacy get")
        return original_get(self, key)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            acquisition._PersistentKeyMap,
            "get",
            _forbid_stream_route_get,
        )
        applied = _r12_successor_attempt(
            authority,
            b,
            scope,
            _successor_mandate(b.state._mandate, "r12-r1-get-trap-c"),
        )

    assert applied.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert applied._registration_receipt is not None
    restored = _r12_successor_attempt(
        authority,
        b,
        scope,
        _successor_mandate(b.state._mandate, "r12-r1-get-trap-restored-c"),
    )
    assert restored.disposition is acquisition.AcquisitionControllerDisposition.APPLIED


def test_wo0151_r12_r1_candidate_lookup_bypass_turns_reuse_control_red() -> None:
    """The early route check is required for an ordinary duplicate-stream REFUSED."""

    authority, scope, initialized = _r8_initialized_controller()
    b = _r12_successor_attempt(
        authority,
        initialized,
        scope,
        _successor_mandate(initialized.state._mandate, "r12-r1-bypass-b"),
    )
    assert b.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    retired_a_stream = (
        initialized.state._mandate.protection_mandate.evidence_policy.stream_generation
    )
    candidate = _successor_mandate(
        b.state._mandate,
        "r12-r1-bypass-reused-a-stream",
        stream_generation=retired_a_stream,
    )
    original = acquisition._registry_market_stream_route
    calls = 0

    def _bypass_only_the_candidate_lookup(
        registry: object,
        stream_generation: object,
    ) -> object:
        nonlocal calls
        if stream_generation == retired_a_stream:
            calls += 1
            if calls == 1:
                return None
        return original(registry, stream_generation)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            acquisition,
            "_registry_market_stream_route",
            _bypass_only_the_candidate_lookup,
        )
        with pytest.raises(ValueError, match="cannot reuse a market stream"):
            _r12_successor_attempt(authority, b, scope, candidate)

    assert calls == 2
    restored = _r12_successor_attempt(authority, b, scope, candidate)
    assert restored.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert restored.state is b.state
    assert restored._registration_receipt is None


def test_wo0151_r11_successor_refuses_changed_recovery_compatibility() -> None:
    """A new mandate cannot change the controller-lifetime emergency contract."""

    authority, scope, initialized = _r8_initialized_controller()
    refresh = authority.refresh_acquisition_context(
        initialized.authority,
        initialized.execution,
        scope,
    )
    bootstrap = initialized.venue.project_acquisition_bootstrap(
        initialized.execution,
        scope,
    )
    admission = authority.project_acquisition_admission(
        initialized.authority,
        initialized.execution,
        scope,
    )
    protection = protection_fixtures._protection_module()
    changed_protection = protection_fixtures._mandate(
        protection,
        mandate_id=kernel.MandateId("wo0151-r11-incompatible-protection"),
        position_scope=scope,
        session_id=initialized.state._mandate.session_id,
        stream_generation=kernel.MarketStreamGenerationId("cc" * 32),
        configuration_version="wo0151-r11-incompatible-protection-v1",
    )
    changed = _approved_acquisition_mandate(
        position_scope=scope,
        session_id=initialized.state._mandate.session_id,
        protection_mandate=changed_protection,
        label="r11-incompatible",
    )

    refused = acquisition.begin_acquisition_generation(
        initialized.state,
        changed,
        bootstrap,
        admission,
        refresh,
        None,
    )

    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.state is initialized.state
    assert refused.authority is initialized.authority
    assert refused.protection is None
    assert refused._registration_receipt is None


def test_wo0151_r11_successor_admission_requires_terminal_no_work() -> None:
    """A flat snapshot cannot retire a generation while its BUY remains live."""

    authority, scope, created = _r8_created_first_effect()
    assert created.created_effect_id is not None
    admission = authority.project_acquisition_admission(
        created.authority,
        created.execution,
        scope,
    )

    assert admission.kind is authority.AcquisitionAdmissionKind.SUCCESSOR
    assert not admission.permits_successor(
        created.state.application_generation_id,
        created.execution,
        scope,
    )


def test_wo0151_r8_same_account_history_initializes_only_the_clear_target() -> None:
    """Sibling history is a bounded freshness witness, not target authority."""

    authority = authority_fixtures._authority_module()
    protection = protection_fixtures._protection_module()
    scope = authority_fixtures.EXECUTION.position.scope
    other_scope = PositionScope(
        broker=authority_fixtures.BROKER,
        environment=authority_fixtures.ENVIRONMENT,
        account=authority_fixtures.ACCOUNT,
        symbol_id=authority_fixtures.OTHER_SYMBOL,
    )
    other_execution = authority_fixtures.ExecutionSnapshot.flat(other_scope)
    book, other_execution = authority_fixtures._apply_closed_sell_fill(
        VenueRecoveryBook.empty(authority_fixtures.VENUE_SCOPE),
        other_execution,
        label="wo0151-r8-sibling-history",
        leg_key=VenueLegKey(
            broker=authority_fixtures.BROKER,
            environment=authority_fixtures.ENVIRONMENT,
            account=authority_fixtures.ACCOUNT,
            order_id=OrderId("wo0151-r8-sibling-history-leg"),
        ),
        symbol_id=authority_fixtures.OTHER_SYMBOL,
    )
    source_authority = authority_fixtures._forge_positive_predecessor(
        authority,
        predecessor=authority_fixtures._forge_venue_predecessor(
            authority_fixtures._genesis(authority),
            book,
        ),
    )
    before = authority_fixtures._iterative_value_fingerprint(
        source_authority,
        other_execution,
    )

    refresh = authority.refresh_acquisition_context(
        source_authority,
        other_execution,
        scope,
    )
    assert (
        refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP
    )
    assert refresh.authority is not None
    assert refresh.execution is not None
    bootstrap = refresh.authority.venue.project_acquisition_bootstrap(
        refresh.execution,
        scope,
    )
    admission = authority.project_acquisition_admission(
        refresh.authority,
        refresh.execution,
        scope,
    )
    protection_mandate = protection_fixtures._mandate(
        protection,
        position_scope=scope,
        session_id=refresh.authority.session_id,
    )
    mandate = _approved_acquisition_mandate(
        position_scope=scope,
        session_id=refresh.authority.session_id,
        protection_mandate=protection_mandate,
    )

    result = acquisition.initialize_acquisition_controller(
        authority_fixtures.GENERATION,
        mandate,
        bootstrap,
        admission,
        refresh,
        None,
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.execution.position.scope == scope
    assert result.authority.venue.execution_binding(scope) is not None
    assert (
        acquisition.project_acquisition_controller(result.state).position_scope == scope
    )
    assert before == authority_fixtures._iterative_value_fingerprint(
        source_authority,
        other_execution,
    )


def test_wo0151_r8_generic_buy_and_public_registration_replay_refuse() -> None:
    """The bootstrap record is reserved for the later specialized first request."""

    authority = authority_fixtures._authority_module()
    protection = protection_fixtures._protection_module()
    source_authority = authority_fixtures._forge_positive_predecessor(authority)
    source_execution = authority_fixtures.EXECUTION
    scope = source_execution.position.scope
    refresh = authority.refresh_acquisition_context(
        source_authority,
        source_execution,
        scope,
    )
    assert (
        refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP
    )
    assert refresh.authority is not None
    assert refresh.execution is not None
    bootstrap = refresh.authority.venue.project_acquisition_bootstrap(
        refresh.execution,
        scope,
    )
    admission = authority.project_acquisition_admission(
        refresh.authority,
        refresh.execution,
        scope,
    )

    before_command = authority_fixtures._create_command(
        authority,
        refresh.authority,
        label="wo0151-r8-bootstrap-generic-before",
        side=authority_fixtures.ExecutionSide.BUY,
    )
    assert venue._venue_authority_view(
        refresh.authority.venue,
        refresh.execution,
        scope,
        None,
    ).bootstrap_bound_target_active
    before_fingerprint = authority_fixtures._iterative_value_fingerprint(
        refresh.authority,
        refresh.execution,
        before_command,
    )
    before_result = authority.apply_execution_authority_input(
        refresh.authority,
        refresh.execution,
        before_command,
    )
    assert before_result.disposition is authority.AuthorityDisposition.REFUSED
    assert before_result.reason is authority.AuthorityReason.VENUE_UNCERTAIN
    assert before_result.state is refresh.authority
    assert before_fingerprint == authority_fixtures._iterative_value_fingerprint(
        refresh.authority,
        refresh.execution,
        before_command,
    )
    assert venue._venue_authority_view(
        refresh.authority.venue,
        refresh.execution,
        scope,
        None,
    ).bootstrap_bound_target_active

    protection_mandate = protection_fixtures._mandate(
        protection,
        position_scope=scope,
        session_id=refresh.authority.session_id,
    )
    mandate = _approved_acquisition_mandate(
        position_scope=scope,
        session_id=refresh.authority.session_id,
        protection_mandate=protection_mandate,
    )
    initialized = acquisition.initialize_acquisition_controller(
        authority_fixtures.GENERATION,
        mandate,
        bootstrap,
        admission,
        refresh,
        None,
    )
    ordinary = authority.refresh_acquisition_context(
        initialized.authority,
        initialized.execution,
        scope,
    )
    assert (
        ordinary.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    assert ordinary.authority is initialized.authority
    assert ordinary.execution is initialized.execution
    assert venue._venue_authority_view(
        initialized.authority.venue,
        initialized.execution,
        scope,
        None,
    ).bootstrap_bound_target_active

    after_command = authority_fixtures._create_command(
        authority,
        initialized.authority,
        label="wo0151-r8-bootstrap-generic-after",
        side=authority_fixtures.ExecutionSide.BUY,
    )
    after_fingerprint = authority_fixtures._iterative_value_fingerprint(
        initialized.authority,
        initialized.execution,
        after_command,
    )
    after_result = authority.apply_execution_authority_input(
        initialized.authority,
        initialized.execution,
        after_command,
    )
    assert after_result.disposition is authority.AuthorityDisposition.REFUSED
    assert after_result.reason is authority.AuthorityReason.VENUE_UNCERTAIN
    assert after_result.state is initialized.authority
    assert after_fingerprint == authority_fixtures._iterative_value_fingerprint(
        initialized.authority,
        initialized.execution,
        after_command,
    )
    assert venue._venue_authority_view(
        initialized.authority.venue,
        initialized.execution,
        scope,
        None,
    ).bootstrap_bound_target_active

    head = acquisition._acquisition_controller_genesis_head(
        authority_fixtures.GENERATION,
        scope,
    )
    generation_id = acquisition._derive_acquisition_generation_id(
        authority_fixtures.GENERATION,
        scope,
        0,
        mandate.binding.commitment,
        head,
        mandate.protection_mandate.emergency_recovery_compatibility.commitment,
    )
    private_replay = authority._mint_acquisition_bootstrap_registration_command(
        application_generation_id=authority_fixtures.GENERATION,
        position_scope=scope,
        session_id=mandate.session_id,
        generation_id=generation_id,
        acquisition_mandate_id=mandate.acquisition_mandate_id,
        protection_mandate_id=mandate.protection_mandate.mandate_id,
        binding_commitment=mandate.binding.commitment,
        emergency_recovery_compatibility_commitment=(
            mandate.protection_mandate.emergency_recovery_compatibility.commitment
        ),
        controller_head=head,
        refresh=refresh,
        bootstrap=bootstrap,
        admission=admission,
    )
    _assert_every_retained_field_is_authenticated(
        private_replay.registration,
        authority._acquisition_currentness_registration_is_authentic,
    )
    _assert_every_retained_field_is_authenticated(
        private_replay,
        authority._register_acquisition_currentness_command_is_authentic,
    )
    replay_result = authority.apply_execution_authority_input(
        initialized.authority,
        initialized.execution,
        private_replay,
    )
    assert replay_result.disposition is authority.AuthorityDisposition.REFUSED
    assert replay_result.reason is authority.AuthorityReason.VENUE_UNCERTAIN
    assert replay_result.state is initialized.authority


def test_wo0151_r8_first_specialized_buy_atomically_promotes_bootstrap_record() -> None:
    """Only the first sealed specialized BUY may consume a live R8 record."""

    authority = authority_fixtures._authority_module()
    protection = protection_fixtures._protection_module()
    source_authority = authority_fixtures._forge_positive_predecessor(authority)
    source_execution = authority_fixtures.EXECUTION
    scope = source_execution.position.scope
    bootstrap_refresh = authority.refresh_acquisition_context(
        source_authority,
        source_execution,
        scope,
    )
    assert (
        bootstrap_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP
    )
    assert bootstrap_refresh.authority is not None
    assert bootstrap_refresh.execution is not None
    bootstrap = bootstrap_refresh.authority.venue.project_acquisition_bootstrap(
        bootstrap_refresh.execution,
        scope,
    )
    admission = authority.project_acquisition_admission(
        bootstrap_refresh.authority,
        bootstrap_refresh.execution,
        scope,
    )
    protection_mandate = protection_fixtures._mandate(
        protection,
        position_scope=scope,
        session_id=bootstrap_refresh.authority.session_id,
    )
    mandate = _approved_acquisition_mandate(
        position_scope=scope,
        session_id=bootstrap_refresh.authority.session_id,
        protection_mandate=protection_mandate,
    )
    initialized = acquisition.initialize_acquisition_controller(
        authority_fixtures.GENERATION,
        mandate,
        bootstrap,
        admission,
        bootstrap_refresh,
        None,
    )
    initial_refresh = authority.refresh_acquisition_context(
        initialized.authority,
        initialized.execution,
        scope,
    )
    assert (
        initial_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    assert initial_refresh.authority is initialized.authority
    assert initial_refresh.execution is initialized.execution
    bootstrap_record = initialized.authority.venue._bootstrap_bound_target_record(scope)
    assert bootstrap_record is not None
    assert venue._venue_authority_view(
        initialized.authority.venue,
        initialized.execution,
        scope,
        None,
    ).bootstrap_bound_target_active

    other_scope = PositionScope(
        broker=authority_fixtures.BROKER,
        environment=authority_fixtures.ENVIRONMENT,
        account=authority_fixtures.ACCOUNT,
        symbol_id=authority_fixtures.OTHER_SYMBOL,
    )
    other_execution = authority_fixtures.ExecutionSnapshot.flat(other_scope)
    advanced_book, advanced_source = authority_fixtures._apply_closed_sell_fill(
        initialized.authority.venue,
        other_execution,
        label="wo0151-r8-first-buy-refresh-sibling",
        leg_key=VenueLegKey(
            broker=authority_fixtures.BROKER,
            environment=authority_fixtures.ENVIRONMENT,
            account=authority_fixtures.ACCOUNT,
            order_id=OrderId("wo0151-r8-first-buy-refresh-sibling-leg"),
        ),
        symbol_id=authority_fixtures.OTHER_SYMBOL,
    )
    advanced_authority = authority_fixtures._forge_venue_predecessor(
        initialized.authority,
        advanced_book,
    )
    refreshed = authority.refresh_acquisition_context(
        advanced_authority,
        advanced_source,
        scope,
    )
    assert (
        refreshed.disposition
        is authority.AcquisitionContextRefreshDisposition.REFRESHED
    )
    assert refreshed.authority is not None
    assert refreshed.execution is not None
    assert refreshed.matches_current(
        refreshed.authority,
        authority_fixtures.GENERATION,
        scope,
    )
    refresh = authority.refresh_acquisition_context(
        refreshed.authority,
        advanced_source,
        scope,
    )
    assert refresh.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    assert refresh.authority is refreshed.authority
    assert refresh.execution is refreshed.execution
    assert venue._venue_authority_view(
        refresh.authority.venue,
        refresh.execution,
        scope,
        None,
    ).bootstrap_bound_target_active

    generic_buy = authority_fixtures._create_command(
        authority,
        refresh.authority,
        label="wo0151-r8-refreshed-generic-buy",
        side=authority_fixtures.ExecutionSide.BUY,
    )
    generic_before = authority_fixtures._iterative_value_fingerprint(
        refresh.authority,
        refresh.execution,
        generic_buy,
    )
    generic_result = authority.apply_execution_authority_input(
        refresh.authority,
        refresh.execution,
        generic_buy,
    )
    assert generic_result.disposition is authority.AuthorityDisposition.REFUSED
    assert generic_result.state is refresh.authority
    assert generic_before == authority_fixtures._iterative_value_fingerprint(
        refresh.authority,
        refresh.execution,
        generic_buy,
    )

    raw_request = authority._venue_request(generic_buy)
    raw_before = authority_fixtures._iterative_value_fingerprint(
        refresh.authority.venue,
        refresh.execution,
        raw_request,
    )
    raw_result = venue._apply_venue_input(
        refresh.authority.venue,
        refresh.execution,
        raw_request,
    )
    assert raw_result.disposition is venue.VenueRecoveryDisposition.REFUSED
    assert raw_result.book is refresh.authority.venue
    assert raw_result.execution is refresh.execution
    assert raw_before == authority_fixtures._iterative_value_fingerprint(
        refresh.authority.venue,
        refresh.execution,
        raw_request,
    )
    with pytest.raises(TypeError, match="exact private permit"):
        venue._apply_venue_input(
            refresh.authority.venue,
            refresh.execution,
            raw_request,
            promotion=True,  # type: ignore[arg-type]
        )
    forged_promotion = object.__new__(venue._BootstrapPromotionPermit)
    forged_result = venue._apply_venue_input(
        refresh.authority.venue,
        refresh.execution,
        raw_request,
        promotion=forged_promotion,
    )
    assert forged_result.disposition is venue.VenueRecoveryDisposition.REFUSED
    assert forged_result.book is refresh.authority.venue
    assert forged_result.execution is refresh.execution
    assert venue._venue_authority_view(
        refresh.authority.venue,
        refresh.execution,
        scope,
        None,
    ).bootstrap_bound_target_active
    alternate_buy = authority_fixtures._create_command(
        authority,
        refresh.authority,
        label="wo0151-r8-refreshed-alternate-raw-buy",
        side=authority_fixtures.ExecutionSide.BUY,
    )
    alternate_request = authority._venue_request(alternate_buy)
    request_bound_promotion = venue._mint_bootstrap_promotion_permit(
        refresh.authority.venue,
        refresh.execution,
        raw_request,
    )
    wrong_request_result = venue._apply_venue_input(
        refresh.authority.venue,
        refresh.execution,
        alternate_request,
        promotion=request_bound_promotion,
    )
    assert wrong_request_result.disposition is venue.VenueRecoveryDisposition.REFUSED
    assert wrong_request_result.book is refresh.authority.venue
    assert wrong_request_result.execution is refresh.execution
    assert venue._venue_authority_view(
        refresh.authority.venue,
        refresh.execution,
        scope,
        None,
    ).bootstrap_bound_target_active

    oversized_terms = acquisition.AcquisitionEffectTerms(
        quantity=authority_fixtures.Quantity(2),
        limit_price=authority_fixtures.PRICE,
        order_type=acquisition.AcquisitionOrderType.LIMIT,
        evaluation_time=1,
    )
    before_fingerprint = authority_fixtures._iterative_value_fingerprint(
        initialized.state,
        refresh.authority,
        refresh.execution,
        oversized_terms,
    )
    refused = acquisition.create_acquisition_effect(
        initialized.state,
        refresh,
        None,
        oversized_terms,
        authority.AuthorityInputId("wo0151-r8-oversized-first-buy"),
    )
    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.state is initialized.state
    assert refused.authority is refresh.authority
    assert refused.execution is refresh.execution
    assert refused.venue is refresh.authority.venue
    assert refused.created_effect_id is None
    assert before_fingerprint == authority_fixtures._iterative_value_fingerprint(
        initialized.state,
        refresh.authority,
        refresh.execution,
        oversized_terms,
    )
    assert venue._venue_authority_view(
        refresh.authority.venue,
        refresh.execution,
        scope,
        None,
    ).bootstrap_bound_target_active

    valid_terms = acquisition.AcquisitionEffectTerms(
        quantity=authority_fixtures.Quantity(1),
        limit_price=authority_fixtures.PRICE,
        order_type=acquisition.AcquisitionOrderType.LIMIT,
        evaluation_time=1,
    )
    created = acquisition.create_acquisition_effect(
        initialized.state,
        refresh,
        None,
        valid_terms,
        authority.AuthorityInputId("wo0151-r8-valid-first-buy"),
    )
    assert created.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert created.created_effect_id is not None
    assert created.venue is created.authority.venue
    assert (
        created._registration_receipt.operation
        is authority.AcquisitionAuthorityOperation.CREATE
    )
    assert len(created._registration_receipt.ordered_venue_transition_commitments) == 1
    effect = created.venue.effect(created.created_effect_id)
    assert effect is not None
    assert effect.state is venue.BrokerEffectState.REQUESTED
    assert effect.scope.side is authority_fixtures.ExecutionSide.BUY
    assert effect.scope.symbol_id == scope.symbol_id
    assert effect.scope.quantity == authority_fixtures.Quantity(1)
    assert effect.scope.mandate_id == mandate.protection_mandate.mandate_id
    assert not venue._venue_authority_view(
        created.authority.venue,
        created.execution,
        scope,
        None,
    ).bootstrap_bound_target_active
    assert created.authority.venue.execution_binding(scope) is not None

    view = authority.project_acquisition_effect(
        created.authority,
        created.created_effect_id,
    )
    assert view is not None
    assert view.position_scope == scope
    assert (
        view.generation_id
        == acquisition.project_acquisition_controller(created.state).live_generation_id
    )
    assert view.binding_commitment == mandate.binding.commitment
    assert view.terms == valid_terms
    assert view.terms_commitment == valid_terms.commitment
    assert view.economic_scope == valid_terms.commitment
    request_route = created.state.lineage.route_request(view.request_occurrence_id)
    effect_route = created.state.lineage.route_effect(created.created_effect_id)
    assert request_route is not None
    assert effect_route is not None
    assert request_route.route_kind is acquisition.GenerationRouteKind.REQUEST
    assert effect_route.route_kind is acquisition.GenerationRouteKind.EFFECT
    assert request_route.generation_id == view.generation_id
    assert effect_route.generation_id == view.generation_id

    retained_marker = created.venue._bootstrap_bound_target_by_scope.get(
        venue._position_scope_index_key(scope)
    )
    assert type(retained_marker) is venue._ConsumedBootstrapBoundTargetRecord
    forged_marker = venue._new_consumed_bootstrap_bound_target_record(
        active_record=bootstrap_record,
        effect=effect,
        request_input_id=retained_marker.request_input_id,
    )
    forged_markers = created.venue._bootstrap_bound_target_by_scope.replace_existing(
        venue._position_scope_index_key(scope),
        forged_marker,
        venue._bootstrap_record_value_commitment(forged_marker),
    )
    forged_book = copy(created.venue)
    object.__setattr__(
        forged_book,
        "_bootstrap_bound_target_by_scope",
        forged_markers,
    )
    with recovery_fixtures._test_certified_external_closure():
        created.venue._validate_full()
        with pytest.raises(ValueError, match="consumption provenance"):
            forged_book._validate_full()

    generic_claim = authority.ClaimEffect(
        input_id=authority.AuthorityInputId("wo0151-r8-generic-claim-refusal"),
        effect_id=created.created_effect_id,
        claim_occurrence_id=authority.ClaimOccurrenceId(
            "wo0151-r8-generic-claim-occurrence"
        ),
    )
    generic_claim_result = authority.apply_execution_authority_input(
        created.authority,
        created.execution,
        generic_claim,
    )
    assert generic_claim_result.disposition is authority.AuthorityDisposition.REFUSED
    assert generic_claim_result.state is created.authority


def test_wo0151_r8_specialized_claim_revalidates_current_controller() -> None:
    """Only a fresh sealed claim may dispatch the created acquisition BUY."""

    authority, scope, created = _r8_created_first_effect()
    assert created.created_effect_id is not None
    refresh = authority.refresh_acquisition_context(
        created.authority,
        created.execution,
        scope,
    )
    generic = authority.ClaimEffect(
        input_id=authority.AuthorityInputId(
            "wo0151-r8-generic-claim-before-specialized"
        ),
        effect_id=created.created_effect_id,
        claim_occurrence_id=authority.ClaimOccurrenceId(
            "wo0151-r8-generic-claim-before-specialized-occurrence"
        ),
    )
    generic_result = authority.apply_execution_authority_input(
        created.authority,
        created.execution,
        generic,
    )
    assert generic_result.disposition is authority.AuthorityDisposition.REFUSED
    assert generic_result.state is created.authority

    claimed = acquisition.claim_acquisition_effect(
        created.state,
        refresh,
        None,
        created.created_effect_id,
        authority.ClaimOccurrenceId("wo0151-r8-specialized-claim-occurrence"),
        authority.AuthorityInputId("wo0151-r8-specialized-claim"),
    )
    assert claimed.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert claimed.created_effect_id is None
    assert type(claimed.fresh_claim) is authority.AcquisitionClaimReceipt
    assert claimed.fresh_claim.effect_id == created.created_effect_id
    assert claimed.fresh_claim.claim_occurrence_id == authority.ClaimOccurrenceId(
        "wo0151-r8-specialized-claim-occurrence"
    )
    assert (
        acquisition.project_acquisition_controller(claimed.state).controller_head
        == acquisition.project_acquisition_controller(created.state).controller_head
    )
    effect = claimed.venue.effect(created.created_effect_id)
    assert effect is not None
    assert effect.state is venue.BrokerEffectState.DISPATCH_CLAIMED
    view = authority.project_acquisition_effect(
        claimed.authority,
        created.created_effect_id,
    )
    assert view is not None
    assert not view.serving

    post_refresh = authority.refresh_acquisition_context(
        claimed.authority,
        claimed.execution,
        scope,
    )
    stale = acquisition.claim_acquisition_effect(
        created.state,
        post_refresh,
        None,
        created.created_effect_id,
        authority.ClaimOccurrenceId("wo0151-r8-stale-specialized-claim-occurrence"),
        authority.AuthorityInputId("wo0151-r8-stale-specialized-claim"),
    )
    assert stale.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert stale.state is created.state
    assert stale.authority is post_refresh.authority

    duplicate = acquisition.claim_acquisition_effect(
        claimed.state,
        post_refresh,
        None,
        created.created_effect_id,
        authority.ClaimOccurrenceId("wo0151-r8-duplicate-specialized-claim-occurrence"),
        authority.AuthorityInputId("wo0151-r8-duplicate-specialized-claim"),
    )
    assert duplicate.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert duplicate.state is claimed.state
    assert duplicate.authority is claimed.authority


def test_wo0151_r11_final_claim_revalidates_the_exact_currentness_head() -> None:
    """A pre-minted claim cannot cross even a venue-neutral currentness advance."""

    authority, scope, created = _r8_created_first_effect()
    assert created.created_effect_id is not None
    refresh = authority.refresh_acquisition_context(
        created.authority,
        created.execution,
        scope,
    )
    assert refresh.authority is not None
    assert refresh.execution is not None
    claim_authority = refresh.authority
    claim_execution = refresh.execution
    mandate = created.state._mandate
    controller = created.state._controller
    generation_id = controller.live_generation_id
    assert generation_id is not None
    input_id = authority.AuthorityInputId("wo0151-r11-preminted-stale-claim")
    occurrence_id = authority.ClaimOccurrenceId(
        "wo0151-r11-preminted-stale-claim-occurrence"
    )
    permit = authority._mint_acquisition_claim_permit(
        claim_authority,
        claim_execution,
        application_generation_id=created.state.application_generation_id,
        position_scope=scope,
        session_id=mandate.session_id,
        generation_id=generation_id,
        acquisition_mandate_id=mandate.acquisition_mandate_id,
        protection_mandate_id=mandate.protection_mandate.mandate_id,
        binding_commitment=mandate.binding.commitment,
        emergency_recovery_compatibility_commitment=(
            mandate.protection_mandate.emergency_recovery_compatibility.commitment
        ),
        controller_head=controller.controller_head,
        successor_ordinal=controller.successor_ordinal,
        protection_commitment=created.state.protection_commitment,
        effect_id=created.created_effect_id,
        claim_occurrence_id=occurrence_id,
        refresh=refresh,
        input_id=input_id,
    )
    _assert_every_retained_field_is_authenticated(
        permit,
        authority._acquisition_claim_permit_is_authentic,
    )
    slot_key = authority._acquisition_scope_key(
        created.state.application_generation_id,
        scope,
    )
    retained = claim_authority._acquisition_currentness_by_scope.get(slot_key)
    assert authority._acquisition_currentness_entry_is_authentic(retained)
    advanced = authority._new_acquisition_currentness_entry(
        source_kind=authority._AcquisitionCurrentnessSourceKind.AUTHORITY_MUTATION,
        application_generation_id=retained.application_generation_id,
        position_scope=retained.position_scope,
        session_id=retained.session_id,
        generation_id=retained.generation_id,
        acquisition_mandate_id=retained.acquisition_mandate_id,
        protection_mandate_id=retained.protection_mandate_id,
        binding_commitment=retained.binding_commitment,
        emergency_recovery_compatibility_commitment=(
            retained.emergency_recovery_compatibility_commitment
        ),
        controller_head=sha256(
            b"wo0151-r11-late-currentness-head" + retained.controller_head
        ).digest(),
        successor_ordinal=retained.successor_ordinal,
        scope_execution_commitment=retained.scope_execution_commitment,
        venue_commitment=retained.venue_commitment,
        protection_commitment=retained.protection_commitment,
        predecessor_slot_commitment=retained.commitment,
    )
    stale_authority = authority._state_with(
        claim_authority,
        _acquisition_currentness_by_scope=authority._replaced(
            claim_authority._acquisition_currentness_by_scope,
            slot_key,
            advanced,
        ),
    )
    command = authority.ClaimAcquisitionEffect(
        input_id=input_id,
        effect_id=created.created_effect_id,
        claim_occurrence_id=occurrence_id,
        permit=permit,
    )

    refused = authority.apply_execution_authority_input(
        stale_authority,
        claim_execution,
        command,
    )

    assert refused.disposition is authority.AuthorityDisposition.REFUSED
    assert refused.state is stale_authority
    assert refused.acquisition_claim_receipt is None
    assert refused.venue_transitions == ()


def test_wo0151_r8_claim_receipt_rejects_tampered_hidden_input_binding() -> None:
    """A read receipt cannot be forged by pairing an arbitrary digest and seal."""

    authority, _, created = _r8_created_first_effect()
    assert created.created_effect_id is not None
    refresh = authority.refresh_acquisition_context(
        created.authority,
        created.execution,
        created.state.position_scope,
    )
    claimed = acquisition.claim_acquisition_effect(
        created.state,
        refresh,
        None,
        created.created_effect_id,
        authority.ClaimOccurrenceId("wo0151-r8-tampered-claim-occurrence"),
        authority.AuthorityInputId("wo0151-r8-tampered-claim"),
    )
    assert claimed.fresh_claim is not None
    receipt = claimed.fresh_claim
    forged = object.__new__(authority.AcquisitionClaimReceipt)
    for name in (
        "effect_id",
        "claim_occurrence_id",
        "controller_head",
        "scope_execution_commitment",
        "venue_commitment",
        "_input_id",
        "_authority_context_commitment",
        "_permit_commitment",
    ):
        object.__setattr__(forged, name, getattr(receipt, name))
    object.__setattr__(forged, "commitment", b"x" * 32)
    object.__setattr__(
        forged,
        "_seal",
        authority._commit_parts(
            b"execution-core/acquisition-authority/claim-receipt-seal/v1",
            forged.commitment,
        ),
    )

    assert not authority._acquisition_claim_receipt_is_authentic(forged)


def test_wo0151_current_generation_fill_arms_fresh_floor_only_protection() -> None:
    """One authenticated first BUY fill advances once and starts fresh normal protection."""

    authority, scope, claimed, filled = _r8_current_generation_fill_transition(
        acknowledged=True
    )

    applied = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )

    assert applied.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert applied.execution is filled.execution
    assert applied.venue is filled.book
    assert applied.protection is not None
    assert (
        applied.protection.policy
        is protection_fixtures._protection_module().ProtectionPolicy.FLOOR_ONLY
    )
    protection_context = (
        protection_fixtures._protection_module().project_acquisition_protection_context(
            applied.protection,
            applied.venue,
            applied.execution,
            applied.venue.project_acquisition_context(
                applied.execution,
                scope,
            ),
        )
    )
    assert protection_context is not None
    assert (
        applied.state.protection_commitment
        == protection_context.scope_protection_commitment
    )
    assert applied.state.protection_commitment != applied.protection.commitment
    assert (
        applied.state.scope_execution_commitment
        != claimed.state.scope_execution_commitment
    )
    assert (
        applied.state.venue_commitment
        == filled.book.project_acquisition_fact(filled).venue_commitment
    )
    assert (
        acquisition.project_acquisition_controller(applied.state).controller_head
        != acquisition.project_acquisition_controller(claimed.state).controller_head
    )
    effect_id = claimed.fresh_claim.effect_id
    relation = filled.book.project_acquisition_fact(filled).fact_relation()
    assert relation is not None
    record = applied.state.registry.record(
        acquisition.project_acquisition_controller(applied.state).live_generation_id
    )
    assert record is not None
    assert applied.state.lineage.route_effect(effect_id) is not None
    assert applied.state.lineage.route_owner(relation.leg_key) is not None
    assert applied.state.lineage.route_root(relation.root_key) is not None
    assert applied.state.lineage.route_fact(relation.fact_key) is not None

    replay = acquisition.reduce_acquisition_controller(
        applied.state,
        filled,
        applied.protection,
        applied.authority,
    )
    assert (
        replay.disposition is acquisition.AcquisitionControllerDisposition.EXACT_REPLAY
    )
    assert replay.state is applied.state
    assert replay.authority is applied.authority


def test_wo0151_current_generation_duplicate_fill_stays_nonserving() -> None:
    """A raw venue replay cannot become a second controller fact source."""

    authority, _, claimed, filled = _r8_current_generation_fill_transition()
    original = filled.book._input_record(
        VenueInputId("wo0151-r8-current-generation-fill-input")
    )
    assert original is not None
    venue_replay = recovery_fixtures.apply_venue_recovery_input(
        filled.book,
        filled.execution,
        original.item,
    )
    assert venue_replay.disposition is venue.VenueRecoveryDisposition.EXACT_REPLAY

    applied = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    replay = acquisition.reduce_acquisition_controller(
        applied.state,
        venue_replay,
        applied.protection,
        applied.authority,
    )

    assert replay.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert replay.state is applied.state
    assert replay.authority is applied.authority
    assert replay.protection is applied.protection
    assert replay.venue is venue_replay.book
    assert replay.execution is venue_replay.execution


def test_wo0151_current_generation_fact_bridges_passive_venue_progression() -> None:
    """A claimed root may fill after normal venue lifecycle progress, not only a stale token."""

    authority, scope, claimed, filled = _r8_current_generation_fill_transition(
        acknowledged=True,
    )
    projection = filled.book.project_acquisition_fact(filled)
    # Lifecycle observations may advance the venue book without changing the
    # bounded target authority coordinate used by controller currentness.
    assert projection.predecessor_venue_commitment == claimed.state.venue_commitment
    assert (
        projection.predecessor_scope_execution_commitment
        == claimed.state.scope_execution_commitment
    )
    assert projection.matches_predecessor_book(claimed.venue, scope)

    applied = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )

    assert applied.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert (
        applied.state.scope_execution_commitment
        == projection.scope_execution_commitment
    )
    assert applied.state.venue_commitment == projection.venue_commitment
    assert applied.state.venue_commitment != claimed.state.venue_commitment
    receipt = applied._registration_receipt
    assert receipt is not None
    assert receipt.predecessor_venue_commitment == claimed.state.venue_commitment
    assert receipt.venue_commitment == applied.state.venue_commitment


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    (
        ("effect_id", EffectId("wo0151-r8-forged-fact-effect")),
        ("command_commitment", b"\\x11" * 32),
    ),
)
def test_wo0151_current_generation_fact_refuses_forged_direct_proof(
    field_name: str,
    replacement: object,
) -> None:
    """The composite accepts only the venue-sealed direct fact relation."""

    authority, _, claimed, filled = _r8_current_generation_fill_transition()
    proof = filled._acquisition_fact_proof
    assert proof is not None
    forged_proof = replace(proof, **{field_name: replacement})
    forged = copy(filled)
    object.__setattr__(forged, "_acquisition_fact_proof", forged_proof)
    object.__setattr__(
        forged,
        "_acquisition_fact_proof_commitment",
        forged_proof.commitment,
    )

    refused = acquisition.reduce_acquisition_controller(
        claimed.state,
        forged,
        None,
        claimed.authority,
    )

    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.state is claimed.state
    assert refused.authority is claimed.authority
    assert refused.protection is None


def test_wo0151_current_generation_fact_refuses_stale_preclaim_authority() -> None:
    """A sealed fill still requires the authority snapshot current at final claim."""

    _, _, claimed, filled = _r8_current_generation_fill_transition()
    assert claimed._refresh is not None
    stale_authority = claimed._refresh.authority
    assert stale_authority is not None
    assert stale_authority is not claimed.authority

    refused = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        stale_authority,
    )

    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.state is claimed.state
    assert refused.authority is stale_authority
    assert refused.protection is None
    assert refused._registration_receipt is None


def test_wo0151_current_generation_fact_replay_refuses_new_target_authority() -> None:
    """A replay cannot pair the retained controller with a newer local authority."""

    authority, scope, claimed, filled = _r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    applied = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    reducing = copy(applied.authority)
    object.__setattr__(reducing, "mode", authority.TradingMode.REDUCING)
    flattened = authority_fixtures._authority_apply_twice(
        authority,
        reducing,
        applied.execution,
        authority.BeginManualFlatten(
            input_id=authority.AuthorityInputId(
                "wo0151-fact-replay-new-authority-input"
            ),
            flatten_id=authority.ManualFlattenId(
                "wo0151-fact-replay-new-authority-flatten"
            ),
            session_id=reducing.session_id,
            symbol_id=scope.symbol_id,
            actor=authority_fixtures.ActorId("wo0151-fact-replay-operator"),
            reason="prove that local authority invalidates a retained fact replay",
            evidence_reference=authority_fixtures.EvidenceReference(
                "wo0151-fact-replay-evidence"
            ),
            emergency_grant_id=None,
        ),
    )
    assert flattened.disposition is authority.AuthorityDisposition.APPLIED, (
        flattened.reason
    )
    assert flattened.state.venue is not applied.authority.venue
    refreshed = authority.refresh_acquisition_context(
        flattened.state,
        filled.execution,
        scope,
    )
    assert (
        refreshed.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    assert refreshed.authority_context is not None
    assert (
        refreshed.authority_context.authority_commitment
        != applied.state.authority_context_commitment
    )

    replay = acquisition.reduce_acquisition_controller(
        applied.state,
        filled,
        applied.protection,
        flattened.state,
    )

    assert replay.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert replay.state is applied.state
    assert replay.authority is flattened.state
    assert replay.protection is applied.protection
    assert replay._registration_receipt is None


def test_wo0151_current_generation_fact_registration_replay_and_conflict_are_inert() -> (
    None
):
    """The sealed public registration has only exact replay or inert conflict outcomes."""

    authority, scope, claimed, filled = _r8_current_generation_fill_transition()
    applied = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert applied.protection is not None
    projection = filled.book.project_acquisition_fact(filled)
    relation = projection.fact_relation()
    assert relation is not None
    generation_id = claimed.state._controller.live_generation_id
    assert generation_id is not None
    registration = authority._mint_acquisition_currentness_registration(
        application_generation_id=claimed.state.application_generation_id,
        position_scope=scope,
        session_id=claimed.state._mandate.session_id,
        generation_id=generation_id,
        acquisition_mandate_id=claimed.state._mandate.acquisition_mandate_id,
        protection_mandate_id=claimed.state._mandate.protection_mandate.mandate_id,
        binding_commitment=claimed.state._mandate.binding.commitment,
        emergency_recovery_compatibility_commitment=(
            claimed.state._mandate.protection_mandate.emergency_recovery_compatibility.commitment
        ),
        controller_head=acquisition._controller_head_after_fact(
            claimed.state,
            projection,
            relation,
        ),
        successor_ordinal=claimed.state._controller.successor_ordinal,
        protection_commitment=applied.state.protection_commitment,
        authority=applied.authority,
        fact_transition=filled,
        fact_projection=projection,
        predecessor_authority_context_commitment=(
            claimed.state.authority_context_commitment
        ),
    )
    command = authority.RegisterAcquisitionCurrentness.from_registration(registration)
    _assert_every_retained_field_is_authenticated(
        registration,
        authority._canonical_fact_currentness_registration_is_authentic,
    )
    _assert_every_retained_field_is_authenticated(
        command,
        authority._register_canonical_fact_currentness_command_is_authentic,
    )

    replay = authority.apply_execution_authority_input(
        applied.authority,
        applied.execution,
        command,
    )
    assert replay.disposition is authority.AuthorityDisposition.EXACT_REPLAY
    assert replay.state is applied.authority
    assert replay.acquisition_receipt is None

    conflict_command = copy(command)
    object.__setattr__(conflict_command, "_seal", b"\\xEA" * 32)
    conflict = authority.apply_execution_authority_input(
        applied.authority,
        applied.execution,
        conflict_command,
    )
    assert conflict.disposition is authority.AuthorityDisposition.CONFLICT
    assert conflict.state is applied.authority
    assert conflict.acquisition_receipt is None


def test_wo0151_current_generation_fact_keeps_generic_buy_nonserving() -> None:
    """A first canonical fact cannot reopen the generic BUY authority route."""

    authority, _, claimed, filled = _r8_current_generation_fill_transition()
    applied = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    command = authority_fixtures._create_command(
        authority,
        applied.authority,
        label="wo0151-r8-after-fact-generic-buy",
        side=authority_fixtures.ExecutionSide.BUY,
    )
    before = authority_fixtures._iterative_value_fingerprint(
        applied.authority,
        applied.execution,
        command,
    )

    refused = authority.apply_execution_authority_input(
        applied.authority,
        applied.execution,
        command,
    )

    assert refused.disposition is authority.AuthorityDisposition.REFUSED
    assert refused.state is applied.authority
    assert refused.created_effect_ids == ()
    assert before == authority_fixtures._iterative_value_fingerprint(
        applied.authority,
        applied.execution,
        command,
    )


def test_wo0151_current_generation_fact_replay_requires_fresh_protection() -> None:
    """The exact canonical fact cannot be replayed without its normal protection state."""

    authority, _, claimed, filled = _r8_current_generation_fill_transition()
    applied = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )

    refused = acquisition.reduce_acquisition_controller(
        applied.state,
        filled,
        None,
        applied.authority,
    )

    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.state is applied.state
    assert refused.authority is applied.authority
    assert refused.protection is None


def test_wo0151_r11_current_bust_updates_direct_lineage_and_flattens_once() -> None:
    """A predecessor-linked revision advances state instead of preserving stale E2."""

    authority, scope, claimed, filled = _r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    first = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert first.protection is not None
    relation = filled.book.project_acquisition_fact(filled).fact_relation()
    assert relation is not None
    bust_key = ExecutionFactKey(
        broker=scope.broker,
        environment=scope.environment,
        account=scope.account,
        source_event_id=SourceEventId("wo0151-r11-current-bust-source"),
    )
    bust = BrokerTradeBustFact(
        key=bust_key,
        scope=ExecutionScope(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            order_id=relation.leg_key.order_id,
            symbol_id=scope.symbol_id,
            side=ExecutionSide.BUY,
        ),
        root_fill_id=relation.root_key.root_fill_id,
        predecessor_source_event_id=relation.fact_key.source_event_id,
        reported_price=authority_fixtures.PRICE,
    )
    busted = recovery_fixtures.apply_venue_recovery_input(
        filled.book,
        filled.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("wo0151-r11-current-bust-input"),
            effect_id=relation.effect_id,
            leg_key=relation.leg_key,
            prior_root_quantity=authority_fixtures.Quantity(1),
            prior_venue_cumulative_quantity=authority_fixtures.Quantity(1),
            resulting_venue_cumulative_quantity=authority_fixtures.Quantity(0),
            fact=bust,
            evidence_digest=b"\xc1" * 32,
        ),
    )
    assert busted.disposition is venue.VenueRecoveryDisposition.APPLIED
    assert busted.quantity_delta == -1
    before = acquisition.project_acquisition_controller(first.state)
    generation_id = before.live_generation_id
    assert generation_id is not None
    before_record = first.state.registry.record(generation_id)
    assert before_record is not None

    result = acquisition.reduce_acquisition_controller(
        first.state,
        busted,
        first.protection,
        first.authority,
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.execution.position.raw_quantity == 0
    assert result.protection is not None
    assert (
        result.protection.policy
        is protection_fixtures._protection_module().ProtectionPolicy.HARD_BAIL
    )
    after = acquisition.project_acquisition_controller(result.state)
    assert after.controller_head != before.controller_head
    assert after.scope_execution_commitment != before.scope_execution_commitment
    fact_route = result.state.lineage.route_fact(bust_key)
    root_route = result.state.lineage.route_root(relation.root_key)
    assert fact_route is not None and fact_route.generation_id == generation_id
    assert root_route is not None and root_route.generation_id == generation_id
    after_record = result.state.registry.record(generation_id)
    assert after_record is not None
    assert (
        after_record.economics_head_commitment
        != before_record.economics_head_commitment
    )
    assert result.created_effect_id is None
    assert result.fresh_claim is None

    replay = acquisition.reduce_acquisition_controller(
        result.state,
        busted,
        result.protection,
        result.authority,
    )
    assert (
        replay.disposition is acquisition.AcquisitionControllerDisposition.EXACT_REPLAY
    )
    assert replay.state is result.state
    assert replay.protection is result.protection
    assert replay.created_effect_id is None
    assert replay.fresh_claim is None


def test_wo0151_r11_current_correct_updates_direct_lineage_once() -> None:
    """A predecessor-linked tail correction advances current E2 exactly once."""

    authority, scope, claimed, filled = _r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    first = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert first.protection is not None
    relation = filled.book.project_acquisition_fact(filled).fact_relation()
    assert relation is not None
    correction_key = ExecutionFactKey(
        broker=scope.broker,
        environment=scope.environment,
        account=scope.account,
        source_event_id=SourceEventId("wo0151-r11-current-correct-source"),
    )
    correction = BrokerTradeCorrectFact(
        key=correction_key,
        scope=ExecutionScope(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            order_id=relation.leg_key.order_id,
            symbol_id=scope.symbol_id,
            side=ExecutionSide.BUY,
        ),
        root_fill_id=relation.root_key.root_fill_id,
        predecessor_source_event_id=relation.fact_key.source_event_id,
        revised_quantity=authority_fixtures.Quantity(2),
        revised_price=authority_fixtures.PRICE,
    )
    corrected = recovery_fixtures.apply_venue_recovery_input(
        filled.book,
        filled.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("wo0151-r11-current-correct-input"),
            effect_id=relation.effect_id,
            leg_key=relation.leg_key,
            prior_root_quantity=authority_fixtures.Quantity(1),
            prior_venue_cumulative_quantity=authority_fixtures.Quantity(1),
            resulting_venue_cumulative_quantity=authority_fixtures.Quantity(2),
            fact=correction,
            evidence_digest=b"\xcf" * 32,
        ),
    )
    assert corrected.disposition is venue.VenueRecoveryDisposition.APPLIED
    assert corrected.quantity_delta == 1
    before = acquisition.project_acquisition_controller(first.state)
    generation_id = before.live_generation_id
    assert generation_id is not None
    before_record = first.state.registry.record(generation_id)
    assert before_record is not None

    result = acquisition.reduce_acquisition_controller(
        first.state,
        corrected,
        first.protection,
        first.authority,
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.execution.position.raw_quantity == 2
    assert result.protection is not None
    assert result.protection.policy is (
        protection_fixtures._protection_module().ProtectionPolicy.HARD_BAIL
    )
    assert result.created_effect_id is None
    assert result.fresh_claim is None
    after = acquisition.project_acquisition_controller(result.state)
    assert after.controller_head != before.controller_head
    after_record = result.state.registry.record(generation_id)
    assert after_record is not None
    assert (
        after_record.economics_head_commitment
        != before_record.economics_head_commitment
    )
    route = result.state.lineage.route_fact(correction_key)
    assert route is not None and route.generation_id == generation_id

    replay = acquisition.reduce_acquisition_controller(
        result.state,
        corrected,
        result.protection,
        result.authority,
    )
    assert (
        replay.disposition is acquisition.AcquisitionControllerDisposition.EXACT_REPLAY
    )
    assert replay.state is result.state
    assert replay.authority is result.authority
    assert replay.created_effect_id is None
    assert replay.fresh_claim is None


def test_wo0151_r11_non_tail_correct_enters_reconciliation_without_buy_service() -> (
    None
):
    """A canonical non-tail revision is retained once without granting service."""

    authority, scope, claimed, first_fill = _r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    first = acquisition.reduce_acquisition_controller(
        claimed.state,
        first_fill,
        None,
        claimed.authority,
    )
    assert first.protection is not None
    first_relation = first_fill.book.project_acquisition_fact(
        first_fill
    ).fact_relation()
    assert first_relation is not None

    second_fact = replace(
        recovery_fixtures._broker_fill(
            "wo0151-r11-reconciliation-second-source",
            "wo0151-r11-reconciliation-second-root",
            leg_key=first_relation.leg_key,
            quantity=1,
        ),
        key=ExecutionFactKey(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            source_event_id=SourceEventId("wo0151-r11-reconciliation-second-source"),
        ),
        scope=ExecutionScope(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            order_id=first_relation.leg_key.order_id,
            symbol_id=scope.symbol_id,
            side=ExecutionSide.BUY,
        ),
    )
    second_fill = recovery_fixtures.apply_venue_recovery_input(
        first.venue,
        first.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("wo0151-r11-reconciliation-second-input"),
            effect_id=first_relation.effect_id,
            leg_key=first_relation.leg_key,
            prior_cumulative_quantity=authority_fixtures.Quantity(1),
            resulting_cumulative_quantity=authority_fixtures.Quantity(2),
            fact=second_fact,
            evidence_digest=b"\xd1" * 32,
        ),
    )
    assert second_fill.disposition is venue.VenueRecoveryDisposition.APPLIED
    first_status = acquisition.project_acquisition_controller(first.state)
    first_generation_id = first_status.live_generation_id
    assert first_generation_id is not None
    first_record = first.state.registry.record(first_generation_id)
    assert first_record is not None
    second = acquisition.reduce_acquisition_controller(
        first.state,
        second_fill,
        first.protection,
        first.authority,
    )
    assert second.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert second.protection is not None
    second_status = acquisition.project_acquisition_controller(second.state)
    second_record = second.state.registry.record(first_generation_id)
    assert second_status.controller_head != first_status.controller_head
    assert second_record is not None
    assert second_record.economics_head_commitment != (
        first_record.economics_head_commitment
    )
    second_replay = acquisition.reduce_acquisition_controller(
        second.state,
        second_fill,
        second.protection,
        second.authority,
    )
    assert second_replay.disposition is (
        acquisition.AcquisitionControllerDisposition.EXACT_REPLAY
    )
    assert second_replay.state is second.state
    assert second_replay.created_effect_id is None
    assert second_replay.fresh_claim is None

    correction_key = ExecutionFactKey(
        broker=scope.broker,
        environment=scope.environment,
        account=scope.account,
        source_event_id=SourceEventId("wo0151-r11-reconciliation-correct-source"),
    )
    correction = BrokerTradeCorrectFact(
        key=correction_key,
        scope=ExecutionScope(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            order_id=first_relation.leg_key.order_id,
            symbol_id=scope.symbol_id,
            side=ExecutionSide.BUY,
        ),
        root_fill_id=first_relation.root_key.root_fill_id,
        predecessor_source_event_id=first_relation.fact_key.source_event_id,
        revised_quantity=authority_fixtures.Quantity(2),
        revised_price=authority_fixtures.PRICE,
    )
    reconciliation = recovery_fixtures.apply_venue_recovery_input(
        second.venue,
        second.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("wo0151-r11-reconciliation-correct-input"),
            effect_id=first_relation.effect_id,
            leg_key=first_relation.leg_key,
            prior_root_quantity=authority_fixtures.Quantity(1),
            prior_venue_cumulative_quantity=authority_fixtures.Quantity(2),
            resulting_venue_cumulative_quantity=authority_fixtures.Quantity(3),
            fact=correction,
            evidence_digest=b"\xd2" * 32,
        ),
    )
    assert (
        reconciliation.disposition
        is venue.VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    )
    assert reconciliation.quantity_delta == 1

    projection = reconciliation.book.project_acquisition_fact(reconciliation)
    assert (
        projection.source_kind
        is venue.AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION
    )
    assert projection.matches_fact_transition(reconciliation, scope)
    assert projection.fact_relation() is not None

    result = acquisition.reduce_acquisition_controller(
        second.state,
        reconciliation,
        second.protection,
        second.authority,
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.execution is reconciliation.execution
    assert result.venue is reconciliation.book
    assert result.protection is not None
    assert result.protection.policy is (
        protection_fixtures._protection_module().ProtectionPolicy.HARD_BAIL
    )
    assert result.created_effect_id is None
    assert result.fresh_claim is None
    assert (
        acquisition.project_acquisition_controller(result.state).recovery_class
        is acquisition.AcquisitionRecoveryClass.RECONCILIATION_REQUIRED
    )
    generation_id = acquisition.project_acquisition_controller(
        result.state
    ).live_generation_id
    assert generation_id is not None
    record = result.state.registry.record(generation_id)
    assert record is not None
    assert (
        record.serving_class
        is acquisition.GenerationServingClass.RECONCILIATION_REQUIRED
    )
    assert result.state.lineage.route_fact(correction_key) is not None

    replay = acquisition.reduce_acquisition_controller(
        result.state,
        reconciliation,
        result.protection,
        result.authority,
    )
    assert replay.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert replay.state is result.state
    assert replay.created_effect_id is None
    assert replay.fresh_claim is None

    refresh = authority.refresh_acquisition_context(
        result.authority,
        result.execution,
        scope,
    )
    refused = acquisition.create_acquisition_effect(
        result.state,
        refresh,
        result.protection,
        acquisition.AcquisitionEffectTerms(
            quantity=authority_fixtures.Quantity(1),
            limit_price=authority_fixtures.PRICE,
            order_type=acquisition.AcquisitionOrderType.LIMIT,
            evaluation_time=2,
        ),
        authority.AuthorityInputId("wo0151-r11-reconciliation-create-refused"),
    )
    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.state is result.state
    assert refused.authority is refresh.authority
    assert refused.created_effect_id is None
    assert refused.fresh_claim is None


def _r11_completed_successor_fixture():
    """Build one closed generation A and initialized successor generation B."""

    authority, scope, claimed, filled = _r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    retired_stream_generation = (
        claimed.state._mandate.protection_mandate.evidence_policy.stream_generation
    )
    rooted = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert rooted.protection is not None
    relation = filled.book.project_acquisition_fact(filled).fact_relation()
    assert relation is not None
    bust = BrokerTradeBustFact(
        key=ExecutionFactKey(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            source_event_id=SourceEventId("wo0151-r11-completed-bust-source"),
        ),
        scope=ExecutionScope(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            order_id=relation.leg_key.order_id,
            symbol_id=scope.symbol_id,
            side=ExecutionSide.BUY,
        ),
        root_fill_id=relation.root_key.root_fill_id,
        predecessor_source_event_id=relation.fact_key.source_event_id,
        reported_price=authority_fixtures.PRICE,
    )
    busted = recovery_fixtures.apply_venue_recovery_input(
        filled.book,
        filled.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("wo0151-r11-completed-bust-input"),
            effect_id=relation.effect_id,
            leg_key=relation.leg_key,
            prior_root_quantity=authority_fixtures.Quantity(1),
            prior_venue_cumulative_quantity=authority_fixtures.Quantity(1),
            resulting_venue_cumulative_quantity=authority_fixtures.Quantity(0),
            fact=bust,
            evidence_digest=b"\xc4" * 32,
        ),
    )
    zero = acquisition.reduce_acquisition_controller(
        rooted.state,
        busted,
        rooted.protection,
        rooted.authority,
    )
    assert zero.protection is not None

    _, terminal = protection_fixtures._terminal_fixture(
        busted,
        effect_id=relation.effect_id,
        leg_key=relation.leg_key,
        label="wo0151-r11-completed",
        cumulative_quantity=1,
    )
    _, closed = protection_fixtures._close_parent_fixture(
        terminal,
        effect_id=relation.effect_id,
        label="wo0151-r11-completed",
    )
    protection = protection_fixtures._protection_module()
    raw = zero.protection
    for source in (terminal, closed):
        reduced = protection.reduce_position_protection(
            raw,
            protection.project_protection_venue(
                source,
                zero.state._mandate.protection_mandate,
            ),
        )
        assert reduced.disposition is protection.ProtectionDisposition.APPLIED
        raw = reduced.state
    assert raw.policy is protection.ProtectionPolicy.FLAT
    assert raw.raw_quantity == 0

    terminal_authority = copy(zero.authority)
    object.__setattr__(terminal_authority, "venue", closed.book)
    refresh = authority.refresh_acquisition_context(
        terminal_authority,
        closed.execution,
        scope,
    )
    assert refresh.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    bootstrap = terminal_authority.venue.project_acquisition_bootstrap(
        closed.execution,
        scope,
    )
    admission = authority.project_acquisition_admission(
        terminal_authority,
        closed.execution,
        scope,
    )
    assert admission.kind is authority.AcquisitionAdmissionKind.SUCCESSOR
    assert admission.permits_successor(
        authority_fixtures.GENERATION,
        closed.execution,
        scope,
    )
    prior_generation = zero.state._controller.live_generation_id
    successor = acquisition.begin_acquisition_generation(
        zero.state,
        _successor_mandate(zero.state._mandate, "r11-completed-successor"),
        bootstrap,
        admission,
        refresh,
        raw,
    )

    assert successor.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert successor.protection is None
    assert successor.state._controller.successor_ordinal == 1
    assert successor.state._controller.live_generation_id != prior_generation
    assert prior_generation is not None
    assert (
        successor.state.registry.record(prior_generation).serving_class
        is acquisition.GenerationServingClass.RETIRED_UNSERVING
    )
    return (
        authority,
        scope,
        relation,
        bust,
        successor,
        prior_generation,
        retired_stream_generation,
    )


def test_wo0151_r11_completed_generation_retires_into_fresh_successor() -> None:
    """A rooted, flat, exactly closed predecessor admits one new generation."""

    authority, scope, _, _, successor, _, _ = _r11_completed_successor_fixture()
    next_refresh = authority.refresh_acquisition_context(
        successor.authority,
        successor.execution,
        scope,
    )
    created = acquisition.create_acquisition_effect(
        successor.state,
        next_refresh,
        None,
        acquisition.AcquisitionEffectTerms(
            quantity=authority_fixtures.Quantity(1),
            limit_price=authority_fixtures.PRICE,
            order_type=acquisition.AcquisitionOrderType.LIMIT,
            evaluation_time=1,
        ),
        authority.AuthorityInputId("wo0151-r11-completed-successor-create"),
    )
    assert created.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert created.created_effect_id is not None


def test_wo0151_r12_retains_retired_stream_route_after_record_replacement() -> None:
    """A fact-replaced retired record cannot release its stream for reuse."""

    authority, scope, _, _, successor, retired_generation, retired_stream = (
        _r11_completed_successor_fixture()
    )
    retired_record = successor.state.registry.record(retired_generation)
    assert retired_record is not None
    assert retired_record.economics_head_commitment != (
        acquisition._initial_generation_economics_head(retired_record.binding)
    )
    retained_route = acquisition._registry_market_stream_route(
        successor.state.registry,
        retired_stream,
    )
    assert retained_route is not None
    assert retained_route.binding == retired_record.binding

    refresh = authority.refresh_acquisition_context(
        successor.authority,
        successor.execution,
        scope,
    )
    assert refresh.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    bootstrap = successor.venue.project_acquisition_bootstrap(
        successor.execution,
        scope,
    )
    admission = authority.project_acquisition_admission(
        successor.authority,
        successor.execution,
        scope,
    )
    assert admission.kind is authority.AcquisitionAdmissionKind.SUCCESSOR
    refused = acquisition.begin_acquisition_generation(
        successor.state,
        _successor_mandate(
            successor.state._mandate,
            "r12-replacement-retained-stream",
            stream_generation=retired_stream,
        ),
        bootstrap,
        admission,
        refresh,
        successor.protection,
    )

    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.state is successor.state
    assert refused.authority is successor.authority
    assert refused.execution is successor.execution
    assert refused.venue is successor.venue
    assert refused.protection is successor.protection
    assert refused.created_effect_id is None
    assert refused.fresh_claim is None
    assert refused._registration_receipt is None


def test_wo0151_r12_r1_rejects_route_pollution_during_record_replacement() -> None:
    """A retired route stays fail-closed even if a replacement pollutes it."""

    authority, scope, relation, _, successor, retired_generation, retired_stream = (
        _r11_completed_successor_fixture()
    )
    original = acquisition._registry_with_replaced_record
    retired_key = acquisition._market_stream_route_key(retired_stream)

    def _pollute_retired_route(registry: object, record: object) -> object:
        replaced = original(registry, record)
        assert record.binding.generation_id == retired_generation
        polluted_routes = replaced._market_stream_routes.replace_existing(
            retired_key,
            None,
            b"\x98" * 32,
        )
        polluted = object.__new__(acquisition.GenerationRegistry)
        object.__setattr__(polluted, "_records", replaced._records)
        object.__setattr__(polluted, "_market_stream_routes", polluted_routes)
        object.__setattr__(
            polluted,
            "_seal",
            acquisition._registry_seal(replaced._records, polluted_routes),
        )
        assert acquisition._registry_is_authentic(polluted)
        return polluted

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            acquisition,
            "_registry_with_replaced_record",
            _pollute_retired_route,
        )
        _, polluted = _apply_retired_fill(
            scope=scope,
            relation=relation,
            current=successor,
            label="wo0151-r12-r1-polluted-retired-fill",
            prior_cumulative_quantity=0,
        )
        with pytest.raises(ValueError, match="market stream route"):
            acquisition._registry_market_stream_route(
                polluted.state.registry,
                retired_stream,
            )

    _, restored = _apply_retired_fill(
        scope=scope,
        relation=relation,
        current=successor,
        label="wo0151-r12-r1-restored-retired-fill",
        prior_cumulative_quantity=0,
    )
    retained_route = acquisition._registry_market_stream_route(
        restored.state.registry,
        retired_stream,
    )
    assert retained_route is not None
    retired_record = restored.state.registry.record(retired_generation)
    assert retired_record is not None
    assert retained_route.binding == retired_record.binding


def _apply_retired_fill(
    *,
    scope: PositionScope,
    relation: object,
    current: object,
    label: str,
    prior_cumulative_quantity: int,
) -> tuple[BrokerFillFact, object]:
    """Apply and register one late retired-generation root through E2."""

    fact = BrokerFillFact(
        key=ExecutionFactKey(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            source_event_id=SourceEventId(f"{label}-source"),
        ),
        scope=ExecutionScope(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            order_id=relation.leg_key.order_id,
            symbol_id=scope.symbol_id,
            side=ExecutionSide.BUY,
        ),
        root_fill_id=RootFillId(f"{label}-root"),
        quantity=authority_fixtures.Quantity(1),
        price=authority_fixtures.PRICE,
    )
    transition = recovery_fixtures.apply_venue_recovery_input(
        current.authority.venue,
        current.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId(f"{label}-input"),
            effect_id=relation.effect_id,
            leg_key=relation.leg_key,
            prior_cumulative_quantity=authority_fixtures.Quantity(
                prior_cumulative_quantity
            ),
            resulting_cumulative_quantity=authority_fixtures.Quantity(
                prior_cumulative_quantity + 1
            ),
            fact=fact,
            evidence_digest=sha256(f"{label}-evidence".encode("ascii")).digest(),
            closure_id=ClosureId(f"{label}-closure"),
            evidence_reference=EvidenceReference(f"{label}-proof"),
        ),
    )
    assert transition.disposition is venue.VenueRecoveryDisposition.APPLIED
    result = acquisition.reduce_acquisition_controller(
        current.state,
        transition,
        current.protection,
        current.authority,
    )
    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.protection is not None
    assert result.protection.policy is (
        protection_fixtures._protection_module().ProtectionPolicy.HARD_BAIL
    )
    return fact, result


def test_wo0151_r11_late_retired_fact_recovers_without_serving_retired_a() -> None:
    """A late direct A fact updates A while B remains the only live generation."""

    authority, scope, relation, _, successor, retired_generation, _ = (
        _r11_completed_successor_fixture()
    )
    late_fill = BrokerFillFact(
        key=ExecutionFactKey(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            source_event_id=SourceEventId("wo0151-r11-retired-fill-source"),
        ),
        scope=ExecutionScope(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            order_id=relation.leg_key.order_id,
            symbol_id=scope.symbol_id,
            side=ExecutionSide.BUY,
        ),
        root_fill_id=RootFillId("wo0151-r11-retired-late-root"),
        quantity=authority_fixtures.Quantity(1),
        price=authority_fixtures.PRICE,
    )
    corrected = recovery_fixtures.apply_venue_recovery_input(
        successor.authority.venue,
        successor.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("wo0151-r11-retired-fill-input"),
            effect_id=relation.effect_id,
            leg_key=relation.leg_key,
            prior_cumulative_quantity=authority_fixtures.Quantity(0),
            resulting_cumulative_quantity=authority_fixtures.Quantity(1),
            fact=late_fill,
            evidence_digest=b"\xc5" * 32,
            closure_id=ClosureId("wo0151-r11-retired-fill-closure"),
            evidence_reference=EvidenceReference("wo0151-r11-retired-fill-proof"),
        ),
    )
    live_generation = successor.state._controller.live_generation_id
    before_live = successor.state.registry.record(live_generation)
    before_retired = successor.state.registry.record(retired_generation)

    result = acquisition.reduce_acquisition_controller(
        successor.state,
        corrected,
        None,
        successor.authority,
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.protection is not None
    assert result.protection.policy is (
        protection_fixtures._protection_module().ProtectionPolicy.HARD_BAIL
    )
    assert result.state._controller.live_generation_id == live_generation
    assert result.state._controller.recovery_class is (
        acquisition.AcquisitionRecoveryClass.MIXED_GENERATION_RECOVERY
    )
    assert result.state.registry.record(live_generation) is before_live
    after_retired = result.state.registry.record(retired_generation)
    assert after_retired is not None and before_retired is not None
    assert (
        after_retired.serving_class
        is acquisition.GenerationServingClass.RETIRED_UNSERVING
    )
    assert (
        after_retired.economics_head_commitment
        != before_retired.economics_head_commitment
    )
    assert (
        result.state.lineage.route_fact(late_fill.key).generation_id
        == retired_generation
    )
    assert result.created_effect_id is None
    assert result.fresh_claim is None
    assert result._registration_receipt is not None
    assert (
        result._registration_receipt.operation
        is authority.AcquisitionAuthorityOperation.REGISTER
    )


def test_wo0151_r11_retired_correct_reexpands_tombstone_once() -> None:
    """A late correction of retired A updates only A and replays inertly."""

    authority, scope, relation, bust, successor, retired_generation, _ = (
        _r11_completed_successor_fixture()
    )
    correction_key = ExecutionFactKey(
        broker=scope.broker,
        environment=scope.environment,
        account=scope.account,
        source_event_id=SourceEventId("wo0151-r11-retired-correct-source"),
    )
    correction = BrokerTradeCorrectFact(
        key=correction_key,
        scope=ExecutionScope(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            order_id=relation.leg_key.order_id,
            symbol_id=scope.symbol_id,
            side=ExecutionSide.BUY,
        ),
        root_fill_id=relation.root_key.root_fill_id,
        predecessor_source_event_id=bust.key.source_event_id,
        revised_quantity=authority_fixtures.Quantity(1),
        revised_price=authority_fixtures.PRICE,
    )
    corrected = recovery_fixtures.apply_venue_recovery_input(
        successor.authority.venue,
        successor.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("wo0151-r11-retired-correct-input"),
            effect_id=relation.effect_id,
            leg_key=relation.leg_key,
            prior_root_quantity=authority_fixtures.Quantity(0),
            prior_venue_cumulative_quantity=authority_fixtures.Quantity(0),
            resulting_venue_cumulative_quantity=authority_fixtures.Quantity(1),
            fact=correction,
            evidence_digest=b"\xd3" * 32,
            closure_id=ClosureId("wo0151-r11-retired-correct-closure"),
            evidence_reference=EvidenceReference("wo0151-r11-retired-correct-proof"),
        ),
    )
    assert corrected.disposition is venue.VenueRecoveryDisposition.APPLIED
    before = successor.state.registry.record(retired_generation)
    assert before is not None

    result = acquisition.reduce_acquisition_controller(
        successor.state,
        corrected,
        None,
        successor.authority,
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.protection is not None
    assert (
        result.protection.policy
        is protection_fixtures._protection_module().ProtectionPolicy.HARD_BAIL
    )
    assert result.state._controller.live_generation_id != retired_generation
    after = result.state.registry.record(retired_generation)
    assert after is not None
    assert after.serving_class is acquisition.GenerationServingClass.RETIRED_UNSERVING
    assert after.economics_head_commitment != before.economics_head_commitment
    route = result.state.lineage.route_fact(correction_key)
    assert route is not None and route.generation_id == retired_generation
    assert result.created_effect_id is None
    assert result.fresh_claim is None

    replay = acquisition.reduce_acquisition_controller(
        result.state,
        corrected,
        result.protection,
        result.authority,
    )
    assert (
        replay.disposition is acquisition.AcquisitionControllerDisposition.EXACT_REPLAY
    )
    assert replay.state is result.state
    assert replay.created_effect_id is None
    assert replay.fresh_claim is None


def test_wo0151_r11_retired_tail_bust_updates_once_and_replays_inertly() -> None:
    """A late retired root and its tail bust each advance A exactly once."""

    _, scope, relation, _, successor, retired_generation, _ = (
        _r11_completed_successor_fixture()
    )
    late_fill, rooted = _apply_retired_fill(
        scope=scope,
        relation=relation,
        current=successor,
        label="wo0151-r11-retired-tail-bust-fill",
        prior_cumulative_quantity=0,
    )
    before = rooted.state.registry.record(retired_generation)
    assert before is not None
    bust_key = ExecutionFactKey(
        broker=scope.broker,
        environment=scope.environment,
        account=scope.account,
        source_event_id=SourceEventId("wo0151-r11-retired-tail-bust-source"),
    )
    bust = BrokerTradeBustFact(
        key=bust_key,
        scope=late_fill.scope,
        root_fill_id=late_fill.root_fill_id,
        predecessor_source_event_id=late_fill.key.source_event_id,
        reported_price=authority_fixtures.PRICE,
    )
    busted = recovery_fixtures.apply_venue_recovery_input(
        rooted.authority.venue,
        rooted.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("wo0151-r11-retired-tail-bust-input"),
            effect_id=relation.effect_id,
            leg_key=relation.leg_key,
            prior_root_quantity=authority_fixtures.Quantity(1),
            prior_venue_cumulative_quantity=authority_fixtures.Quantity(1),
            resulting_venue_cumulative_quantity=authority_fixtures.Quantity(0),
            fact=bust,
            evidence_digest=b"\xd4" * 32,
            closure_id=ClosureId("wo0151-r11-retired-tail-bust-closure"),
            evidence_reference=EvidenceReference("wo0151-r11-retired-tail-bust-proof"),
        ),
    )
    assert busted.disposition is venue.VenueRecoveryDisposition.APPLIED

    result = acquisition.reduce_acquisition_controller(
        rooted.state,
        busted,
        rooted.protection,
        rooted.authority,
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.protection is not None
    assert result.protection.policy is (
        protection_fixtures._protection_module().ProtectionPolicy.HARD_BAIL
    )
    after = result.state.registry.record(retired_generation)
    assert after is not None
    assert after.economics_head_commitment != before.economics_head_commitment
    route = result.state.lineage.route_fact(bust_key)
    assert route is not None and route.generation_id == retired_generation
    assert result.created_effect_id is None
    assert result.fresh_claim is None
    replay = acquisition.reduce_acquisition_controller(
        result.state,
        busted,
        result.protection,
        result.authority,
    )
    assert (
        replay.disposition is acquisition.AcquisitionControllerDisposition.EXACT_REPLAY
    )
    assert replay.state is result.state


def test_wo0151_r11_retired_non_tail_bust_is_reconciliation_only() -> None:
    """A retired non-tail bust is recorded once and cannot restore BUY service."""

    authority, scope, relation, _, successor, retired_generation, _ = (
        _r11_completed_successor_fixture()
    )
    first_fill, first = _apply_retired_fill(
        scope=scope,
        relation=relation,
        current=successor,
        label="wo0151-r11-retired-reconciliation-first",
        prior_cumulative_quantity=0,
    )
    _, second = _apply_retired_fill(
        scope=scope,
        relation=relation,
        current=first,
        label="wo0151-r11-retired-reconciliation-second",
        prior_cumulative_quantity=1,
    )
    before = second.state.registry.record(retired_generation)
    assert before is not None
    bust_key = ExecutionFactKey(
        broker=scope.broker,
        environment=scope.environment,
        account=scope.account,
        source_event_id=SourceEventId("wo0151-r11-retired-reconciliation-bust-source"),
    )
    bust = BrokerTradeBustFact(
        key=bust_key,
        scope=first_fill.scope,
        root_fill_id=first_fill.root_fill_id,
        predecessor_source_event_id=first_fill.key.source_event_id,
        reported_price=authority_fixtures.PRICE,
    )
    reconciliation = recovery_fixtures.apply_venue_recovery_input(
        second.authority.venue,
        second.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("wo0151-r11-retired-reconciliation-bust-input"),
            effect_id=relation.effect_id,
            leg_key=relation.leg_key,
            prior_root_quantity=authority_fixtures.Quantity(1),
            prior_venue_cumulative_quantity=authority_fixtures.Quantity(2),
            resulting_venue_cumulative_quantity=authority_fixtures.Quantity(1),
            fact=bust,
            evidence_digest=b"\xd5" * 32,
            closure_id=ClosureId("wo0151-r11-retired-reconciliation-bust-closure"),
            evidence_reference=EvidenceReference(
                "wo0151-r11-retired-reconciliation-bust-proof"
            ),
        ),
    )
    assert (
        reconciliation.disposition
        is venue.VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    )

    result = acquisition.reduce_acquisition_controller(
        second.state,
        reconciliation,
        second.protection,
        second.authority,
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.protection is not None
    assert result.protection.policy is (
        protection_fixtures._protection_module().ProtectionPolicy.HARD_BAIL
    )
    assert result.state._controller.recovery_class is (
        acquisition.AcquisitionRecoveryClass.MIXED_GENERATION_RECONCILIATION_REQUIRED
    )
    after = result.state.registry.record(retired_generation)
    assert after is not None
    assert after.economics_head_commitment != before.economics_head_commitment
    assert after.serving_class is acquisition.GenerationServingClass.RETIRED_UNSERVING
    route = result.state.lineage.route_fact(bust_key)
    assert route is not None and route.generation_id == retired_generation
    assert result.created_effect_id is None
    assert result.fresh_claim is None

    replay = acquisition.reduce_acquisition_controller(
        result.state,
        reconciliation,
        result.protection,
        result.authority,
    )
    assert (
        replay.disposition is acquisition.AcquisitionControllerDisposition.EXACT_REPLAY
    )
    assert replay.state is result.state
    assert replay.created_effect_id is None
    assert replay.fresh_claim is None

    refresh = authority.refresh_acquisition_context(
        result.authority,
        result.execution,
        scope,
    )
    refused = acquisition.create_acquisition_effect(
        result.state,
        refresh,
        result.protection,
        acquisition.AcquisitionEffectTerms(
            quantity=authority_fixtures.Quantity(1),
            limit_price=authority_fixtures.PRICE,
            order_type=acquisition.AcquisitionOrderType.LIMIT,
            evaluation_time=3,
        ),
        authority.AuthorityInputId("wo0151-r11-retired-reconciliation-create"),
    )
    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.created_effect_id is None
    assert refused.fresh_claim is None


def test_wo0151_r11_r1_retired_fact_preempts_successor_in_one_receipt() -> None:
    """A late A fact and B stand-down are one ordered authority mutation."""

    authority, scope, relation, _, successor, retired_generation, _ = (
        _r11_completed_successor_fixture()
    )
    create_refresh = authority.refresh_acquisition_context(
        successor.authority,
        successor.execution,
        scope,
    )
    created = acquisition.create_acquisition_effect(
        successor.state,
        create_refresh,
        None,
        acquisition.AcquisitionEffectTerms(
            quantity=authority_fixtures.Quantity(1),
            limit_price=authority_fixtures.PRICE,
            order_type=acquisition.AcquisitionOrderType.LIMIT,
            evaluation_time=1,
        ),
        authority.AuthorityInputId("wo0151-r11-r1-successor-create"),
    )
    assert created.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert created.created_effect_id is not None
    stale_claim_refresh = authority.refresh_acquisition_context(
        created.authority,
        created.execution,
        scope,
    )
    late_fill = BrokerFillFact(
        key=ExecutionFactKey(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            source_event_id=SourceEventId("wo0151-r11-r1-raced-fill-source"),
        ),
        scope=ExecutionScope(
            broker=scope.broker,
            environment=scope.environment,
            account=scope.account,
            order_id=relation.leg_key.order_id,
            symbol_id=scope.symbol_id,
            side=ExecutionSide.BUY,
        ),
        root_fill_id=RootFillId("wo0151-r11-r1-raced-fill-root"),
        quantity=authority_fixtures.Quantity(1),
        price=authority_fixtures.PRICE,
    )
    fact_transition = recovery_fixtures.apply_venue_recovery_input(
        created.authority.venue,
        created.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("wo0151-r11-r1-raced-fill-input"),
            effect_id=relation.effect_id,
            leg_key=relation.leg_key,
            prior_cumulative_quantity=authority_fixtures.Quantity(0),
            resulting_cumulative_quantity=authority_fixtures.Quantity(1),
            fact=late_fill,
            evidence_digest=b"\xc6" * 32,
            closure_id=ClosureId("wo0151-r11-r1-raced-fill-closure"),
            evidence_reference=EvidenceReference("wo0151-r11-r1-raced-fill-proof"),
        ),
    )

    result = acquisition.reduce_acquisition_controller(
        created.state,
        fact_transition,
        None,
        created.authority,
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.protection is not None
    assert not result.protection.waiting_buy_resolution
    assert result._registration_receipt is not None
    assert (
        result._registration_receipt.operation
        is authority.AcquisitionAuthorityOperation.PREEMPT
    )
    assert (
        result.state._controller.live_generation_id
        == created.state._controller.live_generation_id
    )
    retired = result.state.registry.record(retired_generation)
    assert retired is not None
    assert retired.serving_class is acquisition.GenerationServingClass.RETIRED_UNSERVING
    assert (
        result.state.lineage.route_fact(late_fill.key).generation_id
        == retired_generation
    )
    assert result.fresh_claim is None
    assert len(result._registration_receipt.ordered_venue_transition_commitments) <= 3

    stale_claim = acquisition.claim_acquisition_effect(
        result.state,
        stale_claim_refresh,
        result.protection,
        created.created_effect_id,
        authority.ClaimOccurrenceId("wo0151-r11-r1-stale-claim"),
        authority.AuthorityInputId("wo0151-r11-r1-stale-claim-input"),
    )
    assert (
        stale_claim.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    )
    assert stale_claim.fresh_claim is None


def test_wo0151_r11_abnormal_first_root_is_retained_and_non_buy_serving() -> None:
    """An authentic overfill becomes conservative state, never stale E2."""

    authority, _, claimed, filled = _r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
        fill_quantity=6,
    )
    result = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.execution.position.raw_quantity == 6
    assert result.protection is not None
    assert (
        result.protection.policy
        is protection_fixtures._protection_module().ProtectionPolicy.HARD_BAIL
    )
    assert result.state.protection_commitment is not None
    assert result.created_effect_id is None
    assert result.fresh_claim is None


def test_wo0151_r11_r1_current_waiting_buy_stages_one_bounded_cancel() -> None:
    """A protection-owned preemption need can only cancel the exact current BUY."""

    authority, scope, current, _ = _r11_waiting_preemption_fixture()
    refresh = authority.refresh_acquisition_context(
        current.authority,
        current.execution,
        scope,
    )
    assert refresh.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    before = acquisition.project_acquisition_controller(current.state)

    result = acquisition.begin_acquisition_preemption(
        current.state,
        refresh,
        current.protection,
        authority.AuthorityInputId("wo0151-r11-r1-current-preempt"),
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.created_effect_id is not None
    assert result.fresh_claim is None
    assert result.protection is not current.protection
    assert result.protection is not None
    assert result.protection.policy is current.protection.policy
    assert result.protection.waiting_buy_resolution
    assert result.protection.commitment != current.protection.commitment
    after = acquisition.project_acquisition_controller(result.state)
    assert after.controller_head != before.controller_head
    assert after.successor_ordinal == before.successor_ordinal
    assert after.live_generation_id == before.live_generation_id
    assert result._registration_receipt is not None
    assert (
        result._registration_receipt.operation
        is authority.AcquisitionAuthorityOperation.PREEMPT
    )
    assert len(result._registration_receipt.ordered_venue_transition_commitments) == 1

    replay_refresh = authority.refresh_acquisition_context(
        result.authority,
        result.execution,
        scope,
    )
    replay = acquisition.begin_acquisition_preemption(
        result.state,
        replay_refresh,
        result.protection,
        authority.AuthorityInputId("wo0151-r11-r1-current-preempt"),
    )
    assert replay.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert replay.state is result.state
    assert replay.authority is result.authority
    assert replay.created_effect_id is None
    assert replay.fresh_claim is None


def test_wo0151_r11_r1_preemption_rechecks_the_owner_intent_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale protection-owned intent cannot ride a current authority handoff."""

    authority, scope, current, _ = _r11_waiting_preemption_fixture()
    refresh = authority.refresh_acquisition_context(
        current.authority,
        current.execution,
        scope,
    )
    assert refresh.venue_context is not None
    context = (
        protection_fixtures._protection_module().project_acquisition_protection_context(
            current.protection,
            current.authority.venue,
            current.execution,
            refresh.venue_context,
        )
    )
    assert context is not None
    intent = (
        protection_fixtures._protection_module()._project_acquisition_preemption_intent(
            current.protection,
            context,
        )
    )
    assert intent is not None
    forged = copy(intent)
    object.__setattr__(forged, "context_commitment", b"\x92" * 32)
    assert not forged.matches_current(current.protection, context)
    monkeypatch.setattr(
        acquisition,
        "_project_acquisition_preemption_intent",
        lambda _state, _context: forged,
    )

    refused = acquisition.begin_acquisition_preemption(
        current.state,
        refresh,
        current.protection,
        authority.AuthorityInputId("wo0151-r11-r1-stale-owner-intent"),
    )

    assert refused.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert refused.state is current.state
    assert refused.authority is current.authority
    assert refused.created_effect_id is None


def test_wo0151_r11_r1_preemption_enforces_the_one_cancel_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An overproducing authority helper stops before recording controller state."""

    authority, scope, current, _ = _r11_waiting_preemption_fixture()
    refresh = authority.refresh_acquisition_context(
        current.authority,
        current.execution,
        scope,
    )
    original = authority._authority_begin_symbol_flatten

    def duplicate_cancel(*args: object, **kwargs: object):
        produced = original(*args, **kwargs)
        assert produced is not None
        next_venue, effect_ids, transitions = produced
        assert len(effect_ids) == 1
        return next_venue, effect_ids + effect_ids, transitions

    monkeypatch.setattr(
        authority,
        "_authority_begin_symbol_flatten",
        duplicate_cancel,
    )

    with pytest.raises(RuntimeError, match="one-cancel cap"):
        acquisition.begin_acquisition_preemption(
            current.state,
            refresh,
            current.protection,
            authority.AuthorityInputId("wo0151-r11-r1-two-cancel-mutant"),
        )


def test_wo0151_r11_r1_goal_owned_protection_exit_is_single_flight() -> None:
    """Only the fresh protection-owned goal may create one bounded SELL."""

    authority, scope, current, released, next_authority, refresh = (
        _r11_protection_exit_fixture()
    )

    result = acquisition.create_acquisition_protection_exit(
        current.state,
        refresh,
        copy(released.state),
        released,
        authority.AuthorityInputId("wo0151-r11-r1-protection-exit"),
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.created_effect_id is not None
    assert result.fresh_claim is None
    assert result.protection is not None
    assert result.protection.raw_quantity == released.state.raw_quantity
    assert not result.protection.waiting_buy_resolution
    assert result._registration_receipt is not None
    assert result._registration_receipt.operation is (
        authority.AcquisitionAuthorityOperation.PROTECTION_EXIT
    )
    assert len(result._registration_receipt.ordered_venue_transition_commitments) == 1
    effect = result.venue.effect(result.created_effect_id)
    assert effect is not None
    assert effect.scope.side is ExecutionSide.SELL
    assert effect.scope.quantity.value == result.execution.position.raw_quantity
    assert (
        effect.scope.mandate_id == current.state._mandate.protection_mandate.mandate_id
    )
    assert result.authority is not next_authority

    replay_refresh = authority.refresh_acquisition_context(
        result.authority,
        result.execution,
        scope,
    )
    replay = acquisition.create_acquisition_protection_exit(
        result.state,
        replay_refresh,
        result.protection,
        released,
        authority.AuthorityInputId("wo0151-r11-r1-protection-exit"),
    )
    assert replay.disposition is acquisition.AcquisitionControllerDisposition.REFUSED
    assert replay.state is result.state
    assert replay.authority is result.authority
    assert replay.created_effect_id is None
    assert replay.fresh_claim is None


def test_wo0151_e2_identity_primitives_are_exact_and_input_validated() -> None:
    """The two E2 identity domains remain simple exact values, not authority."""

    mandate = AcquisitionMandateId("acquisition-mandate-a")
    compatibility = EmergencyRecoveryCompatibilityId("emergency-compatibility-a")

    assert mandate.value == "acquisition-mandate-a"
    assert compatibility.value == "emergency-compatibility-a"
    assert type(mandate) is AcquisitionMandateId
    assert type(compatibility) is EmergencyRecoveryCompatibilityId

    for identity_type in (
        AcquisitionMandateId,
        EmergencyRecoveryCompatibilityId,
    ):
        with pytest.raises(TypeError):
            identity_type(1)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            identity_type("   ")


def test_wo0151_controller_surface_is_explicit_opaque_and_refresh_owned() -> None:
    """E2 composes sealed inputs; it must not grow an implicit action surface."""

    required_names = (
        "AcquisitionOrderType",
        "AcquisitionEffectTerms",
        "DualMandateBinding",
        "AcquisitionMandate",
        "AcquisitionControllerDisposition",
        "AcquisitionRecoveryClass",
        "SymbolAcquisitionController",
        "AcquisitionControllerState",
        "AcquisitionControllerStatus",
        "AcquisitionControllerTransition",
        "initialize_acquisition_controller",
        "begin_acquisition_generation",
        "reduce_acquisition_controller",
        "rebase_acquisition_protection",
        "create_acquisition_effect",
        "claim_acquisition_effect",
        "begin_acquisition_preemption",
        "create_acquisition_protection_exit",
        "project_acquisition_controller",
    )
    missing = tuple(name for name in required_names if not hasattr(acquisition, name))
    assert not missing, f"missing WO-0151 acquisition API: {missing!r}"

    assert tuple(member.value for member in acquisition.AcquisitionOrderType) == (
        "LIMIT",
    )
    assert tuple(
        member.value for member in acquisition.AcquisitionControllerDisposition
    ) == (
        "APPLIED",
        "EXACT_REPLAY",
        "REFUSED",
    )
    assert {
        acquisition.AcquisitionRecoveryClass.NORMAL,
        acquisition.AcquisitionRecoveryClass.RECONCILIATION_REQUIRED,
        acquisition.AcquisitionRecoveryClass.MIXED_GENERATION_RECOVERY,
        acquisition.AcquisitionRecoveryClass.MIXED_GENERATION_RECONCILIATION_REQUIRED,
    } <= set(acquisition.AcquisitionRecoveryClass)

    expected_signatures = {
        "initialize_acquisition_controller": (
            "application_generation_id",
            "mandate",
            "bootstrap",
            "admission",
            "refresh",
            "protection",
        ),
        "begin_acquisition_generation": (
            "state",
            "successor_mandate",
            "bootstrap",
            "admission",
            "refresh",
            "protection",
        ),
        "reduce_acquisition_controller": (
            "state",
            "transition",
            "protection",
            "authority",
        ),
        "rebase_acquisition_protection": ("state", "refresh", "source"),
        "create_acquisition_effect": (
            "state",
            "refresh",
            "protection",
            "terms",
            "input_id",
        ),
        "claim_acquisition_effect": (
            "state",
            "refresh",
            "protection",
            "effect_id",
            "claim_occurrence_id",
            "input_id",
        ),
        "begin_acquisition_preemption": (
            "state",
            "refresh",
            "protection",
            "input_id",
        ),
        "create_acquisition_protection_exit": (
            "state",
            "refresh",
            "protection",
            "transition",
            "input_id",
        ),
        "project_acquisition_controller": ("state",),
    }
    for name, expected in expected_signatures.items():
        assert (
            tuple(inspect.signature(getattr(acquisition, name)).parameters) == expected
        )

    for opaque_type in (
        acquisition.DualMandateBinding,
        acquisition.SymbolAcquisitionController,
        acquisition.AcquisitionControllerState,
        acquisition.AcquisitionControllerTransition,
    ):
        with pytest.raises(TypeError):
            opaque_type()
        with pytest.raises(TypeError):
            type(f"Forged{opaque_type.__name__}", (opaque_type,), {})


def test_wo0151_acquisition_owner_authenticates_every_retained_state_field() -> None:
    _, _, claimed, filled = _r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    applied = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert applied.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    state = applied.state
    controller = state._controller
    mandate = state._mandate
    projection = filled.book.project_acquisition_fact(filled)
    relation = projection.fact_relation()
    assert relation is not None
    route = state.lineage.route_effect(relation.effect_id)
    assert route is not None
    assert controller.live_generation_id is not None
    record = state.registry.record(controller.live_generation_id)
    assert record is not None

    cases = (
        (mandate.binding, acquisition._dual_mandate_binding_is_authentic),
        (mandate, acquisition._acquisition_mandate_is_authentic),
        (record.binding, acquisition._generation_binding_view_is_authentic),
        (record, acquisition._generation_record_is_authentic),
        (state.registry, acquisition._registry_is_authentic),
        (route, acquisition._generation_route_is_authentic),
        (state.lineage, acquisition._lineage_is_authentic),
        (controller, acquisition._controller_is_authentic),
        (state, acquisition._controller_state_is_authentic),
    )
    for value, checker in cases:
        _assert_every_retained_field_is_authenticated(value, checker)


def test_wo0151_authority_owner_authenticates_every_retained_e2_field() -> None:
    authority, scope, created = _r8_created_first_effect()
    assert created.created_effect_id is not None
    scope_key = authority._acquisition_scope_key(
        created.state.application_generation_id,
        scope,
    )
    effect_key = authority._effect_key(created.created_effect_id)
    entry = created.authority._acquisition_currentness_by_scope.get(scope_key)
    descriptor = created.authority._acquisition_descriptor_by_effect.get(effect_key)
    active = created.authority._acquisition_active_by_scope.get(scope_key)
    assert entry is not None
    assert descriptor is not None
    assert active is not None

    refresh = authority.refresh_acquisition_context(
        created.authority,
        created.execution,
        scope,
    )
    assert refresh.venue_context is not None
    context = authority.project_acquisition_authority_context(
        created.authority,
        created.execution,
        refresh.venue_context,
    )
    admission = authority.project_acquisition_admission(
        created.authority,
        created.execution,
        scope,
    )
    _, _, claimed = _r8_claimed_first_effect()
    assert claimed.fresh_claim is not None

    base_permit = descriptor.permit
    next_controller_head = sha256(
        b"wo0151-owner-boundary-exit" + base_permit.controller_head
    ).digest()
    exit_permit = authority._new_acquisition_exit_permit(
        input_id=authority.AuthorityInputId("wo0151-owner-boundary-exit"),
        purpose=authority._AcquisitionExitPurpose.PREEMPT_BUY_ONLY,
        application_generation_id=base_permit.application_generation_id,
        position_scope=base_permit.position_scope,
        session_id=base_permit.session_id,
        generation_id=base_permit.generation_id,
        acquisition_mandate_id=base_permit.acquisition_mandate_id,
        protection_mandate_id=base_permit.protection_mandate_id,
        binding_commitment=base_permit.binding_commitment,
        emergency_recovery_compatibility_commitment=(
            base_permit.emergency_recovery_compatibility_commitment
        ),
        predecessor_controller_head=base_permit.controller_head,
        controller_head=next_controller_head,
        successor_ordinal=base_permit.successor_ordinal,
        execution_snapshot_commitment=base_permit.execution_snapshot_commitment,
        scope_execution_commitment=base_permit.scope_execution_commitment,
        venue_commitment=base_permit.venue_commitment,
        authority_context_commitment=base_permit.authority_context_commitment,
        predecessor_protection_commitment=base_permit.protection_commitment,
        protection_commitment=_commitment("wo0151-owner-boundary-protection"),
        residual_quantity=base_permit.terms.quantity,
        target_effect_id=base_permit.effect_id,
        protective_request=None,
        intent_commitment=_commitment("wo0151-owner-boundary-intent"),
    )
    successor_generation_id = acquisition._derive_acquisition_generation_id(
        base_permit.application_generation_id,
        base_permit.position_scope,
        base_permit.successor_ordinal + 1,
        base_permit.binding_commitment,
        base_permit.controller_head,
        base_permit.emergency_recovery_compatibility_commitment,
    )
    inactive = authority._new_acquisition_inactive_slot(
        active,
        descriptor,
        successor_generation_id,
    )
    _, _, _, fact_transition = _r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    fact_projection = fact_transition.book.project_acquisition_fact(fact_transition)
    fact_preemption = authority._new_acquisition_fact_preemption(
        input_id=exit_permit.input_id,
        permit=exit_permit,
        fact_transition=fact_transition,
        fact_projection=fact_projection,
    )

    def refresh_matches_live(value: object) -> bool:
        return bool(
            type(value) is authority.AcquisitionContextRefresh
            and value.matches_current(
                created.authority,
                created.state.application_generation_id,
                scope,
            )
        )

    cases = (
        (entry, authority._acquisition_currentness_entry_is_authentic),
        (context, authority._acquisition_authority_context_is_authentic),
        (descriptor.permit.terms, authority._acquisition_effect_terms_is_authentic),
        (descriptor.permit, authority._acquisition_effect_permit_is_authentic),
        (descriptor, authority._acquisition_effect_descriptor_is_authentic),
        (active, authority._acquisition_active_effect_is_authentic),
        (inactive, authority._acquisition_inactive_slot_is_authentic),
        (exit_permit, authority._acquisition_exit_permit_is_authentic),
        (claimed.fresh_claim, authority._acquisition_claim_receipt_is_authentic),
    )
    for value, checker in cases:
        _assert_every_retained_field_is_authenticated(value, checker)
    _assert_every_retained_field_is_authenticated(
        refresh,
        refresh_matches_live,
        type_only_fields=frozenset({"predecessor_venue_context"}),
    )
    _assert_every_retained_field_is_authenticated(
        admission,
        authority._acquisition_admission_is_authentic,
        type_only_fields=frozenset({"_authority", "_execution", "_venue_context"}),
    )
    _assert_every_retained_field_is_authenticated(
        fact_preemption,
        authority._acquisition_fact_preemption_is_authentic,
        type_only_fields=frozenset({"permit", "_fact_transition", "_fact_projection"}),
    )


def test_wo0151_protection_owner_authenticates_every_acquisition_field() -> None:
    (
        authority,
        scope,
        applied,
        _,
        predecessor_context,
        rebase_projection,
    ) = _r10_semantic_rebase_fixture()
    protection = protection_fixtures._protection_module()
    assert applied.protection is not None
    compatibility = (
        applied.state._mandate.protection_mandate.emergency_recovery_compatibility
    )

    _, _, waiting, _ = _r11_waiting_preemption_fixture()
    assert waiting.protection is not None
    waiting_refresh = authority.refresh_acquisition_context(
        waiting.authority,
        waiting.execution,
        scope,
    )
    assert waiting_refresh.venue_context is not None
    waiting_context = protection.project_acquisition_protection_context(
        waiting.protection,
        waiting.venue,
        waiting.execution,
        waiting_refresh.venue_context,
    )
    assert waiting_context is not None
    preemption_intent = protection._project_acquisition_preemption_intent(
        waiting.protection,
        waiting_context,
    )
    assert preemption_intent is not None

    _, _, _, released, next_authority, exit_refresh = _r11_protection_exit_fixture()
    assert exit_refresh.venue_context is not None
    exit_context = protection.project_acquisition_protection_context(
        released.state,
        next_authority.venue,
        exit_refresh.execution,
        exit_refresh.venue_context,
    )
    assert exit_context is not None
    exit_intent = protection._project_acquisition_protection_exit_intent(
        released,
        exit_context,
    )
    assert exit_intent is not None

    cases = (
        (compatibility, protection._emergency_recovery_compatibility_is_authentic),
        (applied.protection, protection._state_is_authentic),
        (predecessor_context, protection._acquisition_protection_context_is_authentic),
        (
            rebase_projection,
            protection._acquisition_protection_rebase_projection_is_authentic,
        ),
        (released._source_projection, protection._projection_is_authentic),
        (released, protection._protection_transition_is_authentic),
        (preemption_intent, protection._acquisition_preemption_intent_is_authentic),
        (
            exit_intent,
            protection._acquisition_protection_exit_intent_is_authentic,
        ),
    )
    for value, checker in cases:
        _assert_every_retained_field_is_authenticated(value, checker)


def test_wo0151_venue_owner_authenticates_every_acquisition_fact_field() -> None:
    _, scope, _, filled = _r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    context = filled.book.project_acquisition_context(filled.execution, scope)
    projection = filled.book.project_acquisition_fact(filled)
    relation = projection.fact_relation()
    assert relation is not None
    proof = filled._acquisition_fact_proof
    assert proof is not None
    protection_proof = filled._protection_proof

    _, bootstrap_scope, initialized = _r8_initialized_controller()
    active_bootstrap = initialized.authority.venue._bootstrap_bound_target_record(
        bootstrap_scope
    )
    assert active_bootstrap is not None
    _, _, created = _r8_created_first_effect()
    consumed_bootstrap = created.authority.venue._bootstrap_bound_target_by_scope.get(
        venue._position_scope_index_key(bootstrap_scope)
    )
    assert consumed_bootstrap is not None

    cases = (
        (context, venue._acquisition_venue_context_is_authentic),
        (projection, venue._acquisition_venue_projection_is_authentic),
        (relation, venue._acquisition_fact_relation_is_authentic),
        (protection_proof, venue._protection_transition_proof_is_authentic),
        (active_bootstrap, venue._bootstrap_bound_target_record_is_authentic),
        (
            consumed_bootstrap,
            venue._consumed_bootstrap_bound_target_record_is_authentic,
        ),
    )
    for value, checker in cases:
        _assert_every_retained_field_is_authenticated(value, checker)


def test_wo0151_owner_minted_boundaries_reject_direct_construction() -> None:
    authority = authority_fixtures._authority_module()
    protection = protection_fixtures._protection_module()
    constructor_blocked = (
        acquisition.GenerationBindingView,
        acquisition.GenerationRecordView,
        acquisition.GenerationRouteView,
        acquisition._MarketStreamGenerationRoute,
        acquisition.GenerationRegistry,
        acquisition.AcquisitionLineageIndex,
        acquisition.DualMandateBinding,
        acquisition.SymbolAcquisitionController,
        acquisition.AcquisitionControllerState,
        acquisition.AcquisitionControllerStatus,
        acquisition.AcquisitionControllerTransition,
        authority._RegisterAcquisitionCurrentness,
        authority.RegisterAcquisitionCurrentness,
        authority.ExecutionAuthorityState,
        authority.AcquisitionAuthorityContext,
        authority.AcquisitionAdmissionProjection,
        authority._AcquisitionCurrentnessEntry,
        authority.AcquisitionContextRefresh,
        authority._AcquisitionCurrentnessRegistration,
        authority._CanonicalFactCurrentnessRegistration,
        authority._ProtectionRebaseCurrentnessRegistration,
        authority.AcquisitionAuthorityReceipt,
        authority.AcquisitionClaimReceipt,
        authority.AcquisitionEffectPermit,
        authority.AcquisitionClaimPermit,
        authority.AcquisitionExitPermit,
        authority._AcquisitionFactPreemption,
        authority._AcquisitionEffectDescriptor,
        authority._AcquisitionActiveEffect,
        authority._AcquisitionInactiveSlot,
        authority.AcquisitionEffectView,
        protection.PositionProtectionState,
        protection.ProtectionVenueProjection,
        protection.ProtectionTransition,
        protection.AcquisitionMixedRecoveryProof,
        protection.AcquisitionProtectionContext,
        protection.AcquisitionProtectionRebaseProjection,
        protection._AcquisitionPreemptionIntent,
        protection._AcquisitionProtectionExitIntent,
        venue.VenueAcquisitionCorrelation,
        venue.AcquisitionFactRelation,
        venue.AcquisitionVenueContext,
        venue.AcquisitionVenueProjection,
        venue.VenueRecoveryTransition,
        venue._BootstrapTargetRegistryInput,
        venue._BootstrapBoundTargetRecord,
        venue._StagedBootstrapBoundTargetRecord,
        venue._ConsumedBootstrapBoundTargetRecord,
        venue.VenueRecoveryBook,
        venue._BootstrapPromotionPermit,
    )
    for value_type in constructor_blocked:
        with pytest.raises(TypeError):
            value_type()

    subclass_blocked = tuple(
        value_type
        for value_type in constructor_blocked
        if "__init_subclass__" in vars(value_type)
    )
    assert subclass_blocked
    for value_type in subclass_blocked:
        with pytest.raises(TypeError):
            type(f"Forged{value_type.__name__}", (value_type,), {})


def test_identity_known_answers_replay_and_well_formed_variants_are_data_only() -> None:
    genesis = acquisition._acquisition_controller_genesis_head(_APP, _SCOPE)
    actual = _generation_id()

    assert (
        actual.value
        == "a3a7378c87ce9b0fe2a544d1cccdbe53da28693b66ab127f10df0848223f931a"
    )
    assert actual == acquisition._derive_acquisition_generation_id(
        _APP,
        _SCOPE,
        0,
        _commitment("dual-a"),
        genesis,
        _commitment("compatibility"),
    )

    successor = acquisition._derive_acquisition_generation_id(
        _APP,
        _SCOPE,
        1,
        _commitment("dual-a"),
        _commitment("controller-successor"),
        _commitment("compatibility"),
    )
    assert (
        successor.value
        == "b3054715237a8855dc0194ab9684de0958d5069d753a427aaab2d578fd7cfad8"
    )
    assert successor == acquisition._derive_acquisition_generation_id(
        _APP,
        _SCOPE,
        1,
        _commitment("dual-a"),
        _commitment("controller-successor"),
        _commitment("compatibility"),
    )

    variants = (
        acquisition._derive_acquisition_generation_id(
            ApplicationGenerationId("reset-app-1"),
            _SCOPE,
            0,
            _commitment("dual-a"),
            genesis,
            _commitment("compatibility"),
        ),
        acquisition._derive_acquisition_generation_id(
            _APP,
            PositionScope(
                broker=_BROKER,
                environment=_ENVIRONMENT,
                account=_ACCOUNT,
                symbol_id=SymbolId("MSFT"),
            ),
            0,
            _commitment("dual-a"),
            genesis,
            _commitment("compatibility"),
        ),
        acquisition._derive_acquisition_generation_id(
            _APP,
            _SCOPE,
            1,
            _commitment("dual-a"),
            genesis,
            _commitment("compatibility"),
        ),
        acquisition._derive_acquisition_generation_id(
            _APP,
            _SCOPE,
            0,
            _commitment("dual-b"),
            genesis,
            _commitment("compatibility"),
        ),
        acquisition._derive_acquisition_generation_id(
            _APP,
            _SCOPE,
            0,
            _commitment("dual-a"),
            _commitment("well-formed-but-not-admitted"),
            _commitment("compatibility"),
        ),
        acquisition._derive_acquisition_generation_id(
            _APP,
            _SCOPE,
            0,
            _commitment("dual-a"),
            genesis,
            _commitment("different-compatibility"),
        ),
    )
    assert all(variant != actual for variant in variants)
    assert all(
        acquisition._acquisition_generation_id_is_canonical(variant)
        for variant in variants
    )


@pytest.mark.parametrize("ordinal", [True, False, -1, 2**64])
def test_identity_refuses_noncanonical_ordinal_without_wrap(ordinal: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        acquisition._derive_acquisition_generation_id(
            _APP,
            _SCOPE,
            ordinal,
            _commitment("dual-a"),
            acquisition._acquisition_controller_genesis_head(_APP, _SCOPE),
            _commitment("compatibility"),
        )


@pytest.mark.parametrize(
    "coordinate",
    [
        "dual_mandate_binding_commitment",
        "predecessor_or_genesis_head_commitment",
        "emergency_recovery_compatibility_commitment",
    ],
)
@pytest.mark.parametrize("bad_commitment", [b"", b"x" * 31, b"x" * 33, "not-bytes"])
def test_identity_refuses_noncanonical_commitments(
    coordinate: str,
    bad_commitment: object,
) -> None:
    dual_mandate_binding_commitment = _commitment("dual-a")
    predecessor_or_genesis_head_commitment = (
        acquisition._acquisition_controller_genesis_head(_APP, _SCOPE)
    )
    emergency_recovery_compatibility_commitment = _commitment("compatibility")
    if coordinate == "dual_mandate_binding_commitment":
        dual_mandate_binding_commitment = bad_commitment
    elif coordinate == "predecessor_or_genesis_head_commitment":
        predecessor_or_genesis_head_commitment = bad_commitment
    else:
        emergency_recovery_compatibility_commitment = bad_commitment

    with pytest.raises((TypeError, ValueError)):
        acquisition._derive_acquisition_generation_id(
            _APP,
            _SCOPE,
            0,
            dual_mandate_binding_commitment,
            predecessor_or_genesis_head_commitment,
            emergency_recovery_compatibility_commitment,
        )


def test_identity_requires_exact_application_and_scope_coordinate_types() -> None:
    application_subclass = type("ApplicationSubclass", (ApplicationGenerationId,), {})(
        "reset-app-subclass"
    )
    scope_subclass = type("PositionScopeSubclass", (PositionScope,), {})(
        broker=_BROKER,
        environment=_ENVIRONMENT,
        account=_ACCOUNT,
        symbol_id=SymbolId("AAPL"),
    )
    genesis = acquisition._acquisition_controller_genesis_head(_APP, _SCOPE)

    for application_generation_id, position_scope in (
        (application_subclass, _SCOPE),
        (_APP, scope_subclass),
    ):
        with pytest.raises(TypeError):
            acquisition._derive_acquisition_generation_id(
                application_generation_id,
                position_scope,
                0,
                _commitment("dual-a"),
                genesis,
                _commitment("compatibility"),
            )


def test_public_surface_is_opaque_inert_and_exactly_additive_at_root() -> None:
    expected_acquisition_exports = {
        "AcquisitionControllerDisposition",
        "AcquisitionControllerState",
        "AcquisitionControllerStatus",
        "AcquisitionControllerTransition",
        "AcquisitionEffectTerms",
        "AcquisitionLineageIndex",
        "AcquisitionMandate",
        "AcquisitionOrderType",
        "AcquisitionRecoveryClass",
        "DualMandateBinding",
        "GenerationServingClass",
        "GenerationRouteKind",
        "GenerationBindingView",
        "GenerationRecordView",
        "GenerationRouteView",
        "GenerationRegistry",
        "SymbolAcquisitionController",
        "begin_acquisition_generation",
        "begin_acquisition_preemption",
        "claim_acquisition_effect",
        "create_acquisition_effect",
        "create_acquisition_protection_exit",
        "initialize_acquisition_controller",
        "project_acquisition_controller",
        "rebase_acquisition_protection",
        "reduce_acquisition_controller",
    }
    expected_root_delta = expected_acquisition_exports | {
        "AcquisitionGenerationId",
        "AcquisitionMandateId",
        "EmergencyRecoveryCompatibilityId",
        "VenueAcquisitionCorrelation",
    }

    assert set(acquisition.__all__) == expected_acquisition_exports
    assert expected_root_delta <= set(kernel.__all__)
    assert AcquisitionGenerationId("a" * 64).value == "a" * 64
    with pytest.raises(ValueError):
        AcquisitionGenerationId("A" * 64)

    for view in (
        acquisition.GenerationBindingView,
        acquisition.GenerationRecordView,
        acquisition.GenerationRouteView,
        acquisition.DualMandateBinding,
        acquisition.SymbolAcquisitionController,
        acquisition.AcquisitionControllerState,
        acquisition.AcquisitionControllerStatus,
        acquisition.AcquisitionControllerTransition,
        VenueAcquisitionCorrelation,
    ):
        assert is_dataclass(view)
        assert all(
            field.name.startswith("_") or field.init is False for field in fields(view)
        )
        with pytest.raises(TypeError):
            view()
        with pytest.raises(TypeError):
            type("Substitute", (view,), {})

    expected_methods = {
        acquisition.GenerationRegistry: {"empty", "record"},
        acquisition.AcquisitionLineageIndex: {
            "empty",
            "route_request",
            "route_effect",
            "route_owner",
            "route_root",
            "route_fact",
        },
    }
    for container, public_methods in expected_methods.items():
        exposed = {
            name
            for name, value in vars(container).items()
            if not name.startswith("_")
            and (callable(value) or isinstance(value, classmethod))
        }
        assert exposed == public_methods
        assert not {
            "__iter__",
            "__len__",
            "__getitem__",
            "items",
            "keys",
            "values",
        } & set(vars(container))


def test_empty_readers_are_nonconstructable_and_never_infer_state() -> None:
    registry = acquisition.GenerationRegistry.empty()
    index = acquisition.AcquisitionLineageIndex.empty()
    generation_id = _generation_id()

    assert type(registry) is acquisition.GenerationRegistry
    assert type(index) is acquisition.AcquisitionLineageIndex
    with pytest.raises(TypeError):
        acquisition.GenerationRegistry()
    with pytest.raises(TypeError):
        acquisition.AcquisitionLineageIndex()
    with pytest.raises(FrozenInstanceError):
        registry._seal = b"forged"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        index._seal = b"forged"  # type: ignore[misc]

    assert registry.record(generation_id) is None
    assert index.route_request(_request("missing")) is None
    assert index.route_effect(_effect("missing")) is None
    assert index.route_owner(_leg("missing")) is None
    assert index.route_root(_root("missing")) is None
    assert index.route_fact(_fact("missing")) is None

    malformed_calls = (
        lambda: registry.record("not-a-generation"),
        lambda: index.route_request("not-a-request"),
        lambda: index.route_effect("not-an-effect"),
        lambda: index.route_owner("not-a-leg"),
        lambda: index.route_root("not-a-root"),
        lambda: index.route_fact("not-a-fact"),
    )
    for call in malformed_calls:
        with pytest.raises(TypeError):
            call()

    # Raw, well-formed data never creates a record, route, or serving state.
    assert registry.record(AcquisitionGenerationId(generation_id.value)) is None
    assert index.route_root(_root("same-account-same-symbol")) is None
    forged = object.__new__(AcquisitionGenerationId)
    assert not acquisition._acquisition_generation_id_is_canonical(forged)
    with pytest.raises(TypeError):
        registry.record(forged)
    forged_registry = object.__new__(acquisition.GenerationRegistry)
    forged_index = object.__new__(acquisition.AcquisitionLineageIndex)
    with pytest.raises(ValueError):
        forged_registry.record(generation_id)
    forged_readers = (
        lambda: forged_index.route_request(_request("forged-container")),
        lambda: forged_index.route_effect(_effect("forged-container")),
        lambda: forged_index.route_owner(_leg("forged-container")),
        lambda: forged_index.route_root(_root("forged-container")),
        lambda: forged_index.route_fact(_fact("forged-container")),
    )
    for reader in forged_readers:
        with pytest.raises(ValueError):
            reader()


def _direct_and_human_correlated_books() -> tuple[
    object,
    object,
    object,
    object,
]:
    book, execution = recovery_fixtures._seed_needs_review()
    broker_fact = recovery_fixtures._broker_fill(
        "e1-direct-broker-source",
        "e1-direct-broker-root",
        quantity=2,
    )
    direct = recovery_fixtures.apply_venue_recovery_input(
        book,
        execution,
        RecordBrokerFillEvidence(
            input_id=recovery_fixtures.VenueInputId("e1-direct-broker-input"),
            effect_id=recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_A,
            prior_cumulative_quantity=recovery_fixtures.Quantity(0),
            resulting_cumulative_quantity=recovery_fixtures.Quantity(2),
            fact=broker_fact,
            evidence_digest=b"\xa1" * 32,
        ),
    )
    assert direct.disposition is recovery_fixtures.VenueRecoveryDisposition.APPLIED

    attested_book, attested_execution = recovery_fixtures._seed_needs_review()
    attested = recovery_fixtures._ingest(
        attested_book,
        attested_execution,
        recovery_fixtures._human_fill(),
    )
    correlated_fact = recovery_fixtures._broker_fill(
        "e1-human-broker-source",
        "e1-human-broker-root",
        quantity=4,
    )
    corroborated = recovery_fixtures.apply_venue_recovery_input(
        attested.book,
        attested.execution,
        RecordBrokerFillEvidence(
            input_id=recovery_fixtures.VenueInputId("e1-human-broker-input"),
            effect_id=recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_A,
            prior_cumulative_quantity=recovery_fixtures.Quantity(0),
            resulting_cumulative_quantity=recovery_fixtures.Quantity(4),
            fact=correlated_fact,
            evidence_digest=b"\xa2" * 32,
        ),
    )
    assert (
        corroborated.disposition is recovery_fixtures.VenueRecoveryDisposition.APPLIED
    )
    return direct, broker_fact, corroborated, correlated_fact


def test_venue_correlation_is_direct_immutable_and_has_no_history_fallback() -> None:
    direct, broker_fact, corroborated, correlated_fact = (
        _direct_and_human_correlated_books()
    )

    def _forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "E1 correlation materialized an audit or effective-state view"
        )

    audit_properties = (
        "effects",
        "owners",
        "closure_history",
        "input_records",
        "human_coverages",
        "broker_coverages",
    )
    with patch.object(VenueRecoveryBook, "_current_effect", _forbidden):
        with pytest.MonkeyPatch.context() as monkeypatch:
            for name in audit_properties:
                monkeypatch.setattr(VenueRecoveryBook, name, property(_forbidden))
            direct_correlation = direct.book.acquisition_correlation(
                recovery_fixtures.REQUEST,
                recovery_fixtures.EFFECT,
                root_key=broker_fact.root_key,
            )
            corroborated_correlation = corroborated.book.acquisition_correlation(
                recovery_fixtures.REQUEST,
                recovery_fixtures.EFFECT,
                root_key=correlated_fact.root_key,
            )
            leg_only_correlation = direct.book.acquisition_correlation(
                recovery_fixtures.REQUEST,
                recovery_fixtures.EFFECT,
                leg_key=recovery_fixtures.LEG_A,
            )

    for correlation, root_key, commitment, seal in (
        (
            direct_correlation,
            broker_fact.root_key,
            "073b1315b749391c8a3d75fa863df3bef0c13089b08985ab6fe1eb82684de882",
            "2f8ab4d3e5a4225eb60cb9a83fcaa13293589d93c4812e55b54bb4aeff2fdda3",
        ),
        (
            corroborated_correlation,
            correlated_fact.root_key,
            "27a698edfd5fbe776c07aa8b703aa0a9e8e77eb5534e5e8314ed34f7efff9c2a",
            "310d8bdccc924509b6424f3a2122e90be1ca2ddb0681c66a2ce86123b0eb3dfd",
        ),
    ):
        assert correlation is not None
        assert correlation.application_generation_id == recovery_fixtures.GENERATION
        assert correlation.position_scope == recovery_fixtures.POSITION_SCOPE
        assert correlation.request_occurrence_id == recovery_fixtures.REQUEST
        assert correlation.effect_id == recovery_fixtures.EFFECT
        assert correlation.leg_key == recovery_fixtures.LEG_A
        assert correlation.root_key == root_key
        assert correlation.correlation_commitment.hex() == commitment
        assert correlation._seal.hex() == seal
        with pytest.raises(FrozenInstanceError):
            correlation.effect_id = EffectId("forged")  # type: ignore[misc]

    assert leg_only_correlation is not None
    assert leg_only_correlation.leg_key == recovery_fixtures.LEG_A
    assert leg_only_correlation.root_key is None
    assert (
        leg_only_correlation.correlation_commitment.hex()
        == "6471076d25bc09d0f1d5b43ef0b58e8a6ccb2659969174cf659088ba590ace33"
    )
    assert (
        leg_only_correlation._seal.hex()
        == "184e58ad05e8ad7c4d4c3a4d4ee6771beaf5e34e88be91cb1d89ff2fbb894572"
    )
    with pytest.raises(TypeError):
        VenueAcquisitionCorrelation()
    with pytest.raises(TypeError):
        type("ForgedVenueAcquisitionCorrelation", (VenueAcquisitionCorrelation,), {})

    # Slow audit hydration may rebuild its retained direct index, but must preserve
    # the same current-book projection for ordinary and corroborated-human roots.
    for transition, correlation, root_key in (
        (direct, direct_correlation, broker_fact.root_key),
        (corroborated, corroborated_correlation, correlated_fact.root_key),
    ):
        hydrated = recovery_fixtures._audit_hydrate_book(
            transition.book,
            transition.execution,
        )
        assert (
            hydrated.acquisition_correlation(
                recovery_fixtures.REQUEST,
                recovery_fixtures.EFFECT,
                root_key=root_key,
            )
            == correlation
        )

    # At least one owner-bearing selector is mandatory; no implicit relation exists.
    assert (
        direct.book.acquisition_correlation(
            recovery_fixtures.REQUEST,
            recovery_fixtures.EFFECT,
        )
        is None
    )
    assert (
        direct.book.acquisition_correlation(
            recovery_fixtures.REQUEST,
            EffectId("wrong-effect"),
            root_key=broker_fact.root_key,
        )
        is None
    )
    assert (
        corroborated.book.acquisition_correlation(
            recovery_fixtures.REQUEST,
            recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_B,
            root_key=correlated_fact.root_key,
        )
        is None
    )


def test_venue_correlation_refuses_same_account_different_symbol_claim() -> None:
    book, execution = recovery_fixtures._seed_needs_review(capacity=4)
    other_symbol = SymbolId("MSFT")
    other_scope = PositionScope(
        broker=recovery_fixtures.BROKER,
        environment=recovery_fixtures.ENVIRONMENT,
        account=recovery_fixtures.ACCOUNT,
        symbol_id=other_symbol,
    )
    other_execution = recovery_fixtures.ExecutionSnapshot.bind_verified(
        recovery_fixtures.PositionState.flat(other_scope),
        recovery_fixtures.PositionIntegrity.CONSISTENT,
        recovery_fixtures.RootHeadIndex.empty(other_scope),
        execution.seen_facts,
    )
    other_effect = EffectId("effect-submit-msft")
    registered = recovery_fixtures.apply_venue_recovery_input(
        book,
        other_execution,
        recovery_fixtures.RequestedEffect(
            input_id=recovery_fixtures.VenueInputId("request-msft-effect"),
            effect_id=other_effect,
            request_occurrence_id=RequestOccurrenceId("request-msft"),
            mandate_id=recovery_fixtures.MandateId("mandate-msft"),
            kind=recovery_fixtures.EffectKind.SUBMIT,
            client_order_id=recovery_fixtures.ClientOrderId("client-msft"),
            symbol_id=other_symbol,
            side=recovery_fixtures.ExecutionSide.BUY,
            quantity=recovery_fixtures.Quantity(4),
            economic_scope=b"MSFT|BUY|four",
        ),
    )
    assert registered.disposition is recovery_fixtures.VenueRecoveryDisposition.APPLIED

    aapl_fact = recovery_fixtures._broker_fill(
        "aapl-cross-symbol-source",
        "aapl-cross-symbol-root",
        quantity=2,
    )
    aapl_fill = recovery_fixtures.apply_venue_recovery_input(
        registered.book,
        execution,
        RecordBrokerFillEvidence(
            input_id=recovery_fixtures.VenueInputId("aapl-fill-after-msft-register"),
            effect_id=recovery_fixtures.EFFECT,
            leg_key=recovery_fixtures.LEG_A,
            prior_cumulative_quantity=recovery_fixtures.Quantity(0),
            resulting_cumulative_quantity=recovery_fixtures.Quantity(2),
            fact=aapl_fact,
            evidence_digest=b"\xa0" * 32,
        ),
    )
    assert aapl_fill.disposition is recovery_fixtures.VenueRecoveryDisposition.APPLIED
    assert (
        aapl_fill.book.acquisition_correlation(
            recovery_fixtures.REQUEST,
            recovery_fixtures.EFFECT,
            root_key=aapl_fact.root_key,
        )
        is not None
    )
    assert (
        aapl_fill.book.acquisition_correlation(
            RequestOccurrenceId("request-msft"),
            other_effect,
            root_key=aapl_fact.root_key,
        )
        is None
    )


def test_venue_correlation_has_no_raw_factory_and_one_checked_construction_site() -> (
    None
):
    path = Path(venue.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    top_level_functions = {
        declaration.name
        for declaration in tree.body
        if isinstance(declaration, ast.FunctionDef)
    }
    constructors = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "object"
        and node.func.attr == "__new__"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "VenueAcquisitionCorrelation"
    ]

    assert "_make_acquisition_correlation" not in top_level_functions
    assert len(constructors) == 1
    constructor = constructors[0]
    method = next(
        (
            parent
            for parent in ast.walk(tree)
            if isinstance(parent, ast.FunctionDef) and constructor in ast.walk(parent)
        ),
        None,
    )
    assert method is not None and method.name == "acquisition_correlation"
    owner = parents.get(method)
    assert isinstance(owner, ast.ClassDef) and owner.name == "VenueRecoveryBook"

    app_root = path.parents[1]
    consumers: list[str] = []
    for candidate in sorted(app_root.rglob("*.py")):
        if candidate == path:
            continue
        candidate_tree = ast.parse(
            candidate.read_text(encoding="utf-8"), filename=str(candidate)
        )
        for function in (
            node
            for node in ast.walk(candidate_tree)
            if isinstance(node, ast.FunctionDef)
        ):
            annotations = [
                function.returns,
                *(
                    argument.annotation
                    for argument in (
                        *function.args.posonlyargs,
                        *function.args.args,
                        *function.args.kwonlyargs,
                    )
                ),
            ]
            if any(
                isinstance(annotation, ast.Name)
                and annotation.id == "VenueAcquisitionCorrelation"
                for annotation in annotations
                if annotation is not None
            ):
                consumers.append(f"{candidate}:{function.lineno}:{function.name}")
    assert consumers == []
