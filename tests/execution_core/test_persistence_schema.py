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
    SchemaInstallError,
    SchemaTargetNotEmptyError,
    install_schema,
    schema_ddl_digest,
    verify_schema_connection,
)


_GATE_DIGEST: str | None = (
    "2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859"
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
_DEFAULT_EXECUTION_PROFILE_ID = "cd" * 32
_DEFAULT_MARKET_SOURCE_PROFILE_ID = "ef" * 32


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
    connection.execute("PRAGMA recursive_triggers = ON")
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
            connection_profile_id, application_generation,
            broker_provider, environment_class,
            account_identity, trade_command_origin, order_query_origin,
            order_event_origin, credential_handle_fingerprint,
            adapter_contract_version, capability_profile_sha256,
            deployment_identity, profile_commitment_sha256
        )
        VALUES (
            ?, ?, 'ALPACA', 'PAPER', ?,
            'https://trade.example.com',
            'https://query.example.com',
            'https://stream.example.com',
            ?, '1.2.3', ?, ?, ?
        )
        """,
        (
            _DEFAULT_EXECUTION_PROFILE_ID,
            _DEFAULT_GENERATION_ID,
            "aa" * 32,
            "bb" * 32,
            "cc" * 32,
            "dd" * 32,
            "ee" * 32,
        ),
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
        (
            _DEFAULT_GENERATION_ID,
            _DEFAULT_EXECUTION_PROFILE_ID,
            _DEFAULT_MARKET_SOURCE_PROFILE_ID,
        ),
    )
    return "ab" * 32


def _insert_second_profiles_and_generation(connection: sqlite3.Connection) -> str:
    generation_id = "56" * 32
    execution_profile_id = "67" * 32
    market_profile_id = "78" * 32
    connection.execute(
        """
        INSERT INTO execution_connection_profile (
            connection_profile_id, application_generation,
            broker_provider, environment_class, account_identity,
            trade_command_origin, order_query_origin, order_event_origin,
            credential_handle_fingerprint, adapter_contract_version,
            capability_profile_sha256, deployment_identity,
            profile_commitment_sha256
        )
        VALUES (?, ?, 'ALPACA', 'PAPER', ?,
                'https://trade-two.example.com',
                'https://query-two.example.com',
                'https://stream-two.example.com',
                ?, '1.2.3', ?, ?, ?)
        """,
        (
            execution_profile_id,
            generation_id,
            "11" * 32,
            "22" * 32,
            "33" * 32,
            "44" * 32,
            "55" * 32,
        ),
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
        VALUES (?, 'ALPACA', 'sip-feed', 'https://feed-two.example.com',
                'SIP', '0.1.0', ?, ?)
        """,
        (market_profile_id, "66" * 32, "77" * 32),
    )
    connection.execute(
        """
        INSERT INTO application_generation (
            application_generation_id, selected_execution_profile_id,
            selected_market_source_profile_id, activation_ordinal
        )
        VALUES (?, ?, ?, 2)
        """,
        (generation_id, execution_profile_id, market_profile_id),
    )
    return generation_id


def _seed_scope_with_live_generation(connection: sqlite3.Connection) -> int:
    generation_id = _insert_profiles_and_generation(connection)
    connection.execute(
        """
        INSERT INTO acquisition_scope (
            scope_id, application_generation_id,
            execution_profile_id, symbol_text
        )
        VALUES (1, ?, ?, 'AAPL')
        """,
        (generation_id, _DEFAULT_EXECUTION_PROFILE_ID),
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


def _retire_first_and_insert_live_successor(connection: sqlite3.Connection) -> str:
    successor_id = "34" * 32
    _close_generation_authority(connection, generation_id="12" * 32)
    connection.execute(
        "UPDATE acquisition_generation SET status = 'RETIRED_UNSERVING'"
        " WHERE acquisition_generation_id = ?",
        ("12" * 32,),
    )
    connection.execute(
        "INSERT INTO acquisition_generation VALUES (?, 1, 'LIVE', 2, ?, ?, ?)",
        (successor_id, "12" * 32, "9c" * 32, "9b" * 32),
    )
    return successor_id


def _insert_controller(
    connection: sqlite3.Connection,
    *,
    scope_id: int = 1,
    application_generation_id: str = _DEFAULT_GENERATION_ID,
    execution_profile_id: str = _DEFAULT_EXECUTION_PROFILE_ID,
    acquisition_generation_id: str = "12" * 32,
    emergency_compatibility_sha256: str = "9b" * 32,
    aggregate_quantity: int = 0,
    integrity_state: str = "CONSISTENT",
) -> int:
    connection.execute(
        """
        INSERT INTO symbol_controller (
            scope_id, application_generation_id, execution_profile_id,
            live_acquisition_generation_id, aggregate_quantity,
            integrity_state, currentness_head_ordinal,
            controller_version_ordinal, emergency_compatibility_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, 0, 1, ?)
        """,
        (
            scope_id,
            application_generation_id,
            execution_profile_id,
            acquisition_generation_id,
            aggregate_quantity,
            integrity_state,
            emergency_compatibility_sha256,
        ),
    )
    return scope_id


def _insert_root(
    connection: sqlite3.Connection,
    *,
    key_id: int = 1,
    scope_id: int = 1,
    external: str = "root-fill-A",
    application_generation_id: str = _DEFAULT_GENERATION_ID,
    execution_profile_id: str = _DEFAULT_EXECUTION_PROFILE_ID,
    owner_generation_id: str = "12" * 32,
) -> int:
    connection.execute(
        """
        INSERT INTO root_fill (
            root_fill_key_id, scope_id, application_generation_id,
            execution_profile_id, owner_generation_id,
            root_fill_external, economics_head_ordinal
        )
        VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (
            key_id,
            scope_id,
            application_generation_id,
            execution_profile_id,
            owner_generation_id,
            external,
        ),
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
    execution_profile_id: str = _DEFAULT_EXECUTION_PROFILE_ID,
    side: str = "BUY",
    fact_ordinal: int | None = None,
    ensure_route: bool = True,
) -> int:
    stored_ordinal = fact_id if fact_ordinal is None else fact_ordinal
    if ensure_route:
        _ensure_acquisition_root_route(connection, root_id=root_id)
    connection.execute(
        """
        INSERT INTO execution_fact (
            fact_id, scope_id, application_generation_id,
            execution_profile_id, root_fill_key_id, source_event_id,
            order_external, side, kind, authority, quantity,
            price_present, price_units, scale_sign, scale_digits,
            scale_exponent, tick_units, tick_scale_sign,
            tick_scale_digits, tick_scale_exponent,
            predecessor_fact_id, fact_ordinal
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'FILL',
                'BROKER_AUTHORITATIVE', 10,
                1, 10000, 0, '1', -2, 1, 0, '1', -2, NULL, ?)
        """,
        (
            fact_id,
            scope_id,
            generation_id,
            execution_profile_id,
            root_id,
            event,
            f"order-{root_id}",
            side,
            stored_ordinal,
        ),
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
    fact_ordinal: int | None = None,
    order_external: str | None = None,
    side: str = "BUY",
) -> int:
    stored_ordinal = fact_id if fact_ordinal is None else fact_ordinal
    connection.execute(
        """
        INSERT INTO execution_fact (
            fact_id, scope_id, application_generation_id,
            execution_profile_id, root_fill_key_id, source_event_id,
            order_external, side, kind, authority, quantity,
            price_present, price_units, scale_sign, scale_digits,
            scale_exponent, tick_units, tick_scale_sign,
            tick_scale_digits, tick_scale_exponent,
            predecessor_fact_id, fact_ordinal
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'BROKER_AUTHORITATIVE', 7,
                1, 10100, 0, '1', -2, 1, 0, '1', -2, ?, ?)
        """,
        (
            fact_id,
            scope_id,
            _DEFAULT_GENERATION_ID,
            _DEFAULT_EXECUTION_PROFILE_ID,
            root_id,
            event,
            f"order-{root_id}" if order_external is None else order_external,
            side,
            kind,
            predecessor_fact_id,
            stored_ordinal,
        ),
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
    fact_ordinal: int | None = None,
    side: str = "BUY",
) -> int:
    stored_ordinal = fact_id if fact_ordinal is None else fact_ordinal
    connection.execute(
        """
        INSERT INTO execution_fact (
            fact_id, scope_id, application_generation_id,
            execution_profile_id, root_fill_key_id, source_event_id,
            order_external, side, kind, authority, quantity,
            price_present, price_units, scale_sign, scale_digits,
            scale_exponent, tick_units, tick_scale_sign,
            tick_scale_digits, tick_scale_exponent,
            predecessor_fact_id, fact_ordinal
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'TRADE_BUST',
                'BROKER_AUTHORITATIVE', 0,
                0, 0, 0, '0', 0, 0, 0, '0', 0, ?, ?)
        """,
        (
            fact_id,
            scope_id,
            _DEFAULT_GENERATION_ID,
            _DEFAULT_EXECUTION_PROFILE_ID,
            root_id,
            event,
            f"order-{root_id}",
            side,
            predecessor_fact_id,
            stored_ordinal,
        ),
    )
    return fact_id


def _insert_open_effect(
    connection: sqlite3.Connection,
    effect_id: int,
    *,
    root_id: int = 1,
    scope_id: int = 1,
    application_generation_id: str = _DEFAULT_GENERATION_ID,
    execution_profile_id: str = _DEFAULT_EXECUTION_PROFILE_ID,
    acquisition_generation_id: str = "12" * 32,
    generation_mandate_commitment_sha256: str = "9a" * 32,
    expected_controller_head_ordinal: int | None = None,
    expected_protection_version_ordinal: int | None = None,
    authority_class: str = "NORMAL",
    side: str = "BUY",
    quantity: int = 10,
    ensure_protection: bool = True,
) -> int:
    del root_id
    controller_row = connection.execute(
        "SELECT currentness_head_ordinal FROM symbol_controller WHERE scope_id = ?",
        (scope_id,),
    ).fetchone()
    if controller_row is None:
        compatibility_row = connection.execute(
            "SELECT emergency_compatibility_sha256"
            " FROM acquisition_generation"
            " WHERE acquisition_generation_id = ? AND scope_id = ?",
            (acquisition_generation_id, scope_id),
        ).fetchone()
        compatibility = (
            str(compatibility_row[0]) if compatibility_row is not None else "9b" * 32
        )
        _insert_controller(
            connection,
            scope_id=scope_id,
            application_generation_id=application_generation_id,
            execution_profile_id=execution_profile_id,
            acquisition_generation_id=acquisition_generation_id,
            emergency_compatibility_sha256=compatibility,
        )
        controller_row = (0,)
    stored_head = (
        int(controller_row[0])
        if expected_controller_head_ordinal is None
        else expected_controller_head_ordinal
    )
    if authority_class == "NORMAL" and ensure_protection:
        _ensure_normal_protection(
            connection,
            seed=effect_id,
            scope_id=scope_id,
            application_generation_id=application_generation_id,
            acquisition_generation_id=acquisition_generation_id,
            generation_mandate_commitment_sha256=(generation_mandate_commitment_sha256),
            expected_controller_head_ordinal=stored_head,
        )
    protection_row = connection.execute(
        "SELECT version_ordinal FROM protection_authority WHERE scope_id = ?",
        (scope_id,),
    ).fetchone()
    stored_protection_version = (
        (1 if protection_row is None else int(protection_row[0]))
        if expected_protection_version_ordinal is None
        else expected_protection_version_ordinal
    )
    connection.execute(
        """
        INSERT INTO venue_effect (
            effect_id, effect_external, scope_id, application_generation_id,
            execution_profile_id, acquisition_generation_id,
            generation_mandate_commitment_sha256,
            expected_controller_head_ordinal,
            expected_protection_version_ordinal, authority_class,
            request_occurrence_external, mandate_external, effect_kind,
            client_order_external, target_order_external, side, quantity,
            economic_scope, lifecycle_state, disposition, created_ordinal
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUBMIT', ?, NULL, ?, ?,
                x'01', 'REQUESTED', 'OPEN', ?)
        """,
        (
            effect_id,
            f"effect-{effect_id}",
            scope_id,
            application_generation_id,
            execution_profile_id,
            acquisition_generation_id,
            generation_mandate_commitment_sha256,
            stored_head,
            stored_protection_version,
            authority_class,
            f"request-{effect_id}",
            f"mandate-{effect_id}",
            f"client-{effect_id}",
            side,
            quantity,
            effect_id,
        ),
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
    execution_profile_id: str = _DEFAULT_EXECUTION_PROFILE_ID,
    observation_external: str | None = None,
) -> str:
    stored_observation = (
        f"observation-{owner_external}"
        if observation_external is None
        else observation_external
    )
    effect_row = connection.execute(
        "SELECT disposition FROM venue_effect WHERE effect_id = ?",
        (effect_id,),
    ).fetchone()
    assert effect_row is not None
    effect_disposition = str(effect_row[0])
    assert effect_disposition in {"OPEN", "CLOSED", "INVALIDATED"}
    admitted_after_effect_closed = int(effect_disposition != "OPEN")
    connection.execute(
        """
        INSERT INTO venue_identity_owner (
            scope_id, execution_profile_id, owner_external,
            observation_external, effect_id, root_fill_key_id,
            owner_generation_id, admitted_after_effect_closed
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            scope_id,
            execution_profile_id,
            owner_external,
            stored_observation,
            effect_id,
            root_id,
            owner_generation_id,
            admitted_after_effect_closed,
        ),
    )
    return owner_external


def _ensure_acquisition_root_route(
    connection: sqlite3.Connection,
    *,
    root_id: int,
) -> None:
    if (
        connection.execute(
            "SELECT 1 FROM acquisition_root_route WHERE root_fill_key_id = ?",
            (root_id,),
        ).fetchone()
        is not None
    ):
        return
    root = connection.execute(
        "SELECT scope_id, application_generation_id, execution_profile_id,"
        " owner_generation_id FROM root_fill WHERE root_fill_key_id = ?",
        (root_id,),
    ).fetchone()
    if root is None:
        return
    scope_id, application_generation_id, execution_profile_id, generation_id = root
    mandate = connection.execute(
        "SELECT mandate_commitment_sha256 FROM acquisition_generation"
        " WHERE acquisition_generation_id = ? AND scope_id = ?",
        (generation_id, scope_id),
    ).fetchone()
    assert mandate is not None
    effect_id = 1_000_000 + int(root_id)
    owner_external = f"route-owner-{root_id}"
    observation_external = f"route-observation-{root_id}"
    _insert_open_effect(
        connection,
        effect_id,
        scope_id=int(scope_id),
        application_generation_id=str(application_generation_id),
        execution_profile_id=str(execution_profile_id),
        acquisition_generation_id=str(generation_id),
        generation_mandate_commitment_sha256=str(mandate[0]),
    )
    _insert_venue_owner(
        connection,
        owner_external=owner_external,
        observation_external=observation_external,
        effect_id=effect_id,
        root_id=root_id,
        scope_id=int(scope_id),
        owner_generation_id=str(generation_id),
        execution_profile_id=str(execution_profile_id),
    )
    connection.execute(
        "INSERT INTO acquisition_root_route VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            root_id,
            scope_id,
            application_generation_id,
            execution_profile_id,
            generation_id,
            effect_id,
            owner_external,
            observation_external,
        ),
    )
    _insert_claim(
        connection,
        claim_id=effect_id,
        effect_id=effect_id,
        claim_ordinal=effect_id,
        execution_profile_id=str(execution_profile_id),
    )


