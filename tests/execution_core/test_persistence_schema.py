"""M2-I2 schema/direct-proof RED-test candidate (HUMAN-GATE locked).

Every test in this module is gated by ``_GATE_DIGEST``. While that constant
is ``None``, each test fails loudly at its first statement without touching
SQLite at all: WO-0166 authorizes authoring these tests but explicitly
prohibits executing any schema test or installer, opening or creating any
SQLite database (file or in-memory), or executing any DDL until Ameen
approves the exact HUMAN-GATE packet through Codex. A post-approval,
separately authorized commit sets ``_GATE_DIGEST`` to the approved lowercase
SHA-256, which simultaneously unlocks the suite and pins EC-4: the installer
refuses to run against any other byte digest.

Tests construct fresh temporary file databases under pytest's ``tmp_path``
only. No configured database path exists anywhere in this module; no
in-memory database is ever used.
"""

from __future__ import annotations

import sqlite3

import pytest

import app.execution_core.persistence.schema as schema_module
from app.execution_core.persistence.schema import (
    SCHEMA_VERSION,
    SchemaDigestMismatchError,
    SchemaForeignKeysDisabledError,
    SchemaTargetNotEmptyError,
    install_schema,
    schema_ddl_digest,
)


_GATE_DIGEST: str | None = None

_FORBIDDEN_COLUMN_FRAGMENTS = (
    "identifier",
    "secret",
    "api_key",
    "token",
    "password",
)


def _require_gate_open() -> str:
    """Fail loudly before any database work while the human gate is pending."""

    digest = _GATE_DIGEST
    if digest is None:
        pytest.fail(
            "HUMAN-GATE pending: WO-0166 schema tests stay locked until "
            "Ameen approves the exact DDL candidate"
        )
    assert digest is not None
    return digest


def _connection(tmp_path: object) -> sqlite3.Connection:
    """Gate first: while locked, no connection object or file is ever made."""

    _require_gate_open()
    connection = sqlite3.connect(tmp_path / "m2-i2-gate.db")  # type: ignore[arg-type]
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _installed_connection(tmp_path: object) -> sqlite3.Connection:
    connection = _connection(tmp_path)
    install_schema(connection, approved_ddl_sha256=_require_gate_open())
    return connection


def _insert_profiles_and_generation(connection: sqlite3.Connection) -> str:
    connection.execute(
        """
        INSERT INTO execution_connection_profile (
            connection_profile_id, broker_provider, environment_class,
            account_identity, trade_command_origin, order_query_origin,
            order_event_origin, credential_handle_fingerprint,
            adapter_contract_version, capability_profile_sha256,
            deployment_identity, profile_commitment_sha256
        )
        VALUES (
            ?, 'ALPACA', 'PAPER', ?,
            'https://trade.example.com',
            'https://query.example.com',
            'https://stream.example.com',
            ?, '1.2.3', ?, ?, ?
        )
        """,
        ("cd" * 32, "aa" * 32, "bb" * 32, "cc" * 32, "dd" * 32, "ee" * 32),
    )
    connection.execute(
        """
        INSERT INTO market_data_source_profile (
            market_source_profile_id, provider, environment_or_feed,
            source_origin, entitlement_class,
            normalization_contract_version,
            data_capability_profile_sha256,
            source_profile_commitment_sha256
        )
        VALUES (?, 'ALPACA', 'iex-feed', 'https://feed.example.com',
                'IEX', '0.1.0', ?, ?)
        """,
        ("ef" * 32, "ff" * 32, "01" * 32),
    )
    connection.execute(
        """
        INSERT INTO application_generation (
            application_generation_id, selected_execution_profile_id,
            selected_market_source_profile_id, activation_ordinal
        )
        VALUES (?, ?, ?, 1)
        """,
        ("ab" * 32, "cd" * 32, "ef" * 32),
    )
    return "ab" * 32


def _seed_scope_with_live_generation(connection: sqlite3.Connection) -> int:
    generation_id = _insert_profiles_and_generation(connection)
    connection.execute(
        """
        INSERT INTO acquisition_scope (
            scope_id, application_generation_id, broker_text,
            environment_text, account_text, symbol_text
        )
        VALUES (1, ?, 'alpaca', 'paper', 'account-1', 'AAPL')
        """,
        (generation_id,),
    )
    connection.execute(
        """
        INSERT INTO acquisition_generation (
            acquisition_generation_id, scope_id, status,
            successor_ordinal, predecessor_generation_id,
            mandate_commitment_sha256, emergency_compatibility_sha256
        )
        VALUES (?, 1, 'LIVE', 1, NULL, ?, ?)
        """,
        ("12" * 32, "9a" * 32, "9b" * 32),
    )
    return 1


