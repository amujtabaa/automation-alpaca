"""Pure RED/GREEN controls for the M2 atomic unit-of-work boundary."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from contextlib import contextmanager
from copy import copy
from copy import deepcopy
from dataclasses import replace
import inspect
from types import SimpleNamespace

import pytest

from app.execution_core import authority
from app.execution_core import acquisition
from app.execution_core import fills
from app.execution_core import identity
from app.execution_core import position
from app.execution_core import protection
from app.execution_core import venue
from app.execution_core.persistence import checkpoint_codec
from app.execution_core.persistence import operations
from app.execution_core.persistence import records
from app.execution_core.persistence import unit_of_work
import test_persistence_runtime_checkpoint_pure as checkpoint_fixtures
import test_persistence_startup_hydration as hydration_fixtures
import test_persistence_input_receipt as input_fixtures
import test_authority as authority_fixtures
import test_acquisition as acquisition_fixtures
import test_protection as protection_fixtures
from tests.execution_core import test_venue_recovery as recovery_fixtures


_LOCAL_EXCEPTION_CATCHERS = (ast.Try, ast.TryStar, ast.With, ast.AsyncWith)


def _call_local_exception_catchers(
    node: ast.Call,
    parents: dict[ast.AST, ast.AST],
) -> tuple[ast.AST, ...]:
    catchers: list[ast.AST] = []
    ancestor = parents.get(node)
    while ancestor is not None and not isinstance(
        ancestor,
        (ast.FunctionDef, ast.AsyncFunctionDef),
    ):
        if isinstance(ancestor, _LOCAL_EXCEPTION_CATCHERS):
            catchers.append(ancestor)
        ancestor = parents.get(ancestor)
    return tuple(catchers)


def _call_has_local_exception_catcher(
    node: ast.Call,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    return bool(_call_local_exception_catchers(node, parents))


def _call_enclosing_function_name(
    node: ast.Call,
    parents: dict[ast.AST, ast.AST],
) -> str | None:
    ancestor = parents.get(node)
    while ancestor is not None:
        if isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return ancestor.name
        ancestor = parents.get(ancestor)
    return None


_EXPECTED_M2_C6_WRITE_TABLE = (
    (
        "O1",
        (
            (
                "root-route-fact",
                (
                    "store_root_fill",
                    "store_acquisition_root_route",
                    "store_execution_fact",
                ),
            ),
            ("broker-protection-currentness", ("advance_protection_authority",)),
            (
                "venue-derivatives",
                (
                    "store_venue_effect",
                    "store_acceptance_set",
                    "store_dispatch_claim",
                    "advance_venue_effect",
                    "store_acceptance_evidence",
                    "advance_venue_effect",
                ),
            ),
        ),
    ),
    (
        "O2",
        (
            ("venue-semantic-keys", ("store_durable_input_semantic_key",)),
            (
                "effect-owner-evidence",
                (
                    "advance_venue_effect",
                    "advance_venue_effect",
                    "store_venue_identity_owner",
                    "store_acceptance_evidence",
                ),
            ),
            ("terminal-closure", ("store_closure",)),
            (
                "root-route-fact",
                (
                    "store_root_fill",
                    "store_acquisition_root_route",
                    "store_execution_fact",
                ),
            ),
            (
                "acquisition-currentness",
                (
                    "advance_market_cursor",
                    "advance_symbol_controller",
                    "advance_protection_authority",
                ),
            ),
            (
                "venue-derivatives",
                (
                    "store_venue_effect",
                    "store_acceptance_set",
                    "store_dispatch_claim",
                    "advance_venue_effect",
                    "store_acceptance_evidence",
                    "advance_venue_effect",
                ),
            ),
        ),
    ),
    (
        "O3",
        (
            (
                "venue-derivatives",
                (
                    "store_venue_effect",
                    "store_acceptance_set",
                    "store_dispatch_claim",
                    "advance_venue_effect",
                    "store_acceptance_evidence",
                    "advance_venue_effect",
                ),
            ),
            ("authority-semantic-key", ("store_durable_input_semantic_key",)),
        ),
    ),
    (
        "O4",
        (
            (
                "generation-cutover",
                (
                    "advance_protection_authority",
                    "advance_symbol_controller",
                    "advance_protection_authority",
                    "retire_acquisition_generation",
                    "store_acquisition_generation",
                    "store_market_stream_authority",
                    "store_market_cursor",
                    "advance_symbol_controller",
                    "advance_protection_authority",
                ),
            ),
        ),
    ),
    (
        "O5",
        (
            (
                "acquisition-currentness",
                (
                    "advance_market_cursor",
                    "advance_symbol_controller",
                    "advance_protection_authority",
                ),
            ),
            (
                "venue-derivatives",
                (
                    "store_venue_effect",
                    "store_acceptance_set",
                    "store_dispatch_claim",
                    "advance_venue_effect",
                    "store_acceptance_evidence",
                    "advance_venue_effect",
                ),
            ),
        ),
    ),
    (
        "O6",
        (
            (
                "venue-derivatives",
                (
                    "store_venue_effect",
                    "store_acceptance_set",
                    "store_dispatch_claim",
                    "advance_venue_effect",
                    "store_acceptance_evidence",
                    "advance_venue_effect",
                ),
            ),
            (
                "acquisition-currentness",
                (
                    "advance_market_cursor",
                    "advance_symbol_controller",
                    "advance_protection_authority",
                ),
            ),
        ),
    ),
    (
        "O7",
        (
            (
                "acquisition-currentness",
                (
                    "advance_market_cursor",
                    "advance_symbol_controller",
                    "advance_protection_authority",
                ),
            ),
            (
                "venue-derivatives",
                (
                    "store_venue_effect",
                    "store_acceptance_set",
                    "store_dispatch_claim",
                    "advance_venue_effect",
                    "store_acceptance_evidence",
                    "advance_venue_effect",
                ),
            ),
        ),
    ),
    (
        "O8",
        (
            (
                "acquisition-currentness",
                (
                    "advance_market_cursor",
                    "advance_symbol_controller",
                    "advance_protection_authority",
                ),
            ),
            (
                "venue-derivatives",
                (
                    "store_venue_effect",
                    "store_acceptance_set",
                    "store_dispatch_claim",
                    "advance_venue_effect",
                    "store_acceptance_evidence",
                    "advance_venue_effect",
                ),
            ),
        ),
    ),
)


def _write_table_projection(
    table: tuple[tuple[str, tuple[object, ...]], ...],
) -> tuple[tuple[str, tuple[tuple[str, tuple[str, ...]], ...]], ...]:
    return tuple(
        (
            row_id,
            tuple(
                (family.name, family.repository_calls)  # type: ignore[attr-defined]
                for family in families
            ),
        )
        for row_id, families in table
    )


@pytest.mark.parametrize(("row_id", "expected_families"), _EXPECTED_M2_C6_WRITE_TABLE)
def test_each_o1_o8_row_has_the_exact_closed_repository_call_order(
    row_id: str,
    expected_families: tuple[tuple[str, tuple[str, ...]], ...],
) -> None:
    projected = dict(_write_table_projection(unit_of_work._M2_C6_WRITE_TABLE))
    assert projected[row_id] == expected_families
    assert unit_of_work._m2_write_table_is_exact(unit_of_work._M2_C6_WRITE_TABLE)


def test_o1_o8_write_table_rejects_every_contract_mutant() -> None:
    table = unit_of_work._M2_C6_WRITE_TABLE
    first_row_id, first_families = table[0]
    first_family = first_families[0]
    assert first_row_id == "O1"

    missing_row = table[:-1]
    extra_row = table + (("O9", first_families),)
    reordered_rows = (table[1], table[0], *table[2:])
    missing_family = ((first_row_id, first_families[:-1]), *table[1:])
    duplicate_family = (
        (first_row_id, (*first_families, first_families[-1])),
        *table[1:],
    )
    missing_call_family = replace(
        first_family,
        repository_calls=first_family.repository_calls[:-1],
    )
    missing_call = (
        (first_row_id, (missing_call_family, *first_families[1:])),
        *table[1:],
    )
    extra_call_family = replace(
        first_family,
        repository_calls=(*first_family.repository_calls, "store_execution_fact"),
    )
    extra_call = (
        (first_row_id, (extra_call_family, *first_families[1:])),
        *table[1:],
    )
    reordered_calls_family = replace(
        first_family,
        repository_calls=(
            first_family.repository_calls[1],
            first_family.repository_calls[0],
            *first_family.repository_calls[2:],
        ),
    )
    reordered_calls = (
        (first_row_id, (reordered_calls_family, *first_families[1:])),
        *table[1:],
    )
    dynamic_family = replace(first_family, repository_calls=("getattr",))
    dynamic = ((first_row_id, (dynamic_family, *first_families[1:])), *table[1:])
    wildcard_family = replace(first_family, repository_calls=("store_*",))
    wildcard = ((first_row_id, (wildcard_family, *first_families[1:])), *table[1:])

    for mutant in (
        missing_row,
        extra_row,
        reordered_rows,
        missing_family,
        duplicate_family,
        missing_call,
        extra_call,
        reordered_calls,
        dynamic,
        wildcard,
    ):
        assert not unit_of_work._m2_write_table_is_exact(mutant)


def test_every_repository_mutator_call_site_is_static_and_catalogued() -> None:
    source = inspect.getsource(unit_of_work)
    tree = ast.parse(source)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    write_prefixes = ("advance_", "claim_", "finalize_", "retire_", "store_")
    expected = {
        "_claim_primary_input": ("claim_durable_input",),
        "_store_successor_checkpoint": ("store_runtime_checkpoint",),
        "_m2_store_cold_successor": ("store_runtime_checkpoint",),
        "_store_venue_semantic_key": ("store_durable_input_semantic_key",),
        "_store_authority_query_semantic_key": ("store_durable_input_semantic_key",),
        "_store_authority_manual_semantic_key": ("store_durable_input_semantic_key",),
        "_store_authority_grant_semantic_key": ("store_durable_input_semantic_key",),
        "_store_new_effect_with_acceptance": (
            "store_venue_effect",
            "store_acceptance_set",
        ),
        "_persist_authority_venue_transitions": (
            "store_dispatch_claim",
            "advance_venue_effect",
            "store_acceptance_evidence",
            "advance_venue_effect",
        ),
        "_complete_claimed_input": (
            "store_decision_receipt",
            "store_durable_input_outcome",
            "store_broker_outbox",
            "finalize_durable_input",
        ),
        "_persist_venue_owner_rows": (
            "advance_venue_effect",
            "advance_venue_effect",
            "store_venue_identity_owner",
            "store_acceptance_evidence",
        ),
        "_persist_venue_terminal_closure": ("store_closure",),
        "_persist_venue_economics": (
            "store_root_fill",
            "store_acquisition_root_route",
            "store_execution_fact",
        ),
        "_advance_acquisition_currentness": (
            "store_market_cursor",
            "advance_market_cursor",
        ),
        "_advance_venue_protection_after_trigger": ("advance_market_cursor",),
        "_advance_protection_record": ("advance_protection_authority",),
        "_advance_controller_record": ("advance_symbol_controller",),
        "_execute_generation_operation": (
            "retire_acquisition_generation",
            "store_acquisition_generation",
            "store_market_stream_authority",
            "store_market_cursor",
        ),
        "_execute_broker_execution_operation": (
            "store_root_fill",
            "store_acquisition_root_route",
            "store_execution_fact",
        ),
    }
    actual: dict[str, tuple[str, ...]] = {}
    dynamic_calls: list[int] = []
    wildcard_calls: list[int] = []
    locally_caught_calls: list[int] = []

    for function in (node for node in tree.body if isinstance(node, ast.FunctionDef)):
        calls: list[str] = []

        class RepositoryWriteVisitor(ast.NodeVisitor):
            def visit_Call(self, node: ast.Call) -> None:
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "getattr"
                    and node.args
                    and isinstance(node.args[0], ast.Name)
                    and node.args[0].id == "_repository"
                ):
                    dynamic_calls.append(node.lineno)
                if isinstance(node.func, ast.Attribute):
                    owner = node.func.value
                    if (
                        isinstance(owner, ast.Name)
                        and owner.id == "_repository"
                        and node.func.attr.startswith(write_prefixes)
                        and node.func.attr
                        not in {
                            "_activate_runtime_write_lease",
                            "_retire_runtime_write_lease",
                        }
                    ):
                        calls.append(node.func.attr)
                        if _call_has_local_exception_catcher(node, parents):
                            locally_caught_calls.append(node.lineno)
                        if any(
                            isinstance(argument, ast.Starred) for argument in node.args
                        ) or any(keyword.arg is None for keyword in node.keywords):
                            wildcard_calls.append(node.lineno)
                self.generic_visit(node)

        RepositoryWriteVisitor().visit(function)
        if calls:
            actual[function.name] = tuple(calls)

    catalogued = {
        call
        for _, families in unit_of_work._M2_C6_WRITE_TABLE
        for family in families
        for call in family.repository_calls
    }
    catalogued.update(
        call
        for family in unit_of_work._M2_COMMON_WRITE_TABLE
        for call in family.repository_calls
    )
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    calls_by_function = {
        name: {
            call.func.id
            for call in ast.walk(function)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id in functions
        }
        for name, function in functions.items()
    }
    write_closure = set(expected)
    while True:
        callers = {
            name
            for name, callees in calls_by_function.items()
            if callees & write_closure
        }
        expanded = write_closure | callers
        if expanded == write_closure:
            break
        write_closure = expanded
    assert "_execute_prepared" in write_closure
    assert "execute_unit_of_work" in write_closure
    locally_caught_write_helpers: list[int] = []
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.func.id not in write_closure
        ):
            continue
        catchers = _call_local_exception_catchers(node, parents)
        transaction_coordinator_call = (
            node.func.id == "_execute_prepared"
            and _call_enclosing_function_name(node, parents) == "execute_unit_of_work"
        ) or (
            node.func.id in {"_m2_advance_cold_currentness", "_m2_store_cold_successor"}
            and _call_enclosing_function_name(node, parents)
            == "_m2_cold_compact_cutover"
        )
        if (
            transaction_coordinator_call
            and len(catchers) == 1
            and isinstance(catchers[0], ast.Try)
        ):
            # This one catcher is the required transaction coordinator: it
            # retires the lease and rolls back, then refuses or re-raises.
            continue
        if catchers:
            locally_caught_write_helpers.append(node.lineno)
    decorated_write_functions = [
        function.lineno
        for name, function in functions.items()
        if name in write_closure and function.decorator_list
    ]
    assert dynamic_calls == []
    assert wildcard_calls == []
    assert locally_caught_calls == []
    assert locally_caught_write_helpers == []
    assert decorated_write_functions == []
    assert actual == expected
    assert catalogued == set(unit_of_work._M2_REPOSITORY_WRITE_CALLS)


@pytest.mark.parametrize(
    "mutant_source",
    (
        """
def mutant(_repository, connection, record, capability):
    try:
        _repository.store_execution_fact(connection, record, capability=capability)
    except Exception:
        pass
""",
        """
def mutant(_repository, connection, record, capability):
    try:
        _repository.store_execution_fact(connection, record, capability=capability)
    except* Exception:
        pass
""",
        """
def mutant(_repository, connection, record, capability):
    with contextlib.suppress(Exception):
        _repository.store_execution_fact(connection, record, capability=capability)
""",
        """
async def mutant(_repository, connection, record, capability):
    async with suppressor():
        _repository.store_execution_fact(connection, record, capability=capability)