def _insert_claim(
    connection: sqlite3.Connection,
    *,
    claim_id: int,
    effect_id: int,
    claim_ordinal: int | None = None,
    execution_profile_id: str = _DEFAULT_EXECUTION_PROFILE_ID,
) -> int:
    ordinal = claim_id if claim_ordinal is None else claim_ordinal
    connection.execute(
        """
        INSERT INTO dispatch_claim (
            claim_id, effect_id, execution_profile_id,
            claim_occurrence_external, claim_ordinal
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            claim_id,
            effect_id,
            execution_profile_id,
            f"claim-{claim_id}",
            ordinal,
        ),
    )
    return claim_id


def _insert_market_stream(
    connection: sqlite3.Connection,
    *,
    stream_generation_id: str,
    scope_id: int = 1,
    application_generation_id: str = _DEFAULT_GENERATION_ID,
    acquisition_generation_id: str = "12" * 32,
    generation_mandate_commitment_sha256: str = "9a" * 32,
    source_profile_id: str = _DEFAULT_MARKET_SOURCE_PROFILE_ID,
    session_external: str = "session-1",
    sequence_mode: str = "SEQUENCED",
) -> str:
    connection.execute(
        """
        INSERT INTO market_stream_authority (
            stream_generation_id, scope_id, application_generation_id,
            acquisition_generation_id,
            generation_mandate_commitment_sha256,
            source_profile_id, session_external, sequence_mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stream_generation_id,
            scope_id,
            application_generation_id,
            acquisition_generation_id,
            generation_mandate_commitment_sha256,
            source_profile_id,
            session_external,
            sequence_mode,
        ),
    )
    return stream_generation_id


def _insert_market_cursor(
    connection: sqlite3.Connection,
    *,
    stream_generation_id: str,
    fixed_cursor_ordinal: int,
    published_head_ordinal: int,
    scope_id: int = 1,
    application_generation_id: str = _DEFAULT_GENERATION_ID,
    acquisition_generation_id: str = "12" * 32,
    generation_mandate_commitment_sha256: str = "9a" * 32,
    source_profile_id: str = _DEFAULT_MARKET_SOURCE_PROFILE_ID,
    session_external: str = "session-1",
    sequence_mode: str = "SEQUENCED",
) -> str:
    connection.execute(
        """
        INSERT INTO market_cursor (
            stream_generation_id, scope_id, application_generation_id,
            acquisition_generation_id,
            generation_mandate_commitment_sha256,
            source_profile_id, session_external, sequence_mode,
            fixed_cursor_ordinal, published_head_ordinal
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stream_generation_id,
            scope_id,
            application_generation_id,
            acquisition_generation_id,
            generation_mandate_commitment_sha256,
            source_profile_id,
            session_external,
            sequence_mode,
            fixed_cursor_ordinal,
            published_head_ordinal,
        ),
    )
    return stream_generation_id


def _insert_protection_authority(
    connection: sqlite3.Connection,
    *,
    state_commitment_sha256: str,
    version_ordinal: int,
    scope_id: int = 1,
    stream_generation_id: str | None = None,
    acquisition_generation_id: str = "12" * 32,
    generation_mandate_commitment_sha256: str = "9a" * 32,
    source_profile_id: str = _DEFAULT_MARKET_SOURCE_PROFILE_ID,
    session_external: str = "session-1",
    sequence_mode: str = "SEQUENCED",
    expected_controller_head_ordinal: int | None = None,
    authority_class: str = "NORMAL",
) -> int:
    active_values: tuple[str | None, ...]
    if stream_generation_id is None:
        active_values = (None, None, None, None, None, None)
    else:
        active_values = (
            stream_generation_id,
            acquisition_generation_id,
            generation_mandate_commitment_sha256,
            source_profile_id,
            session_external,
            sequence_mode,
        )
    controller_row = connection.execute(
        "SELECT currentness_head_ordinal FROM symbol_controller WHERE scope_id = ?",
        (scope_id,),
    ).fetchone()
    stored_head = (
        (0 if controller_row is None else int(controller_row[0]))
        if expected_controller_head_ordinal is None
        else expected_controller_head_ordinal
    )
    connection.execute(
        """
        INSERT INTO protection_authority (
            scope_id, authority_class, active_stream_generation_id,
            active_acquisition_generation_id,
            active_generation_mandate_commitment_sha256,
            active_source_profile_id, active_session_external,
            active_sequence_mode, expected_controller_head_ordinal,
            state_commitment_sha256, version_ordinal
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            scope_id,
            authority_class,
            *active_values,
            stored_head,
            state_commitment_sha256,
            version_ordinal,
        ),
    )
    return scope_id


def _ensure_normal_protection(
    connection: sqlite3.Connection,
    *,
    seed: int,
    scope_id: int,
    application_generation_id: str,
    acquisition_generation_id: str,
    generation_mandate_commitment_sha256: str,
    expected_controller_head_ordinal: int,
) -> None:
    source_row = connection.execute(
        "SELECT application.selected_market_source_profile_id"
        " FROM acquisition_scope AS scope"
        " JOIN application_generation AS application"
        " ON application.application_generation_id ="
        " scope.application_generation_id"
        " WHERE scope.scope_id = ?",
        (scope_id,),
    ).fetchone()
    assert source_row is not None
    source_profile_id = str(source_row[0])
    stream_row = connection.execute(
        "SELECT stream_generation_id, session_external, sequence_mode"
        " FROM market_stream_authority"
        " WHERE scope_id = ? AND acquisition_generation_id = ?"
        " AND generation_mandate_commitment_sha256 = ?"
        " ORDER BY stream_generation_id LIMIT 1",
        (
            scope_id,
            acquisition_generation_id,
            generation_mandate_commitment_sha256,
        ),
    ).fetchone()
    if stream_row is None:
        stream_generation_id = "de" * 24 + f"{seed:016x}"
        session_external = f"auto-session-{scope_id}-{seed}"
        sequence_mode = "SEQUENCED"
        _insert_market_stream(
            connection,
            stream_generation_id=stream_generation_id,
            scope_id=scope_id,
            application_generation_id=application_generation_id,
            acquisition_generation_id=acquisition_generation_id,
            generation_mandate_commitment_sha256=(generation_mandate_commitment_sha256),
            source_profile_id=source_profile_id,
            session_external=session_external,
            sequence_mode=sequence_mode,
        )
    else:
        stream_generation_id = str(stream_row[0])
        session_external = str(stream_row[1])
        sequence_mode = str(stream_row[2])

    protection_row = connection.execute(
        "SELECT authority_class, active_acquisition_generation_id,"
        " expected_controller_head_ordinal, version_ordinal"
        " FROM protection_authority WHERE scope_id = ?",
        (scope_id,),
    ).fetchone()
    state_commitment = "cf" * 24 + f"{seed:016x}"
    if protection_row is None:
        _insert_protection_authority(
            connection,
            scope_id=scope_id,
            stream_generation_id=stream_generation_id,
            acquisition_generation_id=acquisition_generation_id,
            generation_mandate_commitment_sha256=(generation_mandate_commitment_sha256),
            source_profile_id=source_profile_id,
            session_external=session_external,
            sequence_mode=sequence_mode,
            expected_controller_head_ordinal=expected_controller_head_ordinal,
            state_commitment_sha256=state_commitment,
            version_ordinal=1,
        )
        return
    if protection_row[:3] == (
        "NORMAL",
        acquisition_generation_id,
        expected_controller_head_ordinal,
    ):
        return
    connection.execute(
        "UPDATE protection_authority"
        " SET authority_class = 'NORMAL', active_stream_generation_id = ?,"
        " active_acquisition_generation_id = ?,"
        " active_generation_mandate_commitment_sha256 = ?,"
        " active_source_profile_id = ?, active_session_external = ?,"
        " active_sequence_mode = ?, expected_controller_head_ordinal = ?,"
        " state_commitment_sha256 = ?, version_ordinal = ?"
        " WHERE scope_id = ?",
        (
            stream_generation_id,
            acquisition_generation_id,
            generation_mandate_commitment_sha256,
            source_profile_id,
            session_external,
            sequence_mode,
            expected_controller_head_ordinal,
            state_commitment,
            int(protection_row[3]) + 1,
            scope_id,
        ),
    )


def _close_generation_authority(
    connection: sqlite3.Connection,
    *,
    generation_id: str,
    scope_id: int = 1,
) -> None:
    effects = connection.execute(
        "SELECT effect_id, lifecycle_state FROM venue_effect"
        " WHERE acquisition_generation_id = ? AND scope_id = ?"
        " AND disposition <> 'CLOSED' ORDER BY effect_id",
        (generation_id, scope_id),
    ).fetchall()
    for effect_id_raw, lifecycle_state_raw in effects:
        effect_id = int(effect_id_raw)
        lifecycle_state = str(lifecycle_state_raw)
        claim_row = connection.execute(
            "SELECT claim_id FROM dispatch_claim WHERE effect_id = ?",
            (effect_id,),
        ).fetchone()
        if claim_row is None:
            assert lifecycle_state == "REQUESTED"
            connection.execute(
                "UPDATE venue_effect"
                " SET lifecycle_state = 'CANCELED_BEFORE_DISPATCH'"
                " WHERE effect_id = ?",
                (effect_id,),
            )
            proof_kind = "NEVER_DISPATCHED"
            claim_id: int | None = None
        else:
            proof_kind = "CONTRACT_COMPLETE_RESPONSE"
            claim_id = int(claim_row[0])
        acceptance_row = connection.execute(
            "SELECT acceptance_set_id FROM acceptance_set WHERE effect_id = ?",
            (effect_id,),
        ).fetchone()
        if acceptance_row is None:
            acceptance_set_id = int(
                connection.execute(
                    "SELECT COALESCE(MAX(acceptance_set_id), 0) + 1 FROM acceptance_set"
                ).fetchone()[0]
            )
            connection.execute(
                "INSERT INTO acceptance_set VALUES (?, ?)",
                (acceptance_set_id, effect_id),
            )
        else:
            acceptance_set_id = int(acceptance_row[0])
        evidence_id = int(
            connection.execute(
                "SELECT COALESCE(MAX(evidence_id), 0) + 1 FROM acceptance_evidence"
            ).fetchone()[0]
        )
        evidence_ordinal = int(
            connection.execute(
                "SELECT COALESCE(MAX(evidence_ordinal), 0) + 1 FROM acceptance_evidence"
            ).fetchone()[0]
        )
        evidence_digest = f"{evidence_id:064x}"
        connection.execute(
            "INSERT INTO acceptance_evidence ("
            " evidence_id, acceptance_set_id, effect_id, evidence_kind,"
            " proof_kind, evidence_digest, evidence_ordinal"
            ") VALUES (?, ?, ?, 'CLOSURE_PROOF', ?, ?, ?)",
            (
                evidence_id,
                acceptance_set_id,
                effect_id,
                proof_kind,
                evidence_digest,
                evidence_ordinal,
            ),
        )
        connection.execute(
            "UPDATE venue_effect SET disposition = 'CLOSED',"
            " closure_proof_kind = ?, closure_proof_digest = ?,"
            " closure_proof_evidence_id = ?, closure_proof_claim_id = ?"
            " WHERE effect_id = ?",
            (
                proof_kind,
                evidence_digest,
                evidence_id,
                claim_id,
                effect_id,
            ),
        )

    protection_row = connection.execute(
        "SELECT expected_controller_head_ordinal, version_ordinal"
        " FROM protection_authority WHERE scope_id = ?"
        " AND active_acquisition_generation_id = ?",
        (scope_id, generation_id),
    ).fetchone()
    if protection_row is None:
        return
    controller_row = connection.execute(
        "SELECT currentness_head_ordinal FROM symbol_controller WHERE scope_id = ?",
        (scope_id,),
    ).fetchone()
    assert controller_row is not None
    next_version = int(protection_row[1]) + 1
    state_commitment = "ce" * 24 + f"{next_version:016x}"
    connection.execute(
        "UPDATE protection_authority SET authority_class = 'NORMAL',"
        " active_stream_generation_id = NULL,"
        " active_acquisition_generation_id = NULL,"
        " active_generation_mandate_commitment_sha256 = NULL,"
        " active_source_profile_id = NULL, active_session_external = NULL,"
        " active_sequence_mode = NULL, expected_controller_head_ordinal = ?,"
        " state_commitment_sha256 = ?, version_ordinal = ?"
        " WHERE scope_id = ?",
        (
            int(controller_row[0]),
            state_commitment,
            next_version,
            scope_id,
        ),
    )


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


def test_disabled_recursive_triggers_are_refused_before_ddl(tmp_path: object) -> None:
    connection = sqlite3.connect(tmp_path / "recursive-disabled.db")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA recursive_triggers = OFF")
    _OPEN_CONNECTIONS.append(connection)

    with pytest.raises(SchemaInstallError, match="recursive triggers"):
        install_schema(connection, approved_ddl_sha256=_require_gate_open())

    assert connection.execute("SELECT count(*) FROM sqlite_master").fetchone() == (0,)


