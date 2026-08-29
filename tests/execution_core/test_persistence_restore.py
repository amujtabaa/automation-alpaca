"""Pure safety controls for isolated SQLite database/WAL restore evidence."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.m2 import closeout


def _write_bundle(database: Path) -> None:
    database.write_bytes(b"source-database-bytes")
    database.with_name(database.name + "-wal").write_bytes(b"source-wal-bytes")


def test_restore_bundle_is_byte_exact_independent_and_source_preserving(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.db"
    destination = tmp_path / "restore" / "restored.db"
    destination.parent.mkdir()
    _write_bundle(source)
    source_before = source.read_bytes()
    wal_before = source.with_name(source.name + "-wal").read_bytes()

    evidence = closeout.snapshot_sqlite_bundle(
        source,
        destination,
        require_wal=True,
    )
    closeout.verify_restore_bundle(evidence)

    assert evidence.source_database != evidence.destination_database
    assert tuple(item.suffix for item in evidence.files) == ("", "-wal")
    assert all(item.source_sha256 == item.destination_sha256 for item in evidence.files)
    assert source.read_bytes() == source_before
    assert source.with_name(source.name + "-wal").read_bytes() == wal_before


def test_restore_bundle_refuses_collision_alias_and_missing_wal(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    source.write_bytes(b"db")
    destination = tmp_path / "destination.db"

    with pytest.raises(closeout.CloseoutCatalogError, match="independent"):
        closeout.snapshot_sqlite_bundle(source, source, require_wal=False)
    with pytest.raises(closeout.CloseoutCatalogError, match="WAL evidence"):
        closeout.snapshot_sqlite_bundle(source, destination, require_wal=True)

    destination.write_bytes(b"occupied")
    with pytest.raises(closeout.CloseoutCatalogError, match="collides"):
        closeout.snapshot_sqlite_bundle(source, destination, require_wal=False)


def test_restore_bundle_verifier_detects_destination_and_source_drift(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.db"
    destination = tmp_path / "destination.db"
    _write_bundle(source)
    evidence = closeout.snapshot_sqlite_bundle(
        source,
        destination,
        require_wal=True,
    )

    destination.write_bytes(b"mutated-destination")
    with pytest.raises(closeout.CloseoutCatalogError, match="destination"):
        closeout.verify_restore_bundle(evidence)

    destination.write_bytes(source.read_bytes())
    source.write_bytes(b"mutated-source")
    with pytest.raises(closeout.CloseoutCatalogError, match="source"):
        closeout.verify_restore_bundle(evidence)
