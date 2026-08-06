"""RED controls for WO-0150 R1's narrow, pure E1 acquisition foundation.

E1 deliberately exposes deterministic identity data, opaque read declarations,
empty readers, and a bounded venue-derived read projection.  It does not admit,
register, bind, route, or update acquisition state; those operations remain
exclusive to WO-0151's authenticated E2 composite transition.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pytest

import app.execution_core as kernel
import app.execution_core.acquisition as acquisition
import app.execution_core.venue as venue
from app.execution_core.fills import PositionScope
from app.execution_core.identity import (
    AccountId,
    AcquisitionGenerationId,
    ApplicationGenerationId,
    BrokerId,
    EffectId,
    EnvironmentId,
    ExecutionFactKey,
    OrderId,
    RequestOccurrenceId,
    RootFillId,
    RootFillKey,
    SourceEventId,
    SymbolId,
    VenueLegKey,
)
from app.execution_core.recovery import RecordBrokerFillEvidence
from app.execution_core.venue import VenueAcquisitionCorrelation, VenueRecoveryBook
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
        "GenerationServingClass",
        "GenerationRouteKind",
        "GenerationBindingView",
        "GenerationRecordView",
        "GenerationRouteView",
        "GenerationRegistry",
        "AcquisitionLineageIndex",
    }
    expected_root_delta = expected_acquisition_exports | {
        "AcquisitionGenerationId",
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
    with pytest.raises(ValueError):
        forged_index.route_root(_root("forged-container"))


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
