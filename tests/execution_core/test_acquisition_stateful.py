"""WO-0152 E3 behavior-first, public-contract acquisition conformance.

This module owns only test evidence.  The narrow setup exceptions below model
deferred environment and adapter composition; every acquisition operation after
that boundary uses the public execution-core contracts.
"""

from __future__ import annotations

import copy
from decimal import Decimal
from fractions import Fraction

import app.execution_core as kernel
import app.execution_core.acquisition as acquisition
import app.execution_core.authority as authority


_APPLICATION = kernel.ApplicationGenerationId("wo0152-e3-application")
_BROKER = kernel.BrokerId("wo0152-e3-broker")
_ENVIRONMENT = kernel.EnvironmentId("paper")
_ACCOUNT = kernel.AccountId("wo0152-e3-account")
_TARGET_SCOPE = kernel.PositionScope(
    broker=_BROKER,
    environment=_ENVIRONMENT,
    account=_ACCOUNT,
    symbol_id=kernel.SymbolId("AAPL"),
)
_OTHER_SCOPE = kernel.PositionScope(
    broker=_BROKER,
    environment=_ENVIRONMENT,
    account=_ACCOUNT,
    symbol_id=kernel.SymbolId("MSFT"),
)
_VENUE_SCOPE = kernel.VenueScope(
    generation=_APPLICATION,
    broker=_BROKER,
    environment=_ENVIRONMENT,
    account=_ACCOUNT,
)
_PRICE_SCALE = kernel.PriceScale(Decimal("1"))
_PRICE = kernel.ReportedPrice(
    units=kernel.PriceUnits(100),
    scale=_PRICE_SCALE,
    tick=kernel.TickMetadata(
        tick_units=kernel.PriceUnits(1),
        scale=_PRICE_SCALE,
    ),
)
_OTHER_LEG = kernel.VenueLegKey(
    broker=_BROKER,
    environment=_ENVIRONMENT,
    account=_ACCOUNT,
    order_id=kernel.OrderId("wo0152-e3-other-leg"),
)
_E3_SESSION = kernel.SessionId("wo0152-e3-serving-session")
_E3_NORMAL_GUARD = kernel.ExecutionGuard(
    guard_id="wo0152-e3-normal-guard",
    policy_commitment=b"\x31" * 32,
)
_E3_EMERGENCY_GUARD = kernel.ExecutionGuard(
    guard_id="wo0152-e3-emergency-guard",
    policy_commitment=b"\x32" * 32,
)
_E3_MARKET_SOURCE = kernel.MarketDataSourceId("wo0152-e3-market-source")
_E3_COMPATIBILITY = kernel.EmergencyRecoveryCompatibility(
    compatibility_id=kernel.EmergencyRecoveryCompatibilityId("wo0152-e3-compatibility"),
    position_scope=_TARGET_SCOPE,
    session_id=_E3_SESSION,
    configuration_version="wo0152-e3-emergency-v1",
    configuration_commitment=b"\x33" * 32,
    emergency_guard=_E3_EMERGENCY_GUARD,
    maximum_goal_rate=4,
    emergency_effect_budget=0,
    deadline=1_000,
    aggregate_emergency_quantity=kernel.Quantity(5),
)
_E3_FIXED_MANDATE_SCHEDULE = (
    (
        "A",
        "wo0152-e3-acquisition-A",
        "wo0152-e3-protection-A",
        "0000000000000000000000000000000000000000000000000000000000000001",
    ),
    (
        "B",
        "wo0152-e3-acquisition-B",
        "wo0152-e3-protection-B",
        "0000000000000000000000000000000000000000000000000000000000000002",
    ),
    (
        "C",
        "wo0152-e3-acquisition-C",
        "wo0152-e3-protection-C",
        "0000000000000000000000000000000000000000000000000000000000000003",
    ),
    (
        "D",
        "wo0152-e3-acquisition-D",
        "wo0152-e3-protection-D",
        "0000000000000000000000000000000000000000000000000000000000000004",
    ),
    (
        "E",
        "wo0152-e3-acquisition-E",
        "wo0152-e3-protection-E",
        "0000000000000000000000000000000000000000000000000000000000000005",
    ),
    (
        "F",
        "wo0152-e3-acquisition-F",
        "wo0152-e3-protection-F",
        "0000000000000000000000000000000000000000000000000000000000000006",
    ),
    (
        "G",
        "wo0152-e3-acquisition-G",
        "wo0152-e3-protection-G",
        "0000000000000000000000000000000000000000000000000000000000000007",
    ),
    (
        "H",
        "wo0152-e3-acquisition-H",
        "wo0152-e3-protection-H",
        "0000000000000000000000000000000000000000000000000000000000000008",
    ),
    (
        "I",
        "wo0152-e3-acquisition-I",
        "wo0152-e3-protection-I",
        "0000000000000000000000000000000000000000000000000000000000000009",
    ),
    (
        "J",
        "wo0152-e3-acquisition-J",
        "wo0152-e3-protection-J",
        "000000000000000000000000000000000000000000000000000000000000000a",
    ),
    (
        "K",
        "wo0152-e3-acquisition-K",
        "wo0152-e3-protection-K",
        "000000000000000000000000000000000000000000000000000000000000000b",
    ),
    (
        "L",
        "wo0152-e3-acquisition-L",
        "wo0152-e3-protection-L",
        "000000000000000000000000000000000000000000000000000000000000000c",
    ),
    (
        "M",
        "wo0152-e3-acquisition-M",
        "wo0152-e3-protection-M",
        "000000000000000000000000000000000000000000000000000000000000000d",
    ),
    (
        "N",
        "wo0152-e3-acquisition-N",
        "wo0152-e3-protection-N",
        "000000000000000000000000000000000000000000000000000000000000000e",
    ),
    (
        "O",
        "wo0152-e3-acquisition-O",
        "wo0152-e3-protection-O",
        "000000000000000000000000000000000000000000000000000000000000000f",
    ),
    (
        "P",
        "wo0152-e3-acquisition-P",
        "wo0152-e3-protection-P",
        "0000000000000000000000000000000000000000000000000000000000000010",
    ),
    (
        "Q",
        "wo0152-e3-acquisition-Q",
        "wo0152-e3-protection-Q",
        "0000000000000000000000000000000000000000000000000000000000000011",
    ),
    (
        "R",
        "wo0152-e3-acquisition-R",
        "wo0152-e3-protection-R",
        "0000000000000000000000000000000000000000000000000000000000000012",
    ),
    (
        "S",
        "wo0152-e3-acquisition-S",
        "wo0152-e3-protection-S",
        "0000000000000000000000000000000000000000000000000000000000000013",
    ),
    (
        "T",
        "wo0152-e3-acquisition-T",
        "wo0152-e3-protection-T",
        "0000000000000000000000000000000000000000000000000000000000000014",
    ),
    (
        "U",
        "wo0152-e3-acquisition-U",
        "wo0152-e3-protection-U",
        "0000000000000000000000000000000000000000000000000000000000000015",
    ),
    (
        "V",
        "wo0152-e3-acquisition-V",
        "wo0152-e3-protection-V",
        "0000000000000000000000000000000000000000000000000000000000000016",
    ),
    (
        "W",
        "wo0152-e3-acquisition-W",
        "wo0152-e3-protection-W",
        "0000000000000000000000000000000000000000000000000000000000000017",
    ),
    (
        "X",
        "wo0152-e3-acquisition-X",
        "wo0152-e3-protection-X",
        "0000000000000000000000000000000000000000000000000000000000000018",
    ),
    (
        "Y",
        "wo0152-e3-acquisition-Y",
        "wo0152-e3-protection-Y",
        "0000000000000000000000000000000000000000000000000000000000000019",
    ),
    (
        "Z",
        "wo0152-e3-acquisition-Z",
        "wo0152-e3-protection-Z",
        "000000000000000000000000000000000000000000000000000000000000001a",
    ),
    (
        "AA",
        "wo0152-e3-acquisition-AA",
        "wo0152-e3-protection-AA",
        "000000000000000000000000000000000000000000000000000000000000001b",
    ),
    (
        "AB",
        "wo0152-e3-acquisition-AB",
        "wo0152-e3-protection-AB",
        "000000000000000000000000000000000000000000000000000000000000001c",
    ),
    (
        "AC",
        "wo0152-e3-acquisition-AC",
        "wo0152-e3-protection-AC",
        "000000000000000000000000000000000000000000000000000000000000001d",
    ),
    (
        "AD",
        "wo0152-e3-acquisition-AD",
        "wo0152-e3-protection-AD",
        "000000000000000000000000000000000000000000000000000000000000001e",
    ),
    (
        "AE",
        "wo0152-e3-acquisition-AE",
        "wo0152-e3-protection-AE",
        "000000000000000000000000000000000000000000000000000000000000001f",
    ),
    (
        "AF",
        "wo0152-e3-acquisition-AF",
        "wo0152-e3-protection-AF",
        "0000000000000000000000000000000000000000000000000000000000000020",
    ),
)
_E3_FIXED_DUPLICATE_STREAM_PROBE = (
    "PROBE",
    "wo0152-e3-acquisition-probe",
    "wo0152-e3-protection-probe",
    "0000000000000000000000000000000000000000000000000000000000000001",
)


