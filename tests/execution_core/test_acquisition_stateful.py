"""WO-0152 E3 behavior-first, public-contract acquisition conformance.

This module owns only test evidence.  The narrow setup exceptions below model
deferred environment and adapter composition; every acquisition operation after
that boundary uses the public execution-core contracts.
"""

from __future__ import annotations

import ast
import copy
import random
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

import app.execution_core as kernel
import app.execution_core.acquisition as acquisition
import app.execution_core.authority as authority
import app.execution_core.venue as venue


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
_TARGET_LEG = kernel.VenueLegKey(
    broker=_BROKER,
    environment=_ENVIRONMENT,
    account=_ACCOUNT,
    order_id=kernel.OrderId("wo0152-e3-target-leg"),
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
_E3_ABORTED_TRACE_LABELS = (
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "I",
    "J",
    "K",
    "L",
    "M",
    "N",
    "O",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
    "AA",
    "AB",
    "AC",
    "AD",
    "AE",
    "AF",
)
_E3_ABORTED_TRACE_ORDINALS = (
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    30,
    31,
)
_E3_TRACE_APPLICATION = "wo0152-e3-application"
_E3_TRACE_SCOPE = (
    "wo0152-e3-broker",
    "paper",
    "wo0152-e3-account",
    "AAPL",
)
_E3_GENESIS_HEAD_COMMITMENT = bytes.fromhex(
    "4fdc75654dcaad1e700030e34571ba476ad0df46073c18a54590e3c9942d2523"
)
_E3_GENESIS_BINDING_COMMITMENT = bytes.fromhex(
    "db551d17dcd19b9e30a9a5f7b136ba452d1f31fd071235b7a6b46481293c9625"
)
_E3_HISTORY_PROPERTY_TARGETS = frozenset(
    {
        ("VenueRecoveryBook", "effects"),
        ("VenueRecoveryBook", "claims"),
        ("VenueRecoveryBook", "owners"),
        ("VenueRecoveryBook", "active_attempts"),
        ("VenueRecoveryBook", "closure_heads"),
        ("VenueRecoveryBook", "execution_bindings"),
        ("VenueRecoveryBook", "input_records"),
        ("VenueRecoveryBook", "closure_history"),
        ("VenueRecoveryBook", "human_coverages"),
        ("VenueRecoveryBook", "broker_coverages"),
        ("VenueRecoveryBook", "reconciliations"),
        ("VenueRecoveryBook", "execution_reconciliations"),
        ("SeenFactIndex", "entries"),
        ("RootHeadIndex", "entries"),
    }
)
_E3_HISTORY_METHOD_TARGETS = frozenset(
    {
        ("VenueRecoveryBook", "effect"),
        ("SeenFactIndex", "observation_at"),
    }
)
_E3_BASE_CONTROL_INVENTORY = (
    (
        "E1-AC-01/FR-01-FR-02",
        "test_acquisition.py",
        "test_identity_known_answers_replay_and_well_formed_variants_are_data_only",
        (
            "actual.value == 'a3a7378c87ce9b0fe2a544d1cccdbe53da28693b66ab127f10df0848223f931a'",
            "actual == acquisition._derive_acquisition_generation_id(",
            "successor.value == 'b3054715237a8855dc0194ab9684de0958d5069d753a427aaab2d578fd7cfad8'",
            "successor == acquisition._derive_acquisition_generation_id(",
            "all((variant != actual for variant in variants))",
            "all((acquisition._acquisition_generation_id_is_canonical(variant) for variant in variants))",
        ),
    ),
    (
        "E1-AC-02/FR-04-FR-07",
        "test_acquisition.py",
        "test_wo0151_r11_late_retired_fact_recovers_without_serving_retired_a",
        (
            "recovery_class is acquisition.AcquisitionRecoveryClass.MIXED_GENERATION_RECOVERY",
            "route_fact(late_fill.key).generation_id == retired_generation",
        ),
    ),
    (
        "E1-AC-03/FR-04-FR-09",
        "test_acquisition.py",
        "test_venue_correlation_refuses_same_account_different_symbol_claim",
        (
            "acquisition_correlation(recovery_fixtures.REQUEST, recovery_fixtures.EFFECT",
            "acquisition_correlation(RequestOccurrenceId('request-msft'), other_effect",
        ),
    ),
    (
        "E1-AC-04/FR-05-FR-06",
        "test_authority.py",
        "test_authority_identity_indexes_are_structurally_shared_and_bounded",
        (
            "state._input_by_id.size == 32",
            "operations <= 16",
        ),
    ),
    (
        "E1-AC-05/FR-07",
        "test_acquisition.py",
        "test_wo0151_r11_retired_tail_bust_updates_once_and_replays_inertly",
        (
            "after.economics_head_commitment != before.economics_head_commitment",
            "replay.state is result.state",
        ),
    ),
    (
        "E1-AC-06/FR-08",
        "test_acquisition.py",
        "test_public_surface_is_opaque_inert_and_exactly_additive_at_root",
        (
            "set(acquisition.__all__) == expected_acquisition_exports",
            "not {'__iter__', '__len__', '__getitem__', 'items', 'keys', 'values'}",
        ),
    ),
    (
        "E1-AC-07/FR-03-FR-10",
        "test_acquisition.py",
        "test_venue_correlation_has_no_raw_factory_and_one_checked_construction_site",
        (
            "len(constructors) == 1",
            "consumers == []",
        ),
    ),
    (
        "E2-AC-01/FR-01-FR-03",
        "test_acquisition.py",
        "test_wo0151_r8_same_account_history_initializes_only_the_clear_target",
        (
            "UNBOUND_BOOTSTRAP",
            "execution_binding(scope) is not None",
        ),
    ),
    (
        "E2-AC-02/FR-04-FR-05",
        "test_acquisition.py",
        "test_wo0151_r13_completed_successor_rolls_cursor_and_arms_first_b_fill",
        (
            "len(registration.venue_transitions) == 1",
            "rooted.protection.policy is protection.ProtectionPolicy.FLOOR_ONLY",
        ),
    ),
    (
        "E2-AC-03/FR-02-FR-04",
        "test_acquisition.py",
        "test_wo0151_r11_serial_aborted_successors_advance_a_to_b_to_c",
        (
            "successor_ordinal == 2",
            "record(c_id).serving_class is acquisition.GenerationServingClass.LIVE",
        ),
    ),
    (
        "E2-AC-04/FR-06",
        "test_acquisition.py",
        "test_wo0151_current_generation_fill_arms_fresh_floor_only_protection",
        (
            "policy is protection_fixtures._protection_module().ProtectionPolicy.FLOOR_ONLY",
            "route_fact(relation.fact_key) is not None",
        ),
    ),
    (
        "E2-AC-05/FR-07-FR-08",
        "test_acquisition.py",
        "test_wo0151_r11_retired_correct_reexpands_tombstone_once",
        (
            "route is not None and route.generation_id == retired_generation",
            "replay.disposition is acquisition.AcquisitionControllerDisposition.EXACT_REPLAY",
        ),
    ),
    (
        "E2-AC-06/FR-09",
        "test_acquisition.py",
        "test_wo0151_r11_final_claim_revalidates_the_exact_currentness_head",
        (
            "refused.disposition is authority.AuthorityDisposition.REFUSED",
            "refused.acquisition_claim_receipt is None",
        ),
    ),
    (
        "E2-AC-07/FR-01-FR-10/NFR-01",
        "test_authority.py",
        "test_hot_authority_paths_never_materialize_audit_history",
        (
            "sequence_reads - before <= 16",
            "flattened.disposition is disposition_type.APPLIED",
        ),
    ),
    (
        "E2-AC-08/FR-05-FR-07-FR-11",
        "test_acquisition.py",
        "test_wo0151_r13_binding_receipt_and_serving_mutations_are_failure_capable",
        (
            "not authority_module.project_acquisition_authority_context",
            "restored.disposition is acquisition.AcquisitionControllerDisposition.APPLIED",
        ),
    ),
)
_E3_DECISIVE_COMPARISONS = frozenset(
    {
        "lineage",
        "head_and_ordinal",
        "one_live",
        "economics_exact_once",
        "compatibility",
        "capacity",
        "codec",
        "bounded_lookup",
        "identity_core_coordinates",
        "identity_predecessor_heads",
        "identity_compatibility",
        "identity_binding_commitments",
    }
)


def _raise_history_property(_: object) -> object:
    raise AssertionError("live acquisition decision materialized retained history")


def _raise_venue_effect(_: object, __: object) -> object:
    raise AssertionError("live acquisition decision materialized effect audit history")


def _raise_seen_observation(_: object, __: object) -> object:
    raise AssertionError("live acquisition decision traversed ordered fact history")


@contextmanager
def _forbid_live_acquisition_history_materialization() -> Iterator[None]:
    """Trip every public history materializer during three live decisions."""

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(
                kernel.VenueRecoveryBook,
                "effects",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(
                kernel.VenueRecoveryBook,
                "claims",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(
                kernel.VenueRecoveryBook,
                "owners",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(
                kernel.VenueRecoveryBook,
                "active_attempts",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(
                kernel.VenueRecoveryBook,
                "closure_heads",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(
                kernel.VenueRecoveryBook,
                "execution_bindings",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(
                kernel.VenueRecoveryBook,
                "input_records",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(
                kernel.VenueRecoveryBook,
                "closure_history",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(
                kernel.VenueRecoveryBook,
                "human_coverages",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(
                kernel.VenueRecoveryBook,
                "broker_coverages",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(
                kernel.VenueRecoveryBook,
                "reconciliations",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(
                kernel.VenueRecoveryBook,
                "execution_reconciliations",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(
                kernel.SeenFactIndex,
                "entries",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(
                kernel.RootHeadIndex,
                "entries",
                property(_raise_history_property),
            )
        )
        stack.enter_context(
            patch.object(kernel.VenueRecoveryBook, "effect", _raise_venue_effect)
        )
        stack.enter_context(
            patch.object(
                kernel.SeenFactIndex, "observation_at", _raise_seen_observation
            )
        )
        yield


def _e3_dotted_name(node: ast.AST) -> str | None:
    if type(node) is ast.Name:
        return node.id
    if type(node) is ast.Attribute:
        prefix = _e3_dotted_name(node.value)
        if prefix is not None:
            return f"{prefix}.{node.attr}"
    return None


def _e3_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _e3_owner_function(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> str | None:
    current = parents.get(node)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
        current = parents.get(current)
    return None


def _e3_source_policy_violations(source: str) -> tuple[str, ...]:
    """Return focused lexical privilege and boundedness-policy violations."""

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ("syntax-error",)
    parents = _e3_parent_map(tree)
    violations: list[str] = []
    private_owners = {
        "acquisition._mint_dual_mandate_binding": {
            "_approved_acquisition_mandates_fixture",
            "_nonadjacent_duplicate_stream_probe_mandate_fixture",
        },
        "venue._apply_venue_input": {"_certified_terminal_parent_fixture"},
        "venue._external_acceptance_closure_is_certified": {
            "_certified_terminal_parent_fixture"
        },
        "object.__setattr__": {
            "_serving_environment_predecessor_fixture",
            "_certified_terminal_parent_fixture",
        },
    }
    dynamic_names = {
        "getattr",
        "setattr",
        "hasattr",
        "vars",
        "globals",
        "locals",
        "eval",
        "exec",
        "__import__",
        "import_module",
    }
    minter_owners: list[str | None] = []
    venue_reducer_owners: list[str | None] = []
    patch_targets: set[tuple[str, str]] = set()
    tripwire_patch_count = 0
    copy_calls: list[tuple[str | None, str | None]] = []
    setter_calls: list[tuple[str | None, str | None, object]] = []
    fixture_patch_calls: list[tuple[str | None, str | None, object]] = []

    for node in ast.walk(tree):
        if type(node) is ast.ImportFrom and node.module is not None:
            if node.module == "tests" or node.module.startswith("tests."):
                violations.append("tests-import")
        if type(node) is ast.Import:
            if any(
                alias.name == "tests" or alias.name.startswith("tests.")
                for alias in node.names
            ):
                violations.append("tests-import")
        if type(node) is ast.Call:
            name = _e3_dotted_name(node.func)
            if name is not None and name.split(".")[-1] in dynamic_names:
                violations.append("dynamic-lookup")
            if name == "acquisition._mint_dual_mandate_binding":
                minter_owners.append(_e3_owner_function(node, parents))
            if name == "venue._apply_venue_input":
                venue_reducer_owners.append(_e3_owner_function(node, parents))
            if name == "patch":
                violations.append("setup-patch-authority")
            if name == "copy.copy":
                copy_calls.append(
                    (
                        _e3_owner_function(node, parents),
                        _e3_dotted_name(node.args[0]) if node.args else None,
                    )
                )
            if name == "object.__setattr__":
                setter_calls.append(
                    (
                        _e3_owner_function(node, parents),
                        _e3_dotted_name(node.args[0]) if node.args else None,
                        (
                            node.args[1].value
                            if len(node.args) >= 2
                            and type(node.args[1]) is ast.Constant
                            else None
                        ),
                    )
                )
            if name == "patch.object":
                fixture_patch_calls.append(
                    (
                        _e3_owner_function(node, parents),
                        _e3_dotted_name(node.args[0]) if node.args else None,
                        (
                            node.args[1].value
                            if len(node.args) >= 2
                            and type(node.args[1]) is ast.Constant
                            else None
                        ),
                    )
                )
            if (
                name == "patch.object"
                and _e3_owner_function(node, parents)
                == "_forbid_live_acquisition_history_materialization"
                and len(node.args) >= 2
                and type(node.args[0]) is ast.Attribute
                and type(node.args[1]) is ast.Constant
                and type(node.args[1].value) is str
            ):
                tripwire_patch_count += 1
                target = (node.args[0].attr, node.args[1].value)
                patch_targets.add(target)
                replacement = node.args[2] if len(node.args) >= 3 else None
                if target in _E3_HISTORY_PROPERTY_TARGETS:
                    if (
                        not isinstance(replacement, ast.Call)
                        or _e3_dotted_name(replacement.func) != "property"
                    ):
                        violations.append("history-tripwire-shape")
                elif target == ("VenueRecoveryBook", "effect"):
                    if (
                        replacement is None
                        or _e3_dotted_name(replacement) != "_raise_venue_effect"
                    ):
                        violations.append("history-tripwire-shape")
                elif target == ("SeenFactIndex", "observation_at"):
                    if (
                        replacement is None
                        or _e3_dotted_name(replacement) != "_raise_seen_observation"
                    ):
                        violations.append("history-tripwire-shape")
        if type(node) is ast.Attribute and node.attr.startswith("_"):
            name = _e3_dotted_name(node)
            if name == "__file__":
                continue
            owner = _e3_owner_function(node, parents)
            if name not in private_owners or owner not in private_owners[name]:
                violations.append("private-production-access")

    if sorted(minter_owners, key=repr) != [
        "_approved_acquisition_mandates_fixture",
        "_nonadjacent_duplicate_stream_probe_mandate_fixture",
    ]:
        violations.append("private-minter-sites")
    if venue_reducer_owners != ["_certified_terminal_parent_fixture"]:
        violations.append("private-venue-reducer-sites")

    expected_targets = _E3_HISTORY_PROPERTY_TARGETS | _E3_HISTORY_METHOD_TARGETS
    if patch_targets != expected_targets or tripwire_patch_count != 16:
        violations.append("history-tripwire-targets")

    expected_copy_calls = sorted(
        {
            ("_serving_environment_predecessor_fixture", "raw_authority"),
            ("_serving_environment_predecessor_fixture", "claimed.state"),
            ("_certified_terminal_parent_fixture", "flat.authority"),
        }
    )
    if sorted(copy_calls, key=repr) != expected_copy_calls:
        violations.append("setup-copy-authority")

    expected_setters = sorted(
        {
            ("_serving_environment_predecessor_fixture", "serving_authority", "phase"),
            ("_serving_environment_predecessor_fixture", "serving_authority", "mode"),
            (
                "_serving_environment_predecessor_fixture",
                "serving_authority",
                "supervisor_fence",
            ),
            (
                "_serving_environment_predecessor_fixture",
                "serving_authority",
                "kill_engaged",
            ),
            (
                "_serving_environment_predecessor_fixture",
                "serving_authority",
                "session_id",
            ),
            ("_serving_environment_predecessor_fixture", "serving_authority", "budget"),
            ("_serving_environment_predecessor_fixture", "copied_authority", "venue"),
            ("_certified_terminal_parent_fixture", "copied_authority", "venue"),
        }
    )
    if sorted(setter_calls, key=repr) != expected_setters:
        violations.append("setup-setattr-authority")

    non_tripwire_patches = sorted(
        (
            call
            for call in fixture_patch_calls
            if call[0] != "_forbid_live_acquisition_history_materialization"
        ),
        key=repr,
    )
    if non_tripwire_patches != [
        (
            "_certified_terminal_parent_fixture",
            "venue",
            "_external_acceptance_closure_is_certified",
        )
    ]:
        violations.append("setup-patch-authority")

    schedule_nodes = [
        node
        for node in tree.body
        if type(node) is ast.Assign
        and len(node.targets) == 1
        and type(node.targets[0]) is ast.Name
        and node.targets[0].id == "_E3_FIXED_MANDATE_SCHEDULE"
    ]
    literal_rows: list[tuple[object, ...]] = []
    if len(schedule_nodes) != 1 or not isinstance(schedule_nodes[0].value, ast.Tuple):
        violations.append("mandate-schedule-shape")
    else:
        entries = schedule_nodes[0].value.elts
        for entry in entries:
            if not isinstance(entry, ast.Tuple) or not all(
                isinstance(value, ast.Constant) for value in entry.elts
            ):
                violations.append("mandate-schedule-dynamic")
                break
            literal_rows.append(
                tuple(
                    value.value
                    for value in entry.elts
                    if isinstance(value, ast.Constant)
                )
            )
        if len(literal_rows) != 32:
            violations.append("mandate-schedule-cardinality")
        if len(literal_rows) == 32:
            for index in (1, 2, 3):
                if len({row[index] for row in literal_rows}) != 32:
                    violations.append("mandate-schedule-uniqueness")
                    break
            if any(
                type(row[3]) is not str
                or len(row[3]) != 64
                or any(character not in "0123456789abcdef" for character in row[3])
                for row in literal_rows
            ):
                violations.append("mandate-stream-literal")

    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    schedule_name = "_approved_acquisition_mandates_fixture"
    probe_name = "_nonadjacent_duplicate_stream_probe_mandate_fixture"
    for fixture_name in (schedule_name, probe_name):
        fixture = functions.get(fixture_name)
        if fixture is None:
            violations.append("mandate-fixture-missing")
            continue
        arguments = fixture.args
        if (
            arguments.posonlyargs
            or arguments.args
            or arguments.kwonlyargs
            or arguments.vararg is not None
            or arguments.kwarg is not None
        ):
            violations.append("mandate-fixture-signature")

    schedule_fixture = functions.get(schedule_name)
    if schedule_fixture is not None:
        schedule_loops = [
            node for node in ast.walk(schedule_fixture) if type(node) is ast.For
        ]
        if (
            len(schedule_loops) != 1
            or type(schedule_loops[0].iter) is not ast.Name
            or schedule_loops[0].iter.id != "_E3_FIXED_MANDATE_SCHEDULE"
        ):
            violations.append("mandate-schedule-loop")
        forbidden_flow = (
            ast.If,
            ast.IfExp,
            ast.Try,
            ast.With,
            ast.While,
            ast.AsyncFor,
            ast.Match,
            ast.Lambda,
            ast.ListComp,
            ast.SetComp,
            ast.DictComp,
            ast.GeneratorExp,
        )
        if any(type(node) in forbidden_flow for node in ast.walk(schedule_fixture)):
            violations.append("mandate-schedule-control-flow")
        if any(
            type(node) in (ast.Break, ast.Continue)
            for node in ast.walk(schedule_fixture)
        ):
            violations.append("mandate-schedule-control-flow")
        returns = [
            node for node in ast.walk(schedule_fixture) if type(node) is ast.Return
        ]
        if len(returns) != 1 or returns[0] is not schedule_fixture.body[-1]:
            violations.append("mandate-schedule-control-flow")
        schedule_mints = [
            node
            for node in ast.walk(schedule_fixture)
            if type(node) is ast.Call
            and _e3_dotted_name(node.func) == "acquisition._mint_dual_mandate_binding"
        ]
        if len(schedule_mints) != 1:
            violations.append("mandate-schedule-mint-shape")
        elif len(schedule_loops) == 1:
            current: ast.AST | None = schedule_mints[0]
            owning_loop = False
            while current is not None and current is not schedule_fixture:
                current = parents.get(current)
                if current is schedule_loops[0]:
                    owning_loop = True
            if not owning_loop:
                violations.append("mandate-schedule-mint-shape")
        if any(
            type(node) is ast.Name
            and node.id
            in {
                "_E3_FIXED_DUPLICATE_STREAM_PROBE",
                "_nonadjacent_duplicate_stream_probe_mandate_fixture",
            }
            for node in ast.walk(schedule_fixture)
        ):
            violations.append("mandate-schedule-probe-contamination")
        final_statement = schedule_fixture.body[-1] if schedule_fixture.body else None
        if not (
            type(final_statement) is ast.Return
            and type(final_statement.value) is ast.Call
            and _e3_dotted_name(final_statement.value.func) == "tuple"
            and len(final_statement.value.args) == 1
            and type(final_statement.value.args[0]) is ast.Name
            and final_statement.value.args[0].id == "mandates"
        ):
            violations.append("mandate-schedule-return")

    probe_nodes = [
        node
        for node in tree.body
        if type(node) is ast.Assign
        and len(node.targets) == 1
        and type(node.targets[0]) is ast.Name
        and node.targets[0].id == "_E3_FIXED_DUPLICATE_STREAM_PROBE"
    ]
    probe_row: tuple[object, ...] | None = None
    if (
        len(probe_nodes) == 1
        and isinstance(probe_nodes[0].value, ast.Tuple)
        and len(probe_nodes[0].value.elts) == 4
        and all(isinstance(value, ast.Constant) for value in probe_nodes[0].value.elts)
    ):
        probe_row = tuple(
            value.value
            for value in probe_nodes[0].value.elts
            if isinstance(value, ast.Constant)
        )
    else:
        violations.append("duplicate-stream-probe-literal")
    if probe_row is not None and len(literal_rows) == 32:
        if (
            probe_row[1] in {row[1] for row in literal_rows}
            or probe_row[2] in {row[2] for row in literal_rows}
            or probe_row[3] != literal_rows[0][3]
            or probe_row[3] == literal_rows[1][3]
        ):
            violations.append("duplicate-stream-probe-provenance")

    probe_fixture = functions.get(probe_name)
    if probe_fixture is not None:
        forbidden_probe_flow = (
            ast.For,
            ast.AsyncFor,
            ast.While,
            ast.If,
            ast.IfExp,
            ast.Try,
            ast.With,
            ast.Match,
            ast.Lambda,
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        )
        if any(
            type(node) in forbidden_probe_flow and node is not probe_fixture
            for node in ast.walk(probe_fixture)
        ):
            violations.append("duplicate-stream-probe-control-flow")
        probe_mints = [
            node
            for node in ast.walk(probe_fixture)
            if type(node) is ast.Call
            and _e3_dotted_name(node.func) == "acquisition._mint_dual_mandate_binding"
        ]
        if len(probe_mints) != 1:
            violations.append("duplicate-stream-probe-mint-shape")
        if any(
            type(node) is ast.Name and node.id == "_E3_FIXED_MANDATE_SCHEDULE"
            for node in ast.walk(probe_fixture)
        ):
            violations.append("duplicate-stream-probe-derived")
        probe_bindings = [
            node
            for node in probe_fixture.body
            if type(node) is ast.Assign
            and type(node.value) is ast.Name
            and node.value.id == "_E3_FIXED_DUPLICATE_STREAM_PROBE"
        ]
        if len(probe_bindings) != 1:
            violations.append("duplicate-stream-probe-binding")
        final_statement = probe_fixture.body[-1] if probe_fixture.body else None
        if not (
            type(final_statement) is ast.Return
            and type(final_statement.value) is ast.Call
            and _e3_dotted_name(final_statement.value.func)
            == "kernel.AcquisitionMandate"
        ):
            violations.append("duplicate-stream-probe-return")

    positive_chain = functions.get(
        "test_e3_public_32_generation_aborted_chain_keeps_exactly_one_live_generation"
    )
    if positive_chain is None or any(
        type(node) is ast.Name
        and node.id
        in {
            "_E3_FIXED_DUPLICATE_STREAM_PROBE",
            "_nonadjacent_duplicate_stream_probe_mandate_fixture",
        }
        for node in ast.walk(positive_chain)
    ):
        violations.append("duplicate-stream-probe-positive-chain")

    for function in functions.values():
        calls = sorted(
            (node for node in ast.walk(function) if type(node) is ast.Call),
            key=lambda node: node.lineno,
        )
        fixture_lines = [
            call.lineno
            for call in calls
            if _e3_dotted_name(call.func) in {schedule_name, probe_name}
        ]
        genesis_lines = [
            call.lineno
            for call in calls
            if _e3_dotted_name(call.func)
            in {
                "_initialize_e3_controller",
                "_serving_environment_predecessor_fixture",
                "kernel.initialize_acquisition_controller",
                "kernel.begin_acquisition_generation",
            }
        ]
        nested_fixture = False
        for call in calls:
            if _e3_dotted_name(call.func) not in {schedule_name, probe_name}:
                continue
            current = parents.get(call)
            while current is not None and current is not function:
                if type(current) is ast.Call and _e3_dotted_name(current.func) in {
                    "_initialize_e3_controller",
                    "_serving_environment_predecessor_fixture",
                    "kernel.initialize_acquisition_controller",
                    "kernel.begin_acquisition_generation",
                }:
                    nested_fixture = True
                    break
                current = parents.get(current)
        if (
            fixture_lines
            and genesis_lines
            and (nested_fixture or min(fixture_lines) > min(genesis_lines))
        ):
            violations.append("mandate-fixture-post-genesis")

    return tuple(sorted(set(violations)))


@dataclass(frozen=True)
class _E3AbortedTrace:
    """Schema-neutral, test-owned commands for one finite serial trace."""

    application: str
    scope: tuple[str, str, str, str]
    labels: tuple[str, ...]
    ordinals: tuple[int, ...]


@dataclass(frozen=True)
class _E3PublicObserver:
    """Named public controller projection fields compared across replay."""

    successor_ordinal: int
    controller_head: bytes
    live_generation_id: kernel.AcquisitionGenerationId | None
    recovery_class: kernel.AcquisitionRecoveryClass
    scope_execution_commitment: bytes
    venue_commitment: bytes
    authority_context_commitment: bytes
    protection_commitment: bytes | None


@dataclass(frozen=True)
class _E3RootedParentSuffix:
    """One fixed public A lifecycle through terminal observation and flat bust."""

    schedule: tuple[kernel.AcquisitionMandate, ...]
    mandate: kernel.AcquisitionMandate
    flat: kernel.AcquisitionControllerTransition
    effect_id: kernel.EffectId
    claim_occurrence_id: kernel.ClaimOccurrenceId
    leg_key: kernel.VenueLegKey
    root_fill: kernel.BrokerFillFact


@dataclass(frozen=True)
class _E3CertifiedParent:
    """One zero-quantity, closed A parent ready for a public B successor."""

    schedule: tuple[kernel.AcquisitionMandate, ...]
    state: kernel.AcquisitionControllerState
    authority: kernel.ExecutionAuthorityState
    execution: kernel.ExecutionSnapshot
    protection: kernel.PositionProtectionState
    effect_id: kernel.EffectId
    claim_occurrence_id: kernel.ClaimOccurrenceId
    leg_key: kernel.VenueLegKey
    root_fill: kernel.BrokerFillFact


@dataclass(frozen=True)
class _E3RootedBEffect:
    """One public B successor with its unclaimed first specialized BUY."""

    parent: _E3CertifiedParent
    created: kernel.AcquisitionControllerTransition
    retired_a_generation_id: kernel.AcquisitionGenerationId
    live_b_generation_id: kernel.AcquisitionGenerationId


@dataclass(frozen=True)
class _E3ClaimedLeg:
    """One public current-generation BUY through claim and leg discovery."""

    mandate: kernel.AcquisitionMandate
    claimed: kernel.AcquisitionControllerTransition
    acknowledged: kernel.VenueRecoveryTransition
    discovered: kernel.VenueRecoveryTransition
    effect_id: kernel.EffectId
    leg_key: kernel.VenueLegKey


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
            session_id=_E3_SESSION,
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
    claimed_effect = claimed.state.venue.effect(other_effect_id)
    assert claimed_effect is not None
    assert claimed_effect.claim_occurrence_id == kernel.ClaimOccurrenceId(
        "wo0152-e3-other-claim"
    )

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


def _initialize_e3_controller(
    mandate: kernel.AcquisitionMandate,
) -> kernel.AcquisitionControllerTransition:
    """Initialize one public target controller from the fixed E3 predecessor."""

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

    initialized = kernel.initialize_acquisition_controller(
        _APPLICATION,
        mandate,
        bootstrap,
        admission,
        refresh,
        None,
    )
    assert initialized.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert initialized.created_effect_id is None
    assert initialized.fresh_claim is None
    assert initialized.protection is None
    return initialized


def _advance_e3_aborted_successor(
    current: kernel.AcquisitionControllerTransition,
    mandate: kernel.AcquisitionMandate,
) -> kernel.AcquisitionControllerTransition:
    """Advance one unused generation through the public serial successor route."""

    refresh = authority.refresh_acquisition_context(
        current.authority,
        current.execution,
        _TARGET_SCOPE,
    )
    assert refresh.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    assert refresh.authority is current.authority
    assert refresh.execution is current.execution
    bootstrap = current.authority.venue.project_acquisition_bootstrap(
        current.execution,
        _TARGET_SCOPE,
    )
    assert bootstrap.matches_bootstrap(
        refresh.execution,
        refresh.authority.venue,
        _TARGET_SCOPE,
    )
    admission = authority.project_acquisition_admission(
        current.authority,
        current.execution,
        _TARGET_SCOPE,
    )
    assert admission.kind is authority.AcquisitionAdmissionKind.SUCCESSOR
    assert admission.permits_successor(
        _APPLICATION,
        refresh.execution,
        _TARGET_SCOPE,
    )

    advanced = kernel.begin_acquisition_generation(
        current.state,
        mandate,
        bootstrap,
        admission,
        refresh,
        current.protection,
    )
    assert advanced.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert advanced.created_effect_id is None
    assert advanced.fresh_claim is None
    assert advanced.protection is None
    return advanced


def _encode_e3_aborted_trace(trace: _E3AbortedTrace) -> tuple[object, ...]:
    """Encode only test-owned primitive restart inputs; never controller state."""

    return (
        trace.application,
        trace.scope,
        trace.labels,
        trace.ordinals,
    )


def _decode_e3_aborted_trace(encoded: object) -> _E3AbortedTrace:
    """Reject malformed trace input before any public reducer is invoked."""

    if type(encoded) is not tuple or len(encoded) != 4:
        raise ValueError("E3 aborted trace must contain four primitive fields")
    application, scope, labels, ordinals = encoded
    if (
        type(application) is not str
        or type(scope) is not tuple
        or type(labels) is not tuple
        or type(ordinals) is not tuple
        or len(scope) != 4
        or any(type(value) is not str for value in scope)
        or any(type(value) is not str for value in labels)
        or any(type(value) is not int for value in ordinals)
    ):
        raise ValueError("E3 aborted trace has non-primitive coordinates")
    if application != _E3_TRACE_APPLICATION or scope != _E3_TRACE_SCOPE:
        raise ValueError("E3 aborted trace has a foreign application or scope")
    if labels != _E3_ABORTED_TRACE_LABELS:
        raise ValueError("E3 aborted trace labels are missing, forked, or stale")
    if ordinals != _E3_ABORTED_TRACE_ORDINALS:
        raise ValueError("E3 aborted trace ordinals are inconsistent")
    return _E3AbortedTrace(
        application=application,
        scope=scope,
        labels=labels,
        ordinals=ordinals,
    )


def _observe_e3_controller(
    transition: kernel.AcquisitionControllerTransition,
) -> _E3PublicObserver:
    """Project named public controller fields for deterministic replay comparison."""

    status = kernel.project_acquisition_controller(transition.state)
    return _E3PublicObserver(
        successor_ordinal=status.successor_ordinal,
        controller_head=status.controller_head,
        live_generation_id=status.live_generation_id,
        recovery_class=status.recovery_class,
        scope_execution_commitment=status.scope_execution_commitment,
        venue_commitment=status.venue_commitment,
        authority_context_commitment=status.authority_context_commitment,
        protection_commitment=status.protection_commitment,
    )


def _replay_e3_aborted_trace(
    trace: _E3AbortedTrace,
) -> tuple[_E3PublicObserver, ...]:
    """Replay the finite test-owned command plan from public genesis."""

    schedule = _approved_acquisition_mandates_fixture()
    assert trace.labels == _E3_ABORTED_TRACE_LABELS
    assert trace.ordinals == _E3_ABORTED_TRACE_ORDINALS
    current = _initialize_e3_controller(schedule[0])
    observations = [_observe_e3_controller(current)]
    assert observations[0].successor_ordinal == trace.ordinals[0]

    for ordinal, _ in enumerate(trace.labels[1:], start=1):
        current = _advance_e3_aborted_successor(current, schedule[ordinal])
        observation = _observe_e3_controller(current)
        assert observation.successor_ordinal == trace.ordinals[ordinal]
        observations.append(observation)
    return tuple(observations)


def _build_e3_claimed_leg() -> _E3ClaimedLeg:
    """Build one ordinary BUY through public create, claim, ACK, and discovery."""

    mandate = _approved_acquisition_mandates_fixture()[0]
    initialized = _initialize_e3_controller(mandate)
    create_refresh = authority.refresh_acquisition_context(
        initialized.authority,
        initialized.execution,
        _TARGET_SCOPE,
    )
    assert (
        create_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    created = kernel.create_acquisition_effect(
        initialized.state,
        create_refresh,
        None,
        kernel.AcquisitionEffectTerms(
            quantity=kernel.Quantity(1),
            limit_price=_PRICE,
            order_type=kernel.AcquisitionOrderType.LIMIT,
            evaluation_time=1,
        ),
        kernel.AuthorityInputId("wo0152-e3-matrix-create"),
    )
    assert created.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert created.created_effect_id is not None
    effect_id = created.created_effect_id

    claim_refresh = authority.refresh_acquisition_context(
        created.authority,
        created.execution,
        _TARGET_SCOPE,
    )
    assert (
        claim_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    claimed = kernel.claim_acquisition_effect(
        created.state,
        claim_refresh,
        None,
        effect_id,
        kernel.ClaimOccurrenceId("wo0152-e3-matrix-claim"),
        kernel.AuthorityInputId("wo0152-e3-matrix-claim"),
    )
    assert claimed.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert claimed.fresh_claim is not None

    acknowledged = kernel.apply_venue_recovery_input(
        claimed.venue,
        claimed.execution,
        kernel.RecordTransportOutcome(
            input_id=kernel.VenueInputId("wo0152-e3-matrix-ack"),
            effect_id=effect_id,
            state=kernel.BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    assert acknowledged.disposition is kernel.VenueRecoveryDisposition.APPLIED
    discovered = kernel.apply_venue_recovery_input(
        acknowledged.book,
        acknowledged.execution,
        kernel.DiscoverVenueLeg(
            input_id=kernel.VenueInputId("wo0152-e3-matrix-discover"),
            effect_id=effect_id,
            leg_key=_TARGET_LEG,
            observation_id=kernel.VenueObservationId("wo0152-e3-matrix-discover"),
        ),
    )
    assert discovered.disposition is kernel.VenueRecoveryDisposition.APPLIED
    return _E3ClaimedLeg(
        mandate=mandate,
        claimed=claimed,
        acknowledged=acknowledged,
        discovered=discovered,
        effect_id=effect_id,
        leg_key=_TARGET_LEG,
    )


def _e3_market_occurrence(
    mandate: kernel.ProtectionMandate,
    *,
    bid: int,
    sequence: int,
    source_time: int,
    label: str,
    halted: bool = False,
) -> kernel.MarketOccurrence:
    """Construct one deterministic public market occurrence for the fixed mandate."""

    del label
    return kernel.MarketOccurrence(
        source_id=mandate.evidence_policy.source_id,
        stream_generation=mandate.evidence_policy.stream_generation,
        position_scope=mandate.position_scope,
        session_id=mandate.session_id,
        market_epoch=0,
        source_sequence=sequence,
        source_time=source_time,
        evaluation_time=source_time,
        kind=kernel.MarketKind.BEST_BID,
        best_bid=replace(_PRICE, units=kernel.PriceUnits(bid)),
        best_ask=replace(_PRICE, units=kernel.PriceUnits(bid + 1)),
        trade_price=None,
        atr_distance=None,
        structure_trail=None,
        halted=halted,
    )


def _build_rooted_parent_public_suffix() -> _E3RootedParentSuffix:
    """Build the one fixed public A lifecycle before certified parent closure."""

    schedule = _approved_acquisition_mandates_fixture()
    mandate = schedule[0]
    initialized = _initialize_e3_controller(mandate)

    create_refresh = authority.refresh_acquisition_context(
        initialized.authority,
        initialized.execution,
        _TARGET_SCOPE,
    )
    assert (
        create_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    created = kernel.create_acquisition_effect(
        initialized.state,
        create_refresh,
        None,
        kernel.AcquisitionEffectTerms(
            quantity=kernel.Quantity(1),
            limit_price=_PRICE,
            order_type=kernel.AcquisitionOrderType.LIMIT,
            evaluation_time=1,
        ),
        kernel.AuthorityInputId("wo0152-e3-rooted-a-create"),
    )
    assert created.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert created.created_effect_id is not None
    assert created.fresh_claim is None
    effect_id = created.created_effect_id

    claim_occurrence_id = kernel.ClaimOccurrenceId("wo0152-e3-rooted-a-claim")
    claim_refresh = authority.refresh_acquisition_context(
        created.authority,
        created.execution,
        _TARGET_SCOPE,
    )
    assert (
        claim_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    claimed = kernel.claim_acquisition_effect(
        created.state,
        claim_refresh,
        None,
        effect_id,
        claim_occurrence_id,
        kernel.AuthorityInputId("wo0152-e3-rooted-a-claim"),
    )
    assert claimed.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert claimed.created_effect_id is None
    assert claimed.fresh_claim is not None
    assert claimed.fresh_claim.effect_id == effect_id
    assert claimed.fresh_claim.claim_occurrence_id == claim_occurrence_id

    acknowledged = kernel.apply_venue_recovery_input(
        claimed.venue,
        claimed.execution,
        kernel.RecordTransportOutcome(
            input_id=kernel.VenueInputId("wo0152-e3-rooted-a-ack"),
            effect_id=effect_id,
            state=kernel.BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    assert acknowledged.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert acknowledged.quantity_delta == 0

    discovered = kernel.apply_venue_recovery_input(
        acknowledged.book,
        acknowledged.execution,
        kernel.DiscoverVenueLeg(
            input_id=kernel.VenueInputId("wo0152-e3-rooted-a-discover"),
            effect_id=effect_id,
            leg_key=_TARGET_LEG,
            observation_id=kernel.VenueObservationId("wo0152-e3-rooted-a-discover"),
        ),
    )
    assert discovered.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert discovered.quantity_delta == 0

    root_fill = kernel.BrokerFillFact(
        key=kernel.ExecutionFactKey(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            source_event_id=kernel.SourceEventId("wo0152-e3-rooted-a-fill"),
        ),
        scope=kernel.ExecutionScope(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            order_id=_TARGET_LEG.order_id,
            symbol_id=_TARGET_SCOPE.symbol_id,
            side=kernel.ExecutionSide.BUY,
        ),
        root_fill_id=kernel.RootFillId("wo0152-e3-rooted-a-root"),
        quantity=kernel.Quantity(1),
        price=_PRICE,
    )
    filled = kernel.apply_venue_recovery_input(
        discovered.book,
        discovered.execution,
        kernel.RecordBrokerFillEvidence(
            input_id=kernel.VenueInputId("wo0152-e3-rooted-a-fill"),
            effect_id=effect_id,
            leg_key=_TARGET_LEG,
            prior_cumulative_quantity=kernel.Quantity(0),
            resulting_cumulative_quantity=kernel.Quantity(1),
            fact=root_fill,
            evidence_digest=b"\xa1" * 32,
        ),
    )
    assert filled.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert filled.quantity_delta == 1

    rooted = kernel.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert rooted.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert rooted.protection is not None
    assert rooted.execution is filled.execution
    assert rooted.venue is filled.book
    assert rooted.authority.venue is filled.book
    assert rooted.execution.position.raw_quantity == 1
    assert rooted.protection.raw_quantity == 1

    terminal = kernel.apply_venue_recovery_input(
        rooted.venue,
        rooted.execution,
        kernel.ObserveVenueStatus(
            input_id=kernel.VenueInputId("wo0152-e3-rooted-a-terminal"),
            leg_key=_TARGET_LEG,
            status=kernel.VenueAttemptState.FILLED,
            observation_id=kernel.VenueObservationId("wo0152-e3-rooted-a-terminal"),
            cumulative_quantity=kernel.Quantity(1),
            closure_id=kernel.ClosureId("wo0152-e3-rooted-a-terminal"),
            evidence_reference=kernel.EvidenceReference("wo0152-e3-rooted-a-terminal"),
        ),
    )
    assert terminal.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert terminal.quantity_delta == 0

    terminal_protection = kernel.reduce_position_protection(
        rooted.protection,
        kernel.project_protection_venue(terminal, mandate.protection_mandate),
    )
    assert terminal_protection.disposition is kernel.ProtectionDisposition.APPLIED

    bust = kernel.BrokerTradeBustFact(
        key=kernel.ExecutionFactKey(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            source_event_id=kernel.SourceEventId("wo0152-e3-rooted-a-bust"),
        ),
        scope=root_fill.scope,
        root_fill_id=root_fill.root_fill_id,
        predecessor_source_event_id=root_fill.key.source_event_id,
        reported_price=_PRICE,
    )
    busted = kernel.apply_venue_recovery_input(
        terminal.book,
        terminal.execution,
        kernel.RecordBrokerRevisionEvidence(
            input_id=kernel.VenueInputId("wo0152-e3-rooted-a-bust"),
            effect_id=effect_id,
            leg_key=_TARGET_LEG,
            prior_root_quantity=kernel.Quantity(1),
            prior_venue_cumulative_quantity=kernel.Quantity(1),
            resulting_venue_cumulative_quantity=kernel.Quantity(0),
            fact=bust,
            evidence_digest=b"\xa2" * 32,
            closure_id=kernel.ClosureId("wo0152-e3-rooted-a-bust"),
            evidence_reference=kernel.EvidenceReference("wo0152-e3-rooted-a-bust"),
        ),
    )
    assert busted.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert busted.quantity_delta == -1

    flat = kernel.reduce_acquisition_controller(
        rooted.state,
        busted,
        terminal_protection.state,
        rooted.authority,
    )
    assert flat.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert flat.venue is busted.book
    assert flat.execution is busted.execution
    assert flat.authority.venue is busted.book
    assert flat.protection is not None
    assert flat.execution.position.raw_quantity == 0
    assert flat.execution.integrity is kernel.PositionIntegrity.CONSISTENT
    assert not flat.execution.account_reconciliation_required
    assert flat.protection.raw_quantity == 0
    status = kernel.project_acquisition_controller(flat.state)
    assert status.recovery_class is kernel.AcquisitionRecoveryClass.NORMAL

    return _E3RootedParentSuffix(
        schedule=schedule,
        mandate=mandate,
        flat=flat,
        effect_id=effect_id,
        claim_occurrence_id=claim_occurrence_id,
        leg_key=_TARGET_LEG,
        root_fill=root_fill,
    )


def _certify_external_closure(
    book: kernel.VenueRecoveryBook,
    effect: venue.BrokerEffect,
    proof: venue.AcceptanceProof,
) -> bool:
    """Test-only stand-in for the fixed deferred adapter certification boundary."""

    del book, effect, proof
    return True


def _certified_terminal_parent_fixture() -> _E3CertifiedParent:
    """Apply the sole certified internal closure after the fixed public suffix."""

    suffix = _build_rooted_parent_public_suffix()
    flat = suffix.flat
    assert flat.protection is not None
    refresh = authority.refresh_acquisition_context(
        flat.authority,
        flat.execution,
        _TARGET_SCOPE,
    )
    assert refresh.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    assert refresh.authority is flat.authority
    assert refresh.execution is flat.execution
    assert refresh.venue_transitions == ()
    assert refresh.matches_current(flat.authority, _APPLICATION, _TARGET_SCOPE)

    effect = flat.venue.effect(suffix.effect_id)
    assert effect is not None
    assert effect.scope.position_scope == _TARGET_SCOPE
    assert effect.scope.generation == _APPLICATION
    assert effect.scope.effect_id == suffix.effect_id
    assert effect.scope.mandate_id == suffix.mandate.protection_mandate.mandate_id
    assert effect.scope.kind is kernel.EffectKind.SUBMIT
    assert effect.scope.side is kernel.ExecutionSide.BUY
    assert effect.scope.quantity == kernel.Quantity(1)
    assert effect.state is kernel.BrokerEffectState.ACKNOWLEDGED
    assert effect.acceptance_set_state is kernel.AcceptanceSetState.OPEN
    assert effect.acceptance_proof is None
    assert effect.claim_occurrence_id == suffix.claim_occurrence_id

    effect_view = authority.project_acquisition_effect(flat.authority, suffix.effect_id)
    assert effect_view is not None
    assert effect_view.effect_id == suffix.effect_id
    assert effect_view.position_scope == _TARGET_SCOPE
    assert effect_view.binding_commitment == suffix.mandate.binding.commitment
    assert effect_view.terms.quantity == kernel.Quantity(1)

    owner = flat.venue.owner(suffix.leg_key)
    assert owner is not None
    assert owner.leg_key == suffix.leg_key
    assert owner.effect_id == suffix.effect_id
    assert owner.effect_scope == effect.scope
    assert flat.venue.active_attempt(suffix.leg_key) is None
    closure_head = flat.venue.closure_head(suffix.leg_key)
    assert closure_head is not None
    assert closure_head.closure_id == kernel.ClosureId("wo0152-e3-rooted-a-bust")
    assert closure_head.status is kernel.VenueAttemptState.FILLED
    assert closure_head.cumulative_quantity == kernel.Quantity(0)
    assert closure_head.observed_cumulative_quantity == kernel.Quantity(1)
    assert closure_head.evidence_reference == kernel.EvidenceReference(
        "wo0152-e3-rooted-a-bust"
    )
    assert closure_head.kind is kernel.VenueClosureKind.BROKER_ECONOMIC
    binding = flat.venue.execution_binding(_TARGET_SCOPE)
    assert binding is not None
    assert binding.position_scope == _TARGET_SCOPE
    assert flat.execution.position.raw_quantity == 0
    assert flat.execution.integrity is kernel.PositionIntegrity.CONSISTENT
    assert not flat.execution.account_reconciliation_required
    status = kernel.project_acquisition_controller(flat.state)
    assert status.application_generation_id == _APPLICATION
    assert status.position_scope == _TARGET_SCOPE
    assert status.live_generation_id is not None
    assert status.recovery_class is kernel.AcquisitionRecoveryClass.NORMAL
    assert flat.venue is flat.authority.venue
    assert flat.venue.effect(suffix.effect_id) == effect

    proof = venue.AcceptanceProof(
        kind=venue.AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
        effect_scope=effect.scope,
        claim_occurrence_id=suffix.claim_occurrence_id,
        evidence_reference=kernel.EvidenceReference("wo0152-e3-rooted-a-parent-proof"),
        evidence_digest=b"\xa3" * 32,
    )
    close = venue.CloseAcceptanceSet(
        input_id=kernel.VenueInputId("wo0152-e3-rooted-a-parent-close"),
        effect_id=suffix.effect_id,
        proof=proof,
    )
    with patch.object(
        venue,
        "_external_acceptance_closure_is_certified",
        _certify_external_closure,
    ):
        applied = venue._apply_venue_input(flat.venue, flat.execution, close)
    assert applied.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert applied.quantity_delta == 0
    closed_effect = applied.book.effect(suffix.effect_id)
    assert closed_effect is not None
    assert closed_effect.acceptance_set_state is kernel.AcceptanceSetState.CLOSED
    assert closed_effect.acceptance_proof == proof

    closed_protection = kernel.reduce_position_protection(
        flat.protection,
        kernel.project_protection_venue(applied, suffix.mandate.protection_mandate),
    )
    assert closed_protection.disposition is kernel.ProtectionDisposition.APPLIED
    assert closed_protection.state.policy is kernel.ProtectionPolicy.FLAT
    assert closed_protection.state.raw_quantity == 0

    copied_authority = copy.copy(flat.authority)
    object.__setattr__(copied_authority, "venue", applied.book)
    assert copied_authority.phase is flat.authority.phase
    assert copied_authority.mode is flat.authority.mode
    assert copied_authority.supervisor_fence is flat.authority.supervisor_fence
    assert copied_authority.kill_engaged is flat.authority.kill_engaged
    assert copied_authority.session_id is flat.authority.session_id
    assert copied_authority.budget is flat.authority.budget
    closed_refresh = authority.refresh_acquisition_context(
        copied_authority,
        applied.execution,
        _TARGET_SCOPE,
    )
    assert (
        closed_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    assert closed_refresh.matches_current(copied_authority, _APPLICATION, _TARGET_SCOPE)

    return _E3CertifiedParent(
        schedule=suffix.schedule,
        state=flat.state,
        authority=copied_authority,
        execution=applied.execution,
        protection=closed_protection.state,
        effect_id=suffix.effect_id,
        claim_occurrence_id=suffix.claim_occurrence_id,
        leg_key=suffix.leg_key,
        root_fill=suffix.root_fill,
    )


def _build_rooted_a_to_b_unclaimed_effect() -> _E3RootedBEffect:
    """Retire fixed A into B, then create B's first effect without claiming it."""

    parent = _certified_terminal_parent_fixture()
    a_status = kernel.project_acquisition_controller(parent.state)
    assert a_status.live_generation_id is not None
    successor_refresh = authority.refresh_acquisition_context(
        parent.authority,
        parent.execution,
        _TARGET_SCOPE,
    )
    assert (
        successor_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    bootstrap = parent.authority.venue.project_acquisition_bootstrap(
        parent.execution,
        _TARGET_SCOPE,
    )
    assert bootstrap.matches_bootstrap(
        parent.execution,
        parent.authority.venue,
        _TARGET_SCOPE,
    )
    admission = authority.project_acquisition_admission(
        parent.authority,
        parent.execution,
        _TARGET_SCOPE,
    )
    assert admission.kind is authority.AcquisitionAdmissionKind.SUCCESSOR
    assert admission.permits_successor(_APPLICATION, parent.execution, _TARGET_SCOPE)
    successor = kernel.begin_acquisition_generation(
        parent.state,
        parent.schedule[1],
        bootstrap,
        admission,
        successor_refresh,
        parent.protection,
    )
    assert successor.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert successor.created_effect_id is None
    assert successor.fresh_claim is None
    assert successor.protection is None
    b_status = kernel.project_acquisition_controller(successor.state)
    assert b_status.successor_ordinal == 1
    assert b_status.live_generation_id is not None
    assert b_status.live_generation_id != a_status.live_generation_id
    assert b_status.recovery_class is kernel.AcquisitionRecoveryClass.NORMAL

    create_refresh = authority.refresh_acquisition_context(
        successor.authority,
        successor.execution,
        _TARGET_SCOPE,
    )
    assert (
        create_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    created = kernel.create_acquisition_effect(
        successor.state,
        create_refresh,
        None,
        kernel.AcquisitionEffectTerms(
            quantity=kernel.Quantity(1),
            limit_price=_PRICE,
            order_type=kernel.AcquisitionOrderType.LIMIT,
            evaluation_time=2,
        ),
        kernel.AuthorityInputId("wo0152-e3-rooted-b-create"),
    )
    assert created.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert created.created_effect_id is not None
    assert created.fresh_claim is None
    return _E3RootedBEffect(
        parent=parent,
        created=created,
        retired_a_generation_id=a_status.live_generation_id,
        live_b_generation_id=b_status.live_generation_id,
    )


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
            session_id=_E3_SESSION,
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


def test_e3_fixed_schedule_is_complete_and_configuration_consistent() -> None:
    """The pre-genesis schedule is a fixed, complete 32-generation input set."""

    schedule = _approved_acquisition_mandates_fixture()

    assert type(schedule) is tuple
    assert len(schedule) == 32
    assert schedule[0].acquisition_mandate_id.value.endswith("-A")
    assert schedule[1].acquisition_mandate_id.value.endswith("-B")
    assert schedule[2].acquisition_mandate_id.value.endswith("-C")

    acquisition_ids = {mandate.acquisition_mandate_id for mandate in schedule}
    protection_ids = {mandate.protection_mandate.mandate_id for mandate in schedule}
    stream_generations = {
        mandate.protection_mandate.evidence_policy.stream_generation
        for mandate in schedule
    }
    binding_commitments = {mandate.binding.commitment for mandate in schedule}
    compatibility_commitments = {
        mandate.protection_mandate.emergency_recovery_compatibility.commitment
        for mandate in schedule
    }

    assert len(acquisition_ids) == len(schedule)
    assert len(protection_ids) == len(schedule)
    assert len(stream_generations) == len(schedule)
    assert len(binding_commitments) == len(schedule)
    assert compatibility_commitments == {_E3_COMPATIBILITY.commitment}
    assert all(mandate.position_scope == _TARGET_SCOPE for mandate in schedule)
    assert all(mandate.session_id == _E3_SESSION for mandate in schedule)
    assert all(
        mandate.protection_mandate.position_scope == _TARGET_SCOPE
        and mandate.protection_mandate.session_id == _E3_SESSION
        and mandate.binding.acquisition_mandate_id == mandate.acquisition_mandate_id
        and mandate.binding.protection_mandate_id
        == mandate.protection_mandate.mandate_id
        and mandate.binding.position_scope == mandate.position_scope
        and mandate.binding.session_id == mandate.session_id
        for mandate in schedule
    )


def test_e3_public_32_generation_aborted_chain_keeps_exactly_one_live_generation() -> (
    None
):
    """A bounded public A..AF chain preserves serial identity and one LIVE slot."""

    schedule = _approved_acquisition_mandates_fixture()
    current = _initialize_e3_controller(schedule[0])
    first_status = kernel.project_acquisition_controller(current.state)
    first_generation_id = first_status.live_generation_id
    assert first_generation_id is not None

    seen_generation_ids = {first_generation_id}
    for ordinal, mandate in enumerate(schedule[1:], start=1):
        predecessor_status = kernel.project_acquisition_controller(current.state)
        predecessor_generation_id = predecessor_status.live_generation_id
        assert predecessor_generation_id is not None
        current = _advance_e3_aborted_successor(current, mandate)

        status = kernel.project_acquisition_controller(current.state)
        current_generation_id = status.live_generation_id
        assert current_generation_id is not None
        assert current_generation_id not in seen_generation_ids
        assert status.successor_ordinal == ordinal
        assert status.recovery_class is kernel.AcquisitionRecoveryClass.NORMAL
        current_record = current.state.registry.record(current_generation_id)
        predecessor_record = current.state.registry.record(predecessor_generation_id)
        first_record = current.state.registry.record(first_generation_id)
        assert current_record is not None
        assert predecessor_record is not None
        assert first_record is not None
        assert current_record.serving_class is kernel.GenerationServingClass.LIVE
        assert (
            predecessor_record.serving_class
            is kernel.GenerationServingClass.RETIRED_UNSERVING
        )
        assert (
            first_record.serving_class
            is kernel.GenerationServingClass.RETIRED_UNSERVING
        )
        assert status.live_generation_id == current_generation_id
        seen_generation_ids.add(current_generation_id)

    assert len(seen_generation_ids) == len(schedule)
    final_status = kernel.project_acquisition_controller(current.state)
    assert final_status.successor_ordinal == 31
    assert final_status.live_generation_id is not None
    final_record = current.state.registry.record(final_status.live_generation_id)
    assert final_record is not None
    assert final_record.serving_class is kernel.GenerationServingClass.LIVE


def test_e3_schema_neutral_aborted_trace_replays_named_public_observers() -> None:
    """A finite command codec replays from public genesis without hydration claims."""

    trace = _E3AbortedTrace(
        application=_E3_TRACE_APPLICATION,
        scope=_E3_TRACE_SCOPE,
        labels=_E3_ABORTED_TRACE_LABELS,
        ordinals=_E3_ABORTED_TRACE_ORDINALS,
    )
    encoded = _encode_e3_aborted_trace(trace)
    decoded = _decode_e3_aborted_trace(encoded)

    uninterrupted = _replay_e3_aborted_trace(decoded)
    restarted = _replay_e3_aborted_trace(_decode_e3_aborted_trace(encoded))

    assert uninterrupted == restarted
    assert len(uninterrupted) == 32
    assert uninterrupted[0].successor_ordinal == 0
    assert uninterrupted[-1].successor_ordinal == 31
    assert all(
        observer.recovery_class is kernel.AcquisitionRecoveryClass.NORMAL
        and observer.protection_commitment is None
        and observer.live_generation_id is not None
        for observer in uninterrupted
    )
    assert len({observer.live_generation_id for observer in uninterrupted}) == 32


def test_e3_schema_neutral_aborted_trace_rejects_corruption_before_replay() -> None:
    """Missing, duplicate, forked, stale, inconsistent, and foreign traces fail early."""

    encoded = _encode_e3_aborted_trace(
        _E3AbortedTrace(
            application=_E3_TRACE_APPLICATION,
            scope=_E3_TRACE_SCOPE,
            labels=_E3_ABORTED_TRACE_LABELS,
            ordinals=_E3_ABORTED_TRACE_ORDINALS,
        )
    )
    corruptions = (
        (
            "other-application",
            _E3_TRACE_SCOPE,
            _E3_ABORTED_TRACE_LABELS,
            _E3_ABORTED_TRACE_ORDINALS,
        ),
        (
            _E3_TRACE_APPLICATION,
            (*_E3_TRACE_SCOPE[:3], "MSFT"),
            _E3_ABORTED_TRACE_LABELS,
            _E3_ABORTED_TRACE_ORDINALS,
        ),
        (
            _E3_TRACE_APPLICATION,
            _E3_TRACE_SCOPE,
            _E3_ABORTED_TRACE_LABELS[:-1],
            _E3_ABORTED_TRACE_ORDINALS[:-1],
        ),
        (
            _E3_TRACE_APPLICATION,
            _E3_TRACE_SCOPE,
            ("A", "A", *_E3_ABORTED_TRACE_LABELS[2:]),
            _E3_ABORTED_TRACE_ORDINALS,
        ),
        (
            _E3_TRACE_APPLICATION,
            _E3_TRACE_SCOPE,
            (*_E3_ABORTED_TRACE_LABELS[1:], "A"),
            _E3_ABORTED_TRACE_ORDINALS,
        ),
        (
            _E3_TRACE_APPLICATION,
            _E3_TRACE_SCOPE,
            _E3_ABORTED_TRACE_LABELS,
            (0, 2, *_E3_ABORTED_TRACE_ORDINALS[2:]),
        ),
    )

    for corrupted in corruptions:
        replay_invoked = False
        try:
            decoded = _decode_e3_aborted_trace(corrupted)
        except ValueError:
            pass
        else:
            replay_invoked = True
            _replay_e3_aborted_trace(decoded)
        assert not replay_invoked

    assert _decode_e3_aborted_trace(encoded).labels == _E3_ABORTED_TRACE_LABELS


def test_e3_rooted_a_parent_closes_before_public_b_successor() -> None:
    """A flat, certified A parent retires before B becomes the sole LIVE generation."""

    rooted = _build_rooted_a_to_b_unclaimed_effect()
    created = rooted.created
    b_status = kernel.project_acquisition_controller(created.state)
    assert b_status.successor_ordinal == 1
    assert b_status.live_generation_id == rooted.live_b_generation_id
    assert b_status.recovery_class is kernel.AcquisitionRecoveryClass.NORMAL
    a_record = created.state.registry.record(rooted.retired_a_generation_id)
    b_record = created.state.registry.record(rooted.live_b_generation_id)
    assert a_record is not None
    assert b_record is not None
    assert a_record.serving_class is kernel.GenerationServingClass.RETIRED_UNSERVING
    assert b_record.serving_class is kernel.GenerationServingClass.LIVE
    assert created.created_effect_id is not None
    assert created.fresh_claim is None


def test_e3_late_retired_a_fact_chain_preserves_b_and_refuses_stale_claim() -> None:
    """Late canonical A FILL/CORRECT/BUST updates only retired A under live B."""

    rooted = _build_rooted_a_to_b_unclaimed_effect()
    created = rooted.created
    stale_claim_refresh = authority.refresh_acquisition_context(
        created.authority,
        created.execution,
        _TARGET_SCOPE,
    )
    assert (
        stale_claim_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    assert stale_claim_refresh.matches_current(
        created.authority,
        _APPLICATION,
        _TARGET_SCOPE,
    )
    a_before = created.state.registry.record(rooted.retired_a_generation_id)
    b_before = created.state.registry.record(rooted.live_b_generation_id)
    assert a_before is not None
    assert b_before is not None
    initial_seen_count = created.execution.seen_facts.count

    late_fill = kernel.BrokerFillFact(
        key=kernel.ExecutionFactKey(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            source_event_id=kernel.SourceEventId("wo0152-e3-late-a-fill"),
        ),
        scope=rooted.parent.root_fill.scope,
        root_fill_id=kernel.RootFillId("wo0152-e3-late-a-root"),
        quantity=kernel.Quantity(1),
        price=_PRICE,
    )
    filled = kernel.apply_venue_recovery_input(
        created.authority.venue,
        created.execution,
        kernel.RecordBrokerFillEvidence(
            input_id=kernel.VenueInputId("wo0152-e3-late-a-fill"),
            effect_id=rooted.parent.effect_id,
            leg_key=rooted.parent.leg_key,
            prior_cumulative_quantity=kernel.Quantity(0),
            resulting_cumulative_quantity=kernel.Quantity(1),
            fact=late_fill,
            evidence_digest=b"\xb1" * 32,
            closure_id=kernel.ClosureId("wo0152-e3-late-a-fill"),
            evidence_reference=kernel.EvidenceReference("wo0152-e3-late-a-fill"),
        ),
    )
    assert filled.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert filled.quantity_delta == 1
    after_fill = kernel.reduce_acquisition_controller(
        created.state,
        filled,
        created.protection,
        created.authority,
    )
    assert after_fill.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert after_fill.created_effect_id is None
    assert after_fill.fresh_claim is None
    assert after_fill.execution.position.raw_quantity == 1
    assert after_fill.execution.seen_facts.count == initial_seen_count + 1
    assert after_fill.execution.seen_facts.get(late_fill.key) is not None
    assert after_fill.protection is not None
    assert after_fill.protection.policy is kernel.ProtectionPolicy.HARD_BAIL
    fill_status = kernel.project_acquisition_controller(after_fill.state)
    assert fill_status.live_generation_id == rooted.live_b_generation_id
    assert fill_status.successor_ordinal == 1
    assert (
        fill_status.recovery_class
        is kernel.AcquisitionRecoveryClass.MIXED_GENERATION_RECOVERY
    )
    a_after_fill = after_fill.state.registry.record(rooted.retired_a_generation_id)
    b_after_fill = after_fill.state.registry.record(rooted.live_b_generation_id)
    assert a_after_fill is not None
    assert b_after_fill == b_before
    assert a_after_fill.economics_head_commitment != a_before.economics_head_commitment
    fill_route = after_fill.state.lineage.route_fact(late_fill.key)
    assert fill_route is not None
    assert fill_route.generation_id == rooted.retired_a_generation_id

    correction = kernel.BrokerTradeCorrectFact(
        key=kernel.ExecutionFactKey(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            source_event_id=kernel.SourceEventId("wo0152-e3-late-a-correct"),
        ),
        scope=late_fill.scope,
        root_fill_id=late_fill.root_fill_id,
        predecessor_source_event_id=late_fill.key.source_event_id,
        revised_quantity=kernel.Quantity(2),
        revised_price=_PRICE,
    )
    corrected = kernel.apply_venue_recovery_input(
        after_fill.venue,
        after_fill.execution,
        kernel.RecordBrokerRevisionEvidence(
            input_id=kernel.VenueInputId("wo0152-e3-late-a-correct"),
            effect_id=rooted.parent.effect_id,
            leg_key=rooted.parent.leg_key,
            prior_root_quantity=kernel.Quantity(1),
            prior_venue_cumulative_quantity=kernel.Quantity(1),
            resulting_venue_cumulative_quantity=kernel.Quantity(2),
            fact=correction,
            evidence_digest=b"\xb2" * 32,
            closure_id=kernel.ClosureId("wo0152-e3-late-a-correct"),
            evidence_reference=kernel.EvidenceReference("wo0152-e3-late-a-correct"),
        ),
    )
    assert corrected.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert corrected.quantity_delta == 1
    after_correct = kernel.reduce_acquisition_controller(
        after_fill.state,
        corrected,
        after_fill.protection,
        after_fill.authority,
    )
    assert after_correct.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert after_correct.created_effect_id is None
    assert after_correct.fresh_claim is None
    assert after_correct.execution.position.raw_quantity == 2
    assert after_correct.execution.seen_facts.count == initial_seen_count + 2
    assert after_correct.execution.seen_facts.get(correction.key) is not None
    assert after_correct.protection is not None
    assert after_correct.protection.policy is kernel.ProtectionPolicy.HARD_BAIL
    correct_status = kernel.project_acquisition_controller(after_correct.state)
    assert correct_status.live_generation_id == rooted.live_b_generation_id
    assert correct_status.successor_ordinal == 1
    assert (
        correct_status.recovery_class
        is kernel.AcquisitionRecoveryClass.MIXED_GENERATION_RECOVERY
    )
    a_after_correct = after_correct.state.registry.record(
        rooted.retired_a_generation_id
    )
    b_after_correct = after_correct.state.registry.record(rooted.live_b_generation_id)
    assert a_after_correct is not None
    assert b_after_correct == b_before
    assert (
        a_after_correct.economics_head_commitment
        != a_after_fill.economics_head_commitment
    )
    correct_route = after_correct.state.lineage.route_fact(correction.key)
    assert correct_route is not None
    assert correct_route.generation_id == rooted.retired_a_generation_id

    bust = kernel.BrokerTradeBustFact(
        key=kernel.ExecutionFactKey(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            source_event_id=kernel.SourceEventId("wo0152-e3-late-a-bust"),
        ),
        scope=late_fill.scope,
        root_fill_id=late_fill.root_fill_id,
        predecessor_source_event_id=correction.key.source_event_id,
        reported_price=_PRICE,
    )
    busted = kernel.apply_venue_recovery_input(
        after_correct.venue,
        after_correct.execution,
        kernel.RecordBrokerRevisionEvidence(
            input_id=kernel.VenueInputId("wo0152-e3-late-a-bust"),
            effect_id=rooted.parent.effect_id,
            leg_key=rooted.parent.leg_key,
            prior_root_quantity=kernel.Quantity(2),
            prior_venue_cumulative_quantity=kernel.Quantity(2),
            resulting_venue_cumulative_quantity=kernel.Quantity(0),
            fact=bust,
            evidence_digest=b"\xb3" * 32,
            closure_id=kernel.ClosureId("wo0152-e3-late-a-bust"),
            evidence_reference=kernel.EvidenceReference("wo0152-e3-late-a-bust"),
        ),
    )
    assert busted.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert busted.quantity_delta == -2
    after_bust = kernel.reduce_acquisition_controller(
        after_correct.state,
        busted,
        after_correct.protection,
        after_correct.authority,
    )
    assert after_bust.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert after_bust.created_effect_id is None
    assert after_bust.fresh_claim is None
    assert after_bust.execution.position.raw_quantity == 0
    assert after_bust.execution.seen_facts.count == initial_seen_count + 3
    assert after_bust.execution.seen_facts.get(bust.key) is not None
    assert after_bust.protection is not None
    assert after_bust.protection.policy is kernel.ProtectionPolicy.HARD_BAIL
    bust_status = kernel.project_acquisition_controller(after_bust.state)
    assert bust_status.live_generation_id == rooted.live_b_generation_id
    assert bust_status.successor_ordinal == 1
    assert (
        bust_status.recovery_class
        is kernel.AcquisitionRecoveryClass.MIXED_GENERATION_RECOVERY
    )
    a_after_bust = after_bust.state.registry.record(rooted.retired_a_generation_id)
    b_after_bust = after_bust.state.registry.record(rooted.live_b_generation_id)
    assert a_after_bust is not None
    assert b_after_bust == b_before
    assert (
        a_after_bust.economics_head_commitment
        != a_after_correct.economics_head_commitment
    )
    bust_route = after_bust.state.lineage.route_fact(bust.key)
    assert bust_route is not None
    assert bust_route.generation_id == rooted.retired_a_generation_id

    assert not stale_claim_refresh.matches_current(
        after_bust.authority,
        _APPLICATION,
        _TARGET_SCOPE,
    )
    assert created.created_effect_id is not None
    stale_claim = kernel.claim_acquisition_effect(
        after_bust.state,
        stale_claim_refresh,
        after_bust.protection,
        created.created_effect_id,
        kernel.ClaimOccurrenceId("wo0152-e3-stale-b-claim"),
        kernel.AuthorityInputId("wo0152-e3-stale-b-claim"),
    )
    assert stale_claim.disposition is kernel.AcquisitionControllerDisposition.REFUSED
    assert stale_claim.state is after_bust.state
    assert stale_claim.created_effect_id is None
    assert stale_claim.fresh_claim is None


def test_e3_late_a_fill_after_b_first_fill_preserves_b_generation_authority() -> None:
    """A retired fact after B's first fill cannot replace B's live authority."""

    rooted = _build_rooted_a_to_b_unclaimed_effect()
    created = rooted.created
    assert created.created_effect_id is not None
    b_effect_id = created.created_effect_id
    claim_refresh = authority.refresh_acquisition_context(
        created.authority,
        created.execution,
        _TARGET_SCOPE,
    )
    assert (
        claim_refresh.disposition
        is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    claimed = kernel.claim_acquisition_effect(
        created.state,
        claim_refresh,
        None,
        b_effect_id,
        kernel.ClaimOccurrenceId("wo0152-e3-b-first-claim"),
        kernel.AuthorityInputId("wo0152-e3-b-first-claim"),
    )
    assert claimed.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert claimed.fresh_claim is not None
    assert claimed.fresh_claim.effect_id == b_effect_id

    b_leg = kernel.VenueLegKey(
        broker=_BROKER,
        environment=_ENVIRONMENT,
        account=_ACCOUNT,
        order_id=kernel.OrderId("wo0152-e3-b-first-leg"),
    )
    acknowledged = kernel.apply_venue_recovery_input(
        claimed.venue,
        claimed.execution,
        kernel.RecordTransportOutcome(
            input_id=kernel.VenueInputId("wo0152-e3-b-first-ack"),
            effect_id=b_effect_id,
            state=kernel.BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    assert acknowledged.disposition is kernel.VenueRecoveryDisposition.APPLIED
    discovered = kernel.apply_venue_recovery_input(
        acknowledged.book,
        acknowledged.execution,
        kernel.DiscoverVenueLeg(
            input_id=kernel.VenueInputId("wo0152-e3-b-first-discover"),
            effect_id=b_effect_id,
            leg_key=b_leg,
            observation_id=kernel.VenueObservationId("wo0152-e3-b-first-discover"),
        ),
    )
    assert discovered.disposition is kernel.VenueRecoveryDisposition.APPLIED
    reviewed = kernel.apply_venue_recovery_input(
        discovered.book,
        discovered.execution,
        kernel.ObserveVenueStatus(
            input_id=kernel.VenueInputId("wo0152-e3-b-first-needs-review"),
            leg_key=b_leg,
            status=kernel.VenueAttemptState.NEEDS_REVIEW,
            observation_id=kernel.VenueObservationId("wo0152-e3-b-first-needs-review"),
            cumulative_quantity=kernel.Quantity(0),
        ),
    )
    assert reviewed.disposition is kernel.VenueRecoveryDisposition.APPLIED
    b_fill = kernel.BrokerFillFact(
        key=kernel.ExecutionFactKey(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            source_event_id=kernel.SourceEventId("wo0152-e3-b-first-fill"),
        ),
        scope=kernel.ExecutionScope(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            order_id=b_leg.order_id,
            symbol_id=_TARGET_SCOPE.symbol_id,
            side=kernel.ExecutionSide.BUY,
        ),
        root_fill_id=kernel.RootFillId("wo0152-e3-b-first-root"),
        quantity=kernel.Quantity(1),
        price=_PRICE,
    )
    b_filled = kernel.apply_venue_recovery_input(
        reviewed.book,
        reviewed.execution,
        kernel.RecordBrokerFillEvidence(
            input_id=kernel.VenueInputId("wo0152-e3-b-first-fill"),
            effect_id=b_effect_id,
            leg_key=b_leg,
            prior_cumulative_quantity=kernel.Quantity(0),
            resulting_cumulative_quantity=kernel.Quantity(1),
            fact=b_fill,
            evidence_digest=b"\xc1" * 32,
        ),
    )
    assert b_filled.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert b_filled.quantity_delta == 1
    b_projection = b_filled.book.project_acquisition_fact(b_filled)
    assert b_projection.matches_fact_transition(b_filled, _TARGET_SCOPE)
    assert b_projection.fact_relation() is not None
    assert (
        b_projection.predecessor_scope_execution_commitment
        == claimed.state.scope_execution_commitment
    )
    assert b_projection.predecessor_venue_commitment == claimed.state.venue_commitment
    b_status_before_fill = kernel.project_acquisition_controller(claimed.state)
    assert b_status_before_fill.protection_commitment is None
    assert b_status_before_fill.recovery_class is kernel.AcquisitionRecoveryClass.NORMAL
    assert b_status_before_fill.live_generation_id == rooted.live_b_generation_id
    b_relation = b_projection.fact_relation()
    assert b_relation is not None
    assert (
        claimed.state.lineage.route_request(b_relation.request_occurrence_id)
        is not None
    )
    assert claimed.state.lineage.route_effect(b_relation.effect_id) is not None
    assert claimed.state.lineage.route_owner(b_relation.leg_key) is None
    assert claimed.state.lineage.route_root(b_relation.root_key) is None
    assert claimed.state.lineage.route_fact(b_relation.fact_key) is None
    b_rooted = kernel.reduce_acquisition_controller(
        claimed.state,
        b_filled,
        None,
        claimed.authority,
    )
    assert b_rooted.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert b_rooted.protection is not None
    assert b_rooted.protection.raw_quantity == 1
    assert b_rooted.execution.position.raw_quantity == 1
    b_before = b_rooted.state.registry.record(rooted.live_b_generation_id)
    a_before = b_rooted.state.registry.record(rooted.retired_a_generation_id)
    assert b_before is not None
    assert a_before is not None

    late_a_fill = kernel.BrokerFillFact(
        key=kernel.ExecutionFactKey(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            source_event_id=kernel.SourceEventId("wo0152-e3-after-b-late-a-fill"),
        ),
        scope=rooted.parent.root_fill.scope,
        root_fill_id=kernel.RootFillId("wo0152-e3-after-b-late-a-root"),
        quantity=kernel.Quantity(1),
        price=_PRICE,
    )
    late_transition = kernel.apply_venue_recovery_input(
        b_rooted.venue,
        b_rooted.execution,
        kernel.RecordBrokerFillEvidence(
            input_id=kernel.VenueInputId("wo0152-e3-after-b-late-a-fill"),
            effect_id=rooted.parent.effect_id,
            leg_key=rooted.parent.leg_key,
            prior_cumulative_quantity=kernel.Quantity(0),
            resulting_cumulative_quantity=kernel.Quantity(1),
            fact=late_a_fill,
            evidence_digest=b"\xc2" * 32,
            closure_id=kernel.ClosureId("wo0152-e3-after-b-late-a-fill"),
            evidence_reference=kernel.EvidenceReference(
                "wo0152-e3-after-b-late-a-fill"
            ),
        ),
    )
    assert late_transition.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert late_transition.quantity_delta == 1
    after_late = kernel.reduce_acquisition_controller(
        b_rooted.state,
        late_transition,
        b_rooted.protection,
        b_rooted.authority,
    )
    assert after_late.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert after_late.created_effect_id is None
    assert after_late.fresh_claim is None
    assert after_late.execution.position.raw_quantity == 2
    assert after_late.protection is not None
    assert after_late.protection.policy is kernel.ProtectionPolicy.HARD_BAIL
    status = kernel.project_acquisition_controller(after_late.state)
    assert status.live_generation_id == rooted.live_b_generation_id
    assert status.successor_ordinal == 1
    assert (
        status.recovery_class
        is kernel.AcquisitionRecoveryClass.MIXED_GENERATION_RECOVERY
    )
    a_after = after_late.state.registry.record(rooted.retired_a_generation_id)
    b_after = after_late.state.registry.record(rooted.live_b_generation_id)
    assert a_after is not None
    assert b_after == b_before
    assert a_after.economics_head_commitment != a_before.economics_head_commitment
    route = after_late.state.lineage.route_fact(late_a_fill.key)
    assert route is not None
    assert route.generation_id == rooted.retired_a_generation_id


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


def test_e3_public_create_and_claim_refusal_matrix_is_nonmutating() -> None:
    """Bound, price, order, deadline, single-flight, and claim gates fail closed."""

    schedule = _approved_acquisition_mandates_fixture()
    initialized = _initialize_e3_controller(schedule[0])
    refresh = authority.refresh_acquisition_context(
        initialized.authority,
        initialized.execution,
        _TARGET_SCOPE,
    )
    assert refresh.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    variants = (
        kernel.AcquisitionEffectTerms(
            quantity=kernel.Quantity(6),
            limit_price=_PRICE,
            order_type=kernel.AcquisitionOrderType.LIMIT,
            evaluation_time=1,
        ),
        kernel.AcquisitionEffectTerms(
            quantity=kernel.Quantity(1),
            limit_price=replace(_PRICE, units=kernel.PriceUnits(101)),
            order_type=kernel.AcquisitionOrderType.LIMIT,
            evaluation_time=1,
        ),
        kernel.AcquisitionEffectTerms(
            quantity=kernel.Quantity(1),
            limit_price=_PRICE,
            order_type=kernel.AcquisitionOrderType.LIMIT,
            evaluation_time=901,
        ),
    )
    for index, terms in enumerate(variants):
        refused = kernel.create_acquisition_effect(
            initialized.state,
            refresh,
            None,
            terms,
            kernel.AuthorityInputId(f"wo0152-e3-create-refusal-{index}"),
        )
        assert refused.disposition is kernel.AcquisitionControllerDisposition.REFUSED
        assert refused.state is initialized.state
        assert refused.authority is initialized.authority
        assert refused.created_effect_id is None
        assert refused.fresh_claim is None

    normal_terms = kernel.AcquisitionEffectTerms(
        quantity=kernel.Quantity(1),
        limit_price=_PRICE,
        order_type=kernel.AcquisitionOrderType.LIMIT,
        evaluation_time=1,
    )
    created = kernel.create_acquisition_effect(
        initialized.state,
        refresh,
        None,
        normal_terms,
        kernel.AuthorityInputId("wo0152-e3-create-matrix-applied"),
    )
    assert created.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert created.created_effect_id is not None
    current = authority.refresh_acquisition_context(
        created.authority,
        created.execution,
        _TARGET_SCOPE,
    )
    single_flight = kernel.create_acquisition_effect(
        created.state,
        current,
        None,
        normal_terms,
        kernel.AuthorityInputId("wo0152-e3-create-matrix-single-flight"),
    )
    assert single_flight.disposition is kernel.AcquisitionControllerDisposition.REFUSED
    assert single_flight.state is created.state
    stale = kernel.create_acquisition_effect(
        created.state,
        refresh,
        None,
        normal_terms,
        kernel.AuthorityInputId("wo0152-e3-create-matrix-stale"),
    )
    assert stale.disposition is kernel.AcquisitionControllerDisposition.REFUSED
    assert stale.state is created.state

    unknown_claim = kernel.claim_acquisition_effect(
        created.state,
        current,
        None,
        kernel.EffectId("wo0152-e3-unknown-effect"),
        kernel.ClaimOccurrenceId("wo0152-e3-unknown-claim"),
        kernel.AuthorityInputId("wo0152-e3-unknown-claim"),
    )
    assert unknown_claim.disposition is kernel.AcquisitionControllerDisposition.REFUSED
    assert unknown_claim.state is created.state
    claimed = kernel.claim_acquisition_effect(
        created.state,
        current,
        None,
        created.created_effect_id,
        kernel.ClaimOccurrenceId("wo0152-e3-create-matrix-claim"),
        kernel.AuthorityInputId("wo0152-e3-create-matrix-claim"),
    )
    assert claimed.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    claimed_refresh = authority.refresh_acquisition_context(
        claimed.authority,
        claimed.execution,
        _TARGET_SCOPE,
    )
    duplicate_claim = kernel.claim_acquisition_effect(
        claimed.state,
        claimed_refresh,
        None,
        created.created_effect_id,
        kernel.ClaimOccurrenceId("wo0152-e3-create-matrix-claim-duplicate"),
        kernel.AuthorityInputId("wo0152-e3-create-matrix-claim-duplicate"),
    )
    assert (
        duplicate_claim.disposition is kernel.AcquisitionControllerDisposition.REFUSED
    )
    assert duplicate_claim.state is claimed.state
    stale_claim = kernel.claim_acquisition_effect(
        claimed.state,
        current,
        None,
        created.created_effect_id,
        kernel.ClaimOccurrenceId("wo0152-e3-create-matrix-claim-stale"),
        kernel.AuthorityInputId("wo0152-e3-create-matrix-claim-stale"),
    )
    assert stale_claim.disposition is kernel.AcquisitionControllerDisposition.REFUSED
    assert stale_claim.state is claimed.state


def test_e3_venue_recovery_duplicate_reorder_replay_and_fork_matrix() -> None:
    """Public broker evidence is exact-once, predecessor-linked, and fail closed."""

    recovery = _build_e3_claimed_leg()
    recovered = kernel.apply_venue_recovery_input(
        recovery.claimed.venue,
        recovery.claimed.execution,
        kernel.RecoverClaimedEffect(
            input_id=kernel.VenueInputId("wo0152-e3-matrix-recover"),
            effect_id=recovery.effect_id,
        ),
    )
    assert recovered.disposition is kernel.VenueRecoveryDisposition.APPLIED
    replay_command = kernel.RecoverClaimedEffect(
        input_id=kernel.VenueInputId("wo0152-e3-matrix-recover"),
        effect_id=recovery.effect_id,
    )
    replayed = kernel.apply_venue_recovery_input(
        recovered.book,
        recovered.execution,
        replay_command,
    )
    assert replayed.disposition is kernel.VenueRecoveryDisposition.EXACT_REPLAY
    conflicting = kernel.apply_venue_recovery_input(
        recovered.book,
        recovered.execution,
        kernel.RecoverClaimedEffect(
            input_id=replay_command.input_id,
            effect_id=kernel.EffectId("wo0152-e3-matrix-other-effect"),
        ),
    )
    assert conflicting.disposition is kernel.VenueRecoveryDisposition.CONFLICT
    repeated_recovery = kernel.apply_venue_recovery_input(
        recovered.book,
        recovered.execution,
        kernel.RecoverClaimedEffect(
            input_id=kernel.VenueInputId("wo0152-e3-matrix-recover-again"),
            effect_id=recovery.effect_id,
        ),
    )
    assert repeated_recovery.disposition is kernel.VenueRecoveryDisposition.REFUSED

    scope = kernel.ExecutionScope(
        broker=_BROKER,
        environment=_ENVIRONMENT,
        account=_ACCOUNT,
        order_id=recovery.leg_key.order_id,
        symbol_id=_TARGET_SCOPE.symbol_id,
        side=kernel.ExecutionSide.BUY,
    )
    fill = kernel.BrokerFillFact(
        key=kernel.ExecutionFactKey(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            source_event_id=kernel.SourceEventId("wo0152-e3-matrix-fill"),
        ),
        scope=scope,
        root_fill_id=kernel.RootFillId("wo0152-e3-matrix-root"),
        quantity=kernel.Quantity(1),
        price=_PRICE,
    )
    fill_command = kernel.RecordBrokerFillEvidence(
        input_id=kernel.VenueInputId("wo0152-e3-matrix-fill"),
        effect_id=recovery.effect_id,
        leg_key=recovery.leg_key,
        prior_cumulative_quantity=kernel.Quantity(0),
        resulting_cumulative_quantity=kernel.Quantity(1),
        fact=fill,
        evidence_digest=b"\xe1" * 32,
    )
    applied = kernel.apply_venue_recovery_input(
        recovery.discovered.book,
        recovery.discovered.execution,
        fill_command,
    )
    assert applied.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert applied.quantity_delta == 1
    exact_replay = kernel.apply_venue_recovery_input(
        applied.book,
        applied.execution,
        fill_command,
    )
    assert exact_replay.disposition is kernel.VenueRecoveryDisposition.EXACT_REPLAY
    same_input_conflict = kernel.apply_venue_recovery_input(
        applied.book,
        applied.execution,
        replace(fill_command, evidence_digest=b"\xe2" * 32),
    )
    assert same_input_conflict.disposition is kernel.VenueRecoveryDisposition.CONFLICT

    duplicate_fact = kernel.apply_venue_recovery_input(
        applied.book,
        applied.execution,
        replace(
            fill_command,
            input_id=kernel.VenueInputId("wo0152-e3-matrix-fill-duplicate"),
        ),
    )
    assert duplicate_fact.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert duplicate_fact.quantity_delta == 0
    assert duplicate_fact.execution == applied.execution
    assert (
        duplicate_fact.execution.seen_facts.count == applied.execution.seen_facts.count
    )
    reordered_revision = kernel.RecordBrokerRevisionEvidence(
        input_id=kernel.VenueInputId("wo0152-e3-matrix-reordered-revision"),
        effect_id=recovery.effect_id,
        leg_key=recovery.leg_key,
        prior_root_quantity=kernel.Quantity(0),
        prior_venue_cumulative_quantity=kernel.Quantity(0),
        resulting_venue_cumulative_quantity=kernel.Quantity(1),
        fact=kernel.BrokerTradeCorrectFact(
            key=kernel.ExecutionFactKey(
                broker=_BROKER,
                environment=_ENVIRONMENT,
                account=_ACCOUNT,
                source_event_id=kernel.SourceEventId(
                    "wo0152-e3-matrix-reordered-correct"
                ),
            ),
            scope=scope,
            root_fill_id=kernel.RootFillId("wo0152-e3-matrix-missing-root"),
            predecessor_source_event_id=kernel.SourceEventId(
                "wo0152-e3-matrix-missing-predecessor"
            ),
            revised_quantity=kernel.Quantity(1),
            revised_price=_PRICE,
        ),
        evidence_digest=b"\xe3" * 32,
    )
    reordered = kernel.apply_venue_recovery_input(
        recovery.discovered.book,
        recovery.discovered.execution,
        reordered_revision,
    )
    assert reordered.disposition in {
        kernel.VenueRecoveryDisposition.REFUSED,
        kernel.VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
    }
    wrong_prior = kernel.apply_venue_recovery_input(
        recovery.discovered.book,
        recovery.discovered.execution,
        replace(
            fill_command,
            input_id=kernel.VenueInputId("wo0152-e3-matrix-wrong-prior"),
            prior_cumulative_quantity=kernel.Quantity(1),
            resulting_cumulative_quantity=kernel.Quantity(2),
        ),
    )
    assert wrong_prior.disposition in {
        kernel.VenueRecoveryDisposition.REFUSED,
        kernel.VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
    }


def test_e3_market_rebase_and_buy_preemption_are_atomic_and_single_flight() -> None:
    """Semantic market updates and BUY stand-down preserve one authority head."""

    fixture = _build_e3_claimed_leg()
    fill = kernel.BrokerFillFact(
        key=kernel.ExecutionFactKey(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            source_event_id=kernel.SourceEventId("wo0152-e3-preempt-fill"),
        ),
        scope=kernel.ExecutionScope(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            order_id=fixture.leg_key.order_id,
            symbol_id=_TARGET_SCOPE.symbol_id,
            side=kernel.ExecutionSide.BUY,
        ),
        root_fill_id=kernel.RootFillId("wo0152-e3-preempt-root"),
        quantity=kernel.Quantity(1),
        price=_PRICE,
    )
    filled = kernel.apply_venue_recovery_input(
        fixture.discovered.book,
        fixture.discovered.execution,
        kernel.RecordBrokerFillEvidence(
            input_id=kernel.VenueInputId("wo0152-e3-preempt-fill"),
            effect_id=fixture.effect_id,
            leg_key=fixture.leg_key,
            prior_cumulative_quantity=kernel.Quantity(0),
            resulting_cumulative_quantity=kernel.Quantity(1),
            fact=fill,
            evidence_digest=b"\xe4" * 32,
        ),
    )
    assert filled.disposition is kernel.VenueRecoveryDisposition.APPLIED
    current = kernel.reduce_acquisition_controller(
        fixture.claimed.state,
        filled,
        None,
        fixture.claimed.authority,
    )
    assert current.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert current.protection is not None
    protection_venue = kernel.project_protection_venue(
        filled,
        fixture.mandate.protection_mandate,
    )

    premature_refresh = authority.refresh_acquisition_context(
        current.authority,
        current.execution,
        _TARGET_SCOPE,
    )
    premature = kernel.begin_acquisition_preemption(
        current.state,
        premature_refresh,
        current.protection,
        kernel.AuthorityInputId("wo0152-e3-preempt-premature"),
    )
    assert premature.disposition is kernel.AcquisitionControllerDisposition.REFUSED
    assert premature.state is current.state
    assert premature.created_effect_id is None

    for sequence, bid in enumerate((120, 110, 109), start=1):
        assert current.protection is not None
        refresh = authority.refresh_acquisition_context(
            current.authority,
            current.execution,
            _TARGET_SCOPE,
        )
        assert (
            refresh.disposition
            is authority.AcquisitionContextRefreshDisposition.CURRENT
        )
        assert refresh.venue_context is not None
        predecessor_context = kernel.project_acquisition_protection_context(
            current.protection,
            current.venue,
            current.execution,
            refresh.venue_context,
        )
        assert predecessor_context is not None
        occurrence = _e3_market_occurrence(
            fixture.mandate.protection_mandate,
            bid=bid,
            sequence=sequence,
            source_time=94 + sequence * 6,
            label=f"preempt-{sequence}",
        )
        reduced = kernel.reduce_position_protection_market(
            current.protection,
            protection_venue,
            occurrence,
        )
        assert reduced.disposition is kernel.ProtectionDisposition.APPLIED
        current_context = kernel.project_acquisition_protection_context(
            reduced.state,
            current.venue,
            current.execution,
            refresh.venue_context,
        )
        assert current_context is not None
        projection = kernel.project_acquisition_protection_rebase(
            current.protection,
            reduced,
            predecessor_context,
            current_context,
        )
        assert projection is not None
        rebased = kernel.rebase_acquisition_protection(
            current.state,
            refresh,
            projection,
        )
        assert rebased.disposition is kernel.AcquisitionControllerDisposition.APPLIED
        assert rebased.protection is reduced.state
        current = rebased

    assert current.protection is not None
    assert current.protection.policy is kernel.ProtectionPolicy.EXIT_NORMAL
    assert current.protection.waiting_buy_resolution
    refresh = authority.refresh_acquisition_context(
        current.authority,
        current.execution,
        _TARGET_SCOPE,
    )
    applied = kernel.begin_acquisition_preemption(
        current.state,
        refresh,
        current.protection,
        kernel.AuthorityInputId("wo0152-e3-preempt-apply"),
    )
    assert applied.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    assert applied.created_effect_id is not None
    assert applied.fresh_claim is None
    assert applied.protection is not None
    assert applied.protection.waiting_buy_resolution
    assert applied.execution == current.execution
    post_refresh = authority.refresh_acquisition_context(
        applied.authority,
        applied.execution,
        _TARGET_SCOPE,
    )
    replay = kernel.begin_acquisition_preemption(
        applied.state,
        post_refresh,
        applied.protection,
        kernel.AuthorityInputId("wo0152-e3-preempt-apply"),
    )
    assert replay.disposition is kernel.AcquisitionControllerDisposition.REFUSED
    assert replay.state is applied.state
    assert replay.created_effect_id is None


@dataclass(frozen=True)
class _E3RootedReplayObserver:
    raw_quantity: int
    seen_fact_count: int
    successor_ordinal: int
    live_generation_id: kernel.AcquisitionGenerationId
    recovery_class: kernel.AcquisitionRecoveryClass
    protection_policy: kernel.ProtectionPolicy
    protection_raw_quantity: int
    effect_state: kernel.BrokerEffectState
    acceptance_state: kernel.AcceptanceSetState
    economics_head_commitment: bytes
    binding_commitment: bytes


def _observe_e3_rooted_parent(parent: _E3CertifiedParent) -> _E3RootedReplayObserver:
    status = kernel.project_acquisition_controller(parent.state)
    assert status.live_generation_id is not None
    record = parent.state.registry.record(status.live_generation_id)
    assert record is not None
    effect = parent.authority.venue.effect(parent.effect_id)
    assert effect is not None
    return _E3RootedReplayObserver(
        raw_quantity=parent.execution.position.raw_quantity,
        seen_fact_count=parent.execution.seen_facts.count,
        successor_ordinal=status.successor_ordinal,
        live_generation_id=status.live_generation_id,
        recovery_class=status.recovery_class,
        protection_policy=parent.protection.policy,
        protection_raw_quantity=parent.protection.raw_quantity,
        effect_state=effect.state,
        acceptance_state=effect.acceptance_set_state,
        economics_head_commitment=record.economics_head_commitment,
        binding_commitment=record.binding.dual_mandate_binding_commitment,
    )


def _assert_e3_proof_oracle(comparisons: dict[str, bool]) -> None:
    """Require every decisive E3 comparison and every observed conclusion."""

    names = frozenset(comparisons)
    missing = _E3_DECISIVE_COMPARISONS - names
    extra = names - _E3_DECISIVE_COMPARISONS
    if missing or extra:
        raise AssertionError(
            f"incomplete E3 oracle: missing={sorted(missing)!r}, extra={sorted(extra)!r}"
        )
    failed = sorted(
        name for name, conclusion in comparisons.items() if conclusion is not True
    )
    if failed:
        raise AssertionError(f"failed E3 oracle comparisons: {failed!r}")


def _e3_base_control_predicate_violations(
    tree: ast.Module,
    test_name: str,
    required_predicates: tuple[str, ...],
) -> tuple[str, ...]:
    owners = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == test_name
    ]
    if len(owners) != 1:
        return ("owning-test",)
    assertions = [
        ast.unparse(node.test)
        for node in ast.walk(owners[0])
        if type(node) is ast.Assert
    ]
    return tuple(
        predicate
        for predicate in required_predicates
        if not any(predicate in assertion for assertion in assertions)
    )


def test_e3_requirement_control_inventory_is_complete() -> None:
    requirements = [row[0] for row in _E3_BASE_CONTROL_INVENTORY]
    controls = [(row[1], row[2]) for row in _E3_BASE_CONTROL_INVENTORY]
    assert len(requirements) == len(set(requirements)) == 15
    assert len(controls) == len(set(controls)) == 15
    assert {requirement.split("/", maxsplit=1)[0] for requirement in requirements} == {
        *(f"E1-AC-{ordinal:02d}" for ordinal in range(1, 8)),
        *(f"E2-AC-{ordinal:02d}" for ordinal in range(1, 9)),
    }

    test_root = Path(__file__).parent
    for (
        requirement,
        relative_path,
        test_name,
        required_predicates,
    ) in _E3_BASE_CONTROL_INVENTORY:
        assert requirement.startswith(("E1-", "E2-"))
        source_path = test_root / relative_path
        assert source_path.is_file()
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        assert (
            _e3_base_control_predicate_violations(
                tree,
                test_name,
                required_predicates,
            )
            == ()
        ), (requirement, relative_path, test_name)

        mutant = copy.deepcopy(tree)
        owners = [
            node
            for node in mutant.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == test_name
        ]
        assert len(owners) == 1, (requirement, relative_path, test_name)
        for assertion in (
            node for node in ast.walk(owners[0]) if type(node) is ast.Assert
        ):
            assertion.test = ast.Constant(value=True)
        assert (
            _e3_base_control_predicate_violations(
                mutant,
                test_name,
                required_predicates,
            )
            == required_predicates
        ), (
            requirement,
            relative_path,
            test_name,
        )


def test_e3_source_policy_and_observer_mutations_are_failure_capable() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    assert _e3_source_policy_violations(source) == ()

    probe_marker = (
        "def _nonadjacent_duplicate_stream_probe_mandate_fixture() "
        "-> kernel.AcquisitionMandate:\n"
    )
    prefix, probe_tail = source.split(probe_marker, maxsplit=1)
    conditional_probe = (
        prefix
        + probe_marker
        + probe_tail.replace(
            "    binding = acquisition._mint_dual_mandate_binding(\n",
            "    if True:\n        binding = acquisition._mint_dual_mandate_binding(\n",
            1,
        )
    )

    specimens = (
        (source + "\nfrom tests.forbidden import helper\n", "tests-import"),
        (
            source + "\ndef rogue(state):\n    return state._controller\n",
            "private-production-access",
        ),
        (
            source
            + "\ndef rogue():\n    return acquisition._mint_dual_mandate_binding()\n",
            "private-minter-sites",
        ),
        (
            source
            + "\ndef rogue():\n    return getattr(kernel, 'VenueRecoveryBook')\n",
            "dynamic-lookup",
        ),
        (
            source.replace('"effects",', '"effects_missing",', 1),
            "history-tripwire-targets",
        ),
        (
            source.replace(
                "property(_raise_history_property)",
                "_raise_venue_effect",
                1,
            ),
            "history-tripwire-shape",
        ),
        (
            source.replace(
                "_E3_FIXED_MANDATE_SCHEDULE = (",
                "_E3_FIXED_MANDATE_SCHEDULE = ()\n_E3_UNUSED_SCHEDULE = (",
                1,
            ),
            "mandate-schedule-cardinality",
        ),
        (
            source.replace(
                "def _approved_acquisition_mandates_fixture() ->",
                "def _approved_acquisition_mandates_fixture(caller: object) ->",
                1,
            ),
            "mandate-fixture-signature",
        ),
        (
            source.replace(
                "def _nonadjacent_duplicate_stream_probe_mandate_fixture() ->",
                "def _nonadjacent_duplicate_stream_probe_mandate_fixture("
                "caller: object) ->",
                1,
            ),
            "mandate-fixture-signature",
        ),
        (conditional_probe, "duplicate-stream-probe-control-flow"),
        (
            prefix
            + probe_marker
            + probe_tail.replace(
                "_E3_FIXED_DUPLICATE_STREAM_PROBE",
                "_E3_FIXED_MANDATE_SCHEDULE[0]",
                1,
            ),
            "duplicate-stream-probe-derived",
        ),
        (
            source.replace(
                "    return tuple(mandates)\n",
                "    return tuple(mandates) + "
                "(_nonadjacent_duplicate_stream_probe_mandate_fixture(),)\n",
                1,
            ),
            "mandate-schedule-probe-contamination",
        ),
        (
            source
            + "\ndef rogue_post_genesis():\n"
            + "    _initialize_e3_controller("
            + "_approved_acquisition_mandates_fixture()[0])\n"
            + "    return _approved_acquisition_mandates_fixture()\n",
            "mandate-fixture-post-genesis",
        ),
        (
            source + "\ndef rogue_copy(value):\n    return copy.copy(value)\n",
            "setup-copy-authority",
        ),
        (
            source
            + "\ndef rogue_patch():\n"
            + "    return patch.object(kernel.VenueRecoveryBook, 'effects', object())\n",
            "setup-patch-authority",
        ),
        (
            source.replace(
                "    return copied_authority, final_transition.execution\n",
                "    object.__setattr__(\n"
                "        copied_authority, 'mode', kernel.TradingMode.ACTIVE\n"
                "    )\n"
                "    return copied_authority, final_transition.execution\n",
                1,
            ),
            "setup-setattr-authority",
        ),
        (
            source.replace(
                "    ) in _E3_FIXED_MANDATE_SCHEDULE:\n",
                "    ) in _E3_FIXED_MANDATE_SCHEDULE:\n        continue\n",
                1,
            ),
            "mandate-schedule-control-flow",
        ),
        (
            source
            + "\ndef rogue_direct_patch():\n"
            + "    return patch('app.execution_core.venue.VenueRecoveryBook')\n",
            "setup-patch-authority",
        ),
        (
            source.replace(
                "    mandates: list[kernel.AcquisitionMandate] = []\n",
                "    mandates: list[kernel.AcquisitionMandate] = []\n"
                "    _ = [entry for entry in _E3_FIXED_MANDATE_SCHEDULE]\n",
                1,
            ),
            "mandate-schedule-control-flow",
        ),
        (
            source.replace(
                "        applied = venue._apply_venue_input("
                "flat.venue, flat.execution, close)\n",
                "        applied = venue._apply_venue_input("
                "flat.venue, flat.execution, close)\n"
                "        venue._apply_venue_input(flat.venue, flat.execution, close)\n",
                1,
            ),
            "private-venue-reducer-sites",
        ),
    )
    for mutated_source, expected_violation in specimens:
        assert expected_violation in _e3_source_policy_violations(mutated_source)

    complete_oracle = {name: True for name in _E3_DECISIVE_COMPARISONS}
    _assert_e3_proof_oracle(complete_oracle)
    for omitted in _E3_DECISIVE_COMPARISONS:
        mutant = {
            name: conclusion
            for name, conclusion in complete_oracle.items()
            if name != omitted
        }
        try:
            _assert_e3_proof_oracle(mutant)
        except AssertionError as exc:
            assert omitted in str(exc)
        else:
            raise AssertionError(f"omitted E3 comparison survived: {omitted}")
    for falsified in _E3_DECISIVE_COMPARISONS:
        mutant = dict(complete_oracle)
        mutant[falsified] = False
        try:
            _assert_e3_proof_oracle(mutant)
        except AssertionError as exc:
            assert falsified in str(exc)
        else:
            raise AssertionError(f"false E3 comparison survived: {falsified}")


def test_e3_seeded_state_machine_preserves_serial_observer_model() -> None:
    """Thirty-six deterministic shrinkable traces retain one LIVE generation."""

    schedule = _approved_acquisition_mandates_fixture()
    genesis = _initialize_e3_controller(schedule[0])
    recorded_seed = 15_152
    randomizer = random.Random(recorded_seed)

    for example in range(36):
        command_count = randomizer.randint(1, 8)
        current = genesis
        generation_ids = [
            kernel.project_acquisition_controller(current.state).live_generation_id
        ]
        for ordinal in range(1, command_count + 1):
            current = _advance_e3_aborted_successor(current, schedule[ordinal])
            status = kernel.project_acquisition_controller(current.state)
            generation_ids.append(status.live_generation_id)
            assert status.successor_ordinal == ordinal, (
                recorded_seed,
                example,
                ordinal,
            )
            assert status.live_generation_id is not None
            assert status.recovery_class is kernel.AcquisitionRecoveryClass.NORMAL
            live_record = current.state.registry.record(status.live_generation_id)
            assert live_record is not None
            assert live_record.serving_class is kernel.GenerationServingClass.LIVE
            for retired_id in generation_ids[:-1]:
                assert retired_id is not None
                retired = current.state.registry.record(retired_id)
                assert retired is not None
                assert (
                    retired.serving_class
                    is kernel.GenerationServingClass.RETIRED_UNSERVING
                )


def test_e3_rooted_trace_replays_public_economics_and_protection() -> None:
    """A test-owned rooted command token replays without state hydration."""

    commands = (
        "CREATE",
        "CLAIM",
        "ACK",
        "DISCOVER",
        "FILL",
        "TERMINAL",
        "BUST",
        "CLOSE",
    )

    def replay(encoded: object) -> _E3RootedReplayObserver:
        if type(encoded) is not tuple or encoded != commands:
            raise ValueError("rooted trace is corrupt, reordered, or incomplete")
        return _observe_e3_rooted_parent(_certified_terminal_parent_fixture())

    uninterrupted = replay(commands)
    restarted = replay(tuple(commands))
    assert uninterrupted == restarted
    assert uninterrupted.raw_quantity == 0
    assert uninterrupted.protection_policy is kernel.ProtectionPolicy.FLAT
    assert uninterrupted.acceptance_state is kernel.AcceptanceSetState.CLOSED

    for corrupt in (
        commands[:-1],
        tuple(reversed(commands)),
        commands[:3] + ("FORK",) + commands[4:],
        list(commands),
    ):
        replay_invoked = False
        try:
            replay(corrupt)
        except ValueError:
            pass
        else:
            replay_invoked = True
        assert not replay_invoked


def test_e3_long_sequence_live_decisions_do_not_materialize_history() -> None:
    """Long serial and rooted traces retain bounded earliest/current routing."""

    schedule = _approved_acquisition_mandates_fixture()
    current = _initialize_e3_controller(schedule[0])
    initial_status = kernel.project_acquisition_controller(current.state)
    assert initial_status.live_generation_id is not None
    generation_ids = [initial_status.live_generation_id]
    controller_heads = [initial_status.controller_head]
    for mandate in schedule[1:]:
        current = _advance_e3_aborted_successor(current, mandate)
        status = kernel.project_acquisition_controller(current.state)
        assert status.live_generation_id is not None
        generation_ids.append(status.live_generation_id)
        controller_heads.append(status.controller_head)

    final_status = kernel.project_acquisition_controller(current.state)
    assert len(generation_ids) == len(set(generation_ids)) == 32
    assert final_status.successor_ordinal == 31
    assert final_status.live_generation_id == generation_ids[-1]

    rooted = _build_rooted_a_to_b_unclaimed_effect()
    created = rooted.created
    late_fill = kernel.BrokerFillFact(
        key=kernel.ExecutionFactKey(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            source_event_id=kernel.SourceEventId("wo0152-e3-bounded-late-a-fill"),
        ),
        scope=rooted.parent.root_fill.scope,
        root_fill_id=kernel.RootFillId("wo0152-e3-bounded-late-a-root"),
        quantity=kernel.Quantity(1),
        price=_PRICE,
    )
    fill_command = kernel.RecordBrokerFillEvidence(
        input_id=kernel.VenueInputId("wo0152-e3-bounded-late-a-fill"),
        effect_id=rooted.parent.effect_id,
        leg_key=rooted.parent.leg_key,
        prior_cumulative_quantity=kernel.Quantity(0),
        resulting_cumulative_quantity=kernel.Quantity(1),
        fact=late_fill,
        evidence_digest=b"\xd1" * 32,
        closure_id=kernel.ClosureId("wo0152-e3-bounded-late-a-fill"),
        evidence_reference=kernel.EvidenceReference("wo0152-e3-bounded-late-a-fill"),
    )
    transition = kernel.apply_venue_recovery_input(
        created.authority.venue,
        created.execution,
        fill_command,
    )
    assert transition.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert transition.quantity_delta == 1

    with _forbid_live_acquisition_history_materialization():
        refreshed = authority.refresh_acquisition_context(
            current.authority,
            current.execution,
            _TARGET_SCOPE,
        )
        admission = authority.project_acquisition_admission(
            current.authority,
            current.execution,
            _TARGET_SCOPE,
        )
        reduced = kernel.reduce_acquisition_controller(
            created.state,
            transition,
            created.protection,
            created.authority,
        )

    assert (
        refreshed.disposition is authority.AcquisitionContextRefreshDisposition.CURRENT
    )
    assert admission.position_scope == _TARGET_SCOPE
    assert reduced.disposition is kernel.AcquisitionControllerDisposition.APPLIED
    earliest = current.state.registry.record(generation_ids[0])
    live = current.state.registry.record(generation_ids[-1])
    route = reduced.state.lineage.route_fact(late_fill.key)
    assert earliest is not None
    assert live is not None
    assert route is not None
    assert route.generation_id == rooted.retired_a_generation_id
    assert earliest.serving_class is kernel.GenerationServingClass.RETIRED_UNSERVING
    assert live.serving_class is kernel.GenerationServingClass.LIVE
    assert reduced.venue.effect(rooted.parent.effect_id) is not None

    duplicate = kernel.apply_venue_recovery_input(
        reduced.venue,
        reduced.execution,
        replace(
            fill_command,
            input_id=kernel.VenueInputId("wo0152-e3-bounded-late-a-duplicate"),
        ),
    )
    assert duplicate.disposition is kernel.VenueRecoveryDisposition.APPLIED
    assert duplicate.quantity_delta == 0
    assert duplicate.execution == reduced.execution

    trace = _E3AbortedTrace(
        application=_E3_TRACE_APPLICATION,
        scope=_E3_TRACE_SCOPE,
        labels=_E3_ABORTED_TRACE_LABELS,
        ordinals=_E3_ABORTED_TRACE_ORDINALS,
    )
    compatibility_commitments = {
        mandate.protection_mandate.emergency_recovery_compatibility.commitment
        for mandate in schedule
    }
    generation_records = [
        current.state.registry.record(generation_id) for generation_id in generation_ids
    ]
    assert all(record is not None for record in generation_records)
    replayed_genesis = _initialize_e3_controller(schedule[0])
    replayed_status = kernel.project_acquisition_controller(replayed_genesis.state)
    assert replayed_status.live_generation_id is not None
    replayed_record = replayed_genesis.state.registry.record(
        replayed_status.live_generation_id
    )
    assert replayed_record is not None
    live_count = sum(
        record is not None
        and record.serving_class is kernel.GenerationServingClass.LIVE
        for record in generation_records
    )
    comparisons = {
        "lineage": route.generation_id == rooted.retired_a_generation_id,
        "head_and_ordinal": (
            kernel.project_acquisition_controller(current.state).successor_ordinal == 31
            and len(controller_heads) == len(set(controller_heads)) == 32
            and controller_heads[0] != controller_heads[-1]
        ),
        "one_live": live_count == 1,
        "economics_exact_once": (
            duplicate.quantity_delta == 0 and duplicate.execution == reduced.execution
        ),
        "compatibility": compatibility_commitments == {_E3_COMPATIBILITY.commitment},
        "capacity": (
            len(schedule) == len(generation_ids) == 32
            and all(
                mandate.maximum_quantity == kernel.Quantity(5)
                and mandate.maximum_notional == Fraction(1_000)
                and mandate.fixed_child_cap == kernel.Quantity(1)
                and record is not None
                and record.binding.dual_mandate_binding_commitment
                == mandate.binding.commitment
                for mandate, record in zip(schedule, generation_records, strict=True)
            )
        ),
        "codec": _decode_e3_aborted_trace(_encode_e3_aborted_trace(trace)) == trace,
        "bounded_lookup": (
            earliest.binding.generation_id == generation_ids[0]
            and live.binding.generation_id == generation_ids[-1]
            and route.route_kind is kernel.GenerationRouteKind.FACT
        ),
        "identity_core_coordinates": all(
            record is not None
            and record.binding.generation_id == generation_id
            and record.binding.application_generation_id == _APPLICATION
            and record.binding.position_scope == _TARGET_SCOPE
            and record.binding.successor_ordinal == ordinal
            for ordinal, (generation_id, record) in enumerate(
                zip(generation_ids, generation_records, strict=True)
            )
        ),
        "identity_predecessor_heads": all(
            record is not None
            and record.binding.predecessor_or_genesis_head_commitment
            == (
                _E3_GENESIS_HEAD_COMMITMENT
                if ordinal == 0
                else controller_heads[ordinal - 1]
            )
            for ordinal, record in enumerate(generation_records)
        )
        and replayed_record.binding.predecessor_or_genesis_head_commitment
        == _E3_GENESIS_HEAD_COMMITMENT,
        "identity_compatibility": all(
            record is not None
            and record.binding.emergency_recovery_compatibility_commitment
            == mandate.protection_mandate.emergency_recovery_compatibility.commitment
            for mandate, record in zip(schedule, generation_records, strict=True)
        ),
        "identity_binding_commitments": (
            len(
                {
                    record.binding.binding_commitment
                    for record in generation_records
                    if record is not None
                }
            )
            == 32
            and replayed_record.binding.binding_commitment
            == earliest.binding.binding_commitment
            == _E3_GENESIS_BINDING_COMMITMENT
            and all(
                record is not None
                and type(record.binding.binding_commitment) is bytes
                and len(record.binding.binding_commitment) == 32
                for record in generation_records
            )
        ),
    }
    _assert_e3_proof_oracle(comparisons)