def test_connection_verifier_refuses_an_uninstalled_temporary_database(
    tmp_path: object,
) -> None:
    connection = _connection(tmp_path)
    with pytest.raises(SchemaInstallError, match="exact installed schema identity"):
        verify_schema_connection(connection)


def test_connection_verifier_refuses_spoofed_metadata_without_exact_catalog(
    tmp_path: object,
) -> None:
    connection = _connection(tmp_path)
    connection.execute(
        "CREATE TABLE schema_meta (schema_version INTEGER, approved_ddl_sha256 TEXT)"
    )
    connection.execute(
        "INSERT INTO schema_meta VALUES (?, ?)",
        (SCHEMA_VERSION, schema_ddl_digest()),
    )

    with pytest.raises(SchemaInstallError, match="exact installed schema catalog"):
        verify_schema_connection(connection)


def test_connection_verifier_refuses_catalog_mutation_after_install(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    connection.execute("DROP TRIGGER trg_schema_meta_no_conflict_replace")

    with pytest.raises(SchemaInstallError, match="exact installed schema catalog"):
        verify_schema_connection(connection)


def test_install_failure_rolls_back_all_ddl_and_remains_retryable(
    tmp_path: object,
) -> None:
    connection = _connection(tmp_path)

    class _FailingConnection:
        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> object:
            if sql.startswith("CREATE TABLE venue_effect"):
                raise RuntimeError("injected DDL interruption")
            return connection.execute(sql, parameters)

    with pytest.raises(RuntimeError, match="injected DDL interruption"):
        install_schema(
            _FailingConnection(),
            approved_ddl_sha256=_require_gate_open(),
        )

    assert connection.execute("SELECT count(*) FROM sqlite_master").fetchone() == (0,)
    assert (
        install_schema(connection, approved_ddl_sha256=_require_gate_open())
        == SCHEMA_VERSION
    )


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
        "verify_schema_connection",
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
    """Source events dedupe inside one profile and remain profile-scoped."""

    connection = _installed_connection(tmp_path)
    generation_a = _insert_profiles_and_generation(connection)
    generation_b = _insert_second_profiles_and_generation(connection)
    connection.execute(
        """
        INSERT INTO acquisition_scope (
            scope_id, application_generation_id, execution_profile_id,
            symbol_text
        ) VALUES
        (1, ?, ?, 'AAPL'),
        (2, ?, ?, 'MSFT'),
        (3, ?, ?, 'AAPL')
        """,
        (
            generation_a,
            _DEFAULT_EXECUTION_PROFILE_ID,
            generation_a,
            _DEFAULT_EXECUTION_PROFILE_ID,
            generation_b,
            "67" * 32,
        ),
    )
    connection.execute(
        """
        INSERT INTO acquisition_generation VALUES
        (?, 1, 'LIVE', 1, NULL, ?, ?),
        (?, 2, 'LIVE', 1, NULL, ?, ?),
        (?, 3, 'LIVE', 1, NULL, ?, ?)
        """,
        (
            "12" * 32,
            "9a" * 32,
            "9b" * 32,
            "34" * 32,
            "8a" * 32,
            "8b" * 32,
            "45" * 32,
            "7a" * 32,
            "7b" * 32,
        ),
    )
    _insert_root(connection, key_id=1, scope_id=1, external="r-A")
    _insert_root(
        connection,
        key_id=2,
        scope_id=2,
        external="r-B",
        owner_generation_id="34" * 32,
    )
    _insert_root(
        connection,
        key_id=3,
        scope_id=3,
        external="r-C",
        application_generation_id=generation_b,
        execution_profile_id="67" * 32,
        owner_generation_id="45" * 32,
    )

    stored = _insert_fill(connection, fact_id=1, root_id=1, event="evt-1", scope_id=1)
    assert stored == 1

    # Same selected profile, different symbol scope: one source event remains
    # one execution fact and is rejected.
    with pytest.raises(sqlite3.IntegrityError):
        _insert_fill(
            connection,
            fact_id=2,
            root_id=2,
            event="evt-1",
            scope_id=2,
            generation_id=generation_a,
        )

    # The same provider text under a distinct immutable profile is a distinct
    # profile-scoped external identity and is accepted.
    assert (
        _insert_fill(
            connection,
            fact_id=3,
            root_id=3,
            event="evt-1",
            scope_id=3,
            generation_id=generation_b,
            execution_profile_id="67" * 32,
            fact_ordinal=2,
        )
        == 3
    )


def test_fact_coordinates_must_equal_their_scope_coordinates(
    tmp_path: object,
) -> None:
    """A fact row cannot silently carry coordinates foreign to its scope."""

    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection)

    with pytest.raises(sqlite3.IntegrityError, match="profile coordinates"):
        connection.execute(
            """
            INSERT INTO execution_fact (
                fact_id, scope_id, application_generation_id,
                execution_profile_id, root_fill_key_id, source_event_id,
                order_external, side, kind, authority, quantity,
                price_present, price_units, scale_sign, scale_digits,
                scale_exponent, tick_units, tick_scale_sign,
                tick_scale_digits, tick_scale_exponent,
                predecessor_fact_id, fact_ordinal
            )
            VALUES (?, 1, ?, ?, 1, 'evt-x', 'order-1', 'BUY', 'FILL',
                    'BROKER_AUTHORITATIVE', 10,
                    1, 10000, 0, '1', -2, 1, 0, '1', -2, NULL, 1)
            """,
            (1, _DEFAULT_GENERATION_ID, "67" * 32),
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
    with pytest.raises(sqlite3.IntegrityError, match="exact predecessor scope"):
        _insert_revision(
            connection,
            fact_id=9,
            root_id=root_a,
            event="evt-x",
            predecessor_fact_id=999,
            scope_id=scope_id,
            fact_ordinal=2,
        )

    # Cross-root mutant: predecessor exists but belongs to another root.
    root_b = _insert_root(connection, key_id=2, scope_id=scope_id, external="root-B")
    _insert_fill(
        connection, fact_id=2, root_id=root_b, event="evt-2", scope_id=scope_id
    )
    with pytest.raises(sqlite3.IntegrityError, match="exact predecessor scope"):
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
        fact_ordinal=3,
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
            fact_ordinal=4,
        )

    # Reusing an already-accounted ordinal would also move this root backward,
    # so the root-local monotonicity guard refuses it.
    with pytest.raises(sqlite3.IntegrityError, match="strictly advance"):
        _insert_revision(
            connection,
            fact_id=6,
            root_id=root_a,
            event="evt-6",
            predecessor_fact_id=4,
            scope_id=scope_id,
            fact_ordinal=3,
        )

    # A same-row predecessor must not satisfy SQLite's self-referential FK.
    with pytest.raises(sqlite3.IntegrityError, match="exact predecessor scope"):
        _insert_revision(
            connection,
            fact_id=8,
            root_id=root_a,
            event="evt-8",
            predecessor_fact_id=8,
            scope_id=scope_id,
            fact_ordinal=4,
        )

    # A root has exactly one canonical FILL fact.
    with pytest.raises(sqlite3.IntegrityError, match="root_fill_key_id"):
        _insert_fill(
            connection,
            fact_id=7,
            root_id=root_a,
            event="evt-7",
            scope_id=scope_id,
            fact_ordinal=4,
        )


def test_closure_chain_rejects_gap_branch_and_cross_owner(
    tmp_path: object,
) -> None:
    """Gap, branch, and cross-owner mutants fail on isolated fresh chains."""

    def _fresh(name: str) -> tuple[sqlite3.Connection, int]:
        connection = sqlite3.connect(tmp_path / name)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA recursive_triggers = ON")
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
            VALUES (?, ?, ?, ?, ?, 'TERMINAL_LEG', ?)
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
    with pytest.raises(
        sqlite3.IntegrityError, match="closure identity is already retained"
    ):
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
        ("UPDATE acquisition_root_route SET effect_id = effect_id + 1", ()),
        ("DELETE FROM acquisition_root_route", ()),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(statement, parameters)