def _approved_acquisition_mandates_fixture() -> tuple[kernel.AcquisitionMandate, ...]:
    """Build the sole fixed, pre-genesis positive mandate schedule."""

    mandates: list[kernel.AcquisitionMandate] = []
    for (
        _,
        acquisition_id_text,
        protection_id_text,
        stream_generation_text,
    ) in _E3_FIXED_MANDATE_SCHEDULE:
        acquisition_id = kernel.AcquisitionMandateId(acquisition_id_text)
        protection = kernel.ProtectionMandate(
            mandate_id=kernel.MandateId(protection_id_text),
            position_scope=_TARGET_SCOPE,
            session_id=_E3_SESSION,
            configuration_version="wo0152-e3-protection-v1",
            loss_fraction=Fraction(1, 20),
            approved_gain=Fraction(1, 10),
            percent_trail_fraction=Fraction(1, 20),
            atr_multiple=Fraction(5, 2),
            tick=_PRICE.tick,
            normal_guard=_E3_NORMAL_GUARD,
            emergency_guard=_E3_EMERGENCY_GUARD,
            evidence_policy=kernel.EvidencePolicy(
                source_id=_E3_MARKET_SOURCE,
                stream_generation=kernel.MarketStreamGenerationId(
                    stream_generation_text
                ),
                sequence_mode=kernel.MarketSequenceMode.SEQUENCED,
                max_age=10,
                corroboration_window=10,
                max_step_fraction=Fraction(1, 2),
            ),
            maximum_quantity=kernel.Quantity(5),
            maximum_goal_rate=4,
            deadline=1_000,
            emergency_recovery_compatibility=_E3_COMPATIBILITY,
        )
        binding = acquisition._mint_dual_mandate_binding(
            acquisition_mandate_id=acquisition_id,
            position_scope=_TARGET_SCOPE,
            session_id=_E3_SESSION,
            configuration_version="wo0152-e3-acquisition-v1",
            maximum_quantity=kernel.Quantity(5),
            maximum_notional=Fraction(1_000),
            maximum_entry_price=_PRICE,
            allowed_order_types=(kernel.AcquisitionOrderType.LIMIT,),
            expiry=1_000,
            deadline=900,
            fixed_child_cap=kernel.Quantity(1),
            certified_participation_cap=Fraction(1, 2),
            cancel_reprice_budget=2,
            protection_mandate=protection,
        )
        mandates.append(
            kernel.AcquisitionMandate(
                acquisition_mandate_id=acquisition_id,
                position_scope=_TARGET_SCOPE,
                session_id=_E3_SESSION,
                configuration_version="wo0152-e3-acquisition-v1",
                maximum_quantity=kernel.Quantity(5),
                maximum_notional=Fraction(1_000),
                maximum_entry_price=_PRICE,
                allowed_order_types=(kernel.AcquisitionOrderType.LIMIT,),
                expiry=1_000,
                deadline=900,
                fixed_child_cap=kernel.Quantity(1),
                certified_participation_cap=Fraction(1, 2),
                cancel_reprice_budget=2,
                protection_mandate=protection,
                binding=binding,
            )
        )
    return tuple(mandates)