def _insert_root(
    connection: sqlite3.Connection,
    *,
    key_id: int = 1,
    scope_id: int = 1,
    external: str = "root-fill-A",
) -> int:
    connection.execute(
        """
        INSERT INTO root_fill (
            root_fill_key_id, scope_id, owner_generation_id,
            root_fill_external, current_quantity, price_units,
            scale_sign, scale_digits, scale_exponent,
            economics_head_ordinal
        )
        VALUES (?, ?, ?, ?, 100, 10000, 0, '01', -2, 0)
        """,
        (key_id, scope_id, "12" * 32, external),
    )
    return key_id


def _insert_fill(
    connection: sqlite3.Connection,
    *,
    fact_id: int,
    root_id: int,
    event: str,
    scope_id: int = 1,
) -> int:
    connection.execute(
        """
        INSERT INTO execution_fact (
            fact_id, scope_id, root_fill_key_id, source_event_id, kind,
            quantity, price_units, scale_sign, scale_digits,
            scale_exponent, predecessor_fact_id, fact_ordinal
        )
        VALUES (?, ?, ?, ?, 'FILL', 10, 10000, 0, '01', -2, NULL, ?)
        """,
        (fact_id, scope_id, root_id, event, fact_id),
    )
    return fact_id


def _insert_revision(
    connection: sqlite3.Connection,
    *,
    fact_id: int,
    root_id: int,
    event: str,
    predecessor_fact_id: int,
    kind: str = "TRADE_CORRECT",
    scope_id: int = 1,
) -> int:
    connection.execute(
        """
        INSERT INTO execution_fact (
            fact_id, scope_id, root_fill_key_id, source_event_id, kind,
            quantity, price_units, scale_sign, scale_digits,
            scale_exponent, predecessor_fact_id, fact_ordinal
        )
        VALUES (?, ?, ?, ?, ?, 7, 10100, 0, '01', -2, ?, ?)
        """,
        (fact_id, scope_id, root_id, event, kind, predecessor_fact_id, fact_id),
    )
    return fact_id


def _insert_bust(
    connection: sqlite3.Connection,
    *,
    fact_id: int,
    root_id: int,
    event: str,
    predecessor_fact_id: int,
    scope_id: int = 1,
) -> int:
    connection.execute(
        """
        INSERT INTO execution_fact (
            fact_id, scope_id, root_fill_key_id, source_event_id, kind,
            quantity, price_units, scale_sign, scale_digits,
            scale_exponent, predecessor_fact_id, fact_ordinal
        )
        VALUES (?, ?, ?, ?, 'TRADE_BUST', 0, NULL, NULL, NULL, NULL, ?, ?)
        """,
        (fact_id, scope_id, root_id, event, predecessor_fact_id, fact_id),
    )
    return fact_id


def _insert_open_effect(connection: sqlite3.Connection, effect_id: int) -> int:
    connection.execute(
        """
        INSERT INTO venue_effect (
            effect_id, scope_id, root_fill_key_id, order_external,
            disposition, created_ordinal
        )
        VALUES (?, 1, 1, ?, 'OPEN', ?)
        """,
        (effect_id, f"order-{effect_id}", effect_id),
    )
    return effect_id


# ---------------------------------------------------------------------------
# Installer contract.


def test_installer_installs_exact_version_into_fresh_temporary_database(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)

    version_row = connection.execute(
        "SELECT schema_version, approved_ddl_sha256 FROM schema_meta"
    ).fetchone()

    assert version_row == (SCHEMA_VERSION, schema_ddl_digest())


def test_digest_mismatch_refuses_before_any_ddl(tmp_path: object) -> None:
    connection = _connection(tmp_path)
    _require_gate_open()

    with pytest.raises(SchemaDigestMismatchError):
        install_schema(connection, approved_ddl_sha256="00" * 32)

    remaining = connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
    assert remaining is not None and remaining[0] == 0


