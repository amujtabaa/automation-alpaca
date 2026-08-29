"""Fresh-file SQLite controls for the WO-0168 atomic unit-of-work boundary.

This suite remains inert until the application-owned DDL execution flag is
explicitly unlocked from an exact human-approved schema candidate.  Every
test uses a pytest-owned file database and closes its connection.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from approved_schema_digest import (
    open_approved_sqlite_connection,
    require_approved_ddl_execution,
)
from app.execution_core.persistence.schema import install_schema
from tests_gated.execution_core import test_persistence_schema as _schema


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Install the exact approved schema in one fresh file database."""

    retained = open_approved_sqlite_connection(tmp_path / "wo-0168-uow.db")
    retained.execute("PRAGMA foreign_keys = ON")
    retained.execute("PRAGMA recursive_triggers = ON")
    install_schema(
        retained,
        approved_ddl_sha256=require_approved_ddl_execution(),
    )
    try:
        yield retained
    finally:
        retained.close()


def _insert_rootless_owner(
    connection: sqlite3.Connection,
    *,
    effect_id: int,
    owner_external: str,
    observation_external: str,
) -> None:
    connection.execute(
        """
        INSERT INTO venue_identity_owner (
            scope_id, execution_profile_id, owner_external,
            observation_external, effect_id, root_fill_key_id,
            owner_generation_id, admitted_after_effect_closed
        ) VALUES (1, ?, ?, ?, ?, NULL, ?, 0)
        """,
        (
            _schema._DEFAULT_EXECUTION_PROFILE_ID,
            owner_external,
            observation_external,
            effect_id,
            "12" * 32,
        ),
    )


def _insert_route(
    connection: sqlite3.Connection,
    *,
    root_id: int,
    effect_id: int,
    owner_external: str,
    observation_external: str,
) -> None:
    connection.execute(
        """
        INSERT INTO acquisition_root_route (
            root_fill_key_id, scope_id, application_generation_id,
            execution_profile_id, acquisition_generation_id,
            effect_id, owner_external, observation_external
        ) VALUES (?, 1, ?, ?, ?, ?, ?, ?)
        """,
        (
            root_id,
            _schema._DEFAULT_GENERATION_ID,
            _schema._DEFAULT_EXECUTION_PROFILE_ID,
            "12" * 32,
            effect_id,
            owner_external,
            observation_external,
        ),
    )


def _seed_dormant_normal_authority(
    connection: sqlite3.Connection,
) -> None:
    _schema._seed_scope_with_live_generation(connection)
    _schema._insert_controller(connection)
    _schema._insert_protection_authority(
        connection,
        state_commitment_sha256="a1" * 32,
        version_ordinal=1,
    )


def _seed_routed_dormant_position(
    connection: sqlite3.Connection,
    *,
    side: str,
    catch_up_dormant: bool = False,
) -> None:
    _seed_dormant_normal_authority(connection)
    _schema._insert_root(connection)
    _schema._insert_open_effect(
        connection,
        900,
        ensure_protection=False,
    )
    _schema._insert_venue_owner(
        connection,
        owner_external="seed-owner",
        observation_external="seed-observation",
        effect_id=900,
        root_id=1,
    )
    _insert_route(
        connection,
        root_id=1,
        effect_id=900,
        owner_external="seed-owner",
        observation_external="seed-observation",
    )
    _schema._insert_fill(
        connection,
        fact_id=1,
        root_id=1,
        event="seed-position",
        side=side,
        ensure_route=False,
    )
    if catch_up_dormant:
        connection.execute(
            "UPDATE protection_authority"
            " SET expected_controller_head_ordinal = 1,"
            " state_commitment_sha256 = ?, version_ordinal = 2"
            " WHERE scope_id = 1",
            ("a8" * 32,),
        )


