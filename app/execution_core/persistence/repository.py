"""Typed, direct-key SQLite repository for the accepted M2-I2 schema.

Every public operation accepts one explicit already-open connection, verifies
the exact schema and connection-local enforcement first, and leaves BEGIN,
COMMIT, and ROLLBACK to its caller. Immutable owner rows are inserted; mutable
current rows advance through expected-version updates; trigger-derived rows
are load-only. Durable identities and values cross this boundary only through
the accepted M2-I1 codec and immutable profile constructors.
"""

from __future__ import annotations as _annotations

from typing import Any as _Any
from typing import Callable as _Callable
from typing import TypeVar as _TypeVar
from typing import cast as _cast

from .. import identity as _identity
from .. import profiles as _profiles
from .. import values as _values
from ..durable_codec import DurableAtom as _DurableAtom
from ..durable_codec import decode_m1_value as _decode_m1_value
from ..durable_codec import encode_m1_value as _encode_m1_value
from . import records as _records
from .schema import SQLiteConnectionProtocol as _SQLiteConnectionProtocol
from .schema import verify_schema_connection as _verify_schema_connection


_RecordT = _TypeVar("_RecordT")
_CONTRACT_VERSION = "1"


def _outcome(
    kind: _records.RepositoryOutcomeKind,
    record: _RecordT | None = None,
) -> _records.RepositoryOutcome[_RecordT]:
    return _records.RepositoryOutcome(kind, record)


def _integrity() -> _records.RepositoryOutcome[_Any]:
    return _outcome(_records.RepositoryOutcomeKind.INTEGRITY_FAILURE)


def _classify_sqlite_failure(
    caught: Exception,
    *,
    conflict_trigger_messages: tuple[str, ...] = (),
) -> _records.RepositoryOutcome[_Any]:
    """Preserve duplicate contention separately from malformed authority."""

    # Resolve only the already-loaded driver on the failure path. A direct
    # ``sys`` or ``sqlite3`` dependency is forbidden in the pure kernel.
    loaded_modules = getattr(__import__("sys"), "modules")
    sqlite_module = loaded_modules.get("sqlite3")
    sqlite_error = (
        None if sqlite_module is None else getattr(sqlite_module, "Error", None)
    )
    sqlite_integrity_error = (
        None
        if sqlite_module is None
        else getattr(sqlite_module, "IntegrityError", None)
    )
    if not isinstance(sqlite_error, type) or not isinstance(caught, sqlite_error):
        raise caught
    if isinstance(sqlite_integrity_error, type) and isinstance(
        caught, sqlite_integrity_error
    ):
        code = getattr(caught, "sqlite_errorcode", None)
        # SQLite extended result codes, intentionally kept as values so the
        # pure execution kernel never imports the sqlite3 capability module.
        conflict_codes = {1555, 2067}  # PRIMARYKEY, UNIQUE
        if code in conflict_codes or str(caught) in conflict_trigger_messages:
            return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
    return _integrity()


def _insert(
    connection: _SQLiteConnectionProtocol,
    sql: str,
    prepare: _Callable[[], tuple[_Any, ...]],
    *,
    conflict_trigger_messages: tuple[str, ...] = (),
    conflict_probe: tuple[
        str,
        _Callable[[tuple[_Any, ...]], tuple[_Any, ...]],
    ],
) -> _records.RepositoryOutcome[_Any]:
    _verify_schema_connection(connection)
    try:
        parameters = prepare()
    except (TypeError, ValueError, OverflowError):
        return _integrity()
    try:
        connection.execute(sql, parameters)
    except Exception as caught:
        classified = _classify_sqlite_failure(
            caught,
            conflict_trigger_messages=conflict_trigger_messages,
        )
        probe_sql, probe_parameters = conflict_probe
        try:
            retained_rows = connection.execute(
                probe_sql,
                probe_parameters(parameters),
            ).fetchall()
        except Exception as probe_failure:
            return _classify_sqlite_failure(probe_failure)
        if len(retained_rows) == 1 and tuple(retained_rows[0]) == parameters:
            return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
        if retained_rows or classified.kind is _records.RepositoryOutcomeKind.CONFLICT:
            return _integrity()
        return classified
    return _outcome(_records.RepositoryOutcomeKind.APPLIED)


def _advance(
    connection: _SQLiteConnectionProtocol,
    sql: str,
    prepare: _Callable[[], tuple[_Any, ...]],
) -> _records.RepositoryOutcome[_Any]:
    _verify_schema_connection(connection)
    try:
        parameters = prepare()
    except (TypeError, ValueError, OverflowError):
        return _integrity()
    try:
        cursor = connection.execute(sql, parameters)
    except Exception as caught:
        return _classify_sqlite_failure(caught)
    if cursor.rowcount != 1:
        return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
    return _outcome(_records.RepositoryOutcomeKind.APPLIED)


def _validate_advance_authority(
    connection: _SQLiteConnectionProtocol,
    sql: str,
    parameters: tuple[_Any, ...],
    build: _Callable[[tuple[_Any, ...]], _RecordT],
    matches: _Callable[[_RecordT], bool],
) -> _records.RepositoryOutcome[_Any] | None:
    retained = _select_one_unchecked(connection, sql, parameters, build)
    if retained.kind is _records.RepositoryOutcomeKind.ABSENT:
        return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
    if retained.kind is not _records.RepositoryOutcomeKind.FOUND:
        return _outcome(retained.kind)
    if retained.record is None or not matches(retained.record):
        return _integrity()
    return None


def _select_one_unchecked(
    connection: _SQLiteConnectionProtocol,
    sql: str,
    parameters: tuple[_Any, ...],
    build: _Callable[[tuple[_Any, ...]], _RecordT],
) -> _records.RepositoryOutcome[_RecordT]:
    try:
        cursor = connection.execute(sql, _query_parameters(parameters))
        row = cursor.fetchone()
        if row is None:
            return _outcome(_records.RepositoryOutcomeKind.ABSENT)
        if cursor.fetchone() is not None:
            return _integrity()
        return _outcome(_records.RepositoryOutcomeKind.FOUND, build(tuple(row)))
    except (TypeError, ValueError, OverflowError, IndexError):
        return _integrity()
    except Exception as caught:
        return _classify_sqlite_failure(caught)


def _load(
    connection: _SQLiteConnectionProtocol,
    sql: str,
    parameters: tuple[_Any, ...],
    build: _Callable[[tuple[_Any, ...]], _RecordT],
) -> _records.RepositoryOutcome[_RecordT]:
    _verify_schema_connection(connection)
    return _select_one_unchecked(connection, sql, parameters, build)


def _load_int_key(
    connection: _SQLiteConnectionProtocol,
    sql: str,
    key: object,
    build: _Callable[[tuple[_Any, ...]], _RecordT],
) -> _records.RepositoryOutcome[_RecordT]:
    _verify_schema_connection(connection)
    try:
        exact_key = _exact_int(key)
    except TypeError:
        return _integrity()
    return _select_one_unchecked(connection, sql, (exact_key,), build)


def _load_text_key(
    connection: _SQLiteConnectionProtocol,
    sql: str,
    key: object,
    build: _Callable[[tuple[_Any, ...]], _RecordT],
) -> _records.RepositoryOutcome[_RecordT]:
    _verify_schema_connection(connection)
    try:
        exact_key = _exact_text(key)
    except TypeError:
        return _integrity()
    return _select_one_unchecked(connection, sql, (exact_key,), build)


def _exact_int(value: object) -> int:
    if type(value) is not int:
        raise TypeError("SQLite integer coordinate is not an exact integer")
    return value


def _exact_optional_int(value: object) -> int | None:
    if value is None:
        return None
    return _exact_int(value)


def _exact_text(value: object) -> str:
    if type(value) is not str:
        raise TypeError("SQLite text coordinate is not exact text")
    return value


def _exact_optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _exact_text(value)


def _exact_bytes(value: object) -> bytes:
    if type(value) is not bytes:
        raise TypeError("SQLite blob coordinate is not exact bytes")
    return value


def _query_parameters(parameters: tuple[_Any, ...]) -> tuple[_Any, ...]:
    normalized: list[_Any] = []
    for value in parameters:
        if value is None or type(value) in (int, str, bytes):
            normalized.append(value)
            continue
        raise TypeError("SQLite query coordinate has a non-exact scalar type")
    return tuple(normalized)


def _identity_text(value: object, owner: type, tag: str) -> str:
    if type(value) is not owner:
        raise TypeError(f"identity must be exact {owner.__name__}")
    atom = _encode_m1_value(_cast(_Any, value))
    if (
        atom.contract_version != _CONTRACT_VERSION
        or atom.type_tag != tag
        or len(atom.fields) != 1
        or type(atom.fields[0]) is not str
    ):
        raise ValueError("M1 identity encoded with an unexpected durable shape")
    return atom.fields[0]


def _decode_identity(value: object, owner: type[_RecordT], tag: str) -> _RecordT:
    decoded = _decode_m1_value(
        _DurableAtom(_CONTRACT_VERSION, tag, (_exact_text(value),))
    )
    if type(decoded) is not owner:
        raise TypeError("durable identity decoded to the wrong owning type")
    return decoded


def _optional_identity_text(value: object | None, owner: type, tag: str) -> str | None:
    if value is None:
        return None
    return _identity_text(value, owner, tag)


def _decode_optional_identity(
    value: object,
    owner: type[_RecordT],
    tag: str,
) -> _RecordT | None:
    if value is None:
        return None
    return _decode_identity(value, owner, tag)


def _quantity_value(value: object) -> int:
    if type(value) is not _values.Quantity:
        raise TypeError("quantity must be an exact M1 Quantity")
    atom = _encode_m1_value(value)
    if atom.type_tag != "quantity" or len(atom.fields) != 1:
        raise ValueError("quantity encoded with an unexpected durable shape")
    text = atom.fields[0]
    if type(text) is not str:
        raise TypeError("quantity durable leaf must be text")
    return int(text)


def _decode_quantity(value: object) -> _values.Quantity:
    integer = _exact_int(value)
    decoded = _decode_m1_value(
        _DurableAtom(_CONTRACT_VERSION, "quantity", (str(integer),))
    )
    if type(decoded) is not _values.Quantity:
        raise TypeError("durable quantity decoded to the wrong owning type")
    return decoded


def _decode_optional_quantity(value: object) -> _values.Quantity | None:
    if value is None:
        return None
    return _decode_quantity(value)


def _decimal_columns(atom: _DurableAtom) -> tuple[int, str, int]:
    if atom.type_tag != "price_scale" or len(atom.fields) != 1:
        raise ValueError("price scale encoded with an unexpected durable shape")
    decimal_atom = atom.fields[0]
    if type(decimal_atom) is not _DurableAtom or decimal_atom.type_tag != "_decimal":
        raise TypeError("price scale durable child is not the canonical decimal atom")
    sign, digits, exponent = decimal_atom.fields
    if type(sign) is not str or type(digits) is not str or type(exponent) is not str:
        raise TypeError("decimal durable leaves must be text")
    return int(sign), digits, int(exponent)