""",
    ),
)
def test_write_ratchet_detects_every_local_exception_catcher_form(
    mutant_source: str,
) -> None:
    tree = ast.parse(mutant_source)
    compile(tree, "<write-catcher-mutant>", "exec")
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "store_execution_fact"
    )
    assert _call_has_local_exception_catcher(call, parents)


@pytest.mark.parametrize(
    ("row_ids", "function_name", "expected_markers"),
    (
        (
            ("O1",),
            "_execute_broker_execution_operation",
            (
                "store_root_fill",
                "store_acquisition_root_route",
                "store_execution_fact",
                "_advance_protection_record",
                "_persist_authority_venue_transitions",
            ),
        ),
        (
            ("O2",),
            "_execute_venue_operation",
            (
                "_store_venue_transition_semantic_keys",
                "_persist_venue_owner_rows",
                "_persist_venue_terminal_closure",
                "_persist_venue_economics",
                "_advance_venue_protection_after_trigger",
                "_advance_venue_protection_after_trigger",
                "_advance_acquisition_currentness",
                "_persist_authority_venue_transitions",
            ),
        ),
        (
            ("O3",),
            "_execute_authority_operation",
            (
                "_persist_authority_venue_transitions",
                "_store_authority_query_semantic_key",
                "_store_authority_grant_semantic_key",
                "_store_authority_manual_semantic_key",
            ),
        ),
        (
            ("O4",),
            "_execute_generation_operation",
            (
                "_advance_protection_record",
                "_advance_controller_record",
                "_advance_protection_record",
                "retire_acquisition_generation",
                "store_acquisition_generation",
                "store_market_stream_authority",
                "store_market_cursor",
                "_advance_controller_record",
                "_advance_protection_record",
            ),
        ),
        (
            ("O5", "O6", "O7"),
            "_execute_acquisition_operation",
            (
                "_advance_acquisition_currentness",
                "_persist_authority_venue_transitions",
                "_advance_acquisition_currentness",
            ),
        ),
        (
            ("O8",),
            "_execute_market_operation",
            (
                "_advance_acquisition_currentness",
                "_persist_authority_venue_transitions",
            ),
        ),
    ),
)
def test_o1_o8_executor_family_markers_are_in_frozen_source_order(
    row_ids: tuple[str, ...],
    function_name: str,
    expected_markers: tuple[str, ...],
) -> None:
    del row_ids
    tree = ast.parse(inspect.getsource(unit_of_work))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    marker_names = frozenset(expected_markers)
    actual: list[str] = []

    class MarkerVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Name) and node.func.id in marker_names:
                actual.append(node.func.id)
            elif (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "_repository"
                and node.func.attr in marker_names
            ):
                actual.append(node.func.attr)
            self.generic_visit(node)

    MarkerVisitor().visit(function)
    assert tuple(actual) == expected_markers


@pytest.mark.parametrize(
    ("public_name", "kernel_name", "argument_count"),
    (
        ("begin_acquisition_generation", "_m2_begin_acquisition_generation", 6),
        ("rebase_acquisition_protection", "_m2_rebase_acquisition_protection", 3),
        ("create_acquisition_effect", "_m2_create_acquisition_effect", 5),
        ("claim_acquisition_effect", "_m2_claim_acquisition_effect", 6),
        ("begin_acquisition_preemption", "_m2_begin_acquisition_preemption", 4),
    ),
)
def test_acquisition_public_routes_delegate_to_the_shared_m2_kernel(
    monkeypatch: pytest.MonkeyPatch,
    public_name: str,
    kernel_name: str,
    argument_count: int,
) -> None:
    arguments = tuple(object() for _ in range(argument_count))
    sentinel = object()
    calls: list[tuple[object, ...]] = []

    def kernel(*received: object) -> object:
        calls.append(received)
        return sentinel

    monkeypatch.setattr(acquisition, kernel_name, kernel)
    assert getattr(acquisition, public_name)(*arguments) is sentinel
    assert calls == [arguments]


def test_acquisition_transition_exposes_only_its_authenticated_venue_derivatives() -> (
    None
):
    _, _, created = acquisition_fixtures._r8_created_first_effect()
    derivatives = acquisition._m2_acquisition_transition_venue_derivatives(created)

    assert len(derivatives) == 1
    assert type(venue._m2_venue_transition_source_item(derivatives[0])) is (
        venue.RequestedEffect
    )

    forged = copy(created)
    object.__setattr__(forged, "_venue_derivatives", ())
    with pytest.raises(ValueError, match="derivative proof"):
        acquisition._m2_acquisition_transition_venue_derivatives(forged)


def test_current_protection_projection_matches_the_owner_transition_projection() -> (
    None
):
    _, _, claimed, filled = acquisition_fixtures._r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    applied = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert applied.protection is not None
    mandate = applied.state._mandate.protection_mandate

    expected = protection.project_protection_venue(filled, mandate)
    actual = protection._m2_project_current_protection_venue(
        applied.venue,
        applied.execution,
        applied.protection,
    )

    assert (
        actual.cursor_ordinal,
        actual.cursor_head,
        actual.execution_commitment,
        actual.blocking_effect_count,
        actual.blocking_buy_effect_count,
        actual.execution_binding_matches,
        actual.account_reconciliation_clear,
        actual._position_scope,
        actual._mandate_commitment,
        actual._raw_quantity,
        actual._position_root_count,
        actual._basis_available,
        actual._cost_basis,
        actual._basis_metadata_available,
        actual._basis_price,
        actual._integrity,
    ) == (
        expected.cursor_ordinal,
        expected.cursor_head,
        expected.execution_commitment,
        expected.blocking_effect_count,
        expected.blocking_buy_effect_count,
        expected.execution_binding_matches,
        expected.account_reconciliation_clear,
        expected._position_scope,
        expected._mandate_commitment,
        expected._raw_quantity,
        expected._position_root_count,
        expected._basis_available,
        expected._cost_basis,
        expected._basis_metadata_available,
        expected._basis_price,
        expected._integrity,
    )


def _payload_equal_manual_contexts() -> tuple[
    object,
    authority.ExecutionAuthorityState,
    authority.ExecutionAuthorityState,
    object,
    object,
]:
    proof, book, clean, owners = checkpoint_fixtures._dormant_projection_inputs()
    _, _, source, _ = checkpoint_fixtures._manual_projection_inputs()
    flatten_id = authority.ManualFlattenId("manual-flatten-AAPL")
    manual = source._manual_by_id.get(authority._manual_key(flatten_id))
    assert manual is not None

    altered = deepcopy(clean)
    object.__setattr__(
        altered,
        "_manual_by_id",
        authority._inserted(
            clean._manual_by_id,
            authority._manual_key(flatten_id),
            manual,
        ),
    )
    clean_payload = checkpoint_codec.encode_runtime_checkpoint(
        checkpoint_codec._project_runtime_checkpoint(proof, book, clean, owners)
    )
    altered_payload = checkpoint_codec.encode_runtime_checkpoint(
        checkpoint_codec._project_runtime_checkpoint(
            proof,
            altered.venue,
            altered,
            owners,
        )
    )
    assert clean_payload == altered_payload
    return proof, clean, altered, owners[0].execution, manual


def _direct_manual_proof(
    state: authority.ExecutionAuthorityState,
    command: object,
    *,
    active_symbol_id: identity.SymbolId | None = None,
    retained_command: authority.BeginManualFlatten | None = None,
    retained_input_bytes: bytes | None = None,
    retained_outcome_bytes: bytes | None = None,
) -> object:
    return authority._m2_authority_manual_observation_from_direct_evidence(
        state,
        command,
        active_symbol_id=active_symbol_id,
        retained_command=retained_command,
        retained_input_bytes=retained_input_bytes,
        retained_outcome_bytes=retained_outcome_bytes,
    )


def test_manual_kernel_ignores_unbound_payload_equal_history() -> None:
    _, clean, altered, execution, manual = _payload_equal_manual_contexts()
    begin = replace(
        manual.command,
        input_id=authority.AuthorityInputId("uow-fresh-manual-begin"),
    )
    advance = authority.AdvanceManualFlatten(
        authority.AuthorityInputId("uow-fresh-manual-advance"),
        manual.command.flatten_id,
    )

    clean_begin = authority._m2_apply_execution_authority_input(
        clean,
        execution,
        begin,
        manual_observation=_direct_manual_proof(clean, begin),
    )
    altered_begin = authority._m2_apply_execution_authority_input(
        altered,
        execution,
        begin,
        manual_observation=_direct_manual_proof(altered, begin),
    )
    assert (clean_begin.disposition, clean_begin.reason) == (
        altered_begin.disposition,
        altered_begin.reason,
    )
    public_clean_begin = authority.apply_execution_authority_input(
        clean,
        execution,
        begin,
    )
    public_altered_begin = authority.apply_execution_authority_input(
        altered,
        execution,
        begin,
    )
    assert (public_clean_begin.disposition, public_clean_begin.reason) == (
        public_altered_begin.disposition,
        public_altered_begin.reason,
    )

    clean_advance = authority._m2_apply_execution_authority_input(
        clean,
        execution,
        advance,
        manual_observation=_direct_manual_proof(clean, advance),
    )
    altered_advance = authority._m2_apply_execution_authority_input(
        altered,
        execution,
        advance,
        manual_observation=_direct_manual_proof(altered, advance),
    )
    assert (clean_advance.disposition, clean_advance.reason) == (
        altered_advance.disposition,
        altered_advance.reason,
    )
    assert clean_advance.disposition is authority.AuthorityDisposition.REFUSED
    public_clean_advance = authority.apply_execution_authority_input(
        clean,
        execution,
        advance,
    )
    public_altered_advance = authority.apply_execution_authority_input(
        altered,
        execution,
        advance,
    )
    assert (public_clean_advance.disposition, public_clean_advance.reason) == (
        public_altered_advance.disposition,
        public_altered_advance.reason,
    )


def test_manual_sell_requires_the_scope_bound_ready_observation() -> None:
    execution = authority_fixtures._advanced_same_scope_execution(
        quantity=3,
        label="uow-operation-bound-manual",
    )
    clean = authority_fixtures._forge_positive_predecessor(
        authority,
        mode="REDUCING",
        remaining=5,
        reserve=1,
    )
    flatten_id = authority.ManualFlattenId("uow-operation-bound-manual")
    begin = authority.BeginManualFlatten(
        authority.AuthorityInputId("uow-operation-bound-manual-begin"),
        flatten_id,
        clean.session_id,
        execution.position.scope.symbol_id,
        identity.ActorId("uow-operation-bound-operator"),
        "prove the exact active manual flatten",
        identity.EvidenceReference("uow-operation-bound-evidence"),
        None,
    )
    begun = authority.apply_execution_authority_input(clean, execution, begin)
    assert begun.disposition is authority.AuthorityDisposition.APPLIED
    ready = authority.apply_execution_authority_input(
        begun.state,
        execution,
        authority.AdvanceManualFlatten(
            authority.AuthorityInputId("uow-operation-bound-manual-ready"),
            flatten_id,
        ),
    )
    assert ready.disposition is authority.AuthorityDisposition.APPLIED
    manual = ready.state._manual_by_id.get(authority._manual_key(flatten_id))
    assert manual is not None
    assert manual.phase is authority._FlattenPhase.READY

    unbound = deepcopy(clean)
    object.__setattr__(
        unbound,
        "_manual_by_id",
        authority._inserted(
            clean._manual_by_id,
            authority._manual_key(flatten_id),
            manual,
        ),
    )
    assert clean._manual_flatten_by_scope == unbound._manual_flatten_by_scope
    command = authority_fixtures._create_command(
        authority,
        clean,
        label="uow-operation-bound-manual-sell",
        side=authority_fixtures.ExecutionSide.SELL,
        quantity=execution.position.authorized_residual_sell.value,
        manual_flatten_id=flatten_id,
    )
    assert type(command) is authority.CreateBrokerEffect

    for state in (clean, unbound):
        missing = authority._m2_apply_execution_authority_input(
            state,
            execution,
            command,
            manual_observation=None,
        )
        assert missing.disposition is authority.AuthorityDisposition.REFUSED
        assert missing.reason is authority.AuthorityReason.MANUAL_FLATTEN_INVALID

        proof = authority._m2_authority_manual_observation_from_direct_evidence(
            state,
            command,
            active_symbol_id=execution.position.scope.symbol_id,
            retained_command=None,
            retained_input_bytes=None,
            retained_outcome_bytes=None,
        )
        direct = authority._m2_apply_execution_authority_input(
            state,
            execution,
            command,
            manual_observation=proof,
        )
        public = authority.apply_execution_authority_input(
            state,
            execution,
            command,
        )
        assert (direct.disposition, direct.reason) == (
            authority.AuthorityDisposition.REFUSED,
            authority.AuthorityReason.MANUAL_FLATTEN_INVALID,
        )
        assert (public.disposition, public.reason) == (
            direct.disposition,
            direct.reason,
        )

    bound_proof = authority._m2_authority_manual_observation_from_direct_evidence(
        ready.state,
        command,
        active_symbol_id=execution.position.scope.symbol_id,
        retained_command=None,
        retained_input_bytes=None,
        retained_outcome_bytes=None,
    )
    bound = authority._m2_apply_execution_authority_input(
        ready.state,
        execution,
        command,
        manual_observation=bound_proof,
    )
    assert bound.disposition is authority.AuthorityDisposition.APPLIED
    assert bound.created_effect_ids == (command.request.effect_id,)


def test_manual_direct_proof_requires_retained_bytes_and_terminal_outcome() -> None:
    _, clean, _, execution, manual = _payload_equal_manual_contexts()
    begin = replace(
        manual.command,
        input_id=authority.AuthorityInputId("uow-retained-manual-begin"),
    )
    with pytest.raises(ValueError, match="retained evidence"):
        _direct_manual_proof(
            clean,
            begin,
            retained_command=manual.command,
            retained_input_bytes=b"retained-input",
        )

    retained = _direct_manual_proof(
        clean,
        begin,
        retained_command=manual.command,
        retained_input_bytes=b"retained-input",
        retained_outcome_bytes=b"retained-terminal-outcome",
    )
    result = authority._m2_apply_execution_authority_input(
        clean,
        execution,
        begin,
        manual_observation=retained,
    )
    assert result.disposition is authority.AuthorityDisposition.CONFLICT


def test_manual_active_current_direct_proof_matches_public_owner_route() -> None:
    _, _, state, owners = checkpoint_fixtures._manual_projection_inputs()
    flatten_id = authority.ManualFlattenId("manual-flatten-AAPL")
    manual = state._manual_by_id.get(authority._manual_key(flatten_id))
    assert manual is not None
    advance = authority.AdvanceManualFlatten(
        authority.AuthorityInputId("uow-active-manual-advance"),
        flatten_id,
    )
    proof = _direct_manual_proof(
        state,
        advance,
        active_symbol_id=manual.command.symbol_id,
    )

    direct = authority._m2_apply_execution_authority_input(
        state,
        owners[0].execution,
        advance,
        manual_observation=proof,
    )
    public = authority.apply_execution_authority_input(
        state,
        owners[0].execution,
        advance,
    )
    assert (direct.disposition, direct.reason, direct.state) == (
        public.disposition,
        public.reason,
        public.state,
    )


def test_manual_observation_proof_is_owner_issued_and_required() -> None:
    _, clean, _, execution, manual = _payload_equal_manual_contexts()
    begin = replace(
        manual.command,
        input_id=authority.AuthorityInputId("uow-forged-manual-proof"),
    )
    with pytest.raises(TypeError, match="owner-issued"):
        authority._M2AuthorityManualObservationProof()
    forged = object.__new__(authority._M2AuthorityManualObservationProof)
    with pytest.raises(ValueError, match="observation proof"):
        authority._m2_apply_execution_authority_input(
            clean,
            execution,
            begin,
            manual_observation=forged,
        )


def test_query_kernel_ignores_omitted_payload_equal_history() -> None:
    _, _, clean, owners = checkpoint_fixtures._dormant_projection_inputs()
    retained = authority.ClaimBrokerQuery(
        identity.AuthorityInputId("retained-query-input"),
        identity.QueryClaimId("query-identity"),
        identity.SymbolId("AAPL"),
        authority.AuthorityQueryKind.QUERY,
    )
    command = replace(
        retained,
        input_id=identity.AuthorityInputId("fresh-query-input"),
    )
    altered = deepcopy(clean)
    object.__setattr__(
        altered,
        "_query_by_id",
        authority._inserted(
            clean._query_by_id,
            authority._query_key(retained.query_claim_id),
            retained,
        ),
    )
    object.__setattr__(
        altered,
        "_input_by_id",
        authority._inserted(
            clean._input_by_id,
            authority._input_key(retained.input_id),
            retained,
        ),
    )

    clean_proof = authority._m2_authority_query_observation_from_direct_evidence(
        clean,
        command,
        retained_command=None,
        retained_input_bytes=None,
        retained_outcome_bytes=None,
    )
    altered_absence = authority._m2_authority_query_observation_from_direct_evidence(
        altered,
        command,
        retained_command=None,
        retained_input_bytes=None,
        retained_outcome_bytes=None,
    )
    clean_result = authority._m2_apply_execution_authority_input(
        clean,
        owners[0].execution,
        command,
        manual_observation=None,
        query_observation=clean_proof,
    )
    altered_result = authority._m2_apply_execution_authority_input(
        altered,
        owners[0].execution,
        command,
        manual_observation=None,
        query_observation=altered_absence,
    )
    assert (clean_result.disposition, clean_result.reason) == (
        altered_result.disposition,
        altered_result.reason,
    )

    retained_proof = authority._m2_authority_query_observation_from_direct_evidence(
        altered,
        command,
        retained_command=retained,
        retained_input_bytes=b"retained-query-input",
        retained_outcome_bytes=b"retained-query-outcome",
    )
    direct_retained = authority._m2_apply_execution_authority_input(
        altered,
        owners[0].execution,
        command,
        manual_observation=None,
        query_observation=retained_proof,
    )
    public_retained = authority.apply_execution_authority_input(
        altered,
        owners[0].execution,
        command,
    )
    assert direct_retained.disposition is authority.AuthorityDisposition.CONFLICT
    assert public_retained.disposition is authority.AuthorityDisposition.CONFLICT


def _emergency_create_inputs() -> tuple[
    authority.ExecutionAuthorityState,
    object,
    authority.CreateBrokerEffect,
    identity.EmergencyGrantId,
]:
    execution = authority_fixtures._advanced_same_scope_execution(
        label="uow-grant-proof"
    )
    base = authority_fixtures._forge_positive_predecessor(
        authority,
        mode="HALTED",
        kill_engaged=True,
        remaining=2,
        reserve=1,
    )
    state, grant_id = authority_fixtures._forge_emergency_grant(
        authority,
        base,
        label="uow-grant-proof",
    )
    command = authority_fixtures._create_command(
        authority,
        state,
        label="uow-grant-proof",
        side=authority_fixtures.ExecutionSide.SELL,
        emergency_grant_id=grant_id,
    )
    assert type(state) is authority.ExecutionAuthorityState
    assert type(command) is authority.CreateBrokerEffect
    assert type(grant_id) is identity.EmergencyGrantId
    return state, execution, command, grant_id


def test_grant_kernel_ignores_omitted_consumed_map_with_direct_absence() -> None:
    state, execution, command, grant_id = _emergency_create_inputs()
    altered = deepcopy(state)
    object.__setattr__(
        altered,
        "_consumed_grant_ids",
        authority._inserted(
            state._consumed_grant_ids,
            authority._grant_key(grant_id),
            True,
        ),
    )
    clean_proof = authority._m2_authority_grant_observation_from_direct_evidence(
        state,
        grant_id,
        retained_claim=None,
        retained_input_bytes=None,
        retained_outcome_bytes=None,
    )
    altered_proof = authority._m2_authority_grant_observation_from_direct_evidence(
        altered,
        grant_id,
        retained_claim=None,
        retained_input_bytes=None,
        retained_outcome_bytes=None,
    )

    clean = authority._m2_apply_execution_authority_input(
        state,
        execution,
        command,
        manual_observation=None,
        grant_observation=clean_proof,
    )
    direct = authority._m2_apply_execution_authority_input(
        altered,
        execution,
        command,
        manual_observation=None,
        grant_observation=altered_proof,
    )
    reference = authority.apply_execution_authority_input(
        altered,
        execution,
        command,
    )

    assert clean.disposition is authority.AuthorityDisposition.APPLIED
    assert (direct.disposition, direct.reason, direct.created_effect_ids) == (
        clean.disposition,
        clean.reason,
        clean.created_effect_ids,
    )
    assert reference.disposition is authority.AuthorityDisposition.REFUSED
    assert reference.reason is authority.AuthorityReason.EMERGENCY_GRANT_MISMATCH


def test_grant_direct_proof_requires_complete_terminal_claim_evidence() -> None:
    state, execution, command, grant_id = _emergency_create_inputs()
    retained_claim = authority.ClaimEffect(
        identity.AuthorityInputId("retained-grant-claim-input"),
        command.request.effect_id,
        identity.ClaimOccurrenceId("retained-grant-claim"),
    )
    with pytest.raises(ValueError, match="retained grant evidence"):
        authority._m2_authority_grant_observation_from_direct_evidence(
            state,
            grant_id,
            retained_claim=retained_claim,
            retained_input_bytes=b"retained-input",
            retained_outcome_bytes=None,
        )

    consumed = authority._m2_authority_grant_observation_from_direct_evidence(
        state,
        grant_id,
        retained_claim=retained_claim,
        retained_input_bytes=b"retained-input",
        retained_outcome_bytes=b"retained-terminal-outcome",
    )
    refused = authority._m2_apply_execution_authority_input(
        state,
        execution,
        command,
        manual_observation=None,
        grant_observation=consumed,
    )
    assert refused.disposition is authority.AuthorityDisposition.REFUSED
    assert refused.reason is authority.AuthorityReason.EMERGENCY_GRANT_MISMATCH
    with pytest.raises(TypeError, match="owner-issued"):
        authority._M2AuthorityGrantObservationProof()


def test_venue_transition_source_is_bound_to_the_owner_proof() -> None:
    state, execution, command, grant_id = _emergency_create_inputs()
    proof = authority._m2_authority_grant_observation_from_direct_evidence(
        state,
        grant_id,
        retained_claim=None,
        retained_input_bytes=None,
        retained_outcome_bytes=None,
    )
    created = authority._m2_apply_execution_authority_input(
        state,
        execution,
        command,
        manual_observation=None,
        grant_observation=proof,
    )
    assert len(created.venue_transitions) == 1
    transition = created.venue_transitions[0]
    source = venue._m2_venue_transition_source_item(transition)
    assert type(source) is venue.RequestedEffect
    assert source.effect_id == command.request.effect_id

    forged = copy(transition)
    object.__setattr__(
        forged,
        "_source_item",
        replace(source, effect_id=identity.EffectId("substituted-effect")),
    )
    with pytest.raises(ValueError, match="source does not match"):
        venue._m2_venue_transition_source_item(forged)


def test_direct_broker_fact_catch_up_retains_exact_owner_attribution() -> None:
    book, predecessor = recovery_fixtures._seed_needs_review(capacity=4)
    fact = recovery_fixtures._broker_fill(
        "m2-direct-owned-fill",
        "m2-direct-owned-root",
        quantity=4,
    )
    applied = position.apply_broker_execution_fact(
        predecessor.position,
        predecessor.integrity,
        predecessor.root_heads,
        predecessor.seen_facts,
        fact,
    )
    assert applied.disposition is position.TransitionDisposition.APPLIED
    successor = position.ExecutionSnapshot(
        applied.position,
        applied.integrity,
        applied.root_heads,
        applied.seen_facts,
    )

    transition = venue._m2_catch_up_broker_execution_fact(
        book,
        predecessor,
        successor,
        fact,
    )

    assert transition.disposition is venue.VenueRecoveryDisposition.APPLIED
    [outcome] = transition.book.execution_reconciliations
    assert type(outcome) is venue._AttributedRegistryAdvanceOutcome
    assert outcome.attribution_resolved is True
    assert outcome.effect_id == recovery_fixtures.EFFECT
    assert outcome.leg_key == recovery_fixtures.LEG_A
    assert outcome.fact == fact
    assert outcome.observation_classification in {
        fills.FirstObservationClassification.APPLIED_AVAILABLE,
        fills.FirstObservationClassification.APPLIED_BASIS_PENDING,
        fills.FirstObservationClassification.APPLIED_OVERFILL_QUARANTINE,
        fills.FirstObservationClassification.APPLIED_PENDING_OVERFILL,
    }
    assert transition.book._unresolved_account_execution_reconciliation_count == 0
    assert transition.execution.seen_facts.get(fact.key).fact == fact
    assert venue._acquisition_fact_proof_is_authentic(
        transition._acquisition_fact_proof
    )
    transition.book._validate_full()
    source = venue._m2_venue_transition_source_item(transition)
    assert type(source) is venue._BrokerExecutionRegistryCatchUp
    with pytest.raises(TypeError, match="internal venue input"):
        venue.apply_venue_recovery_input(book, predecessor, source)
    hydrated = venue._audit_hydrate_book(transition.book, transition.execution)
    assert (
        hydrated._acquisition_correlation_by_root.commitment
        == transition.book._acquisition_correlation_by_root.commitment
    )


def test_direct_broker_fact_catch_up_rejects_a_non_owner_successor() -> None:
    book, predecessor = recovery_fixtures._seed_needs_review(capacity=4)
    fact = recovery_fixtures._broker_fill(
        "m2-direct-owner-mismatch",
        "m2-direct-owner-mismatch-root",
        leg_key=replace(
            recovery_fixtures.LEG_A,
            order_id=identity.OrderId("not-the-retained-owner"),
        ),
        quantity=4,
    )
    applied = position.apply_broker_execution_fact(
        predecessor.position,
        predecessor.integrity,
        predecessor.root_heads,
        predecessor.seen_facts,
        fact,
    )
    successor = position.ExecutionSnapshot(
        applied.position,
        applied.integrity,
        applied.root_heads,
        applied.seen_facts,
    )

    with pytest.raises(ValueError, match="no exact current venue owner"):
        venue._m2_catch_up_broker_execution_fact(
            book,
            predecessor,
            successor,
            fact,
        )


def test_broker_operation_uses_one_position_classification_and_owned_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, claimed, filled = acquisition_fixtures._r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    source = venue._m2_venue_transition_source_item(filled)
    assert type(source) is recovery_fixtures.RecordBrokerFillEvidence
    fact = source.fact
    operation = operations.BrokerExecutionOperation(
        operations.ExecutionOperationCoordinates(
            claimed.state.application_generation_id,
            "ep",
            7,
        ),
        fact,
    )
    prepared = _prepared_acquisition_operation(operation, claimed)
    owner = filled.book.owner(source.leg_key)
    assert owner is not None
    effect = filled.book._current_effect(owner.effect_id)
    assert effect is not None
    generation_id = claimed.state._controller.live_generation_id
    assert generation_id is not None
    effect_record = records.VenueEffectRecord(
        41,
        effect.scope.effect_id,
        7,
        claimed.state.application_generation_id,
        "ep",
        generation_id,
        claimed.state._mandate.binding.commitment.hex(),
        10,
        3,
        "NORMAL",
        effect.scope.request_occurrence_id,
        effect.scope.mandate_id,
        effect.scope.kind.value,
        effect.scope.client_order_id,
        None,
        effect.scope.side.value,
        effect.scope.quantity,
        effect.scope.economic_scope,
        effect.state.value,
        effect.acceptance_set_state.value,
        None,
        None,
        None,
        None,
        1,
    )
    owner_record = records.VenueIdentityOwnerRecord(
        7,
        "ep",
        owner.leg_key.order_id,
        owner.observation_id,
        effect_record.effect_id,
        None,
        generation_id,
        False,
    )
    monkeypatch.setattr(
        unit_of_work,
        "_broker_execution_predecessor_records",
        lambda *args: (None, None, None),
    )
    monkeypatch.setattr(
        unit_of_work,
        "_broker_owner_records",
        lambda *args: (effect_record, owner_record),
    )
    acquisition_result = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert (
        acquisition_result.disposition
        is acquisition.AcquisitionControllerDisposition.APPLIED
    )
    venue_calls: list[tuple[object, ...]] = []
    acquisition_calls: list[tuple[object, ...]] = []

    def catch_up(*args: object) -> venue.VenueRecoveryTransition:
        venue_calls.append(args)
        assert args == (claimed.venue, claimed.execution, filled.execution, fact)
        return filled

    def reduce(*args: object) -> acquisition.AcquisitionControllerTransition:
        acquisition_calls.append(args)
        assert args == (claimed.state, filled, None, claimed.authority)
        return acquisition_result

    monkeypatch.setattr(
        unit_of_work._venue, "_m2_catch_up_broker_execution_fact", catch_up
    )
    monkeypatch.setattr(
        unit_of_work._acquisition,
        "reduce_acquisition_controller",
        reduce,
    )

    (
        execution_transition,
        acquisition_transition,
        derivatives,
        selected,
        root,
        route,
        predecessor,
        selected_effect,
        selected_owner,
    ) = unit_of_work._broker_execution_transition_for_operation(object(), prepared)

    assert execution_transition.disposition is position.TransitionDisposition.APPLIED
    assert (
        acquisition_transition.disposition
        is acquisition.AcquisitionControllerDisposition.APPLIED
    )
    assert acquisition_transition.execution == filled.execution
    assert selected.generation.acquisition_generation_id == generation_id
    assert (root, route, predecessor) == (None, None, None)
    assert (selected_effect, selected_owner) == (effect_record, owner_record)
    assert venue_calls == [
        (claimed.venue, claimed.execution, filled.execution, fact),
    ]
    assert acquisition_calls == [
        (claimed.state, filled, None, claimed.authority),
    ]
    assert derivatives == acquisition._m2_acquisition_transition_venue_derivatives(
        acquisition_transition
    )


def test_broker_operation_preserves_an_unowned_fact_for_quarantine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, claimed, filled = acquisition_fixtures._r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    source = venue._m2_venue_transition_source_item(filled)
    assert type(source) is recovery_fixtures.RecordBrokerFillEvidence
    operation = operations.BrokerExecutionOperation(
        operations.ExecutionOperationCoordinates(
            claimed.state.application_generation_id,
            "ep",
            7,
        ),
        source.fact,
    )
    prepared = _prepared_acquisition_operation(operation, claimed)
    monkeypatch.setattr(
        unit_of_work,
        "_broker_execution_predecessor_records",
        lambda *args: (None, None, None),
    )
    monkeypatch.setattr(
        unit_of_work,
        "_broker_owner_records",
        lambda *args: None,
    )
    monkeypatch.setattr(
        unit_of_work._venue,
        "_m2_catch_up_broker_execution_fact",
        lambda *args: pytest.fail("unowned fact reached the attributed venue reducer"),
    )

    (
        execution_transition,
        acquisition_transition,
        derivatives,
        selected,
        root,
        route,
        predecessor,
        effect,
        owner,
    ) = unit_of_work._broker_execution_transition_for_operation(object(), prepared)

    assert execution_transition.disposition is position.TransitionDisposition.APPLIED
    assert execution_transition.position == filled.execution.position
    assert acquisition_transition is None
    assert derivatives == ()
    assert selected.generation.acquisition_generation_id == (
        claimed.state._controller.live_generation_id
    )
    assert (root, route, predecessor, effect, owner) == (None, None, None, None, None)


@pytest.mark.parametrize("revision_kind", ("correct", "bust"))
def test_route_less_broker_revisions_advance_truth_without_inventing_attribution(
    monkeypatch: pytest.MonkeyPatch,
    revision_kind: str,
) -> None:
    fill = recovery_fixtures._broker_fill(
        "uow-route-less-fill-source",
        "uow-route-less-fill-root",
        quantity=2,
    )
    initial = position.ExecutionSnapshot.flat(fill.scope.position_scope)
    applied_fill = position.apply_broker_execution_fact(
        initial.position,
        initial.integrity,
        initial.root_heads,
        initial.seen_facts,
        fill,
    )
    predecessor_execution = position.ExecutionSnapshot(
        applied_fill.position,
        applied_fill.integrity,
        applied_fill.root_heads,
        applied_fill.seen_facts,
    )
    if revision_kind == "correct":
        fact: fills.BrokerTradeCorrectFact | fills.BrokerTradeBustFact = (
            fills.BrokerTradeCorrectFact(
                replace(
                    fill.key,
                    source_event_id=identity.SourceEventId(
                        "uow-route-less-correct-source"
                    ),
                ),
                fill.scope,
                fill.root_fill_id,
                fill.key.source_event_id,
                authority_fixtures.Quantity(3),
                fill.price,
            )
        )
    else:
        fact = fills.BrokerTradeBustFact(
            replace(
                fill.key,
                source_event_id=identity.SourceEventId("uow-route-less-bust-source"),
            ),
            fill.scope,
            fill.root_fill_id,
            fill.key.source_event_id,
            fill.price,
        )
    transition = position.apply_broker_execution_fact(
        predecessor_execution.position,
        predecessor_execution.integrity,
        predecessor_execution.root_heads,
        predecessor_execution.seen_facts,
        fact,
    )
    assert transition.disposition is position.TransitionDisposition.APPLIED

    application_generation_id = authority_fixtures.GENERATION
    generation_id = identity.AcquisitionGenerationId("ab" * 32)
    operation = operations.BrokerExecutionOperation(
        operations.ExecutionOperationCoordinates(
            application_generation_id,
            "ep",
            7,
        ),
        fact,
    )
    prepared = SimpleNamespace(
        operation=operation,
        scope_id=7,
        application_generation_id=application_generation_id,
        execution_profile_id="ep",
        context=object(),
    )
    root = records.RootFillRecord(
        11,
        7,
        application_generation_id,
        "ep",
        generation_id,
        fill.root_fill_id,
        13,
        fill.kind.value,
        fill.authority.value,
        fill.scope.side.value,
        fill.quantity,
        fill.price,
        17,
    )
    predecessor_fact = records.ExecutionFactRecord(
        13,
        7,
        application_generation_id,
        "ep",
        root.root_fill_key_id,
        fill.key.source_event_id,
        fill.scope.order_id,
        fill.scope.side.value,
        fill.kind.value,
        fill.authority.value,
        fill.quantity,
        fill.price,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        17,
    )
    controller = records.SymbolControllerRecord(
        7,
        application_generation_id,
        "ep",
        generation_id,
        fill.quantity.value,
        "UNMATCHED_LINEAGE_QUARANTINED",
        10,
        3,
        "aa" * 32,
    )
    generation_current = records.AcquisitionGenerationCurrentRecord(
        generation_id,
        7,
        0,
        0,
        0,
    )
    selected = SimpleNamespace(
        generation=SimpleNamespace(acquisition_generation_id=generation_id),
        controller=controller,
        generation_current=generation_current,
    )
    captured: dict[str, records.ExecutionFactRecord] = {}

    monkeypatch.setattr(
        unit_of_work,
        "_broker_execution_transition_for_operation",
        lambda *args: (
            transition,
            None,
            (),
            selected,
            root,
            None,
            predecessor_fact,
            None,
            None,
        ),
    )
    monkeypatch.setattr(unit_of_work, "_next_execution_fact_id", lambda *args: 14)
    monkeypatch.setattr(
        unit_of_work,
        "_next_execution_fact_ordinal",
        lambda *args: 18,
    )

    def found(record: object) -> records.RepositoryOutcome[object]:
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.FOUND, record)

    def store_fact(
        connection: object,
        record: records.ExecutionFactRecord,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[object]:
        del connection, capability
        captured["fact"] = record
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    def resulting_root(*args: object) -> records.RepositoryOutcome[object]:
        del args
        retained = captured["fact"]
        return found(
            replace(
                root,
                current_fact_id=retained.fact_id,
                current_kind=retained.kind,
                current_authority=retained.authority,
                current_side=retained.side,
                current_quantity=retained.quantity,
                current_price=retained.price,
                economics_head_ordinal=retained.fact_ordinal,
            )
        )

    monkeypatch.setattr(unit_of_work._repository, "store_execution_fact", store_fact)
    monkeypatch.setattr(unit_of_work._repository, "load_root_fill", resulting_root)
    monkeypatch.setattr(
        unit_of_work._repository,
        "load_acquisition_root_route",
        lambda *args: records.RepositoryOutcome(records.RepositoryOutcomeKind.ABSENT),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "load_execution_fact_by_source",
        lambda *args: found(captured["fact"]),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "load_symbol_controller",
        lambda *args: found(
            replace(
                controller,
                aggregate_quantity=transition.position.raw_quantity,
                integrity_state="UNMATCHED_LINEAGE_QUARANTINED",
                currentness_head_ordinal=controller.currentness_head_ordinal + 1,
                controller_version_ordinal=controller.controller_version_ordinal + 1,
            )
        ),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "load_acquisition_generation_current",
        lambda *args: found(generation_current),
    )
    completed: list[dict[str, object]] = []
    sentinel = object()

    def complete(*args: object, **kwargs: object) -> object:
        del args
        completed.append(kwargs)
        return sentinel

    monkeypatch.setattr(unit_of_work, "_complete_claimed_input", complete)

    result = unit_of_work._execute_broker_execution_operation(
        object(),
        prepared,
        object(),
        object(),
    )

    assert result is sentinel
    assert captured["fact"].predecessor_fact_id == predecessor_fact.fact_id
    assert captured["fact"].source_event_id == fact.key.source_event_id
    assert completed[0]["owner_disposition"] == "RECONCILIATION_REQUIRED"
    assert completed[0]["checkpoint_changed"] is False
    assert completed[0]["successor_context"] is prepared.context


def _apply_direct_venue_observation(
    book: venue.VenueRecoveryBook,
    execution: position.ExecutionSnapshot,
    item: object,
) -> tuple[venue.VenueRecoveryTransition, venue._M2VenueObservationProof]:
    state = venue._m2_venue_state_from_book(book)
    proof = venue._m2_venue_observation_from_direct_evidence(
        state,
        item,
        retained_item=None,
        retained_input_bytes=None,
        retained_outcome_bytes=None,
        retained_fact_item=None,
        retained_fact_input_bytes=None,
        retained_fact_outcome_bytes=None,
    )
    return (
        venue._m2_apply_venue_input_from_direct_observation(
            state,
            execution,
            proof,
        ),
        proof,
    )


def test_direct_venue_refresh_rebases_a_dormant_controller_without_economics() -> None:
    _, scope, claimed = acquisition_fixtures._r8_claimed_first_effect()
    assert claimed.fresh_claim is not None
    item = venue.RecordTransportOutcome(
        venue.VenueInputId("uow-o2-dormant-transport"),
        claimed.fresh_claim.effect_id,
        venue.BrokerEffectState.OUTCOME_UNKNOWN,
    )
    venue_transition, observation = _apply_direct_venue_observation(
        claimed.venue,
        claimed.execution,
        item,
    )
    refresh = authority._m2_refresh_acquisition_context_from_venue_transition(
        claimed.authority,
        claimed.execution,
        scope,
        venue_transition,
        observation,
    )
    rebased, protection_transition = acquisition._m2_rebase_acquisition_venue(
        claimed.state,
        refresh,
        None,
    )

    assert (
        refresh.disposition is authority.AcquisitionContextRefreshDisposition.REFRESHED
    )
    assert venue_transition.disposition is venue.VenueRecoveryDisposition.APPLIED
    assert venue_transition.quantity_delta == 0
    assert rebased.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert protection_transition is None
    assert rebased.protection is None
    assert rebased.venue is venue_transition.book
    assert rebased.authority is refresh.authority
    assert rebased.execution is venue_transition.execution
    assert rebased.execution.commitment == claimed.execution.commitment
    assert rebased.state.registry is claimed.state.registry
    assert rebased.state.lineage is claimed.state.lineage
    assert (
        rebased.state._controller.controller_head
        == claimed.state._controller.controller_head
    )
    assert refresh.venue_context is not None
    assert rebased.state.scope_execution_commitment == (
        refresh.venue_context.scope_execution_commitment
    )
    assert rebased.state.venue_commitment == refresh.venue_context.commitment


def test_venue_operation_composes_the_direct_owner_with_acquisition_currentness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, claimed = acquisition_fixtures._r8_claimed_first_effect()
    assert claimed.fresh_claim is not None
    item = venue.RecordTransportOutcome(
        venue.VenueInputId("uow-o2-composite-transport"),
        claimed.fresh_claim.effect_id,
        venue.BrokerEffectState.OUTCOME_UNKNOWN,
    )
    transition, observation = _apply_direct_venue_observation(
        claimed.venue,
        claimed.execution,
        item,
    )
    operation = operations.VenueRecoveryOperation(
        operations.VenueOperationCoordinates(
            claimed.state.application_generation_id,
            "ep",
            7,
            claimed.state._mandate.session_id,
        ),
        item,
    )
    prepared = _prepared_acquisition_operation(operation, claimed)
    monkeypatch.setattr(
        unit_of_work,
        "_venue_direct_observation",
        lambda *args: (
            venue._m2_venue_state_from_book(claimed.venue),
            observation,
        ),
    )

    actual, rebased, derivatives, selected, relation = (
        unit_of_work._venue_composite_transition_for_operation(object(), prepared)
    )

    assert actual == transition
    assert relation is None
    assert rebased is not None
    assert rebased.venue is actual.book
    assert rebased.execution is actual.execution
    assert rebased.authority.venue is actual.book
    assert selected.controller.currentness_head_ordinal == 10
    assert derivatives == acquisition._m2_acquisition_transition_venue_derivatives(
        rebased
    )


def test_acknowledged_venue_write_defers_delta_check_to_fresh_checkpoint_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_proof, book, authority_state, owners = (
        hydration_fixtures._active_claimed_projection_inputs()
    )
    owner = owners[0]
    assert owner.acquisition is not None
    assert owner.protection is None
    assert source_proof._selection.cursors == ()
    selected_effect = source_proof._selection.effects[0]
    assert selected_effect.lifecycle_state == "DISPATCH_CLAIMED"
    source_envelope = checkpoint_codec._project_runtime_checkpoint(
        source_proof,
        book,
        authority_state,  # type: ignore[arg-type]
        owners,
    )
    predecessor = records.KernelCheckpointRecord(
        source_envelope.application_generation_id,
        source_envelope.currentness_head_ordinal,
        source_envelope.payload_sha256,
        source_envelope.checkpoint_version_ordinal,
    )
    context = unit_of_work.UnitOfWorkContext(
        predecessor,
        book,
        authority_state,  # type: ignore[arg-type]
        tuple(
            (item.scope_id, item.acquisition, item.execution, item.protection)
            for item in owners
        ),
    )
    effect_id = selected_effect.effect_external
    item = venue.RecordTransportOutcome(
        venue.VenueInputId("uow-o2-acknowledged-fresh-proof"),
        effect_id,
        venue.BrokerEffectState.ACKNOWLEDGED,
    )
    transition, observation = _apply_direct_venue_observation(
        book,
        owner.execution,
        item,
    )
    operation = operations.VenueRecoveryOperation(
        operations.VenueOperationCoordinates(
            source_proof.request.application_generation_id,
            source_proof.request.execution_profile_id,
            owner.scope_id,
            source_proof._selection.streams[0].session_id,
        ),
        item,
    )
    payload = operations.encode_m2_operation(operation)
    (
        domain,
        application_generation_id,
        execution_profile_id,
        scope_id,
        session_id,
        acquisition_generation_id,
        market_source_profile_id,
        stream_generation_id,
        input_identity_sha256,
    ) = operations._derive_m2_durable_input_projection(operation)
    prepared = unit_of_work._PreparedOperation(
        operation,
        context,
        payload,
        domain,
        application_generation_id,
        execution_profile_id,
        scope_id,
        session_id,
        acquisition_generation_id,
        market_source_profile_id,
        stream_generation_id,
        input_identity_sha256,
        source_proof,
        source_envelope,
    )
    monkeypatch.setattr(
        unit_of_work,
        "_venue_direct_observation",
        lambda *args: (
            venue._m2_venue_state_from_book(book),
            observation,
        ),
    )
    monkeypatch.setattr(
        unit_of_work,
        "_store_venue_transition_semantic_keys",
        lambda *args: None,
    )
    monkeypatch.setattr(
        unit_of_work,
        "_persist_venue_owner_rows",
        lambda *args: (object(), None, False),
    )
    monkeypatch.setattr(
        unit_of_work,
        "_persist_venue_terminal_closure",
        lambda *args: None,
    )
    monkeypatch.setattr(
        unit_of_work,
        "_advance_acquisition_currentness",
        lambda *args: object(),
    )
    monkeypatch.setattr(
        unit_of_work,
        "_persist_authority_venue_transitions",
        lambda *args, **kwargs: ((), ()),
    )
    selected_controller = source_proof._selection.controllers[0]
    selected_protection = source_proof._selection.protection_authorities[0]
    fresh_selection = replace(
        source_proof._selection,
        controllers=(
            replace(
                selected_controller,
                currentness_head_ordinal=(
                    selected_controller.currentness_head_ordinal + 1
                ),
                controller_version_ordinal=(
                    selected_controller.controller_version_ordinal + 1
                ),
            ),
        ),
        protection_authorities=(
            replace(
                selected_protection,
                expected_controller_head_ordinal=(
                    selected_protection.expected_controller_head_ordinal + 1
                ),
                version_ordinal=selected_protection.version_ordinal + 1,
            ),
        ),
        effects=(replace(selected_effect, lifecycle_state="ACKNOWLEDGED"),),
    )
    fresh_proof = records._issue_runtime_checkpoint_selection_proof(
        records.RuntimeCheckpointSelectionRequest(
            source_proof.request.application_generation_id,
            source_proof.request.execution_profile_id,
            source_proof.request.market_source_profile_id,
            predecessor,
        ),
        source_proof.application_generation,
        source_proof.execution_profile,
        source_proof.market_source_profile,
        predecessor,
        predecessor.currentness_head_ordinal + 1,
        predecessor.checkpoint_version_ordinal + 1,
        fresh_selection,
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "select_runtime_checkpoint",
        lambda *args: records.RepositoryOutcome(
            records.RepositoryOutcomeKind.FOUND,
            fresh_proof,
        ),
    )
    project = checkpoint_codec._project_runtime_checkpoint
    projected_with: list[records.RuntimeCheckpointSelectionProof] = []

    def project_with_fresh_proof(
        proof: records.RuntimeCheckpointSelectionProof,
        *args: object,
    ) -> checkpoint_codec.RuntimeCheckpointEnvelope:
        assert proof is fresh_proof
        projected_with.append(proof)
        return project(proof, *args)  # type: ignore[arg-type]

    monkeypatch.setattr(
        unit_of_work._checkpoint_codec,
        "_project_runtime_checkpoint",
        project_with_fresh_proof,
    )
    stored_with: list[records.RuntimeCheckpointSelectionProof] = []

    def stop_after_projection(
        connection: object,
        proof: records.RuntimeCheckpointSelectionProof,
        envelope: checkpoint_codec.RuntimeCheckpointEnvelope,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[object]:
        del connection, capability
        assert proof is fresh_proof
        assert (
            envelope.canonical_payload_bytes != source_envelope.canonical_payload_bytes
        )
        stored_with.append(proof)
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.CONFLICT)

    monkeypatch.setattr(
        unit_of_work._repository,
        "store_runtime_checkpoint",
        stop_after_projection,
    )

    with pytest.raises(
        unit_of_work._TechnicalRefusal,
        match="successor checkpoint was not stored exactly",
    ):
        unit_of_work._execute_venue_operation(
            object(),
            prepared,
            object(),
            object(),
        )

    assert projected_with == [fresh_proof]
    assert stored_with == [fresh_proof]


def test_fresh_venue_input_emits_only_its_owner_proven_semantic_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, claimed = acquisition_fixtures._r8_claimed_first_effect()
    assert claimed.fresh_claim is not None
    item = venue.RecordTransportOutcome(
        venue.VenueInputId("uow-o2-semantic-transport"),
        claimed.fresh_claim.effect_id,
        venue.BrokerEffectState.OUTCOME_UNKNOWN,
    )
    transition, _ = _apply_direct_venue_observation(
        claimed.venue,
        claimed.execution,
        item,
    )
    operation = operations.VenueRecoveryOperation(
        operations.VenueOperationCoordinates(
            claimed.state.application_generation_id,
            "ep",
            7,
            claimed.state._mandate.session_id,
        ),
        item,
    )
    prepared = _prepared_acquisition_operation(operation, claimed)
    stored: list[tuple[operations.InputSemanticKeyKind, bytes]] = []

    def retain(
        connection: object,
        received_prepared: object,
        received_claimed: object,
        kind: operations.InputSemanticKeyKind,
        key_bytes: bytes,
        capability: object,
    ) -> None:
        del connection, received_claimed, capability
        assert received_prepared is prepared
        stored.append((kind, key_bytes))

    monkeypatch.setattr(unit_of_work, "_store_venue_semantic_key", retain)
    unit_of_work._store_venue_transition_semantic_keys(
        object(),
        prepared,
        object(),
        transition,
        object(),
    )

    assert stored == [
        (
            operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
            unit_of_work._venue_command_key_bytes(prepared, item),
        )
    ]


def test_venue_semantic_alias_does_not_overwrite_the_command_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, claimed = acquisition_fixtures._r8_claimed_first_effect()
    assert claimed.fresh_claim is not None
    first_item = venue.RecordTransportOutcome(
        venue.VenueInputId("uow-o2-semantic-owner"),
        claimed.fresh_claim.effect_id,
        venue.BrokerEffectState.OUTCOME_UNKNOWN,
    )
    first = venue.apply_venue_recovery_input(
        claimed.venue,
        claimed.execution,
        first_item,
    )
    alias_item = replace(
        first_item,
        input_id=venue.VenueInputId("uow-o2-semantic-alias"),
    )
    alias = venue.apply_venue_recovery_input(
        first.book,
        first.execution,
        alias_item,
    )
    operation = operations.VenueRecoveryOperation(
        operations.VenueOperationCoordinates(
            claimed.state.application_generation_id,
            "ep",
            7,
            claimed.state._mandate.session_id,
        ),
        alias_item,
    )
    prepared = SimpleNamespace(
        operation=operation,
        context=SimpleNamespace(venue=first.book),
        execution_profile_id="ep",
    )
    stored: list[operations.InputSemanticKeyKind] = []
    monkeypatch.setattr(
        unit_of_work,
        "_store_venue_semantic_key",
        lambda _connection, _prepared, _claimed, kind, _bytes, _capability: (
            stored.append(kind)
        ),
    )

    unit_of_work._store_venue_transition_semantic_keys(
        object(),
        prepared,
        object(),
        alias,
        object(),
    )

    alias_record = alias.book._input_record(alias_item.input_id)
    retained_owner = first.book._direct_semantic_input(alias_item)
    assert retained_owner is not None
    assert retained_owner.input_id == first_item.input_id
    assert alias_record is None
    assert stored == []


def test_venue_economic_input_emits_the_complete_coverage_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, claimed, filled = acquisition_fixtures._r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    item = venue._m2_venue_transition_source_item(filled)
    assert type(item) is recovery_fixtures.RecordBrokerFillEvidence
    operation = operations.VenueRecoveryOperation(
        operations.VenueOperationCoordinates(
            claimed.state.application_generation_id,
            "ep",
            7,
            claimed.state._mandate.session_id,
        ),
        item,
    )
    prepared = _prepared_acquisition_operation(operation, claimed)
    stored: list[operations.InputSemanticKeyKind] = []

    def retain(
        connection: object,
        received_prepared: object,
        received_claimed: object,
        kind: operations.InputSemanticKeyKind,
        key_bytes: bytes,
        capability: object,
    ) -> None:
        del connection, received_claimed, key_bytes, capability
        assert received_prepared is prepared
        stored.append(kind)

    monkeypatch.setattr(unit_of_work, "_store_venue_semantic_key", retain)
    unit_of_work._store_venue_transition_semantic_keys(
        object(),
        prepared,
        object(),
        filled,
        object(),
    )

    assert stored == [
        operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
        operations.InputSemanticKeyKind.VENUE_EXECUTION_FACT_V1,
        operations.InputSemanticKeyKind.VENUE_COVERAGE_ROOT_V1,
        operations.InputSemanticKeyKind.VENUE_COVERAGE_INTERVAL_V1,
        operations.InputSemanticKeyKind.VENUE_BROKER_FACT_V1,
    ]


def test_venue_direct_observation_loads_every_coverage_semantic_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, claimed, filled = acquisition_fixtures._r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    item = venue._m2_venue_transition_source_item(filled)
    assert type(item) is recovery_fixtures.RecordBrokerFillEvidence
    operation = operations.VenueRecoveryOperation(
        operations.VenueOperationCoordinates(
            claimed.state.application_generation_id,
            "ep",
            7,
            claimed.state._mandate.session_id,
        ),
        item,
    )
    prepared = _prepared_acquisition_operation(operation, claimed)
    looked_up: list[operations.InputSemanticKeyKind] = []

    def load(
        connection: object,
        received_prepared: object,
        kind: operations.InputSemanticKeyKind,
        key_bytes: bytes,
    ) -> None:
        del connection, key_bytes
        assert received_prepared is prepared
        looked_up.append(kind)
        return None

    monkeypatch.setattr(unit_of_work, "_load_terminal_semantic_input", load)
    _, proof = unit_of_work._venue_direct_observation(object(), prepared, item)

    assert looked_up == [
        operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
        operations.InputSemanticKeyKind.VENUE_EXECUTION_FACT_V1,
        operations.InputSemanticKeyKind.VENUE_COVERAGE_ROOT_V1,
        operations.InputSemanticKeyKind.VENUE_COVERAGE_INTERVAL_V1,
        operations.InputSemanticKeyKind.VENUE_BROKER_FACT_V1,
    ]
    assert proof.retained_coverage_items == (None, None, None)
    assert proof.retained_coverage_input_bytes == (None, None, None)
    assert proof.retained_coverage_outcome_bytes == (None, None, None)
    assert venue._m2_venue_observation_proof_is_authentic(proof)


def test_venue_direct_proof_binds_fixed_coverage_owners_into_scoped_state() -> None:
    _, _, claimed, filled = acquisition_fixtures._r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    item = venue._m2_venue_transition_source_item(filled)
    assert type(item) is recovery_fixtures.RecordBrokerFillEvidence
    retained = replace(
        item,
        input_id=venue.VenueInputId("uow-o2-retained-coverage-owner"),
    )
    state = venue._m2_venue_state_from_book(claimed.venue)
    proof = venue._m2_venue_observation_from_direct_evidence(
        state,
        item,
        retained_item=None,
        retained_input_bytes=None,
        retained_outcome_bytes=None,
        retained_fact_item=None,
        retained_fact_input_bytes=None,
        retained_fact_outcome_bytes=None,
        retained_coverage_items=(retained, retained, retained),
        retained_coverage_input_bytes=(b"input", b"input", b"input"),
        retained_coverage_outcome_bytes=(b"outcome", b"outcome", b"outcome"),
    )

    scoped = venue._m2_venue_state_from_direct_proof(state, proof)

    assert venue._m2_venue_observation_proof_is_authentic(proof)
    assert scoped.book._input_record(retained.input_id) is not None
    wrong_interval = replace(
        retained,
        resulting_cumulative_quantity=fills.Quantity(
            retained.resulting_cumulative_quantity.value + 1
        ),
    )
    with pytest.raises(ValueError, match="coverage evidence"):
        venue._m2_venue_observation_from_direct_evidence(
            state,
            item,
            retained_item=None,
            retained_input_bytes=None,
            retained_outcome_bytes=None,
            retained_fact_item=None,
            retained_fact_input_bytes=None,
            retained_fact_outcome_bytes=None,
            retained_coverage_items=(retained, wrong_interval, retained),
            retained_coverage_input_bytes=(b"input", b"input", b"input"),
            retained_coverage_outcome_bytes=(b"outcome", b"outcome", b"outcome"),
        )


def test_execute_prepared_dispatches_venue_operations_to_the_o2_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, claimed = acquisition_fixtures._r8_claimed_first_effect()
    assert claimed.fresh_claim is not None
    item = venue.RecordTransportOutcome(
        venue.VenueInputId("uow-o2-dispatch"),
        claimed.fresh_claim.effect_id,
        venue.BrokerEffectState.OUTCOME_UNKNOWN,
    )
    operation = operations.VenueRecoveryOperation(
        operations.VenueOperationCoordinates(
            claimed.state.application_generation_id,
            "ep",
            7,
            claimed.state._mandate.session_id,
        ),
        item,
    )
    prepared = SimpleNamespace(operation=operation)
    claimed_record = object()
    primary = unit_of_work._ClaimedPrimaryInput(operation, claimed_record)
    expected = object()
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        unit_of_work,
        "_claim_primary_input",
        lambda *args: primary,
    )

    def execute(*args: object) -> object:
        calls.append(args)
        return expected

    monkeypatch.setattr(unit_of_work, "_execute_venue_operation", execute)
    connection = object()
    capability = object()

    actual = unit_of_work._execute_prepared(connection, prepared, capability)

    assert actual is expected
    assert calls == [(connection, prepared, claimed_record, capability)]


def test_human_execution_fact_record_retains_every_attestation_field() -> None:
    fact = recovery_fixtures._human_fill(input_suffix="uow-o2-record")
    prepared = SimpleNamespace(
        scope_id=7,
        application_generation_id=authority_fixtures.GENERATION,
        execution_profile_id="ep",
    )

    record = unit_of_work._venue_execution_fact_record(
        prepared,
        fact,
        fact_id=31,
        root_fill_key_id=29,
        predecessor_fact_id=None,
        fact_ordinal=37,
    )

    assert record == records.ExecutionFactRecord(
        31,
        7,
        authority_fixtures.GENERATION,
        "ep",
        29,
        fact.key.source_event_id,
        fact.scope.order_id,
        fact.scope.side.value,
        fact.kind.value,
        fact.authority.value,
        fact.quantity,
        fact.price,
        fact.request_occurrence_id,
        fact.claim_occurrence_id,
        fact.prior_cumulative_quantity,
        fact.resulting_cumulative_quantity,
        fact.actor,
        fact.reason,
        fact.evidence_reference,
        None,
        37,
    )
    assert unit_of_work._execution_record_matches_fact(
        record,
        fact,
        root_fill_key_id=29,
        predecessor_fact_id=None,
    )
    assert not unit_of_work._execution_record_matches_fact(
        replace(record, actor_id=None),
        fact,
        root_fill_key_id=29,
        predecessor_fact_id=None,
    )


def test_venue_economics_persists_root_route_then_fact_and_reselects_heads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, claimed, filled = acquisition_fixtures._r8_current_generation_fill_transition(
        acknowledged=True,
        prefill_needs_review=False,
    )
    item = venue._m2_venue_transition_source_item(filled)
    assert type(item) is recovery_fixtures.RecordBrokerFillEvidence
    relation = filled.book.project_acquisition_fact(filled).fact_relation()
    assert relation is not None
    operation = operations.VenueRecoveryOperation(
        operations.VenueOperationCoordinates(
            claimed.state.application_generation_id,
            "ep",
            7,
            claimed.state._mandate.session_id,
        ),
        item,
    )
    prepared = _prepared_acquisition_operation(operation, claimed)
    owner = filled.book.owner(item.leg_key)
    effect = filled.book._current_effect(item.effect_id)
    generation_id = claimed.state._controller.live_generation_id
    assert owner is not None
    assert effect is not None
    assert generation_id is not None
    effect_record = records.VenueEffectRecord(
        41,
        effect.scope.effect_id,
        7,
        claimed.state.application_generation_id,
        "ep",
        generation_id,
        claimed.state._mandate.binding.commitment.hex(),
        10,
        3,
        "NORMAL",
        effect.scope.request_occurrence_id,
        effect.scope.mandate_id,
        effect.scope.kind.value,
        effect.scope.client_order_id,
        None,
        effect.scope.side.value,
        effect.scope.quantity,
        effect.scope.economic_scope,
        effect.state.value,
        effect.acceptance_set_state.value,
        None,
        None,
        None,
        None,
        1,
    )
    owner_record = records.VenueIdentityOwnerRecord(
        7,
        "ep",
        owner.leg_key.order_id,
        owner.observation_id,
        effect_record.effect_id,
        None,
        generation_id,
        False,
    )
    selection = prepared.selection_proof._selection
    selection.effects = (effect_record,)
    selection.owners = (owner_record,)
    writes: list[str] = []
    captured: dict[str, object] = {}

    class Connection:
        def execute(self, sql: str, parameters: object = ()) -> _OrdinalCursor:
            del parameters
            if "MAX(root_fill_key_id)" in sql:
                return _OrdinalCursor(11)
            if "MAX(fact_id)" in sql:
                return _OrdinalCursor(13)
            if "MAX(fact_ordinal)" in sql:
                return _OrdinalCursor(17)
            raise AssertionError(sql)

    def applied(name: str, record: object) -> records.RepositoryOutcome[object]:
        writes.append(name)
        captured[name] = record
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    monkeypatch.setattr(
        unit_of_work._repository,
        "load_root_fill_by_external",
        lambda *args: records.RepositoryOutcome(records.RepositoryOutcomeKind.ABSENT),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "store_root_fill",
        lambda connection, record, *, capability: applied("root", record),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "store_acquisition_root_route",
        lambda connection, record, *, capability: applied("route", record),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "store_execution_fact",
        lambda connection, record, *, capability: applied("fact", record),
    )

    def found(record: object) -> records.RepositoryOutcome[object]:
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.FOUND, record)

    def resulting_root() -> records.RootFillRecord:
        root = captured["root"]
        fact = captured["fact"]
        assert type(root) is records.RootFillRecord
        assert type(fact) is records.ExecutionFactRecord
        return replace(
            root,
            current_fact_id=fact.fact_id,
            current_kind=fact.kind,
            current_authority=fact.authority,
            current_side=fact.side,
            current_quantity=fact.quantity,
            current_price=fact.price,
            economics_head_ordinal=fact.fact_ordinal,
        )

    monkeypatch.setattr(
        unit_of_work._repository,
        "load_root_fill",
        lambda *args: found(resulting_root()),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "load_acquisition_root_route",
        lambda *args: found(captured["route"]),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "load_execution_fact_by_source",
        lambda *args: found(captured["fact"]),
    )

    def fact_head(*args: object) -> records.RepositoryOutcome[object]:
        del args
        fact = captured["fact"]
        assert type(fact) is records.ExecutionFactRecord
        return found(
            records.ExecutionFactHeadRecord(
                fact.root_fill_key_id,
                fact.fact_id,
                fact.fact_ordinal,
            )
        )

    monkeypatch.setattr(
        unit_of_work._repository,
        "load_execution_fact_head",
        fact_head,
    )

    fact_record, root_record, route_record, predecessor = (
        unit_of_work._persist_venue_economics(
            Connection(),
            prepared,
            filled,
            relation,
            object(),
        )
    )

    assert writes == ["root", "route", "fact"]
    assert predecessor is None
    assert fact_record == captured["fact"]
    assert root_record == resulting_root()
    assert route_record == captured["route"]


def test_direct_terminal_venue_refresh_rebases_active_protection_once() -> None:
    _, scope, claimed, filled = (
        acquisition_fixtures._r8_current_generation_fill_transition(
            acknowledged=True,
            prefill_needs_review=False,
        )
    )
    current = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert current.protection is not None
    relation = filled.book.project_acquisition_fact(filled).fact_relation()
    assert relation is not None
    item = venue.ObserveVenueStatus(
        venue.VenueInputId("uow-o2-active-terminal"),
        relation.leg_key,
        venue.VenueAttemptState.FILLED,
        venue.VenueObservationId("uow-o2-active-terminal-observation"),
        authority_fixtures.Quantity(current.execution.position.raw_quantity),
        venue.ClosureId("uow-o2-active-terminal-closure"),
        venue.EvidenceReference("uow-o2-active-terminal-evidence"),
    )
    venue_transition, observation = _apply_direct_venue_observation(
        current.venue,
        current.execution,
        item,
    )
    refresh = authority._m2_refresh_acquisition_context_from_venue_transition(
        current.authority,
        current.execution,
        scope,
        venue_transition,
        observation,
    )
    rebased, protection_transition = acquisition._m2_rebase_acquisition_venue(
        current.state,
        refresh,
        current.protection,
    )

    assert venue_transition.disposition is venue.VenueRecoveryDisposition.APPLIED
    assert venue_transition.quantity_delta == 0
    assert (
        refresh.disposition is authority.AcquisitionContextRefreshDisposition.REFRESHED
    )
    assert protection_transition is not None
    assert protection_transition.disposition is protection.ProtectionDisposition.APPLIED
    assert rebased.protection is protection_transition.state
    assert rebased.venue is venue_transition.book
    assert rebased.execution.position == current.execution.position
    assert rebased.execution.seen_facts.commitment == (
        current.execution.seen_facts.commitment
    )
    assert rebased.state.registry is current.state.registry
    assert rebased.state.lineage is current.state.lineage
    assert (
        rebased.state._controller.controller_head
        == current.state._controller.controller_head
    )
    assert rebased.state.commitment != current.state.commitment


def test_direct_late_owner_reconciliation_rebases_active_protection_once() -> None:
    _, scope, claimed, filled = (
        acquisition_fixtures._r8_current_generation_fill_transition(
            acknowledged=True,
            prefill_needs_review=False,
        )
    )
    current = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert current.protection is not None
    relation = filled.book.project_acquisition_fact(filled).fact_relation()
    assert relation is not None

    terminal, terminal_observation = _apply_direct_venue_observation(
        current.venue,
        current.execution,
        venue.ObserveVenueStatus(
            venue.VenueInputId("uow-o2-late-owner-terminal"),
            relation.leg_key,
            venue.VenueAttemptState.FILLED,
            venue.VenueObservationId("uow-o2-late-owner-terminal-observation"),
            authority_fixtures.Quantity(current.execution.position.raw_quantity),
            venue.ClosureId("uow-o2-late-owner-terminal-closure"),
            venue.EvidenceReference("uow-o2-late-owner-terminal-evidence"),
        ),
    )
    terminal_refresh = authority._m2_refresh_acquisition_context_from_venue_transition(
        current.authority,
        current.execution,
        scope,
        terminal,
        terminal_observation,
    )
    terminal_current, terminal_protection = acquisition._m2_rebase_acquisition_venue(
        current.state,
        terminal_refresh,
        current.protection,
    )
    assert terminal_protection is not None
    assert terminal_current.protection is terminal_protection.state

    closed = recovery_fixtures.apply_venue_recovery_input(
        terminal_current.venue,
        terminal_current.execution,
        venue.CloseAcceptanceSet(
            venue.VenueInputId("uow-o2-close-before-late-owner"),
            claimed.fresh_claim.effect_id,
            venue.AcceptanceProof(
                kind=venue.AcceptanceProofKind.COVERED_RECONCILIATION,
                effect_scope=terminal_current.venue.effect(
                    claimed.fresh_claim.effect_id
                ).scope,
                claim_occurrence_id=claimed.fresh_claim.claim_occurrence_id,
                evidence_reference=venue.EvidenceReference(
                    "uow-o2-close-before-late-owner-proof"
                ),
                evidence_digest=b"\xa7" * 32,
            ),
        ),
    )
    assert closed.disposition is venue.VenueRecoveryDisposition.APPLIED
    assert (
        closed.book.effect(claimed.fresh_claim.effect_id).acceptance_set_state
        is venue.AcceptanceSetState.CLOSED
    )
    closed_protection_transition = protection.reduce_position_protection(
        terminal_current.protection,
        protection.project_protection_venue(
            closed,
            terminal_current.state._mandate.protection_mandate,
        ),
    )
    assert (
        closed_protection_transition.disposition
        is protection.ProtectionDisposition.APPLIED
    )
    closed_protection = closed_protection_transition.state
    closed_authority = authority._state_with(
        terminal_current.authority,
        venue=closed.book,
    )
    closed_venue_context = closed.book.project_acquisition_context(
        closed.execution,
        scope,
    )
    closed_authority_context = authority.project_acquisition_authority_context(
        closed_authority,
        closed.execution,
        closed_venue_context,
    )
    closed_protection_context = protection.project_acquisition_protection_context(
        closed_protection,
        closed.book,
        closed.execution,
        closed_venue_context,
    )
    assert closed_protection_context is not None
    prior_controller = terminal_current.state._controller
    closed_controller = acquisition._new_symbol_acquisition_controller(
        application_generation_id=terminal_current.state.application_generation_id,
        position_scope=terminal_current.state.position_scope,
        controller_head=prior_controller.controller_head,
        successor_ordinal=prior_controller.successor_ordinal,
        live_generation_id=prior_controller.live_generation_id,
        recovery_class=prior_controller.recovery_class,
        scope_execution_commitment=(closed_venue_context.scope_execution_commitment),
        venue_commitment=closed_venue_context.commitment,
        authority_context_commitment=(closed_authority_context.authority_commitment),
        protection_commitment=(closed_protection_context.scope_protection_commitment),
        binding_commitment=prior_controller._binding_commitment,
        compatibility_commitment=prior_controller._compatibility_commitment,
    )
    closed_state = acquisition._new_acquisition_controller_state(
        controller=closed_controller,
        mandate=terminal_current.state._mandate,
        registry=terminal_current.state.registry,
        lineage=terminal_current.state.lineage,
    )

    late_leg = identity.VenueLegKey(
        broker=scope.broker,
        environment=scope.environment,
        account=scope.account,
        order_id=identity.OrderId("uow-o2-late-owner-order"),
    )
    late, late_observation = _apply_direct_venue_observation(
        closed.book,
        closed.execution,
        venue.DiscoverVenueLeg(
            venue.VenueInputId("uow-o2-late-owner-discovery"),
            claimed.fresh_claim.effect_id,
            late_leg,
            venue.VenueObservationId("uow-o2-late-owner-observation"),
        ),
    )
    assert late.disposition is venue.VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert late.quantity_delta == 0
    assert late.execution == closed.execution
    assert late.book.owner(late_leg) is not None

    refresh = authority._m2_refresh_acquisition_context_from_venue_transition(
        closed_authority,
        closed.execution,
        scope,
        late,
        late_observation,
    )
    rebased, late_protection = acquisition._m2_rebase_acquisition_venue(
        closed_state,
        refresh,
        closed_protection,
    )

    assert (
        refresh.disposition is authority.AcquisitionContextRefreshDisposition.REFRESHED
    )
    assert late_protection is not None
    assert late_protection.disposition is protection.ProtectionDisposition.APPLIED
    assert rebased.protection is late_protection.state
    assert rebased.venue is late.book
    assert rebased.execution == closed.execution
    assert rebased.state.registry is closed_state.registry
    assert rebased.state.lineage is closed_state.lineage
    assert (
        rebased.state._controller.controller_head == closed_controller.controller_head
    )


def _authority_effect_prepared(
    state: authority.ExecutionAuthorityState,
    execution: object,
    *,
    effects: tuple[records.VenueEffectRecord, ...] = (),
    acceptance_sets: tuple[records.AcceptanceSetRecord, ...] = (),
    claims: tuple[records.DispatchClaimRecord, ...] = (),
) -> unit_of_work._PreparedOperation:
    base = _prepared_primary_claim()
    scope_id = 7
    execution_profile_id = "11" * 32
    generation_id = identity.AcquisitionGenerationId("ab" * 32)
    symbol_id = execution.position.scope.symbol_id
    selection = SimpleNamespace(
        scopes=(
            records.ScopeRecord(
                scope_id,
                state.venue.scope.generation,
                execution_profile_id,
                symbol_id,
            ),
        ),
        controllers=(
            records.SymbolControllerRecord(
                scope_id,
                state.venue.scope.generation,
                execution_profile_id,
                generation_id,
                execution.position.raw_quantity,
                "CONSISTENT",
                7,
                3,
                "ee" * 32,
            ),
        ),
        protection_authorities=(
            records.ProtectionAuthorityRecord(
                scope_id,
                "EMERGENCY",
                None,
                generation_id,
                "11" * 32,
                None,
                state.session_id,
                None,
                7,
                "aa" * 32,
                3,
            ),
        ),
        live_generations=(
            records.AcquisitionGenerationRecord(
                generation_id,
                scope_id,
                "LIVE",
                1,
                None,
                "11" * 32,
                "ee" * 32,
            ),
        ),
        effects=effects,
        acceptance_sets=acceptance_sets,
        claims=claims,
    )
    context = unit_of_work.UnitOfWorkContext(
        base.context.expected_checkpoint,
        state.venue,
        state,
        ((scope_id, None, execution, None),),
    )
    return replace(
        base,
        context=context,
        application_generation_id=state.venue.scope.generation,
        execution_profile_id=execution_profile_id,
        scope_id=scope_id,
        selection_proof=SimpleNamespace(_selection=selection),
    )


def test_authority_effect_and_claim_rows_follow_dependency_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, execution, command, grant_id = _emergency_create_inputs()
    available = authority._m2_authority_grant_observation_from_direct_evidence(
        state,
        grant_id,
        retained_claim=None,
        retained_input_bytes=None,
        retained_outcome_bytes=None,
    )
    created = authority._m2_apply_execution_authority_input(
        state,
        execution,
        command,
        manual_observation=None,
        grant_observation=available,
    )
    create_prepared = _authority_effect_prepared(state, execution)
    create_events: list[tuple[str, object]] = []

    def store_effect(
        connection: object,
        record: object,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[object]:
        del connection, capability
        create_events.append(("effect", record))
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    def store_acceptance(
        connection: object,
        record: object,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[object]:
        del connection, capability
        create_events.append(("acceptance", record))
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    monkeypatch.setattr(unit_of_work, "_next_venue_effect_id", lambda _: 11)
    monkeypatch.setattr(
        unit_of_work,
        "_next_venue_effect_created_ordinal",
        lambda _: 13,
    )
    monkeypatch.setattr(unit_of_work, "_next_acceptance_set_id", lambda _: 17)
    monkeypatch.setattr(unit_of_work._repository, "store_venue_effect", store_effect)
    monkeypatch.setattr(
        unit_of_work._repository,
        "store_acceptance_set",
        store_acceptance,
    )

    created_effects, created_claims = unit_of_work._persist_authority_venue_transitions(
        object(),
        create_prepared,
        created.venue_transitions,
        object(),
    )
    assert [name for name, _ in create_events] == ["effect", "acceptance"]
    assert len(created_effects) == 1
    assert created_claims == ()
    effect_record = created_effects[0]
    acceptance_record = create_events[1][1]
    assert type(acceptance_record) is records.AcceptanceSetRecord

    claim_command = authority.ClaimEffect(
        identity.AuthorityInputId("uow-grant-claim-input"),
        command.request.effect_id,
        identity.ClaimOccurrenceId("uow-grant-claim"),
    )
    claim_available = authority._m2_authority_grant_observation_from_direct_evidence(
        created.state,
        grant_id,
        retained_claim=None,
        retained_input_bytes=None,
        retained_outcome_bytes=None,
    )
    claimed = authority._m2_apply_execution_authority_input(
        created.state,
        execution,
        claim_command,
        manual_observation=None,
        grant_observation=claim_available,
    )
    claim_prepared = _authority_effect_prepared(
        created.state,
        execution,
        effects=(effect_record,),
        acceptance_sets=(acceptance_record,),
    )
    claim_events: list[tuple[str, object]] = []

    def store_claim(
        connection: object,
        record: object,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[object]:
        del connection, capability
        claim_events.append(("claim", record))
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    monkeypatch.setattr(unit_of_work, "_next_dispatch_claim_id", lambda _: 19)
    monkeypatch.setattr(unit_of_work, "_next_dispatch_claim_ordinal", lambda _: 23)
    monkeypatch.setattr(unit_of_work._repository, "store_dispatch_claim", store_claim)

    claim_effects, persisted_claims = unit_of_work._persist_authority_venue_transitions(
        object(),
        claim_prepared,
        claimed.venue_transitions,
        object(),
    )
    assert claim_effects == ()
    assert [name for name, _ in claim_events] == ["claim"]
    assert len(persisted_claims) == 1
    assert (
        persisted_claims[0].effect.lifecycle_state
        == venue.BrokerEffectState.DISPATCH_CLAIMED.value
    )
    assert persisted_claims[0].claim.claim_occurrence_id == (
        claim_command.claim_occurrence_id
    )


class _TransactionConnection:
    def __init__(
        self,
        *,
        commit_error: Exception | None = None,
        rollback_error: Exception | None = None,
    ) -> None:
        self.in_transaction = False
        self.commit_error = commit_error
        self.rollback_error = rollback_error
        self.events: list[str] = []

    def execute(self, sql: str, parameters: object = ()) -> object:
        del parameters
        self.events.append(sql)
        if sql == "BEGIN IMMEDIATE":
            assert not self.in_transaction
            self.in_transaction = True
        elif sql == "COMMIT":
            assert self.in_transaction
            if self.commit_error is not None:
                raise self.commit_error
            self.in_transaction = False
        elif sql == "ROLLBACK":
            assert self.in_transaction
            if self.rollback_error is not None:
                raise self.rollback_error
            self.in_transaction = False
        else:
            raise AssertionError(f"unexpected transaction SQL: {sql}")
        return object()

    def close(self) -> None:
        self.events.append("CLOSE")


def _uow_context() -> unit_of_work.UnitOfWorkContext:
    proof, book, state, owners = checkpoint_fixtures._dormant_projection_inputs()
    expected = records.KernelCheckpointRecord(
        proof.request.application_generation_id,
        0,
        "0" * 64,
        1,
    )
    return unit_of_work.UnitOfWorkContext(
        expected,
        book,
        state,
        tuple(
            (
                owner.scope_id,
                owner.acquisition,
                owner.execution,
                owner.protection,
            )
            for owner in owners
        ),
    )


def _patch_prepared_path(
    monkeypatch: pytest.MonkeyPatch,
    body: object,
) -> None:
    monkeypatch.setattr(unit_of_work, "_canonicalize_operation", lambda value: value)
    monkeypatch.setattr(
        unit_of_work,
        "_prepare_transaction",
        lambda connection, operation, context: _prepared_primary_claim(),
    )
    monkeypatch.setattr(unit_of_work, "_execute_prepared", body)


@contextmanager
def _test_runtime_write_capability(
    connection: object,
) -> Iterator[unit_of_work._repository._RuntimeWriteCapability]:
    setattr(connection, "in_transaction", True)
    capability = unit_of_work._repository._activate_runtime_write_lease(connection)
    try:
        yield capability
    finally:
        if unit_of_work._repository._runtime_write_lease_is_active(
            connection,
            capability,
        ):
            unit_of_work._repository._retire_runtime_write_lease(
                connection,
                capability,
            )
        setattr(connection, "in_transaction", False)


def _refused_result() -> unit_of_work.UnitOfWorkResult:
    return unit_of_work.UnitOfWorkResult(
        unit_of_work.UnitOfWorkDisposition.REFUSED,
        None,
        None,
        None,
        None,
    )


def _committed_result(
    context: unit_of_work.UnitOfWorkContext,
) -> unit_of_work.UnitOfWorkResult:
    return unit_of_work.UnitOfWorkResult(
        unit_of_work.UnitOfWorkDisposition.COMMITTED,
        "AUTHORITY",
        "APPLIED",
        context,
        None,
    )


def test_unit_of_work_exports_are_exact_and_invalid_input_never_begins() -> None:
    assert set(unit_of_work.__all__) == {
        "PostCommitEffectEligibility",
        "UnitOfWorkContext",
        "UnitOfWorkDisposition",
        "UnitOfWorkResult",
        "execute_unit_of_work",
    }
    connection = _TransactionConnection()
    result = unit_of_work.execute_unit_of_work(connection, object(), _uow_context())
    assert result.disposition is unit_of_work.UnitOfWorkDisposition.REFUSED
    assert connection.events == []


def _authentic_retained_successor_fixture() -> tuple[
    unit_of_work.UnitOfWorkContext,
    records.RuntimeCheckpointSelectionProof,
    checkpoint_codec.RuntimeCheckpointEnvelope,
    checkpoint_codec.RuntimeCheckpointEnvelope,
    checkpoint_codec.RuntimeCheckpointEnvelope,
]:
    source_proof, book, authority_state, owners = (
        checkpoint_fixtures._dormant_projection_inputs()
    )
    predecessor_projection = checkpoint_codec._project_runtime_checkpoint(
        source_proof,
        book,
        authority_state,
        owners,
    )
    retained = checkpoint_codec._decode_runtime_checkpoint(
        checkpoint_codec.encode_runtime_checkpoint(predecessor_projection),
        bytes.fromhex("12" * 32),
    )
    head = records.KernelCheckpointRecord(
        retained.application_generation_id,
        retained.currentness_head_ordinal,
        retained.payload_sha256,
        retained.checkpoint_version_ordinal,
    )
    successor_proof = records._issue_runtime_checkpoint_selection_proof(
        records.RuntimeCheckpointSelectionRequest(
            retained.application_generation_id,
            retained.execution_profile_id,
            retained.market_source_profile_id,
            head,
        ),
        source_proof.application_generation,
        source_proof.execution_profile,
        source_proof.market_source_profile,
        head,
        head.currentness_head_ordinal,
        head.checkpoint_version_ordinal + 1,
        source_proof._selection,
    )
    successor_projection = checkpoint_codec._project_runtime_checkpoint(
        successor_proof,
        book,
        authority_state,
        owners,
    )
    context = unit_of_work.UnitOfWorkContext(
        head,
        book,
        authority_state,
        tuple(
            (
                owner.scope_id,
                owner.acquisition,
                owner.execution,
                owner.protection,
            )
            for owner in owners
        ),
    )
    return (
        context,
        successor_proof,
        predecessor_projection,
        retained,
        successor_projection,
    )


def test_retained_checkpoint_accepts_exact_owners_projected_for_successor() -> None:
    context, _, _, retained, successor_projection = (
        _authentic_retained_successor_fixture()
    )

    assert retained.checkpoint_version_ordinal + 1 == (
        successor_projection.checkpoint_version_ordinal
    )
    assert retained.canonical_payload_bytes != (
        successor_projection.canonical_payload_bytes
    )
    assert unit_of_work._m2_checkpoint_semantics_match(
        retained,
        successor_projection,
    )

    unit_of_work._require_retained_checkpoint_payload(
        context,
        successor_projection,
        records.RepositoryOutcome(records.RepositoryOutcomeKind.FOUND, retained),
    )


def test_retained_checkpoint_rejects_wrong_head_provenance_or_owners(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, _, predecessor_projection, retained, successor_projection = (
        _authentic_retained_successor_fixture()
    )
    head = context.expected_checkpoint
    active_proof, active_book, active_authority, active_owners = (
        hydration_fixtures._active_claimed_projection_inputs()
    )
    mismatched_owner_proof = records._issue_runtime_checkpoint_selection_proof(
        records.RuntimeCheckpointSelectionRequest(
            head.application_generation_id,
            active_proof.request.execution_profile_id,
            active_proof.request.market_source_profile_id,
            head,
        ),
        active_proof.application_generation,
        active_proof.execution_profile,
        active_proof.market_source_profile,
        head,
        head.currentness_head_ordinal,
        head.checkpoint_version_ordinal + 1,
        active_proof._selection,
    )
    mismatched_owner_projection = checkpoint_codec._project_runtime_checkpoint(
        mismatched_owner_proof,
        active_book,
        active_authority,  # type: ignore[arg-type]
        active_owners,
    )
    assert mismatched_owner_projection.checkpoint_version_ordinal == (
        retained.checkpoint_version_ordinal + 1
    )
    assert not unit_of_work._m2_checkpoint_semantics_match(
        retained,
        mismatched_owner_projection,
    )
    owner_comparisons: list[
        tuple[
            checkpoint_codec.RuntimeCheckpointEnvelope,
            checkpoint_codec.RuntimeCheckpointEnvelope,
        ]
    ] = []
    compare_owner_semantics = unit_of_work._m2_checkpoint_semantics_match

    def traced_owner_comparison(
        left: checkpoint_codec.RuntimeCheckpointEnvelope,
        right: checkpoint_codec.RuntimeCheckpointEnvelope,
    ) -> bool:
        owner_comparisons.append((left, right))
        return compare_owner_semantics(left, right)

    monkeypatch.setattr(
        unit_of_work,
        "_m2_checkpoint_semantics_match",
        traced_owner_comparison,
    )

    mismatched_contexts = (
        replace(
            context,
            expected_checkpoint=replace(
                head,
                application_generation_id=identity.ApplicationGenerationId(
                    "different-checkpoint-app"
                ),
            ),
        ),
        replace(
            context,
            expected_checkpoint=replace(
                head,
                currentness_head_ordinal=head.currentness_head_ordinal + 1,
            ),
        ),
        replace(
            context,
            expected_checkpoint=replace(
                head,
                checkpoint_version_ordinal=head.checkpoint_version_ordinal + 1,
            ),
        ),
        replace(
            context,
            expected_checkpoint=replace(head, checkpoint_sha256="f" * 64),
        ),
    )
    for mismatched_context in mismatched_contexts:
        with pytest.raises(
            unit_of_work._TechnicalRefusal,
            match="retained checkpoint payload",
        ):
            unit_of_work._require_retained_checkpoint_payload(
                mismatched_context,
                successor_projection,
                records.RepositoryOutcome(
                    records.RepositoryOutcomeKind.FOUND,
                    retained,
                ),
            )

    rejected_pairs = (
        (
            successor_projection,
            records.RepositoryOutcome(records.RepositoryOutcomeKind.ABSENT),
        ),
        (
            successor_projection,
            records.RepositoryOutcome(
                records.RepositoryOutcomeKind.FOUND,
                predecessor_projection,
            ),
        ),
        (
            retained,
            records.RepositoryOutcome(records.RepositoryOutcomeKind.FOUND, retained),
        ),
        (
            predecessor_projection,
            records.RepositoryOutcome(records.RepositoryOutcomeKind.FOUND, retained),
        ),
        (
            mismatched_owner_projection,
            records.RepositoryOutcome(records.RepositoryOutcomeKind.FOUND, retained),
        ),
    )
    for projected, loaded in rejected_pairs:
        with pytest.raises(
            unit_of_work._TechnicalRefusal,
            match="retained checkpoint payload",
        ):
            unit_of_work._require_retained_checkpoint_payload(
                context,
                projected,
                loaded,
            )
    assert owner_comparisons == [(retained, mismatched_owner_projection)]


def test_prepare_transaction_authenticates_retained_n_against_target_n_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, successor_proof, _, retained, successor_projection = (
        _authentic_retained_successor_fixture()
    )
    operation = object()
    monkeypatch.setattr(
        unit_of_work._operations,
        "encode_m2_operation",
        lambda value: b"canonical-operation" if value is operation else b"unexpected",
    )
    monkeypatch.setattr(
        unit_of_work._operations,
        "_derive_m2_durable_input_projection",
        lambda _value: (
            operations.OperationDomain.VENUE_RECOVERY,
            successor_proof.request.application_generation_id,
            successor_proof.request.execution_profile_id,
            1,
            None,
            None,
            None,
            None,
            "ab" * 32,
        ),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "load_application_generation",
        lambda *args: records.RepositoryOutcome(
            records.RepositoryOutcomeKind.FOUND,
            successor_proof.application_generation,
        ),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "select_runtime_checkpoint",
        lambda *args: records.RepositoryOutcome(
            records.RepositoryOutcomeKind.FOUND,
            successor_proof,
        ),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "load_runtime_checkpoint",
        lambda *args: records.RepositoryOutcome(
            records.RepositoryOutcomeKind.FOUND,
            retained,
        ),
    )

    prepared = unit_of_work._prepare_transaction(object(), operation, context)

    assert prepared.selection_proof is successor_proof
    assert prepared.authenticated_current.checkpoint_version_ordinal == (
        retained.checkpoint_version_ordinal + 1
    )
    assert prepared.authenticated_current.canonical_payload_bytes == (
        successor_projection.canonical_payload_bytes
    )


def test_body_fault_retires_lease_then_rolls_back_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection()
    retained_capability: list[object] = []

    def fail_body(
        body_connection: object,
        prepared: object,
        capability: object,
    ) -> object:
        del body_connection, prepared
        retained_capability.append(capability)
        raise RuntimeError("injected body fault")

    _patch_prepared_path(monkeypatch, fail_body)
    with pytest.raises(RuntimeError, match="injected body fault"):
        unit_of_work.execute_unit_of_work(connection, object(), _uow_context())
    assert connection.events == ["BEGIN IMMEDIATE", "ROLLBACK"]
    with pytest.raises(ValueError, match="not current"):
        unit_of_work._repository._require_write_capability(
            connection,
            retained_capability[0],
        )


def test_rebound_operation_wrapper_cannot_forge_commit_after_write_fault(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _JournalTransactionConnection()
    context = _uow_context()
    operation = object.__new__(operations.BrokerExecutionOperation)
    prepared = replace(_prepared_primary_claim(), operation=operation, context=context)
    retained_capability: list[object] = []

    monkeypatch.setattr(
        unit_of_work, "_canonicalize_operation", lambda value: operation
    )
    monkeypatch.setattr(
        unit_of_work,
        "_prepare_transaction",
        lambda body_connection, canonical_operation, body_context: prepared,
    )
    monkeypatch.setattr(
        unit_of_work,
        "_claim_primary_input",
        lambda body_connection, prepared_operation, capability: (
            unit_of_work._ClaimedPrimaryInput(operation, object())
        ),
    )

    def fault_after_write(
        body_connection: object,
        prepared_operation: object,
        claimed_record: object,
        capability: object,
    ) -> object:
        del prepared_operation, claimed_record
        assert body_connection is connection
        retained_capability.append(capability)
        connection.staged.append("O1:store_execution_fact")
        raise RuntimeError("injected rebound after-write fault")

    def rebound_handler(
        body_connection: object,
        prepared_operation: object,
        claimed_record: object,
        capability: object,
    ) -> object:
        try:
            return fault_after_write(
                body_connection,
                prepared_operation,
                claimed_record,
                capability,
            )
        except Exception:
            return unit_of_work._TransactionDecision(
                True,
                _committed_result(context),
                None,
            )

    monkeypatch.setattr(
        unit_of_work,
        "_execute_broker_execution_operation",
        rebound_handler,
    )

    with pytest.raises(TypeError, match="factory-issued"):
        unit_of_work.execute_unit_of_work(connection, object(), context)

    assert connection.events == ["BEGIN IMMEDIATE", "ROLLBACK"]
    assert connection.staged == []
    assert connection.committed == []
    assert len(retained_capability) == 1
    with pytest.raises(ValueError, match="not current"):
        unit_of_work._repository._require_write_capability(
            connection,
            retained_capability[0],
        )


def test_structural_transaction_decision_forgery_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection()
    forged = object.__new__(unit_of_work._TransactionDecision)
    object.__setattr__(forged, "commit", True)
    object.__setattr__(forged, "result", _committed_result(_uow_context()))
    object.__setattr__(forged, "pending_effect", None)

    _patch_prepared_path(monkeypatch, lambda *args: forged)
    result = unit_of_work.execute_unit_of_work(
        connection,
        object(),
        _uow_context(),
    )

    assert result.disposition is unit_of_work.UnitOfWorkDisposition.REFUSED
    assert connection.events == ["BEGIN IMMEDIATE", "ROLLBACK"]


def test_transaction_decision_is_bound_to_the_issuing_write_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection()
    other_connection = _TransactionConnection()
    context = _uow_context()

    with _test_runtime_write_capability(other_connection) as other_capability:
        cross_lease_decision = unit_of_work._issue_transaction_decision(
            other_capability,
            True,
            _committed_result(context),
            None,
        )
        _patch_prepared_path(monkeypatch, lambda *args: cross_lease_decision)
        result = unit_of_work.execute_unit_of_work(connection, object(), context)

    assert result.disposition is unit_of_work.UnitOfWorkDisposition.REFUSED
    assert connection.events == ["BEGIN IMMEDIATE", "ROLLBACK"]


def _catalogued_write_fault_cases() -> tuple[
    tuple[str, str, tuple[str, ...], int], ...
]:
    cases: list[tuple[str, str, tuple[str, ...], int]] = []
    for row_id, families in unit_of_work._M2_C6_WRITE_TABLE:
        row_calls = tuple(
            call for family in families for call in family.repository_calls
        )
        row_index = 0
        for family in families:
            for ordinal, call in enumerate(family.repository_calls, start=1):
                boundary = f"F04:{row_id}:{family.name}:{ordinal}:{call}"
                cases.extend(
                    (
                        (boundary, "before", row_calls, row_index),
                        (boundary, "after", row_calls, row_index),
                    )
                )
                row_index += 1
    common_calls = tuple(
        call
        for family in unit_of_work._M2_COMMON_WRITE_TABLE
        for call in family.repository_calls
    )
    common_index = 0
    for family in unit_of_work._M2_COMMON_WRITE_TABLE:
        for ordinal, call in enumerate(family.repository_calls, start=1):
            boundary = f"COMMON:{family.name}:{ordinal}:{call}"
            cases.extend(
                (
                    (boundary, "before", common_calls, common_index),
                    (boundary, "after", common_calls, common_index),
                )
            )
            common_index += 1
    return tuple(cases)


class _JournalTransactionConnection(_TransactionConnection):
    def __init__(self) -> None:
        super().__init__()
        self.staged: list[str] = []
        self.committed: list[str] = []

    def execute(self, sql: str, parameters: object = ()) -> object:
        result = super().execute(sql, parameters)
        if sql == "ROLLBACK":
            self.staged.clear()
        elif sql == "COMMIT":
            self.committed.extend(self.staged)
            self.staged.clear()
        return result


@pytest.mark.parametrize(
    ("edge", "phase", "call_path", "target_index"),
    _catalogued_write_fault_cases(),
)
def test_every_catalogued_repository_call_fault_is_old_complete(
    monkeypatch: pytest.MonkeyPatch,
    edge: str,
    phase: str,
    call_path: tuple[str, ...],
    target_index: int,
) -> None:
    connection = _JournalTransactionConnection()
    retained_capability: list[object] = []
    attempted: list[str] = []

    for method_name in frozenset(unit_of_work._M2_REPOSITORY_WRITE_CALLS):

        def repository_probe(
            *args: object,
            _method_name: str = method_name,
            **kwargs: object,
        ) -> records.RepositoryOutcome[object]:
            del args, kwargs
            attempted.append(_method_name)
            current_index = len(attempted) - 1
            if current_index == target_index and phase == "before":
                raise RuntimeError(f"injected write boundary fault: {edge}:{phase}")
            connection.staged.append(f"{current_index}:{_method_name}")
            if current_index == target_index:
                raise RuntimeError(f"injected write boundary fault: {edge}:{phase}")
            return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

        monkeypatch.setattr(
            unit_of_work._repository,
            method_name,
            repository_probe,
        )

    def fail_at_boundary(
        body_connection: object,
        prepared: object,
        capability: object,
    ) -> object:
        del prepared
        assert body_connection is connection
        retained_capability.append(capability)
        for method_name in call_path:
            method = getattr(unit_of_work._repository, method_name)
            method(connection, object(), capability=capability)
        pytest.fail(f"fault edge was not reached: {edge}:{phase}")

    _patch_prepared_path(monkeypatch, fail_at_boundary)
    with pytest.raises(RuntimeError, match="injected write boundary fault"):
        unit_of_work.execute_unit_of_work(connection, object(), _uow_context())

    assert connection.events == ["BEGIN IMMEDIATE", "ROLLBACK"]
    assert connection.staged == []
    assert connection.committed == []
    assert attempted == list(call_path[: target_index + 1])
    assert len(retained_capability) == 1
    with pytest.raises(ValueError, match="not current"):
        unit_of_work._repository._require_write_capability(
            connection,
            retained_capability[0],
        )


def test_noncommitting_decision_retires_lease_and_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection()

    def refuse(
        body_connection: object,
        prepared: object,
        capability: unit_of_work._repository._RuntimeWriteCapability,
    ) -> unit_of_work._TransactionDecision:
        del body_connection, prepared
        return unit_of_work._issue_transaction_decision(
            capability,
            False,
            _refused_result(),
            None,
        )

    _patch_prepared_path(monkeypatch, refuse)
    result = unit_of_work.execute_unit_of_work(connection, object(), _uow_context())
    assert result.disposition is unit_of_work.UnitOfWorkDisposition.REFUSED
    assert connection.events == ["BEGIN IMMEDIATE", "ROLLBACK"]


def test_commit_mints_effect_eligibility_only_after_normal_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection()
    context = _uow_context()

    def commit(
        body_connection: object,
        prepared: object,
        capability: unit_of_work._repository._RuntimeWriteCapability,
    ) -> unit_of_work._TransactionDecision:
        del body_connection, prepared
        assert connection.events == ["BEGIN IMMEDIATE"]
        return unit_of_work._issue_transaction_decision(
            capability,
            True,
            _committed_result(context),
            unit_of_work._PostCommitEffectCandidate(7, 11, 13, "a" * 64),
        )

    _patch_prepared_path(monkeypatch, commit)
    result = unit_of_work.execute_unit_of_work(connection, object(), context)
    assert connection.events == ["BEGIN IMMEDIATE", "COMMIT"]
    assert result.effect_eligibility == unit_of_work.PostCommitEffectEligibility(
        7,
        11,
        13,
        "a" * 64,
    )


def test_commit_ambiguity_never_rolls_back_or_mints_eligibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection(commit_error=RuntimeError("ambiguous commit"))
    context = _uow_context()

    def commit(
        body_connection: object,
        prepared: object,
        capability: unit_of_work._repository._RuntimeWriteCapability,
    ) -> unit_of_work._TransactionDecision:
        del body_connection, prepared
        return unit_of_work._issue_transaction_decision(
            capability,
            True,
            _committed_result(context),
            unit_of_work._PostCommitEffectCandidate(7, 11, 13, "a" * 64),
        )

    _patch_prepared_path(monkeypatch, commit)
    result = unit_of_work.execute_unit_of_work(connection, object(), context)
    assert result.disposition is unit_of_work.UnitOfWorkDisposition.RECONCILIATION_ONLY
    assert result.effect_eligibility is None
    assert connection.events == ["BEGIN IMMEDIATE", "COMMIT", "CLOSE"]


def _cold_cutover_fixture() -> tuple[
    unit_of_work.UnitOfWorkContext,
    records.RuntimeCheckpointSelectionProof,
    checkpoint_codec.RuntimeCheckpointEnvelope,
]:
    proof, book, authority_state, owners = (
        checkpoint_fixtures._dormant_projection_inputs()
    )
    envelope = checkpoint_codec._project_runtime_checkpoint(
        proof,
        book,
        authority_state,
        owners,
    )
    head = records.KernelCheckpointRecord(
        envelope.application_generation_id,
        envelope.currentness_head_ordinal,
        envelope.payload_sha256,
        envelope.checkpoint_version_ordinal,
    )
    context = unit_of_work.UnitOfWorkContext(
        head,
        book,
        authority_state,
        tuple(
            (
                owner.scope_id,
                owner.acquisition,
                owner.execution,
                owner.protection,
            )
            for owner in owners
        ),
    )
    return context, proof, envelope


def test_cold_cutover_exact_replay_rolls_back_without_write_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection()
    context, proof, envelope = _cold_cutover_fixture()
    monkeypatch.setattr(
        unit_of_work,
        "_m2_load_compact_context",
        lambda *args: (context, proof, envelope),
    )

    result = unit_of_work._m2_cold_compact_cutover(
        connection,
        proof.request.application_generation_id,
        proof.request.execution_profile_id,
        proof.request.market_source_profile_id,
    )

    assert result.disposition is unit_of_work.UnitOfWorkDisposition.EXACT_REPLAY
    assert result.failure is None
    assert result.successor_context == context
    assert result.selection_proof is proof
    assert connection.events == ["BEGIN IMMEDIATE", "ROLLBACK"]


def test_cold_cutover_exact_replay_does_not_retry_ambiguous_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection(
        rollback_error=RuntimeError("ambiguous cold rollback")
    )
    context, proof, envelope = _cold_cutover_fixture()
    monkeypatch.setattr(
        unit_of_work,
        "_m2_load_compact_context",
        lambda *args: (context, proof, envelope),
    )

    with pytest.raises(RuntimeError, match="ambiguous cold rollback"):
        unit_of_work._m2_cold_compact_cutover(
            connection,
            proof.request.application_generation_id,
            proof.request.execution_profile_id,
            proof.request.market_source_profile_id,
        )

    assert connection.events == ["BEGIN IMMEDIATE", "ROLLBACK"]


def _patch_changed_cold_cutover(
    monkeypatch: pytest.MonkeyPatch,
    context: unit_of_work.UnitOfWorkContext,
    proof: records.RuntimeCheckpointSelectionProof,
    envelope: checkpoint_codec.RuntimeCheckpointEnvelope,
    *,
    fail_store: bool = False,
) -> unit_of_work.UnitOfWorkContext:
    successor_head = replace(
        context.expected_checkpoint,
        checkpoint_sha256="f" * 64,
        checkpoint_version_ordinal=(
            context.expected_checkpoint.checkpoint_version_ordinal + 1
        ),
    )
    successor = replace(context, expected_checkpoint=successor_head)
    monkeypatch.setattr(
        unit_of_work,
        "_m2_load_compact_context",
        lambda *args: (context, proof, envelope),
    )
    monkeypatch.setattr(
        unit_of_work,
        "_m2_checkpoint_semantics_match",
        lambda *args: False,
    )
    monkeypatch.setattr(
        unit_of_work,
        "_m2_advance_cold_currentness",
        lambda *args: None,
    )

    def store(*args: object) -> tuple[object, object, object]:
        del args
        if fail_store:
            raise unit_of_work._TechnicalRefusal("injected cold store refusal")
        return successor, proof, envelope

    monkeypatch.setattr(unit_of_work, "_m2_store_cold_successor", store)
    monkeypatch.setattr(
        unit_of_work,
        "_m2_reread_cold_context",
        lambda *args: (successor, proof),
    )
    return successor


def test_cold_cutover_commit_returns_only_the_exact_reread_successor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection()
    context, proof, envelope = _cold_cutover_fixture()
    successor = _patch_changed_cold_cutover(
        monkeypatch,
        context,
        proof,
        envelope,
    )

    result = unit_of_work._m2_cold_compact_cutover(
        connection,
        proof.request.application_generation_id,
        proof.request.execution_profile_id,
        proof.request.market_source_profile_id,
    )

    assert result.disposition is unit_of_work.UnitOfWorkDisposition.COMMITTED
    assert result.successor_context is successor
    assert result.selection_proof is proof
    assert connection.events == ["BEGIN IMMEDIATE", "COMMIT"]


def test_cold_cutover_store_refusal_retires_lease_and_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection()
    context, proof, envelope = _cold_cutover_fixture()
    _patch_changed_cold_cutover(
        monkeypatch,
        context,
        proof,
        envelope,
        fail_store=True,
    )

    result = unit_of_work._m2_cold_compact_cutover(
        connection,
        proof.request.application_generation_id,
        proof.request.execution_profile_id,
        proof.request.market_source_profile_id,
    )

    assert result.disposition is unit_of_work.UnitOfWorkDisposition.REFUSED
    assert result.failure is unit_of_work._ColdCompactCutoverFailure.DATASTORE
    assert result.successor_context is None
    assert result.selection_proof is None
    assert connection.events == ["BEGIN IMMEDIATE", "ROLLBACK"]


def test_cold_cutover_commit_ambiguity_closes_without_rollback_or_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection(commit_error=RuntimeError("ambiguous commit"))
    context, proof, envelope = _cold_cutover_fixture()
    _patch_changed_cold_cutover(monkeypatch, context, proof, envelope)

    result = unit_of_work._m2_cold_compact_cutover(
        connection,
        proof.request.application_generation_id,
        proof.request.execution_profile_id,
        proof.request.market_source_profile_id,
    )

    assert result.disposition is unit_of_work.UnitOfWorkDisposition.RECONCILIATION_ONLY
    assert result.failure is unit_of_work._ColdCompactCutoverFailure.COMMIT_AMBIGUITY
    assert result.successor_context is None
    assert result.selection_proof is None
    assert connection.events == ["BEGIN IMMEDIATE", "COMMIT", "CLOSE"]


def test_cold_cutover_distinguishes_current_proof_from_invalidation_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, proof, envelope = _cold_cutover_fixture()

    def load_refusal(*args: object) -> tuple[object, object, object]:
        del args
        raise unit_of_work._TechnicalRefusal("injected current proof refusal")

    monkeypatch.setattr(unit_of_work, "_m2_load_compact_context", load_refusal)
    proof_result = unit_of_work._m2_cold_compact_cutover(
        _TransactionConnection(),
        proof.request.application_generation_id,
        proof.request.execution_profile_id,
        proof.request.market_source_profile_id,
    )
    assert proof_result.failure is unit_of_work._ColdCompactCutoverFailure.CURRENT_PROOF

    monkeypatch.setattr(
        unit_of_work,
        "_m2_load_compact_context",
        lambda *args: (context, proof, envelope),
    )

    def invalidation_refusal(*args: object) -> unit_of_work.UnitOfWorkContext:
        del args
        raise unit_of_work._TechnicalRefusal("injected invalidation refusal")

    monkeypatch.setattr(
        unit_of_work,
        "_m2_cold_invalidated_context",
        invalidation_refusal,
    )
    invalidation_result = unit_of_work._m2_cold_compact_cutover(
        _TransactionConnection(),
        proof.request.application_generation_id,
        proof.request.execution_profile_id,
        proof.request.market_source_profile_id,
    )
    assert (
        invalidation_result.failure
        is unit_of_work._ColdCompactCutoverFailure.INVALIDATION
    )


def test_rollback_ambiguity_propagates_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _TransactionConnection(
        rollback_error=RuntimeError("ambiguous rollback")
    )

    def refuse(
        body_connection: object,
        prepared: object,
        capability: unit_of_work._repository._RuntimeWriteCapability,
    ) -> unit_of_work._TransactionDecision:
        del body_connection, prepared
        return unit_of_work._issue_transaction_decision(
            capability,
            False,
            _refused_result(),
            None,
        )

    _patch_prepared_path(monkeypatch, refuse)
    with pytest.raises(RuntimeError, match="ambiguous rollback"):
        unit_of_work.execute_unit_of_work(connection, object(), _uow_context())
    assert connection.events == ["BEGIN IMMEDIATE", "ROLLBACK"]


class _OrdinalCursor:
    def __init__(self, ordinal: int) -> None:
        self.ordinal = ordinal

    def fetchone(self) -> tuple[int]:
        return (self.ordinal,)


class _PrimaryClaimConnection:
    def __init__(self, ordinal: int = 1) -> None:
        self.ordinal = ordinal
        self.statements: list[str] = []

    def execute(self, sql: str, parameters: object = ()) -> _OrdinalCursor:
        del parameters
        self.statements.append(sql)
        assert sql == (
            "SELECT COALESCE(MAX(created_ordinal), 0) + 1 FROM durable_input"
        )
        return _OrdinalCursor(self.ordinal)


class _CompletionConnection:
    def __init__(self, receipt_ordinal: int = 4) -> None:
        self.receipt_ordinal = receipt_ordinal
        self.statements: list[str] = []

    def execute(self, sql: str, parameters: object = ()) -> _OrdinalCursor:
        del parameters
        self.statements.append(sql)
        assert sql == (
            "SELECT COALESCE(MAX(receipt_ordinal), 0) + 1 FROM decision_receipt"
        )
        return _OrdinalCursor(self.receipt_ordinal)


def _prepared_primary_claim() -> unit_of_work._PreparedOperation:
    operation = input_fixtures._passive_venue_operation()
    payload = operations.encode_m2_operation(operation)
    (
        domain,
        application_generation_id,
        execution_profile_id,
        scope_id,
        session_id,
        acquisition_generation_id,
        market_source_profile_id,
        stream_generation_id,
        input_identity_sha256,
    ) = operations._derive_m2_durable_input_projection(operation)
    return unit_of_work._PreparedOperation(
        operation,
        _uow_context(),
        payload,
        domain,
        application_generation_id,
        execution_profile_id,
        scope_id,
        session_id,
        acquisition_generation_id,
        market_source_profile_id,
        stream_generation_id,
        input_identity_sha256,
        object(),
        object(),
    )


def _acquisition_coordinates(
    transition: acquisition.AcquisitionControllerTransition,
) -> operations.AcquisitionOperationCoordinates:
    live_generation_id = transition.state._controller.live_generation_id
    assert live_generation_id is not None
    return operations.AcquisitionOperationCoordinates(
        authority_fixtures.GENERATION,
        "ep",
        7,
        transition.state._mandate.session_id,
        live_generation_id,
    )


def _prepared_acquisition_operation(
    operation: operations.M2Operation,
    transition: acquisition.AcquisitionControllerTransition,
) -> unit_of_work._PreparedOperation:
    payload = operations.encode_m2_operation(operation)
    (
        domain,
        application_generation_id,
        execution_profile_id,
        scope_id,
        session_id,
        acquisition_generation_id,
        market_source_profile_id,
        stream_generation_id,
        input_identity_sha256,
    ) = operations._derive_m2_durable_input_projection(operation)
    context = unit_of_work.UnitOfWorkContext(
        _uow_context().expected_checkpoint,
        transition.venue,
        transition.authority,
        ((7, transition.state, transition.execution, transition.protection),),
    )
    generation_id = transition.state._controller.live_generation_id
    assert generation_id is not None
    generation = transition.state.registry.record(generation_id)
    assert generation is not None
    mandate = transition.state._mandate
    stream_id = mandate.protection_mandate.evidence_policy.stream_generation
    stream = records.MarketStreamAuthorityRecord(
        stream_id,
        7,
        transition.state.application_generation_id,
        generation_id,
        generation.binding.dual_mandate_binding_commitment.hex(),
        "mp",
        mandate.session_id,
        mandate.protection_mandate.evidence_policy.sequence_mode.value,
    )
    venue_context = transition.venue.project_acquisition_context(
        transition.execution,
        transition.state.position_scope,
    )
    fixed_cursor = (
        venue_context._source_protection_cursor_ordinal
        if transition.protection is None
        else transition.protection._cursor_ordinal
    )
    if transition.protection is None:
        protection_record = records.ProtectionAuthorityRecord(
            7,
            "NORMAL",
            None,
            None,
            None,
            None,
            None,
            None,
            10,
            "aa" * 32,
            3,
        )
    else:
        protection_record = records.ProtectionAuthorityRecord(
            7,
            (
                "HARD_BAIL"
                if transition.protection.policy is protection.ProtectionPolicy.HARD_BAIL
                else "NORMAL"
            ),
            stream_id,
            generation_id,
            generation.binding.dual_mandate_binding_commitment.hex(),
            "mp",
            mandate.session_id,
            mandate.protection_mandate.evidence_policy.sequence_mode.value,
            10,
            transition.protection.commitment.hex(),
            3,
        )
    selection = SimpleNamespace(
        scopes=(
            records.ScopeRecord(
                7,
                transition.state.application_generation_id,
                "ep",
                transition.state.position_scope.symbol_id,
            ),
        ),
        controllers=(
            records.SymbolControllerRecord(
                7,
                transition.state.application_generation_id,
                "ep",
                generation_id,
                transition.execution.position.raw_quantity,
                "CONSISTENT",
                10,
                3,
                generation.binding.emergency_recovery_compatibility_commitment.hex(),
            ),
        ),
        protection_authorities=(protection_record,),
        live_generations=(
            records.AcquisitionGenerationRecord(
                generation_id,
                7,
                "LIVE",
                generation.binding.successor_ordinal + 1,
                None,
                generation.binding.dual_mandate_binding_commitment.hex(),
                generation.binding.emergency_recovery_compatibility_commitment.hex(),
            ),
        ),
        live_generation_current=(
            records.AcquisitionGenerationCurrentRecord(
                generation_id,
                7,
                0,
                0,
                0 if transition.protection is None else 1,
            ),
        ),
        streams=(stream,),
        cursors=(
            records.MarketCursorRecord(
                stream.stream_generation_id,
                stream.scope_id,
                stream.application_generation_id,
                stream.acquisition_generation_id,
                stream.generation_mandate_commitment_sha256,
                stream.source_profile_id,
                stream.session_id,
                stream.sequence_mode,
                fixed_cursor,
                max(fixed_cursor, 10),
            ),
        ),
        effects=(),
        acceptance_sets=(),
        claims=(),
    )
    return unit_of_work._PreparedOperation(
        operation,
        context,
        payload,
        domain,
        application_generation_id,
        execution_profile_id,
        scope_id,
        session_id,
        acquisition_generation_id,
        market_source_profile_id,
        stream_generation_id,
        input_identity_sha256,
        SimpleNamespace(
            request=SimpleNamespace(market_source_profile_id="mp"),
            _selection=selection,
        ),
        object(),
    )


def test_acquisition_current_proof_rejects_dormant_count_and_class_splices() -> None:
    _, _, initialized = acquisition_fixtures._r8_initialized_controller()
    operation = operations.CreateAcquisitionEffectOperation(
        _acquisition_coordinates(initialized),
        authority.AuthorityInputId("uow-dormant-current-proof"),
        acquisition.AcquisitionEffectTerms(
            authority_fixtures.Quantity(1),
            authority_fixtures.PRICE,
            acquisition.AcquisitionOrderType.LIMIT,
            1,
        ),
    )

    prepared = _prepared_acquisition_operation(operation, initialized)
    selection = prepared.selection_proof._selection
    original_current = selection.live_generation_current
    selection.live_generation_current = (
        replace(original_current[0], active_protection_count=1),
    )
    with pytest.raises(
        unit_of_work._TechnicalRefusal,
        match="dormant protection authority",
    ):
        unit_of_work._selected_acquisition_authority(
            prepared,
            initialized.state,
            initialized.execution,
            initialized.protection,
        )

    selection.live_generation_current = original_current
    original_protection = selection.protection_authorities
    selection.protection_authorities = (
        replace(original_protection[0], authority_class="HARD_BAIL"),
    )
    with pytest.raises(
        unit_of_work._TechnicalRefusal,
        match="dormant protection authority",
    ):
        unit_of_work._selected_acquisition_authority(
            prepared,
            initialized.state,
            initialized.execution,
            initialized.protection,
        )


def test_acquisition_current_proof_rejects_active_count_class_and_cursor_splices() -> (
    None
):
    _, _, claimed, filled = acquisition_fixtures._r8_current_generation_fill_transition(
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
    operation = operations.BeginAcquisitionPreemptionOperation(
        _acquisition_coordinates(current),
        authority.AuthorityInputId("uow-active-current-proof"),
    )
    prepared = _prepared_acquisition_operation(operation, current)
    selection = prepared.selection_proof._selection
    original_current = selection.live_generation_current
    selection.live_generation_current = (
        replace(original_current[0], active_protection_count=0),
    )
    with pytest.raises(
        unit_of_work._TechnicalRefusal,
        match="active protection authority",
    ):
        unit_of_work._selected_acquisition_authority(
            prepared,
            current.state,
            current.execution,
            current.protection,
        )

    selection.live_generation_current = original_current
    original_protection = selection.protection_authorities
    wrong_class = (
        "NORMAL"
        if original_protection[0].authority_class == "HARD_BAIL"
        else "HARD_BAIL"
    )
    selection.protection_authorities = (
        replace(original_protection[0], authority_class=wrong_class),
    )
    with pytest.raises(
        unit_of_work._TechnicalRefusal,
        match="active protection authority",
    ):
        unit_of_work._selected_acquisition_authority(
            prepared,
            current.state,
            current.execution,
            current.protection,
        )

    selection.protection_authorities = original_protection
    original_cursors = selection.cursors
    assert len(original_cursors) == 1
    selection.cursors = ()
    with pytest.raises(
        unit_of_work._TechnicalRefusal,
        match="acquisition market cursor is not singular",
    ):
        unit_of_work._selected_acquisition_authority(
            prepared,
            current.state,
            current.execution,
            current.protection,
        )


def test_create_acquisition_effect_route_uses_owner_kernel_and_exact_derivative() -> (
    None
):
    _, _, initialized = acquisition_fixtures._r8_initialized_controller()
    operation = operations.CreateAcquisitionEffectOperation(
        _acquisition_coordinates(initialized),
        authority.AuthorityInputId("uow-create-acquisition-effect"),
        acquisition.AcquisitionEffectTerms(
            authority_fixtures.Quantity(1),
            authority_fixtures.PRICE,
            acquisition.AcquisitionOrderType.LIMIT,
            1,
        ),
    )

    result, derivatives = unit_of_work._acquisition_transition_for_operation(
        _prepared_acquisition_operation(operation, initialized)
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.created_effect_id is not None
    assert tuple(
        type(venue._m2_venue_transition_source_item(item)) for item in derivatives
    ) == (venue.RequestedEffect,)


def test_claim_acquisition_effect_route_uses_owner_kernel_and_exact_derivative() -> (
    None
):
    _, _, created = acquisition_fixtures._r8_created_first_effect()
    assert created.created_effect_id is not None
    operation = operations.ClaimAcquisitionEffectOperation(
        _acquisition_coordinates(created),
        authority.AuthorityInputId("uow-claim-acquisition-effect"),
        created.created_effect_id,
        authority.ClaimOccurrenceId("uow-acquisition-claim-occurrence"),
    )

    result, derivatives = unit_of_work._acquisition_transition_for_operation(
        _prepared_acquisition_operation(operation, created)
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert result.fresh_claim is not None
    assert result.fresh_claim.effect_id == operation.effect_id
    assert result.fresh_claim.claim_occurrence_id == operation.claim_occurrence_id
    assert tuple(
        type(venue._m2_venue_transition_source_item(item)) for item in derivatives
    ) == (venue.RecordDispatchClaim,)


def test_begin_acquisition_preemption_route_uses_owner_kernel_and_exact_derivative() -> (
    None
):
    _, _, current, _ = acquisition_fixtures._r11_waiting_preemption_fixture()
    operation = operations.BeginAcquisitionPreemptionOperation(
        _acquisition_coordinates(current),
        authority.AuthorityInputId("uow-begin-acquisition-preemption"),
    )

    result, derivatives = unit_of_work._acquisition_transition_for_operation(
        _prepared_acquisition_operation(operation, current)
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    assert tuple(
        type(venue._m2_venue_transition_source_item(item)) for item in derivatives
    ) == (venue.RequestedEffect,)


def test_begin_acquisition_generation_route_uses_owner_kernel_and_serial_successor() -> (
    None
):
    _, _, initialized = acquisition_fixtures._r8_initialized_controller()
    predecessor_generation_id = initialized.state._controller.live_generation_id
    assert predecessor_generation_id is not None
    successor_mandate = acquisition_fixtures._successor_mandate(
        initialized.state._mandate,
        "uow-successor",
    )
    operation = operations.BeginAcquisitionGenerationOperation(
        _acquisition_coordinates(initialized),
        authority.AuthorityInputId("uow-begin-acquisition-generation"),
        successor_mandate,
    )

    result, derivatives = unit_of_work._acquisition_transition_for_operation(
        _prepared_acquisition_operation(operation, initialized)
    )

    assert result.disposition is acquisition.AcquisitionControllerDisposition.APPLIED
    successor_generation_id = result.state._controller.live_generation_id
    assert successor_generation_id not in (None, predecessor_generation_id)
    assert (
        result.state.registry.record(predecessor_generation_id).serving_class
        is acquisition.GenerationServingClass.RETIRED_UNSERVING
    )
    assert (
        result.state.registry.record(successor_generation_id).serving_class
        is acquisition.GenerationServingClass.LIVE
    )
    assert derivatives == ()


def test_market_occurrence_route_reduces_protection_then_rebases_acquisition() -> None:
    _, scope, claimed, filled = (
        acquisition_fixtures._r8_current_generation_fill_transition(
            acknowledged=True,
            prefill_needs_review=False,
        )
    )
    current = acquisition.reduce_acquisition_controller(
        claimed.state,
        filled,
        None,
        claimed.authority,
    )
    assert current.protection is not None
    mandate = current.protection.mandate
    occurrence = protection_fixtures._occurrence(
        protection,
        "uow-market-baseline",
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
    coordinates = _acquisition_coordinates(current)
    operation = operations.MarketOccurrenceOperation(
        operations.MarketOperationCoordinates(
            coordinates.application_generation_id,
            coordinates.execution_profile_id,
            coordinates.scope_id,
            coordinates.session_id,
            coordinates.acquisition_generation_id,
            "mp",
            mandate.evidence_policy.stream_generation,
        ),
        occurrence,
    )

    protection_result, acquisition_result, derivatives = (
        unit_of_work._market_transition_for_operation(
            _prepared_acquisition_operation(operation, current)
        )
    )

    assert protection_result.disposition is protection.ProtectionDisposition.APPLIED
    assert protection_result.goal is None
    assert acquisition_result is not None
    assert (
        acquisition_result.disposition
        is acquisition.AcquisitionControllerDisposition.APPLIED
    )
    assert acquisition_result.protection is protection_result.state
    assert derivatives == ()


def test_protection_persistence_advances_cursor_controller_then_authority_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, current, _ = acquisition_fixtures._r11_waiting_preemption_fixture()
    assert current.protection is not None
    prepared = _prepared_acquisition_operation(
        operations.BeginAcquisitionPreemptionOperation(
            _acquisition_coordinates(current),
            authority.AuthorityInputId("uow-protection-write-order"),
        ),
        current,
    )
    transition, _ = unit_of_work._acquisition_transition_for_operation(prepared)
    assert transition.protection is not None
    selected = unit_of_work._selected_acquisition_authority(
        prepared,
        current.state,
        current.execution,
        current.protection,
    )
    events: list[tuple[str, object]] = []

    def advance_cursor(
        connection: object,
        expected_fixed: int,
        expected_published: int,
        record: object,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[object]:
        del connection, capability
        events.append(("cursor", (expected_fixed, expected_published, record)))
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    def advance_protection(
        connection: object,
        expected_version: int,
        record: object,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[object]:
        del connection, capability
        events.append(("protection", (expected_version, record)))
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    def advance_controller(
        connection: object,
        expected_version: int,
        record: object,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[object]:
        del connection, capability
        events.append(("controller", (expected_version, record)))
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    monkeypatch.setattr(
        unit_of_work._repository,
        "advance_market_cursor",
        advance_cursor,
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "advance_protection_authority",
        advance_protection,
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "advance_symbol_controller",
        advance_controller,
    )

    resulting = unit_of_work._advance_acquisition_currentness(
        object(),
        selected,
        current.protection,
        transition.protection,
        object(),
    )

    assert [name for name, _ in events] == ["cursor", "controller", "protection"]
    cursor = events[0][1][2]
    assert isinstance(cursor, records.MarketCursorRecord)
    assert cursor.fixed_cursor_ordinal == transition.protection._cursor_ordinal
    assert cursor.published_head_ordinal == selected.cursor.published_head_ordinal + 1
    assert resulting.protection.version_ordinal == (
        selected.protection.version_ordinal + 1
    )
    assert (
        resulting.protection.state_commitment_sha256
        == transition.protection.commitment.hex()
    )
    assert resulting.controller.currentness_head_ordinal == (
        selected.controller.currentness_head_ordinal + 1
    )


def test_preemption_persists_successor_protection_before_new_effect_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, current, _ = acquisition_fixtures._r11_waiting_preemption_fixture()
    operation = operations.BeginAcquisitionPreemptionOperation(
        _acquisition_coordinates(current),
        authority.AuthorityInputId("uow-preemption-write-order"),
    )
    prepared = _prepared_acquisition_operation(operation, current)
    transition, _ = unit_of_work._acquisition_transition_for_operation(prepared)
    assert transition.created_effect_id is not None
    events: list[str] = []
    successor_protection = replace(
        prepared.selection_proof._selection.protection_authorities[0],
        state_commitment_sha256="bb" * 32,
        version_ordinal=4,
    )

    selected = unit_of_work._selected_acquisition_authority(
        prepared,
        current.state,
        current.execution,
        current.protection,
    )
    successor_controller = replace(
        selected.controller,
        currentness_head_ordinal=selected.controller.currentness_head_ordinal + 1,
        controller_version_ordinal=selected.controller.controller_version_ordinal + 1,
    )
    successor_authority = unit_of_work._SelectedScopeAuthority(
        selected.scope,
        successor_controller,
        selected.generation,
        successor_protection,
    )

    def advance(*args: object, **kwargs: object) -> object:
        del args, kwargs
        events.append("protection")
        return successor_authority

    def persist(
        connection: object,
        routed: object,
        derivatives: object,
        capability: object,
        *,
        new_effect_authority: object = None,
    ) -> tuple[tuple[object, ...], tuple[object, ...]]:
        del connection, routed, derivatives, capability
        events.append("effect")
        assert isinstance(
            new_effect_authority,
            unit_of_work._SelectedScopeAuthority,
        )
        assert new_effect_authority is successor_authority
        return ((SimpleNamespace(effect_external=transition.created_effect_id),), ())

    completed = object()

    def complete(*args: object, **kwargs: object) -> object:
        del args
        events.append("complete")
        assert kwargs["checkpoint_changed"] is True
        return completed

    monkeypatch.setattr(unit_of_work, "_advance_acquisition_currentness", advance)
    monkeypatch.setattr(
        unit_of_work,
        "_persist_authority_venue_transitions",
        persist,
    )
    monkeypatch.setattr(unit_of_work, "_complete_claimed_input", complete)

    result = unit_of_work._execute_acquisition_operation(
        object(),
        prepared,
        object(),
        object(),
    )

    assert result is completed
    assert events == ["protection", "effect", "complete"]


def test_claim_uses_retained_effect_fence_before_advancing_currentness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, current = acquisition_fixtures._r8_created_first_effect()
    assert current.created_effect_id is not None
    operation = operations.ClaimAcquisitionEffectOperation(
        _acquisition_coordinates(current),
        authority.AuthorityInputId("uow-claim-fence-order"),
        current.created_effect_id,
        authority.ClaimOccurrenceId("uow-claim-fence-occurrence"),
    )
    prepared = _prepared_acquisition_operation(operation, current)
    transition, _ = unit_of_work._acquisition_transition_for_operation(prepared)
    assert transition.fresh_claim is not None
    events: list[str] = []
    persisted = unit_of_work._PersistedEffectClaim(
        SimpleNamespace(effect_external=transition.fresh_claim.effect_id),
        SimpleNamespace(claim_occurrence_id=transition.fresh_claim.claim_occurrence_id),
    )

    def persist(*args: object, **kwargs: object):
        del args
        events.append("claim")
        assert kwargs["new_effect_authority"] is None
        return (), (persisted,)

    def outbox(*args: object, **kwargs: object) -> object:
        del args, kwargs
        events.append("outbox")
        return object()

    def advance(*args: object, **kwargs: object) -> object:
        del args, kwargs
        events.append("currentness")
        return object()

    completed = object()

    def complete(*args: object, **kwargs: object) -> object:
        del args
        events.append("complete")
        assert kwargs["checkpoint_changed"] is True
        return completed

    monkeypatch.setattr(
        unit_of_work,
        "_persist_authority_venue_transitions",
        persist,
    )
    monkeypatch.setattr(unit_of_work, "_broker_outbox_record", outbox)
    monkeypatch.setattr(unit_of_work, "_advance_acquisition_currentness", advance)
    monkeypatch.setattr(unit_of_work, "_complete_claimed_input", complete)

    result = unit_of_work._execute_acquisition_operation(
        object(),
        prepared,
        object(),
        object(),
    )

    assert result is completed
    assert events == ["claim", "outbox", "currentness", "complete"]


def test_generation_persistence_uses_fenced_null_then_serial_successor_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, predecessor = acquisition_fixtures._r8_initialized_controller()
    successor_mandate = acquisition_fixtures._successor_mandate(
        predecessor.state._mandate,
        "uow-persisted-successor",
    )
    operation = operations.BeginAcquisitionGenerationOperation(
        _acquisition_coordinates(predecessor),
        authority.AuthorityInputId("uow-persist-generation"),
        successor_mandate,
    )
    prepared = _prepared_acquisition_operation(operation, predecessor)
    transition, _ = unit_of_work._acquisition_transition_for_operation(prepared)
    selected = unit_of_work._selected_acquisition_authority(
        prepared,
        predecessor.state,
        predecessor.execution,
        predecessor.protection,
    )
    events: list[tuple[str, object]] = []

    def applied(name: str):
        def operation_call(*args: object, **kwargs: object):
            del kwargs
            record = args[-1] if name not in {"retire"} else args[1]
            events.append((name, record))
            return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

        return operation_call

    monkeypatch.setattr(
        unit_of_work._repository,
        "advance_symbol_controller",
        applied("controller"),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "advance_protection_authority",
        applied("protection"),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "retire_acquisition_generation",
        applied("retire"),
    )
    captured_generation: list[records.AcquisitionGenerationRecord] = []

    def store_generation(*args: object, **kwargs: object):
        del kwargs
        record = args[1]
        assert isinstance(record, records.AcquisitionGenerationRecord)
        captured_generation.append(record)
        events.append(("generation", record))
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    def load_current(*args: object, **kwargs: object):
        del args, kwargs
        generation = captured_generation[0]
        events.append(("load-current", generation.acquisition_generation_id))
        return records.RepositoryOutcome(
            records.RepositoryOutcomeKind.FOUND,
            records.AcquisitionGenerationCurrentRecord(
                generation.acquisition_generation_id,
                generation.scope_id,
                0,
                0,
                0,
            ),
        )

    monkeypatch.setattr(
        unit_of_work._repository,
        "store_acquisition_generation",
        store_generation,
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "load_acquisition_generation_current",
        load_current,
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "store_market_stream_authority",
        applied("stream"),
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "store_market_cursor",
        applied("cursor"),
    )
    committed = object()

    def complete(*args: object, **kwargs: object) -> object:
        del args
        events.append(("complete", kwargs["successor_context"]))
        return committed

    monkeypatch.setattr(unit_of_work, "_complete_claimed_input", complete)

    result = unit_of_work._execute_generation_operation(
        object(),
        prepared,
        object(),
        transition,
        selected,
        object(),
    )

    assert result is committed
    assert [name for name, _ in events] == [
        "controller",
        "protection",
        "retire",
        "generation",
        "load-current",
        "stream",
        "cursor",
        "controller",
        "protection",
        "complete",
    ]
    controllers = [value for name, value in events if name == "controller"]
    assert isinstance(controllers[0], records.SymbolControllerRecord)
    assert isinstance(controllers[1], records.SymbolControllerRecord)
    assert controllers[0].live_acquisition_generation_id is None
    assert (
        controllers[1].live_acquisition_generation_id
        == captured_generation[0].acquisition_generation_id
    )
    assert captured_generation[0].successor_ordinal == (
        selected.generation.successor_ordinal + 1
    )


def test_primary_claim_builds_exact_canonical_record_at_next_ordinal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _PrimaryClaimConnection(9)
    captured: list[records.DurableInputRecord] = []

    def claim(
        claim_connection: object,
        record: records.DurableInputRecord,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[operations.InputDedupeFact]:
        del capability
        assert claim_connection is connection
        captured.append(record)
        return records.RepositoryOutcome(
            records.RepositoryOutcomeKind.APPLIED,
            operations.InputDedupeFact(
                operations.InputDedupeKind.UNSEEN,
                record.input_domain.value,
                record.input_identity_sha256,
                record.payload_sha256,
                None,
                (),
            ),
        )

    monkeypatch.setattr(unit_of_work._repository, "claim_durable_input", claim)
    result = unit_of_work._claim_primary_input(
        connection,
        _prepared_primary_claim(),
        object(),
    )

    assert type(result) is unit_of_work._ClaimedPrimaryInput
    assert result.record is captured[0]
    assert result.record.created_ordinal == 9
    assert result.record.technical_state == "CLAIMED"
    assert result.record.canonical_payload_bytes == operations.encode_m2_operation(
        result.operation
    )


@pytest.mark.parametrize(
    ("repository_kind", "dedupe_kind", "expected_disposition"),
    (
        (
            records.RepositoryOutcomeKind.FOUND,
            operations.InputDedupeKind.EXACT_REPLAY,
            unit_of_work.UnitOfWorkDisposition.EXACT_REPLAY,
        ),
        (
            records.RepositoryOutcomeKind.CONFLICT,
            operations.InputDedupeKind.IDENTITY_CONFLICT,
            unit_of_work.UnitOfWorkDisposition.CONFLICT,
        ),
    ),
)
def test_primary_replay_and_conflict_short_circuit_before_owner_reduction(
    monkeypatch: pytest.MonkeyPatch,
    repository_kind: records.RepositoryOutcomeKind,
    dedupe_kind: operations.InputDedupeKind,
    expected_disposition: unit_of_work.UnitOfWorkDisposition,
) -> None:
    prepared = _prepared_primary_claim()
    connection = _PrimaryClaimConnection()

    def claim(
        claim_connection: object,
        record: records.DurableInputRecord,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[operations.InputDedupeFact]:
        del claim_connection, capability
        return records.RepositoryOutcome(
            repository_kind,
            operations.InputDedupeFact(
                dedupe_kind,
                record.input_domain.value,
                record.input_identity_sha256,
                record.payload_sha256,
                "ab" * 32
                if dedupe_kind is operations.InputDedupeKind.EXACT_REPLAY
                else None,
                (),
            ),
        )

    monkeypatch.setattr(unit_of_work._repository, "claim_durable_input", claim)
    with _test_runtime_write_capability(connection) as capability:
        result = unit_of_work._claim_primary_input(
            connection,
            prepared,
            capability,
        )

    assert type(result) is unit_of_work._TransactionDecision
    assert result.commit is False
    assert result.result.disposition is expected_disposition
    assert result.pending_effect is None


def test_committed_no_change_decision_stores_coherent_receipt_outcome_then_finalizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepared_primary_claim()
    claimed = records.DurableInputRecord(
        prepared.application_generation_id,
        prepared.execution_profile_id,
        prepared.scope_id,
        prepared.input_domain,
        prepared.session_id,
        prepared.acquisition_generation_id,
        prepared.market_source_profile_id,
        prepared.stream_generation_id,
        prepared.input_identity_sha256,
        1,
        prepared.canonical_payload_bytes,
        unit_of_work._hashlib.sha256(prepared.canonical_payload_bytes).hexdigest(),
        "CLAIMED",
        3,
    )
    connection = _CompletionConnection()
    stored: list[object] = []

    def applied(
        target_connection: object,
        record: object,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[object]:
        del capability
        assert target_connection is connection
        stored.append(record)
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    monkeypatch.setattr(unit_of_work._repository, "store_decision_receipt", applied)
    monkeypatch.setattr(
        unit_of_work._repository,
        "store_durable_input_outcome",
        applied,
    )
    monkeypatch.setattr(unit_of_work._repository, "finalize_durable_input", applied)

    with _test_runtime_write_capability(connection) as capability:
        decision = unit_of_work._complete_claimed_input(
            connection,
            prepared,
            claimed,
            owner_domain="VENUE_RECOVERY",
            owner_disposition="REFUSED",
            successor_context=prepared.context,
            checkpoint_changed=False,
            pending_outbox=None,
            capability=capability,
        )

    assert decision.commit is True
    assert decision.result.disposition is unit_of_work.UnitOfWorkDisposition.COMMITTED
    assert decision.result.owner_domain == "VENUE_RECOVERY"
    assert decision.result.owner_disposition == "REFUSED"
    assert decision.result.successor_context is prepared.context
    assert decision.pending_effect is None
    assert tuple(type(item) for item in stored) == (
        records.DecisionReceiptRecord,
        records.DurableInputOutcomeRecord,
        records.DurableInputRecord,
    )
    receipt, outcome, finalized = stored
    assert type(receipt) is records.DecisionReceiptRecord
    assert type(outcome) is records.DurableInputOutcomeRecord
    assert type(finalized) is records.DurableInputRecord
    assert receipt.receipt_ordinal == 4
    assert receipt.checkpoint_payload_sha256 is None
    assert outcome.receipt_sha256 == receipt.receipt_sha256
    assert outcome.result_sha256 == receipt.result_sha256
    assert finalized.technical_state == "TERMINAL"


def test_claim_completion_stores_outbox_after_outcome_before_finalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepared_primary_claim()
    claimed = records.DurableInputRecord(
        prepared.application_generation_id,
        prepared.execution_profile_id,
        prepared.scope_id,
        prepared.input_domain,
        prepared.session_id,
        prepared.acquisition_generation_id,
        prepared.market_source_profile_id,
        prepared.stream_generation_id,
        prepared.input_identity_sha256,
        1,
        prepared.canonical_payload_bytes,
        unit_of_work._hashlib.sha256(prepared.canonical_payload_bytes).hexdigest(),
        "CLAIMED",
        3,
    )
    connection = _CompletionConnection()
    outbox = input_fixtures._broker_outbox_record()
    stored: list[object] = []

    def applied(
        target_connection: object,
        record: object,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[object]:
        del capability
        assert target_connection is connection
        stored.append(record)
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    monkeypatch.setattr(unit_of_work._repository, "store_decision_receipt", applied)
    monkeypatch.setattr(
        unit_of_work._repository,
        "store_durable_input_outcome",
        applied,
    )
    monkeypatch.setattr(unit_of_work._repository, "store_broker_outbox", applied)
    monkeypatch.setattr(unit_of_work._repository, "finalize_durable_input", applied)

    with _test_runtime_write_capability(connection) as capability:
        decision = unit_of_work._complete_claimed_input(
            connection,
            prepared,
            claimed,
            owner_domain="VENUE_RECOVERY",
            owner_disposition="APPLIED",
            successor_context=prepared.context,
            checkpoint_changed=False,
            pending_outbox=outbox,
            capability=capability,
        )

    assert tuple(type(item) for item in stored) == (
        records.DecisionReceiptRecord,
        records.DurableInputOutcomeRecord,
        records.BrokerOutboxRecord,
        records.DurableInputRecord,
    )
    assert decision.pending_effect == unit_of_work._PostCommitEffectCandidate(
        outbox.outbox_sequence,
        outbox.effect_id,
        outbox.claim_id,
        outbox.payload_sha256,
    )


def test_authority_engage_kill_route_uses_shared_kernel_and_common_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepared_primary_claim()
    command = authority.EngageKill(
        authority.AuthorityInputId("uow-engage-kill"),
        authority.ActorId("operator"),
        "operator kill",
        authority.EvidenceReference("evidence"),
    )
    scope_id = prepared.context.scope_owners[0][0]
    operation = operations.AuthorityOperation(
        operations.ExecutionOperationCoordinates(
            prepared.application_generation_id,
            prepared.execution_profile_id,
            scope_id,
        ),
        command,
    )
    payload = operations.encode_m2_operation(operation)
    projection = operations._derive_m2_durable_input_projection(operation)
    prepared = replace(
        prepared,
        operation=operation,
        canonical_payload_bytes=payload,
        input_domain=operations.OperationDomain.AUTHORITY,
        scope_id=scope_id,
        input_identity_sha256=projection[-1],
    )
    owner_called: list[object] = []
    completed: list[tuple[str, str, bool]] = []

    def owner(
        state: authority.ExecutionAuthorityState,
        execution: object,
        item: object,
        *,
        manual_observation: object,
        query_observation: object,
        grant_observation: object,
    ) -> authority.ExecutionAuthorityTransition:
        del execution
        assert state is prepared.context.authority
        assert item is command
        assert manual_observation is None
        assert query_observation is None
        assert grant_observation is None
        owner_called.append(item)
        return authority.ExecutionAuthorityTransition(
            state,
            authority.AuthorityDisposition.EXACT_REPLAY,
            None,
            (),
            None,
            (),
            None,
            None,
        )

    def complete(
        connection: object,
        prepared_operation: object,
        claimed_record: object,
        *,
        owner_domain: str,
        owner_disposition: str,
        successor_context: object,
        checkpoint_changed: bool,
        pending_outbox: object,
        capability: object,
    ) -> object:
        del connection, prepared_operation, claimed_record, successor_context
        del pending_outbox, capability
        completed.append((owner_domain, owner_disposition, checkpoint_changed))
        return SimpleNamespace(commit=True)

    monkeypatch.setattr(
        unit_of_work._authority,
        "_m2_apply_execution_authority_input",
        owner,
    )
    monkeypatch.setattr(unit_of_work, "_complete_claimed_input", complete)

    result = unit_of_work._execute_authority_operation(
        object(),
        prepared,
        records.DurableInputRecord(
            prepared.application_generation_id,
            prepared.execution_profile_id,
            prepared.scope_id,
            prepared.input_domain,
            None,
            None,
            None,
            None,
            prepared.input_identity_sha256,
            1,
            payload,
            unit_of_work._hashlib.sha256(payload).hexdigest(),
            "CLAIMED",
            1,
        ),
        object(),
    )

    assert result.commit is True
    assert owner_called == [command]
    assert completed == [("AUTHORITY", "EXACT_REPLAY", False)]


def test_bounded_change_detection_ignores_omitted_owner_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepared_primary_claim()
    successor_authority = deepcopy(prepared.context.authority)
    successor = unit_of_work.UnitOfWorkContext(
        prepared.context.expected_checkpoint,
        successor_authority.venue,
        successor_authority,
        prepared.context.scope_owners,
    )
    projected: list[object] = []

    class _Envelope:
        canonical_payload_bytes = b"same-bounded-payload"

    monkeypatch.setattr(
        unit_of_work._checkpoint_codec,
        "_project_runtime_checkpoint",
        lambda proof, venue, authority_state, owners: (
            projected.append((proof, venue, authority_state, owners)) or _Envelope()
        ),
    )
    prepared = replace(prepared, authenticated_current=_Envelope())

    assert unit_of_work._bounded_context_changed(prepared, successor) is False
    assert len(projected) == 1


def test_successor_checkpoint_requires_a_delta_under_its_fresh_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, proof, envelope = _cold_cutover_fixture()
    fresh_proof = records._issue_runtime_checkpoint_selection_proof(
        proof.request,
        proof.application_generation,
        proof.execution_profile,
        proof.market_source_profile,
        proof.predecessor_checkpoint,
        proof.target_currentness_head_ordinal,
        proof.target_checkpoint_version_ordinal,
        proof._selection,
    )
    assert fresh_proof is not proof
    prepared = SimpleNamespace(
        application_generation_id=proof.request.application_generation_id,
        execution_profile_id=proof.request.execution_profile_id,
        selection_proof=proof,
        context=context,
        authenticated_current=envelope,
    )
    selected = records.RepositoryOutcome(
        records.RepositoryOutcomeKind.FOUND,
        fresh_proof,
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "select_runtime_checkpoint",
        lambda *args: selected,
    )

    def project_with_fresh_proof(
        selected_proof: records.RuntimeCheckpointSelectionProof,
        *args: object,
    ) -> checkpoint_codec.RuntimeCheckpointEnvelope:
        del args
        assert selected_proof is fresh_proof
        return envelope

    monkeypatch.setattr(
        unit_of_work._checkpoint_codec,
        "_project_runtime_checkpoint",
        project_with_fresh_proof,
    )

    def stale_store(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("unchanged successor reached checkpoint storage")

    monkeypatch.setattr(
        unit_of_work._repository,
        "store_runtime_checkpoint",
        stale_store,
    )

    with pytest.raises(
        unit_of_work._TechnicalRefusal,
        match="successor checkpoint omitted its bounded delta",
    ):
        unit_of_work._store_successor_checkpoint(
            object(),
            prepared,
            context,
            object(),
        )


def test_authority_query_applied_claims_semantic_key_before_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepared_primary_claim()
    scope_id, _, execution, _ = prepared.context.scope_owners[0]
    command = authority.ClaimBrokerQuery(
        identity.AuthorityInputId("uow-query-input"),
        identity.QueryClaimId("uow-query-claim"),
        execution.position.scope.symbol_id,
        authority.AuthorityQueryKind.QUERY,
    )
    operation = operations.AuthorityOperation(
        operations.ExecutionOperationCoordinates(
            prepared.application_generation_id,
            prepared.execution_profile_id,
            scope_id,
        ),
        command,
    )
    payload = operations.encode_m2_operation(operation)
    projection = operations._derive_m2_durable_input_projection(operation)
    prepared = replace(
        prepared,
        operation=operation,
        canonical_payload_bytes=payload,
        input_domain=operations.OperationDomain.AUTHORITY,
        scope_id=scope_id,
        input_identity_sha256=projection[-1],
    )
    claimed = records.DurableInputRecord(
        prepared.application_generation_id,
        prepared.execution_profile_id,
        prepared.scope_id,
        prepared.input_domain,
        None,
        None,
        None,
        None,
        prepared.input_identity_sha256,
        1,
        payload,
        unit_of_work._hashlib.sha256(payload).hexdigest(),
        "CLAIMED",
        1,
    )
    successor_state = deepcopy(prepared.context.authority)
    object.__setattr__(successor_state, "venue", prepared.context.venue)
    observation = object()
    stored: list[records.DurableInputSemanticKeyRecord] = []
    completed: list[tuple[str, str, bool]] = []

    monkeypatch.setattr(
        unit_of_work,
        "_authority_query_observation",
        lambda connection, prepared_operation, query: observation,
    )

    def owner(
        state: authority.ExecutionAuthorityState,
        execution_state: object,
        item: object,
        *,
        manual_observation: object,
        query_observation: object,
        grant_observation: object,
    ) -> authority.ExecutionAuthorityTransition:
        del state, execution_state, manual_observation
        assert item is command
        assert query_observation is observation
        assert grant_observation is None
        return authority.ExecutionAuthorityTransition(
            successor_state,
            authority.AuthorityDisposition.APPLIED,
            None,
            (),
            authority._FreshQueryClaim(
                command.query_claim_id,
                command.symbol_id,
                command.kind,
            ),
            (),
            None,
            None,
        )

    def store_key(
        connection: object,
        record: records.DurableInputSemanticKeyRecord,
        *,
        capability: object,
    ) -> records.RepositoryOutcome[object]:
        del connection, capability
        stored.append(record)
        return records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)

    def complete(
        connection: object,
        prepared_operation: object,
        claimed_record: object,
        *,
        owner_domain: str,
        owner_disposition: str,
        successor_context: object,
        checkpoint_changed: bool,
        pending_outbox: object,
        capability: object,
    ) -> object:
        del connection, prepared_operation, claimed_record, successor_context
        del pending_outbox, capability
        completed.append((owner_domain, owner_disposition, checkpoint_changed))
        return SimpleNamespace(commit=True)

    monkeypatch.setattr(
        unit_of_work._authority,
        "_m2_apply_execution_authority_input",
        owner,
    )
    monkeypatch.setattr(unit_of_work, "_bounded_context_changed", lambda *args: True)
    monkeypatch.setattr(
        unit_of_work,
        "_next_semantic_key_created_ordinal",
        lambda connection: 7,
    )
    monkeypatch.setattr(
        unit_of_work._repository,
        "store_durable_input_semantic_key",
        store_key,
    )
    monkeypatch.setattr(unit_of_work, "_complete_claimed_input", complete)

    unit_of_work._execute_authority_operation(
        object(),
        prepared,
        claimed,
        object(),
    )

    assert len(stored) == 1
    assert (
        stored[0].key_kind is operations.InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1
    )
    assert stored[0].input_identity_sha256 == claimed.input_identity_sha256
    assert stored[0].created_ordinal == 7
    assert completed == [("AUTHORITY", "APPLIED", True)]


def test_authority_manual_begin_uses_direct_proof_and_claims_semantic_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepared_primary_claim()
    scope_id, _, execution, _ = prepared.context.scope_owners[0]
    command = authority.BeginManualFlatten(
        identity.AuthorityInputId("uow-manual-input"),
        identity.ManualFlattenId("uow-manual-flatten"),
        identity.SessionId("uow-manual-session"),
        execution.position.scope.symbol_id,
        identity.ActorId("operator"),
        "bounded manual flatten",
        identity.EvidenceReference("manual-evidence"),
        None,
    )
    operation = operations.AuthorityOperation(
        operations.ExecutionOperationCoordinates(
            prepared.application_generation_id,
            prepared.execution_profile_id,
            scope_id,
        ),
        command,
    )
    payload = operations.encode_m2_operation(operation)
    projection = operations._derive_m2_durable_input_projection(operation)
    prepared = replace(
        prepared,
        operation=operation,
        canonical_payload_bytes=payload,
        input_domain=operations.OperationDomain.AUTHORITY,
        scope_id=scope_id,
        input_identity_sha256=projection[-1],
    )
    claimed = records.DurableInputRecord(
        prepared.application_generation_id,
        prepared.execution_profile_id,
        prepared.scope_id,
        prepared.input_domain,
        None,
        None,
        None,
        None,
        prepared.input_identity_sha256,
        1,
        payload,
        unit_of_work._hashlib.sha256(payload).hexdigest(),
        "CLAIMED",
        1,
    )
    observation = object()
    owner_calls: list[tuple[object, object]] = []
    semantic_calls: list[tuple[object, object]] = []

    monkeypatch.setattr(
        unit_of_work,
        "_authority_manual_observation",
        lambda connection, prepared_operation, item: observation,
    )

    def owner(
        state: authority.ExecutionAuthorityState,
        execution_state: object,
        item: object,
        *,
        manual_observation: object,
        query_observation: object,
        grant_observation: object,
    ) -> authority.ExecutionAuthorityTransition:
        del state, execution_state
        owner_calls.append((manual_observation, query_observation))
        assert grant_observation is None
        assert item is command
        return authority.ExecutionAuthorityTransition(
            prepared.context.authority,
            authority.AuthorityDisposition.APPLIED,
            None,
            (),
            None,
            (),
            None,
            None,
        )

    def store_manual_key(
        connection: object,
        prepared_operation: object,
        claimed_record: object,
        item: object,
        capability: object,
    ) -> None:
        del connection, prepared_operation, claimed_record
        semantic_calls.append((item, capability))

    monkeypatch.setattr(
        unit_of_work._authority,
        "_m2_apply_execution_authority_input",
        owner,
    )
    monkeypatch.setattr(
        unit_of_work,
        "_store_authority_manual_semantic_key",
        store_manual_key,
    )
    monkeypatch.setattr(
        unit_of_work,
        "_complete_claimed_input",
        lambda *args, **kwargs: SimpleNamespace(commit=True),
    )

    capability = object()
    decision = unit_of_work._execute_authority_operation(
        object(),
        prepared,
        claimed,
        capability,
    )

    assert decision.commit is True
    assert owner_calls == [(observation, None)]
    assert semantic_calls == [(command, capability)]


def test_authority_manual_sell_uses_an_operation_targeted_direct_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = _prepared_primary_claim()
    scope_id, _, execution, _ = prepared.context.scope_owners[0]
    command = authority.CreateBrokerEffect(
        identity.AuthorityInputId("uow-manual-sell-input"),
        identity.SessionId("uow-manual-sell-session"),
        authority_fixtures._effect_request(
            authority,
            "uow-manual-sell",
            side=authority_fixtures.ExecutionSide.SELL,
            quantity=1,
        ),
        identity.ManualFlattenId("uow-manual-sell-flatten"),
        None,
    )
    operation = operations.AuthorityOperation(
        operations.ExecutionOperationCoordinates(
            prepared.application_generation_id,
            prepared.execution_profile_id,
            scope_id,
        ),
        command,
    )
    payload = operations.encode_m2_operation(operation)
    projection = operations._derive_m2_durable_input_projection(operation)
    prepared = replace(
        prepared,
        operation=operation,
        canonical_payload_bytes=payload,
        input_domain=operations.OperationDomain.AUTHORITY,
        scope_id=scope_id,
        input_identity_sha256=projection[-1],
    )
    claimed = records.DurableInputRecord(
        prepared.application_generation_id,
        prepared.execution_profile_id,
        prepared.scope_id,
        prepared.input_domain,
        None,
        None,
        None,
        None,
        prepared.input_identity_sha256,
        1,
        payload,
        unit_of_work._hashlib.sha256(payload).hexdigest(),
        "CLAIMED",
        1,
    )
    observation = object()
    observation_calls: list[object] = []

    def observe(
        connection: object,
        prepared_operation: object,
        item: object,
    ) -> object:
        del connection
        assert prepared_operation is prepared
        observation_calls.append(item)
        return observation

    def owner(
        state: authority.ExecutionAuthorityState,
        execution_state: object,
        item: object,
        *,
        manual_observation: object,
        query_observation: object,
        grant_observation: object,
    ) -> authority.ExecutionAuthorityTransition:
        del execution_state
        assert state is prepared.context.authority
        assert item is command
        assert manual_observation is observation
        assert query_observation is None
        assert grant_observation is None
        return authority.ExecutionAuthorityTransition(
            state,
            authority.AuthorityDisposition.REFUSED,
            authority.AuthorityReason.MANUAL_FLATTEN_INVALID,
            (),
            None,
            (),
            None,
            None,
        )

    monkeypatch.setattr(unit_of_work, "_authority_manual_observation", observe)
    monkeypatch.setattr(
        unit_of_work._authority,
        "_m2_apply_execution_authority_input",
        owner,
    )
    monkeypatch.setattr(
        unit_of_work,
        "_complete_claimed_input",
        lambda *args, **kwargs: SimpleNamespace(commit=True),
    )

    decision = unit_of_work._execute_authority_operation(
        object(),
        prepared,
        claimed,
        object(),
    )

    assert decision.commit is True
    assert observation_calls == [command]