def _insert_invalidation(
    connection: sqlite3.Connection,
    *,
    evidence_id: int,
    evidence_ordinal: int,
    effect_id: int,
    owner_external: str,
) -> None:
    acceptance_set_id = int(
        connection.execute(
            "SELECT acceptance_set_id FROM acceptance_set WHERE effect_id = ?",
            (effect_id,),
        ).fetchone()[0]
    )
    connection.execute(
        """
        INSERT INTO acceptance_evidence (
            evidence_id, acceptance_set_id, effect_id, evidence_kind,
            proof_kind, evidence_digest, evidence_ordinal,
            contradiction_owner_external,
            contradiction_observation_external
        ) VALUES (?, ?, ?, 'INVALIDATION', NULL, ?, ?, ?, ?)
        """,
        (
            evidence_id,
            acceptance_set_id,
            effect_id,
            f"{evidence_id:064x}",
            evidence_ordinal,
            owner_external,
            f"observation-{owner_external}",
        ),
    )


def _advance_protection_to_controller_head(
    connection: sqlite3.Connection,
    *,
    state_seed: int,
) -> None:
    head = int(
        connection.execute(
            "SELECT currentness_head_ordinal FROM symbol_controller WHERE scope_id = 1"
        ).fetchone()[0]
    )
    connection.execute(
        """
        UPDATE protection_authority
           SET expected_controller_head_ordinal = ?,
               state_commitment_sha256 = ?,
               version_ordinal = version_ordinal + 1
         WHERE scope_id = 1
        """,
        (head, f"{state_seed:064x}"),
    )


def test_rootless_owner_can_bind_one_exact_root_route(
    connection: sqlite3.Connection,
) -> None:
    _schema._seed_scope_with_live_generation(connection)
    _schema._insert_controller(connection)
    _schema._insert_root(connection)
    _schema._insert_open_effect(connection, 1)
    _insert_rootless_owner(
        connection,
        effect_id=1,
        owner_external="rootless-owner",
        observation_external="rootless-observation",
    )

    _insert_route(
        connection,
        root_id=1,
        effect_id=1,
        owner_external="rootless-owner",
        observation_external="rootless-observation",
    )

    assert connection.execute(
        "SELECT effect_id, owner_external FROM acquisition_root_route"
    ).fetchone() == (1, "rootless-owner")
    _schema._insert_root(connection, key_id=2, external="second-root")
    with pytest.raises(
        sqlite3.IntegrityError,
        match="route owner is already bound",
    ):
        _insert_route(
            connection,
            root_id=2,
            effect_id=1,
            owner_external="rootless-owner",
            observation_external="rootless-observation",
        )


def test_route_refuses_a_root_that_conflicts_with_prebound_owner(
    connection: sqlite3.Connection,
) -> None:
    _schema._seed_scope_with_live_generation(connection)
    _schema._insert_controller(connection)
    _schema._insert_root(connection, key_id=1, external="root-one")
    _schema._insert_root(connection, key_id=2, external="root-two")
    _schema._insert_open_effect(connection, 1)
    _schema._insert_venue_owner(
        connection,
        owner_external="prebound-owner",
        observation_external="prebound-observation",
        effect_id=1,
        root_id=1,
    )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="route must match the retained owner root",
    ):
        _insert_route(
            connection,
            root_id=2,
            effect_id=1,
            owner_external="prebound-owner",
            observation_external="prebound-observation",
        )


def test_flat_dormant_normal_effect_and_claim_are_admitted(
    connection: sqlite3.Connection,
) -> None:
    _seed_dormant_normal_authority(connection)

    _schema._insert_open_effect(
        connection,
        1,
        ensure_protection=False,
    )
    _schema._insert_claim(connection, claim_id=1, effect_id=1)

    assert connection.execute(
        "SELECT lifecycle_state FROM venue_effect WHERE effect_id = 1"
    ).fetchone() == ("DISPATCH_CLAIMED",)


