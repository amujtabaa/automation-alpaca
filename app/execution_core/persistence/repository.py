"""Typed, direct-key SQLite repository for the accepted M2-I2 schema.

Every public operation accepts one explicit already-open connection, verifies
the exact schema and connection-local enforcement first, and leaves BEGIN,
COMMIT, and ROLLBACK to its caller. Immutable owner rows are inserted; mutable
current rows advance through expected-version updates; trigger-derived rows
are load-only. Durable identities and values cross this boundary only through
the accepted M2-I1 codec and immutable profile constructors.
"""

from __future__ import annotations as _annotations

from hashlib import sha256 as _sha256
from threading import RLock as _RLock
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
from . import checkpoint_codec as _checkpoint_codec
from . import operations as _operations
from . import records as _records
from .schema import SQLiteConnectionProtocol as _SQLiteConnectionProtocol
from .schema import verify_schema_connection as _verify_schema_connection


_RecordT = _TypeVar("_RecordT")
_CONTRACT_VERSION = "1"
_SETUP_WRITE_CAPABILITY_SEAL = object()
_RUNTIME_WRITE_CAPABILITY_SEAL = object()
_RETIRED_RUNTIME_WRITE_CAPABILITY_SEAL = object()
_RUNTIME_WRITE_LEASE_LOCK = _RLock()
_RUNTIME_WRITE_LEASES: dict[
    int,
    tuple[_SQLiteConnectionProtocol, "_RuntimeWriteCapability"],
] = {}


class _RuntimeWriteCapability:
    """Connection- and transaction-bound authority issued only by unit_of_work."""

    __slots__ = ("_connection", "_seal")
    _connection: _SQLiteConnectionProtocol
    _seal: object

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("runtime write capability is factory-issued")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("runtime write capability cannot be subclassed")

    def __copy__(self) -> _Any:
        raise TypeError("runtime write capability cannot be copied")

    def __deepcopy__(self, memo: object) -> _Any:
        del memo
        raise TypeError("runtime write capability cannot be copied")

    def __reduce__(self) -> _Any:
        raise TypeError("runtime write capability cannot be reduced")

    def __reduce_ex__(self, protocol: object) -> _Any:
        del protocol
        raise TypeError("runtime write capability cannot be reduced")


class _SetupWriteCapability:
    """Connection-bound fixture authority; never a runtime composition token."""

    __slots__ = ("_connection", "_seal")
    _connection: _SQLiteConnectionProtocol
    _seal: object

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("setup write capability is factory-issued")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("setup write capability cannot be subclassed")


_WriteCapability = _RuntimeWriteCapability | _SetupWriteCapability


def _issue_setup_write_capability(
    connection: _SQLiteConnectionProtocol,
) -> _SetupWriteCapability:
    """Mint one private setup token for the named test-support boundary only."""

    capability = object.__new__(_SetupWriteCapability)
    object.__setattr__(capability, "_connection", connection)
    object.__setattr__(capability, "_seal", _SETUP_WRITE_CAPABILITY_SEAL)
    return capability


def _runtime_write_lease_is_active(
    connection: _SQLiteConnectionProtocol,
    capability: _RuntimeWriteCapability,
) -> bool:
    with _RUNTIME_WRITE_LEASE_LOCK:
        retained = _RUNTIME_WRITE_LEASES.get(id(connection))
        return bool(
            retained is not None
            and retained[0] is connection
            and retained[1] is capability
        )


def _activate_runtime_write_lease(
    connection: _SQLiteConnectionProtocol,
) -> _RuntimeWriteCapability:
    """Mint the sole write authority for one already-active UOW transaction."""

    if getattr(connection, "in_transaction", False) is not True:
        raise ValueError("runtime write lease requires an active transaction")
    key = id(connection)
    with _RUNTIME_WRITE_LEASE_LOCK:
        retained = _RUNTIME_WRITE_LEASES.get(key)
        if retained is not None:
            raise ValueError("runtime write lease is already active")
        capability = object.__new__(_RuntimeWriteCapability)
        object.__setattr__(capability, "_connection", connection)
        object.__setattr__(capability, "_seal", _RUNTIME_WRITE_CAPABILITY_SEAL)
        _RUNTIME_WRITE_LEASES[key] = (connection, capability)
    return capability


def _retire_runtime_write_lease(
    connection: _SQLiteConnectionProtocol,
    capability: object,
) -> None:
    """Irreversibly retire the exact active lease before COMMIT or ROLLBACK."""

    if type(capability) is not _RuntimeWriteCapability:
        raise TypeError("runtime write capability is not admitted")
    exact = _cast(_RuntimeWriteCapability, capability)
    key = id(connection)
    with _RUNTIME_WRITE_LEASE_LOCK:
        retained = _RUNTIME_WRITE_LEASES.get(key)
        if (
            retained is None
            or retained[0] is not connection
            or retained[1] is not exact
            or getattr(exact, "_connection", None) is not connection
            or getattr(exact, "_seal", None) is not _RUNTIME_WRITE_CAPABILITY_SEAL
            or getattr(connection, "in_transaction", False) is not True
        ):
            raise ValueError("runtime write lease is not active")
        del _RUNTIME_WRITE_LEASES[key]
        object.__setattr__(exact, "_seal", _RETIRED_RUNTIME_WRITE_CAPABILITY_SEAL)


def _require_write_capability(
    connection: _SQLiteConnectionProtocol,
    capability: object,
) -> None:
    """Refuse absent, forged, stale, cross-connection, or subclassed authority."""

    # Read the sealed slots defensively: a capability forged with
    # ``object.__new__`` has the exact type but no slot values at all, and a bare
    # attribute read leaks ``AttributeError`` instead of the refusal this function
    # promises. ``None`` can never be a seal or a connection, so an unset slot
    # takes the same refusal path as a wrong one.
    capability_type = type(capability)
    if capability_type is _RuntimeWriteCapability:
        runtime_capability = _cast(_RuntimeWriteCapability, capability)
        if (
            getattr(runtime_capability, "_seal", None)
            is not _RUNTIME_WRITE_CAPABILITY_SEAL
            or getattr(runtime_capability, "_connection", None) is not connection
            or getattr(connection, "in_transaction", False) is not True
            or not _runtime_write_lease_is_active(connection, runtime_capability)
        ):
            raise ValueError("runtime write capability is not current for connection")
        return
    if capability_type is _SetupWriteCapability:
        setup_capability = _cast(_SetupWriteCapability, capability)
        if (
            getattr(setup_capability, "_seal", None) is not _SETUP_WRITE_CAPABILITY_SEAL
            or getattr(setup_capability, "_connection", None) is not connection
        ):
            raise ValueError("setup write capability is not current for connection")
        return
    raise TypeError("write capability is not admitted")


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


_RUNTIME_CHECKPOINT_PAYLOAD_CONFLICT_MESSAGE = (
    "runtime checkpoint payload identity is already retained"
)


def _classify_runtime_checkpoint_sqlite_failure(
    caught: Exception,
    *,
    payload_insert: bool,
) -> _records.RepositoryOutcome[_Any]:
    """Apply the closed checkpoint-only SQLite exception partition."""

    if type(payload_insert) is not bool:
        raise TypeError("payload_insert must be exact bool")
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
        if code in (1555, 2067) or (
            payload_insert
            and str(caught) == _RUNTIME_CHECKPOINT_PAYLOAD_CONFLICT_MESSAGE
        ):
            return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
    return _integrity()