def test_insert_or_replace_cannot_bypass_immutable_authority(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection)
    _insert_fill(connection, fact_id=1, root_id=1, event="evt-1")
    _insert_open_effect(connection, 1)
    _insert_claim(connection, claim_id=1, effect_id=1)

    statements = (
        ("INSERT OR REPLACE INTO execution_fact_head VALUES (1, 1, 1)", ()),
        (
            "INSERT OR REPLACE INTO dispatch_claim VALUES (1, 1, ?, 'claim-1', 1)",
            (_DEFAULT_EXECUTION_PROFILE_ID,),
        ),
        (
            "INSERT OR REPLACE INTO protection_authority"
            " SELECT * FROM protection_authority WHERE scope_id = 1",
            (),
        ),
        (
            "INSERT OR REPLACE INTO acquisition_generation"
            " SELECT * FROM acquisition_generation"
            " WHERE acquisition_generation_id = ?",
            ("12" * 32,),
        ),
        (
            "INSERT OR REPLACE INTO acquisition_generation_current"
            " SELECT * FROM acquisition_generation_current"
            " WHERE acquisition_generation_id = ?",
            ("12" * 32,),
        ),
        (
            "INSERT OR REPLACE INTO acquisition_root_route"
            " SELECT * FROM acquisition_root_route WHERE root_fill_key_id = 1",
            (),
        ),
    )
    for statement, parameters in statements:
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
    _insert_open_effect(connection, 2, root_id=2)
    connection.execute("INSERT INTO acceptance_set VALUES (1, 1)")

    with pytest.raises(sqlite3.IntegrityError, match="identity is immutable"):
        connection.execute(
            "UPDATE venue_effect"
            " SET side = 'SELL', disposition = 'INVALIDATED'"
            " WHERE effect_id = 1"
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
    _insert_open_effect(connection, 2, root_id=2)
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


# ---------------------------------------------------------------------------
# Fresh REV-0071 adversarial RED controls.


@pytest.mark.parametrize(
    ("order_external", "side"),
    (("other-order", "BUY"), ("order-1", "SELL")),
)
def test_revision_must_preserve_exact_root_order_and_side(
    tmp_path: object,
    order_external: str,
    side: str,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection)
    _insert_fill(connection, fact_id=1, root_id=1, event="scope-fill")

    with pytest.raises(sqlite3.IntegrityError, match="exact predecessor scope"):
        _insert_revision(
            connection,
            fact_id=2,
            root_id=1,
            event=f"scope-revision-{side}",
            predecessor_fact_id=1,
            order_external=order_external,
            side=side,
        )


def test_negative_broker_truth_is_retained_and_quarantined(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    generation_id = _insert_profiles_and_generation(connection)
    connection.execute(
        "INSERT INTO acquisition_scope VALUES (1, ?, ?, 'AAPL')",
        (generation_id, _DEFAULT_EXECUTION_PROFILE_ID),
    )
    connection.execute(
        "INSERT INTO acquisition_generation VALUES (?, 1, 'LIVE', 1, NULL, ?, ?)",
        ("12" * 32, "9a" * 32, "9b" * 32),
    )
    connection.execute(
        "INSERT INTO symbol_controller VALUES (1, ?, ?, ?, 0, 'CONSISTENT', 0, 1, ?)",
        (
            generation_id,
            _DEFAULT_EXECUTION_PROFILE_ID,
            "12" * 32,
            "9b" * 32,
        ),
    )
    _insert_root(connection)

    _insert_fill(
        connection,
        fact_id=1,
        root_id=1,
        event="negative-sell",
        side="SELL",
    )

    assert connection.execute("SELECT count(*) FROM execution_fact").fetchone() == (1,)
    assert connection.execute(
        "SELECT aggregate_quantity, integrity_state FROM symbol_controller"
    ).fetchone() == (-10, "NEGATIVE_POSITION_QUARANTINED")


def test_unmatched_broker_truth_is_retained_but_cannot_serve(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection)

    _insert_fill(
        connection,
        fact_id=1,
        root_id=1,
        event="unmatched-broker-fill",
        ensure_route=False,
    )

    assert connection.execute("SELECT count(*) FROM execution_fact").fetchone() == (1,)
    assert connection.execute(
        "SELECT current_fact_id, current_quantity FROM root_fill"
    ).fetchone() == (1, 10)
    assert connection.execute(
        "SELECT aggregate_quantity, integrity_state, currentness_head_ordinal"
        " FROM symbol_controller"
    ).fetchone() == (10, "UNMATCHED_LINEAGE_QUARANTINED", 1)
    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_open_effect(connection, 1, ensure_protection=False)
    with pytest.raises(sqlite3.IntegrityError, match="controller authority"):
        _insert_protection_authority(
            connection,
            state_commitment_sha256="98" * 32,
            version_ordinal=1,
        )


def test_live_effect_owner_cannot_rebind_a_retired_generation_root(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    successor_id = _retire_first_and_insert_live_successor(connection)
    _insert_controller(
        connection,
        acquisition_generation_id=successor_id,
    )
    _insert_root(connection, owner_generation_id="12" * 32)
    _insert_open_effect(
        connection,
        1,
        acquisition_generation_id=successor_id,
        generation_mandate_commitment_sha256="9c" * 32,
    )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        _insert_venue_owner(
            connection,
            owner_external="retired-root-owner",
            effect_id=1,
            owner_generation_id="12" * 32,
        )


def test_acquisition_route_cannot_borrow_another_roots_owner_proof(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection, key_id=1, external="root-a")
    _insert_root(connection, key_id=2, external="root-b")
    _ensure_acquisition_root_route(connection, root_id=1)
    route = connection.execute(
        "SELECT effect_id, owner_external, observation_external"
        " FROM acquisition_root_route WHERE root_fill_key_id = 1"
    ).fetchone()
    assert route is not None

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        connection.execute(
            "INSERT INTO acquisition_root_route VALUES (?, 1, ?, ?, ?, ?, ?, ?)",
            (
                2,
                _DEFAULT_GENERATION_ID,
                _DEFAULT_EXECUTION_PROFILE_ID,
                "12" * 32,
                *route,
            ),
        )


def test_requested_effect_is_rootless_and_preserves_complete_scope(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)

    _ensure_normal_protection(
        connection,
        seed=1,
        scope_id=1,
        application_generation_id=_DEFAULT_GENERATION_ID,
        acquisition_generation_id="12" * 32,
        generation_mandate_commitment_sha256="9a" * 32,
        expected_controller_head_ordinal=0,
    )

    connection.execute(
        """
        INSERT INTO venue_effect (
            effect_id, effect_external, scope_id, application_generation_id,
            execution_profile_id, acquisition_generation_id,
            generation_mandate_commitment_sha256,
            expected_controller_head_ordinal,
            expected_protection_version_ordinal, authority_class,
            request_occurrence_external, mandate_external, effect_kind,
            client_order_external, target_order_external, side, quantity,
            economic_scope, lifecycle_state, disposition, created_ordinal
        ) VALUES (
            1, 'effect-1', 1, ?, ?, ?, ?, 0, 1, 'NORMAL',
            'request-1', 'mandate-1',
            'SUBMIT', 'client-1', NULL, 'BUY', 10, x'0102',
            'REQUESTED', 'OPEN', 1
        )
        """,
        (
            _DEFAULT_GENERATION_ID,
            _DEFAULT_EXECUTION_PROFILE_ID,
            "12" * 32,
            "9a" * 32,
        ),
    )
    assert connection.execute(
        "SELECT request_occurrence_external, mandate_external, effect_kind,"
        " client_order_external, target_order_external, side, quantity,"
        " economic_scope FROM venue_effect WHERE effect_id = 1"
    ).fetchone() == (
        "request-1",
        "mandate-1",
        "SUBMIT",
        "client-1",
        None,
        "BUY",
        10,
        b"\x01\x02",
    )


def test_invalidation_evidence_atomically_invalidates_closed_effect(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection)
    _insert_open_effect(connection, 1)
    _insert_venue_owner(connection, owner_external="owner-1", effect_id=1)
    connection.execute("INSERT INTO acceptance_set VALUES (1, 1)")
    _insert_claim(connection, claim_id=1, effect_id=1)
    connection.execute(
        "INSERT INTO acceptance_evidence VALUES"
        " (1, 1, 1, 'CLOSURE_PROOF', 'CONTRACT_COMPLETE_RESPONSE', ?, 1,"
        " NULL, NULL)",
        ("91" * 32,),
    )
    connection.execute(
        "UPDATE venue_effect SET disposition = 'CLOSED',"
        " closure_proof_kind = 'CONTRACT_COMPLETE_RESPONSE',"
        " closure_proof_digest = ?, closure_proof_evidence_id = 1,"
        " closure_proof_claim_id = 1 WHERE effect_id = 1",
        ("91" * 32,),
    )

    with pytest.raises(sqlite3.IntegrityError, match="acceptance transition"):
        connection.execute(
            "UPDATE venue_effect SET disposition = 'INVALIDATED' WHERE effect_id = 1"
        )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO acceptance_evidence VALUES"
            " (2, 1, 1, 'INVALIDATION', NULL, ?, 2, 'owner-1',"
            " 'wrong-observation')",
            ("92" * 32,),
        )
    connection.execute(
        "INSERT INTO acceptance_evidence VALUES"
        " (3, 1, 1, 'INVALIDATION', NULL, ?, 3, 'owner-1',"
        " 'observation-owner-1')",
        ("93" * 32,),
    )
    assert connection.execute(
        "SELECT disposition FROM venue_effect WHERE effect_id = 1"
    ).fetchone() == ("INVALIDATED",)
    assert connection.execute(
        "SELECT closure_id, owner_external, ordinal, effect_id, closure_kind,"
        " predecessor_closure_id FROM closure_chain"
    ).fetchone() == (-3, "owner-1", 1, 1, "INVALIDATED_TERMINAL", None)

    with pytest.raises(sqlite3.IntegrityError, match="canonical effect authority"):
        connection.execute(
            "INSERT INTO closure_chain VALUES"
            " (4, 1, 'owner-1', 2, 1, 'ACCEPTANCE_CLOSED', -3)"
        )


def test_effect_creation_and_dispatch_claim_require_current_controller_head(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_open_effect(connection, 1, expected_controller_head_ordinal=0)
    _insert_root(connection)
    _insert_fill(connection, fact_id=1, root_id=1, event="controller-advance")

    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_claim(connection, claim_id=1, effect_id=1)
    assert connection.execute(
        "SELECT count(*) FROM dispatch_claim WHERE effect_id = 1"
    ).fetchone() == (0,)
    assert connection.execute(
        "SELECT lifecycle_state FROM venue_effect WHERE effect_id = 1"
    ).fetchone() == ("REQUESTED",)

    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_open_effect(
            connection,
            2,
            expected_controller_head_ordinal=0,
            ensure_protection=False,
        )

    _insert_open_effect(connection, 3, expected_controller_head_ordinal=1)
    assert _insert_claim(connection, claim_id=2, effect_id=3) == 2


def test_owner_identity_cannot_rebind_across_scopes_in_one_profile(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    connection.execute(
        "INSERT INTO acquisition_scope VALUES (2, ?, ?, 'MSFT')",
        (_DEFAULT_GENERATION_ID, _DEFAULT_EXECUTION_PROFILE_ID),
    )
    connection.execute(
        "INSERT INTO acquisition_generation VALUES (?, 2, 'LIVE', 1, NULL, ?, ?)",
        ("34" * 32, "9c" * 32, "9b" * 32),
    )
    _insert_root(connection, key_id=1, scope_id=1, external="root-a")
    _insert_root(
        connection,
        key_id=2,
        scope_id=2,
        external="root-b",
        owner_generation_id="34" * 32,
    )
    _insert_open_effect(connection, 1, root_id=1, scope_id=1)
    _insert_open_effect(
        connection,
        2,
        root_id=2,
        scope_id=2,
        acquisition_generation_id="34" * 32,
        generation_mandate_commitment_sha256="9c" * 32,
    )
    _insert_venue_owner(connection, owner_external="broker-order", effect_id=1)

    with pytest.raises(sqlite3.IntegrityError):
        _insert_venue_owner(
            connection,
            owner_external="broker-order",
            effect_id=2,
            root_id=2,
            scope_id=2,
            owner_generation_id="34" * 32,
        )


def test_nonflat_protection_stream_cannot_be_transferred(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    generation_id = _insert_profiles_and_generation(connection)
    connection.execute(
        "INSERT INTO acquisition_scope VALUES (1, ?, ?, 'AAPL')",
        (generation_id, _DEFAULT_EXECUTION_PROFILE_ID),
    )
    connection.execute(
        "INSERT INTO acquisition_generation VALUES (?, 1, 'LIVE', 1, NULL, ?, ?)",
        ("12" * 32, "9a" * 32, "9b" * 32),
    )
    connection.execute(
        "INSERT INTO symbol_controller VALUES (1, ?, ?, ?, 0, 'CONSISTENT', 0, 1, ?)",
        (generation_id, _DEFAULT_EXECUTION_PROFILE_ID, "12" * 32, "9b" * 32),
    )
    _insert_root(connection)
    for stream_id in ("81" * 32, "82" * 32):
        _insert_market_stream(
            connection,
            stream_generation_id=stream_id,
            application_generation_id=generation_id,
        )
    _insert_protection_authority(
        connection,
        stream_generation_id="81" * 32,
        state_commitment_sha256="93" * 32,
        version_ordinal=1,
    )
    _insert_fill(connection, fact_id=1, root_id=1, event="positive-fill")

    with pytest.raises(sqlite3.IntegrityError, match="nonflat"):
        connection.execute(
            "UPDATE protection_authority SET active_stream_generation_id = ?,"
            " expected_controller_head_ordinal = 1,"
            " state_commitment_sha256 = ?, version_ordinal = 2 WHERE scope_id = 1",
            ("82" * 32, "94" * 32),
        )


def test_sticky_quarantine_refuses_flat_protection_transfer(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection)
    for stream_id in ("81" * 32, "82" * 32):
        _insert_market_stream(connection, stream_generation_id=stream_id)
    _insert_protection_authority(
        connection,
        stream_generation_id="81" * 32,
        state_commitment_sha256="93" * 32,
        version_ordinal=1,
    )

    _insert_fill(
        connection,
        fact_id=1,
        root_id=1,
        event="negative-fill",
        side="SELL",
    )
    _insert_bust(
        connection,
        fact_id=2,
        root_id=1,
        event="negative-fill-bust",
        predecessor_fact_id=1,
        side="SELL",
    )
    assert connection.execute(
        "SELECT aggregate_quantity, integrity_state FROM symbol_controller"
    ).fetchone() == (0, "NEGATIVE_POSITION_QUARANTINED")

    with pytest.raises(sqlite3.IntegrityError, match="controller authority"):
        connection.execute(
            "UPDATE protection_authority SET active_stream_generation_id = ?,"
            " state_commitment_sha256 = ?, version_ordinal = 2 WHERE scope_id = 1",
            ("82" * 32, "94" * 32),
        )
    with pytest.raises(sqlite3.IntegrityError, match="controller authority"):
        connection.execute(
            "UPDATE protection_authority"
            " SET expected_controller_head_ordinal = 2,"
            " state_commitment_sha256 = ?, version_ordinal = 2"
            " WHERE scope_id = 1",
            ("94" * 32,),
        )


def test_quarantined_controller_refuses_new_protection_authority(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_open_effect(connection, 1)
    _insert_root(connection)
    _insert_fill(
        connection,
        fact_id=1,
        root_id=1,
        event="negative-fill",
        side="SELL",
    )

    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_claim(connection, claim_id=1, effect_id=1)
    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_open_effect(connection, 2, ensure_protection=False)
    with pytest.raises(sqlite3.IntegrityError, match="controller authority"):
        connection.execute(
            "UPDATE protection_authority"
            " SET expected_controller_head_ordinal = 1,"
            " state_commitment_sha256 = ?, version_ordinal = 2",
            ("95" * 32,),
        )


def test_protection_authority_requires_the_exact_live_generation(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    successor_id = _retire_first_and_insert_live_successor(connection)
    _insert_controller(
        connection,
        acquisition_generation_id=successor_id,
    )
    retired_stream = "81" * 32
    live_stream = "82" * 32
    _insert_market_stream(
        connection,
        stream_generation_id=retired_stream,
        acquisition_generation_id="12" * 32,
    )
    _insert_market_stream(
        connection,
        stream_generation_id=live_stream,
        acquisition_generation_id=successor_id,
        generation_mandate_commitment_sha256="9c" * 32,
    )

    with pytest.raises(sqlite3.IntegrityError, match="controller authority"):
        _insert_protection_authority(
            connection,
            stream_generation_id=retired_stream,
            acquisition_generation_id="12" * 32,
            state_commitment_sha256="99" * 32,
            version_ordinal=1,
        )
    assert (
        _insert_protection_authority(
            connection,
            stream_generation_id=live_stream,
            acquisition_generation_id=successor_id,
            generation_mandate_commitment_sha256="9c" * 32,
            state_commitment_sha256="9a" * 32,
            version_ordinal=1,
        )
        == 1
    )


def test_retired_fact_enters_mixed_recovery_and_only_hard_bail_may_serve(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection)
    _ensure_acquisition_root_route(connection, root_id=1)
    _close_generation_authority(connection, generation_id="12" * 32)
    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = NULL,"
        " currentness_head_ordinal = 1, controller_version_ordinal = 2"
    )
    successor_id = _retire_first_and_insert_live_successor(connection)
    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = ?,"
        " currentness_head_ordinal = 2, controller_version_ordinal = 3",
        (successor_id,),
    )
    successor_stream_id = "82" * 32
    _insert_market_stream(
        connection,
        stream_generation_id=successor_stream_id,
        acquisition_generation_id=successor_id,
        generation_mandate_commitment_sha256="9c" * 32,
    )
    _ensure_normal_protection(
        connection,
        seed=2,
        scope_id=1,
        application_generation_id=_DEFAULT_GENERATION_ID,
        acquisition_generation_id=successor_id,
        generation_mandate_commitment_sha256="9c" * 32,
        expected_controller_head_ordinal=2,
    )
    _insert_open_effect(
        connection,
        2,
        acquisition_generation_id=successor_id,
        generation_mandate_commitment_sha256="9c" * 32,
    )

    _insert_fill(
        connection,
        fact_id=1,
        root_id=1,
        event="late-retired-fill",
    )
    assert connection.execute(
        "SELECT aggregate_quantity, integrity_state, currentness_head_ordinal"
        " FROM symbol_controller"
    ).fetchone() == (10, "MIXED_GENERATION_RECOVERY", 3)

    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_open_effect(
            connection,
            3,
            acquisition_generation_id=successor_id,
            generation_mandate_commitment_sha256="9c" * 32,
            ensure_protection=False,
        )
    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_claim(connection, claim_id=1, effect_id=2)
    with pytest.raises(sqlite3.IntegrityError, match="controller authority"):
        connection.execute(
            "UPDATE protection_authority"
            " SET expected_controller_head_ordinal = 3,"
            " state_commitment_sha256 = ?, version_ordinal = 4",
            ("a2" * 32,),
        )

    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_open_effect(
            connection,
            4,
            acquisition_generation_id=successor_id,
            generation_mandate_commitment_sha256="9c" * 32,
            authority_class="HARD_BAIL",
            side="SELL",
        )

    connection.execute(
        "UPDATE protection_authority"
        " SET authority_class = 'HARD_BAIL',"
        " expected_controller_head_ordinal = 3,"
        " state_commitment_sha256 = ?, version_ordinal = 4",
        ("a3" * 32,),
    )
    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_open_effect(
            connection,
            5,
            acquisition_generation_id=successor_id,
            generation_mandate_commitment_sha256="9c" * 32,
            authority_class="HARD_BAIL",
            side="SELL",
            quantity=11,
        )
    _insert_open_effect(
        connection,
        6,
        acquisition_generation_id=successor_id,
        generation_mandate_commitment_sha256="9c" * 32,
        authority_class="HARD_BAIL",
        side="SELL",
    )
    assert _insert_claim(connection, claim_id=2, effect_id=6) == 2
    with pytest.raises(sqlite3.IntegrityError):
        _insert_open_effect(
            connection,
            7,
            acquisition_generation_id=successor_id,
            generation_mandate_commitment_sha256="9c" * 32,
            authority_class="HARD_BAIL",
            side="SELL",
        )

    _insert_root(
        connection,
        key_id=2,
        external="hard-bail-root",
        owner_generation_id=successor_id,
    )
    _insert_venue_owner(
        connection,
        owner_external="hard-bail-owner",
        observation_external="hard-bail-observation",
        effect_id=6,
        root_id=2,
        owner_generation_id=successor_id,
    )
    connection.execute(
        "INSERT INTO acquisition_root_route VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            2,
            1,
            _DEFAULT_GENERATION_ID,
            _DEFAULT_EXECUTION_PROFILE_ID,
            successor_id,
            6,
            "hard-bail-owner",
            "hard-bail-observation",
        ),
    )
    _insert_fill(
        connection,
        fact_id=2,
        root_id=2,
        event="hard-bail-flat-fill",
        side="SELL",
        ensure_route=False,
    )
    assert connection.execute(
        "SELECT aggregate_quantity, integrity_state, currentness_head_ordinal,"
        " controller_version_ordinal FROM symbol_controller"
    ).fetchone() == (0, "CONSISTENT", 4, 5)
    _close_generation_authority(connection, generation_id=successor_id)
    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = NULL,"
        " currentness_head_ordinal = 5, controller_version_ordinal = 6"
    )


def test_negative_quarantine_overrides_retired_lineage_mixed_recovery(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection)
    _insert_root(connection, key_id=2, external="root-fill-B")
    _insert_root(connection, key_id=3, external="root-fill-C")
    _ensure_acquisition_root_route(connection, root_id=1)
    _ensure_acquisition_root_route(connection, root_id=2)
    _ensure_acquisition_root_route(connection, root_id=3)
    _close_generation_authority(connection, generation_id="12" * 32)
    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = NULL,"
        " currentness_head_ordinal = 1, controller_version_ordinal = 2"
    )
    successor_id = _retire_first_and_insert_live_successor(connection)
    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = ?,"
        " currentness_head_ordinal = 2, controller_version_ordinal = 3",
        (successor_id,),
    )

    _insert_fill(connection, fact_id=1, root_id=1, event="late-retired-fill")
    assert connection.execute(
        "SELECT aggregate_quantity, integrity_state FROM symbol_controller"
    ).fetchone() == (10, "MIXED_GENERATION_RECOVERY")

    _insert_fill(
        connection,
        fact_id=2,
        root_id=2,
        event="late-retired-sell-1",
        side="SELL",
    )
    _insert_fill(
        connection,
        fact_id=3,
        root_id=3,
        event="late-retired-sell-2",
        side="SELL",
    )
    assert connection.execute(
        "SELECT aggregate_quantity, integrity_state, currentness_head_ordinal"
        " FROM symbol_controller"
    ).fetchone() == (-10, "NEGATIVE_POSITION_QUARANTINED", 5)

    with pytest.raises(sqlite3.IntegrityError, match="controller authority"):
        connection.execute(
            "UPDATE protection_authority"
            " SET authority_class = 'HARD_BAIL',"
            " expected_controller_head_ordinal = 5,"
            " state_commitment_sha256 = ?, version_ordinal = 2",
            ("a4" * 32,),
        )
    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_open_effect(
            connection,
            8,
            acquisition_generation_id=successor_id,
            generation_mandate_commitment_sha256="9c" * 32,
            authority_class="HARD_BAIL",
            side="SELL",
        )


def test_retired_exact_noop_revision_does_not_stale_live_generation_authority(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection)
    _ensure_acquisition_root_route(connection, root_id=1)
    _insert_fill(connection, fact_id=1, root_id=1, event="live-fill")
    _insert_bust(
        connection,
        fact_id=2,
        root_id=1,
        event="live-bust",
        predecessor_fact_id=1,
    )
    assert connection.execute(
        "SELECT aggregate_quantity, integrity_state, currentness_head_ordinal,"
        " controller_version_ordinal FROM symbol_controller"
    ).fetchone() == (0, "CONSISTENT", 2, 3)

    _close_generation_authority(connection, generation_id="12" * 32)
    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = NULL,"
        " currentness_head_ordinal = 3, controller_version_ordinal = 4"
    )
    successor_id = _retire_first_and_insert_live_successor(connection)
    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = ?,"
        " currentness_head_ordinal = 4, controller_version_ordinal = 5",
        (successor_id,),
    )
    _insert_open_effect(
        connection,
        9,
        acquisition_generation_id=successor_id,
        generation_mandate_commitment_sha256="9c" * 32,
    )

    _insert_bust(
        connection,
        fact_id=3,
        root_id=1,
        event="late-retired-noop-bust",
        predecessor_fact_id=2,
    )
    assert connection.execute(
        "SELECT aggregate_quantity, integrity_state, currentness_head_ordinal,"
        " controller_version_ordinal FROM symbol_controller"
    ).fetchone() == (0, "CONSISTENT", 4, 5)
    assert connection.execute(
        "SELECT current_fact_id, economics_head_ordinal FROM root_fill"
    ).fetchone() == (3, 3)
    assert _insert_claim(connection, claim_id=3, effect_id=9) == 3