def _price_columns(
    price: object | None,
) -> tuple[int, int, int, str, int, int, int, str, int]:
    if price is None:
        return (0, 0, 0, "0", 0, 0, 0, "0", 0)
    if type(price) is not _values.ReportedPrice:
        raise TypeError("price must be an exact M1 ReportedPrice or None")
    atom = _encode_m1_value(price)
    if atom.type_tag != "reported_price" or len(atom.fields) != 3:
        raise ValueError("reported price encoded with an unexpected durable shape")
    units_atom, scale_atom, tick_atom = atom.fields
    if (
        type(units_atom) is not _DurableAtom
        or units_atom.type_tag != "price_units"
        or type(scale_atom) is not _DurableAtom
        or type(tick_atom) is not _DurableAtom
        or tick_atom.type_tag != "tick_metadata"
        or len(units_atom.fields) != 1
        or len(tick_atom.fields) != 2
    ):
        raise TypeError("reported price durable children have the wrong shape")
    tick_units_atom, tick_scale_atom = tick_atom.fields
    if (
        type(tick_units_atom) is not _DurableAtom
        or tick_units_atom.type_tag != "price_units"
        or type(tick_scale_atom) is not _DurableAtom
        or len(tick_units_atom.fields) != 1
    ):
        raise TypeError("tick durable children have the wrong shape")
    units_text = units_atom.fields[0]
    tick_units_text = tick_units_atom.fields[0]
    if type(units_text) is not str or type(tick_units_text) is not str:
        raise TypeError("price unit durable leaves must be text")
    sign, digits, exponent = _decimal_columns(scale_atom)
    tick_sign, tick_digits, tick_exponent = _decimal_columns(tick_scale_atom)
    return (
        1,
        int(units_text),
        sign,
        digits,
        exponent,
        int(tick_units_text),
        tick_sign,
        tick_digits,
        tick_exponent,
    )


def _decode_price(values: tuple[object, ...]) -> _values.ReportedPrice | None:
    if len(values) != 9:
        raise ValueError("reported price requires exactly nine SQLite columns")
    present = _exact_int(values[0])
    integers = (
        _exact_int(values[1]),
        _exact_int(values[2]),
        _exact_int(values[4]),
        _exact_int(values[5]),
        _exact_int(values[6]),
        _exact_int(values[8]),
    )
    digits = _exact_text(values[3])
    tick_digits = _exact_text(values[7])
    if present == 0:
        if integers != (0, 0, 0, 0, 0, 0) or digits != "0" or tick_digits != "0":
            raise ValueError("absent price carries noncanonical durable placeholders")
        return None
    if present != 1:
        raise ValueError("price presence flag is not canonical")
    units, sign, exponent, tick_units, tick_sign, tick_exponent = integers
    decimal_atom = _DurableAtom(
        _CONTRACT_VERSION,
        "_decimal",
        (str(sign), digits, str(exponent)),
    )
    tick_decimal_atom = _DurableAtom(
        _CONTRACT_VERSION,
        "_decimal",
        (str(tick_sign), tick_digits, str(tick_exponent)),
    )
    atom = _DurableAtom(
        _CONTRACT_VERSION,
        "reported_price",
        (
            _DurableAtom(_CONTRACT_VERSION, "price_units", (str(units),)),
            _DurableAtom(_CONTRACT_VERSION, "price_scale", (decimal_atom,)),
            _DurableAtom(
                _CONTRACT_VERSION,
                "tick_metadata",
                (
                    _DurableAtom(
                        _CONTRACT_VERSION,
                        "price_units",
                        (str(tick_units),),
                    ),
                    _DurableAtom(
                        _CONTRACT_VERSION,
                        "price_scale",
                        (tick_decimal_atom,),
                    ),
                ),
            ),
        ),
    )
    decoded = _decode_m1_value(atom)
    if type(decoded) is not _values.ReportedPrice:
        raise TypeError("durable price decoded to the wrong owning type")
    return decoded


def _application_id(value: object) -> str:
    return _identity_text(
        value, _identity.ApplicationGenerationId, "application_generation_id"
    )


def _decode_application_id(value: object) -> _identity.ApplicationGenerationId:
    return _decode_identity(
        value,
        _identity.ApplicationGenerationId,
        "application_generation_id",
    )


def _acquisition_id(value: object) -> str:
    return _identity_text(
        value, _identity.AcquisitionGenerationId, "acquisition_generation_id"
    )


def _decode_acquisition_id(value: object) -> _identity.AcquisitionGenerationId:
    return _decode_identity(
        value,
        _identity.AcquisitionGenerationId,
        "acquisition_generation_id",
    )


_EXECUTION_PROFILE_COLUMNS = (
    "connection_profile_id, application_generation, broker_provider,"
    " environment_class, account_identity, trade_command_origin,"
    " order_query_origin, order_event_origin, credential_handle_fingerprint,"
    " adapter_contract_version, capability_profile_sha256, deployment_identity,"
    " profile_commitment_sha256"
)


def _build_execution_profile(
    row: tuple[_Any, ...],
) -> _profiles.ExecutionConnectionProfile:
    values = tuple(_exact_text(value) for value in row)
    profile = _profiles.ExecutionConnectionProfile(*values[:-1])
    if profile.profile_commitment_sha256 != values[-1]:
        raise ValueError("execution profile commitment does not match its exact fields")
    return profile


def store_execution_profile(
    connection: _SQLiteConnectionProtocol,
    profile: _profiles.ExecutionConnectionProfile,
) -> _records.RepositoryOutcome[_Any]:
    def prepare() -> tuple[_Any, ...]:
        if type(profile) is not _profiles.ExecutionConnectionProfile:
            raise TypeError("profile must be an exact ExecutionConnectionProfile")
        return (
            profile.connection_profile_id,
            profile.application_generation,
            profile.broker_provider,
            profile.environment_class,
            profile.account_identity,
            profile.trade_command_origin,
            profile.order_query_origin,
            profile.order_event_origin,
            profile.credential_handle_fingerprint,
            profile.adapter_contract_version,
            profile.capability_profile_sha256,
            profile.deployment_identity,
            profile.profile_commitment_sha256,
        )

    return _insert(
        connection,
        f"INSERT INTO execution_connection_profile ({_EXECUTION_PROFILE_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        prepare,
        conflict_trigger_messages=("execution profile identity is already retained",),
        conflict_probe=(
            f"SELECT {_EXECUTION_PROFILE_COLUMNS} FROM execution_connection_profile"
            " WHERE connection_profile_id = ? OR profile_commitment_sha256 = ?",
            lambda parameters: (parameters[0], parameters[12]),
        ),
    )


def load_execution_profile(
    connection: _SQLiteConnectionProtocol,
    connection_profile_id: str,
) -> _records.RepositoryOutcome[_profiles.ExecutionConnectionProfile]:
    return _load_text_key(
        connection,
        f"SELECT {_EXECUTION_PROFILE_COLUMNS} FROM execution_connection_profile"
        " WHERE connection_profile_id = ?",
        connection_profile_id,
        _build_execution_profile,
    )


_MARKET_PROFILE_COLUMNS = (
    "market_source_profile_id, provider, environment_or_feed, source_origin,"
    " entitlement_class, normalization_contract_version,"
    " data_capability_profile_sha256, source_profile_commitment_sha256"
)


def _build_market_profile(row: tuple[_Any, ...]) -> _profiles.MarketDataSourceProfile:
    values = tuple(_exact_text(value) for value in row)
    profile = _profiles.MarketDataSourceProfile(*values[:-1])
    if profile.source_profile_commitment_sha256 != values[-1]:
        raise ValueError("market profile commitment does not match its exact fields")
    return profile


def store_market_source_profile(
    connection: _SQLiteConnectionProtocol,
    profile: _profiles.MarketDataSourceProfile,
) -> _records.RepositoryOutcome[_Any]:
    def prepare() -> tuple[_Any, ...]:
        if type(profile) is not _profiles.MarketDataSourceProfile:
            raise TypeError("profile must be an exact MarketDataSourceProfile")
        return (
            profile.market_source_profile_id,
            profile.provider,
            profile.environment_or_feed,
            profile.source_origin,
            profile.entitlement_class,
            profile.normalization_contract_version,
            profile.data_capability_profile_sha256,
            profile.source_profile_commitment_sha256,
        )

    return _insert(
        connection,
        f"INSERT INTO market_data_source_profile ({_MARKET_PROFILE_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        prepare,
        conflict_trigger_messages=("market profile identity is already retained",),
        conflict_probe=(
            f"SELECT {_MARKET_PROFILE_COLUMNS} FROM market_data_source_profile"
            " WHERE market_source_profile_id = ?"
            " OR source_profile_commitment_sha256 = ?",
            lambda parameters: (parameters[0], parameters[7]),
        ),
    )


def load_market_source_profile(
    connection: _SQLiteConnectionProtocol,
    market_source_profile_id: str,
) -> _records.RepositoryOutcome[_profiles.MarketDataSourceProfile]:
    return _load_text_key(
        connection,
        f"SELECT {_MARKET_PROFILE_COLUMNS} FROM market_data_source_profile"
        " WHERE market_source_profile_id = ?",
        market_source_profile_id,
        _build_market_profile,
    )


_APPLICATION_COLUMNS = (
    "application_generation_id, selected_execution_profile_id,"
    " selected_market_source_profile_id, activation_ordinal"
)


def _build_application(row: tuple[_Any, ...]) -> _records.ApplicationGenerationRecord:
    return _records.ApplicationGenerationRecord(
        _decode_application_id(row[0]),
        _exact_text(row[1]),
        _exact_text(row[2]),
        _exact_int(row[3]),
    )


def store_application_generation(
    connection: _SQLiteConnectionProtocol,
    record: _records.ApplicationGenerationRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO application_generation ({_APPLICATION_COLUMNS})"
        " VALUES (?, ?, ?, ?)",
        lambda: (
            _application_id(record.application_generation_id),
            _exact_text(record.selected_execution_profile_id),
            _exact_text(record.selected_market_source_profile_id),
            _exact_int(record.activation_ordinal),
        ),
        conflict_trigger_messages=(
            "application generation identity is already retained",
        ),
        conflict_probe=(
            f"SELECT {_APPLICATION_COLUMNS} FROM application_generation"
            " WHERE application_generation_id = ?"
            " OR selected_execution_profile_id = ?",
            lambda parameters: (parameters[0], parameters[1]),
        ),
    )


def load_application_generation(
    connection: _SQLiteConnectionProtocol,
    application_generation_id: _identity.ApplicationGenerationId,
) -> _records.RepositoryOutcome[_records.ApplicationGenerationRecord]:
    try:
        key = _application_id(application_generation_id)
    except (TypeError, ValueError):
        _verify_schema_connection(connection)
        return _integrity()
    return _load(
        connection,
        f"SELECT {_APPLICATION_COLUMNS} FROM application_generation"
        " WHERE application_generation_id = ?",
        (key,),
        _build_application,
    )


_SCOPE_COLUMNS = (
    "scope_id, application_generation_id, execution_profile_id, symbol_text"
)


def _build_scope(row: tuple[_Any, ...]) -> _records.ScopeRecord:
    return _records.ScopeRecord(
        _exact_int(row[0]),
        _decode_application_id(row[1]),
        _exact_text(row[2]),
        _decode_identity(row[3], _identity.SymbolId, "symbol_id"),
    )


def store_scope(
    connection: _SQLiteConnectionProtocol,
    record: _records.ScopeRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO acquisition_scope ({_SCOPE_COLUMNS}) VALUES (?, ?, ?, ?)",
        lambda: (
            _exact_int(record.scope_id),
            _application_id(record.application_generation_id),
            _exact_text(record.execution_profile_id),
            _identity_text(record.symbol, _identity.SymbolId, "symbol_id"),
        ),
        conflict_trigger_messages=("acquisition scope identity is already retained",),
        conflict_probe=(
            f"SELECT {_SCOPE_COLUMNS} FROM acquisition_scope WHERE scope_id = ?"
            " OR (application_generation_id = ? AND execution_profile_id = ?"
            " AND symbol_text = ?)",
            lambda parameters: (
                parameters[0],
                parameters[1],
                parameters[2],
                parameters[3],
            ),
        ),
    )


def load_scope(
    connection: _SQLiteConnectionProtocol,
    scope_id: int,
) -> _records.RepositoryOutcome[_records.ScopeRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_SCOPE_COLUMNS} FROM acquisition_scope WHERE scope_id = ?",
        scope_id,
        _build_scope,
    )