def test_non_empty_target_is_refused(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    approved = _require_gate_open()

    with pytest.raises(SchemaTargetNotEmptyError):
        install_schema(connection, approved_ddl_sha256=approved)


def test_disabled_foreign_keys_are_refused(tmp_path: object) -> None:
    connection = _connection(tmp_path)
    connection.execute("PRAGMA foreign_keys = OFF")
    approved = _require_gate_open()

    with pytest.raises(SchemaForeignKeysDisabledError):
        install_schema(connection, approved_ddl_sha256=approved)


def test_module_import_stays_inert_without_any_database() -> None:
    """Importing the contract performs no work and exposes the frozen API."""

    assert schema_module.SCHEMA_VERSION == SCHEMA_VERSION
    assert schema_module.schema_ddl() == schema_module.SCHEMA_DDL
    digest = schema_module.schema_ddl_digest()

    assert len(digest) == 64
    assert digest == digest.lower()
    assert set(schema_module.__all__) == {
        "SCHEMA_DDL",
        "SCHEMA_VERSION",
        "SchemaDigestMismatchError",
        "SchemaForeignKeysDisabledError",
        "SchemaInstallError",
        "SchemaTargetNotEmptyError",
        "SQLiteConnectionProtocol",
        "install_schema",
        "schema_ddl",
        "schema_ddl_digest",
    }


# ---------------------------------------------------------------------------
# AC-1 negative constraint mutants.


def test_duplicate_root_external_identity_is_rejected(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    scope_id = _seed_scope_with_live_generation(connection)
    _insert_root(connection, key_id=1, scope_id=scope_id, external="root-fill-A")

    with pytest.raises(sqlite3.IntegrityError):
        _insert_root(connection, key_id=2, scope_id=scope_id, external="root-fill-A")


def test_two_live_acquisition_generations_in_one_scope_are_rejected(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    scope_id = _seed_scope_with_live_generation(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO acquisition_generation (
                acquisition_generation_id, scope_id, status,
                successor_ordinal, predecessor_generation_id,
                mandate_commitment_sha256, emergency_compatibility_sha256
            )
            VALUES (?, ?, 'LIVE', 2, ?, ?, ?)
            """,
            ("34" * 32, scope_id, "12" * 32, "8a" * 32, "8b" * 32),
        )


def test_retiring_then_reopening_is_the_only_status_path(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)

    connection.execute(
        "UPDATE acquisition_generation SET status = 'RETIRED_UNSERVING'"
        " WHERE acquisition_generation_id = ?",
        ("12" * 32,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE acquisition_generation SET status = 'LIVE'"
            " WHERE acquisition_generation_id = ?",
            ("12" * 32,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("DELETE FROM acquisition_generation")


def test_cross_scope_or_cross_profile_event_reuse_is_rejected(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    generation_id = _insert_profiles_and_generation(connection)
    connection.execute(
        """
        INSERT INTO acquisition_scope VALUES
        (1, ?, 'alpaca', 'paper', 'account-1', 'AAPL'),
        (2, ?, 'alpaca', 'paper', 'account-1', 'MSFT')
        """,
        (generation_id, generation_id),
    )
    connection.execute(
        """
        INSERT INTO root_fill (
            root_fill_key_id, scope_id, owner_generation_id,
            root_fill_external, current_quantity, price_units,
            scale_sign, scale_digits, scale_exponent, economics_head_ordinal
        )
        VALUES
        (1, 1, ?, 'r-A', 10, 10000, 0, '01', -2, 0),
        (2, 2, ?, 'r-B', 10, 10000, 0, '01', -2, 0)
        """,
        ("12" * 32, "12" * 32),
    )
    _insert_fill(connection, fact_id=1, root_id=1, event="evt-1", scope_id=1)

    with pytest.raises(sqlite3.IntegrityError):
        _insert_fill(connection, fact_id=2, root_id=2, event="evt-1", scope_id=2)


def test_revision_predecessor_must_exist_inside_same_root(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    scope_id = _seed_scope_with_live_generation(connection)
    root_a = _insert_root(connection, key_id=1, scope_id=scope_id, external="root-A")
    _insert_fill(
        connection, fact_id=1, root_id=root_a, event="evt-1", scope_id=scope_id
    )

    # Gap mutant: declared predecessor id does not exist.
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO execution_fact (
                fact_id, scope_id, root_fill_key_id, source_event_id, kind,
                quantity, price_units, scale_sign, scale_digits,
                scale_exponent, predecessor_fact_id, fact_ordinal
            )
            VALUES (9, ?, ?, 'evt-x', 'TRADE_CORRECT', 7, 10100, 0, '01',
                    -2, 999, 9)
            """,
            (scope_id, root_a),
        )

    # Cross-root mutant: predecessor exists but belongs to another root.
    root_b = _insert_root(connection, key_id=2, scope_id=scope_id, external="root-B")
    _insert_fill(
        connection, fact_id=2, root_id=root_b, event="evt-2", scope_id=scope_id
    )
    with pytest.raises(sqlite3.IntegrityError):
        _insert_bust(
            connection,
            fact_id=3,
            root_id=root_a,
            event="evt-3",
            predecessor_fact_id=2,
            scope_id=scope_id,
        )

    # Positive control: immediate same-root predecessor is accepted.
    stored = _insert_bust(
        connection,
        fact_id=4,
        root_id=root_a,
        event="evt-4",
        predecessor_fact_id=1,
        scope_id=scope_id,
    )
    assert stored == 4


def test_closure_chain_rejects_gap_branch_and_cross_owner(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    scope_id = _seed_scope_with_live_generation(connection)
    _insert_root(connection, scope_id=scope_id)
    _insert_open_effect(connection, 1)
    second_effect = _insert_open_effect(connection, 2)
    third_effect = _insert_open_effect(connection, 3)

    def _closure(
        closure_id: int,
        owner: str,
        ordinal: int,
        effect_id: int,
        predecessor: int | None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO closure_chain (
                closure_id, scope_id, owner_external, ordinal, effect_id,
                closure_kind, predecessor_closure_id
            )
            VALUES (?, ?, ?, ?, ?, 'TERMINAL_LEG', ?)
            """,
            (closure_id, scope_id, owner, ordinal, effect_id, predecessor),
        )

    _closure(1, "owner-A", 1, 1, None)

    # Gap mutant: ordinal 3 cannot follow ordinal 1 directly.
    with pytest.raises(sqlite3.IntegrityError):
        _closure(2, "owner-A", 3, 1, 1)

    _closure(3, "owner-A", 2, 1, 1)

    # Branch mutant: two successors of the same predecessor.
    with pytest.raises(sqlite3.IntegrityError):
        _closure(4, "owner-A", 3, second_effect, 1)

    # Cross-owner mutant: predecessor belongs to another owner string.
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO closure_chain (
                closure_id, scope_id, owner_external, ordinal, effect_id,
                closure_kind, predecessor_closure_id
            )
            VALUES (5, ?, 'owner-B', 1, ?, 'TERMINAL_LEG', 1)
            """,
            (scope_id, third_effect),
        )


def test_immutable_rows_refuse_update_and_delete(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection)
    _insert_fill(connection, fact_id=1, root_id=1, event="evt-1")

    for statement, parameters in (
        ("UPDATE execution_connection_profile SET broker_provider = 'WEBULL'", ()),
        ("DELETE FROM execution_connection_profile", ()),
        ("UPDATE application_generation SET activation_ordinal = 2", ()),
        ("DELETE FROM application_generation", ()),
        ("UPDATE execution_fact SET quantity = 11 WHERE fact_id = 1", ()),
        ("DELETE FROM execution_fact", ()),
        ("DELETE FROM schema_meta", ()),
        ("UPDATE root_fill SET owner_generation_id = ?", ("34" * 32,)),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(statement, parameters)


def test_monotonic_heads_refuse_regression(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    generation_id = _insert_profiles_and_generation(connection)
    connection.execute(
        """
        INSERT INTO kernel_checkpoint (
            application_generation_id, currentness_head_ordinal,
            checkpoint_sha256, checkpoint_version_ordinal
        )
        VALUES (?, 5, ?, 1)
        """,
        (generation_id, "77" * 32),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE kernel_checkpoint SET currentness_head_ordinal = 4")
    connection.execute("UPDATE kernel_checkpoint SET currentness_head_ordinal = 6")


# ---------------------------------------------------------------------------
# FR-5 canonical effect ownership.


def test_close_requires_committed_claim_and_terminal_freezes(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection)
    _insert_open_effect(connection, 1)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE venue_effect SET disposition = 'CLOSED' WHERE effect_id = 1"
        )

    connection.execute(
        """
        INSERT INTO dispatch_claim (claim_id, effect_id, claim_ordinal, resolved_kind)
        VALUES (1, 1, 1, NULL)
        """
    )
    connection.execute(
        "UPDATE venue_effect SET disposition = 'CLOSED' WHERE effect_id = 1"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE venue_effect SET disposition = 'OPEN' WHERE effect_id = 1"
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE venue_effect SET disposition = 'INVALIDATED' WHERE effect_id = 1"
        )

    connection.execute(
        "UPDATE dispatch_claim SET resolved_kind = 'DISPATCHED' WHERE claim_id = 1"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE dispatch_claim SET resolved_kind = NULL WHERE claim_id = 1"
        )
    connection.execute(
        """
        INSERT INTO dispatch_claim (claim_id, effect_id, claim_ordinal, resolved_kind)
        VALUES (2, 1, 2, NULL)
        """
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO dispatch_claim (claim_id, effect_id, claim_ordinal, resolved_kind)
            VALUES (3, 1, 3, NULL)
            """
        )


def test_acceptance_state_machine_gates_late_evidence(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection)
    _insert_open_effect(connection, 1)
    connection.execute(
        """
        INSERT INTO dispatch_claim (claim_id, effect_id, claim_ordinal, resolved_kind)
        VALUES (1, 1, 1, 'DISPATCHED')
        """
    )
    connection.execute("UPDATE venue_effect SET disposition = 'CLOSED'")
    connection.execute(
        "INSERT INTO acceptance_set (acceptance_set_id, effect_id, state)"
        " VALUES (1, 1, 'OPEN')"
    )
    connection.execute(
        "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
        " evidence_kind, evidence_digest, evidence_ordinal)"
        " VALUES (1, 1, 'OBSERVATION', ?, 1)",
        ("88" * 32,),
    )

    connection.execute("UPDATE acceptance_set SET state = 'CLOSED'")

    # EC-2: after CLOSED, only invalidation evidence may append.
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
            " evidence_kind, evidence_digest, evidence_ordinal)"
            " VALUES (2, 1, 'OBSERVATION', ?, 2)",
            ("89" * 32,),
        )
    connection.execute(
        "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
        " evidence_kind, evidence_digest, evidence_ordinal)"
        " VALUES (3, 1, 'INVALIDATION', ?, 3)",
        ("90" * 32,),
    )
    connection.execute("UPDATE acceptance_set SET state = 'INVALIDATED'")


# ---------------------------------------------------------------------------
# AC-2 direct current proof / query-plan controls.


def test_direct_head_lookups_use_indexes_not_scans(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    scope_id = _seed_scope_with_live_generation(connection)
    root_id = _insert_root(connection, scope_id=scope_id)
    _insert_fill(
        connection, fact_id=1, root_id=root_id, event="evt-0", scope_id=scope_id
    )
    predecessor = 1
    for index in range(2, 51):
        _insert_revision(
            connection,
            fact_id=index,
            root_id=root_id,
            event=f"evt-{index}",
            predecessor_fact_id=predecessor,
            scope_id=scope_id,
        )
        predecessor = index

    head_plan = connection.execute(
        """
        EXPLAIN QUERY PLAN SELECT fact_id FROM execution_fact
        WHERE root_fill_key_id = ? ORDER BY fact_ordinal DESC LIMIT 1
        """,
        (root_id,),
    ).fetchall()
    head_text = " ".join(str(row[-1]) for row in head_plan)
    assert "ix_execution_fact_root_head" in head_text
    assert "SCAN TABLE execution_fact" not in head_text

    open_plan = connection.execute(
        """
        EXPLAIN QUERY PLAN SELECT effect_id FROM venue_effect
        WHERE scope_id = ? AND disposition = 'OPEN'
        """,
        (scope_id,),
    ).fetchall()
    open_text = " ".join(str(row[-1]) for row in open_plan)
    assert "ix_venue_effect_scope_state" in open_text


def test_no_column_retains_credential_or_account_material(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)

    table_rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()

    offenders: list[str] = []
    for (table_name,) in table_rows:
        for column_row in connection.execute(f"PRAGMA table_info({table_name})"):
            column_name = str(column_row[1])
            if any(fragment in column_name for fragment in _FORBIDDEN_COLUMN_FRAGMENTS):
                offenders.append(f"{table_name}.{column_name}")

    assert offenders == []