def test_nonflat_controller_cannot_unbind_or_replace_its_live_generation(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection)
    _insert_fill(connection, fact_id=1, root_id=1, event="positive-live-fill")

    with pytest.raises(
        sqlite3.IntegrityError, match="flat consistent closed authority"
    ):
        connection.execute(
            "UPDATE symbol_controller"
            " SET live_acquisition_generation_id = NULL,"
            " currentness_head_ordinal = 2, controller_version_ordinal = 3"
        )


def test_unresolved_generation_authority_blocks_serial_successor_until_closed(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection)
    _insert_open_effect(connection, 1)
    _insert_venue_owner(
        connection,
        owner_external="old-owner",
        effect_id=1,
    )
    _insert_claim(connection, claim_id=1, effect_id=1)
    assert connection.execute(
        "SELECT unresolved_effect_count, active_protection_count"
        " FROM acquisition_generation_current"
        " WHERE acquisition_generation_id = ?",
        ("12" * 32,),
    ).fetchone() == (1, 1)

    with pytest.raises(sqlite3.IntegrityError, match="closed authority"):
        connection.execute(
            "UPDATE symbol_controller"
            " SET live_acquisition_generation_id = NULL,"
            " currentness_head_ordinal = 1, controller_version_ordinal = 2"
        )
    with pytest.raises(sqlite3.IntegrityError, match="closed effects"):
        connection.execute(
            "UPDATE acquisition_generation SET status = 'RETIRED_UNSERVING'"
            " WHERE acquisition_generation_id = ?",
            ("12" * 32,),
        )

    _close_generation_authority(connection, generation_id="12" * 32)
    assert connection.execute(
        "SELECT unresolved_effect_count, active_protection_count"
        " FROM acquisition_generation_current"
        " WHERE acquisition_generation_id = ?",
        ("12" * 32,),
    ).fetchone() == (0, 0)
    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = NULL,"
        " currentness_head_ordinal = 1, controller_version_ordinal = 2"
    )
    successor_id = _retire_first_and_insert_live_successor(connection)
    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = ?,"
        " currentness_head_ordinal = 2, controller_version_ordinal = 3",
        (successor_id,),
    )
    _insert_open_effect(
        connection,
        2,
        acquisition_generation_id=successor_id,
        generation_mandate_commitment_sha256="9c" * 32,
    )
    old_acceptance_set_id = int(
        connection.execute(
            "SELECT acceptance_set_id FROM acceptance_set WHERE effect_id = 1"
        ).fetchone()[0]
    )
    connection.execute(
        "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
        " effect_id, evidence_kind, proof_kind, evidence_digest, evidence_ordinal,"
        " contradiction_owner_external, contradiction_observation_external)"
        " VALUES (99, ?, 1, 'INVALIDATION', NULL, ?, 2, ?, ?)",
        (
            old_acceptance_set_id,
            "a6" * 32,
            "old-owner",
            "observation-old-owner",
        ),
    )
    assert connection.execute(
        "SELECT integrity_state, currentness_head_ordinal FROM symbol_controller"
    ).fetchone() == ("UNRESOLVED_VENUE_QUARANTINED", 3)
    assert connection.execute(
        "SELECT unresolved_effect_count FROM acquisition_generation_current"
        " WHERE acquisition_generation_id = ?",
        ("12" * 32,),
    ).fetchone() == (1,)
    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_claim(connection, claim_id=2, effect_id=2)


def test_post_closure_owner_atomically_quarantines_serial_successor(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection)
    _insert_open_effect(connection, 1)
    _insert_venue_owner(connection, owner_external="known-owner", effect_id=1)
    _insert_claim(connection, claim_id=1, effect_id=1)
    _close_generation_authority(connection, generation_id="12" * 32)
    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = NULL,"
        " currentness_head_ordinal = 1, controller_version_ordinal = 2"
    )
    successor_id = _retire_first_and_insert_live_successor(connection)
    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = ?,"
        " currentness_head_ordinal = 2, controller_version_ordinal = 3",
        (successor_id,),
    )
    _insert_open_effect(
        connection,
        2,
        acquisition_generation_id=successor_id,
        generation_mandate_commitment_sha256="9c" * 32,
    )

    with pytest.raises(sqlite3.IntegrityError, match="exact canonical effect state"):
        connection.execute(
            "INSERT INTO venue_identity_owner (scope_id, execution_profile_id,"
            " owner_external, observation_external, effect_id, root_fill_key_id,"
            " owner_generation_id, admitted_after_effect_closed)"
            " VALUES (1, ?, 'misclassified-late-owner',"
            " 'misclassified-late-observation', 1, 1, ?, 0)",
            (_DEFAULT_EXECUTION_PROFILE_ID, "12" * 32),
        )
    _insert_venue_owner(
        connection,
        owner_external="late-owner-1",
        effect_id=1,
    )
    _insert_venue_owner(
        connection,
        owner_external="late-owner-2",
        effect_id=1,
    )

    assert connection.execute(
        "SELECT unresolved_effect_count FROM acquisition_generation_current"
        " WHERE acquisition_generation_id = ?",
        ("12" * 32,),
    ).fetchone() == (1,)
    assert connection.execute(
        "SELECT integrity_state, currentness_head_ordinal,"
        " controller_version_ordinal FROM symbol_controller"
    ).fetchone() == ("UNRESOLVED_VENUE_QUARANTINED", 4, 5)
    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_claim(connection, claim_id=2, effect_id=2)

    for closure_id, closure_kind in (
        (10, "TERMINAL_LEG"),
        (11, "ACCEPTANCE_CLOSED"),
    ):
        with pytest.raises(sqlite3.IntegrityError, match="invalidation evidence"):
            connection.execute(
                "INSERT INTO closure_chain VALUES"
                " (?, 1, 'late-owner-1', 1, 1, ?, NULL)",
                (closure_id, closure_kind),
            )

    acceptance_set_id = int(
        connection.execute(
            "SELECT acceptance_set_id FROM acceptance_set WHERE effect_id = 1"
        ).fetchone()[0]
    )
    connection.execute(
        "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
        " effect_id, evidence_kind, proof_kind, evidence_digest, evidence_ordinal,"
        " contradiction_owner_external, contradiction_observation_external)"
        " VALUES (99, ?, 1, 'INVALIDATION', NULL, ?, 2, 'late-owner-1',"
        " 'observation-late-owner-1')",
        (acceptance_set_id, "a6" * 32),
    )
    assert connection.execute(
        "SELECT disposition FROM venue_effect WHERE effect_id = 1"
    ).fetchone() == ("INVALIDATED",)

    with pytest.raises(sqlite3.IntegrityError, match="canonical effect authority"):
        connection.execute(
            "INSERT INTO closure_chain VALUES"
            " (-1000, 1, 'late-owner-2', 1, 1, 'INVALIDATED_TERMINAL', NULL)"
        )
    with pytest.raises(sqlite3.IntegrityError, match="exact canonical effect state"):
        connection.execute(
            "INSERT INTO venue_identity_owner (scope_id, execution_profile_id,"
            " owner_external, observation_external, effect_id, root_fill_key_id,"
            " owner_generation_id, admitted_after_effect_closed)"
            " VALUES (1, ?, 'misclassified-invalidated-owner',"
            " 'misclassified-invalidated-observation', 1, 1, ?, 0)",
            (_DEFAULT_EXECUTION_PROFILE_ID, "12" * 32),
        )
    _insert_venue_owner(
        connection,
        owner_external="late-owner-3",
        effect_id=1,
    )

    for evidence_id, evidence_ordinal, owner in (
        (100, 3, "late-owner-2"),
        (101, 4, "late-owner-3"),
    ):
        connection.execute(
            "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
            " effect_id, evidence_kind, proof_kind, evidence_digest,"
            " evidence_ordinal, contradiction_owner_external,"
            " contradiction_observation_external)"
            " VALUES (?, ?, 1, 'INVALIDATION', NULL, ?, ?, ?, ?)",
            (
                evidence_id,
                acceptance_set_id,
                f"{evidence_id:064x}",
                evidence_ordinal,
                owner,
                f"observation-{owner}",
            ),
        )

    with pytest.raises(sqlite3.IntegrityError, match="identity is already retained"):
        connection.execute(
            "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
            " effect_id, evidence_kind, proof_kind, evidence_digest,"
            " evidence_ordinal, contradiction_owner_external,"
            " contradiction_observation_external)"
            " VALUES (102, ?, 1, 'INVALIDATION', NULL, ?, 5, 'late-owner-1',"
            " 'observation-late-owner-1')",
            (acceptance_set_id, "a7" * 32),
        )

    assert connection.execute(
        "SELECT closure_id, owner_external, closure_kind FROM closure_chain"
        " WHERE effect_id = 1 AND owner_external LIKE 'late-owner-%'"
        " ORDER BY owner_external"
    ).fetchall() == [
        (-99, "late-owner-1", "INVALIDATED_TERMINAL"),
        (-100, "late-owner-2", "INVALIDATED_TERMINAL"),
        (-101, "late-owner-3", "INVALIDATED_TERMINAL"),
    ]
    assert connection.execute(
        "SELECT unresolved_effect_count FROM acquisition_generation_current"
        " WHERE acquisition_generation_id = ?",
        ("12" * 32,),
    ).fetchone() == (1,)
    assert connection.execute(
        "SELECT integrity_state, currentness_head_ordinal,"
        " controller_version_ordinal FROM symbol_controller"
    ).fetchone() == ("UNRESOLVED_VENUE_QUARANTINED", 6, 7)