_ACQUISITION_COLUMNS = (
    "acquisition_generation_id, scope_id, status, successor_ordinal,"
    " predecessor_generation_id, mandate_commitment_sha256,"
    " emergency_compatibility_sha256"
)


def _build_acquisition(row: tuple[_Any, ...]) -> _records.AcquisitionGenerationRecord:
    return _records.AcquisitionGenerationRecord(
        _decode_acquisition_id(row[0]),
        _exact_int(row[1]),
        _exact_text(row[2]),
        _exact_int(row[3]),
        _decode_optional_identity(
            row[4],
            _identity.AcquisitionGenerationId,
            "acquisition_generation_id",
        ),
        _exact_text(row[5]),
        _exact_text(row[6]),
    )


def store_acquisition_generation(
    connection: _SQLiteConnectionProtocol,
    record: _records.AcquisitionGenerationRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO acquisition_generation ({_ACQUISITION_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        lambda: (
            _acquisition_id(record.acquisition_generation_id),
            _exact_int(record.scope_id),
            _exact_text(record.status),
            _exact_int(record.successor_ordinal),
            _optional_identity_text(
                record.predecessor_generation_id,
                _identity.AcquisitionGenerationId,
                "acquisition_generation_id",
            ),
            _exact_text(record.mandate_commitment_sha256),
            _exact_text(record.emergency_compatibility_sha256),
        ),
        conflict_trigger_messages=(
            "acquisition generation identity is already retained",
        ),
        conflict_probe=(
            f"SELECT {_ACQUISITION_COLUMNS} FROM acquisition_generation"
            " WHERE acquisition_generation_id = ?"
            " OR (scope_id = ? AND successor_ordinal = ?)",
            lambda parameters: (parameters[0], parameters[1], parameters[3]),
        ),
    )


def load_acquisition_generation(
    connection: _SQLiteConnectionProtocol,
    acquisition_generation_id: _identity.AcquisitionGenerationId,
) -> _records.RepositoryOutcome[_records.AcquisitionGenerationRecord]:
    try:
        key = _acquisition_id(acquisition_generation_id)
    except (TypeError, ValueError):
        _verify_schema_connection(connection)
        return _integrity()
    return _load(
        connection,
        f"SELECT {_ACQUISITION_COLUMNS} FROM acquisition_generation"
        " WHERE acquisition_generation_id = ?",
        (key,),
        _build_acquisition,
    )


def retire_acquisition_generation(
    connection: _SQLiteConnectionProtocol,
    acquisition_generation_id: _identity.AcquisitionGenerationId,
) -> _records.RepositoryOutcome[_Any]:
    return _advance(
        connection,
        "UPDATE acquisition_generation SET status = 'RETIRED_UNSERVING'"
        " WHERE acquisition_generation_id = ? AND status = 'LIVE'",
        lambda: (_acquisition_id(acquisition_generation_id),),
    )


_ACQUISITION_CURRENT_COLUMNS = (
    "acquisition_generation_id, scope_id, current_economics_head_ordinal,"
    " unresolved_effect_count, active_protection_count"
)


def _build_acquisition_current(
    row: tuple[_Any, ...],
) -> _records.AcquisitionGenerationCurrentRecord:
    return _records.AcquisitionGenerationCurrentRecord(
        _decode_acquisition_id(row[0]),
        _exact_int(row[1]),
        _exact_int(row[2]),
        _exact_int(row[3]),
        _exact_int(row[4]),
    )


def load_acquisition_generation_current(
    connection: _SQLiteConnectionProtocol,
    acquisition_generation_id: _identity.AcquisitionGenerationId,
) -> _records.RepositoryOutcome[_records.AcquisitionGenerationCurrentRecord]:
    try:
        key = _acquisition_id(acquisition_generation_id)
    except (TypeError, ValueError):
        _verify_schema_connection(connection)
        return _integrity()
    return _load(
        connection,
        f"SELECT {_ACQUISITION_CURRENT_COLUMNS}"
        " FROM acquisition_generation_current WHERE acquisition_generation_id = ?",
        (key,),
        _build_acquisition_current,
    )


_CHECKPOINT_COLUMNS = (
    "application_generation_id, currentness_head_ordinal, checkpoint_sha256,"
    " checkpoint_version_ordinal"
)


def _build_checkpoint(row: tuple[_Any, ...]) -> _records.KernelCheckpointRecord:
    return _records.KernelCheckpointRecord(
        _decode_application_id(row[0]),
        _exact_int(row[1]),
        _exact_text(row[2]),
        _exact_int(row[3]),
    )


def store_kernel_checkpoint(
    connection: _SQLiteConnectionProtocol,
    record: _records.KernelCheckpointRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO kernel_checkpoint ({_CHECKPOINT_COLUMNS}) VALUES (?, ?, ?, ?)",
        lambda: (
            _application_id(record.application_generation_id),
            _exact_int(record.currentness_head_ordinal),
            _exact_text(record.checkpoint_sha256),
            _exact_int(record.checkpoint_version_ordinal),
        ),
        conflict_trigger_messages=("kernel checkpoint identity is already retained",),
        conflict_probe=(
            f"SELECT {_CHECKPOINT_COLUMNS} FROM kernel_checkpoint"
            " WHERE application_generation_id = ?",
            lambda parameters: (parameters[0],),
        ),
    )


def advance_kernel_checkpoint(
    connection: _SQLiteConnectionProtocol,
    expected_version_ordinal: int,
    record: _records.KernelCheckpointRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _advance(
        connection,
        "UPDATE kernel_checkpoint SET currentness_head_ordinal = ?,"
        " checkpoint_sha256 = ?, checkpoint_version_ordinal = ?"
        " WHERE application_generation_id = ? AND checkpoint_version_ordinal = ?",
        lambda: (
            _exact_int(record.currentness_head_ordinal),
            _exact_text(record.checkpoint_sha256),
            _exact_int(record.checkpoint_version_ordinal),
            _application_id(record.application_generation_id),
            _exact_int(expected_version_ordinal),
        ),
    )


def load_kernel_checkpoint(
    connection: _SQLiteConnectionProtocol,
    application_generation_id: _identity.ApplicationGenerationId,
) -> _records.RepositoryOutcome[_records.KernelCheckpointRecord]:
    try:
        key = _application_id(application_generation_id)
    except (TypeError, ValueError):
        _verify_schema_connection(connection)
        return _integrity()
    return _load(
        connection,
        f"SELECT {_CHECKPOINT_COLUMNS} FROM kernel_checkpoint"
        " WHERE application_generation_id = ?",
        (key,),
        _build_checkpoint,
    )


_CONTROLLER_COLUMNS = (
    "scope_id, application_generation_id, execution_profile_id,"
    " live_acquisition_generation_id, aggregate_quantity, integrity_state,"
    " currentness_head_ordinal, controller_version_ordinal,"
    " emergency_compatibility_sha256"
)


def _build_controller(row: tuple[_Any, ...]) -> _records.SymbolControllerRecord:
    return _records.SymbolControllerRecord(
        _exact_int(row[0]),
        _decode_application_id(row[1]),
        _exact_text(row[2]),
        _decode_optional_identity(
            row[3],
            _identity.AcquisitionGenerationId,
            "acquisition_generation_id",
        ),
        _exact_int(row[4]),
        _exact_text(row[5]),
        _exact_int(row[6]),
        _exact_int(row[7]),
        _exact_text(row[8]),
    )


def _controller_parameters(record: _records.SymbolControllerRecord) -> tuple[_Any, ...]:
    return (
        _exact_int(record.scope_id),
        _application_id(record.application_generation_id),
        _exact_text(record.execution_profile_id),
        _optional_identity_text(
            record.live_acquisition_generation_id,
            _identity.AcquisitionGenerationId,
            "acquisition_generation_id",
        ),
        _exact_int(record.aggregate_quantity),
        _exact_text(record.integrity_state),
        _exact_int(record.currentness_head_ordinal),
        _exact_int(record.controller_version_ordinal),
        _exact_text(record.emergency_compatibility_sha256),
    )


def store_symbol_controller(
    connection: _SQLiteConnectionProtocol,
    record: _records.SymbolControllerRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO symbol_controller ({_CONTROLLER_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        lambda: _controller_parameters(record),
        conflict_trigger_messages=("symbol controller identity is already retained",),
        conflict_probe=(
            f"SELECT {_CONTROLLER_COLUMNS} FROM symbol_controller WHERE scope_id = ?",
            lambda parameters: (parameters[0],),
        ),
    )


def advance_symbol_controller(
    connection: _SQLiteConnectionProtocol,
    expected_version_ordinal: int,
    record: _records.SymbolControllerRecord,
) -> _records.RepositoryOutcome[_Any]:
    _verify_schema_connection(connection)
    try:
        values = _controller_parameters(record)
    except (TypeError, ValueError, OverflowError):
        return _integrity()
    authority_failure = _validate_advance_authority(
        connection,
        f"SELECT {_CONTROLLER_COLUMNS} FROM symbol_controller WHERE scope_id = ?",
        (values[0],),
        _build_controller,
        lambda retained: (
            retained.scope_id == record.scope_id
            and retained.application_generation_id == record.application_generation_id
            and retained.execution_profile_id == record.execution_profile_id
        ),
    )
    if authority_failure is not None:
        return authority_failure

    return _advance(
        connection,
        "UPDATE symbol_controller SET live_acquisition_generation_id = ?,"
        " aggregate_quantity = ?, integrity_state = ?, currentness_head_ordinal = ?,"
        " controller_version_ordinal = ?, emergency_compatibility_sha256 = ?"
        " WHERE scope_id = ? AND controller_version_ordinal = ?",
        lambda: (*values[3:], values[0], _exact_int(expected_version_ordinal)),
    )


def load_symbol_controller(
    connection: _SQLiteConnectionProtocol,
    scope_id: int,
) -> _records.RepositoryOutcome[_records.SymbolControllerRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_CONTROLLER_COLUMNS} FROM symbol_controller WHERE scope_id = ?",
        scope_id,
        _build_controller,
    )


_ROOT_FILL_COLUMNS = (
    "root_fill_key_id, scope_id, application_generation_id,"
    " execution_profile_id, owner_generation_id, root_fill_external,"
    " current_fact_id, current_kind, current_authority, current_side,"
    " current_quantity, price_present, price_units, scale_sign, scale_digits,"
    " scale_exponent, tick_units, tick_scale_sign, tick_scale_digits,"
    " tick_scale_exponent, economics_head_ordinal"
)


def _build_root_fill(row: tuple[_Any, ...]) -> _records.RootFillRecord:
    if len(row) != 21:
        raise ValueError("root fill row has the wrong shape")
    quantity = _decode_optional_quantity(row[10])
    price_values = tuple(row[11:20])
    if row[6] is None:
        if any(value is not None for value in row[7:20]) or quantity is not None:
            raise ValueError("unheaded root carries partial current economics")
        price = None
    else:
        if any(value is None for value in row[7:20]) or quantity is None:
            raise ValueError("headed root is missing current economics")
        price = _decode_price(price_values)
    return _records.RootFillRecord(
        _exact_int(row[0]),
        _exact_int(row[1]),
        _decode_application_id(row[2]),
        _exact_text(row[3]),
        _decode_acquisition_id(row[4]),
        _decode_identity(row[5], _identity.RootFillId, "root_fill_id"),
        _exact_optional_int(row[6]),
        _exact_optional_text(row[7]),
        _exact_optional_text(row[8]),
        _exact_optional_text(row[9]),
        quantity,
        price,
        _exact_int(row[20]),
    )


def store_root_fill(
    connection: _SQLiteConnectionProtocol,
    record: _records.RootFillRecord,
) -> _records.RepositoryOutcome[_Any]:
    def prepare() -> tuple[_Any, ...]:
        if (
            record.current_fact_id is not None
            or record.current_kind is not None
            or record.current_authority is not None
            or record.current_side is not None
            or record.current_quantity is not None
            or record.current_price is not None
            or record.economics_head_ordinal != 0
        ):
            raise ValueError("new root fill must not claim trigger-owned economics")
        return (
            _exact_int(record.root_fill_key_id),
            _exact_int(record.scope_id),
            _application_id(record.application_generation_id),
            _exact_text(record.execution_profile_id),
            _acquisition_id(record.owner_generation_id),
            _identity_text(record.root_fill_id, _identity.RootFillId, "root_fill_id"),
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            0,
        )

    return _insert(
        connection,
        f"INSERT INTO root_fill ({_ROOT_FILL_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        prepare,
        conflict_trigger_messages=("root fill identity is already retained",),
        conflict_probe=(
            f"SELECT {_ROOT_FILL_COLUMNS} FROM root_fill WHERE root_fill_key_id = ?"
            " OR (execution_profile_id = ? AND root_fill_external = ?)",
            lambda parameters: (parameters[0], parameters[3], parameters[5]),
        ),
    )


def load_root_fill(
    connection: _SQLiteConnectionProtocol,
    root_fill_key_id: int,
) -> _records.RepositoryOutcome[_records.RootFillRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_ROOT_FILL_COLUMNS} FROM root_fill WHERE root_fill_key_id = ?",
        root_fill_key_id,
        _build_root_fill,
    )


_EXECUTION_FACT_COLUMNS = (
    "fact_id, scope_id, application_generation_id, execution_profile_id,"
    " root_fill_key_id, source_event_id, order_external, side, kind, authority,"
    " quantity, price_present, price_units, scale_sign, scale_digits,"
    " scale_exponent, tick_units, tick_scale_sign, tick_scale_digits,"
    " tick_scale_exponent, request_occurrence_external, claim_occurrence_external,"
    " prior_cumulative_quantity, resulting_cumulative_quantity, actor_external,"
    " reason_text, evidence_reference_external, predecessor_fact_id, fact_ordinal"
)


def _build_execution_fact(row: tuple[_Any, ...]) -> _records.ExecutionFactRecord:
    if len(row) != 29:
        raise ValueError("execution fact row has the wrong shape")
    return _records.ExecutionFactRecord(
        _exact_int(row[0]),
        _exact_int(row[1]),
        _decode_application_id(row[2]),
        _exact_text(row[3]),
        _exact_int(row[4]),
        _decode_identity(row[5], _identity.SourceEventId, "source_event_id"),
        _decode_identity(row[6], _identity.OrderId, "order_id"),
        _exact_text(row[7]),
        _exact_text(row[8]),
        _exact_text(row[9]),
        _decode_quantity(row[10]),
        _decode_price(tuple(row[11:20])),
        _decode_optional_identity(
            row[20], _identity.RequestOccurrenceId, "request_occurrence_id"
        ),
        _decode_optional_identity(
            row[21], _identity.ClaimOccurrenceId, "claim_occurrence_id"
        ),
        _decode_optional_quantity(row[22]),
        _decode_optional_quantity(row[23]),
        _decode_optional_identity(row[24], _identity.ActorId, "actor_id"),
        _exact_optional_text(row[25]),
        _decode_optional_identity(
            row[26], _identity.EvidenceReference, "evidence_reference"
        ),
        _exact_optional_int(row[27]),
        _exact_int(row[28]),
    )


def store_execution_fact(
    connection: _SQLiteConnectionProtocol,
    record: _records.ExecutionFactRecord,
) -> _records.RepositoryOutcome[_Any]:
    def prepare() -> tuple[_Any, ...]:
        return (
            _exact_int(record.fact_id),
            _exact_int(record.scope_id),
            _application_id(record.application_generation_id),
            _exact_text(record.execution_profile_id),
            _exact_int(record.root_fill_key_id),
            _identity_text(
                record.source_event_id,
                _identity.SourceEventId,
                "source_event_id",
            ),
            _identity_text(record.order_id, _identity.OrderId, "order_id"),
            _exact_text(record.side),
            _exact_text(record.kind),
            _exact_text(record.authority),
            _quantity_value(record.quantity),
            *_price_columns(record.price),
            _optional_identity_text(
                record.request_occurrence_id,
                _identity.RequestOccurrenceId,
                "request_occurrence_id",
            ),
            _optional_identity_text(
                record.claim_occurrence_id,
                _identity.ClaimOccurrenceId,
                "claim_occurrence_id",
            ),
            None
            if record.prior_cumulative_quantity is None
            else _quantity_value(record.prior_cumulative_quantity),
            None
            if record.resulting_cumulative_quantity is None
            else _quantity_value(record.resulting_cumulative_quantity),
            _optional_identity_text(record.actor_id, _identity.ActorId, "actor_id"),
            None if record.reason_text is None else _exact_text(record.reason_text),
            _optional_identity_text(
                record.evidence_reference,
                _identity.EvidenceReference,
                "evidence_reference",
            ),
            _exact_optional_int(record.predecessor_fact_id),
            _exact_int(record.fact_ordinal),
        )

    return _insert(
        connection,
        f"INSERT INTO execution_fact ({_EXECUTION_FACT_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
        " ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        prepare,
        conflict_trigger_messages=("execution fact identity is already retained",),
        conflict_probe=(
            f"SELECT {_EXECUTION_FACT_COLUMNS} FROM execution_fact WHERE fact_id = ?"
            " OR (execution_profile_id = ? AND source_event_id = ?)",
            lambda parameters: (parameters[0], parameters[3], parameters[5]),
        ),
    )


def load_execution_fact(
    connection: _SQLiteConnectionProtocol,
    fact_id: int,
) -> _records.RepositoryOutcome[_records.ExecutionFactRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_EXECUTION_FACT_COLUMNS} FROM execution_fact WHERE fact_id = ?",
        fact_id,
        _build_execution_fact,
    )


_FACT_HEAD_COLUMNS = "root_fill_key_id, fact_id, fact_ordinal"


def _build_fact_head(row: tuple[_Any, ...]) -> _records.ExecutionFactHeadRecord:
    return _records.ExecutionFactHeadRecord(
        _exact_int(row[0]),
        _exact_int(row[1]),
        _exact_int(row[2]),
    )


def load_execution_fact_head(
    connection: _SQLiteConnectionProtocol,
    root_fill_key_id: int,
) -> _records.RepositoryOutcome[_records.ExecutionFactHeadRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_FACT_HEAD_COLUMNS} FROM execution_fact_head"
        " WHERE root_fill_key_id = ?",
        root_fill_key_id,
        _build_fact_head,
    )


_EFFECT_COLUMNS = (
    "effect_id, effect_external, scope_id, application_generation_id,"
    " execution_profile_id, acquisition_generation_id,"
    " generation_mandate_commitment_sha256, expected_controller_head_ordinal,"
    " expected_protection_version_ordinal, authority_class,"
    " request_occurrence_external, mandate_external, effect_kind,"
    " client_order_external, target_order_external, side, quantity,"
    " economic_scope, lifecycle_state, disposition, closure_proof_kind,"
    " closure_proof_digest, closure_proof_evidence_id, closure_proof_claim_id,"
    " created_ordinal"
)


def _build_effect(row: tuple[_Any, ...]) -> _records.VenueEffectRecord:
    if len(row) != 25:
        raise ValueError("venue effect row has the wrong shape")
    return _records.VenueEffectRecord(
        _exact_int(row[0]),
        _decode_identity(row[1], _identity.EffectId, "effect_id"),
        _exact_int(row[2]),
        _decode_application_id(row[3]),
        _exact_text(row[4]),
        _decode_acquisition_id(row[5]),
        _exact_text(row[6]),
        _exact_int(row[7]),
        _exact_int(row[8]),
        _exact_text(row[9]),
        _decode_identity(
            row[10], _identity.RequestOccurrenceId, "request_occurrence_id"
        ),
        _decode_identity(row[11], _identity.MandateId, "mandate_id"),
        _exact_text(row[12]),
        _decode_optional_identity(row[13], _identity.ClientOrderId, "client_order_id"),
        _decode_optional_identity(row[14], _identity.OrderId, "order_id"),
        _exact_text(row[15]),
        _decode_quantity(row[16]),
        _exact_bytes(row[17]),
        _exact_text(row[18]),
        _exact_text(row[19]),
        _exact_optional_text(row[20]),
        _exact_optional_text(row[21]),
        _exact_optional_int(row[22]),
        _exact_optional_int(row[23]),
        _exact_int(row[24]),
    )


def _effect_parameters(record: _records.VenueEffectRecord) -> tuple[_Any, ...]:
    return (
        _exact_int(record.effect_id),
        _identity_text(record.effect_external, _identity.EffectId, "effect_id"),
        _exact_int(record.scope_id),
        _application_id(record.application_generation_id),
        _exact_text(record.execution_profile_id),
        _acquisition_id(record.acquisition_generation_id),
        _exact_text(record.generation_mandate_commitment_sha256),
        _exact_int(record.expected_controller_head_ordinal),
        _exact_int(record.expected_protection_version_ordinal),
        _exact_text(record.authority_class),
        _identity_text(
            record.request_occurrence_id,
            _identity.RequestOccurrenceId,
            "request_occurrence_id",
        ),
        _identity_text(record.mandate_id, _identity.MandateId, "mandate_id"),
        _exact_text(record.effect_kind),
        _optional_identity_text(
            record.client_order_id,
            _identity.ClientOrderId,
            "client_order_id",
        ),
        _optional_identity_text(record.target_order_id, _identity.OrderId, "order_id"),
        _exact_text(record.side),
        _quantity_value(record.quantity),
        _exact_bytes(record.economic_scope),
        _exact_text(record.lifecycle_state),
        _exact_text(record.disposition),
        None
        if record.closure_proof_kind is None
        else _exact_text(record.closure_proof_kind),
        None
        if record.closure_proof_digest is None
        else _exact_text(record.closure_proof_digest),
        _exact_optional_int(record.closure_proof_evidence_id),
        _exact_optional_int(record.closure_proof_claim_id),
        _exact_int(record.created_ordinal),
    )


def _effect_immutable_coordinates(
    record: _records.VenueEffectRecord,
) -> tuple[_Any, ...]:
    return (
        record.effect_id,
        record.effect_external,
        record.scope_id,
        record.application_generation_id,
        record.execution_profile_id,
        record.acquisition_generation_id,
        record.generation_mandate_commitment_sha256,
        record.expected_controller_head_ordinal,
        record.expected_protection_version_ordinal,
        record.authority_class,
        record.request_occurrence_id,
        record.mandate_id,
        record.effect_kind,
        record.client_order_id,
        record.target_order_id,
        record.side,
        record.quantity,
        record.economic_scope,
        record.created_ordinal,
    )


def store_venue_effect(
    connection: _SQLiteConnectionProtocol,
    record: _records.VenueEffectRecord,
) -> _records.RepositoryOutcome[_Any]:
    def prepare() -> tuple[_Any, ...]:
        if (
            record.lifecycle_state != "REQUESTED"
            or record.disposition != "OPEN"
            or record.closure_proof_kind is not None
            or record.closure_proof_digest is not None
            or record.closure_proof_evidence_id is not None
            or record.closure_proof_claim_id is not None
        ):
            raise ValueError("new effect must start open without closure proof")
        return _effect_parameters(record)

    return _insert(
        connection,
        f"INSERT INTO venue_effect ({_EFFECT_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
        " ?, ?, ?, ?, ?)",
        prepare,
        conflict_trigger_messages=("venue effect identity is already retained",),
        conflict_probe=(
            f"SELECT {_EFFECT_COLUMNS} FROM venue_effect WHERE effect_id = ?"
            " OR (execution_profile_id = ? AND effect_external = ?)"
            " OR (execution_profile_id = ? AND request_occurrence_external = ?)"
            " OR (? IS NOT NULL AND execution_profile_id = ?"
            " AND client_order_external = ?)",
            lambda parameters: (
                parameters[0],
                parameters[4],
                parameters[1],
                parameters[4],
                parameters[10],
                parameters[13],
                parameters[4],
                parameters[13],
            ),
        ),
    )


def advance_venue_effect(
    connection: _SQLiteConnectionProtocol,
    expected_lifecycle_state: str,
    expected_disposition: str,
    record: _records.VenueEffectRecord,
) -> _records.RepositoryOutcome[_Any]:
    _verify_schema_connection(connection)
    try:
        parameters = _effect_parameters(record)
    except (TypeError, ValueError, OverflowError):
        return _integrity()
    authority_failure = _validate_advance_authority(
        connection,
        f"SELECT {_EFFECT_COLUMNS} FROM venue_effect WHERE effect_id = ?",
        (parameters[0],),
        _build_effect,
        lambda retained: (
            _effect_immutable_coordinates(retained)
            == _effect_immutable_coordinates(record)
        ),
    )
    if authority_failure is not None:
        return authority_failure
    return _advance(
        connection,
        "UPDATE venue_effect SET lifecycle_state = ?, disposition = ?,"
        " closure_proof_kind = ?, closure_proof_digest = ?,"
        " closure_proof_evidence_id = ?, closure_proof_claim_id = ?"
        " WHERE effect_id = ? AND lifecycle_state = ? AND disposition = ?",
        lambda: (
            _exact_text(record.lifecycle_state),
            _exact_text(record.disposition),
            None
            if record.closure_proof_kind is None
            else _exact_text(record.closure_proof_kind),
            None
            if record.closure_proof_digest is None
            else _exact_text(record.closure_proof_digest),
            _exact_optional_int(record.closure_proof_evidence_id),
            _exact_optional_int(record.closure_proof_claim_id),
            _exact_int(record.effect_id),
            _exact_text(expected_lifecycle_state),
            _exact_text(expected_disposition),
        ),
    )


def load_venue_effect(
    connection: _SQLiteConnectionProtocol,
    effect_id: int,
) -> _records.RepositoryOutcome[_records.VenueEffectRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_EFFECT_COLUMNS} FROM venue_effect WHERE effect_id = ?",
        effect_id,
        _build_effect,
    )


