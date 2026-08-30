"""Fresh-file cross-layer commit-fault proof for WO-0170."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any

import pytest

from app.execution_core.persistence import startup
from tests_gated.execution_core import (
    test_persistence_cold_recovery_sqlite as cold_sqlite,
)
from tests.execution_core import test_persistence_cold_recovery as cold_fakes


class _CommitFaultConnection:
    def __init__(self, connection: sqlite3.Connection, phase: str) -> None:
        self._connection = connection
        self._phase = phase
        self._faulted = False

    @property
    def in_transaction(self) -> bool:
        return self._connection.in_transaction

    @property
    def faulted(self) -> bool:
        return self._faulted

    def execute(
        self,
        sql: str,
        parameters: tuple[object, ...] = (),
    ) -> Any:
        if sql == "COMMIT" and not self._faulted:
            self._faulted = True
            if self._phase == "before":
                raise sqlite3.OperationalError("injected pre-commit-return fault")
            self._connection.execute(sql, parameters)
            raise sqlite3.OperationalError("injected post-commit-return fault")
        return self._connection.execute(sql, parameters)

    def close(self) -> None:
        self._connection.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


class _FaultDatastore(startup._StartupDatastorePort):
    def __init__(self, path: Path, phase: str) -> None:
        self._path = path
        self._phase = phase
        self.connection: _CommitFaultConnection | None = None

    def open(self) -> _CommitFaultConnection:
        self.connection = _CommitFaultConnection(
            cold_sqlite._open_database(self._path),
            self._phase,
        )
        return self.connection


def _durable_snapshot(path: Path) -> tuple[str, ...]:
    connection = cold_sqlite._open_database(path)
    try:
        return tuple(connection.iterdump())
    finally:
        connection.close()


@pytest.mark.parametrize("phase", ("before", "after"))
def test_startup_commit_fault_reopens_old_or_new_complete(
    tmp_path: Path,
    phase: str,
) -> None:
    database = tmp_path / f"wo0170-commit-{phase}.db"
    request, _checkpoint, session_id = cold_sqlite._install_claimed_c0(database)
    old_complete = _durable_snapshot(database)

    control_database = tmp_path / f"wo0170-control-{phase}.db"
    control_request, _control_checkpoint, control_session_id = (
        cold_sqlite._install_claimed_c0(control_database)
    )
    assert control_request == request
    assert control_session_id == session_id
    assert _durable_snapshot(control_database) == old_complete
    control_owner = cold_fakes._Owner([])
    control_queries = cold_sqlite._AcknowledgingQueries(control_session_id)
    control = startup.start_startup(
        control_request,
        owner_lock=control_owner,
        datastore=cold_sqlite._FileDatastore(control_database),
        effect_queries=control_queries,
        market_source=cold_fakes._NoMarketSource(),
    )
    assert control.disposition is startup.StartupDisposition.SERVING
    assert control.owner_lease is not None
    assert len(control_queries.requests) == 1
    control_owner.release(control.owner_lease)
    new_complete = _durable_snapshot(control_database)
    assert new_complete != old_complete

    owner = cold_fakes._Owner([])
    datastore = _FaultDatastore(database, phase)

    faulted = startup.start_startup(
        request,
        owner_lock=owner,
        datastore=datastore,
        effect_queries=cold_sqlite._AcknowledgingQueries(session_id),
        market_source=cold_fakes._NoMarketSource(),
    )

    assert faulted.disposition is startup.StartupDisposition.NON_SERVING
    assert faulted.refusal_code is startup.StartupRefusalCode.UNRESOLVED_EFFECTS
    assert datastore.connection is not None
    assert datastore.connection.faulted
    observed = _durable_snapshot(database)
    if phase == "before":
        assert observed == old_complete
    else:
        assert observed == new_complete

    retry_owner = cold_fakes._Owner([])
    retry_queries = cold_sqlite._AcknowledgingQueries(session_id)
    recovered = startup.start_startup(
        request,
        owner_lock=retry_owner,
        datastore=cold_sqlite._FileDatastore(database),
        effect_queries=retry_queries,
        market_source=cold_fakes._NoMarketSource(),
    )
    assert recovered.disposition is startup.StartupDisposition.SERVING
    assert recovered.owner_lease is not None
    assert len(retry_queries.requests) == (1 if phase == "before" else 0)
    retry_owner.release(recovered.owner_lease)

    replay_owner = cold_fakes._Owner([])
    replay_queries = cold_sqlite._AcknowledgingQueries(session_id)
    replay = startup.start_startup(
        request,
        owner_lock=replay_owner,
        datastore=cold_sqlite._FileDatastore(database),
        effect_queries=replay_queries,
        market_source=cold_fakes._NoMarketSource(),
    )
    assert replay.disposition is startup.StartupDisposition.SERVING
    assert replay.owner_lease is not None
    assert replay_queries.requests == []
    replay_owner.release(replay.owner_lease)