def test_normal_effect_and_claim_require_current_normal_protection(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)

    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_open_effect(connection, 1, ensure_protection=False)

    _insert_open_effect(connection, 2)
    connection.execute(
        "UPDATE protection_authority SET state_commitment_sha256 = ?,"
        " version_ordinal = 2",
        ("a5" * 32,),
    )
    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_claim(connection, claim_id=1, effect_id=2)

    _insert_open_effect(connection, 3)
    connection.execute(
        "UPDATE protection_authority SET active_stream_generation_id = NULL,"
        " active_acquisition_generation_id = NULL,"
        " active_generation_mandate_commitment_sha256 = NULL,"
        " active_source_profile_id = NULL, active_session_external = NULL,"
        " active_sequence_mode = NULL, state_commitment_sha256 = ?,"
        " version_ordinal = 3",
        ("a7" * 32,),
    )
    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_claim(connection, claim_id=2, effect_id=3)


def test_one_effect_retains_multiple_concrete_acceptance_owners(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection)
    _insert_open_effect(connection, 1)
    _insert_venue_owner(connection, owner_external="owner-1", effect_id=1)
    _insert_venue_owner(connection, owner_external="owner-2", effect_id=1)
    connection.execute(
        "INSERT INTO closure_chain VALUES (1, 1, 'owner-1', 1, 1, 'TERMINAL_LEG', NULL)"
    )
    connection.execute(
        "INSERT INTO closure_chain VALUES (2, 1, 'owner-2', 1, 1, 'TERMINAL_LEG', NULL)"
    )
    assert connection.execute(
        "SELECT owner_external FROM venue_identity_owner"
        " WHERE effect_id = 1 ORDER BY owner_external"
    ).fetchall() == [("owner-1",), ("owner-2",)]


def test_initial_negative_aggregate_outranks_missing_lineage(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection)
    _insert_fill(
        connection,
        fact_id=1,
        root_id=1,
        event="pre-controller-negative",
        side="SELL",
        ensure_route=False,
    )
    _insert_controller(
        connection,
        aggregate_quantity=-10,
        integrity_state="NEGATIVE_POSITION_QUARANTINED",
    )
    assert connection.execute(
        "SELECT aggregate_quantity, integrity_state FROM symbol_controller"
    ).fetchone() == (-10, "NEGATIVE_POSITION_QUARANTINED")


def test_unmatched_lineage_prevents_mixed_recovery_flat_release(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection)
    _ensure_acquisition_root_route(connection, root_id=1)
    _close_generation_authority(connection, generation_id="12" * 32)
    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = NULL,"
        " currentness_head_ordinal = 1, controller_version_ordinal = 2"
    )
    successor_id = _retire_first_and_insert_live_successor(connection)
    connection.execute(
        "UPDATE symbol_controller"
        " SET live_acquisition_generation_id = ?,"
        " currentness_head_ordinal = 2, controller_version_ordinal = 3",
        (successor_id,),
    )
    _insert_root(
        connection,
        key_id=2,
        external="unmatched-live-buy",
        owner_generation_id=successor_id,
    )
    for key_id in (3, 4):
        _insert_root(
            connection,
            key_id=key_id,
            external=f"routed-live-sell-{key_id}",
            owner_generation_id=successor_id,
        )
        _ensure_acquisition_root_route(connection, root_id=key_id)

    _insert_fill(connection, fact_id=1, root_id=1, event="late-retired-buy")
    _insert_fill(
        connection,
        fact_id=2,
        root_id=2,
        event="unmatched-live-buy",
        ensure_route=False,
    )
    for fact_id, root_id in ((3, 3), (4, 4)):
        _insert_fill(
            connection,
            fact_id=fact_id,
            root_id=root_id,
            event=f"routed-live-sell-{root_id}",
            side="SELL",
            ensure_route=False,
        )
    assert connection.execute(
        "SELECT aggregate_quantity, integrity_state FROM symbol_controller"
    ).fetchone() == (0, "UNMATCHED_LINEAGE_QUARANTINED")
    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_open_effect(connection, 5, ensure_protection=False)