@pytest.mark.parametrize(
    ("mutation", "aggregate_quantity"),
    [("positive", 1), ("negative", -1), ("stale-protection", 0)],
)
def test_dormant_normal_admission_is_narrow(
    connection: sqlite3.Connection,
    mutation: str,
    aggregate_quantity: int,
) -> None:
    if aggregate_quantity > 0:
        _seed_routed_dormant_position(
            connection,
            side="BUY",
            catch_up_dormant=True,
        )
    elif aggregate_quantity < 0:
        _seed_routed_dormant_position(connection, side="SELL")
    else:
        _seed_dormant_normal_authority(connection)

    with pytest.raises(
        sqlite3.IntegrityError,
        match="venue effect requires the exact current controller head",
    ):
        _schema._insert_open_effect(
            connection,
            1,
            ensure_protection=False,
            expected_protection_version_ordinal=(
                2 if mutation in {"positive", "stale-protection"} else 1
            ),
        )


def test_positive_dormant_protection_can_activate_once_but_not_transfer(
    connection: sqlite3.Connection,
) -> None:
    _seed_routed_dormant_position(connection, side="BUY")
    assert connection.execute(
        "SELECT aggregate_quantity, integrity_state, currentness_head_ordinal"
        " FROM symbol_controller WHERE scope_id = 1"
    ).fetchone() == (10, "CONSISTENT", 1)
    first_stream = "b1" * 32
    second_stream = "b2" * 32
    _schema._insert_market_stream(
        connection,
        stream_generation_id=first_stream,
        session_external="activation-session",
    )

    connection.execute(
        """
        UPDATE protection_authority
           SET active_stream_generation_id = ?,
               active_acquisition_generation_id = ?,
               active_generation_mandate_commitment_sha256 = ?,
               active_source_profile_id = ?,
               active_session_external = 'activation-session',
               active_sequence_mode = 'SEQUENCED',
               expected_controller_head_ordinal = 1,
               state_commitment_sha256 = ?, version_ordinal = 2
         WHERE scope_id = 1
        """,
        (
            first_stream,
            "12" * 32,
            "9a" * 32,
            _schema._DEFAULT_MARKET_SOURCE_PROFILE_ID,
            "a2" * 32,
        ),
    )
    _schema._insert_market_stream(
        connection,
        stream_generation_id=second_stream,
        session_external="transfer-session",
    )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="nonflat or quarantined protection authority cannot transfer",
    ):
        connection.execute(
            """
            UPDATE protection_authority
               SET active_stream_generation_id = ?,
                   active_session_external = 'transfer-session',
                   state_commitment_sha256 = ?, version_ordinal = 3
             WHERE scope_id = 1
            """,
            (second_stream, "a3" * 32),
        )
    with pytest.raises(
        sqlite3.IntegrityError,
        match="nonflat or quarantined protection authority cannot transfer",
    ):
        connection.execute(
            """
            UPDATE protection_authority
               SET active_stream_generation_id = NULL,
                   active_acquisition_generation_id = NULL,
                   active_generation_mandate_commitment_sha256 = NULL,
                   active_source_profile_id = NULL,
                   active_session_external = NULL,
                   active_sequence_mode = NULL,
                   state_commitment_sha256 = ?, version_ordinal = 3
             WHERE scope_id = 1
            """,
            ("a3" * 32,),
        )


def test_flat_consistent_protection_transfer_and_release_remain_allowed(
    connection: sqlite3.Connection,
) -> None:
    _schema._seed_scope_with_live_generation(connection)
    _schema._insert_controller(connection)
    first_stream = "b4" * 32
    second_stream = "b5" * 32
    for stream_id in (first_stream, second_stream):
        _schema._insert_market_stream(
            connection,
            stream_generation_id=stream_id,
        )
    _schema._insert_protection_authority(
        connection,
        stream_generation_id=first_stream,
        state_commitment_sha256="a5" * 32,
        version_ordinal=1,
    )

    connection.execute(
        "UPDATE protection_authority SET active_stream_generation_id = ?,"
        " state_commitment_sha256 = ?, version_ordinal = 2 WHERE scope_id = 1",
        (second_stream, "a6" * 32),
    )
    connection.execute(
        "UPDATE protection_authority SET active_stream_generation_id = NULL,"
        " active_acquisition_generation_id = NULL,"
        " active_generation_mandate_commitment_sha256 = NULL,"
        " active_source_profile_id = NULL, active_session_external = NULL,"
        " active_sequence_mode = NULL, state_commitment_sha256 = ?,"
        " version_ordinal = 3 WHERE scope_id = 1",
        ("a7" * 32,),
    )

    assert connection.execute(
        "SELECT active_stream_generation_id, version_ordinal"
        " FROM protection_authority WHERE scope_id = 1"
    ).fetchone() == (None, 3)


