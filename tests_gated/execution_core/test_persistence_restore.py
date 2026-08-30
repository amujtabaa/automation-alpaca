"""Fresh-file DB/WAL restore and fail-closed corruption proof for WO-0170."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from approved_schema_digest import open_approved_sqlite_connection
from app.execution_core.persistence import startup
from harness.m2 import closeout
from tests_gated.execution_core import (
    test_persistence_cold_recovery_sqlite as cold_sqlite,
)
from tests.execution_core import test_persistence_cold_recovery as cold_fakes


def _connection_state(connection: sqlite3.Connection) -> tuple[int, int, str, int, str]:
    row = connection.execute(
        "SELECT currentness_head_ordinal, checkpoint_version_ordinal, "
        "checkpoint_sha256 FROM kernel_checkpoint"
    ).fetchone()
    payload_count = connection.execute(
        "SELECT count(*) FROM runtime_checkpoint_payload"
    ).fetchone()
    lifecycle = connection.execute(
        "SELECT lifecycle_state FROM venue_effect WHERE effect_external='effect-1'"
    ).fetchone()
    assert row is not None and payload_count is not None and lifecycle is not None
    return (
        int(row[0]),
        int(row[1]),
        str(row[2]),
        int(payload_count[0]),
        str(lifecycle[0]),
    )


def test_live_wal_bundle_restores_to_independent_exact_replay(tmp_path: Path) -> None:
    source = tmp_path / "source" / "m2.db"
    destination = tmp_path / "restore" / "m2.db"
    source.parent.mkdir()
    destination.parent.mkdir()
    request, _checkpoint, session_id = cold_sqlite._install_claimed_c0(source)

    keeper = open_approved_sqlite_connection(source)
    try:
        keeper.execute("PRAGMA foreign_keys = ON")
        keeper.execute("PRAGMA recursive_triggers = ON")
        assert keeper.execute("PRAGMA journal_mode = WAL").fetchone() == ("wal",)
        keeper.execute("PRAGMA wal_autocheckpoint = 0")

        owner = cold_fakes._Owner([])
        queries = cold_sqlite._AcknowledgingQueries(session_id)
        first = startup.start_startup(
            request,
            owner_lock=owner,
            datastore=cold_sqlite._FileDatastore(source),
            effect_queries=queries,
            market_source=cold_fakes._NoMarketSource(),
        )
        assert first.disposition is startup.StartupDisposition.SERVING
        assert first.owner_lease is not None
        owner.release(first.owner_lease)
        expected_state = _connection_state(keeper)

        evidence = closeout.snapshot_sqlite_bundle(
            source,
            destination,
            require_wal=True,
        )
        closeout.verify_restore_bundle(evidence)
        assert tuple(item.suffix for item in evidence.files) == ("", "-wal")

        restored_state = cold_sqlite._checkpoint_state(destination)
        assert restored_state == expected_state
    finally:
        keeper.close()

    replay_owner = cold_fakes._Owner([])
    replay_queries = cold_sqlite._AcknowledgingQueries(session_id)
    replay = startup.start_startup(
        request,
        owner_lock=replay_owner,
        datastore=cold_sqlite._FileDatastore(destination),
        effect_queries=replay_queries,
        market_source=cold_fakes._NoMarketSource(),
    )
    assert replay.disposition is startup.StartupDisposition.SERVING
    assert replay.owner_lease is not None
    assert replay_queries.requests == []
    replay_owner.release(replay.owner_lease)


def test_restored_profile_substitution_and_catalog_corruption_are_non_serving(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.db"
    restored = tmp_path / "restored.db"
    request, _checkpoint, _session_id = cold_sqlite._install_claimed_c0(source)
    closeout.snapshot_sqlite_bundle(source, restored, require_wal=False)

    substituted = startup.StartupRequest(
        request.application_generation_id,
        "f" * 64,
        request.market_source_profile_id,
    )
    substituted_owner = cold_fakes._Owner([])
    substituted_result = startup.start_startup(
        substituted,
        owner_lock=substituted_owner,
        datastore=cold_sqlite._FileDatastore(restored),
        effect_queries=cold_fakes._NoEffectQueries(),
        market_source=cold_fakes._NoMarketSource(),
    )
    assert substituted_result.disposition is startup.StartupDisposition.NON_SERVING
    assert substituted_result.refusal_code in {
        startup.StartupRefusalCode.DATASTORE_INTEGRITY,
        startup.StartupRefusalCode.CURRENT_PROOF_FAILURE,
    }

    corruption = open_approved_sqlite_connection(restored)
    corruption.execute("CREATE TABLE wo0170_rogue_catalog(value INTEGER)")
    corruption.commit()
    corruption.close()
    corrupt_owner = cold_fakes._Owner([])
    corrupt_result = startup.start_startup(
        request,
        owner_lock=corrupt_owner,
        datastore=cold_sqlite._FileDatastore(restored),
        effect_queries=cold_fakes._NoEffectQueries(),
        market_source=cold_fakes._NoMarketSource(),
    )
    assert corrupt_result.disposition is startup.StartupDisposition.NON_SERVING
    assert corrupt_result.refusal_code is startup.StartupRefusalCode.DATASTORE_INTEGRITY