def test_protection_versions_are_scope_local(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    _seed_two_scopes(connection)
    _insert_controller(connection)
    _insert_controller(
        connection,
        scope_id=2,
        application_generation_id="56" * 32,
        execution_profile_id="67" * 32,
        acquisition_generation_id="34" * 32,
        emergency_compatibility_sha256="8b" * 32,
    )

    assert (
        _insert_protection_authority(
            connection,
            scope_id=1,
            state_commitment_sha256="96" * 32,
            version_ordinal=1,
        )
        == 1
    )
    assert (
        _insert_protection_authority(
            connection,
            scope_id=2,
            state_commitment_sha256="97" * 32,
            version_ordinal=1,
        )
        == 2
    )


def test_reopened_default_connection_cannot_replace_direct_authority(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_protection_authority(
        connection,
        state_commitment_sha256="95" * 32,
        version_ordinal=5,
    )
    connection.commit()
    connection.close()
    _OPEN_CONNECTIONS.remove(connection)

    reopened = sqlite3.connect(tmp_path / "m2-i2-gate.db")  # type: ignore[operator]
    _OPEN_CONNECTIONS.append(reopened)
    assert reopened.execute("PRAGMA foreign_keys").fetchone() == (0,)
    assert reopened.execute("PRAGMA recursive_triggers").fetchone() == (0,)
    with pytest.raises(sqlite3.IntegrityError, match="metadata is already retained"):
        reopened.execute(
            "INSERT OR REPLACE INTO schema_meta VALUES (1, ?)",
            ("00" * 32,),
        )
    reopened.rollback()
    with pytest.raises(SchemaForeignKeysDisabledError):
        verify_schema_connection(reopened)
    reopened.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(SchemaInstallError, match="recursive triggers"):
        verify_schema_connection(reopened)
    reopened.execute("PRAGMA recursive_triggers = ON")
    assert verify_schema_connection(reopened) == SCHEMA_VERSION
    with pytest.raises(sqlite3.IntegrityError):
        reopened.execute(
            "INSERT OR REPLACE INTO protection_authority VALUES"
            " (1, 'NORMAL', NULL, NULL, NULL, NULL, NULL, NULL, 0, ?, 1)",
            ("96" * 32,),
        )
    assert reopened.execute(
        "SELECT state_commitment_sha256, version_ordinal"
        " FROM protection_authority WHERE scope_id = 1"
    ).fetchone() == ("95" * 32, 5)


def test_reopened_default_connection_cannot_replace_invalidation_evidence(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection)
    _insert_open_effect(connection, 1)
    _insert_venue_owner(connection, owner_external="owner-1", effect_id=1)
    _insert_claim(connection, claim_id=1, effect_id=1)
    _insert_open_effect(connection, 2)
    _insert_venue_owner(connection, owner_external="owner-2", effect_id=2)
    _insert_claim(connection, claim_id=2, effect_id=2)
    _close_generation_authority(connection, generation_id="12" * 32)
    acceptance_set_id = int(
        connection.execute(
            "SELECT acceptance_set_id FROM acceptance_set WHERE effect_id = 1"
        ).fetchone()[0]
    )
    other_acceptance_set_id = int(
        connection.execute(
            "SELECT acceptance_set_id FROM acceptance_set WHERE effect_id = 2"
        ).fetchone()[0]
    )
    connection.execute(
        "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
        " effect_id, evidence_kind, proof_kind, evidence_digest, evidence_ordinal,"
        " contradiction_owner_external, contradiction_observation_external)"
        " VALUES (99, ?, 1, 'INVALIDATION', NULL, ?, 3, 'owner-1',"
        " 'observation-owner-1')",
        (acceptance_set_id, "a8" * 32),
    )
    connection.commit()
    connection.close()
    _OPEN_CONNECTIONS.remove(connection)

    reopened = sqlite3.connect(tmp_path / "m2-i2-gate.db")  # type: ignore[operator]
    _OPEN_CONNECTIONS.append(reopened)
    assert reopened.execute("PRAGMA foreign_keys").fetchone() == (0,)
    assert reopened.execute("PRAGMA recursive_triggers").fetchone() == (0,)
    with pytest.raises(sqlite3.IntegrityError, match="identity is already retained"):
        reopened.execute(
            "INSERT OR REPLACE INTO acceptance_evidence ("
            " evidence_id, acceptance_set_id, effect_id, evidence_kind,"
            " proof_kind, evidence_digest, evidence_ordinal,"
            " contradiction_owner_external, contradiction_observation_external)"
            " VALUES (100, ?, 1, 'INVALIDATION', NULL, ?, 4, 'owner-1',"
            " 'observation-owner-1')",
            (acceptance_set_id, "a9" * 32),
        )
    malformed_bindings = (
        (101, acceptance_set_id, "owner-2", "observation-owner-1"),
        (102, acceptance_set_id, "owner-1", "wrong-observation"),
        (103, other_acceptance_set_id, "owner-1", "observation-owner-1"),
    )
    for evidence_id, set_id, owner, observation in malformed_bindings:
        with pytest.raises(sqlite3.IntegrityError, match="exact retained authority"):
            reopened.execute(
                "INSERT INTO acceptance_evidence ("
                " evidence_id, acceptance_set_id, effect_id, evidence_kind,"
                " proof_kind, evidence_digest, evidence_ordinal,"
                " contradiction_owner_external, contradiction_observation_external)"
                " VALUES (?, ?, 1, 'INVALIDATION', NULL, ?, 4, ?, ?)",
                (evidence_id, set_id, f"{evidence_id:064x}", owner, observation),
            )
    reopened.rollback()

    assert reopened.execute(
        "SELECT evidence_id, evidence_kind FROM acceptance_evidence"
        " ORDER BY evidence_id"
    ).fetchall() == [
        (1, "CLOSURE_PROOF"),
        (2, "CLOSURE_PROOF"),
        (99, "INVALIDATION"),
    ]
    assert reopened.execute(
        "SELECT closure_id, owner_external, closure_kind FROM closure_chain"
    ).fetchall() == [(-99, "owner-1", "INVALIDATED_TERMINAL")]
    assert reopened.execute(
        "SELECT unresolved_effect_count FROM acquisition_generation_current"
        " WHERE acquisition_generation_id = ?",
        ("12" * 32,),
    ).fetchone() == (1,)
    assert reopened.execute(
        "SELECT integrity_state, currentness_head_ordinal,"
        " controller_version_ordinal FROM symbol_controller"
    ).fetchone() == ("UNRESOLVED_VENUE_QUARANTINED", 1, 2)
    assert reopened.execute(
        "SELECT effect_id, disposition FROM venue_effect ORDER BY effect_id"
    ).fetchall() == [(1, "INVALIDATED"), (2, "CLOSED")]

    reopened.execute("PRAGMA foreign_keys = ON")
    reopened.execute("PRAGMA recursive_triggers = ON")
    assert verify_schema_connection(reopened) == SCHEMA_VERSION


def test_controller_aggregate_query_is_scope_indexed(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    plan = " ".join(
        str(part)
        for row in connection.execute(
            "EXPLAIN QUERY PLAN SELECT SUM(CASE current_side WHEN 'BUY'"
            " THEN current_quantity ELSE -current_quantity END)"
            " FROM root_fill WHERE scope_id = 1 AND current_fact_id IS NOT NULL"
        )
        for part in row
    ).upper()
    assert "SEARCH" in plan
    assert "SCAN ROOT_FILL" not in plan


def test_execution_sequence_rejects_unaccounted_global_gaps(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection, key_id=1, external="root-1")
    _insert_root(connection, key_id=2, external="root-2")
    _insert_fill(
        connection,
        fact_id=1,
        root_id=1,
        event="sequence-1",
        fact_ordinal=1,
    )
    with pytest.raises(sqlite3.IntegrityError, match="next global execution sequence"):
        _insert_fill(
            connection,
            fact_id=2,
            root_id=2,
            event="sequence-gap",
            fact_ordinal=3,
        )


# ---------------------------------------------------------------------------
# Codex fresh-review RED controls.  Each control isolates one authority gap
# reproduced against checkpoint b284beaa before the replacement mechanism.


def test_current_root_economics_must_equal_the_authenticated_fact(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    scope_id = _seed_scope_with_live_generation(connection)
    root_id = _insert_root(connection, scope_id=scope_id)
    _insert_fill(connection, fact_id=1, root_id=root_id, event="evt-1")
    _insert_revision(
        connection,
        fact_id=2,
        root_id=root_id,
        event="evt-2",
        predecessor_fact_id=1,
    )

    with pytest.raises(sqlite3.IntegrityError, match="exact current execution fact"):
        connection.execute(
            """
            UPDATE root_fill
               SET current_quantity = 99,
                   price_units = 777,
                   economics_head_ordinal = 2
             WHERE root_fill_key_id = ?
            """,
            (root_id,),
        )


def test_execution_profile_is_generation_owned_and_scope_retains_no_raw_account(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _insert_profiles_and_generation(connection)

    profile_columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(execution_connection_profile)")
    }
    assert "application_generation" in profile_columns

    scope_columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(acquisition_scope)")
    }
    fact_columns = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(execution_fact)")
    }
    assert "execution_profile_id" in scope_columns
    assert "execution_profile_id" in fact_columns
    assert "account_text" not in scope_columns | fact_columns

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO application_generation (
                application_generation_id, selected_execution_profile_id,
                selected_market_source_profile_id, activation_ordinal
            )
            VALUES ('replacement-generation', ?, ?, 2)
            """,
            ("cd" * 32, "ef" * 32),
        )


def test_execution_fact_schema_preserves_complete_typed_fact_coordinates(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    columns = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(execution_fact)")
    }
    assert {
        "execution_profile_id",
        "order_external",
        "side",
        "authority",
        "price_present",
        "tick_units",
        "tick_scale_sign",
        "tick_scale_digits",
        "tick_scale_exponent",
        "request_occurrence_external",
        "claim_occurrence_external",
        "prior_cumulative_quantity",
        "resulting_cumulative_quantity",
        "actor_external",
        "reason_text",
        "evidence_reference_external",
    } <= columns


def test_execution_fact_shapes_round_trip_and_refuse_kind_economics_collision(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection, key_id=1, external="broker-root")
    _insert_fill(connection, fact_id=1, root_id=1, event="broker-fill")

    with pytest.raises(sqlite3.IntegrityError):
        _insert_revision(
            connection,
            fact_id=2,
            root_id=1,
            event="invalid-bust",
            predecessor_fact_id=1,
            kind="TRADE_BUST",
        )

    _insert_root(connection, key_id=2, external="human-root")
    _ensure_acquisition_root_route(connection, root_id=2)
    connection.execute(
        """
        INSERT INTO execution_fact (
            fact_id, scope_id, application_generation_id,
            execution_profile_id, root_fill_key_id, source_event_id,
            order_external, side, kind, authority, quantity,
            price_present, price_units, scale_sign, scale_digits,
            scale_exponent, tick_units, tick_scale_sign,
            tick_scale_digits, tick_scale_exponent,
            request_occurrence_external, claim_occurrence_external,
            prior_cumulative_quantity, resulting_cumulative_quantity,
            actor_external, reason_text, evidence_reference_external,
            predecessor_fact_id, fact_ordinal
        ) VALUES (
            3, 1, ?, ?, 2, 'human-fill', 'order-2', 'BUY', 'FILL',
            'HUMAN_ATTESTED', 5,
            1, 2500, 0, '1', -2, 1, 0, '1', -2,
            'request-1', 'claim-1', 0, 5,
            'operator-1', 'broker outage reconciliation', 'evidence-1',
            NULL, 2
        )
        """,
        (_DEFAULT_GENERATION_ID, _DEFAULT_EXECUTION_PROFILE_ID),
    )
    stored = connection.execute(
        """
        SELECT order_external, side, authority, quantity,
               price_units, tick_units, request_occurrence_external,
               claim_occurrence_external, prior_cumulative_quantity,
               resulting_cumulative_quantity, actor_external,
               reason_text, evidence_reference_external
          FROM execution_fact
         WHERE fact_id = 3
        """
    ).fetchone()
    assert stored == (
        "order-2",
        "BUY",
        "HUMAN_ATTESTED",
        5,
        2500,
        1,
        "request-1",
        "claim-1",
        0,
        5,
        "operator-1",
        "broker outage reconciliation",
        "evidence-1",
    )

    # Human attestations remain retained facts but cannot become revision
    # roots. Only broker-authoritative facts may participate in a broker
    # TRADE_CORRECT/TRADE_BUST predecessor chain.
    with pytest.raises(sqlite3.IntegrityError, match="exact predecessor scope"):
        _insert_revision(
            connection,
            fact_id=4,
            root_id=2,
            event="revision-of-human-attestation",
            predecessor_fact_id=3,
            fact_ordinal=3,
        )


def test_effect_schema_carries_lifecycle_and_bound_closure_proof(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    columns = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(venue_effect)")
    }
    assert {
        "expected_controller_head_ordinal",
        "expected_protection_version_ordinal",
        "authority_class",
        "lifecycle_state",
        "closure_proof_kind",
        "closure_proof_digest",
        "closure_proof_evidence_id",
        "closure_proof_claim_id",
    } <= columns


def test_effect_must_start_open(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    _insert_root(connection)
    _ensure_normal_protection(
        connection,
        seed=10,
        scope_id=1,
        application_generation_id=_DEFAULT_GENERATION_ID,
        acquisition_generation_id="12" * 32,
        generation_mandate_commitment_sha256="9a" * 32,
        expected_controller_head_ordinal=0,
    )

    with pytest.raises(sqlite3.IntegrityError, match="starts OPEN"):
        connection.execute(
            """
            INSERT INTO venue_effect (
                effect_id, effect_external, scope_id,
                application_generation_id, execution_profile_id,
                acquisition_generation_id,
                generation_mandate_commitment_sha256,
                expected_controller_head_ordinal,
                expected_protection_version_ordinal, authority_class,
                request_occurrence_external, mandate_external, effect_kind,
                client_order_external, target_order_external, side, quantity,
                economic_scope, lifecycle_state, disposition, created_ordinal
            )
            VALUES (10, 'effect-10', 1, ?, ?, ?, ?, 0, 1, 'NORMAL',
                    'request-10', 'mandate-10', 'SUBMIT', 'client-10', NULL,
                    'BUY', 10, x'01', 'REQUESTED', 'CLOSED', 10)
            """,
            (
                _DEFAULT_GENERATION_ID,
                _DEFAULT_EXECUTION_PROFILE_ID,
                "12" * 32,
                "9a" * 32,
            ),
        )


def test_successor_generation_requires_retired_compatible_predecessor(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    scope_id = _seed_scope_with_live_generation(connection)
    connection.execute(
        "UPDATE acquisition_generation SET status = 'RETIRED_UNSERVING' "
        "WHERE acquisition_generation_id = ?",
        ("12" * 32,),
    )

    with pytest.raises(sqlite3.IntegrityError, match="retired and compatibility-equal"):
        connection.execute(
            """
            INSERT INTO acquisition_generation (
                acquisition_generation_id, scope_id, status,
                successor_ordinal, predecessor_generation_id,
                mandate_commitment_sha256, emergency_compatibility_sha256
            )
            VALUES (?, ?, 'LIVE', 2, ?, ?, ?)
            """,
            ("34" * 32, scope_id, "12" * 32, "9c" * 32, "9d" * 32),
        )


def test_market_stream_route_is_exact_scope_session_and_source_profile(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(market_stream_authority)")
    }
    assert {
        "stream_generation_id",
        "scope_id",
        "application_generation_id",
        "source_profile_id",
        "session_external",
        "sequence_mode",
    } <= columns

    _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
    stream_id = "81" * 32
    _insert_market_stream(
        connection,
        stream_generation_id=stream_id,
    )
    _insert_market_cursor(
        connection,
        stream_generation_id=stream_id,
        fixed_cursor_ordinal=4,
        published_head_ordinal=5,
    )
    _insert_protection_authority(
        connection,
        stream_generation_id=stream_id,
        state_commitment_sha256="82" * 32,
        version_ordinal=1,
    )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        connection.execute(
            "UPDATE protection_authority"
            " SET active_stream_generation_id = ?, version_ordinal = 2"
            " WHERE scope_id = 1",
            ("83" * 32,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE market_cursor SET fixed_cursor_ordinal = 6"
            " WHERE stream_generation_id = ?",
            (stream_id,),
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

    with pytest.raises(sqlite3.IntegrityError, match="head may only advance"):
        connection.execute(
            "UPDATE kernel_checkpoint SET currentness_head_ordinal = 4,"
            " checkpoint_version_ordinal = 2"
        )
    connection.execute(
        "UPDATE kernel_checkpoint"
        " SET currentness_head_ordinal = 6, checkpoint_version_ordinal = 2"
    )


def test_current_proof_payloads_require_fresh_heads_or_versions(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    generation_id = _DEFAULT_GENERATION_ID
    _seed_scope_with_live_generation(connection)
    connection.execute(
        "INSERT INTO kernel_checkpoint VALUES (?, 5, ?, 1)",
        (generation_id, "77" * 32),
    )
    _insert_root(connection)
    connection.execute(
        """
        INSERT INTO symbol_controller (
            scope_id, application_generation_id, execution_profile_id,
            live_acquisition_generation_id, aggregate_quantity,
            integrity_state,
            currentness_head_ordinal, controller_version_ordinal,
            emergency_compatibility_sha256
        ) VALUES (1, ?, ?, ?, 0, 'CONSISTENT', 0, 1, ?)
        """,
        (
            generation_id,
            _DEFAULT_EXECUTION_PROFILE_ID,
            "12" * 32,
            "9b" * 32,
        ),
    )
    _insert_fill(connection, fact_id=1, root_id=1, event="evt-head")
    connection.execute(
        "UPDATE protection_authority"
        " SET expected_controller_head_ordinal = 1,"
        " state_commitment_sha256 = ?, version_ordinal = 2",
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

    with pytest.raises(sqlite3.IntegrityError, match="canonical root economics"):
        connection.execute(
            "UPDATE symbol_controller SET aggregate_quantity = 99,"
            " currentness_head_ordinal = currentness_head_ordinal + 1,"
            " controller_version_ordinal = controller_version_ordinal + 1"
            " WHERE scope_id = 1"
        )

    with pytest.raises(sqlite3.IntegrityError, match="exact current execution fact"):
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
    _insert_revision(
        connection,
        fact_id=2,
        root_id=1,
        event="evt-head-2",
        predecessor_fact_id=1,
    )
    assert connection.execute(
        "SELECT current_quantity, economics_head_ordinal FROM root_fill"
        " WHERE root_fill_key_id = 1"
    ).fetchone() == (7, 2)
    assert connection.execute(
        "SELECT aggregate_quantity FROM symbol_controller WHERE scope_id = 1"
    ).fetchone() == (7,)
    connection.execute(
        "UPDATE protection_authority"
        " SET expected_controller_head_ordinal = 2,"
        " state_commitment_sha256 = ?, version_ordinal = 3",
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
    _insert_venue_owner(connection, owner_external="owner-1", effect_id=1)
    _insert_open_effect(connection, 2)
    _insert_open_effect(connection, 3)

    with pytest.raises(sqlite3.IntegrityError, match="exact proof"):
        connection.execute(
            "UPDATE venue_effect SET disposition = 'CLOSED' WHERE effect_id = 1"
        )

    with pytest.raises(sqlite3.IntegrityError, match="requires immutable claim"):
        connection.execute(
            "UPDATE venue_effect SET lifecycle_state = 'DISPATCH_CLAIMED'"
            " WHERE effect_id = 1"
        )

    _insert_claim(connection, claim_id=1, effect_id=1)
    assert connection.execute(
        "SELECT lifecycle_state FROM venue_effect WHERE effect_id = 1"
    ).fetchone() == ("DISPATCH_CLAIMED",)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_claim(connection, claim_id=2, effect_id=1)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE dispatch_claim SET claim_ordinal = 9 WHERE claim_id = 1"
        )

    connection.execute(
        "INSERT INTO acceptance_set (acceptance_set_id, effect_id) VALUES (1, 1)"
    )
    connection.execute(
        """
        INSERT INTO acceptance_evidence (
            evidence_id, acceptance_set_id, effect_id, evidence_kind,
            proof_kind, evidence_digest, evidence_ordinal
        ) VALUES (1, 1, 1, 'CLOSURE_PROOF',
                  'CONTRACT_COMPLETE_RESPONSE', ?, 1)
        """,
        ("71" * 32,),
    )
    connection.execute(
        """
        UPDATE venue_effect
           SET disposition = 'CLOSED',
               closure_proof_kind = 'CONTRACT_COMPLETE_RESPONSE',
               closure_proof_digest = ?,
               closure_proof_evidence_id = 1,
               closure_proof_claim_id = 1
         WHERE effect_id = 1
        """,
        ("71" * 32,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE venue_effect SET disposition = 'OPEN' WHERE effect_id = 1"
        )

    _insert_claim(connection, claim_id=4, effect_id=3)
    assert connection.execute(
        "SELECT lifecycle_state FROM venue_effect WHERE effect_id = 3"
    ).fetchone() == ("DISPATCH_CLAIMED",)

    # Accepted authority (EC-2 / acceptance_set machine): CLOSED advances
    # only to INVALIDATED, which is then fully terminal.
    with pytest.raises(sqlite3.IntegrityError, match="acceptance transition"):
        connection.execute(
            "UPDATE venue_effect SET disposition = 'INVALIDATED' WHERE effect_id = 1"
        )
    connection.execute(
        "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
        " effect_id, evidence_kind, proof_kind, evidence_digest, evidence_ordinal,"
        " contradiction_owner_external, contradiction_observation_external)"
        " VALUES (2, 1, 1, 'INVALIDATION', NULL, ?, 2, ?, ?)",
        ("72" * 32, "owner-1", "observation-owner-1"),
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE venue_effect SET disposition = 'OPEN' WHERE effect_id = 1"
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE venue_effect SET disposition = 'CLOSED' WHERE effect_id = 1"
        )

    with pytest.raises(sqlite3.IntegrityError):
        _insert_claim(connection, claim_id=2, effect_id=1)

    # NEVER_DISPATCHED is the exact locally-canceled, no-claim closure route.
    connection.execute(
        "UPDATE venue_effect SET lifecycle_state = 'CANCELED_BEFORE_DISPATCH'"
        " WHERE effect_id = 2"
    )
    connection.execute(
        "INSERT INTO acceptance_set (acceptance_set_id, effect_id) VALUES (2, 2)"
    )
    connection.execute(
        """
        INSERT INTO acceptance_evidence (
            evidence_id, acceptance_set_id, effect_id, evidence_kind,
            proof_kind, evidence_digest, evidence_ordinal
        ) VALUES (3, 2, 2, 'CLOSURE_PROOF', 'NEVER_DISPATCHED', ?, 3)
        """,
        ("72" * 32,),
    )
    connection.execute(
        """
        UPDATE venue_effect
           SET disposition = 'CLOSED',
               closure_proof_kind = 'NEVER_DISPATCHED',
               closure_proof_digest = ?,
               closure_proof_evidence_id = 3
         WHERE effect_id = 2
        """,
        ("72" * 32,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        _insert_claim(connection, claim_id=3, effect_id=2)

    connection.execute(
        "INSERT INTO acceptance_set (acceptance_set_id, effect_id) VALUES (3, 3)"
    )
    connection.execute(
        """
        INSERT INTO acceptance_evidence (
            evidence_id, acceptance_set_id, effect_id, evidence_kind,
            proof_kind, evidence_digest, evidence_ordinal
        ) VALUES (4, 3, 3, 'CLOSURE_PROOF', 'NEVER_DISPATCHED', ?, 4)
        """,
        ("73" * 32,),
    )
    with pytest.raises(sqlite3.IntegrityError, match="CANCELED_BEFORE_DISPATCH"):
        connection.execute(
            """
            UPDATE venue_effect
               SET disposition = 'CLOSED',
                   closure_proof_kind = 'NEVER_DISPATCHED',
                   closure_proof_digest = ?,
                   closure_proof_evidence_id = 4
             WHERE effect_id = 3
            """,
            ("73" * 32,),
        )


def test_acceptance_state_machine_gates_late_evidence(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_scope_with_live_generation(connection)
    _insert_root(connection)
    _insert_open_effect(connection, 1)
    _insert_venue_owner(connection, owner_external="owner-1", effect_id=1)
    connection.execute(
        "INSERT INTO acceptance_set (acceptance_set_id, effect_id) VALUES (1, 1)"
    )
    connection.execute(
        "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
        " effect_id, evidence_kind, proof_kind, evidence_digest, evidence_ordinal)"
        " VALUES (1, 1, 1, 'OBSERVATION', NULL, ?, 1)",
        ("88" * 32,),
    )
    _insert_claim(connection, claim_id=1, effect_id=1)
    assert connection.execute(
        "SELECT lifecycle_state FROM venue_effect WHERE effect_id = 1"
    ).fetchone() == ("DISPATCH_CLAIMED",)
    connection.execute(
        """
        INSERT INTO acceptance_evidence (
            evidence_id, acceptance_set_id, effect_id, evidence_kind,
            proof_kind, evidence_digest, evidence_ordinal
        ) VALUES (2, 1, 1, 'CLOSURE_PROOF',
                  'CONTRACT_COMPLETE_RESPONSE', ?, 2)
        """,
        ("74" * 32,),
    )
    connection.execute(
        """
        UPDATE venue_effect
           SET disposition = 'CLOSED',
               closure_proof_kind = 'CONTRACT_COMPLETE_RESPONSE',
               closure_proof_digest = ?,
               closure_proof_evidence_id = 2,
               closure_proof_claim_id = 1
         WHERE effect_id = 1
        """,
        ("74" * 32,),
    )

    # EC-2: after CLOSED, only invalidation evidence may append.
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
            " effect_id, evidence_kind, proof_kind, evidence_digest, evidence_ordinal)"
            " VALUES (3, 1, 1, 'OBSERVATION', NULL, ?, 3)",
            ("89" * 32,),
        )
    connection.execute(
        "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
        " effect_id, evidence_kind, proof_kind, evidence_digest, evidence_ordinal,"
        " contradiction_owner_external, contradiction_observation_external)"
        " VALUES (4, 1, 1, 'INVALIDATION', NULL, ?, 4, ?, ?)",
        ("90" * 32, "owner-1", "observation-owner-1"),
    )
    connection.execute("UPDATE venue_effect SET disposition = 'INVALIDATED'")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
            " effect_id, evidence_kind, proof_kind, evidence_digest, evidence_ordinal)"
            " VALUES (5, 1, 1, 'OBSERVATION', NULL, ?, 5)",
            ("91" * 32,),
        )


# ---------------------------------------------------------------------------
# AC-2 direct current proof / query-plan controls.


def test_direct_head_lookups_use_indexes_not_scans(tmp_path: object) -> None:
    connection = _installed_connection(tmp_path)
    scope_id = _seed_scope_with_live_generation(connection)
    _insert_controller(connection)
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

    connection.execute(
        "INSERT INTO kernel_checkpoint VALUES (?, 50, ?, 1)",
        (_DEFAULT_GENERATION_ID, "75" * 32),
    )
    _insert_open_effect(connection, 1)
    _insert_venue_owner(connection, owner_external="owner-1", effect_id=1)
    connection.execute("INSERT INTO acceptance_set VALUES (1, 1)")
    _insert_claim(connection, claim_id=1, effect_id=1)
    connection.execute(
        "INSERT INTO closure_chain VALUES (1, 1, 'owner-1', 1, 1, 'TERMINAL_LEG', NULL)"
    )
    stream_id = "85" * 32
    _insert_market_stream(
        connection,
        stream_generation_id=stream_id,
    )
    _insert_market_cursor(
        connection,
        stream_generation_id=stream_id,
        fixed_cursor_ordinal=20,
        published_head_ordinal=50,
    )
    connection.execute(
        "UPDATE protection_authority"
        " SET state_commitment_sha256 = ?, version_ordinal ="
        " version_ordinal + 1",
        ("86" * 32,),
    )
    protection_stream_id = str(
        connection.execute(
            "SELECT active_stream_generation_id FROM protection_authority"
            " WHERE scope_id = ?",
            (scope_id,),
        ).fetchone()[0]
    )

    query_manifest = (
        (
            "checkpoint",
            "SELECT checkpoint_sha256 FROM kernel_checkpoint"
            " WHERE application_generation_id = ?",
            (_DEFAULT_GENERATION_ID,),
            ("75" * 32,),
        ),
        (
            "controller",
            "SELECT aggregate_quantity FROM symbol_controller WHERE scope_id = ?",
            (scope_id,),
            (7,),
        ),
        (
            "live-generation",
            "SELECT acquisition_generation_id FROM acquisition_generation"
            " WHERE scope_id = ? AND status = 'LIVE'",
            (scope_id,),
            ("12" * 32,),
        ),
        (
            "generation-current",
            "SELECT current_economics_head_ordinal, unresolved_effect_count,"
            " active_protection_count FROM acquisition_generation_current"
            " WHERE acquisition_generation_id = ?",
            ("12" * 32,),
            (50, 2, 1),
        ),
        (
            "root-route",
            "SELECT root_fill_key_id FROM root_fill"
            " WHERE execution_profile_id = ? AND root_fill_external = ?",
            (_DEFAULT_EXECUTION_PROFILE_ID, "root-fill-A"),
            (root_id,),
        ),
        (
            "acquisition-owner-route",
            "SELECT effect_id FROM acquisition_root_route WHERE root_fill_key_id = ?",
            (root_id,),
            (1_000_000 + root_id,),
        ),
        (
            "fact-head",
            "SELECT fact_id FROM execution_fact_head WHERE root_fill_key_id = ?",
            (root_id,),
            (50,),
        ),
        (
            "owner",
            "SELECT effect_id FROM venue_identity_owner"
            " WHERE scope_id = ? AND owner_external = ?",
            (scope_id, "owner-1"),
            (1,),
        ),
        (
            "acceptance",
            "SELECT acceptance_set_id FROM acceptance_set WHERE effect_id = ?",
            (1,),
            (1,),
        ),
        (
            "claim",
            "SELECT claim_id FROM dispatch_claim WHERE effect_id = ?",
            (1,),
            (1,),
        ),
        (
            "closure-head",
            "SELECT closure_id FROM closure_chain"
            " WHERE scope_id = ? AND owner_external = ?"
            " ORDER BY ordinal DESC LIMIT 1",
            (scope_id, "owner-1"),
            (1,),
        ),
        (
            "protection",
            "SELECT active_stream_generation_id FROM protection_authority"
            " WHERE scope_id = ?",
            (scope_id,),
            (protection_stream_id,),
        ),
        (
            "market-cursor",
            "SELECT fixed_cursor_ordinal FROM market_cursor"
            " WHERE stream_generation_id = ?",
            (stream_id,),
            (20,),
        ),
    )
    for label, query, parameters, expected in query_manifest:
        plan_rows = connection.execute(
            f"EXPLAIN QUERY PLAN {query}", parameters
        ).fetchall()
        plan_text = " ".join(str(row[-1]) for row in plan_rows)
        assert "SEARCH" in plan_text, (label, plan_text)
        assert "SCAN" not in plan_text, (label, plan_text)
        assert connection.execute(query, parameters).fetchone() == expected

    open_plan = connection.execute(
        "EXPLAIN QUERY PLAN SELECT effect_id FROM venue_effect"
        " WHERE scope_id = ? AND disposition = 'OPEN'",
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
            connection_profile_id, application_generation,
            broker_provider, environment_class,
            account_identity, trade_command_origin, order_query_origin,
            order_event_origin, credential_handle_fingerprint,
            adapter_contract_version, capability_profile_sha256,
            deployment_identity, profile_commitment_sha256
        )
        VALUES (?, ?, 'ALPACA', 'PAPER', ?,
                'https://trade.example.com',
                'https://query.example.com',
                ?, ?, '1.2.3', ?, ?, ?)
        """,
        (
            profile_id,
            f"generation-{profile_id[:8]}",
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
        "leading-hyphen": "https://-bad.example.com",
        "empty-label": "https://a..b",
        "leading-zero-port": "https://stream.example.com:01",
        "oversized-port": "https://stream.example.com:65536",
        "ipv4": "https://127.0.0.1",
        "trailing-dot": "https://stream.example.com.",
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
        "connection_profile_id, application_generation,"
        " broker_provider, environment_class,"
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
        "application_generation": f"generation-{profile_id[:8]}",
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

    if column in {"source_origin", "normalization_contract_version"}:
        source_origin = "https://feed.example.com"
        normalization_version = "0.1.0"
        if column == "source_origin":
            source_origin = value
        else:
            normalization_version = value
        connection.execute(
            """
            INSERT INTO market_data_source_profile (
                market_source_profile_id, provider, environment_or_feed,
                source_origin, entitlement_class,
                normalization_contract_version,
                data_capability_profile_sha256,
                source_profile_commitment_sha256
            )
            VALUES (?, 'ALPACA', 'iex-feed', ?, 'IEX', ?, ?, ?)
            """,
            (
                profile_id,
                source_origin,
                normalization_version,
                "ff" * 32,
                ("b7" * 15 + profile_id[:2] + "c8" * 16),
            ),
        )
        return

    values[column] = value

    connection.execute(
        f"INSERT INTO execution_connection_profile ({columns}) VALUES"
        " (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tuple(
            values[name]
            for name in (
                "connection_profile_id",
                "application_generation",
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


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("adapter_contract_version", "01.2.3"),
        ("adapter_contract_version", "1.2.3.4"),
        ("adapter_contract_version", "1..3"),
        ("normalization_contract_version", "00.1.0"),
        ("normalization_contract_version", "0.1.0.1"),
    ],
)
def test_sqlite_refuses_noncanonical_profile_versions(
    tmp_path: object,
    column: str,
    value: str,
) -> None:
    connection = _installed_connection(tmp_path)
    with pytest.raises(sqlite3.IntegrityError, match="version"):
        _insert_profile_with_origin_override(
            connection,
            profile_id=(value.encode().hex() + "ab" * 32)[:64],
            column=column,
            value=value,
        )


# ---------------------------------------------------------------------------
# FR-3 / FR-4 / FR-6 same-scope relational bindings: database-level negative
# controls proving cross-scope substitutions are structurally refused.


def _seed_two_scopes(connection: sqlite3.Connection) -> None:
    """Two deployment generations, two scopes, one live acquisition gen each."""

    generation_a = _insert_profiles_and_generation(connection)
    generation_b = _insert_second_profiles_and_generation(connection)
    connection.execute(
        """
        INSERT INTO acquisition_scope (
            scope_id, application_generation_id, execution_profile_id,
            symbol_text
        ) VALUES
        (1, ?, ?, 'AAPL'),
        (2, ?, ?, 'MSFT')
        """,
        (
            generation_a,
            _DEFAULT_EXECUTION_PROFILE_ID,
            generation_b,
            "67" * 32,
        ),
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
        "INSERT INTO symbol_controller VALUES (1, ?, ?, ?, 0, 'CONSISTENT', 0, 1, ?)",
        (
            _DEFAULT_GENERATION_ID,
            _DEFAULT_EXECUTION_PROFILE_ID,
            "12" * 32,
            "9b" * 32,
        ),
    ).rowcount
    assert stored == 1

    with pytest.raises(sqlite3.IntegrityError, match="live generation"):
        connection.execute(
            "INSERT INTO symbol_controller VALUES"
            " (2, ?, ?, ?, 0, 'CONSISTENT', 0, 1, ?)",
            ("56" * 32, "67" * 32, "12" * 32, "9b" * 32),
        )

    with pytest.raises(sqlite3.IntegrityError, match="compatible"):
        connection.execute(
            "INSERT INTO symbol_controller VALUES"
            " (2, ?, ?, ?, 0, 'CONSISTENT', 0, 1, ?)",
            ("56" * 32, "67" * 32, "34" * 32, "9b" * 32),
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

    assert _insert_root(connection, key_id=1, scope_id=1, external="r-A") == 1

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        _insert_root(
            connection,
            key_id=2,
            scope_id=2,
            external="r-B",
            application_generation_id="56" * 32,
            execution_profile_id="67" * 32,
            owner_generation_id="12" * 32,
        )


def test_execution_fact_cannot_reference_root_of_another_scope(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_two_scopes(connection)
    _insert_root(connection, key_id=1, scope_id=1, external="r-A")

    # Run the cross-scope mutant before the canonical FILL exists so the
    # exact root/scope foreign key, not one-FILL-per-root uniqueness, owns it.
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        _insert_fill(
            connection,
            fact_id=2,
            root_id=1,
            event="evt-x",
            scope_id=2,
            generation_id="56" * 32,
            execution_profile_id="67" * 32,
            fact_ordinal=1,
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


def test_venue_effect_cannot_reference_generation_of_another_scope(
    tmp_path: object,
) -> None:
    connection = _installed_connection(tmp_path)
    _seed_two_scopes(connection)
    assert _insert_open_effect(connection, 1) == 1
    _insert_controller(
        connection,
        scope_id=2,
        application_generation_id="56" * 32,
        execution_profile_id="67" * 32,
        acquisition_generation_id="34" * 32,
        emergency_compatibility_sha256="8b" * 32,
    )

    with pytest.raises(sqlite3.IntegrityError, match="current controller head"):
        _insert_open_effect(
            connection,
            2,
            scope_id=2,
            application_generation_id="56" * 32,
            execution_profile_id="67" * 32,
            acquisition_generation_id="12" * 32,
            generation_mandate_commitment_sha256="9a" * 32,
            ensure_protection=False,
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
        ("bb" * 32, "12" * 32, "7c" * 32, "9b" * 32),
    )
    with pytest.raises(sqlite3.IntegrityError, match="immediate prior"):
        connection.execute(
            "INSERT INTO acquisition_generation VALUES"
            " (?, 1, 'RETIRED_UNSERVING', 4, ?, ?, ?)",
            ("cc" * 32, "12" * 32, "7e" * 32, "9b" * 32),
        )

    # Positive control: the immediate same-scope successor is accepted and
    # may hold LIVE authority once its predecessor retired.
    stored = connection.execute(
        "INSERT INTO acquisition_generation VALUES (?, 1, 'LIVE', 3, ?, ?, ?)",
        ("dd" * 32, "bb" * 32, "6a" * 32, "9b" * 32),
    ).rowcount
    assert stored == 1