def _nonadjacent_duplicate_stream_probe_mandate_fixture() -> kernel.AcquisitionMandate:
    """Build the one isolated, otherwise-valid A-stream negative probe."""

    _, acquisition_id_text, protection_id_text, stream_generation_text = (
        _E3_FIXED_DUPLICATE_STREAM_PROBE
    )
    acquisition_id = kernel.AcquisitionMandateId(acquisition_id_text)
    protection = kernel.ProtectionMandate(
        mandate_id=kernel.MandateId(protection_id_text),
        position_scope=_TARGET_SCOPE,
        session_id=_E3_SESSION,
        configuration_version="wo0152-e3-protection-v1",
        loss_fraction=Fraction(1, 20),
        approved_gain=Fraction(1, 10),
        percent_trail_fraction=Fraction(1, 20),
        atr_multiple=Fraction(5, 2),
        tick=_PRICE.tick,
        normal_guard=_E3_NORMAL_GUARD,
        emergency_guard=_E3_EMERGENCY_GUARD,
        evidence_policy=kernel.EvidencePolicy(
            source_id=_E3_MARKET_SOURCE,
            stream_generation=kernel.MarketStreamGenerationId(stream_generation_text),
            sequence_mode=kernel.MarketSequenceMode.SEQUENCED,
            max_age=10,
            corroboration_window=10,
            max_step_fraction=Fraction(1, 2),
        ),
        maximum_quantity=kernel.Quantity(5),
        maximum_goal_rate=4,
        deadline=1_000,
        emergency_recovery_compatibility=_E3_COMPATIBILITY,
    )
    binding = acquisition._mint_dual_mandate_binding(
        acquisition_mandate_id=acquisition_id,
        position_scope=_TARGET_SCOPE,
        session_id=_E3_SESSION,
        configuration_version="wo0152-e3-acquisition-v1",
        maximum_quantity=kernel.Quantity(5),
        maximum_notional=Fraction(1_000),
        maximum_entry_price=_PRICE,
        allowed_order_types=(kernel.AcquisitionOrderType.LIMIT,),
        expiry=1_000,
        deadline=900,
        fixed_child_cap=kernel.Quantity(1),
        certified_participation_cap=Fraction(1, 2),
        cancel_reprice_budget=2,
        protection_mandate=protection,
    )
    return kernel.AcquisitionMandate(
        acquisition_mandate_id=acquisition_id,
        position_scope=_TARGET_SCOPE,
        session_id=_E3_SESSION,
        configuration_version="wo0152-e3-acquisition-v1",
        maximum_quantity=kernel.Quantity(5),
        maximum_notional=Fraction(1_000),
        maximum_entry_price=_PRICE,
        allowed_order_types=(kernel.AcquisitionOrderType.LIMIT,),
        expiry=1_000,
        deadline=900,
        fixed_child_cap=kernel.Quantity(1),
        certified_participation_cap=Fraction(1, 2),
        cancel_reprice_budget=2,
        protection_mandate=protection,
        binding=binding,
    )


