"""M2-I2 schema/direct-proof tests for the Codex remediation candidate.

Every test remains pinned to the exact lowercase SHA-256 in ``_GATE_DIGEST``;
the installer refuses any byte drift. Ameen's 2026-08-22 authority amendment
grants Codex standing approval to revise this bounded DDL and execute these
tests against fresh temporary file databases without another hash pause.

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


_GATE_DIGEST: str | None = (
    "2cd0fea0b60d4ecf6779e258a7b4ce6af08e1137e06edac66806076bbbeea520"
)

_OPEN_CONNECTIONS: list[sqlite3.Connection] = []


@pytest.fixture(autouse=True)
def _close_tracked_connections():
    """Close every tracked temporary database before teardown ends."""
    yield
    while _OPEN_CONNECTIONS:
        _OPEN_CONNECTIONS.pop().close()


_FORBIDDEN_COLUMN_FRAGMENTS = (
    "identifier",
    "secret",
    "api_key",
    "token",
    "password",
)

_ORIGIN_COLUMNS = (
    "trade_command_origin",
    "order_query_origin",
    "order_event_origin",
    "source_origin",
)

_DEFAULT_GENERATION_ID = "ab" * 32
_SCOPE_BROKER_TEXT = "alpaca"
_SCOPE_ENVIRONMENT_TEXT = "paper"
_SCOPE_ACCOUNT_TEXT = "account-1"
_FACT_COORDS = (
    _DEFAULT_GENERATION_ID,
    _SCOPE_BROKER_TEXT,
    _SCOPE_ENVIRONMENT_TEXT,
    _SCOPE_ACCOUNT_TEXT,
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
    _OPEN_CONNECTIONS.append(connection)
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
        VALUES (?, ?, ?, ?, 100, 10000, 0, '1', -2, 0)
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
    generation_id: str = _DEFAULT_GENERATION_ID,
) -> int:
    connection.execute(
        """
        INSERT INTO execution_fact (
            fact_id, scope_id, application_generation_id,
            broker_text, environment_text, account_text,
            root_fill_key_id, source_event_id, kind,
            quantity, price_units, scale_sign, scale_digits,
            scale_exponent, predecessor_fact_id, fact_ordinal
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'FILL', 10, 10000, 0, '1', -2,
                NULL, ?)
        """,
        (fact_id, scope_id)
        + (generation_id,)
        + _FACT_COORDS[1:]
        + (root_id, event, fact_id),
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
            fact_id, scope_id, application_generation_id,
            broker_text, environment_text, account_text,
            root_fill_key_id, source_event_id, kind,
            quantity, price_units, scale_sign, scale_digits,
            scale_exponent, predecessor_fact_id, fact_ordinal
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 7, 10100, 0, '1', -2, ?, ?)
        """,
        (fact_id, scope_id)
        + _FACT_COORDS
        + (root_id, event, kind, predecessor_fact_id, fact_id),
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
            fact_id, scope_id, application_generation_id,
            broker_text, environment_text, account_text,
            root_fill_key_id, source_event_id, kind,
            quantity, price_units, scale_sign, scale_digits,
            scale_exponent, predecessor_fact_id, fact_ordinal
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'TRADE_BUST', 0, NULL, NULL, NULL,
                NULL, ?, ?)
        """,
        (fact_id, scope_id)
        + _FACT_COORDS
        + (root_id, event, predecessor_fact_id, fact_id),
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


def _insert_venue_owner(
    connection: sqlite3.Connection,
    *,
    owner_external: str,
    effect_id: int,
    root_id: int = 1,
    scope_id: int = 1,
    owner_generation_id: str = "12" * 32,
) -> str:
    connection.execute(
        """
        INSERT INTO venue_identity_owner (
            scope_id, owner_external, effect_id,
            root_fill_key_id, owner_generation_id
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (scope_id, owner_external, effect_id, root_id, owner_generation_id),
    )
    return owner_external


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
    """The exact M1 ExecutionFactKey dedupes across scopes and symbols."""

    connection = _installed_connection(tmp_path)
    generation_a = _insert_profiles_and_generation(connection)
    connection.execute(
        "INSERT INTO application_generation VALUES (?, ?, ?, 2)",
        ("56" * 32, "cd" * 32, "ef" * 32),
    )
    connection.execute(
        """
        INSERT INTO acquisition_scope VALUES
        (1, ?, 'alpaca', 'paper', 'account-1', 'AAPL'),
        (2, ?, 'alpaca', 'paper', 'account-1', 'MSFT')
        """,
        (generation_a, "56" * 32),
    )
    connection.execute(
        """
        INSERT INTO acquisition_generation VALUES
        (?, 1, 'LIVE', 1, NULL, ?, ?),
        (?, 2, 'LIVE', 1, NULL, ?, ?)
        """,
        ("12" * 32, "9a" * 32, "9b" * 32, "34" * 32, "8a" * 32, "8b" * 32),
    )
    connection.execute(
        """
        INSERT INTO root_fill (
            root_fill_key_id, scope_id, owner_generation_id,
            root_fill_external, current_quantity, price_units,
            scale_sign, scale_digits, scale_exponent, economics_head_ordinal
        )
        VALUES
        (1, 1, ?, 'r-A', 10, 10000, 0, '1', -2, 0),
        (2, 2, ?, 'r-B', 10, 10000, 0, '1', -2, 0)
        """,
        ("12" * 32, "34" * 32),
    )

    stored = _insert_fill(connection, fact_id=1, root_id=1, event="evt-1", scope_id=1)
    assert stored == 1

    # Mutant: the identical ExecutionFactKey under the second scope. Only the
    # four-column M1-key uniqueness can refuse this insert.
    with pytest.raises(sqlite3.IntegrityError):
        _insert_fill(
            connection,
            fact_id=2,
            root_id=2,
            event="evt-1",
            scope_id=2,
            generation_id="56" * 32,
        )

    # Positive control: a distinct event on the second scope is accepted.
    assert (
        _insert_fill(
            connection,
            fact_id=3,
            root_id=2,
            event="evt-2",
            scope_id=2,
            generation_id="56" * 32,
        )
        == 3
    )


