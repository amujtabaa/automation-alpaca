"""Explicit setup-only write capability issuance for fresh persistence fixtures.

This test-support module is deliberately the sole test-side route to a setup
capability.  Production modules never import it, and it has no connection
creation, schema installation, path discovery, or transaction behavior of its
own; named tmp_path fixtures retain those responsibilities.
"""

from __future__ import annotations

from copy import copy as _copy

from app.execution_core import authority as _authority
from app.execution_core import identity as _identity
from app.execution_core.fills import PositionScope as _PositionScope
from app.execution_core.identity import SymbolId as _SymbolId
from app.execution_core.position import ExecutionSnapshot as _ExecutionSnapshot
from app.execution_core.venue import VenueScope as _VenueScope
from app.execution_core.persistence import repository as _repository
from app.execution_core.persistence.schema import (
    SQLiteConnectionProtocol as _SQLiteConnectionProtocol,
)


def issue_setup_write_capability(
    connection: _SQLiteConnectionProtocol,
) -> _repository._SetupWriteCapability:
    """Return one connection-bound setup token to a named fresh test fixture."""

    return _repository._issue_setup_write_capability(connection)


def authority_state_with_manual_flattens(
    scope: _VenueScope,
    symbols: tuple[_SymbolId, ...],
    *,
    session: str = "manual-fixture-session",
) -> _authority.ExecutionAuthorityState:
    """Return a reducer-built authority state holding one manual flatten per symbol.

    Only the six environmental proof fields are forged, exactly as the authority
    suite's own fixtures do; every manual flatten itself is produced by the public
    reducer, so projected rows exercise real owner semantics instead of hand-minted
    records.
    """

    state = _copy(_authority.initial_execution_authority_state(scope))
    for name, value in (
        ("phase", _authority.EnginePhase.SERVING),
        ("mode", _authority.TradingMode.REDUCING),
        ("supervisor_fence", _authority.SupervisorFence.PAPER_MUTATION_ELIGIBLE),
        ("kill_engaged", False),
        ("session_id", _authority.SessionId(session)),
        ("budget", _authority.RequestBudget(remaining=8, safety_reserve=1)),
    ):
        object.__setattr__(state, name, value)

    for index, symbol in enumerate(symbols):
        execution = _ExecutionSnapshot.flat(
            _PositionScope(scope.broker, scope.environment, scope.account, symbol)
        )
        command = _authority.BeginManualFlatten(
            _authority.AuthorityInputId(f"manual-input-{index}"),
            _authority.ManualFlattenId(f"manual-flatten-{symbol.value}"),
            _authority.SessionId(session),
            symbol,
            _identity.ActorId("fixture-operator"),
            "fixture manual flatten",
            _identity.EvidenceReference(f"manual-evidence-{index}"),
            None,
        )
        transition = _authority.apply_execution_authority_input(
            state, execution, command
        )
        if transition.disposition is not _authority.AuthorityDisposition.APPLIED:
            raise AssertionError(
                "manual flatten fixture was refused: "
                f"{transition.disposition} {transition.reason}"
            )
        state = transition.state
    return state