def _serving_environment_predecessor_fixture() -> tuple[
    kernel.ExecutionAuthorityState,
    kernel.ExecutionSnapshot,
]:
    """Build the one R2-R3-fixed OTHER-symbol public adapter handoff."""

    raw_authority = kernel.initial_execution_authority_state(_VENUE_SCOPE)
    original_book = raw_authority.venue
    original_registry_count = original_book.execution_registry_count
    original_registry_commitment = original_book.execution_registry_commitment
    other_execution = kernel.ExecutionSnapshot.flat(_OTHER_SCOPE)
    original_execution_commitment = other_execution.commitment

    serving_authority = copy.copy(raw_authority)
    object.__setattr__(serving_authority, "phase", kernel.EnginePhase.SERVING)
    object.__setattr__(serving_authority, "mode", kernel.TradingMode.ACTIVE)
    object.__setattr__(
        serving_authority,
        "supervisor_fence",
        kernel.SupervisorFence.PAPER_MUTATION_ELIGIBLE,
    )
    object.__setattr__(serving_authority, "kill_engaged", False)
    object.__setattr__(
        serving_authority,
        "session_id",
        kernel.SessionId("wo0152-e3-serving-session"),
    )
    object.__setattr__(
        serving_authority,
        "budget",
        kernel.RequestBudget(remaining=8, safety_reserve=1),
    )

    created = kernel.apply_execution_authority_input(
        serving_authority,
        other_execution,
        kernel.CreateBrokerEffect(
            input_id=kernel.AuthorityInputId("wo0152-e3-other-create"),
            session_id=serving_authority.session_id,
            request=kernel.BrokerEffectRequest(
                effect_id=kernel.EffectId("wo0152-e3-other-effect"),
                request_occurrence_id=kernel.RequestOccurrenceId(
                    "wo0152-e3-other-request"
                ),
                mandate_id=kernel.MandateId("wo0152-e3-other-mandate"),
                kind=kernel.EffectKind.SUBMIT,
                client_order_id=kernel.ClientOrderId("wo0152-e3-other-client"),
                symbol_id=_OTHER_SCOPE.symbol_id,
                side=kernel.ExecutionSide.BUY,
                quantity=kernel.Quantity(1),
                economic_scope=b"wo0152-e3-other-scope",
                target_leg_key=None,
            ),
            manual_flatten_id=None,
            emergency_grant_id=None,
        ),
    )
    assert type(created) is kernel.ExecutionAuthorityTransition
    assert created.disposition is kernel.AuthorityDisposition.APPLIED
    assert len(created.created_effect_ids) == 1
    other_effect_id = created.created_effect_ids[0]

    claimed = kernel.apply_execution_authority_input(
        created.state,
        other_execution,
        kernel.ClaimEffect(
            input_id=kernel.AuthorityInputId("wo0152-e3-other-claim"),
            effect_id=other_effect_id,
            claim_occurrence_id=kernel.ClaimOccurrenceId("wo0152-e3-other-claim"),
        ),
    )
    assert type(claimed) is kernel.ExecutionAuthorityTransition
    assert claimed.disposition is kernel.AuthorityDisposition.APPLIED
    assert claimed.fresh_claim is not None
    assert claimed.fresh_claim.effect_id == other_effect_id

    acknowledged = kernel.apply_venue_recovery_input(
        claimed.state.venue,
        other_execution,
        kernel.RecordTransportOutcome(
            input_id=kernel.VenueInputId("wo0152-e3-other-acknowledged"),
            effect_id=other_effect_id,
            state=kernel.BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    assert type(acknowledged) is kernel.VenueRecoveryTransition
    assert acknowledged.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert acknowledged.quantity_delta == 0

    discovered = kernel.apply_venue_recovery_input(
        acknowledged.book,
        acknowledged.execution,
        kernel.DiscoverVenueLeg(
            input_id=kernel.VenueInputId("wo0152-e3-other-discover"),
            effect_id=other_effect_id,
            leg_key=_OTHER_LEG,
            observation_id=kernel.VenueObservationId("wo0152-e3-other-discover"),
        ),
    )
    assert type(discovered) is kernel.VenueRecoveryTransition
    assert discovered.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert discovered.quantity_delta == 0

    reviewed = kernel.apply_venue_recovery_input(
        discovered.book,
        discovered.execution,
        kernel.ObserveVenueStatus(
            input_id=kernel.VenueInputId("wo0152-e3-other-needs-review"),
            leg_key=_OTHER_LEG,
            status=kernel.VenueAttemptState.NEEDS_REVIEW,
            observation_id=kernel.VenueObservationId("wo0152-e3-other-needs-review"),
            cumulative_quantity=kernel.Quantity(0),
        ),
    )
    assert type(reviewed) is kernel.VenueRecoveryTransition
    assert reviewed.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert reviewed.quantity_delta == 0

    final_transition = kernel.apply_venue_recovery_input(
        reviewed.book,
        reviewed.execution,
        kernel.RecordBrokerFillEvidence(
            input_id=kernel.VenueInputId("wo0152-e3-other-fill"),
            effect_id=other_effect_id,
            leg_key=_OTHER_LEG,
            prior_cumulative_quantity=kernel.Quantity(0),
            resulting_cumulative_quantity=kernel.Quantity(1),
            fact=kernel.BrokerFillFact(
                key=kernel.ExecutionFactKey(
                    broker=_BROKER,
                    environment=_ENVIRONMENT,
                    account=_ACCOUNT,
                    source_event_id=kernel.SourceEventId("wo0152-e3-other-fill"),
                ),
                scope=kernel.ExecutionScope(
                    broker=_BROKER,
                    environment=_ENVIRONMENT,
                    account=_ACCOUNT,
                    order_id=_OTHER_LEG.order_id,
                    symbol_id=_OTHER_SCOPE.symbol_id,
                    side=kernel.ExecutionSide.BUY,
                ),
                root_fill_id=kernel.RootFillId("wo0152-e3-other-root"),
                quantity=kernel.Quantity(1),
                price=_PRICE,
            ),
            evidence_digest=bytes([0x51]) * 32,
        ),
    )
    assert type(final_transition) is kernel.VenueRecoveryTransition
    assert final_transition.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert final_transition.quantity_delta == 1
    assert final_transition.execution.position.raw_quantity == 1
    assert final_transition.execution.integrity is kernel.PositionIntegrity.CONSISTENT
    assert not final_transition.execution.account_reconciliation_required
    assert (
        final_transition.book.execution_registry_count
        == final_transition.execution.seen_facts.count
    )
    assert (
        final_transition.book.execution_registry_commitment
        == final_transition.execution.seen_facts.commitment
    )
    assert final_transition.book.execution_binding(_OTHER_SCOPE) is not None
    assert final_transition.book.execution_binding(_TARGET_SCOPE) is None
    assert _OTHER_SCOPE.account == _TARGET_SCOPE.account
    assert _OTHER_SCOPE.symbol_id != _TARGET_SCOPE.symbol_id
    assert raw_authority.venue is original_book
    assert raw_authority.venue.execution_registry_count == original_registry_count
    assert (
        raw_authority.venue.execution_registry_commitment
        == original_registry_commitment
    )
    assert other_execution.commitment == original_execution_commitment

    copied_authority = copy.copy(claimed.state)
    object.__setattr__(copied_authority, "venue", final_transition.book)
    bootstrap_probe = authority.refresh_acquisition_context(
        copied_authority,
        final_transition.execution,
        _TARGET_SCOPE,
    )
    assert (
        bootstrap_probe.disposition
        is authority.AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP
    )
    assert bootstrap_probe.authority is not None
    assert bootstrap_probe.execution is not None
    assert len(bootstrap_probe.venue_transitions) == 1
    assert bootstrap_probe.venue_transitions[0].quantity_delta == 0
    return copied_authority, final_transition.execution


def test_e3_raw_genesis_remains_nonserving_and_refuses_generic_target_buy() -> None:
    raw_authority = kernel.initial_execution_authority_state(_VENUE_SCOPE)
    target_execution = kernel.ExecutionSnapshot.flat(_TARGET_SCOPE)

    refused = kernel.apply_execution_authority_input(
        raw_authority,
        target_execution,
        kernel.CreateBrokerEffect(
            input_id=kernel.AuthorityInputId("wo0152-e3-raw-target-create"),
            session_id=kernel.SessionId("wo0152-e3-raw-session"),
            request=kernel.BrokerEffectRequest(
                effect_id=kernel.EffectId("wo0152-e3-raw-target-effect"),
                request_occurrence_id=kernel.RequestOccurrenceId(
                    "wo0152-e3-raw-target-request"
                ),
                mandate_id=kernel.MandateId("wo0152-e3-raw-target-mandate"),
                kind=kernel.EffectKind.SUBMIT,
                client_order_id=kernel.ClientOrderId("wo0152-e3-raw-target-client"),
                symbol_id=_TARGET_SCOPE.symbol_id,
                side=kernel.ExecutionSide.BUY,
                quantity=kernel.Quantity(1),
                economic_scope=b"wo0152-e3-raw-target-scope",
                target_leg_key=None,
            ),
            manual_flatten_id=None,
            emergency_grant_id=None,
        ),
    )

    assert refused.disposition is kernel.AuthorityDisposition.REFUSED
    assert refused.reason is kernel.AuthorityReason.SUPERVISOR_FENCE_BLOCKED
    assert refused.state is raw_authority
    assert refused.created_effect_ids == ()
    assert refused.fresh_claim is None
    assert refused.venue_transitions == ()


def test_e3_sibling_history_bootstraps_target_but_generic_target_buy_stays_refused() -> (
    None
):
    predecessor, sibling_execution = _serving_environment_predecessor_fixture()
    refresh = authority.refresh_acquisition_context(
        predecessor,
        sibling_execution,
        _TARGET_SCOPE,
    )

    assert (
        refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP
    )
    assert refresh.authority is not None
    assert refresh.execution is not None
    assert refresh.execution.position.raw_quantity == 0
    assert refresh.matches_current(refresh.authority, _APPLICATION, _TARGET_SCOPE)
    bootstrap = refresh.authority.venue.project_acquisition_bootstrap(
        refresh.execution,
        _TARGET_SCOPE,
    )
    assert bootstrap.matches_bootstrap(
        refresh.execution,
        refresh.authority.venue,
        _TARGET_SCOPE,
    )
    admission = authority.project_acquisition_admission(
        refresh.authority,
        refresh.execution,
        _TARGET_SCOPE,
    )
    assert admission.kind is authority.AcquisitionAdmissionKind.GENESIS_EMPTY
    assert admission.permits_genesis(_APPLICATION, refresh.execution, _TARGET_SCOPE)

    refused = kernel.apply_execution_authority_input(
        refresh.authority,
        refresh.execution,
        kernel.CreateBrokerEffect(
            input_id=kernel.AuthorityInputId("wo0152-e3-bound-target-create"),
            session_id=refresh.authority.session_id,
            request=kernel.BrokerEffectRequest(
                effect_id=kernel.EffectId("wo0152-e3-bound-target-effect"),
                request_occurrence_id=kernel.RequestOccurrenceId(
                    "wo0152-e3-bound-target-request"
                ),
                mandate_id=kernel.MandateId("wo0152-e3-bound-target-mandate"),
                kind=kernel.EffectKind.SUBMIT,
                client_order_id=kernel.ClientOrderId("wo0152-e3-bound-target-client"),
                symbol_id=_TARGET_SCOPE.symbol_id,
                side=kernel.ExecutionSide.BUY,
                quantity=kernel.Quantity(1),
                economic_scope=b"wo0152-e3-bound-target-scope",
                target_leg_key=None,
            ),
            manual_flatten_id=None,
            emergency_grant_id=None,
        ),
    )

    assert refused.disposition is kernel.AuthorityDisposition.REFUSED
    assert refused.reason is kernel.AuthorityReason.VENUE_UNCERTAIN
    assert refused.state is refresh.authority
    assert refused.created_effect_ids == ()
    assert refused.fresh_claim is None
    assert refused.venue_transitions == ()


def test_e3_public_nonadjacent_duplicate_stream_successor_is_refused() -> None:
    """A valid fresh successor cannot reuse retired A's market-stream authority."""

    schedule = _approved_acquisition_mandates_fixture()
    probe = _nonadjacent_duplicate_stream_probe_mandate_fixture()
    assert len(schedule) == 32
    a_mandate = schedule[0]
    b_mandate = schedule[1]
    assert a_mandate.acquisition_mandate_id != b_mandate.acquisition_mandate_id
    assert (
        a_mandate.protection_mandate.mandate_id
        != b_mandate.protection_mandate.mandate_id
    )
    assert (
        a_mandate.protection_mandate.evidence_policy.stream_generation
        != b_mandate.protection_mandate.evidence_policy.stream_generation
    )
    assert probe.acquisition_mandate_id not in {
        mandate.acquisition_mandate_id for mandate in schedule
    }
    assert probe.protection_mandate.mandate_id not in {
        mandate.protection_mandate.mandate_id for mandate in schedule
    }
    assert probe.binding.commitment not in {
        mandate.binding.commitment for mandate in schedule
    }
    assert (
        probe.protection_mandate.evidence_policy.stream_generation
        == a_mandate.protection_mandate.evidence_policy.stream_generation
    )
    assert (
        probe.protection_mandate.evidence_policy.stream_generation
        != b_mandate.protection_mandate.evidence_policy.stream_generation
    )
    assert probe.position_scope == a_mandate.position_scope == b_mandate.position_scope
    assert probe.session_id == a_mandate.session_id == b_mandate.session_id
    assert (
        probe.protection_mandate.emergency_recovery_compatibility.commitment
        == a_mandate.protection_mandate.emergency_recovery_compatibility.commitment
        == b_mandate.protection_mandate.emergency_recovery_compatibility.commitment
    )

    predecessor, sibling_execution = _serving_environment_predecessor_fixture()
    genesis_refresh = authority.refresh_acquisition_context(
        predecessor,
        sibling_execution,
        _TARGET_SCOPE,
    )
    assert (
        genesis_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP
    )
    assert genesis_refresh.authority is not None
    assert genesis_refresh.execution is not None
    genesis_bootstrap = genesis_refresh.authority.venue.project_acquisition_bootstrap(
        genesis_refresh.execution,
        _TARGET_SCOPE,
    )
    assert genesis_bootstrap.matches_bootstrap(
        genesis_refresh.execution,
        genesis_refresh.authority.venue,
        _TARGET_SCOPE,
    )
    genesis_admission = authority.project_acquisition_admission(
        genesis_refresh.authority,
        genesis_refresh.execution,
        _TARGET_SCOPE,
    )
    assert genesis_admission.kind is authority.AcquisitionAdmissionKind.GENESIS_EMPTY
    assert genesis_admission.permits_genesis(
        _APPLICATION,
        genesis_refresh.execution,
        _TARGET_SCOPE,
    )

    initialized = kernel.initialize_acquisition_controller(
        _APPLICATION,
        a_mandate,
        genesis_bootstrap,
        genesis_admission,
        genesis_refresh,
        None,
    )
    assert initialized.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert initialized.created_effect_id is None
    assert initialized.fresh_claim is None
    assert initialized.protection is None

    b_refresh = authority.refresh_acquisition_context(
        initialized.authority,
        initialized.execution,
        _TARGET_SCOPE,
    )
    assert (
        b_refresh.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    assert b_refresh.authority is initialized.authority
    assert b_refresh.execution is initialized.execution
    b_bootstrap = initialized.authority.venue.project_acquisition_bootstrap(
        initialized.execution,
        _TARGET_SCOPE,
    )
    assert b_bootstrap.matches_bootstrap(
        b_refresh.execution,
        b_refresh.authority.venue,
        _TARGET_SCOPE,
    )
    b_admission = authority.project_acquisition_admission(
        initialized.authority,
        initialized.execution,
        _TARGET_SCOPE,
    )
    assert b_admission.kind is authority.AcquisitionAdmissionKind.SUCCESSOR
    assert b_admission.permits_successor(
        _APPLICATION,
        b_refresh.execution,
        _TARGET_SCOPE,
    )
    b_transition = kernel.begin_acquisition_generation(
        initialized.state,
        b_mandate,
        b_bootstrap,
        b_admission,
        b_refresh,
        None,
    )
    assert b_transition.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert b_transition.created_effect_id is None
    assert b_transition.fresh_claim is None
    assert b_transition.protection is None
    b_status = kernel.project_acquisition_controller(b_transition.state)
    assert b_status.successor_ordinal == 1
    assert b_status.live_generation_id is not None
    assert b_status.recovery_class is kernel.AcquisitionRecoveryClass.NORMAL

    probe_refresh = authority.refresh_acquisition_context(
        b_transition.authority,
        b_transition.execution,
        _TARGET_SCOPE,
    )
    assert (
        probe_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    assert probe_refresh.authority is b_transition.authority
    assert probe_refresh.execution is b_transition.execution
    probe_bootstrap = b_transition.authority.venue.project_acquisition_bootstrap(
        b_transition.execution,
        _TARGET_SCOPE,
    )
    assert probe_bootstrap.matches_bootstrap(
        probe_refresh.execution,
        probe_refresh.authority.venue,
        _TARGET_SCOPE,
    )
    probe_admission = authority.project_acquisition_admission(
        b_transition.authority,
        b_transition.execution,
        _TARGET_SCOPE,
    )
    assert probe_admission.kind is authority.AcquisitionAdmissionKind.SUCCESSOR
    assert probe_admission.permits_successor(
        _APPLICATION,
        probe_refresh.execution,
        _TARGET_SCOPE,
    )

    refused = kernel.begin_acquisition_generation(
        b_transition.state,
        probe,
        probe_bootstrap,
        probe_admission,
        probe_refresh,
        None,
    )

    assert refused.disposition is kernel.AcquisitionControllerDisposition.REFUSED
    assert refused.state is b_transition.state
    assert refused.authority is b_transition.authority
    assert refused.venue is b_transition.venue
    assert refused.execution is b_transition.execution
    assert refused.protection is b_transition.protection
    assert refused.created_effect_id is None
    assert refused.fresh_claim is None