def test_negative_controller_cannot_activate_dormant_protection(
    connection: sqlite3.Connection,
) -> None:
    _seed_routed_dormant_position(connection, side="SELL")
    assert connection.execute(
        "SELECT aggregate_quantity, integrity_state, currentness_head_ordinal"
        " FROM symbol_controller WHERE scope_id = 1"
    ).fetchone() == (-10, "NEGATIVE_POSITION_QUARANTINED", 1)
    stream_id = "b3" * 32
    _schema._insert_market_stream(
        connection,
        stream_generation_id=stream_id,
        session_external="negative-session",
    )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="nonflat or quarantined protection authority cannot transfer",
    ):
        connection.execute(
            """
            UPDATE protection_authority
               SET active_stream_generation_id = ?,
                   active_acquisition_generation_id = ?,
                   active_generation_mandate_commitment_sha256 = ?,
                   active_source_profile_id = ?,
                   active_session_external = 'negative-session',
                   active_sequence_mode = 'SEQUENCED',
                   expected_controller_head_ordinal = 1,
                   state_commitment_sha256 = ?, version_ordinal = 2
             WHERE scope_id = 1
            """,
            (
                stream_id,
                "12" * 32,
                "9a" * 32,
                _schema._DEFAULT_MARKET_SOURCE_PROFILE_ID,
                "a4" * 32,
            ),
        )


def test_non_late_invalidation_still_advances_controller(
    connection: sqlite3.Connection,
) -> None:
    _schema._seed_scope_with_live_generation(connection)
    _schema._insert_controller(connection)
    _schema._insert_root(connection)
    _schema._insert_open_effect(connection, 1)
    _schema._insert_venue_owner(
        connection,
        owner_external="known-owner",
        effect_id=1,
    )
    _schema._insert_claim(connection, claim_id=1, effect_id=1)
    _schema._close_generation_authority(connection, generation_id="12" * 32)
    original_head, original_version = connection.execute(
        "SELECT currentness_head_ordinal, controller_version_ordinal"
        " FROM symbol_controller WHERE scope_id = 1"
    ).fetchone()

    _insert_invalidation(
        connection,
        evidence_id=100,
        evidence_ordinal=2,
        effect_id=1,
        owner_external="known-owner",
    )

    assert connection.execute(
        "SELECT integrity_state, currentness_head_ordinal,"
        " controller_version_ordinal"
        " FROM symbol_controller WHERE scope_id = 1"
    ).fetchone() == (
        "UNRESOLVED_VENUE_QUARANTINED",
        int(original_head) + 1,
        int(original_version) + 1,
    )


def test_protection_catch_up_requires_invalidation_for_the_same_late_owner(
    connection: sqlite3.Connection,
) -> None:
    _schema._seed_scope_with_live_generation(connection)
    _schema._insert_controller(connection)
    _schema._insert_root(connection)
    _schema._insert_open_effect(connection, 1)
    _schema._insert_venue_owner(
        connection,
        owner_external="known-owner",
        effect_id=1,
    )
    _schema._insert_claim(connection, claim_id=1, effect_id=1)
    _schema._close_generation_authority(connection, generation_id="12" * 32)
    _schema._insert_venue_owner(
        connection,
        owner_external="late-owner",
        effect_id=1,
    )
    _insert_invalidation(
        connection,
        evidence_id=100,
        evidence_ordinal=2,
        effect_id=1,
        owner_external="known-owner",
    )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="protection update requires matching current controller authority",
    ):
        _advance_protection_to_controller_head(connection, state_seed=203)

    _insert_invalidation(
        connection,
        evidence_id=101,
        evidence_ordinal=3,
        effect_id=1,
        owner_external="late-owner",
    )
    _advance_protection_to_controller_head(connection, state_seed=204)