_OWNER_COLUMNS = (
    "scope_id, execution_profile_id, owner_external, observation_external,"
    " effect_id, root_fill_key_id, owner_generation_id,"
    " admitted_after_effect_closed"
)


def _build_owner(row: tuple[_Any, ...]) -> _records.VenueIdentityOwnerRecord:
    admitted = _exact_int(row[7])
    if admitted not in (0, 1):
        raise ValueError("owner admission flag is not canonical")
    return _records.VenueIdentityOwnerRecord(
        _exact_int(row[0]),
        _exact_text(row[1]),
        _decode_identity(row[2], _identity.OrderId, "order_id"),
        _decode_identity(row[3], _identity.VenueObservationId, "venue_observation_id"),
        _exact_int(row[4]),
        _exact_optional_int(row[5]),
        _decode_acquisition_id(row[6]),
        bool(admitted),
    )


def store_venue_identity_owner(
    connection: _SQLiteConnectionProtocol,
    record: _records.VenueIdentityOwnerRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO venue_identity_owner ({_OWNER_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        lambda: (
            _exact_int(record.scope_id),
            _exact_text(record.execution_profile_id),
            _identity_text(record.owner_id, _identity.OrderId, "order_id"),
            _identity_text(
                record.observation_id,
                _identity.VenueObservationId,
                "venue_observation_id",
            ),
            _exact_int(record.effect_id),
            _exact_optional_int(record.root_fill_key_id),
            _acquisition_id(record.owner_generation_id),
            int(record.admitted_after_effect_closed)
            if type(record.admitted_after_effect_closed) is bool
            else (_ for _ in ()).throw(TypeError("admission flag must be bool")),
        ),
        conflict_trigger_messages=("venue owner identity is already retained",),
        conflict_probe=(
            f"SELECT {_OWNER_COLUMNS} FROM venue_identity_owner"
            " WHERE execution_profile_id = ? AND owner_external = ?",
            lambda parameters: (parameters[1], parameters[2]),
        ),
    )


def load_venue_identity_owner(
    connection: _SQLiteConnectionProtocol,
    execution_profile_id: str,
    owner_id: _identity.OrderId,
) -> _records.RepositoryOutcome[_records.VenueIdentityOwnerRecord]:
    _verify_schema_connection(connection)
    try:
        profile_key = _exact_text(execution_profile_id)
        owner_text = _identity_text(owner_id, _identity.OrderId, "order_id")
    except (TypeError, ValueError):
        return _integrity()
    return _select_one_unchecked(
        connection,
        f"SELECT {_OWNER_COLUMNS} FROM venue_identity_owner"
        " WHERE execution_profile_id = ? AND owner_external = ?",
        (profile_key, owner_text),
        _build_owner,
    )


_ROUTE_COLUMNS = (
    "root_fill_key_id, scope_id, application_generation_id, execution_profile_id,"
    " acquisition_generation_id, effect_id, owner_external, observation_external"
)


def _build_route(row: tuple[_Any, ...]) -> _records.AcquisitionRootRouteRecord:
    return _records.AcquisitionRootRouteRecord(
        _exact_int(row[0]),
        _exact_int(row[1]),
        _decode_application_id(row[2]),
        _exact_text(row[3]),
        _decode_acquisition_id(row[4]),
        _exact_int(row[5]),
        _decode_identity(row[6], _identity.OrderId, "order_id"),
        _decode_identity(row[7], _identity.VenueObservationId, "venue_observation_id"),
    )


def store_acquisition_root_route(
    connection: _SQLiteConnectionProtocol,
    record: _records.AcquisitionRootRouteRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO acquisition_root_route ({_ROUTE_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        lambda: (
            _exact_int(record.root_fill_key_id),
            _exact_int(record.scope_id),
            _application_id(record.application_generation_id),
            _exact_text(record.execution_profile_id),
            _acquisition_id(record.acquisition_generation_id),
            _exact_int(record.effect_id),
            _identity_text(record.owner_id, _identity.OrderId, "order_id"),
            _identity_text(
                record.observation_id,
                _identity.VenueObservationId,
                "venue_observation_id",
            ),
        ),
        conflict_trigger_messages=("acquisition root route is already retained",),
        conflict_probe=(
            f"SELECT {_ROUTE_COLUMNS} FROM acquisition_root_route"
            " WHERE root_fill_key_id = ?",
            lambda parameters: (parameters[0],),
        ),
    )


def load_acquisition_root_route(
    connection: _SQLiteConnectionProtocol,
    root_fill_key_id: int,
) -> _records.RepositoryOutcome[_records.AcquisitionRootRouteRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_ROUTE_COLUMNS} FROM acquisition_root_route"
        " WHERE root_fill_key_id = ?",
        root_fill_key_id,
        _build_route,
    )


_CLAIM_COLUMNS = (
    "claim_id, effect_id, execution_profile_id, claim_occurrence_external,"
    " claim_ordinal"
)


def _build_claim(row: tuple[_Any, ...]) -> _records.DispatchClaimRecord:
    return _records.DispatchClaimRecord(
        _exact_int(row[0]),
        _exact_int(row[1]),
        _exact_text(row[2]),
        _decode_identity(row[3], _identity.ClaimOccurrenceId, "claim_occurrence_id"),
        _exact_int(row[4]),
    )


def store_dispatch_claim(
    connection: _SQLiteConnectionProtocol,
    record: _records.DispatchClaimRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO dispatch_claim ({_CLAIM_COLUMNS}) VALUES (?, ?, ?, ?, ?)",
        lambda: (
            _exact_int(record.claim_id),
            _exact_int(record.effect_id),
            _exact_text(record.execution_profile_id),
            _identity_text(
                record.claim_occurrence_id,
                _identity.ClaimOccurrenceId,
                "claim_occurrence_id",
            ),
            _exact_int(record.claim_ordinal),
        ),
        conflict_trigger_messages=("dispatch claim identity is already retained",),
        conflict_probe=(
            f"SELECT {_CLAIM_COLUMNS} FROM dispatch_claim"
            " WHERE claim_id = ? OR effect_id = ?"
            " OR (execution_profile_id = ? AND claim_occurrence_external = ?)",
            lambda parameters: (
                parameters[0],
                parameters[1],
                parameters[2],
                parameters[3],
            ),
        ),
    )


def load_dispatch_claim(
    connection: _SQLiteConnectionProtocol,
    claim_id: int,
) -> _records.RepositoryOutcome[_records.DispatchClaimRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_CLAIM_COLUMNS} FROM dispatch_claim WHERE claim_id = ?",
        claim_id,
        _build_claim,
    )


_ACCEPTANCE_SET_COLUMNS = "acceptance_set_id, effect_id"


def _build_acceptance_set(row: tuple[_Any, ...]) -> _records.AcceptanceSetRecord:
    return _records.AcceptanceSetRecord(_exact_int(row[0]), _exact_int(row[1]))


def store_acceptance_set(
    connection: _SQLiteConnectionProtocol,
    record: _records.AcceptanceSetRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO acceptance_set ({_ACCEPTANCE_SET_COLUMNS}) VALUES (?, ?)",
        lambda: (
            _exact_int(record.acceptance_set_id),
            _exact_int(record.effect_id),
        ),
        conflict_trigger_messages=("acceptance set identity is already retained",),
        conflict_probe=(
            f"SELECT {_ACCEPTANCE_SET_COLUMNS} FROM acceptance_set"
            " WHERE acceptance_set_id = ? OR effect_id = ?",
            lambda parameters: (parameters[0], parameters[1]),
        ),
    )


def load_acceptance_set(
    connection: _SQLiteConnectionProtocol,
    acceptance_set_id: int,
) -> _records.RepositoryOutcome[_records.AcceptanceSetRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_ACCEPTANCE_SET_COLUMNS} FROM acceptance_set"
        " WHERE acceptance_set_id = ?",
        acceptance_set_id,
        _build_acceptance_set,
    )


_EVIDENCE_COLUMNS = (
    "evidence_id, acceptance_set_id, effect_id, evidence_kind, proof_kind,"
    " evidence_digest, evidence_ordinal, contradiction_owner_external,"
    " contradiction_observation_external"
)


def _build_evidence(row: tuple[_Any, ...]) -> _records.AcceptanceEvidenceRecord:
    return _records.AcceptanceEvidenceRecord(
        _exact_int(row[0]),
        _exact_int(row[1]),
        _exact_int(row[2]),
        _exact_text(row[3]),
        _exact_optional_text(row[4]),
        _exact_text(row[5]),
        _exact_int(row[6]),
        _decode_optional_identity(row[7], _identity.OrderId, "order_id"),
        _decode_optional_identity(
            row[8],
            _identity.VenueObservationId,
            "venue_observation_id",
        ),
    )


def store_acceptance_evidence(
    connection: _SQLiteConnectionProtocol,
    record: _records.AcceptanceEvidenceRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO acceptance_evidence ({_EVIDENCE_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        lambda: (
            _exact_int(record.evidence_id),
            _exact_int(record.acceptance_set_id),
            _exact_int(record.effect_id),
            _exact_text(record.evidence_kind),
            None if record.proof_kind is None else _exact_text(record.proof_kind),
            _exact_text(record.evidence_digest),
            _exact_int(record.evidence_ordinal),
            _optional_identity_text(
                record.contradiction_owner_id,
                _identity.OrderId,
                "order_id",
            ),
            _optional_identity_text(
                record.contradiction_observation_id,
                _identity.VenueObservationId,
                "venue_observation_id",
            ),
        ),
        conflict_trigger_messages=("acceptance evidence identity is already retained",),
        conflict_probe=(
            f"SELECT {_EVIDENCE_COLUMNS} FROM acceptance_evidence"
            " WHERE evidence_id = ? OR evidence_ordinal = ?"
            " OR (? = 'INVALIDATION' AND evidence_kind = 'INVALIDATION'"
            " AND effect_id = ? AND contradiction_owner_external = ?"
            " AND contradiction_observation_external = ?)",
            lambda parameters: (
                parameters[0],
                parameters[6],
                parameters[3],
                parameters[2],
                parameters[7],
                parameters[8],
            ),
        ),
    )


def load_acceptance_evidence(
    connection: _SQLiteConnectionProtocol,
    evidence_id: int,
) -> _records.RepositoryOutcome[_records.AcceptanceEvidenceRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_EVIDENCE_COLUMNS} FROM acceptance_evidence WHERE evidence_id = ?",
        evidence_id,
        _build_evidence,
    )


_CLOSURE_COLUMNS = (
    "closure_id, scope_id, owner_external, ordinal, effect_id, closure_kind,"
    " predecessor_closure_id"
)


def _build_closure(row: tuple[_Any, ...]) -> _records.ClosureChainRecord:
    return _records.ClosureChainRecord(
        _exact_int(row[0]),
        _exact_int(row[1]),
        _decode_identity(row[2], _identity.OrderId, "order_id"),
        _exact_int(row[3]),
        _exact_int(row[4]),
        _exact_text(row[5]),
        _exact_optional_int(row[6]),
    )


def store_closure(
    connection: _SQLiteConnectionProtocol,
    record: _records.ClosureChainRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO closure_chain ({_CLOSURE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
        lambda: (
            _exact_int(record.closure_id),
            _exact_int(record.scope_id),
            _identity_text(record.owner_id, _identity.OrderId, "order_id"),
            _exact_int(record.ordinal),
            _exact_int(record.effect_id),
            _exact_text(record.closure_kind),
            _exact_optional_int(record.predecessor_closure_id),
        ),
        conflict_trigger_messages=("closure identity is already retained",),
        conflict_probe=(
            f"SELECT {_CLOSURE_COLUMNS} FROM closure_chain WHERE closure_id = ?"
            " OR (scope_id = ? AND owner_external = ?"
            " AND ((? IS NOT NULL AND predecessor_closure_id = ?)"
            " OR (? IS NULL AND predecessor_closure_id IS NULL)))",
            lambda parameters: (
                parameters[0],
                parameters[1],
                parameters[2],
                parameters[6],
                parameters[6],
                parameters[6],
            ),
        ),
    )


def load_closure_head(
    connection: _SQLiteConnectionProtocol,
    scope_id: int,
    owner_id: _identity.OrderId,
) -> _records.RepositoryOutcome[_records.ClosureChainRecord]:
    _verify_schema_connection(connection)
    try:
        scope_key = _exact_int(scope_id)
        owner_text = _identity_text(owner_id, _identity.OrderId, "order_id")
    except (TypeError, ValueError):
        return _integrity()
    return _select_one_unchecked(
        connection,
        f"SELECT {_CLOSURE_COLUMNS} FROM closure_chain"
        " WHERE scope_id = ? AND owner_external = ?"
        " ORDER BY ordinal DESC LIMIT 1",
        (scope_key, owner_text),
        _build_closure,
    )


_MARKET_STREAM_COLUMNS = (
    "stream_generation_id, scope_id, application_generation_id,"
    " acquisition_generation_id, generation_mandate_commitment_sha256,"
    " source_profile_id, session_external, sequence_mode"
)


def _build_market_stream(row: tuple[_Any, ...]) -> _records.MarketStreamAuthorityRecord:
    return _records.MarketStreamAuthorityRecord(
        _decode_identity(
            row[0],
            _identity.MarketStreamGenerationId,
            "market_stream_generation_id",
        ),
        _exact_int(row[1]),
        _decode_application_id(row[2]),
        _decode_acquisition_id(row[3]),
        _exact_text(row[4]),
        _exact_text(row[5]),
        _decode_identity(row[6], _identity.SessionId, "session_id"),
        _exact_text(row[7]),
    )


def _stream_id(value: object) -> str:
    return _identity_text(
        value,
        _identity.MarketStreamGenerationId,
        "market_stream_generation_id",
    )


def store_market_stream_authority(
    connection: _SQLiteConnectionProtocol,
    record: _records.MarketStreamAuthorityRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO market_stream_authority ({_MARKET_STREAM_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        lambda: (
            _stream_id(record.stream_generation_id),
            _exact_int(record.scope_id),
            _application_id(record.application_generation_id),
            _acquisition_id(record.acquisition_generation_id),
            _exact_text(record.generation_mandate_commitment_sha256),
            _exact_text(record.source_profile_id),
            _identity_text(record.session_id, _identity.SessionId, "session_id"),
            _exact_text(record.sequence_mode),
        ),
        conflict_trigger_messages=("market stream identity is already retained",),
        conflict_probe=(
            f"SELECT {_MARKET_STREAM_COLUMNS} FROM market_stream_authority"
            " WHERE stream_generation_id = ?",
            lambda parameters: (parameters[0],),
        ),
    )


def load_market_stream_authority(
    connection: _SQLiteConnectionProtocol,
    stream_generation_id: _identity.MarketStreamGenerationId,
) -> _records.RepositoryOutcome[_records.MarketStreamAuthorityRecord]:
    try:
        key = _stream_id(stream_generation_id)
    except (TypeError, ValueError):
        _verify_schema_connection(connection)
        return _integrity()
    return _load(
        connection,
        f"SELECT {_MARKET_STREAM_COLUMNS} FROM market_stream_authority"
        " WHERE stream_generation_id = ?",
        (key,),
        _build_market_stream,
    )


_MARKET_CURSOR_COLUMNS = (
    "stream_generation_id, scope_id, application_generation_id,"
    " acquisition_generation_id, generation_mandate_commitment_sha256,"
    " source_profile_id, session_external, sequence_mode, fixed_cursor_ordinal,"
    " published_head_ordinal"
)


def _build_market_cursor(row: tuple[_Any, ...]) -> _records.MarketCursorRecord:
    return _records.MarketCursorRecord(
        _decode_identity(
            row[0],
            _identity.MarketStreamGenerationId,
            "market_stream_generation_id",
        ),
        _exact_int(row[1]),
        _decode_application_id(row[2]),
        _decode_acquisition_id(row[3]),
        _exact_text(row[4]),
        _exact_text(row[5]),
        _decode_identity(row[6], _identity.SessionId, "session_id"),
        _exact_text(row[7]),
        _exact_int(row[8]),
        _exact_int(row[9]),
    )


def _cursor_parameters(record: _records.MarketCursorRecord) -> tuple[_Any, ...]:
    return (
        _stream_id(record.stream_generation_id),
        _exact_int(record.scope_id),
        _application_id(record.application_generation_id),
        _acquisition_id(record.acquisition_generation_id),
        _exact_text(record.generation_mandate_commitment_sha256),
        _exact_text(record.source_profile_id),
        _identity_text(record.session_id, _identity.SessionId, "session_id"),
        _exact_text(record.sequence_mode),
        _exact_int(record.fixed_cursor_ordinal),
        _exact_int(record.published_head_ordinal),
    )


def _cursor_immutable_coordinates(
    record: _records.MarketCursorRecord,
) -> tuple[_Any, ...]:
    return (
        record.stream_generation_id,
        record.scope_id,
        record.application_generation_id,
        record.acquisition_generation_id,
        record.generation_mandate_commitment_sha256,
        record.source_profile_id,
        record.session_id,
        record.sequence_mode,
    )


def store_market_cursor(
    connection: _SQLiteConnectionProtocol,
    record: _records.MarketCursorRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO market_cursor ({_MARKET_CURSOR_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        lambda: _cursor_parameters(record),
        conflict_trigger_messages=("market cursor identity is already retained",),
        conflict_probe=(
            f"SELECT {_MARKET_CURSOR_COLUMNS} FROM market_cursor"
            " WHERE stream_generation_id = ?",
            lambda parameters: (parameters[0],),
        ),
    )


def advance_market_cursor(
    connection: _SQLiteConnectionProtocol,
    expected_fixed_cursor_ordinal: int,
    expected_published_head_ordinal: int,
    record: _records.MarketCursorRecord,
) -> _records.RepositoryOutcome[_Any]:
    _verify_schema_connection(connection)
    try:
        parameters = _cursor_parameters(record)
    except (TypeError, ValueError, OverflowError):
        return _integrity()
    authority_failure = _validate_advance_authority(
        connection,
        f"SELECT {_MARKET_CURSOR_COLUMNS} FROM market_cursor"
        " WHERE stream_generation_id = ?",
        (parameters[0],),
        _build_market_cursor,
        lambda retained: (
            _cursor_immutable_coordinates(retained)
            == _cursor_immutable_coordinates(record)
        ),
    )
    if authority_failure is not None:
        return authority_failure
    return _advance(
        connection,
        "UPDATE market_cursor SET fixed_cursor_ordinal = ?,"
        " published_head_ordinal = ? WHERE stream_generation_id = ?"
        " AND fixed_cursor_ordinal = ? AND published_head_ordinal = ?",
        lambda: (
            _exact_int(record.fixed_cursor_ordinal),
            _exact_int(record.published_head_ordinal),
            _stream_id(record.stream_generation_id),
            _exact_int(expected_fixed_cursor_ordinal),
            _exact_int(expected_published_head_ordinal),
        ),
    )


def load_market_cursor(
    connection: _SQLiteConnectionProtocol,
    stream_generation_id: _identity.MarketStreamGenerationId,
) -> _records.RepositoryOutcome[_records.MarketCursorRecord]:
    try:
        key = _stream_id(stream_generation_id)
    except (TypeError, ValueError):
        _verify_schema_connection(connection)
        return _integrity()
    return _load(
        connection,
        f"SELECT {_MARKET_CURSOR_COLUMNS} FROM market_cursor"
        " WHERE stream_generation_id = ?",
        (key,),
        _build_market_cursor,
    )


_PROTECTION_COLUMNS = (
    "scope_id, authority_class, active_stream_generation_id,"
    " active_acquisition_generation_id,"
    " active_generation_mandate_commitment_sha256, active_source_profile_id,"
    " active_session_external, active_sequence_mode,"
    " expected_controller_head_ordinal, state_commitment_sha256, version_ordinal"
)


def _build_protection(row: tuple[_Any, ...]) -> _records.ProtectionAuthorityRecord:
    return _records.ProtectionAuthorityRecord(
        _exact_int(row[0]),
        _exact_text(row[1]),
        _decode_optional_identity(
            row[2],
            _identity.MarketStreamGenerationId,
            "market_stream_generation_id",
        ),
        _decode_optional_identity(
            row[3],
            _identity.AcquisitionGenerationId,
            "acquisition_generation_id",
        ),
        _exact_optional_text(row[4]),
        _exact_optional_text(row[5]),
        _decode_optional_identity(row[6], _identity.SessionId, "session_id"),
        _exact_optional_text(row[7]),
        _exact_int(row[8]),
        _exact_text(row[9]),
        _exact_int(row[10]),
    )


def _protection_parameters(
    record: _records.ProtectionAuthorityRecord,
) -> tuple[_Any, ...]:
    return (
        _exact_int(record.scope_id),
        _exact_text(record.authority_class),
        _optional_identity_text(
            record.active_stream_generation_id,
            _identity.MarketStreamGenerationId,
            "market_stream_generation_id",
        ),
        _optional_identity_text(
            record.active_acquisition_generation_id,
            _identity.AcquisitionGenerationId,
            "acquisition_generation_id",
        ),
        None
        if record.active_generation_mandate_commitment_sha256 is None
        else _exact_text(record.active_generation_mandate_commitment_sha256),
        None
        if record.active_source_profile_id is None
        else _exact_text(record.active_source_profile_id),
        _optional_identity_text(
            record.active_session_id, _identity.SessionId, "session_id"
        ),
        None
        if record.active_sequence_mode is None
        else _exact_text(record.active_sequence_mode),
        _exact_int(record.expected_controller_head_ordinal),
        _exact_text(record.state_commitment_sha256),
        _exact_int(record.version_ordinal),
    )


def store_protection_authority(
    connection: _SQLiteConnectionProtocol,
    record: _records.ProtectionAuthorityRecord,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        connection,
        f"INSERT INTO protection_authority ({_PROTECTION_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        lambda: _protection_parameters(record),
        conflict_trigger_messages=(
            "protection_authority identity is already retained",
        ),
        conflict_probe=(
            f"SELECT {_PROTECTION_COLUMNS} FROM protection_authority"
            " WHERE scope_id = ?",
            lambda parameters: (parameters[0],),
        ),
    )


def advance_protection_authority(
    connection: _SQLiteConnectionProtocol,
    expected_version_ordinal: int,
    record: _records.ProtectionAuthorityRecord,
) -> _records.RepositoryOutcome[_Any]:
    def prepare() -> tuple[_Any, ...]:
        values = _protection_parameters(record)
        return (*values[1:], values[0], _exact_int(expected_version_ordinal))

    return _advance(
        connection,
        "UPDATE protection_authority SET authority_class = ?,"
        " active_stream_generation_id = ?, active_acquisition_generation_id = ?,"
        " active_generation_mandate_commitment_sha256 = ?,"
        " active_source_profile_id = ?, active_session_external = ?,"
        " active_sequence_mode = ?, expected_controller_head_ordinal = ?,"
        " state_commitment_sha256 = ?, version_ordinal = ?"
        " WHERE scope_id = ? AND version_ordinal = ?",
        prepare,
    )


def load_protection_authority(
    connection: _SQLiteConnectionProtocol,
    scope_id: int,
) -> _records.RepositoryOutcome[_records.ProtectionAuthorityRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_PROTECTION_COLUMNS} FROM protection_authority WHERE scope_id = ?",
        scope_id,
        _build_protection,
    )


def _select_many_unchecked(
    connection: _SQLiteConnectionProtocol,
    sql: str,
    parameters: tuple[_Any, ...],
    build: _Callable[[tuple[_Any, ...]], _RecordT],
) -> _records.RepositoryOutcome[tuple[_RecordT, ...]]:
    try:
        rows = connection.execute(sql, _query_parameters(parameters)).fetchall()
        if not rows:
            return _outcome(_records.RepositoryOutcomeKind.ABSENT)
        records = tuple(build(tuple(row)) for row in rows)
        return _outcome(_records.RepositoryOutcomeKind.FOUND, records)
    except (TypeError, ValueError, OverflowError, IndexError):
        return _integrity()
    except Exception as caught:
        return _classify_sqlite_failure(caught)


def load_live_acquisition_generation(
    connection: _SQLiteConnectionProtocol,
    scope_id: int,
) -> _records.RepositoryOutcome[_records.AcquisitionGenerationRecord]:
    _verify_schema_connection(connection)
    try:
        scope_key = _exact_int(scope_id)
    except TypeError:
        return _integrity()
    return _select_one_unchecked(
        connection,
        f"SELECT {_ACQUISITION_COLUMNS} FROM acquisition_generation"
        " WHERE scope_id = ? AND status = 'LIVE'",
        (scope_key,),
        _build_acquisition,
    )


def load_root_fill_by_external(
    connection: _SQLiteConnectionProtocol,
    execution_profile_id: str,
    root_fill_id: _identity.RootFillId,
) -> _records.RepositoryOutcome[_records.RootFillRecord]:
    _verify_schema_connection(connection)
    try:
        profile_key = _exact_text(execution_profile_id)
        external = _identity_text(root_fill_id, _identity.RootFillId, "root_fill_id")
    except (TypeError, ValueError):
        return _integrity()
    return _select_one_unchecked(
        connection,
        f"SELECT {_ROOT_FILL_COLUMNS} FROM root_fill"
        " WHERE execution_profile_id = ? AND root_fill_external = ?",
        (profile_key, external),
        _build_root_fill,
    )


def load_execution_fact_by_source(
    connection: _SQLiteConnectionProtocol,
    execution_profile_id: str,
    source_event_id: _identity.SourceEventId,
) -> _records.RepositoryOutcome[_records.ExecutionFactRecord]:
    _verify_schema_connection(connection)
    try:
        profile_key = _exact_text(execution_profile_id)
        external = _identity_text(
            source_event_id,
            _identity.SourceEventId,
            "source_event_id",
        )
    except (TypeError, ValueError):
        return _integrity()
    return _select_one_unchecked(
        connection,
        f"SELECT {_EXECUTION_FACT_COLUMNS} FROM execution_fact"
        " WHERE execution_profile_id = ? AND source_event_id = ?",
        (profile_key, external),
        _build_execution_fact,
    )


def load_open_venue_effects(
    connection: _SQLiteConnectionProtocol,
    scope_id: int,
) -> _records.RepositoryOutcome[tuple[_records.VenueEffectRecord, ...]]:
    _verify_schema_connection(connection)
    try:
        scope_key = _exact_int(scope_id)
    except TypeError:
        return _integrity()
    return _select_many_unchecked(
        connection,
        f"SELECT {_EFFECT_COLUMNS} FROM venue_effect"
        " WHERE scope_id = ? AND disposition = 'OPEN' ORDER BY effect_id",
        (scope_key,),
        _build_effect,
    )


def load_venue_identity_owners_for_effect(
    connection: _SQLiteConnectionProtocol,
    effect_id: int,
) -> _records.RepositoryOutcome[tuple[_records.VenueIdentityOwnerRecord, ...]]:
    _verify_schema_connection(connection)
    try:
        effect_key = _exact_int(effect_id)
    except TypeError:
        return _integrity()
    return _select_many_unchecked(
        connection,
        f"SELECT {_OWNER_COLUMNS} FROM venue_identity_owner"
        " WHERE effect_id = ? ORDER BY owner_external",
        (effect_key,),
        _build_owner,
    )


def load_dispatch_claim_for_effect(
    connection: _SQLiteConnectionProtocol,
    effect_id: int,
) -> _records.RepositoryOutcome[_records.DispatchClaimRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_CLAIM_COLUMNS} FROM dispatch_claim WHERE effect_id = ?",
        effect_id,
        _build_claim,
    )


def load_acceptance_set_for_effect(
    connection: _SQLiteConnectionProtocol,
    effect_id: int,
) -> _records.RepositoryOutcome[_records.AcceptanceSetRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_ACCEPTANCE_SET_COLUMNS} FROM acceptance_set WHERE effect_id = ?",
        effect_id,
        _build_acceptance_set,
    )


def load_latest_acceptance_evidence(
    connection: _SQLiteConnectionProtocol,
    acceptance_set_id: int,
) -> _records.RepositoryOutcome[_records.AcceptanceEvidenceRecord]:
    return _load_int_key(
        connection,
        f"SELECT {_EVIDENCE_COLUMNS} FROM acceptance_evidence"
        " WHERE acceptance_set_id = ? ORDER BY evidence_ordinal DESC LIMIT 1",
        acceptance_set_id,
        _build_evidence,
    )


class _ProofFailure(Exception):
    pass


def _required(
    outcome: _records.RepositoryOutcome[_RecordT],
) -> _RecordT:
    if (
        outcome.kind is not _records.RepositoryOutcomeKind.FOUND
        or outcome.record is None
    ):
        raise _ProofFailure
    return outcome.record


def load_current_proof(
    connection: _SQLiteConnectionProtocol,
    request: _records.CurrentProofRequest,
) -> _records.RepositoryOutcome[_records.CurrentProofSlice]:
    """Load one total exact-key proof without folding explanatory history."""

    _verify_schema_connection(connection)
    try:
        if type(request) is not _records.CurrentProofRequest:
            raise _ProofFailure
        application_key = _application_id(request.application_generation_id)
        scope_key = _exact_int(request.scope_id)
        if (
            type(request.require_acceptance) is not bool
            or type(request.require_closure) is not bool
        ):
            raise _ProofFailure

        application = _required(
            _select_one_unchecked(
                connection,
                f"SELECT {_APPLICATION_COLUMNS} FROM application_generation"
                " WHERE application_generation_id = ?",
                (application_key,),
                _build_application,
            )
        )
        scope = _required(
            _select_one_unchecked(
                connection,
                f"SELECT {_SCOPE_COLUMNS} FROM acquisition_scope WHERE scope_id = ?",
                (scope_key,),
                _build_scope,
            )
        )
        execution_profile = _required(
            _select_one_unchecked(
                connection,
                f"SELECT {_EXECUTION_PROFILE_COLUMNS} FROM execution_connection_profile"
                " WHERE connection_profile_id = ?",
                (application.selected_execution_profile_id,),
                _build_execution_profile,
            )
        )
        market_profile = _required(
            _select_one_unchecked(
                connection,
                f"SELECT {_MARKET_PROFILE_COLUMNS} FROM market_data_source_profile"
                " WHERE market_source_profile_id = ?",
                (application.selected_market_source_profile_id,),
                _build_market_profile,
            )
        )
        checkpoint = _required(
            _select_one_unchecked(
                connection,
                f"SELECT {_CHECKPOINT_COLUMNS} FROM kernel_checkpoint"
                " WHERE application_generation_id = ?",
                (application_key,),
                _build_checkpoint,
            )
        )
        controller = _required(
            _select_one_unchecked(
                connection,
                f"SELECT {_CONTROLLER_COLUMNS} FROM symbol_controller WHERE scope_id = ?",
                (scope_key,),
                _build_controller,
            )
        )
        if controller.live_acquisition_generation_id is None:
            raise _ProofFailure
        live_generation = _required(
            _select_one_unchecked(
                connection,
                f"SELECT {_ACQUISITION_COLUMNS} FROM acquisition_generation"
                " WHERE scope_id = ? AND status = 'LIVE'",
                (scope_key,),
                _build_acquisition,
            )
        )
        generation_current = _required(
            _select_one_unchecked(
                connection,
                f"SELECT {_ACQUISITION_CURRENT_COLUMNS}"
                " FROM acquisition_generation_current"
                " WHERE acquisition_generation_id = ?",
                (_acquisition_id(live_generation.acquisition_generation_id),),
                _build_acquisition_current,
            )
        )
        protection = _required(
            _select_one_unchecked(
                connection,
                f"SELECT {_PROTECTION_COLUMNS} FROM protection_authority WHERE scope_id = ?",
                (scope_key,),
                _build_protection,
            )
        )

        if (
            application.application_generation_id != request.application_generation_id
            or scope.application_generation_id != request.application_generation_id
            or scope.execution_profile_id != application.selected_execution_profile_id
            or execution_profile.connection_profile_id
            != application.selected_execution_profile_id
            or execution_profile.application_generation != application_key
            or market_profile.market_source_profile_id
            != application.selected_market_source_profile_id
            or controller.scope_id != scope_key
            or controller.application_generation_id != request.application_generation_id
            or controller.execution_profile_id != scope.execution_profile_id
            or controller.live_acquisition_generation_id
            != live_generation.acquisition_generation_id
            or live_generation.scope_id != scope_key
            or live_generation.status != "LIVE"
            or generation_current.acquisition_generation_id
            != live_generation.acquisition_generation_id
            or generation_current.scope_id != scope_key
            or checkpoint.application_generation_id != request.application_generation_id
            or checkpoint.currentness_head_ordinal
            != controller.currentness_head_ordinal
            or protection.scope_id != scope_key
            or protection.expected_controller_head_ordinal
            != controller.currentness_head_ordinal
        ):
            raise _ProofFailure

        active_stream_coordinates = (
            protection.active_stream_generation_id,
            protection.active_acquisition_generation_id,
            protection.active_generation_mandate_commitment_sha256,
            protection.active_source_profile_id,
            protection.active_session_id,
            protection.active_sequence_mode,
        )
        if not (
            all(value is None for value in active_stream_coordinates)
            or all(value is not None for value in active_stream_coordinates)
        ):
            raise _ProofFailure

        market_stream: _records.MarketStreamAuthorityRecord | None = None
        market_cursor: _records.MarketCursorRecord | None = None
        if protection.active_stream_generation_id is not None:
            stream_key = _stream_id(protection.active_stream_generation_id)
            market_stream = _required(
                _select_one_unchecked(
                    connection,
                    f"SELECT {_MARKET_STREAM_COLUMNS} FROM market_stream_authority"
                    " WHERE stream_generation_id = ?",
                    (stream_key,),
                    _build_market_stream,
                )
            )
            market_cursor = _required(
                _select_one_unchecked(
                    connection,
                    f"SELECT {_MARKET_CURSOR_COLUMNS} FROM market_cursor"
                    " WHERE stream_generation_id = ?",
                    (stream_key,),
                    _build_market_cursor,
                )
            )
            if (
                protection.active_acquisition_generation_id
                != live_generation.acquisition_generation_id
                or protection.active_generation_mandate_commitment_sha256
                != live_generation.mandate_commitment_sha256
                or protection.active_source_profile_id
                != application.selected_market_source_profile_id
                or market_stream.stream_generation_id
                != protection.active_stream_generation_id
                or market_stream.scope_id != scope_key
                or market_stream.application_generation_id
                != request.application_generation_id
                or market_stream.acquisition_generation_id
                != live_generation.acquisition_generation_id
                or market_stream.generation_mandate_commitment_sha256
                != live_generation.mandate_commitment_sha256
                or market_stream.source_profile_id
                != application.selected_market_source_profile_id
                or market_stream.session_id != protection.active_session_id
                or market_stream.sequence_mode != protection.active_sequence_mode
                or market_cursor.stream_generation_id
                != market_stream.stream_generation_id
                or market_cursor.scope_id != market_stream.scope_id
                or market_cursor.application_generation_id
                != market_stream.application_generation_id
                or market_cursor.acquisition_generation_id
                != market_stream.acquisition_generation_id
                or market_cursor.generation_mandate_commitment_sha256
                != market_stream.generation_mandate_commitment_sha256
                or market_cursor.source_profile_id != market_stream.source_profile_id
                or market_cursor.session_id != market_stream.session_id
                or market_cursor.sequence_mode != market_stream.sequence_mode
            ):
                raise _ProofFailure

        root: _records.RootFillRecord | None = None
        route: _records.AcquisitionRootRouteRecord | None = None
        fact_head: _records.ExecutionFactHeadRecord | None = None
        current_fact: _records.ExecutionFactRecord | None = None
        if request.root_fill_key_id is not None:
            root_key = _exact_int(request.root_fill_key_id)
            root = _required(
                _select_one_unchecked(
                    connection,
                    f"SELECT {_ROOT_FILL_COLUMNS} FROM root_fill WHERE root_fill_key_id = ?",
                    (root_key,),
                    _build_root_fill,
                )
            )
            route = _required(
                _select_one_unchecked(
                    connection,
                    f"SELECT {_ROUTE_COLUMNS} FROM acquisition_root_route"
                    " WHERE root_fill_key_id = ?",
                    (root_key,),
                    _build_route,
                )
            )
            fact_head = _required(
                _select_one_unchecked(
                    connection,
                    f"SELECT {_FACT_HEAD_COLUMNS} FROM execution_fact_head"
                    " WHERE root_fill_key_id = ?",
                    (root_key,),
                    _build_fact_head,
                )
            )
            current_fact = _required(
                _select_one_unchecked(
                    connection,
                    f"SELECT {_EXECUTION_FACT_COLUMNS} FROM execution_fact WHERE fact_id = ?",
                    (fact_head.fact_id,),
                    _build_execution_fact,
                )
            )
            if (
                root.scope_id != scope_key
                or root.application_generation_id != request.application_generation_id
                or root.execution_profile_id != scope.execution_profile_id
                or root.owner_generation_id != live_generation.acquisition_generation_id
                or route.root_fill_key_id != root.root_fill_key_id
                or route.scope_id != scope_key
                or route.application_generation_id != request.application_generation_id
                or route.execution_profile_id != scope.execution_profile_id
                or route.acquisition_generation_id
                != live_generation.acquisition_generation_id
                or root.current_fact_id != fact_head.fact_id
                or root.economics_head_ordinal != fact_head.fact_ordinal
                or current_fact.root_fill_key_id != root.root_fill_key_id
                or current_fact.scope_id != scope_key
                or current_fact.application_generation_id
                != request.application_generation_id
                or current_fact.execution_profile_id != scope.execution_profile_id
                or current_fact.fact_id != fact_head.fact_id
                or current_fact.fact_ordinal != fact_head.fact_ordinal
                or root.current_kind != current_fact.kind
                or root.current_authority != current_fact.authority
                or root.current_side != current_fact.side
                or root.current_quantity != current_fact.quantity
                or root.current_price != current_fact.price
            ):
                raise _ProofFailure

        effect: _records.VenueEffectRecord | None = None
        claim: _records.DispatchClaimRecord | None = None
        if request.effect_id is not None:
            effect_key = _exact_int(request.effect_id)
            effect = _required(
                _select_one_unchecked(
                    connection,
                    f"SELECT {_EFFECT_COLUMNS} FROM venue_effect WHERE effect_id = ?",
                    (effect_key,),
                    _build_effect,
                )
            )
            if (
                effect.scope_id != scope_key
                or effect.application_generation_id != request.application_generation_id
                or effect.execution_profile_id != scope.execution_profile_id
                or effect.acquisition_generation_id
                != live_generation.acquisition_generation_id
                or effect.generation_mandate_commitment_sha256
                != live_generation.mandate_commitment_sha256
                or effect.authority_class != protection.authority_class
                or effect.expected_controller_head_ordinal
                != controller.currentness_head_ordinal
                or effect.expected_protection_version_ordinal
                != protection.version_ordinal
            ):
                raise _ProofFailure
            claim_outcome = _select_one_unchecked(
                connection,
                f"SELECT {_CLAIM_COLUMNS} FROM dispatch_claim WHERE effect_id = ?",
                (effect_key,),
                _build_claim,
            )
            if effect.lifecycle_state not in ("REQUESTED", "CANCELED_BEFORE_DISPATCH"):
                claim = _required(claim_outcome)
            elif claim_outcome.kind is not _records.RepositoryOutcomeKind.ABSENT:
                raise _ProofFailure
            if claim is not None and (
                claim.effect_id != effect.effect_id
                or claim.execution_profile_id != effect.execution_profile_id
            ):
                raise _ProofFailure
            if route is not None and route.effect_id != effect.effect_id:
                raise _ProofFailure

        owner: _records.VenueIdentityOwnerRecord | None = None
        if request.owner_id is not None:
            if effect is None:
                raise _ProofFailure
            owner_text = _identity_text(request.owner_id, _identity.OrderId, "order_id")
            owner = _required(
                _select_one_unchecked(
                    connection,
                    f"SELECT {_OWNER_COLUMNS} FROM venue_identity_owner"
                    " WHERE execution_profile_id = ? AND owner_external = ?",
                    (scope.execution_profile_id, owner_text),
                    _build_owner,
                )
            )
            if (
                owner.scope_id != scope_key
                or owner.execution_profile_id != scope.execution_profile_id
                or owner.effect_id != effect.effect_id
                or owner.owner_generation_id
                != live_generation.acquisition_generation_id
            ):
                raise _ProofFailure
            if route is not None and (
                route.owner_id != owner.owner_id
                or route.observation_id != owner.observation_id
            ):
                raise _ProofFailure

        acceptance: _records.AcceptanceSetRecord | None = None
        evidence: _records.AcceptanceEvidenceRecord | None = None
        if request.require_acceptance:
            if effect is None:
                raise _ProofFailure
            acceptance = _required(
                _select_one_unchecked(
                    connection,
                    f"SELECT {_ACCEPTANCE_SET_COLUMNS} FROM acceptance_set"
                    " WHERE effect_id = ?",
                    (effect.effect_id,),
                    _build_acceptance_set,
                )
            )
            if acceptance.effect_id != effect.effect_id:
                raise _ProofFailure
            evidence = _required(
                _select_one_unchecked(
                    connection,
                    f"SELECT {_EVIDENCE_COLUMNS} FROM acceptance_evidence"
                    " WHERE acceptance_set_id = ?"
                    " ORDER BY evidence_ordinal DESC LIMIT 1",
                    (acceptance.acceptance_set_id,),
                    _build_evidence,
                )
            )
            if (
                evidence.acceptance_set_id != acceptance.acceptance_set_id
                or evidence.effect_id != effect.effect_id
            ):
                raise _ProofFailure

        closure: _records.ClosureChainRecord | None = None
        if request.require_closure:
            if owner is None or effect is None:
                raise _ProofFailure
            closure = _required(
                _select_one_unchecked(
                    connection,
                    f"SELECT {_CLOSURE_COLUMNS} FROM closure_chain"
                    " WHERE scope_id = ? AND owner_external = ?"
                    " ORDER BY ordinal DESC LIMIT 1",
                    (
                        scope_key,
                        _identity_text(owner.owner_id, _identity.OrderId, "order_id"),
                    ),
                    _build_closure,
                )
            )
            if (
                closure.scope_id != scope_key
                or closure.owner_id != owner.owner_id
                or closure.effect_id != effect.effect_id
            ):
                raise _ProofFailure

        proof = _records.CurrentProofSlice(
            execution_profile,
            market_profile,
            application,
            scope,
            live_generation,
            generation_current,
            checkpoint,
            controller,
            protection,
            market_stream,
            market_cursor,
            root,
            route,
            fact_head,
            current_fact,
            effect,
            claim,
            owner,
            acceptance,
            evidence,
            closure,
        )
        return _outcome(_records.RepositoryOutcomeKind.FOUND, proof)
    except (TypeError, ValueError, OverflowError, IndexError, _ProofFailure):
        return _integrity()


__all__ = (
    "advance_kernel_checkpoint",
    "advance_market_cursor",
    "advance_protection_authority",
    "advance_symbol_controller",
    "advance_venue_effect",
    "load_acceptance_evidence",
    "load_acceptance_set",
    "load_acceptance_set_for_effect",
    "load_acquisition_generation",
    "load_acquisition_generation_current",
    "load_acquisition_root_route",
    "load_application_generation",
    "load_closure_head",
    "load_current_proof",
    "load_dispatch_claim",
    "load_dispatch_claim_for_effect",
    "load_execution_fact",
    "load_execution_fact_by_source",
    "load_execution_fact_head",
    "load_execution_profile",
    "load_kernel_checkpoint",
    "load_latest_acceptance_evidence",
    "load_live_acquisition_generation",
    "load_market_cursor",
    "load_market_source_profile",
    "load_market_stream_authority",
    "load_open_venue_effects",
    "load_protection_authority",
    "load_root_fill",
    "load_root_fill_by_external",
    "load_scope",
    "load_symbol_controller",
    "load_venue_effect",
    "load_venue_identity_owner",
    "load_venue_identity_owners_for_effect",
    "retire_acquisition_generation",
    "store_acceptance_evidence",
    "store_acceptance_set",
    "store_acquisition_generation",
    "store_acquisition_root_route",
    "store_application_generation",
    "store_closure",
    "store_dispatch_claim",
    "store_execution_fact",
    "store_execution_profile",
    "store_kernel_checkpoint",
    "store_market_cursor",
    "store_market_source_profile",
    "store_market_stream_authority",
    "store_protection_authority",
    "store_root_fill",
    "store_scope",
    "store_symbol_controller",
    "store_venue_effect",
    "store_venue_identity_owner",
)