def test_fact_coordinates_must_equal_their_scope_coordinates(
    tmp_path: object,
) -> None:
    """A fact row cannot silently carry coordinates foreign to its scope."""

    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)

    with pytest.raises(sqlite3.IntegrityError, match="scope coordinates"):
        connection.execute(
            """
            INSERT INTO execution_fact (
                fact_id, scope_id, application_generation_id,
                broker_text, environment_text, account_text,
                root_fill_key_id, source_event_id, kind,
                quantity, price_units, scale_sign, scale_digits,
                scale_exponent, predecessor_fact_id, fact_ordinal
            )
            VALUES (?, 1, ?, ?, 'paper', 'account-1', 1, 'evt-x',
                    'FILL', 10, 10000, 0, '1', -2, NULL, 1)
            """,
            (1, "ab" * 32, "other-broker"),
        )


def test_revision_predecessor_must_exist_inside_same_root(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    scope_id = _seed_scope_with_live_generation(connection)
    root_a = _insert_root(connection, key_id=1, scope_id=scope_id, external="root-A")
    _insert_fill(
        connection, fact_id=1, root_id=root_a, event="evt-1", scope_id=scope_id
    )

    # Missing-parent mutant: the root exists and every coordinate matches, so
    # only the composite lineage foreign key can reject predecessor id 999.
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        connection.execute(
            """
            INSERT INTO execution_fact (
                fact_id, scope_id, application_generation_id,
                broker_text, environment_text, account_text,
                root_fill_key_id, source_event_id, kind,
                quantity, price_units, scale_sign, scale_digits,
                scale_exponent, predecessor_fact_id, fact_ordinal
            )
            VALUES (9, ?, ?, ?, ?, ?, ?, 'evt-x', 'TRADE_CORRECT',
                    7, 10100, 0, '1', -2, 999, 9)
            """,
            (scope_id, "ab" * 32, "alpaca", "paper", "account-1", root_a),
        )

    # Cross-root mutant: predecessor exists but belongs to another root.
    root_b = _insert_root(connection, key_id=2, scope_id=scope_id, external="root-B")
    _insert_fill(
        connection, fact_id=2, root_id=root_b, event="evt-2", scope_id=scope_id
    )
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
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

    # Existing-parent branch mutant: predecessor 1 exists under this root but
    # is no longer its current head after fact 4. All coordinates and ordinals
    # are otherwise valid, so the current-predecessor rule must reject it.
    with pytest.raises(sqlite3.IntegrityError, match="current root head"):
        _insert_revision(
            connection,
            fact_id=5,
            root_id=root_a,
            event="evt-5",
            predecessor_fact_id=1,
            scope_id=scope_id,
        )

    # Out-of-order mutant: predecessor 4 is the current head, but ordinal 3
    # would move the root's fact order backwards. The ordinal is globally free.
    with pytest.raises(sqlite3.IntegrityError, match="strictly advance"):
        connection.execute(
            """
            INSERT INTO execution_fact (
                fact_id, scope_id, application_generation_id,
                broker_text, environment_text, account_text,
                root_fill_key_id, source_event_id, kind,
                quantity, price_units, scale_sign, scale_digits,
                scale_exponent, predecessor_fact_id, fact_ordinal
            )
            VALUES (6, ?, ?, ?, ?, ?, ?, 'evt-6', 'TRADE_CORRECT',
                    7, 10100, 0, '1', -2, 4, 3)
            """,
            (scope_id,) + _FACT_COORDS + (root_a,),
        )

    # A same-row predecessor must not satisfy SQLite's self-referential FK.
    with pytest.raises(sqlite3.IntegrityError, match="predecessor_fact_id"):
        connection.execute(
            """
            INSERT INTO execution_fact (
                fact_id, scope_id, application_generation_id,
                broker_text, environment_text, account_text,
                root_fill_key_id, source_event_id, kind,
                quantity, price_units, scale_sign, scale_digits,
                scale_exponent, predecessor_fact_id, fact_ordinal
            )
            VALUES (8, ?, ?, ?, ?, ?, ?, 'evt-8', 'TRADE_CORRECT',
                    7, 10100, 0, '1', -2, 8, 8)
            """,
            (scope_id,) + _FACT_COORDS + (root_a,),
        )

    # A root has exactly one canonical FILL fact.
    with pytest.raises(sqlite3.IntegrityError, match="root_fill_key_id"):
        _insert_fill(
            connection,
            fact_id=7,
            root_id=root_a,
            event="evt-7",
            scope_id=scope_id,
        )


def test_closure_chain_rejects_gap_branch_and_cross_owner(
    tmp_path: object,
) -> None:
    """Gap, branch, and cross-owner mutants fail on isolated fresh chains."""

    def _fresh(name: str) -> tuple[sqlite3.Connection, int]:
        connection = sqlite3.connect(tmp_path / name)
        connection.execute("PRAGMA foreign_keys = ON")
        _OPEN_CONNECTIONS.append(connection)
        install_schema(connection, approved_ddl_sha256=_require_gate_open())
        scope_id = _seed_scope_with_live_generation(connection)
        _insert_root(connection, scope_id=scope_id)
        for effect_id in (1, 2, 3):
            _insert_open_effect(connection, effect_id)
        _insert_venue_owner(
            connection, owner_external="owner-A", effect_id=1, scope_id=scope_id
        )
        _insert_venue_owner(
            connection, owner_external="owner-B", effect_id=2, scope_id=scope_id
        )
        connection.execute(
            """
            INSERT INTO closure_chain (
                closure_id, scope_id, owner_external, ordinal, effect_id,
                closure_kind, predecessor_closure_id
            )
            VALUES (1, ?, 'owner-A', 1, 1, 'TERMINAL_LEG', NULL)
            """,
            (scope_id,),
        )
        return connection, scope_id

    def _append(
        connection: sqlite3.Connection,
        closure_id: int,
        scope_id: int,
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
            VALUES (?, ?, ?, ?, ?, 'ACCEPTANCE_CLOSED', ?)
            """,
            (closure_id, scope_id, owner, ordinal, effect_id, predecessor),
        )

    # Positive control: the immediate same-owner continuation is accepted.
    continued, scope_id = _fresh("positive.db")
    _append(continued, 2, scope_id, "owner-A", 2, 1, 1)
    head = continued.execute(
        "SELECT ordinal FROM closure_chain WHERE closure_id = 2"
    ).fetchone()
    assert head == (2,)

    # Gap mutant: ordinal 3 declared after predecessor at ordinal 1. The
    # composite FK passes (row exists), the ordinal unique is free, and no
    # successor of row 1 exists yet - only the no-gap trigger can refuse.
    gapped, gap_scope = _fresh("gap.db")
    with pytest.raises(sqlite3.IntegrityError, match="gap-free"):
        _append(gapped, 2, gap_scope, "owner-A", 3, 1, 1)

    # Branch mutant: a second ordinal-2 successor of the same ordinal-1
    # predecessor. The no-gap rule passes it; only the single-successor
    # constraint can refuse it.
    branched, branch_scope = _fresh("branch.db")
    _append(branched, 2, branch_scope, "owner-A", 2, 1, 1)
    with pytest.raises(sqlite3.IntegrityError, match="predecessor_closure_id"):
        _append(branched, 3, branch_scope, "owner-A", 2, 1, 1)

    # Second root mutant: a second predecessorless row for the same owner is
    # refused by the single-root constraint.
    rooted, root_scope = _fresh("root.db")
    with pytest.raises(sqlite3.IntegrityError):
        _append(rooted, 9, root_scope, "owner-A", 1, 1, None)

    # Cross-owner mutant: predecessor belongs to another owner string; the
    # composite foreign key cannot resolve it within this owner's chain.
    crossed, cross_scope = _fresh("cross.db")
    with pytest.raises(sqlite3.IntegrityError):
        crossed.execute(
            """
            INSERT INTO closure_chain (
                closure_id, scope_id, owner_external, ordinal, effect_id,
                closure_kind, predecessor_closure_id
            )
            VALUES (2, ?, 'owner-B', 2, 2, 'TERMINAL_LEG', 1)
            """,
            (cross_scope,),
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
        ("UPDATE root_fill SET root_fill_key_id = 2", ()),
        ("UPDATE root_fill SET owner_generation_id = ?", ("34" * 32,)),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(statement, parameters)


def test_retirement_cannot_rewrite_acquisition_generation_binding(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)

    with pytest.raises(sqlite3.IntegrityError, match="binding is immutable"):
        connection.execute(
            """
            UPDATE acquisition_generation
               SET status = 'RETIRED_UNSERVING',
                   mandate_commitment_sha256 = ?
             WHERE acquisition_generation_id = ?
            """,
            ("7a" * 32, "12" * 32),
        )

    stored = connection.execute(
        "SELECT status, mandate_commitment_sha256 FROM acquisition_generation"
    ).fetchone()
    assert stored == ("LIVE", "9a" * 32)


def test_venue_effect_and_acceptance_bindings_are_immutable(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection, key_id=1, external="root-A")
    _insert_root(connection, key_id=2, external="root-B")
    _insert_open_effect(connection, 1)
    connection.execute(
        "INSERT INTO venue_effect VALUES (2, 1, 2, 'order-2', 'OPEN', 2)"
    )
    connection.execute("INSERT INTO acceptance_set VALUES (1, 1)")

    with pytest.raises(sqlite3.IntegrityError, match="identity is immutable"):
        connection.execute(
            "UPDATE venue_effect"
            " SET root_fill_key_id = 2, disposition = 'INVALIDATED'"
            " WHERE effect_id = 1"
        )
    connection.execute(
        "UPDATE venue_effect SET disposition = 'INVALIDATED' WHERE effect_id = 1"
    )

    with pytest.raises(sqlite3.IntegrityError, match="binding is immutable"):
        connection.execute(
            "UPDATE acceptance_set SET effect_id = 2 WHERE acceptance_set_id = 1"
        )


def test_venue_owner_is_immutable_and_closure_binding_is_exact(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection, key_id=1, external="root-A")
    _insert_root(connection, key_id=2, external="root-B")
    _insert_open_effect(connection, 1)
    connection.execute(
        "INSERT INTO venue_effect VALUES (2, 1, 2, 'order-2', 'OPEN', 2)"
    )
    _insert_venue_owner(connection, owner_external="owner-A", effect_id=1)
    _insert_venue_owner(connection, owner_external="owner-B", effect_id=2, root_id=2)

    stored = connection.execute(
        "INSERT INTO closure_chain VALUES (1, 1, 'owner-A', 1, 1, 'TERMINAL_LEG', NULL)"
    ).rowcount
    assert stored == 1

    # owner-B exists in this scope but belongs to effect/root 2. All closure
    # root-chain checks pass, leaving only the owner-to-effect binding to fail.
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        connection.execute(
            "INSERT INTO closure_chain VALUES"
            " (2, 1, 'owner-B', 1, 1, 'TERMINAL_LEG', NULL)"
        )

    with pytest.raises(sqlite3.IntegrityError, match="owner is immutable"):
        connection.execute(
            """
            UPDATE venue_identity_owner
               SET effect_id = 2, root_fill_key_id = 2
             WHERE scope_id = 1 AND owner_external = 'owner-A'
            """
        )


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
    connection.execute(
        "UPDATE kernel_checkpoint"
        " SET currentness_head_ordinal = 6, checkpoint_version_ordinal = 2"
    )


def test_current_proof_payloads_require_fresh_heads_or_versions(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    generation_id = _insert_profiles_and_generation(connection)
    connection.execute(
        "INSERT INTO acquisition_scope VALUES"
        " (1, ?, 'alpaca', 'paper', 'account-1', 'AAPL')",
        (generation_id,),
    )
    connection.execute(
        "INSERT INTO acquisition_generation VALUES (?, 1, 'LIVE', 1, NULL, ?, ?)",
        ("12" * 32, "9a" * 32, "9b" * 32),
    )
    connection.execute(
        "INSERT INTO kernel_checkpoint VALUES (?, 5, ?, 1)",
        (generation_id, "77" * 32),
    )
    connection.execute(
        "INSERT INTO symbol_controller VALUES (1, ?, 0, 0, 1, 5, 1, ?)",
        ("12" * 32, "9b" * 32),
    )
    _insert_root(connection)
    _insert_fill(connection, fact_id=1, root_id=1, event="evt-head")
    connection.execute(
        "UPDATE root_fill SET economics_head_ordinal = 1 WHERE root_fill_key_id = 1"
    )
    connection.execute(
        "INSERT INTO protection_authority VALUES (1, NULL, ?, 1)",
        ("65" * 32,),
    )

    # Exact no-op writes do not manufacture a new version requirement.
    connection.execute(
        "UPDATE kernel_checkpoint SET checkpoint_sha256 = checkpoint_sha256"
    )
    connection.execute(
        "UPDATE symbol_controller SET aggregate_quantity = aggregate_quantity"
    )
    connection.execute("UPDATE root_fill SET current_quantity = current_quantity")
    connection.execute(
        "UPDATE protection_authority"
        " SET state_commitment_sha256 = state_commitment_sha256"
    )

    with pytest.raises(sqlite3.IntegrityError, match="checkpoint version must advance"):
        connection.execute(
            "UPDATE kernel_checkpoint SET checkpoint_sha256 = ?",
            ("78" * 32,),
        )

    with pytest.raises(sqlite3.IntegrityError, match="controller head must advance"):
        connection.execute(
            "UPDATE symbol_controller SET aggregate_quantity = 1 WHERE scope_id = 1"
        )

    with pytest.raises(sqlite3.IntegrityError, match="economics head must advance"):
        connection.execute(
            "UPDATE root_fill SET current_quantity = 99 WHERE root_fill_key_id = 1"
        )

    with pytest.raises(sqlite3.IntegrityError, match="protection version must advance"):
        connection.execute(
            "UPDATE protection_authority SET state_commitment_sha256 = ?",
            ("66" * 32,),
        )

    # Positive controls: every material replacement carries a fresh owning
    # version/head and remains valid.
    connection.execute(
        "UPDATE kernel_checkpoint"
        " SET checkpoint_sha256 = ?, currentness_head_ordinal = 6,"
        " checkpoint_version_ordinal = 2",
        ("78" * 32,),
    )
    connection.execute(
        "UPDATE symbol_controller"
        " SET aggregate_quantity = 1, currentness_head_ordinal = 6,"
        " controller_version_ordinal = 2 WHERE scope_id = 1"
    )
    _insert_revision(
        connection,
        fact_id=2,
        root_id=1,
        event="evt-head-2",
        predecessor_fact_id=1,
    )
    connection.execute(
        "UPDATE root_fill"
        " SET current_quantity = 99, economics_head_ordinal = 2"
        " WHERE root_fill_key_id = 1"
    )
    connection.execute(
        "UPDATE protection_authority"
        " SET state_commitment_sha256 = ?, version_ordinal = 2",
        ("66" * 32,),
    )

    with pytest.raises(sqlite3.IntegrityError, match="retained"):
        connection.execute("DELETE FROM protection_authority WHERE scope_id = 1")


# ---------------------------------------------------------------------------
# FR-5 canonical effect ownership.


def test_close_requires_committed_claim_and_terminal_freezes(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection)
    _insert_open_effect(connection, 1)
    _insert_open_effect(connection, 2)
    _insert_open_effect(connection, 3)

    with pytest.raises(sqlite3.IntegrityError, match="closure proof"):
        connection.execute(
            "UPDATE venue_effect SET disposition = 'CLOSED' WHERE effect_id = 1"
        )

    connection.execute(
        """
        INSERT INTO dispatch_claim (claim_id, effect_id, claim_ordinal, resolved_kind)
        VALUES (1, 1, 1, NULL)
        """
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO dispatch_claim (claim_id, effect_id, claim_ordinal, resolved_kind)
            VALUES (2, 1, 2, NULL)
            """
        )
    connection.execute(
        "UPDATE dispatch_claim SET resolved_kind = 'DISPATCHED' WHERE claim_id = 1"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE dispatch_claim SET resolved_kind = NULL WHERE claim_id = 1"
        )
    connection.execute(
        "INSERT INTO effect_closure_proof VALUES (1, 'CLAIMED_TERMINAL', ?)",
        ("71" * 32,),
    )
    connection.execute(
        "UPDATE venue_effect SET disposition = 'CLOSED' WHERE effect_id = 1"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE venue_effect SET disposition = 'OPEN' WHERE effect_id = 1"
        )

    # Accepted authority (EC-2 / acceptance_set machine): CLOSED advances
    # only to INVALIDATED, which is then fully terminal.
    connection.execute(
        "UPDATE venue_effect SET disposition = 'INVALIDATED' WHERE effect_id = 1"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE venue_effect SET disposition = 'OPEN' WHERE effect_id = 1"
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE venue_effect SET disposition = 'CLOSED' WHERE effect_id = 1"
        )

    with pytest.raises(sqlite3.IntegrityError, match="OPEN venue effect"):
        connection.execute(
            """
            INSERT INTO dispatch_claim (claim_id, effect_id, claim_ordinal, resolved_kind)
            VALUES (2, 1, 2, NULL)
            """
        )

    # NEVER_DISPATCHED is the exact no-claim closure route. The proof blocks
    # any later claim, and a prior claim blocks manufacture of that proof.
    connection.execute(
        "INSERT INTO effect_closure_proof VALUES (2, 'NEVER_DISPATCHED', ?)",
        ("72" * 32,),
    )
    with pytest.raises(sqlite3.IntegrityError, match="NEVER_DISPATCHED"):
        connection.execute("INSERT INTO dispatch_claim VALUES (3, 2, 3, NULL)")
    connection.execute(
        "UPDATE venue_effect SET disposition = 'CLOSED' WHERE effect_id = 2"
    )

    connection.execute("INSERT INTO dispatch_claim VALUES (4, 3, 4, NULL)")
    with pytest.raises(sqlite3.IntegrityError, match="NEVER_DISPATCHED"):
        connection.execute(
            "INSERT INTO effect_closure_proof VALUES (3, 'NEVER_DISPATCHED', ?)",
            ("73" * 32,),
        )


def test_acceptance_state_machine_gates_late_evidence(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection)
    _insert_open_effect(connection, 1)
    connection.execute(
        "INSERT INTO acceptance_set (acceptance_set_id, effect_id) VALUES (1, 1)"
    )
    connection.execute(
        "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
        " evidence_kind, evidence_digest, evidence_ordinal)"
        " VALUES (1, 1, 'OBSERVATION', ?, 1)",
        ("88" * 32,),
    )
    connection.execute(
        """
        INSERT INTO dispatch_claim (claim_id, effect_id, claim_ordinal, resolved_kind)
        VALUES (1, 1, 1, 'DISPATCHED')
        """
    )
    connection.execute(
        "INSERT INTO effect_closure_proof VALUES (1, 'ADAPTER_COMPLETE', ?)",
        ("74" * 32,),
    )
    connection.execute("UPDATE venue_effect SET disposition = 'CLOSED'")

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
    connection.execute("UPDATE venue_effect SET disposition = 'INVALIDATED'")


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
        EXPLAIN QUERY PLAN SELECT fact_id FROM execution_fact_head
        WHERE root_fill_key_id = ?
        """,
        (root_id,),
    ).fetchall()
    head_text = " ".join(str(row[-1]) for row in head_plan)
    assert "INTEGER PRIMARY KEY" in head_text
    assert "SCAN execution_fact" not in head_text

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


# ---------------------------------------------------------------------------
# REV-0070-followup regression locks for the revised origin CHECK blocks.


def test_origin_charset_predicates_target_the_host_part_only() -> None:
    """The scheme prefix must never be scanned by content predicates."""

    _require_gate_open()
    ddl = schema_module.SCHEMA_DDL

    for column in _ORIGIN_COLUMNS:
        assert f"AND {column} NOT GLOB '*[^a-z0-9.:-]*'" not in ddl
        assert f"AND substr({column}, 9) NOT GLOB '*[^a-z0-9.:-]*'" in ddl
        assert f"AND length({column}) >= 9" in ddl


def _insert_profile_with_event_origin(
    connection: sqlite3.Connection,
    *,
    profile_id: str,
    order_event_origin: str,
) -> None:
    connection.execute(
        """
        INSERT INTO execution_connection_profile (
            connection_profile_id, broker_provider, environment_class,
            account_identity, trade_command_origin, order_query_origin,
            order_event_origin, credential_handle_fingerprint,
            adapter_contract_version, capability_profile_sha256,
            deployment_identity, profile_commitment_sha256
        )
        VALUES (?, 'ALPACA', 'PAPER', ?,
                'https://trade.example.com',
                'https://query.example.com',
                ?, ?, '1.2.3', ?, ?, ?)
        """,
        (
            profile_id,
            "aa" * 32,
            order_event_origin,
            "bb" * 32,
            "cc" * 32,
            "dd" * 32,
            "ee" * 32,
        ),
    )


def test_sqlite_origin_checks_accept_canonical_and_refuse_every_mutant(
    tmp_path: object,
) -> None:
    """Origin CHECK clauses are exercised by the real SQLite engine itself."""

    connection = _connection(tmp_path)
    install_schema(connection, approved_ddl_sha256=_require_gate_open())

    canonical_mutants: dict[str, str] = {
        "scheme": "http://stream.example.com",
        "bare-scheme": "https://",
        "uppercase-host": "https://Stream.example.com",
        "path": "https://stream.example.com/v1",
        "userinfo": "https://user@stream.example.com",
        "port-443": "https://stream.example.com:443",
        "double-colon": "https://str::eam.example.com",
        "space": "https://stream.example.com path",
        "second-double-slash": "https://stream.example.com//x",
        "empty-origin": "",
    }

    accepted_profile = "cd" * 32
    _insert_profile_with_event_origin(
        connection,
        profile_id=accepted_profile,
        order_event_origin="https://stream.example.com",
    )

    for label, mutant_origin in canonical_mutants.items():
        with pytest.raises(sqlite3.IntegrityError):
            _insert_profile_with_event_origin(
                connection,
                profile_id=label.encode().hex().ljust(64, "0")[:64],
                order_event_origin=mutant_origin,
            )

    remaining = connection.execute(
        "SELECT count(*) FROM execution_connection_profile"
    ).fetchone()
    assert remaining is not None and remaining[0] == 1


def _insert_profile_with_origin_override(
    connection: sqlite3.Connection,
    *,
    profile_id: str,
    column: str,
    value: str,
) -> None:
    columns = (
        "connection_profile_id, broker_provider, environment_class,"
        " account_identity, trade_command_origin, order_query_origin,"
        " order_event_origin, credential_handle_fingerprint,"
        " adapter_contract_version, capability_profile_sha256,"
        " deployment_identity, profile_commitment_sha256"
    )
    canonical = {
        "trade_command_origin": "https://trade.example.com",
        "order_query_origin": "https://query.example.com",
        "order_event_origin": "https://stream.example.com",
    }
    values = {
        "connection_profile_id": profile_id,
        "broker_provider": "ALPACA",
        "environment_class": "PAPER",
        "account_identity": "aa" * 32,
        "credential_handle_fingerprint": "bb" * 32,
        "adapter_contract_version": "1.2.3",
        "capability_profile_sha256": "cc" * 32,
        "deployment_identity": "dd" * 32,
        "profile_commitment_sha256": ("f0" * 15 + profile_id[:2] + "ee" * 16),
    }
    values["trade_command_origin"] = canonical["trade_command_origin"]
    values["order_query_origin"] = canonical["order_query_origin"]
    values["order_event_origin"] = canonical["order_event_origin"]

    if column == "source_origin":
        connection.execute(
            """
            INSERT INTO market_data_source_profile (
                market_source_profile_id, provider, environment_or_feed,
                source_origin, entitlement_class,
                normalization_contract_version,
                data_capability_profile_sha256,
                source_profile_commitment_sha256
            )
            VALUES (?, 'ALPACA', 'iex-feed', ?, 'IEX', '0.1.0', ?, ?)
            """,
            (
                profile_id,
                value,
                "ff" * 32,
                ("b7" * 15 + profile_id[:2] + "c8" * 16),
            ),
        )
        return

    values[column] = value

    connection.execute(
        f"INSERT INTO execution_connection_profile ({columns}) VALUES"
        " (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuple(
            values[name]
            for name in (
                "connection_profile_id",
                "broker_provider",
                "environment_class",
                "account_identity",
                "trade_command_origin",
                "order_query_origin",
                "order_event_origin",
                "credential_handle_fingerprint",
                "adapter_contract_version",
                "capability_profile_sha256",
                "deployment_identity",
                "profile_commitment_sha256",
            )
        ),
    )


@pytest.mark.parametrize(
    "column",
    [
        "trade_command_origin",
        "order_query_origin",
        "order_event_origin",
        "source_origin",
    ],
)
def test_sqlite_rejects_uppercase_scheme_on_every_origin_column(
    tmp_path: object,
    column: str,
) -> None:
    """LIKE folds ASCII case; the GLOB anchor must not."""

    connection = _installed_connection(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        _insert_profile_with_origin_override(
            connection,
            profile_id="97" * 32,
            column=column,
            value="HTTPS://stream.example.com",
        )


# ---------------------------------------------------------------------------
# FR-3 / FR-4 / FR-6 same-scope relational bindings: database-level negative
# controls proving cross-scope substitutions are structurally refused.


def _seed_two_scopes(connection: sqlite3.Connection) -> None:
    """Two deployment generations, two scopes, one live acquisition gen each."""

    generation_a = _insert_profiles_and_generation(connection)
    connection.execute(
        "INSERT INTO application_generation VALUES (?, ?, ?, 2)",
        ("56" * 32, "cd" * 32, "ef" * 32),
    )
    connection.execute(
        """
        INSERT INTO acquisition_scope VALUES
        (1, ?, 'alpaca', 'paper', 'account-1', 'AAPL'),
        (2, ?, 'alpaca', 'paper', 'account-1', 'MSFT')
        """,
        (generation_a, "56" * 32),
    )
    connection.execute(
        """
        INSERT INTO acquisition_generation VALUES
        (?, 1, 'LIVE', 1, NULL, ?, ?),
        (?, 2, 'LIVE', 1, NULL, ?, ?)
        """,
        ("12" * 32, "9a" * 32, "9b" * 32, "34" * 32, "8a" * 32, "8b" * 32),
    )


def test_controller_cannot_bind_generation_from_another_scope(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_two_scopes(connection)

    stored = connection.execute(
        "INSERT INTO symbol_controller VALUES (1, ?, 0, 0, 1, 0, 1, ?)",
        ("12" * 32, "9b" * 32),
    ).rowcount
    assert stored == 1

    with pytest.raises(sqlite3.IntegrityError, match="live generation"):
        connection.execute(
            "INSERT INTO symbol_controller VALUES (2, ?, 0, 0, 1, 0, 2, ?)",
            ("12" * 32, "9b" * 32),
        )

    with pytest.raises(sqlite3.IntegrityError, match="compatible"):
        connection.execute(
            "INSERT INTO symbol_controller VALUES (2, ?, 0, 0, 1, 0, 2, ?)",
            ("34" * 32, "9b" * 32),
        )

    with pytest.raises(sqlite3.IntegrityError, match="remains LIVE"):
        connection.execute(
            "UPDATE acquisition_generation SET status = 'RETIRED_UNSERVING'"
            " WHERE acquisition_generation_id = ?",
            ("12" * 32,),
        )

    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = NULL,"
        " currentness_head_ordinal = 1, controller_version_ordinal = 2"
        " WHERE scope_id = 1"
    )
    connection.execute(
        "UPDATE acquisition_generation SET status = 'RETIRED_UNSERVING'"
        " WHERE acquisition_generation_id = ?",
        ("12" * 32,),
    )


def test_root_fill_cannot_be_owned_by_generation_of_another_scope(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_two_scopes(connection)

    stored = connection.execute(
        "INSERT INTO root_fill VALUES (1, 1, ?, 'r-A', 10, 10000, 0, '1', -2, 0)",
        ("12" * 32,),
    ).rowcount
    assert stored == 1

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        connection.execute(
            "INSERT INTO root_fill VALUES (2, 2, ?, 'r-B', 10, 10000, 0, '1', -2, 0)",
            ("12" * 32,),
        )


def test_execution_fact_cannot_reference_root_of_another_scope(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_two_scopes(connection)
    connection.execute(
        "INSERT INTO root_fill VALUES (1, 1, ?, 'r-A', 10, 10000, 0, '1', -2, 0)",
        ("12" * 32,),
    )

    # Run the cross-scope mutant before the canonical FILL exists so the
    # exact root/scope foreign key, not one-FILL-per-root uniqueness, owns it.
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        connection.execute(
            """
            INSERT INTO execution_fact (
                fact_id, scope_id, application_generation_id,
                broker_text, environment_text, account_text,
                root_fill_key_id, source_event_id, kind,
                quantity, price_units, scale_sign, scale_digits,
                scale_exponent, predecessor_fact_id, fact_ordinal
            )
            VALUES (2, 2, ?, 'alpaca', 'paper', 'account-1',
                    1, 'evt-x', 'FILL', 5, 10000, 0, '1', -2, NULL, 2)
            """,
            ("56" * 32,),
        )

    # Positive control: same-scope root reference is accepted.
    assert (
        _insert_fill(
            connection,
            fact_id=1,
            root_id=1,
            event="evt-ok",
            scope_id=1,
            generation_id="ab" * 32,
        )
        == 1
    )


def test_venue_effect_cannot_reference_root_of_another_scope(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_two_scopes(connection)
    connection.execute(
        "INSERT INTO root_fill VALUES (1, 1, ?, 'r-A', 10, 10000, 0, '1', -2, 0)",
        ("12" * 32,),
    )

    stored = connection.execute(
        "INSERT INTO venue_effect VALUES (1, 1, 1, 'o-1', 'OPEN', 1)"
    ).rowcount
    assert stored == 1

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        connection.execute(
            "INSERT INTO venue_effect VALUES (2, 2, 1, 'o-2', 'OPEN', 2)"
        )


def test_closure_cannot_reference_effect_of_another_scope_or_owner(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_two_scopes(connection)
    _insert_root(connection)
    _insert_open_effect(connection, 1)
    _insert_open_effect(connection, 2)
    _insert_venue_owner(connection, owner_external="owner-A", effect_id=1)
    _insert_venue_owner(connection, owner_external="owner-B", effect_id=2)

    stored = connection.execute(
        "INSERT INTO closure_chain VALUES (1, 1, 'owner-A', 1, 1, 'TERMINAL_LEG', NULL)"
    ).rowcount
    assert stored == 1

    # Scope substitution: closure scoped to scope 2 referencing an effect
    # owned by scope 1.
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        connection.execute(
            "INSERT INTO closure_chain VALUES (2, 2, 'owner-B', 1, 1,"
            " 'TERMINAL_LEG', NULL)"
        )

    # Owner substitution within one scope: owner-B is valid and has no closure
    # root yet, but belongs to effect 2 rather than effect 1. Only the exact
    # owner-to-effect foreign key can reject this otherwise valid root row.
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        connection.execute(
            "INSERT INTO closure_chain VALUES (3, 1, 'owner-B', 1, 1,"
            " 'TERMINAL_LEG', NULL)"
        )


def test_acquisition_predecessor_must_be_same_scope_and_immediate(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_two_scopes(connection)

    # Other-scope predecessor is refused outright.
    with pytest.raises(sqlite3.IntegrityError, match="immediate prior"):
        connection.execute(
            "INSERT INTO acquisition_generation VALUES"
            " (?, 2, 'RETIRED_UNSERVING', 2, ?, ?, ?)",
            ("aa" * 32, "12" * 32, "7a" * 32, "7b" * 32),
        )

    # Non-immediate ordinal inside the same scope is refused too.
    connection.execute(
        "UPDATE acquisition_generation SET status = 'RETIRED_UNSERVING'"
        " WHERE acquisition_generation_id = ?",
        ("12" * 32,),
    )
    connection.execute(
        "INSERT INTO acquisition_generation VALUES"
        " (?, 1, 'RETIRED_UNSERVING', 2, ?, ?, ?)",
        ("bb" * 32, "12" * 32, "7c" * 32, "7d" * 32),
    )
    with pytest.raises(sqlite3.IntegrityError, match="immediate prior"):
        connection.execute(
            "INSERT INTO acquisition_generation VALUES"
            " (?, 1, 'RETIRED_UNSERVING', 4, ?, ?, ?)",
            ("cc" * 32, "12" * 32, "7e" * 32, "7f" * 32),
        )

    # Positive control: the immediate same-scope successor is accepted and
    # may hold LIVE authority once its predecessor retired.
    stored = connection.execute(
        "INSERT INTO acquisition_generation VALUES (?, 1, 'LIVE', 3, ?, ?, ?)",
        ("dd" * 32, "bb" * 32, "6a" * 32, "6b" * 32),
    ).rowcount
    assert stored == 1