def _insert(
    capability: _WriteCapability,
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
    try:
        _require_write_capability(connection, capability)
        _verify_schema_connection(connection)
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
    capability: _WriteCapability,
    connection: _SQLiteConnectionProtocol,
    sql: str,
    prepare: _Callable[[], tuple[_Any, ...]],
) -> _records.RepositoryOutcome[_Any]:
    try:
        _require_write_capability(connection, capability)
        _verify_schema_connection(connection)
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
    *,
    capability: _WriteCapability,
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
        capability,
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
    *,
    capability: _WriteCapability,
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
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _advance(
        capability,
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


def _decode_operation_domain(value: object) -> _operations.OperationDomain:
    text = _exact_text(value)
    try:
        decoded = _operations.OperationDomain(text)
    except ValueError as error:
        raise ValueError("operation domain is not admitted") from error
    if decoded.value != text:
        raise ValueError("operation domain is not canonical")
    return decoded


def _decode_semantic_key_kind(value: object) -> _operations.InputSemanticKeyKind:
    text = _exact_text(value)
    try:
        decoded = _operations.InputSemanticKeyKind(text)
    except ValueError as error:
        raise ValueError("semantic key kind is not admitted") from error
    if decoded.value != text:
        raise ValueError("semantic key kind is not canonical")
    return decoded


def _validated_durable_input(record: object) -> _records.DurableInputRecord:
    if type(record) is not _records.DurableInputRecord:
        raise TypeError("durable input must be an exact record")
    return _records.DurableInputRecord(
        record.application_generation_id,
        record.execution_profile_id,
        record.scope_id,
        record.input_domain,
        record.session_id,
        record.acquisition_generation_id,
        record.market_source_profile_id,
        record.stream_generation_id,
        record.input_identity_sha256,
        record.operation_contract_version,
        record.canonical_payload_bytes,
        record.payload_sha256,
        record.technical_state,
        record.created_ordinal,
    )


_DURABLE_INPUT_COLUMNS = (
    "application_generation_id, execution_profile_id, scope_id, input_domain,"
    " session_external, acquisition_generation_id, market_source_profile_id,"
    " stream_generation_id, input_identity_sha256, operation_contract_version,"
    " canonical_payload_bytes, payload_sha256, technical_state, created_ordinal"
)


def _durable_input_parameters(record: object) -> tuple[_Any, ...]:
    validated = _validated_durable_input(record)
    return (
        _application_id(validated.application_generation_id),
        _exact_text(validated.execution_profile_id),
        _exact_int(validated.scope_id),
        validated.input_domain.value,
        _optional_identity_text(
            validated.session_id, _identity.SessionId, "session_id"
        ),
        _optional_identity_text(
            validated.acquisition_generation_id,
            _identity.AcquisitionGenerationId,
            "acquisition_generation_id",
        ),
        _exact_optional_text(validated.market_source_profile_id),
        _optional_identity_text(
            validated.stream_generation_id,
            _identity.MarketStreamGenerationId,
            "market_stream_generation_id",
        ),
        _exact_text(validated.input_identity_sha256),
        _exact_int(validated.operation_contract_version),
        _exact_bytes(validated.canonical_payload_bytes),
        _exact_text(validated.payload_sha256),
        _exact_text(validated.technical_state),
        _exact_int(validated.created_ordinal),
    )


def _build_durable_input(row: tuple[_Any, ...]) -> _records.DurableInputRecord:
    return _records.DurableInputRecord(
        _decode_application_id(row[0]),
        _exact_text(row[1]),
        _exact_int(row[2]),
        _decode_operation_domain(row[3]),
        _decode_optional_identity(row[4], _identity.SessionId, "session_id"),
        _decode_optional_identity(
            row[5],
            _identity.AcquisitionGenerationId,
            "acquisition_generation_id",
        ),
        _exact_optional_text(row[6]),
        _decode_optional_identity(
            row[7],
            _identity.MarketStreamGenerationId,
            "market_stream_generation_id",
        ),
        _exact_text(row[8]),
        _exact_int(row[9]),
        _exact_bytes(row[10]),
        _exact_text(row[11]),
        _exact_text(row[12]),
        _exact_int(row[13]),
    )


def _durable_input_primary_parameters(
    record: _records.DurableInputRecord,
) -> tuple[str, str, str]:
    """Return the exact primary durable-input coordinate for one validated row."""

    return (
        _application_id(record.application_generation_id),
        record.input_domain.value,
        _exact_text(record.input_identity_sha256),
    )


def _load_durable_input_primary_unchecked(
    connection: _SQLiteConnectionProtocol,
    record: _records.DurableInputRecord,
) -> _records.RepositoryOutcome[_records.DurableInputRecord]:
    """Load one primary input after the caller has already verified the connection."""

    return _select_one_unchecked(
        connection,
        f"SELECT {_DURABLE_INPUT_COLUMNS} FROM durable_input"
        " WHERE application_generation_id = ? AND input_domain = ?"
        " AND input_identity_sha256 = ?",
        _durable_input_primary_parameters(record),
        _build_durable_input,
    )


def _same_durable_input_claim(
    retained: _records.DurableInputRecord,
    candidate: _records.DurableInputRecord,
) -> bool:
    """Compare the immutable operation claim, excluding lifecycle bookkeeping.

    ``created_ordinal`` is a global technical ordering coordinate, and
    ``technical_state`` advances after a coherent outcome/receipt pair exists.
    Neither changes whether a retried canonical operation is the same claimed
    input.  Every operation-derived coordinate and byte remains exact.
    """

    return (
        retained.application_generation_id == candidate.application_generation_id
        and retained.execution_profile_id == candidate.execution_profile_id
        and retained.scope_id == candidate.scope_id
        and retained.input_domain is candidate.input_domain
        and retained.session_id == candidate.session_id
        and retained.acquisition_generation_id == candidate.acquisition_generation_id
        and retained.market_source_profile_id == candidate.market_source_profile_id
        and retained.stream_generation_id == candidate.stream_generation_id
        and retained.input_identity_sha256 == candidate.input_identity_sha256
        and retained.operation_contract_version == candidate.operation_contract_version
        and retained.canonical_payload_bytes == candidate.canonical_payload_bytes
        and retained.payload_sha256 == candidate.payload_sha256
    )


def _durable_input_dedupe_fact(
    kind: _operations.InputDedupeKind,
    record: _records.DurableInputRecord,
    retained_outcome_sha256: str | None = None,
) -> _operations.InputDedupeFact:
    """Build the exact primary classification without caller-shaped proof data."""

    return _operations.InputDedupeFact(
        kind,
        record.input_domain.value,
        record.input_identity_sha256,
        record.payload_sha256,
        retained_outcome_sha256,
        (),
    )


def _classify_retained_durable_input(
    connection: _SQLiteConnectionProtocol,
    candidate: _records.DurableInputRecord,
    retained: _records.DurableInputRecord,
) -> _records.RepositoryOutcome[_operations.InputDedupeFact]:
    """Classify an already-retained primary input without invoking a reducer."""

    if not _same_durable_input_claim(retained, candidate):
        return _outcome(
            _records.RepositoryOutcomeKind.CONFLICT,
            _durable_input_dedupe_fact(
                _operations.InputDedupeKind.IDENTITY_CONFLICT,
                candidate,
            ),
        )
    if retained.technical_state not in {"TERMINAL", "RECONCILIATION_PENDING"}:
        return _integrity()
    outcome = _select_one_unchecked(
        connection,
        f"SELECT {_DURABLE_INPUT_OUTCOME_COLUMNS} FROM durable_input_outcome"
        " WHERE application_generation_id = ? AND input_domain = ?"
        " AND input_identity_sha256 = ?",
        _durable_input_primary_parameters(retained),
        _build_durable_input_outcome,
    )
    if outcome.kind is _records.RepositoryOutcomeKind.ABSENT:
        return _integrity()
    if outcome.kind is not _records.RepositoryOutcomeKind.FOUND:
        return _outcome(outcome.kind)
    if outcome.record is None:
        return _integrity()
    if (
        outcome.record.terminal_technical_state != retained.technical_state
        or outcome.record.application_generation_id
        != retained.application_generation_id
        or outcome.record.input_domain is not retained.input_domain
        or outcome.record.input_identity_sha256 != retained.input_identity_sha256
    ):
        return _integrity()
    return _outcome(
        _records.RepositoryOutcomeKind.FOUND,
        _durable_input_dedupe_fact(
            _operations.InputDedupeKind.EXACT_REPLAY,
            candidate,
            outcome.record.outcome_sha256,
        ),
    )


def claim_durable_input(
    connection: _SQLiteConnectionProtocol,
    record: _records.DurableInputRecord,
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_operations.InputDedupeFact]:
    """Claim one canonical input or return its exact retained primary fact.

    The unit-of-work later supplies the separate authenticated alternate-key
    matches.  This lower repository primitive never accepts a caller-shaped
    semantic match, and it never maps a duplicate to a generic SQLite error.
    """

    try:
        _require_write_capability(connection, capability)
        _verify_schema_connection(connection)
        candidate = _validated_durable_input(record)
        if candidate.technical_state != "CLAIMED":
            raise ValueError("durable input claim must start in CLAIMED state")
        parameters = _durable_input_parameters(candidate)
    except (TypeError, ValueError, OverflowError):
        return _integrity()

    retained = _load_durable_input_primary_unchecked(connection, candidate)
    if retained.kind is _records.RepositoryOutcomeKind.FOUND:
        if retained.record is None:
            return _integrity()
        return _classify_retained_durable_input(connection, candidate, retained.record)
    if retained.kind is not _records.RepositoryOutcomeKind.ABSENT:
        return _outcome(retained.kind)

    try:
        connection.execute(
            f"INSERT INTO durable_input ({_DURABLE_INPUT_COLUMNS})"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            parameters,
        )
    except Exception as caught:
        classified = _classify_sqlite_failure(
            caught,
            conflict_trigger_messages=("durable input identity is already retained",),
        )
        if classified.kind is not _records.RepositoryOutcomeKind.CONFLICT:
            return classified
        retained_after_conflict = _load_durable_input_primary_unchecked(
            connection,
            candidate,
        )
        if retained_after_conflict.kind is not _records.RepositoryOutcomeKind.FOUND:
            return _outcome(retained_after_conflict.kind)
        if retained_after_conflict.record is None:
            return _integrity()
        return _classify_retained_durable_input(
            connection,
            candidate,
            retained_after_conflict.record,
        )
    return _outcome(
        _records.RepositoryOutcomeKind.APPLIED,
        _durable_input_dedupe_fact(_operations.InputDedupeKind.UNSEEN, candidate),
    )


def finalize_durable_input(
    connection: _SQLiteConnectionProtocol,
    record: _records.DurableInputRecord,
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    try:
        _require_write_capability(connection, capability)
        _verify_schema_connection(connection)
        validated = _validated_durable_input(record)
        if validated.technical_state not in {"TERMINAL", "RECONCILIATION_PENDING"}:
            raise ValueError("durable input finalization requires a terminal state")
        claimed = _records.DurableInputRecord(
            validated.application_generation_id,
            validated.execution_profile_id,
            validated.scope_id,
            validated.input_domain,
            validated.session_id,
            validated.acquisition_generation_id,
            validated.market_source_profile_id,
            validated.stream_generation_id,
            validated.input_identity_sha256,
            validated.operation_contract_version,
            validated.canonical_payload_bytes,
            validated.payload_sha256,
            "CLAIMED",
            validated.created_ordinal,
        )
    except (TypeError, ValueError, OverflowError):
        return _integrity()
    retained = _select_one_unchecked(
        connection,
        f"SELECT {_DURABLE_INPUT_COLUMNS} FROM durable_input"
        " WHERE application_generation_id = ? AND input_domain = ?"
        " AND input_identity_sha256 = ?",
        (
            _application_id(claimed.application_generation_id),
            claimed.input_domain.value,
            claimed.input_identity_sha256,
        ),
        _build_durable_input,
    )
    if retained.kind is _records.RepositoryOutcomeKind.ABSENT:
        return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
    if retained.kind is not _records.RepositoryOutcomeKind.FOUND:
        return _outcome(retained.kind)
    if retained.record != claimed:
        return _integrity()
    return _advance(
        capability,
        connection,
        "UPDATE durable_input SET technical_state = ?"
        " WHERE application_generation_id = ? AND input_domain = ?"
        " AND input_identity_sha256 = ? AND technical_state = 'CLAIMED'",
        lambda: (
            validated.technical_state,
            _application_id(validated.application_generation_id),
            validated.input_domain.value,
            validated.input_identity_sha256,
        ),
    )


def load_durable_input(
    connection: _SQLiteConnectionProtocol,
    application_generation_id: _identity.ApplicationGenerationId,
    input_domain: _operations.OperationDomain,
    input_identity_sha256: str,
) -> _records.RepositoryOutcome[_records.DurableInputRecord]:
    try:
        if type(input_domain) is not _operations.OperationDomain:
            raise TypeError("input domain must be exact OperationDomain")
        parameters = (
            _application_id(application_generation_id),
            input_domain.value,
            _exact_text(input_identity_sha256),
        )
    except (TypeError, ValueError):
        _verify_schema_connection(connection)
        return _integrity()
    return _load(
        connection,
        f"SELECT {_DURABLE_INPUT_COLUMNS} FROM durable_input"
        " WHERE application_generation_id = ? AND input_domain = ?"
        " AND input_identity_sha256 = ?",
        parameters,
        _build_durable_input,
    )


_DURABLE_INPUT_SEMANTIC_KEY_COLUMNS = (
    "key_kind, key_application_generation_id, execution_profile_id, key_scope_id,"
    " canonical_key_bytes, key_sha256, input_application_generation_id,"
    " input_domain, input_identity_sha256, created_ordinal"
)


def _validated_durable_input_semantic_key(
    record: object,
) -> _records.DurableInputSemanticKeyRecord:
    if type(record) is not _records.DurableInputSemanticKeyRecord:
        raise TypeError("durable input semantic key must be an exact record")
    return _records.DurableInputSemanticKeyRecord(
        record.key_kind,
        record.key_application_generation_id,
        record.execution_profile_id,
        record.key_scope_id,
        record.canonical_key_bytes,
        record.key_sha256,
        record.input_application_generation_id,
        record.input_domain,
        record.input_identity_sha256,
        record.created_ordinal,
    )


def _durable_input_semantic_key_parameters(record: object) -> tuple[_Any, ...]:
    validated = _validated_durable_input_semantic_key(record)
    return (
        validated.key_kind.value,
        None
        if validated.key_application_generation_id is None
        else _application_id(validated.key_application_generation_id),
        _exact_text(validated.execution_profile_id),
        _exact_optional_int(validated.key_scope_id),
        _exact_bytes(validated.canonical_key_bytes),
        _exact_text(validated.key_sha256),
        _application_id(validated.input_application_generation_id),
        validated.input_domain.value,
        _exact_text(validated.input_identity_sha256),
        _exact_int(validated.created_ordinal),
    )


def _build_durable_input_semantic_key(
    row: tuple[_Any, ...],
) -> _records.DurableInputSemanticKeyRecord:
    return _records.DurableInputSemanticKeyRecord(
        _decode_semantic_key_kind(row[0]),
        _decode_optional_identity(
            row[1], _identity.ApplicationGenerationId, "application_generation_id"
        ),
        _exact_text(row[2]),
        _exact_optional_int(row[3]),
        _exact_bytes(row[4]),
        _exact_text(row[5]),
        _decode_application_id(row[6]),
        _decode_operation_domain(row[7]),
        _exact_text(row[8]),
        _exact_int(row[9]),
    )


def store_durable_input_semantic_key(
    connection: _SQLiteConnectionProtocol,
    record: _records.DurableInputSemanticKeyRecord,
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
        connection,
        f"INSERT INTO durable_input_semantic_key ({_DURABLE_INPUT_SEMANTIC_KEY_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        lambda: _durable_input_semantic_key_parameters(record),
        conflict_trigger_messages=(
            "durable input semantic key must bind its exact input domain",
        ),
        conflict_probe=(
            f"SELECT {_DURABLE_INPUT_SEMANTIC_KEY_COLUMNS}"
            " FROM durable_input_semantic_key"
            " WHERE input_application_generation_id = ? AND input_domain = ?"
            " AND input_identity_sha256 = ? AND key_kind = ?"
            " AND canonical_key_bytes = ?",
            lambda parameters: (
                parameters[6],
                parameters[7],
                parameters[8],
                parameters[0],
                parameters[4],
            ),
        ),
    )


def _semantic_key_lookup_parameters(
    key_kind: _operations.InputSemanticKeyKind,
    key_application_generation_id: _identity.ApplicationGenerationId | None,
    execution_profile_id: str,
    key_scope_id: int | None,
    canonical_key_bytes: bytes,
) -> tuple[_Any, ...]:
    if type(key_kind) is not _operations.InputSemanticKeyKind:
        raise TypeError("semantic key kind must be exact")
    decoded_kind, coordinates, _ = _operations.decode_m2_semantic_key(
        canonical_key_bytes
    )
    if decoded_kind is not key_kind:
        raise ValueError("semantic key kind does not match canonical bytes")
    profile_id = _exact_text(execution_profile_id)
    if key_kind.value.startswith("VENUE_"):
        if key_application_generation_id is not None or key_scope_id is not None:
            raise ValueError("venue semantic keys have no application or scope")
        if coordinates != (profile_id,):
            raise ValueError("venue semantic key coordinates do not match")
        application_id = None
        scope_id = None
    else:
        if (
            type(key_application_generation_id) is not _identity.ApplicationGenerationId
            or type(key_scope_id) is not int
        ):
            raise TypeError("authority semantic key coordinates are incomplete")
        application_id = _application_id(key_application_generation_id)
        scope_id = _exact_int(key_scope_id)
        if coordinates != (application_id, profile_id, scope_id):
            raise ValueError("authority semantic key coordinates do not match")
    return (
        key_kind.value,
        application_id,
        profile_id,
        scope_id,
        _exact_bytes(canonical_key_bytes),
    )


def load_durable_input_semantic_key(
    connection: _SQLiteConnectionProtocol,
    key_kind: _operations.InputSemanticKeyKind,
    key_application_generation_id: _identity.ApplicationGenerationId | None,
    execution_profile_id: str,
    key_scope_id: int | None,
    canonical_key_bytes: bytes,
) -> _records.RepositoryOutcome[_records.DurableInputSemanticKeyRecord]:
    try:
        parameters = _semantic_key_lookup_parameters(
            key_kind,
            key_application_generation_id,
            execution_profile_id,
            key_scope_id,
            canonical_key_bytes,
        )
    except (TypeError, ValueError):
        _verify_schema_connection(connection)
        return _integrity()
    return _load(
        connection,
        f"SELECT {_DURABLE_INPUT_SEMANTIC_KEY_COLUMNS}"
        " FROM durable_input_semantic_key"
        " WHERE key_kind = ?"
        " AND key_application_generation_id IS ?"
        " AND execution_profile_id = ?"
        " AND key_scope_id IS ?"
        " AND canonical_key_bytes = ?",
        parameters,
        _build_durable_input_semantic_key,
    )


def load_durable_input_by_semantic_key(
    connection: _SQLiteConnectionProtocol,
    key_kind: _operations.InputSemanticKeyKind,
    key_application_generation_id: _identity.ApplicationGenerationId | None,
    execution_profile_id: str,
    key_scope_id: int | None,
    canonical_key_bytes: bytes,
) -> _records.RepositoryOutcome[_records.DurableInputRecord]:
    semantic_key = load_durable_input_semantic_key(
        connection,
        key_kind,
        key_application_generation_id,
        execution_profile_id,
        key_scope_id,
        canonical_key_bytes,
    )
    if semantic_key.kind is not _records.RepositoryOutcomeKind.FOUND:
        return _outcome(semantic_key.kind)
    if semantic_key.record is None:
        return _integrity()
    return load_durable_input(
        connection,
        semantic_key.record.input_application_generation_id,
        semantic_key.record.input_domain,
        semantic_key.record.input_identity_sha256,
    )


_DECISION_RECEIPT_COLUMNS = (
    "receipt_ordinal, application_generation_id, input_domain,"
    " input_identity_sha256, owner_domain, owner_disposition,"
    " terminal_technical_state, result_sha256,"
    " checkpoint_currentness_head_ordinal, checkpoint_version_ordinal,"
    " checkpoint_payload_sha256, canonical_receipt_bytes, receipt_length,"
    " receipt_sha256"
)


def _validated_decision_receipt(record: object) -> _records.DecisionReceiptRecord:
    if type(record) is not _records.DecisionReceiptRecord:
        raise TypeError("decision receipt must be an exact record")
    return _records.DecisionReceiptRecord(
        record.receipt_ordinal,
        record.application_generation_id,
        record.input_domain,
        record.input_identity_sha256,
        record.owner_domain,
        record.owner_disposition,
        record.terminal_technical_state,
        record.result_sha256,
        record.checkpoint_currentness_head_ordinal,
        record.checkpoint_version_ordinal,
        record.checkpoint_payload_sha256,
        record.canonical_receipt_bytes,
        record.receipt_length,
        record.receipt_sha256,
    )


def _decision_receipt_parameters(record: object) -> tuple[_Any, ...]:
    validated = _validated_decision_receipt(record)
    return (
        _exact_int(validated.receipt_ordinal),
        _application_id(validated.application_generation_id),
        validated.input_domain.value,
        _exact_text(validated.input_identity_sha256),
        _exact_text(validated.owner_domain),
        _exact_text(validated.owner_disposition),
        _exact_text(validated.terminal_technical_state),
        _exact_text(validated.result_sha256),
        _exact_optional_int(validated.checkpoint_currentness_head_ordinal),
        _exact_optional_int(validated.checkpoint_version_ordinal),
        _exact_optional_text(validated.checkpoint_payload_sha256),
        _exact_bytes(validated.canonical_receipt_bytes),
        _exact_int(validated.receipt_length),
        _exact_text(validated.receipt_sha256),
    )


def _build_decision_receipt(row: tuple[_Any, ...]) -> _records.DecisionReceiptRecord:
    return _records.DecisionReceiptRecord(
        _exact_int(row[0]),
        _decode_application_id(row[1]),
        _decode_operation_domain(row[2]),
        _exact_text(row[3]),
        _exact_text(row[4]),
        _exact_text(row[5]),
        _exact_text(row[6]),
        _exact_text(row[7]),
        _exact_optional_int(row[8]),
        _exact_optional_int(row[9]),
        _exact_optional_text(row[10]),
        _exact_bytes(row[11]),
        _exact_int(row[12]),
        _exact_text(row[13]),
    )


def store_decision_receipt(
    connection: _SQLiteConnectionProtocol,
    record: _records.DecisionReceiptRecord,
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
        connection,
        f"INSERT INTO decision_receipt ({_DECISION_RECEIPT_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        lambda: _decision_receipt_parameters(record),
        conflict_trigger_messages=("decision receipt identity is already retained",),
        conflict_probe=(
            f"SELECT {_DECISION_RECEIPT_COLUMNS} FROM decision_receipt"
            " WHERE receipt_ordinal = ?"
            " OR (application_generation_id = ? AND input_domain = ?"
            " AND input_identity_sha256 = ?)",
            lambda parameters: (
                parameters[0],
                parameters[1],
                parameters[2],
                parameters[3],
            ),
        ),
    )


def load_decision_receipt(
    connection: _SQLiteConnectionProtocol,
    application_generation_id: _identity.ApplicationGenerationId,
    input_domain: _operations.OperationDomain,
    input_identity_sha256: str,
) -> _records.RepositoryOutcome[_records.DecisionReceiptRecord]:
    try:
        if type(input_domain) is not _operations.OperationDomain:
            raise TypeError("input domain must be exact OperationDomain")
        parameters = (
            _application_id(application_generation_id),
            input_domain.value,
            _exact_text(input_identity_sha256),
        )
    except (TypeError, ValueError):
        _verify_schema_connection(connection)
        return _integrity()
    return _load(
        connection,
        f"SELECT {_DECISION_RECEIPT_COLUMNS} FROM decision_receipt"
        " WHERE application_generation_id = ? AND input_domain = ?"
        " AND input_identity_sha256 = ?",
        parameters,
        _build_decision_receipt,
    )


_DURABLE_INPUT_OUTCOME_COLUMNS = (
    "application_generation_id, input_domain, input_identity_sha256,"
    " owner_domain, owner_disposition, terminal_technical_state, result_sha256,"
    " checkpoint_currentness_head_ordinal, checkpoint_version_ordinal,"
    " checkpoint_payload_sha256, receipt_ordinal, receipt_sha256,"
    " canonical_outcome_bytes, outcome_length, outcome_sha256"
)


def _validated_durable_input_outcome(
    record: object,
) -> _records.DurableInputOutcomeRecord:
    if type(record) is not _records.DurableInputOutcomeRecord:
        raise TypeError("durable input outcome must be an exact record")
    return _records.DurableInputOutcomeRecord(
        record.application_generation_id,
        record.input_domain,
        record.input_identity_sha256,
        record.owner_domain,
        record.owner_disposition,
        record.terminal_technical_state,
        record.result_sha256,
        record.checkpoint_currentness_head_ordinal,
        record.checkpoint_version_ordinal,
        record.checkpoint_payload_sha256,
        record.receipt_ordinal,
        record.receipt_sha256,
        record.canonical_outcome_bytes,
        record.outcome_length,
        record.outcome_sha256,
    )


def _durable_input_outcome_parameters(record: object) -> tuple[_Any, ...]:
    validated = _validated_durable_input_outcome(record)
    return (
        _application_id(validated.application_generation_id),
        validated.input_domain.value,
        _exact_text(validated.input_identity_sha256),
        _exact_text(validated.owner_domain),
        _exact_text(validated.owner_disposition),
        _exact_text(validated.terminal_technical_state),
        _exact_text(validated.result_sha256),
        _exact_optional_int(validated.checkpoint_currentness_head_ordinal),
        _exact_optional_int(validated.checkpoint_version_ordinal),
        _exact_optional_text(validated.checkpoint_payload_sha256),
        _exact_int(validated.receipt_ordinal),
        _exact_text(validated.receipt_sha256),
        _exact_bytes(validated.canonical_outcome_bytes),
        _exact_int(validated.outcome_length),
        _exact_text(validated.outcome_sha256),
    )


def _build_durable_input_outcome(
    row: tuple[_Any, ...],
) -> _records.DurableInputOutcomeRecord:
    return _records.DurableInputOutcomeRecord(
        _decode_application_id(row[0]),
        _decode_operation_domain(row[1]),
        _exact_text(row[2]),
        _exact_text(row[3]),
        _exact_text(row[4]),
        _exact_text(row[5]),
        _exact_text(row[6]),
        _exact_optional_int(row[7]),
        _exact_optional_int(row[8]),
        _exact_optional_text(row[9]),
        _exact_int(row[10]),
        _exact_text(row[11]),
        _exact_bytes(row[12]),
        _exact_int(row[13]),
        _exact_text(row[14]),
    )


def store_durable_input_outcome(
    connection: _SQLiteConnectionProtocol,
    record: _records.DurableInputOutcomeRecord,
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
        connection,
        f"INSERT INTO durable_input_outcome ({_DURABLE_INPUT_OUTCOME_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        lambda: _durable_input_outcome_parameters(record),
        conflict_trigger_messages=(
            "durable input outcome must exactly match its decision receipt",
        ),
        conflict_probe=(
            f"SELECT {_DURABLE_INPUT_OUTCOME_COLUMNS}"
            " FROM durable_input_outcome"
            " WHERE application_generation_id = ? AND input_domain = ?"
            " AND input_identity_sha256 = ?",
            lambda parameters: (parameters[0], parameters[1], parameters[2]),
        ),
    )


def load_durable_input_outcome(
    connection: _SQLiteConnectionProtocol,
    application_generation_id: _identity.ApplicationGenerationId,
    input_domain: _operations.OperationDomain,
    input_identity_sha256: str,
) -> _records.RepositoryOutcome[_records.DurableInputOutcomeRecord]:
    try:
        if type(input_domain) is not _operations.OperationDomain:
            raise TypeError("input domain must be exact OperationDomain")
        parameters = (
            _application_id(application_generation_id),
            input_domain.value,
            _exact_text(input_identity_sha256),
        )
    except (TypeError, ValueError):
        _verify_schema_connection(connection)
        return _integrity()
    return _load(
        connection,
        f"SELECT {_DURABLE_INPUT_OUTCOME_COLUMNS} FROM durable_input_outcome"
        " WHERE application_generation_id = ? AND input_domain = ?"
        " AND input_identity_sha256 = ?",
        parameters,
        _build_durable_input_outcome,
    )


_BROKER_OUTBOX_COLUMNS = (
    "outbox_sequence, application_generation_id, execution_profile_id, scope_id,"
    " acquisition_generation_id, input_domain, input_identity_sha256, effect_id,"
    " claim_id, canonical_payload_bytes, payload_length, payload_sha256"
)


def _validated_broker_outbox(record: object) -> _records.BrokerOutboxRecord:
    if type(record) is not _records.BrokerOutboxRecord:
        raise TypeError("broker outbox must be an exact record")
    return _records.BrokerOutboxRecord(
        record.outbox_sequence,
        record.application_generation_id,
        record.execution_profile_id,
        record.scope_id,
        record.acquisition_generation_id,
        record.input_domain,
        record.input_identity_sha256,
        record.effect_id,
        record.claim_id,
        record.canonical_payload_bytes,
        record.payload_length,
        record.payload_sha256,
    )


def _broker_outbox_parameters(record: object) -> tuple[_Any, ...]:
    validated = _validated_broker_outbox(record)
    return (
        _exact_int(validated.outbox_sequence),
        _application_id(validated.application_generation_id),
        _exact_text(validated.execution_profile_id),
        _exact_int(validated.scope_id),
        _acquisition_id(validated.acquisition_generation_id),
        validated.input_domain.value,
        _exact_text(validated.input_identity_sha256),
        _exact_int(validated.effect_id),
        _exact_int(validated.claim_id),
        _exact_bytes(validated.canonical_payload_bytes),
        _exact_int(validated.payload_length),
        _exact_text(validated.payload_sha256),
    )


def _build_broker_outbox(row: tuple[_Any, ...]) -> _records.BrokerOutboxRecord:
    return _records.BrokerOutboxRecord(
        _exact_int(row[0]),
        _decode_application_id(row[1]),
        _exact_text(row[2]),
        _exact_int(row[3]),
        _decode_acquisition_id(row[4]),
        _decode_operation_domain(row[5]),
        _exact_text(row[6]),
        _exact_int(row[7]),
        _exact_int(row[8]),
        _exact_bytes(row[9]),
        _exact_int(row[10]),
        _exact_text(row[11]),
    )


def _validate_broker_outbox_effect_claim_binding(
    connection: _SQLiteConnectionProtocol,
    record: _records.BrokerOutboxRecord,
) -> _records.RepositoryOutcome[_Any] | None:
    """Bind every immutable outbox document field to its effect and claim rows."""

    try:
        validated = _validated_broker_outbox(record)
        snapshot = _records._decode_broker_outbox_snapshot(validated)
    except (TypeError, ValueError, OverflowError):
        return _integrity()
    effect = _select_one_unchecked(
        connection,
        f"SELECT {_EFFECT_COLUMNS} FROM venue_effect WHERE effect_id = ?",
        (_exact_int(validated.effect_id),),
        _build_effect,
    )
    if effect.kind is _records.RepositoryOutcomeKind.ABSENT:
        return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
    if effect.kind is not _records.RepositoryOutcomeKind.FOUND:
        return _outcome(effect.kind)
    claim = _select_one_unchecked(
        connection,
        f"SELECT {_CLAIM_COLUMNS} FROM dispatch_claim"
        " WHERE effect_id = ? AND claim_id = ?",
        (_exact_int(validated.effect_id), _exact_int(validated.claim_id)),
        _build_claim,
    )
    if claim.kind is _records.RepositoryOutcomeKind.ABSENT:
        return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
    if claim.kind is not _records.RepositoryOutcomeKind.FOUND:
        return _outcome(claim.kind)
    if effect.record is None or claim.record is None:
        return _integrity()
    (
        effect_external,
        request_occurrence_id,
        mandate_id,
        generation_mandate_commitment_sha256,
        expected_controller_head_ordinal,
        expected_protection_version_ordinal,
        authority_class,
        effect_kind,
        client_order_id,
        target_order_id,
        side,
        quantity,
        economic_scope,
        claim_occurrence_id,
        claim_ordinal,
    ) = snapshot
    retained_effect = effect.record
    retained_claim = claim.record
    if (
        validated.application_generation_id != retained_effect.application_generation_id
        or validated.execution_profile_id != retained_effect.execution_profile_id
        or validated.scope_id != retained_effect.scope_id
        or validated.acquisition_generation_id
        != retained_effect.acquisition_generation_id
        or effect_external != retained_effect.effect_external
        or request_occurrence_id != retained_effect.request_occurrence_id
        or mandate_id != retained_effect.mandate_id
        or generation_mandate_commitment_sha256
        != retained_effect.generation_mandate_commitment_sha256
        or expected_controller_head_ordinal
        != retained_effect.expected_controller_head_ordinal
        or expected_protection_version_ordinal
        != retained_effect.expected_protection_version_ordinal
        or authority_class != retained_effect.authority_class
        or effect_kind.value != retained_effect.effect_kind
        or client_order_id != retained_effect.client_order_id
        or target_order_id != retained_effect.target_order_id
        or side.value != retained_effect.side
        or quantity != retained_effect.quantity
        or economic_scope != retained_effect.economic_scope
        or retained_claim.execution_profile_id != retained_effect.execution_profile_id
        or claim_occurrence_id != retained_claim.claim_occurrence_id
        or claim_ordinal != retained_claim.claim_ordinal
    ):
        return _integrity()
    return None


def store_broker_outbox(
    connection: _SQLiteConnectionProtocol,
    record: _records.BrokerOutboxRecord,
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    try:
        _require_write_capability(connection, capability)
        _verify_schema_connection(connection)
    except (TypeError, ValueError):
        return _integrity()
    binding_failure = _validate_broker_outbox_effect_claim_binding(connection, record)
    if binding_failure is not None:
        return binding_failure
    return _insert(
        capability,
        connection,
        f"INSERT INTO broker_outbox ({_BROKER_OUTBOX_COLUMNS})"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        lambda: _broker_outbox_parameters(record),
        conflict_trigger_messages=("broker outbox identity is already retained",),
        conflict_probe=(
            f"SELECT {_BROKER_OUTBOX_COLUMNS} FROM broker_outbox"
            " WHERE outbox_sequence = ? OR (effect_id = ? AND claim_id = ?)",
            lambda parameters: (parameters[0], parameters[7], parameters[8]),
        ),
    )


def load_broker_outbox(
    connection: _SQLiteConnectionProtocol,
    outbox_sequence: int,
) -> _records.RepositoryOutcome[_records.BrokerOutboxRecord]:
    loaded = _load_int_key(
        connection,
        f"SELECT {_BROKER_OUTBOX_COLUMNS} FROM broker_outbox WHERE outbox_sequence = ?",
        outbox_sequence,
        _build_broker_outbox,
    )
    if loaded.kind is not _records.RepositoryOutcomeKind.FOUND:
        return loaded
    if loaded.record is None:
        return _integrity()
    binding_failure = _validate_broker_outbox_effect_claim_binding(
        connection, loaded.record
    )
    if binding_failure is not None:
        return _outcome(binding_failure.kind)
    return loaded


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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    try:
        _require_write_capability(connection, capability)
        _verify_schema_connection(connection)
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
        capability,
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
    *,
    capability: _WriteCapability,
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
        capability,
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
    *,
    capability: _WriteCapability,
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
        capability,
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
    *,
    capability: _WriteCapability,
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
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    try:
        _require_write_capability(connection, capability)
        _verify_schema_connection(connection)
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
        capability,
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


def _load_venue_effect_by_external(
    connection: _SQLiteConnectionProtocol,
    execution_profile_id: str,
    effect_id: _identity.EffectId,
) -> _records.RepositoryOutcome[_records.VenueEffectRecord]:
    _verify_schema_connection(connection)
    try:
        profile_key = _exact_text(execution_profile_id)
        external = _identity_text(effect_id, _identity.EffectId, "effect_id")
    except (TypeError, ValueError):
        return _integrity()
    return _select_one_unchecked(
        connection,
        f"SELECT {_EFFECT_COLUMNS} FROM venue_effect"
        " WHERE execution_profile_id = ? AND effect_external = ?",
        (profile_key, external),
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    try:
        _require_write_capability(connection, capability)
        _verify_schema_connection(connection)
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
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    return _insert(
        capability,
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
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    def prepare() -> tuple[_Any, ...]:
        values = _protection_parameters(record)
        return (*values[1:], values[0], _exact_int(expected_version_ordinal))

    return _advance(
        capability,
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

        proof = _records._issue_current_proof_slice(
            _records._CURRENT_PROOF_ISSUER,
            request,
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


_RUNTIME_CHECKPOINT_CAP = 65_536
_RUNTIME_CHECKPOINT_SCOPE_CAP = 4_097
_RUNTIME_CHECKPOINT_PAYLOAD_COLUMNS = (
    "application_generation_id, execution_profile_id, market_source_profile_id,"
    " currentness_head_ordinal, checkpoint_version_ordinal, payload_bytes,"
    " payload_length, payload_sha256"
)


def _checkpoint_vector(alias: str, columns: str) -> str:
    return ",".join(f"{alias}.{column.strip()}" for column in columns.split(","))


_RUNTIME_CHECKPOINT_STORAGE_VECTORS = (
    ("APP", _APPLICATION_COLUMNS),
    ("EXEC_PROFILE", _EXECUTION_PROFILE_COLUMNS),
    ("MARKET_PROFILE", _MARKET_PROFILE_COLUMNS),
    ("HEAD", _CHECKPOINT_COLUMNS),
    ("SCOPE", _SCOPE_COLUMNS),
    ("CONTROLLER", _CONTROLLER_COLUMNS),
    ("PROTECTION", _PROTECTION_COLUMNS),
    ("GENERATION", _ACQUISITION_COLUMNS),
    ("GENERATION_CURRENT", _ACQUISITION_CURRENT_COLUMNS),
    ("EFFECT", _EFFECT_COLUMNS),
    ("OWNER", _OWNER_COLUMNS),
    ("CLAIM", _CLAIM_COLUMNS),
    ("ACCEPTANCE", _ACCEPTANCE_SET_COLUMNS),
    ("EVIDENCE", _EVIDENCE_COLUMNS),
    ("CLOSURE", _CLOSURE_COLUMNS),
    ("ROUTE", _ROUTE_COLUMNS),
    ("ROOT", _ROOT_FILL_COLUMNS),
    ("FACT_HEAD", _FACT_HEAD_COLUMNS),
    ("FACT", _EXECUTION_FACT_COLUMNS),
    ("STREAM", _MARKET_STREAM_COLUMNS),
    ("CURSOR", _MARKET_CURSOR_COLUMNS),
    ("PAYLOAD", _RUNTIME_CHECKPOINT_PAYLOAD_COLUMNS),
)

_RC_APP = _checkpoint_vector("application", _APPLICATION_COLUMNS)
_RC_EXECUTION_PROFILE = _checkpoint_vector(
    "execution_profile", _EXECUTION_PROFILE_COLUMNS
)
_RC_MARKET_PROFILE = _checkpoint_vector("market_profile", _MARKET_PROFILE_COLUMNS)
_RC_HEAD = _checkpoint_vector("checkpoint", _CHECKPOINT_COLUMNS)
_RC_SCOPE = _checkpoint_vector("scope", _SCOPE_COLUMNS)
_RC_CONTROLLER = _checkpoint_vector("controller", _CONTROLLER_COLUMNS)
_RC_PROTECTION = _checkpoint_vector("protection", _PROTECTION_COLUMNS)
_RC_GENERATION = _checkpoint_vector("generation", _ACQUISITION_COLUMNS)
_RC_GENERATION_CURRENT = _checkpoint_vector("current", _ACQUISITION_CURRENT_COLUMNS)
_RC_EFFECT = _checkpoint_vector("effect", _EFFECT_COLUMNS)
_RC_OWNER = _checkpoint_vector("owner", _OWNER_COLUMNS)
_RC_CLAIM = _checkpoint_vector("claim", _CLAIM_COLUMNS)
_RC_ACCEPTANCE = _checkpoint_vector("acceptance", _ACCEPTANCE_SET_COLUMNS)
_RC_EVIDENCE = _checkpoint_vector("evidence", _EVIDENCE_COLUMNS)
_RC_CLOSURE = _checkpoint_vector("closure", _CLOSURE_COLUMNS)
_RC_ROUTE = _checkpoint_vector("route", _ROUTE_COLUMNS)
_RC_ROOT = _checkpoint_vector("root", _ROOT_FILL_COLUMNS)
_RC_FACT_HEAD = _checkpoint_vector("head", _FACT_HEAD_COLUMNS)
_RC_FACT = _checkpoint_vector("fact", _EXECUTION_FACT_COLUMNS)
_RC_STREAM = _checkpoint_vector("stream", _MARKET_STREAM_COLUMNS)
_RC_CURSOR = _checkpoint_vector("cursor", _MARKET_CURSOR_COLUMNS)

_RUNTIME_CHECKPOINT_SELECTED_GENERATION_SQL = """
WITH selected_scope(scope_id) AS MATERIALIZED (
    SELECT scope.scope_id FROM acquisition_scope AS scope
      INDEXED BY ix_acquisition_scope_checkpoint
    WHERE scope.application_generation_id=? AND scope.execution_profile_id=?
),
live_generation AS MATERIALIZED (
    SELECT generation.acquisition_generation_id,generation.scope_id
    FROM selected_scope AS selected
    CROSS JOIN symbol_controller AS controller ON controller.scope_id=selected.scope_id
    CROSS JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id=controller.live_acquisition_generation_id
     AND generation.scope_id=selected.scope_id AND generation.status='LIVE'
    CROSS JOIN acquisition_generation_current AS current
      ON current.acquisition_generation_id=generation.acquisition_generation_id
     AND current.scope_id=generation.scope_id
    WHERE controller.live_acquisition_generation_id IS NOT NULL
    LIMIT 65536
),
effect_unresolved AS MATERIALIZED (
    SELECT current.acquisition_generation_id,current.scope_id
    FROM selected_scope AS selected
    CROSS JOIN acquisition_generation_current AS current
      INDEXED BY ix_acquisition_generation_current_checkpoint_effect
      ON current.scope_id=selected.scope_id AND current.unresolved_effect_count>0
    CROSS JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id=current.acquisition_generation_id
     AND generation.scope_id=current.scope_id AND generation.status='RETIRED_UNSERVING'
    LIMIT 65536
),
protection_active AS MATERIALIZED (
    SELECT current.acquisition_generation_id,current.scope_id
    FROM selected_scope AS selected
    CROSS JOIN acquisition_generation_current AS current
      INDEXED BY ix_acquisition_generation_current_checkpoint_protection
      ON current.scope_id=selected.scope_id AND current.active_protection_count>0
    CROSS JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id=current.acquisition_generation_id
     AND generation.scope_id=current.scope_id AND generation.status='RETIRED_UNSERVING'
    LIMIT 65536
),
selected_generation AS MATERIALIZED (
    SELECT * FROM (
      SELECT * FROM live_generation
      UNION SELECT * FROM effect_unresolved
      UNION SELECT * FROM protection_active)
    LIMIT 65536
)
""".strip()

_RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_SQL = """
, qualifying_effect(effect_id) AS MATERIALIZED (
    SELECT effect.effect_id
    FROM selected_generation AS selected
    CROSS JOIN venue_effect AS effect INDEXED BY ix_venue_effect_generation_disposition
      ON effect.acquisition_generation_id=selected.acquisition_generation_id
     AND effect.disposition IN ('OPEN','INVALIDATED')
    UNION
    SELECT effect.effect_id
    FROM selected_generation AS selected
    CROSS JOIN venue_identity_owner AS owner INDEXED BY ix_venue_owner_checkpoint_late
      ON owner.owner_generation_id=selected.acquisition_generation_id
     AND owner.admitted_after_effect_closed=1
    CROSS JOIN venue_effect AS effect ON effect.effect_id=owner.effect_id
     AND effect.scope_id=selected.scope_id
     AND effect.acquisition_generation_id=selected.acquisition_generation_id
     AND effect.disposition='CLOSED'
)
""".strip()

_RUNTIME_CHECKPOINT_SELECTION_SQL = (
    f"""
SELECT {_RC_APP},{_RC_EXECUTION_PROFILE},{_RC_MARKET_PROFILE},
       CASE WHEN checkpoint.application_generation_id IS NULL THEN 0 ELSE 1 END,
       {_RC_HEAD}
FROM application_generation AS application
JOIN execution_connection_profile AS execution_profile
  ON execution_profile.connection_profile_id=application.selected_execution_profile_id
 AND execution_profile.application_generation=application.application_generation_id
JOIN market_data_source_profile AS market_profile
  ON market_profile.market_source_profile_id=application.selected_market_source_profile_id
LEFT JOIN kernel_checkpoint AS checkpoint
  ON checkpoint.application_generation_id=application.application_generation_id
WHERE application.application_generation_id=?
LIMIT 2
""".strip(),
    f"""
SELECT {_RC_SCOPE},
       CASE WHEN controller.scope_id IS NULL THEN 0 ELSE 1 END,{_RC_CONTROLLER},
       CASE WHEN protection.scope_id IS NULL THEN 0 ELSE 1 END,{_RC_PROTECTION}
FROM acquisition_scope AS scope INDEXED BY ix_acquisition_scope_checkpoint
LEFT JOIN symbol_controller AS controller ON controller.scope_id=scope.scope_id
 AND controller.application_generation_id=scope.application_generation_id
 AND controller.execution_profile_id=scope.execution_profile_id
LEFT JOIN protection_authority AS protection ON protection.scope_id=scope.scope_id
WHERE scope.application_generation_id=? AND scope.execution_profile_id=?
ORDER BY scope.scope_id
LIMIT 4097
""".strip(),
    f"""
WITH selected_scope(scope_id) AS MATERIALIZED (
    SELECT scope.scope_id
    FROM acquisition_scope AS scope INDEXED BY ix_acquisition_scope_checkpoint
    WHERE scope.application_generation_id=? AND scope.execution_profile_id=?
)
SELECT {_RC_GENERATION},{_RC_GENERATION_CURRENT}
FROM selected_scope AS selected
JOIN symbol_controller AS controller ON controller.scope_id=selected.scope_id
JOIN acquisition_generation AS generation
  ON generation.acquisition_generation_id=controller.live_acquisition_generation_id
 AND generation.scope_id=selected.scope_id AND generation.status='LIVE'
JOIN acquisition_generation_current AS current
  ON current.acquisition_generation_id=generation.acquisition_generation_id
 AND current.scope_id=generation.scope_id
WHERE controller.live_acquisition_generation_id IS NOT NULL
ORDER BY generation.scope_id,generation.successor_ordinal,
         generation.acquisition_generation_id
LIMIT 65536
""".strip(),
    f"""
WITH selected_scope(scope_id) AS MATERIALIZED (
    SELECT scope.scope_id
    FROM acquisition_scope AS scope INDEXED BY ix_acquisition_scope_checkpoint
    WHERE scope.application_generation_id=? AND scope.execution_profile_id=?
),
effect_unresolved AS MATERIALIZED (
    SELECT {_RC_GENERATION},{_RC_GENERATION_CURRENT}
    FROM selected_scope AS selected
    CROSS JOIN acquisition_generation_current AS current
      INDEXED BY ix_acquisition_generation_current_checkpoint_effect
      ON current.scope_id=selected.scope_id AND current.unresolved_effect_count>0
    CROSS JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id=current.acquisition_generation_id
     AND generation.scope_id=current.scope_id
     AND generation.status='RETIRED_UNSERVING'
    LIMIT 65536
),
protection_active AS MATERIALIZED (
    SELECT {_RC_GENERATION},{_RC_GENERATION_CURRENT}
    FROM selected_scope AS selected
    CROSS JOIN acquisition_generation_current AS current
      INDEXED BY ix_acquisition_generation_current_checkpoint_protection
      ON current.scope_id=selected.scope_id AND current.active_protection_count>0
    CROSS JOIN acquisition_generation AS generation
      ON generation.acquisition_generation_id=current.acquisition_generation_id
     AND generation.scope_id=current.scope_id
     AND generation.status='RETIRED_UNSERVING'
    LIMIT 65536
),
combined AS (
    SELECT * FROM effect_unresolved
    UNION
    SELECT * FROM protection_active
)
SELECT * FROM combined
LIMIT 65536
""".strip(),
    f"""{_RUNTIME_CHECKPOINT_SELECTED_GENERATION_SQL}, admitted AS MATERIALIZED (
    SELECT {_RC_EFFECT}
    FROM selected_generation AS selected
    CROSS JOIN venue_effect AS effect INDEXED BY ix_venue_effect_generation_disposition
      ON effect.acquisition_generation_id=selected.acquisition_generation_id
     AND effect.disposition IN ('OPEN','INVALIDATED')
    LIMIT 65536
)
SELECT * FROM admitted ORDER BY 25,1""",
    f"""{_RUNTIME_CHECKPOINT_SELECTED_GENERATION_SQL}, admitted AS MATERIALIZED (
    SELECT {_RC_OWNER},{_RC_EFFECT}
    FROM selected_generation AS selected
    CROSS JOIN venue_identity_owner AS owner INDEXED BY ix_venue_owner_checkpoint_late
      ON owner.owner_generation_id=selected.acquisition_generation_id
     AND owner.admitted_after_effect_closed=1
    CROSS JOIN venue_effect AS effect ON effect.effect_id=owner.effect_id
     AND effect.scope_id=selected.scope_id
     AND effect.acquisition_generation_id=selected.acquisition_generation_id
     AND effect.disposition='CLOSED'
    LIMIT 65536
)
SELECT * FROM admitted ORDER BY 7,5,3""",
    f"""{_RUNTIME_CHECKPOINT_SELECTED_GENERATION_SQL}
{_RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_SQL}, admitted AS MATERIALIZED (
    SELECT {_RC_OWNER}
    FROM qualifying_effect AS selected
    CROSS JOIN venue_identity_owner AS owner INDEXED BY ix_venue_identity_owner_effect
      ON owner.effect_id=selected.effect_id
    LIMIT 65536
)
SELECT * FROM admitted ORDER BY 5,3,4""",
    f"""{_RUNTIME_CHECKPOINT_SELECTED_GENERATION_SQL}
{_RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_SQL}, admitted AS MATERIALIZED (
    SELECT {_RC_CLAIM}
    FROM qualifying_effect AS selected
    CROSS JOIN dispatch_claim AS claim INDEXED BY ix_dispatch_claim_effect
      ON claim.effect_id=selected.effect_id
    LIMIT 65536
)
SELECT * FROM admitted ORDER BY 2,1""",
    f"""{_RUNTIME_CHECKPOINT_SELECTED_GENERATION_SQL}
{_RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_SQL}, admitted AS MATERIALIZED (
    SELECT {_RC_ACCEPTANCE}
    FROM qualifying_effect AS selected
    CROSS JOIN acceptance_set AS acceptance ON acceptance.effect_id=selected.effect_id
    LIMIT 65536
)
SELECT * FROM admitted ORDER BY 2,1""",
    f"""{_RUNTIME_CHECKPOINT_SELECTED_GENERATION_SQL}
{_RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_SQL}, admitted AS MATERIALIZED (
    SELECT {_RC_EVIDENCE}
    FROM qualifying_effect AS selected
    CROSS JOIN acceptance_set AS acceptance ON acceptance.effect_id=selected.effect_id
    CROSS JOIN acceptance_evidence AS evidence INDEXED BY ix_acceptance_evidence_set
      ON evidence.acceptance_set_id=acceptance.acceptance_set_id
    LIMIT 65536
)
SELECT * FROM admitted ORDER BY 3,7,1""",
    f"""{_RUNTIME_CHECKPOINT_SELECTED_GENERATION_SQL}
{_RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_SQL}, admitted AS MATERIALIZED (
    SELECT {_RC_CLOSURE}
    FROM qualifying_effect AS selected
    CROSS JOIN venue_identity_owner AS owner INDEXED BY ix_venue_identity_owner_effect
      ON owner.effect_id=selected.effect_id
    CROSS JOIN closure_chain AS closure ON closure.closure_id=(
        SELECT candidate.closure_id
        FROM closure_chain AS candidate INDEXED BY ix_closure_chain_head
        WHERE candidate.scope_id=owner.scope_id
          AND candidate.owner_external=owner.owner_external
        ORDER BY candidate.ordinal DESC LIMIT 1)
    LIMIT 65536
)
SELECT * FROM admitted ORDER BY 5,3,4""",
    f"""{_RUNTIME_CHECKPOINT_SELECTED_GENERATION_SQL}
{_RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_SQL}, admitted AS MATERIALIZED (
    SELECT {_RC_ROUTE},{_RC_ROOT},
           CASE WHEN head.fact_id IS NULL THEN 0 ELSE 1 END,
           {_RC_FACT_HEAD},{_RC_FACT}
    FROM qualifying_effect AS selected
    CROSS JOIN venue_identity_owner AS owner INDEXED BY ix_venue_identity_owner_effect
      ON owner.effect_id=selected.effect_id
    CROSS JOIN acquisition_root_route AS route INDEXED BY ix_acquisition_root_route_owner
      ON route.effect_id=owner.effect_id
     AND route.owner_external=owner.owner_external
     AND route.observation_external=owner.observation_external
    CROSS JOIN root_fill AS root ON root.root_fill_key_id=route.root_fill_key_id
     AND root.scope_id=route.scope_id
     AND root.owner_generation_id=route.acquisition_generation_id
    LEFT JOIN execution_fact_head AS head ON head.root_fill_key_id=root.root_fill_key_id
    LEFT JOIN execution_fact AS fact ON fact.root_fill_key_id=head.root_fill_key_id
     AND fact.fact_id=head.fact_id AND fact.fact_ordinal=head.fact_ordinal
    LIMIT 65536
)
SELECT * FROM admitted ORDER BY 6,7,1""",
    f"""{_RUNTIME_CHECKPOINT_SELECTED_GENERATION_SQL}, admitted AS MATERIALIZED (
    SELECT {_RC_STREAM},
           CASE WHEN cursor.stream_generation_id IS NULL THEN 0 ELSE 1 END,
           {_RC_CURSOR}
    FROM selected_generation AS selected
    CROSS JOIN market_stream_authority AS stream
      INDEXED BY ix_market_stream_authority_checkpoint_generation
      ON stream.acquisition_generation_id=selected.acquisition_generation_id
     AND stream.scope_id=selected.scope_id
    LEFT JOIN market_cursor AS cursor ON cursor.stream_generation_id=stream.stream_generation_id
    LIMIT 65536
)
SELECT * FROM admitted ORDER BY 4,1""",
)

# Authoritative plan access contract for the frozen thirteen-query selection
# manifest.  Each member is ``(base_table, EXPLAIN name, forced_index)``.  The
# name is the SQL alias when the statement declares one and the base table name
# otherwise; ``None`` says the statement intentionally relies on a primary or
# unique-key search rather than a named ``INDEXED BY`` assertion.  This is kept
# beside the SQL instead of reverse-engineering sources from a partial parser:
# planner proof is safety-critical, so a new source must be named deliberately.
_RuntimeCheckpointPlanAccess = tuple[str, str, str | None]

_RUNTIME_CHECKPOINT_SELECTED_GENERATION_PLAN_ACCESS: tuple[
    _RuntimeCheckpointPlanAccess, ...
] = (
    ("acquisition_scope", "scope", "ix_acquisition_scope_checkpoint"),
    ("symbol_controller", "controller", None),
    ("acquisition_generation", "generation", None),
    ("acquisition_generation_current", "current", None),
    (
        "acquisition_generation_current",
        "current",
        "ix_acquisition_generation_current_checkpoint_effect",
    ),
    ("acquisition_generation", "generation", None),
    (
        "acquisition_generation_current",
        "current",
        "ix_acquisition_generation_current_checkpoint_protection",
    ),
    ("acquisition_generation", "generation", None),
)

# Upper-bound multisets of non-base planner access names.  SQLite must read
# materialized CTEs/subqueries to drive the indexed base-table searches above;
# those bounded intermediates are not historical table scans.  Repeated names
# are deliberate and cap the number of matching plan rows that may be consumed.
_RUNTIME_CHECKPOINT_SELECTED_GENERATION_PLAN_INTERMEDIATES = (
    "selected",
    "live_generation",
    "selected",
    "effect_unresolved",
    "selected",
    "protection_active",
    "(subquery)",
)
_RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_PLAN_INTERMEDIATES = (
    "selected",
    "selected",
)
_RUNTIME_CHECKPOINT_SELECTED_OUTPUT_PLAN_INTERMEDIATES = (
    _RUNTIME_CHECKPOINT_SELECTED_GENERATION_PLAN_INTERMEDIATES
    + ("selected", "admitted")
)
_RUNTIME_CHECKPOINT_QUALIFIED_OUTPUT_PLAN_INTERMEDIATES = (
    _RUNTIME_CHECKPOINT_SELECTED_GENERATION_PLAN_INTERMEDIATES
    + _RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_PLAN_INTERMEDIATES
    + ("selected", "admitted")
)

_RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_PLAN_ACCESS: tuple[
    _RuntimeCheckpointPlanAccess, ...
] = (
    ("venue_effect", "effect", "ix_venue_effect_generation_disposition"),
    ("venue_identity_owner", "owner", "ix_venue_owner_checkpoint_late"),
    ("venue_effect", "effect", None),
)

_RUNTIME_CHECKPOINT_SELECTION_PLAN_ACCESS: tuple[
    tuple[_RuntimeCheckpointPlanAccess, ...], ...
] = (
    (
        ("application_generation", "application", None),
        ("execution_connection_profile", "execution_profile", None),
        ("market_data_source_profile", "market_profile", None),
        ("kernel_checkpoint", "checkpoint", None),
    ),
    (
        ("acquisition_scope", "scope", "ix_acquisition_scope_checkpoint"),
        ("symbol_controller", "controller", None),
        ("protection_authority", "protection", None),
    ),
    (
        ("acquisition_scope", "scope", "ix_acquisition_scope_checkpoint"),
        ("symbol_controller", "controller", None),
        ("acquisition_generation", "generation", None),
        ("acquisition_generation_current", "current", None),
    ),
    (
        ("acquisition_scope", "scope", "ix_acquisition_scope_checkpoint"),
        (
            "acquisition_generation_current",
            "current",
            "ix_acquisition_generation_current_checkpoint_effect",
        ),
        ("acquisition_generation", "generation", None),
        (
            "acquisition_generation_current",
            "current",
            "ix_acquisition_generation_current_checkpoint_protection",
        ),
        ("acquisition_generation", "generation", None),
    ),
    _RUNTIME_CHECKPOINT_SELECTED_GENERATION_PLAN_ACCESS
    + (("venue_effect", "effect", "ix_venue_effect_generation_disposition"),),
    _RUNTIME_CHECKPOINT_SELECTED_GENERATION_PLAN_ACCESS
    + (
        ("venue_identity_owner", "owner", "ix_venue_owner_checkpoint_late"),
        ("venue_effect", "effect", None),
    ),
    _RUNTIME_CHECKPOINT_SELECTED_GENERATION_PLAN_ACCESS
    + _RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_PLAN_ACCESS
    + (("venue_identity_owner", "owner", "ix_venue_identity_owner_effect"),),
    _RUNTIME_CHECKPOINT_SELECTED_GENERATION_PLAN_ACCESS
    + _RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_PLAN_ACCESS
    + (("dispatch_claim", "claim", "ix_dispatch_claim_effect"),),
    _RUNTIME_CHECKPOINT_SELECTED_GENERATION_PLAN_ACCESS
    + _RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_PLAN_ACCESS
    + (("acceptance_set", "acceptance", None),),
    _RUNTIME_CHECKPOINT_SELECTED_GENERATION_PLAN_ACCESS
    + _RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_PLAN_ACCESS
    + (
        ("acceptance_set", "acceptance", None),
        ("acceptance_evidence", "evidence", "ix_acceptance_evidence_set"),
    ),
    _RUNTIME_CHECKPOINT_SELECTED_GENERATION_PLAN_ACCESS
    + _RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_PLAN_ACCESS
    + (
        ("venue_identity_owner", "owner", "ix_venue_identity_owner_effect"),
        ("closure_chain", "closure", None),
        ("closure_chain", "candidate", "ix_closure_chain_head"),
    ),
    _RUNTIME_CHECKPOINT_SELECTED_GENERATION_PLAN_ACCESS
    + _RUNTIME_CHECKPOINT_QUALIFYING_EFFECT_PLAN_ACCESS
    + (
        ("venue_identity_owner", "owner", "ix_venue_identity_owner_effect"),
        ("acquisition_root_route", "route", "ix_acquisition_root_route_owner"),
        ("root_fill", "root", None),
        ("execution_fact_head", "head", None),
        ("execution_fact", "fact", None),
    ),
    _RUNTIME_CHECKPOINT_SELECTED_GENERATION_PLAN_ACCESS
    + (
        (
            "market_stream_authority",
            "stream",
            "ix_market_stream_authority_checkpoint_generation",
        ),
        ("market_cursor", "cursor", None),
    ),
)

_RUNTIME_CHECKPOINT_SELECTION_PLAN_BOUNDED_INTERMEDIATES: tuple[
    tuple[str, ...], ...
] = (
    (),
    (),
    ("selected",),
    (
        "selected",
        "effect_unresolved",
        "selected",
        "protection_active",
        "combined",
    ),
    _RUNTIME_CHECKPOINT_SELECTED_OUTPUT_PLAN_INTERMEDIATES,
    _RUNTIME_CHECKPOINT_SELECTED_OUTPUT_PLAN_INTERMEDIATES,
    _RUNTIME_CHECKPOINT_QUALIFIED_OUTPUT_PLAN_INTERMEDIATES,
    _RUNTIME_CHECKPOINT_QUALIFIED_OUTPUT_PLAN_INTERMEDIATES,
    _RUNTIME_CHECKPOINT_QUALIFIED_OUTPUT_PLAN_INTERMEDIATES,
    _RUNTIME_CHECKPOINT_QUALIFIED_OUTPUT_PLAN_INTERMEDIATES,
    _RUNTIME_CHECKPOINT_QUALIFIED_OUTPUT_PLAN_INTERMEDIATES,
    _RUNTIME_CHECKPOINT_QUALIFIED_OUTPUT_PLAN_INTERMEDIATES,
    _RUNTIME_CHECKPOINT_SELECTED_OUTPUT_PLAN_INTERMEDIATES,
)

_RUNTIME_CHECKPOINT_LOAD_PLAN_ACCESS: tuple[
    tuple[_RuntimeCheckpointPlanAccess, ...], ...
] = (
    (("kernel_checkpoint", "kernel_checkpoint", None),),
    (("runtime_checkpoint_payload", "runtime_checkpoint_payload", None),),
)

_RUNTIME_CHECKPOINT_HEAD_SELECT_SQL = (
    f"SELECT {_CHECKPOINT_COLUMNS} FROM kernel_checkpoint "
    "WHERE application_generation_id=? LIMIT 2"
)
_RUNTIME_CHECKPOINT_PAYLOAD_SELECT_SQL = (
    f"SELECT {_RUNTIME_CHECKPOINT_PAYLOAD_COLUMNS} "
    "FROM runtime_checkpoint_payload "
    "WHERE application_generation_id=? AND currentness_head_ordinal=? "
    "AND checkpoint_version_ordinal=? AND payload_sha256=? LIMIT 2"
)
_RUNTIME_CHECKPOINT_PAYLOAD_INSERT_SQL = (
    "INSERT INTO runtime_checkpoint_payload("
    "application_generation_id,execution_profile_id,market_source_profile_id,"
    "currentness_head_ordinal,checkpoint_version_ordinal,payload_bytes,"
    "payload_length,payload_sha256) VALUES (?,?,?,?,?,?,?,?)"
)
_RUNTIME_CHECKPOINT_HEAD_INSERT_SQL = (
    "INSERT INTO kernel_checkpoint(application_generation_id,currentness_head_ordinal,"
    "checkpoint_sha256,checkpoint_version_ordinal) "
    "SELECT ?,?,?,? WHERE NOT EXISTS ("
    "SELECT 1 FROM kernel_checkpoint WHERE application_generation_id=?)"
)
_RUNTIME_CHECKPOINT_HEAD_UPDATE_SQL = (
    "UPDATE kernel_checkpoint SET currentness_head_ordinal=?,checkpoint_sha256=?,"
    "checkpoint_version_ordinal=? WHERE application_generation_id=? "
    "AND currentness_head_ordinal=? AND checkpoint_sha256=? "
    "AND checkpoint_version_ordinal=?"
)


def _runtime_checkpoint_records_member(name: str) -> _Any:
    member = getattr(_records, name, None)
    if member is None:
        raise RuntimeError(f"checkpoint records integration is missing {name}")
    return member


def _runtime_checkpoint_codec_member(name: str) -> _Any:
    member = getattr(_checkpoint_codec, name, None)
    if member is None:
        raise RuntimeError(f"checkpoint codec integration is missing {name}")
    return member


def _checkpoint_query_rows(
    connection: _SQLiteConnectionProtocol,
    sql: str,
    parameters: tuple[_Any, ...],
) -> _records.RepositoryOutcome[tuple[tuple[_Any, ...], ...]]:
    try:
        rows = connection.execute(sql, _query_parameters(parameters)).fetchall()
    except Exception as caught:
        return _classify_runtime_checkpoint_sqlite_failure(
            caught,
            payload_insert=False,
        )
    return _outcome(
        _records.RepositoryOutcomeKind.FOUND,
        tuple(tuple(row) for row in rows),
    )


def _checkpoint_required_rows(
    outcome: _records.RepositoryOutcome[tuple[tuple[_Any, ...], ...]],
) -> tuple[tuple[_Any, ...], ...]:
    if outcome.kind is not _records.RepositoryOutcomeKind.FOUND:
        raise _CheckpointSelectionOutcome(outcome.kind)
    if outcome.record is None:
        raise ValueError("checkpoint query omitted its row collection")
    return outcome.record


class _CheckpointSelectionOutcome(Exception):
    def __init__(self, kind: _records.RepositoryOutcomeKind) -> None:
        super().__init__(kind.value)
        self.kind = kind


def _checkpoint_presence(
    value: object,
    fields: tuple[_Any, ...],
    *,
    optional: bool,
) -> bool:
    present = _exact_int(value)
    if present == 0:
        if not optional or any(field is not None for field in fields):
            raise ValueError("checkpoint absence vector is not wholly null")
        return False
    if present != 1:
        raise ValueError("checkpoint presence vector is not canonical")
    return True


def _checkpoint_unique_records(
    records: tuple[_RecordT, ...],
    key: _Callable[[_RecordT], object],
) -> dict[object, _RecordT]:
    unique: dict[object, _RecordT] = {}
    for record in records:
        coordinate = key(record)
        retained = unique.get(coordinate)
        if retained is not None and retained != record:
            raise ValueError("checkpoint coordinate has conflicting rows")
        if retained is not None:
            raise ValueError("checkpoint coordinate is duplicated")
        unique[coordinate] = record
    return unique


def _checkpoint_pack(domain: bytes, *parts: bytes) -> bytes:
    return (
        len(domain).to_bytes(4, "big")
        + domain
        + b"".join(len(part).to_bytes(8, "big") + part for part in parts)
    )


def _checkpoint_commit(domain: bytes, *parts: bytes) -> bytes:
    return _sha256(_checkpoint_pack(domain, *parts)).digest()


def _checkpoint_binding_int(value: int) -> bytes:
    exact = _exact_int(value)
    magnitude = abs(exact)
    width = max(1, (magnitude.bit_length() + 7) // 8)
    return (
        bytes((0 if exact >= 0 else 1,))
        + width.to_bytes(4, "big")
        + magnitude.to_bytes(width, "big")
    )


def _checkpoint_binding_text(value: str) -> bytes:
    encoded = _exact_text(value).encode("utf-8")
    return len(encoded).to_bytes(8, "big") + encoded


def _checkpoint_field_int(value: int) -> bytes:
    return _checkpoint_commit(
        b"execution-core/runtime-checkpoint/field/int/v1",
        _checkpoint_binding_int(value),
    )


def _checkpoint_field_text(value: str) -> bytes:
    return _checkpoint_commit(
        b"execution-core/runtime-checkpoint/field/text/v1",
        _checkpoint_binding_text(value),
    )


def _checkpoint_absence(
    family: str,
    suffix: str,
    *parts: bytes,
) -> tuple[str, bytes]:
    return (
        family,
        _checkpoint_commit(
            f"execution-core/runtime-checkpoint/absence-key/{suffix}/v1".encode(
                "ascii"
            ),
            *parts,
        ),
    )


def _checkpoint_rows_are_bounded(rows: tuple[tuple[_Any, ...], ...]) -> None:
    if len(rows) >= _RUNTIME_CHECKPOINT_CAP:
        raise OverflowError("checkpoint query returned its refusal sentinel")


def _checkpoint_issue_selection_set(
    values: tuple[_Any, ...],
) -> _Any:
    selection_type = _runtime_checkpoint_records_member(
        "_RuntimeCheckpointSelectionSet"
    )
    return selection_type(*values)


def _checkpoint_issue_selection_proof(
    request: _Any,
    application: _records.ApplicationGenerationRecord,
    execution_profile: _profiles.ExecutionConnectionProfile,
    market_profile: _profiles.MarketDataSourceProfile,
    predecessor: _records.KernelCheckpointRecord | None,
    target_head: int,
    target_version: int,
    selection: _Any,
) -> _Any:
    issuer = _runtime_checkpoint_records_member(
        "_issue_runtime_checkpoint_selection_proof"
    )
    return issuer(
        request,
        application,
        execution_profile,
        market_profile,
        predecessor,
        target_head,
        target_version,
        selection,
    )


def _checkpoint_request_values(request: object) -> tuple[str, str, str]:
    request_type = _runtime_checkpoint_records_member(
        "RuntimeCheckpointSelectionRequest"
    )
    if type(request) is not request_type:
        raise TypeError("selection request must be exact")
    exact_request = _cast(_Any, request)
    application_id = _application_id(exact_request.application_generation_id)
    return (
        application_id,
        _exact_text(exact_request.execution_profile_id),
        _exact_text(exact_request.market_source_profile_id),
    )


def select_runtime_checkpoint(
    connection: _SQLiteConnectionProtocol,
    request: _Any,
) -> _records.RepositoryOutcome[_Any]:
    """Select one bounded, authenticated non-serving checkpoint preimage."""

    if getattr(connection, "in_transaction", False) is not True:
        return _integrity()
    try:
        _verify_schema_connection(connection)
        application_key, execution_profile_id, market_profile_id = (
            _checkpoint_request_values(request)
        )
        parameters = (application_key, execution_profile_id)

        q1 = _checkpoint_required_rows(
            _checkpoint_query_rows(
                connection,
                _RUNTIME_CHECKPOINT_SELECTION_SQL[0],
                (application_key,),
            )
        )
        if not q1:
            return _outcome(_records.RepositoryOutcomeKind.ABSENT)
        if len(q1) != 1:
            return _integrity()
        q1_row = q1[0]
        if len(q1_row) != 30:
            raise ValueError("checkpoint Q1 has the wrong exact vector length")
        application = _build_application(q1_row[0:4])
        execution_profile = _build_execution_profile(q1_row[4:17])
        market_profile = _build_market_profile(q1_row[17:25])
        head_values = q1_row[26:30]
        head_present = _checkpoint_presence(q1_row[25], head_values, optional=True)
        predecessor = _build_checkpoint(head_values) if head_present else None
        if (
            _application_id(application.application_generation_id) != application_key
            or application.selected_execution_profile_id != execution_profile_id
            or application.selected_market_source_profile_id != market_profile_id
            or execution_profile.connection_profile_id != execution_profile_id
            or execution_profile.application_generation != application_key
            or market_profile.market_source_profile_id != market_profile_id
        ):
            return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
        if predecessor != request.expected_checkpoint:
            return _outcome(_records.RepositoryOutcomeKind.CONFLICT)

        q2 = _checkpoint_required_rows(
            _checkpoint_query_rows(
                connection, _RUNTIME_CHECKPOINT_SELECTION_SQL[1], parameters
            )
        )
        if len(q2) >= _RUNTIME_CHECKPOINT_SCOPE_CAP:
            raise OverflowError("checkpoint selected too many scopes")
        scopes: list[_records.ScopeRecord] = []
        controllers: list[_records.SymbolControllerRecord] = []
        protections: list[_records.ProtectionAuthorityRecord] = []
        prior_scope_id = -1
        for row in q2:
            if len(row) != 26:
                raise ValueError("checkpoint Q2 has the wrong exact vector length")
            scope = _build_scope(row[0:4])
            controller_values = row[5:14]
            protection_values = row[15:26]
            if not _checkpoint_presence(row[4], controller_values, optional=True):
                raise ValueError("selected scope has no controller")
            if not _checkpoint_presence(row[14], protection_values, optional=True):
                raise ValueError("selected scope has no protection authority")
            controller = _build_controller(controller_values)
            protection = _build_protection(protection_values)
            if (
                scope.scope_id <= prior_scope_id
                or scope.application_generation_id
                != application.application_generation_id
                or scope.execution_profile_id != execution_profile_id
                or controller.scope_id != scope.scope_id
                or controller.application_generation_id
                != application.application_generation_id
                or controller.execution_profile_id != execution_profile_id
                or protection.scope_id != scope.scope_id
                or protection.expected_controller_head_ordinal
                != controller.currentness_head_ordinal
            ):
                raise ValueError("checkpoint scope vectors do not agree")
            active = (
                protection.active_stream_generation_id,
                protection.active_acquisition_generation_id,
                protection.active_generation_mandate_commitment_sha256,
                protection.active_source_profile_id,
                protection.active_session_id,
                protection.active_sequence_mode,
            )
            if not (
                all(value is None for value in active)
                or all(value is not None for value in active)
            ):
                raise ValueError("checkpoint protection activity is partial")
            if protection.authority_class == "HARD_BAIL" and any(
                value is None for value in active
            ):
                raise ValueError("hard-bail protection has no active coordinates")
            prior_scope_id = scope.scope_id
            scopes.append(scope)
            controllers.append(controller)
            protections.append(protection)

        generation_rows: list[tuple[tuple[_Any, ...], ...]] = []
        for query_index in (2, 3):
            rows = _checkpoint_required_rows(
                _checkpoint_query_rows(
                    connection,
                    _RUNTIME_CHECKPOINT_SELECTION_SQL[query_index],
                    parameters,
                )
            )
            _checkpoint_rows_are_bounded(rows)
            generation_rows.append(rows)

        generation_families: list[
            tuple[
                tuple[_records.AcquisitionGenerationRecord, ...],
                tuple[_records.AcquisitionGenerationCurrentRecord, ...],
            ]
        ] = []
        for family_index, rows in enumerate(generation_rows):
            generations: list[_records.AcquisitionGenerationRecord] = []
            currents: list[_records.AcquisitionGenerationCurrentRecord] = []
            seen: dict[tuple[str, int], tuple[_Any, _Any]] = {}
            for row in rows:
                if len(row) != 12:
                    raise ValueError(
                        "checkpoint generation query has the wrong vector length"
                    )
                generation = _build_acquisition(row[0:7])
                current = _build_acquisition_current(row[7:12])
                coordinate = (
                    _acquisition_id(generation.acquisition_generation_id),
                    generation.scope_id,
                )
                if (
                    coordinate in seen
                    or current.acquisition_generation_id
                    != generation.acquisition_generation_id
                    or current.scope_id != generation.scope_id
                    or (family_index == 0 and generation.status != "LIVE")
                    or (
                        family_index == 1
                        and (
                            generation.status != "RETIRED_UNSERVING"
                            or (
                                current.unresolved_effect_count <= 0
                                and current.active_protection_count <= 0
                            )
                        )
                    )
                ):
                    raise ValueError("checkpoint generation vectors do not agree")
                seen[coordinate] = (generation, current)
                generations.append(generation)
                currents.append(current)
            generation_families.append((tuple(generations), tuple(currents)))

        live_generations, live_currents = generation_families[0]
        unresolved_generations, unresolved_currents = generation_families[1]
        controller_live = {
            (controller.live_acquisition_generation_id, controller.scope_id)
            for controller in controllers
            if controller.live_acquisition_generation_id is not None
        }
        selected_live = {
            (generation.acquisition_generation_id, generation.scope_id)
            for generation in live_generations
        }
        if controller_live != selected_live:
            raise ValueError("checkpoint LIVE discovery is incomplete")
        selected_generation: dict[tuple[str, int], tuple[_Any, _Any]] = {}
        for generation, current in zip(
            live_generations + unresolved_generations,
            live_currents + unresolved_currents,
            strict=True,
        ):
            coordinate = (
                _acquisition_id(generation.acquisition_generation_id),
                generation.scope_id,
            )
            retained = selected_generation.get(coordinate)
            if retained is not None and retained != (generation, current):
                raise ValueError("checkpoint generation union is spliced")
            selected_generation[coordinate] = (generation, current)
        if len(selected_generation) >= _RUNTIME_CHECKPOINT_CAP:
            raise OverflowError("checkpoint selected-generation union is too large")
        selected_coordinates = set(selected_generation)

        later_rows: list[tuple[tuple[_Any, ...], ...]] = []
        for query_index in range(4, 13):
            rows = _checkpoint_required_rows(
                _checkpoint_query_rows(
                    connection,
                    _RUNTIME_CHECKPOINT_SELECTION_SQL[query_index],
                    parameters,
                )
            )
            _checkpoint_rows_are_bounded(rows)
            later_rows.append(rows)

        effects_by_id: dict[int, _records.VenueEffectRecord] = {}
        for row in later_rows[0]:
            if len(row) != 25:
                raise ValueError("checkpoint Q4a has the wrong vector length")
            effect = _build_effect(row)
            if (
                effect.disposition not in ("OPEN", "INVALIDATED")
                or (
                    _acquisition_id(effect.acquisition_generation_id),
                    effect.scope_id,
                )
                not in selected_coordinates
            ):
                raise ValueError("checkpoint Q4a admitted an unselected effect")
            if effect.effect_id in effects_by_id:
                raise ValueError("checkpoint effect is duplicated")
            effects_by_id[effect.effect_id] = effect

        late_owners: dict[tuple[int, str, str], _records.VenueIdentityOwnerRecord] = {}
        for row in later_rows[1]:
            if len(row) != 33:
                raise ValueError("checkpoint Q4b has the wrong vector length")
            owner = _build_owner(row[0:8])
            effect = _build_effect(row[8:33])
            if (
                not owner.admitted_after_effect_closed
                or owner.effect_id != effect.effect_id
                or owner.scope_id != effect.scope_id
                or owner.owner_generation_id != effect.acquisition_generation_id
                or effect.disposition != "CLOSED"
                or (
                    _acquisition_id(effect.acquisition_generation_id),
                    effect.scope_id,
                )
                not in selected_coordinates
            ):
                raise ValueError("checkpoint Q4b admitted a spliced late owner")
            retained_effect = effects_by_id.get(effect.effect_id)
            if retained_effect is not None and retained_effect != effect:
                raise ValueError("checkpoint effect vectors conflict")
            effects_by_id[effect.effect_id] = effect
            owner_key = (
                owner.effect_id,
                owner.owner_id.value,
                owner.observation_id.value,
            )
            if owner_key in late_owners:
                raise ValueError("checkpoint late owner is duplicated")
            late_owners[owner_key] = owner

        unresolved_count = sum(
            current.unresolved_effect_count
            for current in live_currents + unresolved_currents
        )
        if unresolved_count >= _RUNTIME_CHECKPOINT_CAP:
            raise OverflowError("checkpoint unresolved-effect sum is too large")
        if len(effects_by_id) != unresolved_count:
            raise ValueError("checkpoint effect union disagrees with counters")
        qualifying_effect_ids = set(effects_by_id)

        owners = tuple(_build_owner(row) for row in later_rows[2])
        claims = tuple(_build_claim(row) for row in later_rows[3])
        acceptances = tuple(_build_acceptance_set(row) for row in later_rows[4])
        evidence = tuple(_build_evidence(row) for row in later_rows[5])
        closures = tuple(_build_closure(row) for row in later_rows[6])
        owner_by_key = _checkpoint_unique_records(
            owners,
            lambda owner: (
                owner.effect_id,
                owner.owner_id.value,
                owner.observation_id.value,
            ),
        )
        if any(owner.effect_id not in qualifying_effect_ids for owner in owners):
            raise ValueError("checkpoint owner has no qualifying effect")
        if any(owner_by_key.get(key) != owner for key, owner in late_owners.items()):
            raise ValueError("checkpoint late owner is absent from owner discovery")
        claim_by_effect = _checkpoint_unique_records(
            claims, lambda claim: claim.effect_id
        )
        acceptance_by_effect = _checkpoint_unique_records(
            acceptances, lambda acceptance: acceptance.effect_id
        )
        _checkpoint_unique_records(
            evidence,
            lambda item: (item.effect_id, item.evidence_ordinal, item.evidence_id),
        )
        evidence_acceptance_ids = {item.acceptance_set_id for item in evidence}
        if (
            any(effect_id not in qualifying_effect_ids for effect_id in claim_by_effect)
            or any(
                effect_id not in qualifying_effect_ids
                for effect_id in acceptance_by_effect
            )
            or any(item.effect_id not in qualifying_effect_ids for item in evidence)
        ):
            raise ValueError("checkpoint effect child is spliced")
        for item in evidence:
            acceptance = acceptance_by_effect.get(item.effect_id)
            if (
                acceptance is None
                or acceptance.acceptance_set_id != item.acceptance_set_id
            ):
                raise ValueError("checkpoint evidence has no selected acceptance")

        closure_by_owner = _checkpoint_unique_records(
            closures,
            lambda closure: (closure.scope_id, closure.owner_id.value),
        )
        owner_coordinates = {(owner.scope_id, owner.owner_id.value) for owner in owners}
        if any(key not in owner_coordinates for key in closure_by_owner):
            raise ValueError("checkpoint closure has no selected owner")

        routes: list[_records.AcquisitionRootRouteRecord] = []
        roots: list[_records.RootFillRecord] = []
        fact_heads: list[_records.ExecutionFactHeadRecord] = []
        current_facts: list[_records.ExecutionFactRecord] = []
        route_by_owner: dict[tuple[int, str, str], _Any] = {}
        root_by_id: dict[int, _Any] = {}
        fact_head_by_root: dict[int, _Any] = {}
        fact_by_root: dict[int, _Any] = {}
        for row in later_rows[7]:
            if len(row) != 62:
                raise ValueError("checkpoint Q8 has the wrong vector length")
            route = _build_route(row[0:8])
            root = _build_root_fill(row[8:29])
            head_values = row[30:33]
            fact_values = row[33:62]
            present = _checkpoint_presence(
                row[29], head_values + fact_values, optional=True
            )
            owner_key = (
                route.effect_id,
                route.owner_id.value,
                route.observation_id.value,
            )
            selected_owner = owner_by_key.get(owner_key)
            if (
                selected_owner is None
                or route.root_fill_key_id != root.root_fill_key_id
                or route.scope_id != root.scope_id
                or route.acquisition_generation_id != root.owner_generation_id
                or route.effect_id != selected_owner.effect_id
                or route.scope_id != selected_owner.scope_id
                or route.acquisition_generation_id != selected_owner.owner_generation_id
                or owner_key in route_by_owner
                or root.root_fill_key_id in root_by_id
            ):
                raise ValueError("checkpoint route/root vectors do not agree")
            routes.append(route)
            roots.append(root)
            route_by_owner[owner_key] = route
            root_by_id[root.root_fill_key_id] = root
            if present:
                fact_head = _build_fact_head(head_values)
                fact = _build_execution_fact(fact_values)
                if (
                    fact_head.root_fill_key_id != root.root_fill_key_id
                    or fact.root_fill_key_id != root.root_fill_key_id
                    or fact_head.fact_id != fact.fact_id
                    or fact_head.fact_ordinal != fact.fact_ordinal
                    or root.current_fact_id != fact.fact_id
                    or root.economics_head_ordinal != fact.fact_ordinal
                ):
                    raise ValueError("checkpoint current fact is spliced")
                fact_heads.append(fact_head)
                current_facts.append(fact)
                fact_head_by_root[root.root_fill_key_id] = fact_head
                fact_by_root[root.root_fill_key_id] = fact

        streams: list[_records.MarketStreamAuthorityRecord] = []
        cursors: list[_records.MarketCursorRecord] = []
        streams_by_generation: dict[str, list[_Any]] = {}
        stream_by_identity: dict[str, _Any] = {}
        cursor_by_stream: dict[str, _Any] = {}
        for row in later_rows[8]:
            if len(row) != 19:
                raise ValueError("checkpoint Q9 has the wrong vector length")
            stream = _build_market_stream(row[0:8])
            cursor_values = row[9:19]
            present = _checkpoint_presence(row[8], cursor_values, optional=True)
            generation_key = _acquisition_id(stream.acquisition_generation_id)
            stream_key = stream.stream_generation_id.value
            if (
                generation_key,
                stream.scope_id,
            ) not in selected_coordinates or stream_key in stream_by_identity:
                raise ValueError("checkpoint stream has no selected generation")
            streams.append(stream)
            stream_by_identity[stream_key] = stream
            streams_by_generation.setdefault(generation_key, []).append(stream)
            if present:
                cursor = _build_market_cursor(cursor_values)
                if cursor.stream_generation_id != stream.stream_generation_id:
                    raise ValueError("checkpoint cursor is spliced")
                cursors.append(cursor)
                cursor_by_stream[stream.stream_generation_id.value] = cursor

        for controller, protection in zip(controllers, protections, strict=True):
            if protection.active_acquisition_generation_id is None:
                continue
            generation_key = _acquisition_id(
                protection.active_acquisition_generation_id
            )
            selected_stream = stream_by_identity.get(
                protection.active_stream_generation_id.value
                if protection.active_stream_generation_id is not None
                else ""
            )
            if (
                controller.live_acquisition_generation_id
                != protection.active_acquisition_generation_id
                or selected_stream is None
                or selected_stream.stream_generation_id
                != protection.active_stream_generation_id
                or selected_stream.generation_mandate_commitment_sha256
                != protection.active_generation_mandate_commitment_sha256
                or selected_stream.source_profile_id
                != protection.active_source_profile_id
                or selected_stream.session_id != protection.active_session_id
                or selected_stream.sequence_mode != protection.active_sequence_mode
            ):
                raise ValueError("checkpoint active protection stream is spliced")

        effects = tuple(
            sorted(
                effects_by_id.values(),
                key=lambda effect: (effect.created_ordinal, effect.effect_id),
            )
        )
        owners = tuple(
            sorted(
                owners,
                key=lambda owner: (
                    owner.effect_id,
                    owner.owner_id.value,
                    owner.observation_id.value,
                ),
            )
        )
        selected_generation_ids = {coordinate[0] for coordinate in selected_coordinates}
        owner_effect_absences = tuple(
            _checkpoint_absence(
                "owner/effect",
                "owner-effect",
                _checkpoint_field_int(effect_id),
            )
            for effect_id in sorted(
                qualifying_effect_ids - {owner.effect_id for owner in owners}
            )
        )
        claim_effect_absences = tuple(
            _checkpoint_absence(
                "claim/effect", "claim-effect", _checkpoint_field_int(effect_id)
            )
            for effect_id in sorted(qualifying_effect_ids - set(claim_by_effect))
        )
        acceptance_effect_absences = tuple(
            _checkpoint_absence(
                "acceptance/effect",
                "acceptance-effect",
                _checkpoint_field_int(effect_id),
            )
            for effect_id in sorted(qualifying_effect_ids - set(acceptance_by_effect))
        )
        evidence_acceptance_absences = tuple(
            _checkpoint_absence(
                "evidence/acceptance",
                "evidence-acceptance",
                _checkpoint_field_int(acceptance.acceptance_set_id),
            )
            for acceptance in acceptances
            if acceptance.acceptance_set_id not in evidence_acceptance_ids
        )
        closure_owner_absences = tuple(
            _checkpoint_absence(
                "closure/owner",
                "closure-owner",
                _checkpoint_field_int(owner.scope_id),
                _checkpoint_field_text(owner.owner_id.value),
            )
            for owner in owners
            if (owner.scope_id, owner.owner_id.value) not in closure_by_owner
        )
        route_owner_absences = tuple(
            _checkpoint_absence(
                "route/owner",
                "route-owner",
                _checkpoint_field_int(owner.effect_id),
                _checkpoint_field_text(owner.owner_id.value),
                _checkpoint_field_text(owner.observation_id.value),
            )
            for owner in owners
            if (
                owner.effect_id,
                owner.owner_id.value,
                owner.observation_id.value,
            )
            not in route_by_owner
        )
        fact_head_root_absences = tuple(
            _checkpoint_absence(
                "fact-head/root",
                "fact-head-root",
                _checkpoint_field_int(root.root_fill_key_id),
            )
            for root in roots
            if root.root_fill_key_id not in fact_head_by_root
        )
        current_fact_root_absences = tuple(
            _checkpoint_absence(
                "current-fact/root",
                "current-fact-root",
                _checkpoint_field_int(root.root_fill_key_id),
            )
            for root in roots
            if root.root_fill_key_id not in fact_by_root
        )
        stream_generation_absences = tuple(
            _checkpoint_absence(
                "stream/generation",
                "stream-generation",
                _checkpoint_field_text(generation_id),
            )
            for generation_id in sorted(
                selected_generation_ids - set(streams_by_generation)
            )
        )
        cursor_stream_absences = tuple(
            _checkpoint_absence(
                "cursor/stream",
                "cursor-stream",
                _checkpoint_field_text(stream.stream_generation_id.value),
            )
            for stream in streams
            if stream.stream_generation_id.value not in cursor_by_stream
        )
        (
            owner_effect_absences,
            claim_effect_absences,
            acceptance_effect_absences,
            evidence_acceptance_absences,
            closure_owner_absences,
            route_owner_absences,
            fact_head_root_absences,
            current_fact_root_absences,
            stream_generation_absences,
            cursor_stream_absences,
        ) = tuple(
            tuple(sorted(items, key=lambda item: item[1]))
            for items in (
                owner_effect_absences,
                claim_effect_absences,
                acceptance_effect_absences,
                evidence_acceptance_absences,
                closure_owner_absences,
                route_owner_absences,
                fact_head_root_absences,
                current_fact_root_absences,
                stream_generation_absences,
                cursor_stream_absences,
            )
        )
        query_counts = tuple(
            len(rows) for rows in (q1, q2, *generation_rows, *later_rows)
        )
        if len(query_counts) != 13:
            raise ValueError("checkpoint selection did not execute thirteen queries")

        selection = _checkpoint_issue_selection_set(
            (
                tuple(scopes),
                tuple(controllers),
                tuple(protections),
                live_generations,
                live_currents,
                unresolved_generations,
                unresolved_currents,
                effects,
                owners,
                claims,
                acceptances,
                evidence,
                closures,
                tuple(routes),
                tuple(roots),
                tuple(fact_heads),
                tuple(current_facts),
                tuple(streams),
                tuple(cursors),
                owner_effect_absences,
                claim_effect_absences,
                acceptance_effect_absences,
                evidence_acceptance_absences,
                closure_owner_absences,
                route_owner_absences,
                fact_head_root_absences,
                current_fact_root_absences,
                stream_generation_absences,
                cursor_stream_absences,
                query_counts,
            )
        )
        if controllers:
            target_head = max(
                controller.currentness_head_ordinal for controller in controllers
            )
        elif predecessor is not None:
            target_head = predecessor.currentness_head_ordinal
        else:
            target_head = 0
        if (
            predecessor is not None
            and target_head < predecessor.currentness_head_ordinal
        ):
            raise ValueError("checkpoint target head regresses")
        target_version = (
            predecessor.checkpoint_version_ordinal + 1 if predecessor is not None else 1
        )
        proof = _checkpoint_issue_selection_proof(
            request,
            application,
            execution_profile,
            market_profile,
            predecessor,
            target_head,
            target_version,
            selection,
        )
        return _outcome(_records.RepositoryOutcomeKind.FOUND, proof)
    except _CheckpointSelectionOutcome as failure:
        return _outcome(failure.kind)
    except (TypeError, ValueError, OverflowError, IndexError):
        return _integrity()


def _checkpoint_proof_is_authentic(proof: object) -> bool:
    proof_type = _runtime_checkpoint_records_member("RuntimeCheckpointSelectionProof")
    if type(proof) is not proof_type:
        return False
    checker = _runtime_checkpoint_records_member(
        "_runtime_checkpoint_selection_proof_is_authentic"
    )
    return checker(proof) is True


def _checkpoint_envelope_is_authentic(envelope: object) -> bool:
    envelope_type = _runtime_checkpoint_codec_member("RuntimeCheckpointEnvelope")
    if type(envelope) is not envelope_type:
        return False
    checker = _runtime_checkpoint_codec_member("_envelope_is_authentic")
    return checker(envelope) is True


def _checkpoint_payload_parameters(payload: object) -> tuple[_Any, ...]:
    payload_type = _runtime_checkpoint_records_member("RuntimeCheckpointPayloadRecord")
    if type(payload) is not payload_type:
        raise TypeError("checkpoint payload record must be exact")
    exact_payload = _cast(_Any, payload)
    return (
        _application_id(exact_payload.application_generation_id),
        _exact_text(exact_payload.execution_profile_id),
        _exact_text(exact_payload.market_source_profile_id),
        _exact_int(exact_payload.currentness_head_ordinal),
        _exact_int(exact_payload.checkpoint_version_ordinal),
        _exact_bytes(exact_payload.payload_bytes),
        _exact_int(exact_payload.payload_length),
        _exact_text(exact_payload.payload_sha256),
    )


def _checkpoint_head_parameters(
    head: _records.KernelCheckpointRecord,
) -> tuple[_Any, ...]:
    if type(head) is not _records.KernelCheckpointRecord:
        raise TypeError("checkpoint head must be exact")
    return (
        _application_id(head.application_generation_id),
        _exact_int(head.currentness_head_ordinal),
        _exact_text(head.checkpoint_sha256),
        _exact_int(head.checkpoint_version_ordinal),
    )


def _checkpoint_load_head_unchecked(
    connection: _SQLiteConnectionProtocol,
    application_key: str,
) -> _records.RepositoryOutcome[_records.KernelCheckpointRecord]:
    rows_outcome = _checkpoint_query_rows(
        connection,
        _RUNTIME_CHECKPOINT_HEAD_SELECT_SQL,
        (application_key,),
    )
    if rows_outcome.kind is not _records.RepositoryOutcomeKind.FOUND:
        return _outcome(rows_outcome.kind)
    rows = rows_outcome.record
    if rows is None:
        return _integrity()
    if not rows:
        return _outcome(_records.RepositoryOutcomeKind.ABSENT)
    if len(rows) != 1:
        return _integrity()
    try:
        return _outcome(
            _records.RepositoryOutcomeKind.FOUND,
            _build_checkpoint(rows[0]),
        )
    except (TypeError, ValueError, OverflowError, IndexError):
        return _integrity()


def _issue_runtime_checkpoint_write_receipt(
    payload: object,
    predecessor: _records.KernelCheckpointRecord | None,
    resulting: _records.KernelCheckpointRecord,
    selection_commitment: bytes,
) -> _records.RepositoryOutcome[_Any]:
    """Translate only exact receipt-phase validation exceptions."""

    issuer = _runtime_checkpoint_records_member(
        "_issue_runtime_checkpoint_write_receipt"
    )
    try:
        receipt = issuer(
            payload,
            predecessor,
            resulting,
            selection_commitment,
        )
    except Exception as caught:
        if type(caught) in (TypeError, ValueError, OverflowError):
            return _integrity()
        raise
    return _outcome(_records.RepositoryOutcomeKind.APPLIED, receipt)


def store_runtime_checkpoint(
    connection: _SQLiteConnectionProtocol,
    proof: _Any,
    envelope: _Any,
    *,
    capability: _WriteCapability,
) -> _records.RepositoryOutcome[_Any]:
    """Stage payload, CAS the head, reread, then issue one receipt."""

    _require_write_capability(connection, capability)
    if getattr(connection, "in_transaction", False) is not True:
        return _integrity()
    try:
        _verify_schema_connection(connection)
        if not _checkpoint_proof_is_authentic(proof):
            return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
        if not _checkpoint_envelope_is_authentic(envelope):
            return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
        if envelope._provenance != "PROJECTED":
            return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
        proof_binding = _exact_bytes(proof._binding)
        selection_commitment = _exact_bytes(proof.selection_commitment)
        if (
            len(proof_binding) != 32
            or len(selection_commitment) != 32
            or envelope._selection_binding != proof_binding
            or envelope.application_generation_id
            != proof.request.application_generation_id
            or envelope.execution_profile_id != proof.request.execution_profile_id
            or envelope.market_source_profile_id
            != proof.request.market_source_profile_id
            or envelope.currentness_head_ordinal
            != proof.target_currentness_head_ordinal
            or envelope.checkpoint_version_ordinal
            != proof.target_checkpoint_version_ordinal
            or tuple(scope.scope_id for scope in envelope.scopes)
            != tuple(scope.scope_id for scope in proof._selection.scopes)
        ):
            return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
        encoder = _runtime_checkpoint_codec_member("encode_runtime_checkpoint")
        payload_bytes = encoder(envelope)
        if (
            payload_bytes != envelope.canonical_payload_bytes
            or len(payload_bytes) != len(envelope.canonical_payload_bytes)
            or _sha256(payload_bytes).hexdigest() != envelope.payload_sha256
        ):
            return _integrity()
    except (TypeError, ValueError, OverflowError, IndexError):
        return _integrity()

    reselected = select_runtime_checkpoint(connection, proof.request)
    if reselected.kind is _records.RepositoryOutcomeKind.INTEGRITY_FAILURE:
        return _integrity()
    if reselected.kind is not _records.RepositoryOutcomeKind.FOUND:
        return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
    fresh_proof = reselected.record
    if (
        fresh_proof is None
        or not _checkpoint_proof_is_authentic(fresh_proof)
        or fresh_proof._binding != proof._binding
        or fresh_proof.selection_commitment != proof.selection_commitment
        or fresh_proof.predecessor_checkpoint != proof.predecessor_checkpoint
        or fresh_proof.target_currentness_head_ordinal
        != proof.target_currentness_head_ordinal
        or fresh_proof.target_checkpoint_version_ordinal
        != proof.target_checkpoint_version_ordinal
        or fresh_proof._selection != proof._selection
    ):
        return _outcome(_records.RepositoryOutcomeKind.CONFLICT)

    payload_type = _runtime_checkpoint_records_member("RuntimeCheckpointPayloadRecord")
    try:
        payload = payload_type(
            envelope.application_generation_id,
            envelope.execution_profile_id,
            envelope.market_source_profile_id,
            envelope.currentness_head_ordinal,
            envelope.checkpoint_version_ordinal,
            payload_bytes,
            len(payload_bytes),
            envelope.payload_sha256,
        )
        payload_parameters = _checkpoint_payload_parameters(payload)
        resulting = _records.KernelCheckpointRecord(
            envelope.application_generation_id,
            envelope.currentness_head_ordinal,
            envelope.payload_sha256,
            envelope.checkpoint_version_ordinal,
        )
        resulting_parameters = _checkpoint_head_parameters(resulting)
    except (TypeError, ValueError, OverflowError):
        return _integrity()

    try:
        connection.execute(
            _RUNTIME_CHECKPOINT_PAYLOAD_INSERT_SQL,
            payload_parameters,
        )
    except Exception as caught:
        return _classify_runtime_checkpoint_sqlite_failure(
            caught,
            payload_insert=True,
        )

    predecessor = proof.predecessor_checkpoint
    if predecessor is None:
        cas_sql = _RUNTIME_CHECKPOINT_HEAD_INSERT_SQL
        cas_parameters = resulting_parameters + (resulting_parameters[0],)
    else:
        try:
            predecessor_parameters = _checkpoint_head_parameters(predecessor)
        except (TypeError, ValueError, OverflowError):
            return _integrity()
        cas_sql = _RUNTIME_CHECKPOINT_HEAD_UPDATE_SQL
        cas_parameters = resulting_parameters[1:] + predecessor_parameters
    try:
        cursor = connection.execute(cas_sql, cas_parameters)
    except Exception as caught:
        return _classify_runtime_checkpoint_sqlite_failure(
            caught,
            payload_insert=False,
        )
    if cursor.rowcount != 1:
        return _outcome(_records.RepositoryOutcomeKind.CONFLICT)

    reread = _checkpoint_load_head_unchecked(
        connection,
        resulting_parameters[0],
    )
    if (
        reread.kind is not _records.RepositoryOutcomeKind.FOUND
        or reread.record != resulting
    ):
        return _integrity()
    return _issue_runtime_checkpoint_write_receipt(
        payload,
        predecessor,
        resulting,
        selection_commitment,
    )


def load_runtime_checkpoint_payload(
    connection: _SQLiteConnectionProtocol,
    application_generation_id: _identity.ApplicationGenerationId,
    currentness_head_ordinal: int,
    checkpoint_version_ordinal: int,
    payload_sha256: str,
) -> _records.RepositoryOutcome[_Any]:
    """Load and authenticate one immutable payload by its complete identity."""

    try:
        _verify_schema_connection(connection)
        parameters = (
            _application_id(application_generation_id),
            _exact_int(currentness_head_ordinal),
            _exact_int(checkpoint_version_ordinal),
            _exact_text(payload_sha256),
        )
    except (TypeError, ValueError, OverflowError):
        return _integrity()
    rows_outcome = _checkpoint_query_rows(
        connection,
        _RUNTIME_CHECKPOINT_PAYLOAD_SELECT_SQL,
        parameters,
    )
    if rows_outcome.kind is not _records.RepositoryOutcomeKind.FOUND:
        return _outcome(rows_outcome.kind)
    rows = rows_outcome.record
    if rows is None:
        return _integrity()
    if not rows:
        return _outcome(_records.RepositoryOutcomeKind.ABSENT)
    if len(rows) != 1:
        return _integrity()
    payload_type = _runtime_checkpoint_records_member("RuntimeCheckpointPayloadRecord")
    try:
        row = rows[0]
        if len(row) != 8:
            raise ValueError("checkpoint payload has the wrong vector length")
        payload = payload_type(
            _decode_application_id(row[0]),
            _exact_text(row[1]),
            _exact_text(row[2]),
            _exact_int(row[3]),
            _exact_int(row[4]),
            _exact_bytes(row[5]),
            _exact_int(row[6]),
            _exact_text(row[7]),
        )
        payload_parameters = _checkpoint_payload_parameters(payload)
        if (
            payload_parameters[0] != parameters[0]
            or payload_parameters[3] != parameters[1]
            or payload_parameters[4] != parameters[2]
            or payload_parameters[7] != parameters[3]
            or payload.payload_length != len(payload.payload_bytes)
            or payload.payload_sha256 != _sha256(payload.payload_bytes).hexdigest()
        ):
            return _integrity()
    except (TypeError, ValueError, OverflowError, IndexError):
        return _integrity()
    return _outcome(_records.RepositoryOutcomeKind.FOUND, payload)


def load_runtime_checkpoint(
    connection: _SQLiteConnectionProtocol,
    request: _Any,
) -> _records.RepositoryOutcome[_Any]:
    """Compose head, payload, fresh selection, decode, and final-head proof."""

    if getattr(connection, "in_transaction", False) is not True:
        return _integrity()
    load_request_type = _runtime_checkpoint_records_member(
        "RuntimeCheckpointLoadRequest"
    )
    if type(request) is not load_request_type:
        return _integrity()
    try:
        _verify_schema_connection(connection)
        application_key = _application_id(request.application_generation_id)
        execution_profile_id = _exact_text(request.execution_profile_id)
        market_profile_id = _exact_text(request.market_source_profile_id)
    except (TypeError, ValueError, OverflowError):
        return _integrity()
    initial = _checkpoint_load_head_unchecked(connection, application_key)
    if initial.kind is not _records.RepositoryOutcomeKind.FOUND:
        return _outcome(initial.kind)
    initial_head = initial.record
    if initial_head is None:
        return _integrity()
    payload_outcome = load_runtime_checkpoint_payload(
        connection,
        request.application_generation_id,
        initial_head.currentness_head_ordinal,
        initial_head.checkpoint_version_ordinal,
        initial_head.checkpoint_sha256,
    )
    if payload_outcome.kind is _records.RepositoryOutcomeKind.ABSENT:
        return _integrity()
    if payload_outcome.kind is not _records.RepositoryOutcomeKind.FOUND:
        return _outcome(payload_outcome.kind)
    payload = payload_outcome.record
    if payload is None:
        return _integrity()
    selection_request_type = _runtime_checkpoint_records_member(
        "RuntimeCheckpointSelectionRequest"
    )
    try:
        selection_request = selection_request_type(
            request.application_generation_id,
            execution_profile_id,
            market_profile_id,
            initial_head,
        )
    except (TypeError, ValueError, OverflowError):
        return _integrity()
    selected = select_runtime_checkpoint(connection, selection_request)
    if selected.kind is _records.RepositoryOutcomeKind.INTEGRITY_FAILURE:
        return _integrity()
    if selected.kind is not _records.RepositoryOutcomeKind.FOUND:
        return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
    proof = selected.record
    if proof is None or not _checkpoint_proof_is_authentic(proof):
        return _integrity()
    load_proof_issuer = _runtime_checkpoint_records_member(
        "_issue_runtime_checkpoint_load_proof_binding"
    )
    try:
        load_proof_binding = load_proof_issuer(
            request,
            initial_head,
            payload,
            proof,
        )
        decoder = _runtime_checkpoint_codec_member("_decode_runtime_checkpoint")
        envelope = decoder(payload.payload_bytes, load_proof_binding)
        encoder = _runtime_checkpoint_codec_member("encode_runtime_checkpoint")
        if (
            not _checkpoint_envelope_is_authentic(envelope)
            or envelope._provenance != "LOADED"
            or envelope.application_generation_id != request.application_generation_id
            or envelope.execution_profile_id != execution_profile_id
            or envelope.market_source_profile_id != market_profile_id
            or envelope.currentness_head_ordinal
            != initial_head.currentness_head_ordinal
            or envelope.checkpoint_version_ordinal
            != initial_head.checkpoint_version_ordinal
            or envelope.payload_sha256 != initial_head.checkpoint_sha256
            or encoder(envelope) != payload.payload_bytes
        ):
            return _integrity()
    except (TypeError, ValueError, OverflowError, IndexError):
        return _integrity()
    final = _checkpoint_load_head_unchecked(connection, application_key)
    if (
        final.kind is not _records.RepositoryOutcomeKind.FOUND
        or final.record != initial_head
    ):
        return _outcome(_records.RepositoryOutcomeKind.CONFLICT)
    return _outcome(_records.RepositoryOutcomeKind.FOUND, envelope)


__all__ = (
    "advance_market_cursor",
    "advance_protection_authority",
    "advance_symbol_controller",
    "advance_venue_effect",
    "claim_durable_input",
    "finalize_durable_input",
    "load_acceptance_evidence",
    "load_acceptance_set",
    "load_acceptance_set_for_effect",
    "load_acquisition_generation",
    "load_acquisition_generation_current",
    "load_acquisition_root_route",
    "load_application_generation",
    "load_broker_outbox",
    "load_closure_head",
    "load_current_proof",
    "load_decision_receipt",
    "load_dispatch_claim",
    "load_dispatch_claim_for_effect",
    "load_durable_input",
    "load_durable_input_by_semantic_key",
    "load_durable_input_outcome",
    "load_durable_input_semantic_key",
    "load_execution_fact",
    "load_execution_fact_by_source",
    "load_execution_fact_head",
    "load_execution_profile",
    "load_latest_acceptance_evidence",
    "load_live_acquisition_generation",
    "load_market_cursor",
    "load_market_source_profile",
    "load_market_stream_authority",
    "load_open_venue_effects",
    "load_protection_authority",
    "load_root_fill",
    "load_root_fill_by_external",
    "load_runtime_checkpoint",
    "load_runtime_checkpoint_payload",
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
    "store_broker_outbox",
    "store_closure",
    "store_dispatch_claim",
    "store_decision_receipt",
    "store_durable_input_outcome",
    "store_durable_input_semantic_key",
    "store_execution_fact",
    "store_execution_profile",
    "store_market_cursor",
    "store_market_source_profile",
    "store_market_stream_authority",
    "store_protection_authority",
    "store_root_fill",
    "store_runtime_checkpoint",
    "store_scope",
    "store_symbol_controller",
    "store_venue_effect",
    "store_venue_identity_owner",
    "select_runtime_checkpoint",
)