@pytest.mark.parametrize("active", [False, True])
def test_each_late_owner_advances_controller_once_and_protection_catches_up(
    connection: sqlite3.Connection,
    active: bool,
) -> None:
    _schema._seed_scope_with_live_generation(connection)
    _schema._insert_controller(connection)
    _schema._insert_root(connection)
    if not active:
        _schema._insert_protection_authority(
            connection,
            state_commitment_sha256="c1" * 32,
            version_ordinal=1,
        )
    _schema._insert_open_effect(
        connection,
        1,
        ensure_protection=active,
    )
    _schema._insert_venue_owner(
        connection,
        owner_external="known-owner",
        effect_id=1,
    )
    _schema._insert_claim(connection, claim_id=1, effect_id=1)
    _schema._close_generation_authority(connection, generation_id="12" * 32)
    original_head, original_version = connection.execute(
        "SELECT currentness_head_ordinal, controller_version_ordinal"
        " FROM symbol_controller WHERE scope_id = 1"
    ).fetchone()

    _schema._insert_venue_owner(
        connection,
        owner_external="late-owner-1",
        effect_id=1,
    )
    first_head = int(original_head) + 1
    assert connection.execute(
        "SELECT currentness_head_ordinal, controller_version_ordinal"
        " FROM symbol_controller WHERE scope_id = 1"
    ).fetchone() == (first_head, int(original_version) + 1)
    with pytest.raises(
        sqlite3.IntegrityError,
        match="protection update requires matching current controller authority",
    ):
        _advance_protection_to_controller_head(connection, state_seed=200)

    _insert_invalidation(
        connection,
        evidence_id=100,
        evidence_ordinal=2,
        effect_id=1,
        owner_external="late-owner-1",
    )
    assert connection.execute(
        "SELECT integrity_state, currentness_head_ordinal,"
        " controller_version_ordinal FROM symbol_controller WHERE scope_id = 1"
    ).fetchone() == (
        "UNRESOLVED_VENUE_QUARANTINED",
        first_head,
        int(original_version) + 1,
    )
    _advance_protection_to_controller_head(connection, state_seed=201)

    _schema._insert_venue_owner(
        connection,
        owner_external="late-owner-2",
        effect_id=1,
    )
    second_head = first_head + 1
    assert connection.execute(
        "SELECT currentness_head_ordinal, controller_version_ordinal"
        " FROM symbol_controller WHERE scope_id = 1"
    ).fetchone() == (second_head, int(original_version) + 2)
    with pytest.raises(
        sqlite3.IntegrityError,
        match="protection update requires matching current controller authority",
    ):
        _advance_protection_to_controller_head(connection, state_seed=205)

    _insert_invalidation(
        connection,
        evidence_id=101,
        evidence_ordinal=3,
        effect_id=1,
        owner_external="late-owner-2",
    )
    assert connection.execute(
        "SELECT currentness_head_ordinal, controller_version_ordinal"
        " FROM symbol_controller WHERE scope_id = 1"
    ).fetchone() == (second_head, int(original_version) + 2)
    _advance_protection_to_controller_head(connection, state_seed=202)

    with pytest.raises(
        sqlite3.IntegrityError,
        match="protection update requires matching current controller authority",
    ):
        connection.execute(
            """
            UPDATE protection_authority
               SET expected_controller_head_ordinal = ?,
                   state_commitment_sha256 = ?,
                   version_ordinal = version_ordinal + 1
             WHERE scope_id = 1
            """,
            (first_head, "cb" * 32),
        )
