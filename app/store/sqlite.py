"""SQLite-backed StateStore — the durable store the running app uses.

One local SQLite file, accessed only through this class. Design points that
satisfy ``docs/02_DATA_AND_PERSISTENCE.md``:

* **Idempotent schema** — ``CREATE TABLE IF NOT EXISTS`` on every startup.
* **Atomic multi-row writes** — every method that writes more than one row wraps
  the writes in a single ``BEGIN``/``COMMIT`` (rolled back on failure), so a
  crash mid-write can't leave the audit trail inconsistent with the state it
  describes.
* **Append-only fills** — there is no UPDATE or DELETE issued against ``fills``
  anywhere in this file. Duplicate protection is a **partial composite** unique
  index ``idx_fills_order_source`` on ``(order_id, source_fill_id)`` WHERE
  ``source_fill_id IS NOT NULL`` (Item 5 / F1) — per-order, so two different
  orders may legitimately report the same ``source_fill_id``; NULLs are exempt.
* **Position is derived from the event log** (Spine v2 wave 3a-truth,
  ``event_truth``) — there is no positions table; positions are folded from the
  append-only ``execution_events`` ``FILL`` rows via
  :func:`app.events.projectors.project_symbol_position`, the exact same code
  path the in-memory store uses (Rule 7). The ``fills`` table is a compatibility
  read-model kept in lockstep; a store opened on pre-wave-3a fills backfills a
  ``FILL`` event per fill at init.

The ``sqlite3`` driver is synchronous; calls are made under an ``asyncio.Lock``
that serializes them, so a single shared connection is safe and each
transaction runs alone. This is single-user localhost — the lock, not threads,
is the concurrency model (see ``docs/01_ARCHITECTURE.md``).
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_UNRESOLVED,
    Candidate,
    EventAuthority,
    EventSource,
    CandidateStatus,
    Event,
    ExecutionEvent,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSnapshot,
    SellIntent,
    SellIntentStatus,
    SellReason,
    SessionRecord,
    SessionStatus,
    SubmitRecoveryRecord,
    TradingMode,
    TradingState,
    WatchlistSymbol,
    utcnow,
)
from app.events.projectors import (
    active_emergency_reduce_overrides,
    compose_trading_state,
    control_trading_state,
    current_trading_state,
    project_symbol_position,
    quarantined_symbols,
    reconcile_trading_state,
    timeout_quarantined_order_ids,
)
from app.store.base import (
    CLAIM_BLOCKED,
    CLAIM_CLAIMED,
    FLATTEN_CREATED,
    FLATTEN_EXISTING,
    FLATTEN_FLAT,
    CandidateTransitionError,
    EmergencyReduceBlockedError,
    FillAppendResult,
    FlattenBlockedError,
    FlattenResult,
    InvalidOrderError,
    RiskLimits,
    SellIntentTransitionError,
    SessionAlreadyClosedError,
    SessionClosedError,
    StateStore,
    SubmissionClaim,
    UnknownEntityError,
    normalize_symbol,
)
from app.store.core import (
    CREATE_ORDER_REJECT,
    FILL_DUPLICATE,
    FILL_REJECT,
    execution_event_for_fill,
    FLATTEN_FLAT as _PLAN_FLATTEN_FLAT,
    FLATTEN_EXISTING as _PLAN_FLATTEN_EXISTING,
    FLATTEN_DENIED_HALTED,
    FLATTEN_SUPERSEDE_AND_CREATE,
    ORDER_TRANSITION_NOOP,
    ORDER_TRANSITION_REJECT,
    OrderEventedTransitionPlan,
    plan_append_fill,
    plan_claim_order_for_submission,
    plan_close_session,
    plan_create_order_for_candidate,
    plan_create_order_for_sell_intent,
    plan_flatten_position,
    plan_quarantine_timed_out_order,
    plan_reconcile_resolve_order,
    plan_resolve_timeout_quarantine,
    plan_transition_order,
    reconcile_trading_state_event,
    trading_state_change_event,
    emergency_reduce_override_event,
    require_bool,
    require_recovery_status,
    require_status_enum,
    recovery_status_event,
    sell_intent_is_active,
)
from app.transitions import (
    CANDIDATE_TIMESTAMP,
    CANDIDATE_TRANSITIONS,
    SELL_INTENT_TIMESTAMP,
    SELL_INTENT_TRANSITIONS,
)
from app.policy import (
    NON_TERMINAL_ORDER_STATUSES,
    candidate_numeric_reason,
    existing_exposure,
    order_candidate_match_reason,
    whole_count_reason,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    symbol     TEXT PRIMARY KEY,
    armed      INTEGER NOT NULL DEFAULT 0,
    added_at   TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    armed_at   TEXT
);

CREATE TABLE IF NOT EXISTS candidates (
    id                    TEXT PRIMARY KEY,
    symbol                TEXT NOT NULL,
    status                TEXT NOT NULL,
    strategy              TEXT,
    reason                TEXT,
    risk_decision         TEXT,
    suggested_quantity    INTEGER,
    suggested_limit_price REAL,
    session_id            TEXT,
    order_id              TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    approved_at           TEXT,
    rejected_at           TEXT,
    expired_at            TEXT,
    ordered_at            TEXT
);

-- Phase 7: candidate_id is nullable (a SELL order carries sell_intent_id instead
-- of candidate_id — the XOR-origin invariant). On a pre-Phase-7 DB the live
-- column is candidate_id TEXT NOT NULL with no sell_intent_id; _migrate() rebuilds
-- this table (SQLite has no ALTER COLUMN and CREATE TABLE IF NOT EXISTS is a
-- no-op against an existing table).
CREATE TABLE IF NOT EXISTS orders (
    id                TEXT PRIMARY KEY,
    candidate_id      TEXT,
    sell_intent_id    TEXT,
    symbol            TEXT NOT NULL,
    side              TEXT NOT NULL,
    order_type        TEXT NOT NULL,
    quantity          INTEGER NOT NULL,
    limit_price       REAL,
    status            TEXT NOT NULL,
    filled_quantity   INTEGER NOT NULL DEFAULT 0,
    replaces_order_id TEXT,
    broker_order_id   TEXT,
    session_id        TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    submitted_at      TEXT,
    filled_at         TEXT,
    canceled_at       TEXT,
    rejected_at       TEXT
);

-- Phase 7 — Sell-Side Protection: the sell-intent lifecycle (analogue of
-- candidates). One SELL order per intent; open intents expire at session close.
CREATE TABLE IF NOT EXISTS sell_intents (
    id              TEXT PRIMARY KEY,
    symbol          TEXT NOT NULL,
    reason          TEXT NOT NULL,
    status          TEXT NOT NULL,
    target_quantity INTEGER NOT NULL,
    floor_price     REAL,
    observed_price  REAL,
    session_id      TEXT,
    order_id        TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    approved_at     TEXT,
    rejected_at     TEXT,
    expired_at      TEXT,
    ordered_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_sell_intents_symbol ON sell_intents(symbol);

-- Append-only. No UPDATE/DELETE is ever issued against this table.
-- Dedup is per-(order_id, source_fill_id) via idx_fills_order_source, NOT a
-- column-level UNIQUE on source_fill_id alone (Item 5 / F1): two different orders
-- may legitimately report a fill with the same source_fill_id string.
CREATE TABLE IF NOT EXISTS fills (
    id             TEXT PRIMARY KEY,
    order_id       TEXT NOT NULL,
    symbol         TEXT NOT NULL,
    side           TEXT NOT NULL,
    quantity       INTEGER NOT NULL,
    price          REAL NOT NULL,
    source_fill_id TEXT,
    session_id     TEXT,
    filled_at      TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fills_symbol ON fills(symbol);
-- idx_fills_session and idx_fills_order_source are created in initialize()
-- *after* _migrate, so they work on databases migrated from older schemas
-- (pre-D-007 session_id column; pre-Item-5 column-level UNIQUE rebuild).

-- Point-in-time positions captured at session close (D-007). Fills remain the
-- source of truth; these are a fast, accurate read for closed sessions.
CREATE TABLE IF NOT EXISTS position_snapshots (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    quantity      INTEGER NOT NULL,
    cost_basis    REAL NOT NULL,
    average_price REAL,
    captured_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_session ON position_snapshots(session_id);

CREATE TABLE IF NOT EXISTS events (
    id             TEXT PRIMARY KEY,
    event_type     TEXT NOT NULL,
    message        TEXT NOT NULL DEFAULT '',
    symbol         TEXT,
    candidate_id   TEXT,
    order_id       TEXT,
    fill_id        TEXT,
    payload        TEXT NOT NULL DEFAULT '{}',
    session_id     TEXT,
    correlation_id TEXT,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT PRIMARY KEY,
    session_date TEXT NOT NULL,
    mode         TEXT NOT NULL,
    session_type TEXT,
    status       TEXT NOT NULL,
    kill_switch  INTEGER NOT NULL DEFAULT 0,
    buys_paused  INTEGER NOT NULL DEFAULT 0,
    trading_state TEXT NOT NULL DEFAULT 'active',
    opened_at    TEXT NOT NULL,
    closed_at    TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

-- Durable broker-submit recovery ledger (D-017): a broker order accepted
-- upstream whose local SUBMITTING->SUBMITTED persist failed. The monitoring
-- tick's recovery step polls/cancels broker_order_id until cleanup_status
-- leaves 'unresolved'.
CREATE TABLE IF NOT EXISTS submit_recoveries (
    id               TEXT PRIMARY KEY,
    local_order_id   TEXT NOT NULL,
    broker_order_id  TEXT NOT NULL,
    client_order_id  TEXT,
    symbol           TEXT NOT NULL,
    side             TEXT NOT NULL,
    quantity         INTEGER NOT NULL,
    limit_price      REAL,
    failure_reason   TEXT NOT NULL,
    cleanup_status   TEXT NOT NULL DEFAULT 'unresolved',
    retry_count      INTEGER NOT NULL DEFAULT 0,
    session_id       TEXT,
    created_at       TEXT NOT NULL,
    last_attempt_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_recoveries_status ON submit_recoveries(cleanup_status);

-- Spine v2 execution-event log (Phase 2): the append-only event-sourcing
-- truth (§11), distinct from the audit `events` table above. `sequence` is a
-- monotonic per-store ordering key (UNIQUE enforces no collision/gap at the DB
-- level); `dedupe_key` UNIQUE enforces INV-5 idempotency (SQLite treats NULLs
-- as distinct, so un-deduped events with NULL keys coexist freely) AND creates
-- the implicit lookup index the dedupe SELECT uses — no separate index needed.
-- Phase 2 is shadow: nothing writes here on the production path yet.
CREATE TABLE IF NOT EXISTS execution_events (
    id              TEXT PRIMARY KEY,
    sequence        INTEGER NOT NULL UNIQUE,
    schema_version  INTEGER NOT NULL,
    event_type      TEXT NOT NULL,
    source          TEXT NOT NULL,
    authority       TEXT NOT NULL,
    dedupe_key      TEXT UNIQUE,
    ts_event        TEXT,
    ts_init         TEXT NOT NULL,
    symbol          TEXT,
    side            TEXT,
    quantity        INTEGER,
    price           REAL,
    order_id        TEXT,
    primary_id      TEXT,
    spawn_id        TEXT,
    session_id      TEXT,
    correlation_id  TEXT,
    payload         TEXT NOT NULL DEFAULT '{}'
);
"""


def _dt(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _bit(value: bool) -> int:
    return 1 if value else 0


class SqliteStateStore(StateStore):
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._lock = asyncio.Lock()
        self._conn: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------ #
    # Connection / transactions
    # ------------------------------------------------------------------ #
    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(self._db_path), check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            conn.isolation_level = None  # autocommit; we manage BEGIN/COMMIT
            self._conn = conn
        return self._conn

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Cursor]:
        """Run a multi-row write atomically. Commits on success, rolls back on
        any exception. Callers already hold ``self._lock``."""

        conn = self._connect()
        cur = conn.cursor()
        cur.execute("BEGIN")
        try:
            yield cur
            cur.execute("COMMIT")
        except BaseException:
            cur.execute("ROLLBACK")
            raise
        finally:
            cur.close()

    async def initialize(self) -> None:
        async with self._lock:
            conn = self._connect()
            conn.executescript(SCHEMA)
            self._migrate(conn)
            # Created after migration so they work on databases migrated from
            # older schemas (a fills-table rebuild drops the table's indexes).
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_fills_symbol ON fills(symbol)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_fills_session "
                "ON fills(session_id)"
            )
            # Per-(order_id, source_fill_id) dedup (Item 5). Partial index so the
            # uniqueness applies only when source_fill_id is present. This CREATE
            # can only fail if the existing rows already contain a duplicate
            # (order_id, source_fill_id) pair — impossible for any DB this code
            # ever produced, because every prior schema enforced the *stricter*
            # column-level UNIQUE on source_fill_id alone. It fails closed (no
            # silent data change) if a hand-crafted DB ever violated that.
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_fills_order_source "
                "ON fills(order_id, source_fill_id) "
                "WHERE source_fill_id IS NOT NULL"
            )
            # Index the event-log position read path (symbol + event_type); the
            # flip to event-truth turned an index-backed fills query into an
            # otherwise-unindexed scan of execution_events (review MEDIUM).
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_exec_events_symbol_type "
                "ON execution_events(symbol, event_type)"
            )
            self._backfill_fill_events_locked()
            self._backfill_trading_state_events_locked()
            self._ensure_current_session_locked()

    def _backfill_trading_state_events_locked(self) -> None:
        """Ensure each session's derived ``TradingState`` (§8 / wave 3d) is
        reflected in the event log + the ``trading_state`` column. A DB created
        before wave 3d has ``trading_state='active'`` (the migration default) even
        when ``kill_switch``/``buys_paused`` say otherwise; emit a
        ``TRADING_STATE_CHANGED`` so ``current_trading_state()`` matches the derived
        state on reopen (event-truth parity). Idempotent: a session already
        consistent is a no-op. Mirrors ``InMemoryStateStore``."""

        conn = self._connect()
        session_rows = conn.execute("SELECT * FROM sessions").fetchall()
        tsc_rows = conn.execute(
            "SELECT * FROM execution_events WHERE event_type = "
            "'trading_state_changed' ORDER BY sequence"
        ).fetchall()
        tsc_events = [self._execution_event(r) for r in tsc_rows]
        with self._tx() as cur:
            for row in session_rows:
                session = self._session(row)
                new_control = TradingState.of(
                    kill_switch=session.kill_switch, buys_paused=session.buys_paused
                )
                control_prior = control_trading_state(tsc_events, session.id)
                if control_prior is not new_control:
                    event = trading_state_change_event(
                        session.id, prior_control=control_prior,
                        kill_switch=session.kill_switch,
                        buys_paused=session.buys_paused, reason="backfill",
                    )
                    if event is not None:
                        self._insert_execution_event(cur, event)
                # Effective = control composed with any independent reconcile driver
                # (wave 4f); a pre-4f log has no reconcile events → == control.
                effective = compose_trading_state(
                    new_control, reconcile_trading_state(tsc_events, session.id)
                )
                # Heal the raw read-model column if it disagrees with the derived
                # state (a pre-wave-3d row defaults to 'active'). Compare the RAW
                # persisted value, not session.trading_state — the mapper reflects
                # the column, so this is the same value, but reading row[...] makes
                # the write's purpose (fix the stored column) unambiguous.
                if row["trading_state"] != effective.value:
                    cur.execute(
                        "UPDATE sessions SET trading_state=? WHERE id=?",
                        (effective.value, session.id),
                    )

    def _backfill_fill_events_locked(self) -> None:
        """Ensure every fill row has a matching `FILL` event (wave 3a-truth).
        Position now derives from the event log, so a DB opened on fill rows that
        predate the log would read a wrong (understated) position unless those
        fills are backfilled.

        Additive + identity-matched: for each fill in rowid order, append its
        event through the DEDUPED insert. A fill whose event already exists is a
        no-op (its deterministic ``dedupe_key`` is already present); a fill
        lacking one appends it. Idempotent, order-preserving for the realizable
        pre-event-log migration (0 events → all appended in fill order), and it
        NEVER deletes an event that has no fill row — reconciliation-inferred
        fills (Phase 4) and directly-appended FILL events legitimately have none.
        A fresh DB (0 fills) is a no-op. Mirrors ``InMemoryStateStore``.
        """

        conn = self._connect()
        fill_rows = conn.execute("SELECT * FROM fills ORDER BY rowid").fetchall()
        if not fill_rows:
            return
        with self._tx() as cur:
            for row in fill_rows:
                self._insert_execution_event(
                    cur, execution_event_for_fill(self._fill(row))
                )

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Lightweight, idempotent migrations for databases created before a
        schema addition. (CREATE TABLE IF NOT EXISTS doesn't add columns to an
        existing table.)"""

        fill_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(fills)").fetchall()
        }
        if "session_id" not in fill_cols:  # added in D-007
            conn.execute("ALTER TABLE fills ADD COLUMN session_id TEXT")

        order_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(orders)").fetchall()
        }
        if "broker_order_id" not in order_cols:  # added in Phase 4 (D-011)
            # The Alpaca order UUID, set on submission and used to poll/cancel.
            # Fresh DBs already get this column from SCHEMA; this guard only fires
            # on an orders table created before the column existed.
            conn.execute("ALTER TABLE orders ADD COLUMN broker_order_id TEXT")

        # Phase 7: `candidate_id` becomes NULLABLE and a `sell_intent_id` column is
        # added (a SELL order carries an intent, not a candidate — the XOR origin).
        # SQLite has no ALTER COLUMN to drop the old `candidate_id TEXT NOT NULL`
        # constraint, and CREATE TABLE IF NOT EXISTS is a no-op against an existing
        # table, so an orders table created before Phase 7 must be REBUILT (rows
        # preserved, sell_intent_id NULL for every pre-existing buy). Detected by
        # the absent column. Runs after the broker_order_id guard so that column is
        # guaranteed present to copy. No orders indexes exist to recreate.
        if "sell_intent_id" not in order_cols:
            conn.executescript(
                """
                ALTER TABLE orders RENAME TO orders_old;
                CREATE TABLE orders (
                    id                TEXT PRIMARY KEY,
                    candidate_id      TEXT,
                    sell_intent_id    TEXT,
                    symbol            TEXT NOT NULL,
                    side              TEXT NOT NULL,
                    order_type        TEXT NOT NULL,
                    quantity          INTEGER NOT NULL,
                    limit_price       REAL,
                    status            TEXT NOT NULL,
                    filled_quantity   INTEGER NOT NULL DEFAULT 0,
                    replaces_order_id TEXT,
                    broker_order_id   TEXT,
                    session_id        TEXT,
                    created_at        TEXT NOT NULL,
                    updated_at        TEXT NOT NULL,
                    submitted_at      TEXT,
                    filled_at         TEXT,
                    canceled_at       TEXT,
                    rejected_at       TEXT
                );
                INSERT INTO orders
                    (id, candidate_id, sell_intent_id, symbol, side, order_type,
                     quantity, limit_price, status, filled_quantity,
                     replaces_order_id, broker_order_id, session_id, created_at,
                     updated_at, submitted_at, filled_at, canceled_at, rejected_at)
                    SELECT id, candidate_id, NULL, symbol, side, order_type,
                           quantity, limit_price, status, filled_quantity,
                           replaces_order_id, broker_order_id, session_id,
                           created_at, updated_at, submitted_at, filled_at,
                           canceled_at, rejected_at
                    FROM orders_old;
                DROP TABLE orders_old;
                """
            )

        session_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()
        }
        if "trading_state" not in session_cols:  # added in Phase 3 wave 3d (§8)
            # Additive: pre-wave-3d sessions default 'active'; a session whose
            # booleans say otherwise is corrected + gets a TRADING_STATE_CHANGED
            # event by the init backfill (_backfill_trading_state_events_locked).
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN trading_state TEXT NOT NULL "
                "DEFAULT 'active'"
            )

        event_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(events)").fetchall()
        }
        if "correlation_id" not in event_cols:  # added in Wave 2 (D-020)
            # The lifecycle-correlation key. Additive; pre-D-020 rows stay NULL
            # (backfill not required). Fresh DBs already get it from SCHEMA.
            conn.execute("ALTER TABLE events ADD COLUMN correlation_id TEXT")

        # Item 5 / F1: dedup moved from a column-level UNIQUE on source_fill_id to
        # a composite (order_id, source_fill_id) index. SQLite can't ALTER away a
        # column constraint, so a DB created with the old `source_fill_id TEXT
        # UNIQUE` must be rebuilt without it (rows preserved). Detect via the
        # fills table's own CREATE SQL — the only UNIQUE it ever carried was that
        # column constraint. The composite index is (re)created in initialize().
        fills_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='fills'"
        ).fetchone()
        if fills_row is not None and "UNIQUE" in fills_row["sql"].upper():
            conn.executescript(
                """
                ALTER TABLE fills RENAME TO fills_old;
                CREATE TABLE fills (
                    id             TEXT PRIMARY KEY,
                    order_id       TEXT NOT NULL,
                    symbol         TEXT NOT NULL,
                    side           TEXT NOT NULL,
                    quantity       INTEGER NOT NULL,
                    price          REAL NOT NULL,
                    source_fill_id TEXT,
                    session_id     TEXT,
                    filled_at      TEXT NOT NULL,
                    created_at     TEXT NOT NULL
                );
                INSERT INTO fills
                    (id, order_id, symbol, side, quantity, price,
                     source_fill_id, session_id, filled_at, created_at)
                    SELECT id, order_id, symbol, side, quantity, price,
                           source_fill_id, session_id, filled_at, created_at
                    FROM fills_old;
                DROP TABLE fills_old;
                """
            )

    async def close(self) -> None:
        async with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # ------------------------------------------------------------------ #
    # Row -> model mappers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _watchlist(row: sqlite3.Row) -> WatchlistSymbol:
        return WatchlistSymbol(
            symbol=row["symbol"],
            armed=bool(row["armed"]),
            added_at=row["added_at"],
            updated_at=row["updated_at"],
            armed_at=row["armed_at"],
        )

    @staticmethod
    def _candidate(row: sqlite3.Row) -> Candidate:
        return Candidate(
            id=row["id"],
            symbol=row["symbol"],
            status=row["status"],
            strategy=row["strategy"],
            reason=row["reason"],
            risk_decision=row["risk_decision"],
            suggested_quantity=row["suggested_quantity"],
            suggested_limit_price=row["suggested_limit_price"],
            session_id=row["session_id"],
            order_id=row["order_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            approved_at=row["approved_at"],
            rejected_at=row["rejected_at"],
            expired_at=row["expired_at"],
            ordered_at=row["ordered_at"],
        )

    @staticmethod
    def _sell_intent(row: sqlite3.Row) -> SellIntent:
        return SellIntent(
            id=row["id"],
            symbol=row["symbol"],
            reason=row["reason"],
            status=row["status"],
            target_quantity=row["target_quantity"],
            floor_price=row["floor_price"],
            observed_price=row["observed_price"],
            session_id=row["session_id"],
            order_id=row["order_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            approved_at=row["approved_at"],
            rejected_at=row["rejected_at"],
            expired_at=row["expired_at"],
            ordered_at=row["ordered_at"],
        )

    @staticmethod
    def _order(row: sqlite3.Row) -> Order:
        return Order(
            id=row["id"],
            candidate_id=row["candidate_id"],
            sell_intent_id=row["sell_intent_id"],
            symbol=row["symbol"],
            side=row["side"],
            order_type=row["order_type"],
            quantity=row["quantity"],
            limit_price=row["limit_price"],
            status=row["status"],
            filled_quantity=row["filled_quantity"],
            replaces_order_id=row["replaces_order_id"],
            broker_order_id=row["broker_order_id"],
            session_id=row["session_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            submitted_at=row["submitted_at"],
            filled_at=row["filled_at"],
            canceled_at=row["canceled_at"],
            rejected_at=row["rejected_at"],
        )

    @staticmethod
    def _fill(row: sqlite3.Row) -> Fill:
        return Fill(
            id=row["id"],
            order_id=row["order_id"],
            symbol=row["symbol"],
            side=row["side"],
            quantity=row["quantity"],
            price=row["price"],
            source_fill_id=row["source_fill_id"],
            session_id=row["session_id"],
            filled_at=row["filled_at"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _snapshot(row: sqlite3.Row) -> PositionSnapshot:
        return PositionSnapshot(
            id=row["id"],
            session_id=row["session_id"],
            symbol=row["symbol"],
            quantity=row["quantity"],
            cost_basis=row["cost_basis"],
            average_price=row["average_price"],
            captured_at=row["captured_at"],
        )

    @staticmethod
    def _event(row: sqlite3.Row) -> Event:
        return Event(
            id=row["id"],
            event_type=row["event_type"],
            message=row["message"],
            symbol=row["symbol"],
            candidate_id=row["candidate_id"],
            order_id=row["order_id"],
            fill_id=row["fill_id"],
            payload=json.loads(row["payload"]) if row["payload"] else {},
            session_id=row["session_id"],
            correlation_id=row["correlation_id"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _execution_event(row: sqlite3.Row) -> ExecutionEvent:
        return ExecutionEvent(
            id=row["id"],
            sequence=row["sequence"],
            schema_version=row["schema_version"],
            event_type=row["event_type"],
            source=row["source"],
            authority=row["authority"],
            dedupe_key=row["dedupe_key"],
            ts_event=row["ts_event"],
            ts_init=row["ts_init"],
            symbol=row["symbol"],
            side=row["side"],
            quantity=row["quantity"],
            price=row["price"],
            order_id=row["order_id"],
            primary_id=row["primary_id"],
            spawn_id=row["spawn_id"],
            session_id=row["session_id"],
            correlation_id=row["correlation_id"],
            payload=json.loads(row["payload"]) if row["payload"] else {},
        )

    @staticmethod
    def _session(row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            id=row["id"],
            session_date=row["session_date"],
            mode=row["mode"],
            session_type=row["session_type"],
            status=row["status"],
            kill_switch=bool(row["kill_switch"]),
            buys_paused=bool(row["buys_paused"]),
            trading_state=row["trading_state"],
            opened_at=row["opened_at"],
            closed_at=row["closed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------ #
    # Insert helpers (operate on a cursor inside a transaction)
    # ------------------------------------------------------------------ #
    def _insert_event(
        self,
        cur: sqlite3.Cursor,
        event_type: str,
        *,
        message: str = "",
        symbol: Optional[str] = None,
        candidate_id: Optional[str] = None,
        order_id: Optional[str] = None,
        fill_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Event:
        # Owning candidate's id is the correlation key (D-020); default from
        # candidate_id so a whole lifecycle shares one filterable key with no
        # per-call-site threading. Same rule in InMemoryStateStore — parity.
        #
        # X-004: candidate_id is always None for a sell order (XOR origin), so
        # the buy-side default alone left every generic order/fill/recovery
        # event for a protective sell with correlation_id=None. Resolved HERE,
        # once, for every call site: when neither an explicit correlation_id
        # nor a candidate_id is available but order_id is, look up that
        # order's sell_intent_id via the SAME cursor/transaction (so it also
        # sees this transaction's own not-yet-committed order writes). See
        # InMemoryStateStore._append_event_unlocked for the full rationale.
        resolved_correlation_id = correlation_id or candidate_id
        if resolved_correlation_id is None and order_id is not None:
            owning_row = cur.execute(
                "SELECT sell_intent_id FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            if owning_row is not None and owning_row["sell_intent_id"] is not None:
                resolved_correlation_id = owning_row["sell_intent_id"]

        event = Event(
            event_type=str(event_type),
            message=message,
            symbol=symbol,
            candidate_id=candidate_id,
            order_id=order_id,
            fill_id=fill_id,
            payload=payload or {},
            session_id=session_id,
            correlation_id=resolved_correlation_id,
        )
        cur.execute(
            """INSERT INTO events
               (id, event_type, message, symbol, candidate_id, order_id,
                fill_id, payload, session_id, correlation_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event.id,
                event.event_type,
                event.message,
                event.symbol,
                event.candidate_id,
                event.order_id,
                event.fill_id,
                json.dumps(event.payload),
                event.session_id,
                event.correlation_id,
                _dt(event.created_at),
            ),
        )
        return event

    def _read_one(self, sql: str, params: tuple) -> Optional[sqlite3.Row]:
        return self._connect().execute(sql, params).fetchone()

    def _read_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self._connect().execute(sql, params).fetchall()

    # ------------------------------------------------------------------ #
    # Sessions — current-session bootstrap used by several methods
    # ------------------------------------------------------------------ #
    def _ensure_current_session_locked(self) -> SessionRecord:
        # One session per calendar date (D-009): return today's session if it
        # exists — active *or* closed — and only create one when today has none.
        # A closed today-session must NOT trigger creating a second; closing
        # ends the trading day until a genuinely new one starts.
        today = utcnow().date().isoformat()
        row = self._read_one(
            "SELECT * FROM sessions WHERE session_date = ? "
            "ORDER BY rowid DESC LIMIT 1",
            (today,),
        )
        if row is not None:
            return self._session(row)
        session = SessionRecord(session_date=today, mode=TradingMode.PAPER)
        with self._tx() as cur:
            self._insert_session(cur, session)
            self._insert_event(
                cur,
                "session_opened",
                message=f"session opened for {today}",
                session_id=session.id,
            )
        return session

    def _insert_session(self, cur: sqlite3.Cursor, s: SessionRecord) -> None:
        cur.execute(
            """INSERT INTO sessions
               (id, session_date, mode, session_type, status, kill_switch,
                buys_paused, trading_state, opened_at, closed_at, created_at,
                updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                s.id,
                s.session_date,
                s.mode.value,
                s.session_type.value if s.session_type else None,
                s.status.value,
                _bit(s.kill_switch),
                _bit(s.buys_paused),
                s.trading_state.value,
                _dt(s.opened_at),
                _dt(s.closed_at),
                _dt(s.created_at),
                _dt(s.updated_at),
            ),
        )

    # ------------------------------------------------------------------ #
    # Watchlist
    # ------------------------------------------------------------------ #
    async def add_watchlist_symbol(
        self, symbol: str, *, armed: bool = False
    ) -> WatchlistSymbol:
        require_bool(armed, field="armed")
        key = normalize_symbol(symbol)
        async with self._lock:
            existing = self._read_one(
                "SELECT * FROM watchlist WHERE symbol = ?", (key,)
            )
            if existing is not None:
                return self._watchlist(existing)
            session = self._ensure_current_session_locked()
            now = utcnow()
            entry = WatchlistSymbol(
                symbol=key,
                armed=armed,
                added_at=now,
                updated_at=now,
                armed_at=now if armed else None,
            )
            with self._tx() as cur:
                cur.execute(
                    """INSERT INTO watchlist (symbol, armed, added_at, updated_at,
                       armed_at) VALUES (?,?,?,?,?)""",
                    (
                        entry.symbol,
                        _bit(entry.armed),
                        _dt(entry.added_at),
                        _dt(entry.updated_at),
                        _dt(entry.armed_at),
                    ),
                )
                self._insert_event(
                    cur,
                    "watchlist_added",
                    message=f"{key} added",
                    symbol=key,
                    session_id=session.id,
                )
            return entry

    async def list_watchlist(self) -> list[WatchlistSymbol]:
        async with self._lock:
            rows = self._read_all("SELECT * FROM watchlist ORDER BY symbol")
            return [self._watchlist(r) for r in rows]

    async def get_watchlist_symbol(self, symbol: str) -> Optional[WatchlistSymbol]:
        key = normalize_symbol(symbol)
        async with self._lock:
            row = self._read_one("SELECT * FROM watchlist WHERE symbol = ?", (key,))
            return self._watchlist(row) if row else None

    async def set_watchlist_armed(self, symbol: str, armed: bool) -> WatchlistSymbol:
        require_bool(armed, field="armed")
        key = normalize_symbol(symbol)
        async with self._lock:
            row = self._read_one("SELECT * FROM watchlist WHERE symbol = ?", (key,))
            if row is None:
                raise UnknownEntityError(f"watchlist symbol {key} not found")
            session = self._ensure_current_session_locked()
            entry = self._watchlist(row)
            entry.armed = armed
            entry.armed_at = utcnow() if armed else None
            entry.updated_at = utcnow()
            with self._tx() as cur:
                cur.execute(
                    "UPDATE watchlist SET armed=?, armed_at=?, updated_at=? "
                    "WHERE symbol=?",
                    (_bit(armed), _dt(entry.armed_at), _dt(entry.updated_at), key),
                )
                self._insert_event(
                    cur,
                    "watchlist_armed" if armed else "watchlist_disarmed",
                    message=f"{key} {'armed' if armed else 'disarmed'}",
                    symbol=key,
                    session_id=session.id,
                )
            return entry

    async def remove_watchlist_symbol(self, symbol: str) -> bool:
        key = normalize_symbol(symbol)
        async with self._lock:
            row = self._read_one("SELECT * FROM watchlist WHERE symbol = ?", (key,))
            if row is None:
                return False
            session = self._ensure_current_session_locked()
            with self._tx() as cur:
                cur.execute("DELETE FROM watchlist WHERE symbol = ?", (key,))
                self._insert_event(
                    cur,
                    "watchlist_removed",
                    message=f"{key} removed",
                    symbol=key,
                    session_id=session.id,
                )
            return True

    # ------------------------------------------------------------------ #
    # Candidates
    # ------------------------------------------------------------------ #
    async def create_candidate(
        self,
        symbol: str,
        *,
        strategy: Optional[str] = None,
        reason: Optional[str] = None,
        risk_decision: Optional[str] = None,
        suggested_quantity: Optional[int] = None,
        suggested_limit_price: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> Candidate:
        key = normalize_symbol(symbol)
        async with self._lock:
            # Default to the active session so close/expiry and date-scoped
            # review see this candidate (Fix 7). An explicit session_id wins —
            # but it must actually resolve: an explicit id that names no session
            # is rejected (F-004), never allowed to create an orphan candidate
            # whose declared session doesn't exist (which then dispatches an
            # orphan order). The `None` -> current-session default is unchanged.
            if session_id is None:
                session = self._ensure_current_session_locked()
                session_id = session.id
            else:
                row = self._read_one(
                    "SELECT * FROM sessions WHERE id = ?", (session_id,)
                )
                session = self._session(row) if row is not None else None
                if session is None:
                    raise UnknownEntityError(
                        f"session {session_id} does not exist; cannot create candidate"
                    )
            # No new candidates in a closed session (D-009 / F2): the trading day
            # is over, and a post-close candidate would sit outside the captured
            # review snapshot. Guard at the store boundary so every future
            # producer (Phase 5) is covered, not only the dev route.
            if session is not None and session.status is SessionStatus.CLOSED:
                raise SessionClosedError(
                    f"session {session_id} is closed; cannot create candidate"
                )
            # Validate candidate numerics at the boundary (AIR-008) — identical
            # guard to InMemoryStateStore's, so a NaN/Inf/zero/negative/
            # fractional/bool/string quantity or price is rejected with a clean
            # domain error in BOTH stores (SQLite used to roundtrip a NaN price as
            # NULL while memory roundtripped nan — the parity break this closes).
            bad = candidate_numeric_reason(
                suggested_quantity=suggested_quantity,
                suggested_limit_price=suggested_limit_price,
            )
            if bad is not None:
                field, why = bad
                value = (
                    suggested_quantity
                    if field == "suggested_quantity"
                    else suggested_limit_price
                )
                raise InvalidOrderError(
                    f"candidate {key} has an invalid {field} ({why}: {value!r})"
                )
            candidate = Candidate(
                symbol=key,
                strategy=strategy,
                reason=reason,
                risk_decision=risk_decision,
                suggested_quantity=suggested_quantity,
                suggested_limit_price=suggested_limit_price,
                session_id=session_id,
            )
            with self._tx() as cur:
                self._insert_candidate(cur, candidate)
                self._insert_event(
                    cur,
                    "candidate_created",
                    message=f"candidate created for {key}",
                    symbol=key,
                    candidate_id=candidate.id,
                    session_id=session_id,
                )
            return candidate

    def _insert_candidate(self, cur: sqlite3.Cursor, c: Candidate) -> None:
        cur.execute(
            """INSERT INTO candidates
               (id, symbol, status, strategy, reason, risk_decision,
                suggested_quantity, suggested_limit_price, session_id, order_id,
                created_at, updated_at, approved_at, rejected_at, expired_at,
                ordered_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                c.id,
                c.symbol,
                c.status.value,
                c.strategy,
                c.reason,
                c.risk_decision,
                c.suggested_quantity,
                c.suggested_limit_price,
                c.session_id,
                c.order_id,
                _dt(c.created_at),
                _dt(c.updated_at),
                _dt(c.approved_at),
                _dt(c.rejected_at),
                _dt(c.expired_at),
                _dt(c.ordered_at),
            ),
        )

    async def list_candidates(
        self,
        *,
        session_id: Optional[str] = None,
        status: Optional[CandidateStatus] = None,
    ) -> list[Candidate]:
        clauses, params = [], []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if status is not None:
            # Require a real enum (AIR-009) — not CandidateStatus(status), which
            # coerced a bare string and silently matched what memory returned [].
            require_status_enum(status, CandidateStatus, field="status filter")
            clauses.append("status = ?")
            params.append(status.value)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        async with self._lock:
            rows = self._read_all(
                f"SELECT * FROM candidates{where} ORDER BY rowid", tuple(params)
            )
            return [self._candidate(r) for r in rows]

    async def get_candidate(self, candidate_id: str) -> Optional[Candidate]:
        async with self._lock:
            row = self._read_one(
                "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
            )
            return self._candidate(row) if row else None

    async def transition_candidate(
        self,
        candidate_id: str,
        new_status: CandidateStatus,
        *,
        order_id: Optional[str] = None,
    ) -> Candidate:
        # Require a real enum (AIR-009) — do NOT coerce a bare string via
        # CandidateStatus(new_status), which silently accepted what
        # InMemoryStateStore rejected.
        require_status_enum(new_status, CandidateStatus, field="new_status")
        async with self._lock:
            row = self._read_one(
                "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
            )
            if row is None:
                raise UnknownEntityError(f"candidate {candidate_id} not found")
            candidate = self._candidate(row)
            current = candidate.status
            if new_status is current:
                # Idempotent no-op: write no event and mutate nothing —
                # including order_id, which is set only on the real
                # APPROVED -> ORDERED transition. A stray order_id arg is
                # ignored, not applied (Fix 6 / D-008 philosophy).
                return candidate
            if new_status not in CANDIDATE_TRANSITIONS.get(current, set()):
                raise CandidateTransitionError(
                    f"illegal candidate transition {current.value} -> "
                    f"{new_status.value}"
                )
            candidate.status = new_status
            candidate.updated_at = utcnow()
            ts_field = CANDIDATE_TIMESTAMP.get(new_status)
            if ts_field:
                setattr(candidate, ts_field, utcnow())
            if new_status is CandidateStatus.ORDERED and order_id is not None:
                candidate.order_id = order_id
            with self._tx() as cur:
                cur.execute(
                    """UPDATE candidates SET status=?, updated_at=?, order_id=?,
                       approved_at=?, rejected_at=?, expired_at=?, ordered_at=?
                       WHERE id=?""",
                    (
                        candidate.status.value,
                        _dt(candidate.updated_at),
                        candidate.order_id,
                        _dt(candidate.approved_at),
                        _dt(candidate.rejected_at),
                        _dt(candidate.expired_at),
                        _dt(candidate.ordered_at),
                        candidate.id,
                    ),
                )
                self._insert_event(
                    cur,
                    "candidate_transition",
                    message=f"candidate {current.value} -> {new_status.value}",
                    symbol=candidate.symbol,
                    candidate_id=candidate.id,
                    order_id=order_id,
                    payload={"from": current.value, "to": new_status.value},
                    session_id=candidate.session_id,
                )
            return candidate

    # ------------------------------------------------------------------ #
    # Sell intents (Phase 7 — Sell-Side Protection)
    # ------------------------------------------------------------------ #
    def _insert_sell_intent(self, cur: sqlite3.Cursor, si: SellIntent) -> None:
        cur.execute(
            """INSERT INTO sell_intents
               (id, symbol, reason, status, target_quantity, floor_price,
                observed_price, session_id, order_id, created_at, updated_at,
                approved_at, rejected_at, expired_at, ordered_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                si.id,
                si.symbol,
                si.reason.value,
                si.status.value,
                si.target_quantity,
                si.floor_price,
                si.observed_price,
                si.session_id,
                si.order_id,
                _dt(si.created_at),
                _dt(si.updated_at),
                _dt(si.approved_at),
                _dt(si.rejected_at),
                _dt(si.expired_at),
                _dt(si.ordered_at),
            ),
        )

    def _update_sell_intent(self, cur: sqlite3.Cursor, si: SellIntent) -> None:
        cur.execute(
            """UPDATE sell_intents SET status=?, order_id=?, updated_at=?,
               approved_at=?, rejected_at=?, expired_at=?, ordered_at=?
               WHERE id=?""",
            (
                si.status.value,
                si.order_id,
                _dt(si.updated_at),
                _dt(si.approved_at),
                _dt(si.rejected_at),
                _dt(si.expired_at),
                _dt(si.ordered_at),
                si.id,
            ),
        )

    def _order_needs_review_locked(self, order_id: str) -> bool:
        """X-003: whether ``order_id`` currently carries an OPEN
        ``needs_review`` broker-submit recovery record (D-017). See
        ``InMemoryStateStore._order_needs_review_unlocked`` for the full
        rationale — mirrored here for parity."""

        row = self._read_one(
            "SELECT 1 FROM submit_recoveries WHERE local_order_id = ? "
            "AND cleanup_status = ? LIMIT 1",
            (order_id, RECOVERY_NEEDS_REVIEW),
        )
        return row is not None

    def _active_sell_intent_locked(self, symbol: str) -> Optional[SellIntent]:
        # Scan this symbol's intents newest-first; the linked order (if any)
        # decides whether an ORDERED intent is still in flight (shared predicate).
        rows = self._read_all(
            "SELECT * FROM sell_intents WHERE symbol = ? ORDER BY rowid DESC",
            (symbol,),
        )
        for row in rows:
            si = self._sell_intent(row)
            order = None
            if si.order_id is not None:
                order_row = self._read_one(
                    "SELECT * FROM orders WHERE id = ?", (si.order_id,)
                )
                order = self._order(order_row) if order_row is not None else None
            needs_review = (
                order is not None and self._order_needs_review_locked(order.id)
            )
            if sell_intent_is_active(si, order, order_needs_review=needs_review):
                return si
        return None

    def _insert_sell_intent_locked(
        self,
        cur: sqlite3.Cursor,
        *,
        symbol: str,
        reason: SellReason,
        target_quantity: int,
        floor_price: Optional[float] = None,
        observed_price: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> SellIntent:
        """Build + insert a fresh sell intent row + its ``sell_intent_created``
        event (assumes the caller already holds ``self._lock`` and is inside a
        ``with self._tx() as cur:`` block — either the public
        ``create_sell_intent`` or ``flatten_position``, X-001). No input
        validation: a caller that accepts external input
        (``create_sell_intent``) validates before calling this; a caller
        building the intent from trusted internal state (``flatten_position``,
        sizing from the live position) does not need to."""

        intent = SellIntent(
            symbol=symbol,
            reason=reason,
            target_quantity=target_quantity,
            floor_price=floor_price,
            observed_price=observed_price,
            session_id=session_id,
        )
        self._insert_sell_intent(cur, intent)
        self._insert_event(
            cur,
            "sell_intent_created",
            message=f"sell intent ({reason.value}) created for {symbol}",
            symbol=symbol,
            session_id=session_id,
            correlation_id=intent.id,
            payload={"reason": reason.value, "target_quantity": target_quantity},
        )
        return intent

    def _transition_sell_intent_locked(
        self,
        cur: sqlite3.Cursor,
        intent: SellIntent,
        new_status: SellIntentStatus,
        *,
        order_id: Optional[str] = None,
    ) -> bool:
        """Apply a sell-intent status transition in place + persist it (assumes
        the caller already holds ``self._lock`` and is inside a
        ``with self._tx() as cur:`` block). Returns ``False`` for a
        same-status no-op (nothing applied, no event written); ``True`` if it
        actually transitioned. Raises :class:`SellIntentTransitionError` for an
        illegal transition (nothing mutated, nothing persisted)."""

        current = intent.status
        if new_status is current:
            return False
        if new_status not in SELL_INTENT_TRANSITIONS.get(current, set()):
            raise SellIntentTransitionError(
                f"illegal sell intent transition {current.value} -> "
                f"{new_status.value}"
            )
        intent.status = new_status
        intent.updated_at = utcnow()
        ts_field = SELL_INTENT_TIMESTAMP.get(new_status)
        if ts_field:
            setattr(intent, ts_field, utcnow())
        if new_status is SellIntentStatus.ORDERED and order_id is not None:
            intent.order_id = order_id
        self._update_sell_intent(cur, intent)
        self._insert_event(
            cur,
            "sell_intent_transition",
            message=f"sell intent {current.value} -> {new_status.value}",
            symbol=intent.symbol,
            order_id=order_id,
            payload={"from": current.value, "to": new_status.value},
            session_id=intent.session_id,
            correlation_id=intent.id,
        )
        return True

    async def create_sell_intent(
        self,
        *,
        symbol: str,
        reason: SellReason,
        target_quantity: int,
        floor_price: Optional[float] = None,
        observed_price: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> SellIntent:
        if not isinstance(reason, SellReason):
            raise InvalidOrderError(
                f"sell intent reason must be a SellReason, not {reason!r}"
            )
        key = normalize_symbol(symbol)
        bad = whole_count_reason(target_quantity)
        if bad is not None or target_quantity <= 0:
            raise InvalidOrderError(
                f"sell intent for {key} needs a positive whole target_quantity "
                f"(got {target_quantity!r})"
            )
        async with self._lock:
            # Single-flight (atomic dedup): the active-check and the insert are one
            # lock hold, so a flatten POST and a protection tick cannot both create
            # an intent for the same symbol.
            active = self._active_sell_intent_locked(key)
            if active is not None:
                return active
            with self._tx() as cur:
                intent = self._insert_sell_intent_locked(
                    cur,
                    symbol=key,
                    reason=reason,
                    target_quantity=target_quantity,
                    floor_price=floor_price,
                    observed_price=observed_price,
                    session_id=session_id,
                )
            return intent

    async def transition_sell_intent(
        self,
        intent_id: str,
        new_status: SellIntentStatus,
        *,
        order_id: Optional[str] = None,
    ) -> SellIntent:
        require_status_enum(new_status, SellIntentStatus, field="new_status")
        async with self._lock:
            row = self._read_one(
                "SELECT * FROM sell_intents WHERE id = ?", (intent_id,)
            )
            if row is None:
                raise UnknownEntityError(f"sell intent {intent_id} not found")
            intent = self._sell_intent(row)
            with self._tx() as cur:
                self._transition_sell_intent_locked(
                    cur, intent, new_status, order_id=order_id
                )
            return intent

    async def get_sell_intent(self, intent_id: str) -> Optional[SellIntent]:
        async with self._lock:
            row = self._read_one(
                "SELECT * FROM sell_intents WHERE id = ?", (intent_id,)
            )
            return self._sell_intent(row) if row else None

    async def list_sell_intents(
        self,
        *,
        session_id: Optional[str] = None,
        status: Optional[SellIntentStatus] = None,
        symbol: Optional[str] = None,
    ) -> list[SellIntent]:
        clauses, params = [], []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if status is not None:
            require_status_enum(status, SellIntentStatus, field="status filter")
            clauses.append("status = ?")
            params.append(status.value)
        if symbol is not None:
            clauses.append("symbol = ?")
            params.append(normalize_symbol(symbol))
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        async with self._lock:
            rows = self._read_all(
                f"SELECT * FROM sell_intents{where} ORDER BY rowid", tuple(params)
            )
            return [self._sell_intent(r) for r in rows]

    async def active_sell_intent_for(self, symbol: str) -> Optional[SellIntent]:
        key = normalize_symbol(symbol)
        async with self._lock:
            return self._active_sell_intent_locked(key)

    def _dispatch_order_for_sell_intent_locked(
        self,
        intent: SellIntent,
        *,
        order_type: OrderType,
        limit_price: Optional[float],
    ) -> Order:
        """The plan+apply body of the APPROVED->ORDERED handoff (assumes the
        caller already holds ``self._lock`` — either the public
        ``create_order_for_sell_intent`` or ``flatten_position``, X-001, which
        needs this same dispatch inlined into its own single lock hold rather
        than calling the public method and re-acquiring the lock).

        Re-reads the LIVE position so a race that reduced it cannot oversell.
        On reject, atomically applies the X-002 self-heal (``expire_intent``/
        ``expire_event``) alongside any ``reject_event`` before raising — an
        intent is never left stranded ``approved``. On create, atomically
        inserts the order + transitions the intent to ``ordered`` + writes both
        events.
        """

        live_qty = self._position_locked(intent.symbol).quantity
        plan = plan_create_order_for_sell_intent(
            intent=intent,
            live_position_quantity=live_qty,
            order_type=order_type,
            limit_price=limit_price,
        )
        if plan.outcome == CREATE_ORDER_REJECT:
            if plan.reject_event is not None or plan.expire_intent is not None:
                with self._tx() as cur:
                    if plan.reject_event is not None:
                        self._insert_event(
                            cur,
                            plan.reject_event.event_type,
                            **plan.reject_event.as_kwargs(),
                        )
                    if plan.expire_intent is not None:
                        self._update_sell_intent(cur, plan.expire_intent)
                        self._insert_event(
                            cur,
                            plan.expire_event.event_type,
                            **plan.expire_event.as_kwargs(),
                        )
            raise plan.error
        order = plan.order
        now = utcnow()
        intent.status = SellIntentStatus.ORDERED
        intent.order_id = order.id
        intent.ordered_at = now
        intent.updated_at = now
        with self._tx() as cur:
            self._insert_order(cur, order)
            self._update_sell_intent(cur, intent)
            for event in plan.events:
                self._insert_event(cur, event.event_type, **event.as_kwargs())
        return order

    async def create_order_for_sell_intent(
        self,
        intent_id: str,
        *,
        order_type: OrderType,
        limit_price: Optional[float] = None,
    ) -> Order:
        async with self._lock:
            row = self._read_one(
                "SELECT * FROM sell_intents WHERE id = ?", (intent_id,)
            )
            if row is None:
                raise UnknownEntityError(f"sell intent {intent_id} not found")
            intent = self._sell_intent(row)
            # Idempotent: an intent already dispatched returns its existing order.
            if intent.status is SellIntentStatus.ORDERED:
                if intent.order_id is None:
                    raise InvalidOrderError(
                        f"sell intent {intent_id} is ORDERED but has no linked order"
                    )
                order_row = self._read_one(
                    "SELECT * FROM orders WHERE id = ?", (intent.order_id,)
                )
                if order_row is None:
                    raise InvalidOrderError(
                        f"sell intent {intent_id} links to missing order "
                        f"{intent.order_id}"
                    )
                return self._order(order_row)
            return self._dispatch_order_for_sell_intent_locked(
                intent, order_type=order_type, limit_price=limit_price
            )

    async def flatten_position(
        self, symbol: str, *, session_id: Optional[str] = None
    ) -> FlattenResult:
        key = normalize_symbol(symbol)
        async with self._lock:
            # Every read this decision depends on happens under this ONE lock
            # hold, continuously through to the writes below — a concurrent
            # protection tick's own create_sell_intent call cannot interleave
            # anywhere in between (X-001). Individual steps below each commit
            # their own small SQL transaction (matching close_session's and
            # _run_protection's existing multi-step-under-one-lock shape) —
            # what makes this safe against the CONCURRENCY race is the
            # continuous lock hold, not a single giant transaction; never a
            # double-sell (this is verified for real races). A hard CRASH
            # between the two commits below (insert+approve, then dispatch) is
            # a separate, narrower concern: it durably strands the fresh
            # MANUAL_FLATTEN intent APPROVED with no order. That is NOT
            # silently unrecoverable — plan_flatten_position (app/store/core.py)
            # treats a MANUAL_FLATTEN intent found here as "existing" only when
            # it is already ORDERED; a stranded pending/approved one instead
            # self-heals on the next flatten call, exactly like a stranded
            # PROTECTION_FLOOR intent (see docs/INVARIANTS.md INV-038 — an
            # adversarial re-review of this diff found the earlier version of
            # this comment's "never a silently-blocked symbol" claim was false
            # before that fix).
            position = self._position_locked(key)
            active = self._active_sell_intent_locked(key)
            active_order = None
            if active is not None and active.order_id is not None:
                order_row = self._read_one(
                    "SELECT * FROM orders WHERE id = ?", (active.order_id,)
                )
                active_order = self._order(order_row) if order_row is not None else None

            # ADR-003 / wave 3e: current session's §8 FSM + whether an
            # emergency-reduce override is active for this symbol, read under the
            # same continuous lock hold as the decision above.
            current_session = self._ensure_current_session_locked()
            trading_state = self._current_trading_state_locked(current_session.id)
            override_active = key in self._active_overrides_locked(current_session.id)

            plan = plan_flatten_position(
                position=position, active_intent=active, active_order=active_order,
                trading_state=trading_state, override_active=override_active,
            )

            if plan.outcome == FLATTEN_DENIED_HALTED:
                raise FlattenBlockedError(
                    f"manual flatten of {key} denied: trading halted "
                    "(issue an emergency reduce override to exit)"
                )
            # ADR-003 / wave 3e (review MEDIUM fix): the override authorized THIS
            # flatten call — spend it on ANY authorized outcome (create / existing /
            # flat). Consuming only on the create branch leaked the grant when the
            # flatten dedup'd, later letting an ordinary flatten slip past the
            # Halted-deny.
            if override_active:
                self._write_emergency_reduce_override_locked(
                    key, actor="engine", reason="flatten_authorized", resolved=True
                )

            if plan.outcome == _PLAN_FLATTEN_FLAT:
                return FlattenResult(FLATTEN_FLAT)
            if plan.outcome == _PLAN_FLATTEN_EXISTING:
                return FlattenResult(
                    FLATTEN_EXISTING,
                    intent=plan.existing_intent,
                    order=plan.existing_order,
                )

            assert plan.outcome == FLATTEN_SUPERSEDE_AND_CREATE
            if session_id is None:
                session_id = self._ensure_current_session_locked().id

            superseded = False
            if plan.supersede_order_cancel is not None:
                with self._tx() as cur:
                    cur.execute(
                        "UPDATE orders SET status=?, canceled_at=?, updated_at=? "
                        "WHERE id=?",
                        (
                            OrderStatus.CANCELED.value,
                            _dt(plan.supersede_order_cancel.canceled_at),
                            _dt(plan.supersede_order_cancel.updated_at),
                            plan.supersede_order_cancel.id,
                        ),
                    )
                    self._insert_event(
                        cur,
                        plan.supersede_cancel_event.event_type,
                        **plan.supersede_cancel_event.as_kwargs(),
                    )
                superseded = True
            if plan.supersede_intent_expire is not None:
                with self._tx() as cur:
                    self._update_sell_intent(cur, plan.supersede_intent_expire)
                    self._insert_event(
                        cur,
                        plan.supersede_expire_event.event_type,
                        **plan.supersede_expire_event.as_kwargs(),
                    )
                superseded = True

            with self._tx() as cur:
                intent = self._insert_sell_intent_locked(
                    cur,
                    symbol=key,
                    reason=SellReason.MANUAL_FLATTEN,
                    target_quantity=plan.target_quantity,
                    session_id=session_id,
                )
                self._transition_sell_intent_locked(
                    cur, intent, SellIntentStatus.APPROVED
                )

            order = self._dispatch_order_for_sell_intent_locked(
                intent, order_type=OrderType.MARKET, limit_price=None
            )
            return FlattenResult(
                FLATTEN_CREATED, intent=intent, order=order, superseded=superseded
            )

    # ------------------------------------------------------------------ #
    # Orders
    # ------------------------------------------------------------------ #
    async def create_order_for_test(
        self,
        candidate_id: str,
        symbol: str,
        side: OrderSide,
        quantity: int,
        *,
        order_type: OrderType = OrderType.LIMIT,
        limit_price: Optional[float] = None,
        replaces_order_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Order:
        """TEST-ONLY order-setup helper — NOT part of the public ``StateStore``
        contract (AIR-006). Production orders are created *only* via
        ``create_order_for_candidate`` (approved-only rule + CAPI/control gates).
        Mirrors ``InMemoryStateStore.create_order_for_test`` exactly."""

        key = normalize_symbol(symbol)
        async with self._lock:
            # Validate the order against its candidate (Fix 4). Existence +
            # symbol match only — the approved-only rule and the auto-ORDERED
            # transition belong to Phase 3's Approval Gate (D-010), not here.
            cand_row = self._read_one(
                "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
            )
            if cand_row is None:
                raise UnknownEntityError(f"candidate {candidate_id} not found")
            mismatch = order_candidate_match_reason(self._candidate(cand_row), key)
            if mismatch is not None:
                raise InvalidOrderError(
                    f"order symbol {key} does not match candidate "
                    f"{cand_row['symbol']} ({mismatch})"
                )
            order = Order(
                candidate_id=candidate_id,
                symbol=key,
                side=OrderSide(side),
                order_type=OrderType(order_type),
                quantity=quantity,
                limit_price=limit_price,
                replaces_order_id=replaces_order_id,
                # Inherit the candidate's session when not given (parity with
                # memory + production) so a test order can be claimed like a real one.
                session_id=(
                    session_id
                    if session_id is not None
                    else self._candidate(cand_row).session_id
                ),
            )
            with self._tx() as cur:
                self._insert_order(cur, order)
                self._insert_event(
                    cur,
                    "order_created",
                    message=f"order created for {key}",
                    symbol=key,
                    candidate_id=candidate_id,
                    order_id=order.id,
                    session_id=session_id,
                )
            return order

    def _current_exposure_locked(self) -> float:
        positions = [
            self._position_locked(r["symbol"])
            for r in self._read_all(
                "SELECT DISTINCT symbol FROM execution_events "
                "WHERE event_type = 'fill' ORDER BY symbol"
            )
        ]
        non_terminal_placeholders = ",".join("?" * len(NON_TERMINAL_ORDER_STATUSES))
        open_orders = [
            self._order(r)
            for r in self._read_all(
                f"SELECT * FROM orders WHERE status IN ({non_terminal_placeholders}) "
                "ORDER BY rowid",
                tuple(s.value for s in NON_TERMINAL_ORDER_STATUSES),
            )
        ]
        # Every fill, not just fills against open_orders — existing_exposure
        # derives each order's actual filled quantity from these directly
        # (see its docstring: Order.filled_quantity can lag a just-appended
        # fill by one transition_order call during reconciliation).
        fills = [self._fill(r) for r in self._read_all("SELECT * FROM fills ORDER BY rowid")]
        return existing_exposure(positions, open_orders, fills)

    async def current_exposure(self) -> float:
        async with self._lock:
            return self._current_exposure_locked()

    async def create_order_for_candidate(
        self,
        candidate_id: str,
        *,
        risk_limits: RiskLimits = RiskLimits(),
    ) -> Order:
        async with self._lock:
            cand_row = self._read_one(
                "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
            )
            if cand_row is None:
                raise UnknownEntityError(f"candidate {candidate_id} not found")
            candidate = self._candidate(cand_row)
            # Idempotent: a candidate already dispatched returns its existing
            # order and writes nothing — no second order, no extra audit rows.
            if candidate.status is CandidateStatus.ORDERED:
                if candidate.order_id is None:  # ordered but unlinked — corrupt
                    raise InvalidOrderError(
                        f"candidate {candidate_id} is ORDERED but has no linked order"
                    )
                order_row = self._read_one(
                    "SELECT * FROM orders WHERE id = ?", (candidate.order_id,)
                )
                if order_row is None:
                    raise InvalidOrderError(
                        f"candidate {candidate_id} links to missing order "
                        f"{candidate.order_id}"
                    )
                return self._order(order_row)
            # Shared validation cascade + order construction (app/store/core.py);
            # the candidate-missing and ORDERED-idempotent cases above stay here
            # since they need store-specific fetches. Exposure is computed
            # unconditionally (cheap at beta scale) — the planner only uses it
            # when a CAPI limit above is actually configured.
            sess_row = self._read_one(
                "SELECT * FROM sessions WHERE id = ?", (candidate.session_id,)
            )
            session = self._session(sess_row) if sess_row is not None else None
            fill_event_rows = self._read_all(
                "SELECT * FROM execution_events WHERE event_type = 'fill' "
                "ORDER BY sequence"
            )
            quarantined = candidate.symbol in quarantined_symbols(
                [self._execution_event(r) for r in fill_event_rows]
            )
            plan = plan_create_order_for_candidate(
                candidate=candidate,
                session=session,
                exposure_before_order=self._current_exposure_locked(),
                risk_limits=risk_limits,
                quarantined=quarantined,
            )
            if plan.outcome == CREATE_ORDER_REJECT:
                # The kill-switch/pause block and the Phase 6 CAPI risk-limit
                # block each write an audit row before raising; the not-approved
                # and invalid-qty/price rejections don't.
                if plan.reject_event is not None:
                    with self._tx() as cur:
                        self._insert_event(
                            cur,
                            plan.reject_event.event_type,
                            **plan.reject_event.as_kwargs(),
                        )
                raise plan.error

            # CREATE — one transaction covers the order insert, the candidate
            # ORDERED transition, and both audit events (the atomic "candidate
            # approval + order creation + audit event" group from docs/02).
            order = plan.order
            now = utcnow()
            candidate.status = CandidateStatus.ORDERED
            candidate.order_id = order.id
            candidate.updated_at = now
            candidate.ordered_at = now
            with self._tx() as cur:
                self._insert_order(cur, order)
                cur.execute(
                    """UPDATE candidates SET status=?, updated_at=?, order_id=?,
                       approved_at=?, rejected_at=?, expired_at=?, ordered_at=?
                       WHERE id=?""",
                    (
                        candidate.status.value,
                        _dt(candidate.updated_at),
                        candidate.order_id,
                        _dt(candidate.approved_at),
                        _dt(candidate.rejected_at),
                        _dt(candidate.expired_at),
                        _dt(candidate.ordered_at),
                        candidate.id,
                    ),
                )
                for event in plan.events:
                    self._insert_event(cur, event.event_type, **event.as_kwargs())
            return order

    async def claim_order_for_submission(self, order_id: str) -> SubmissionClaim:
        async with self._lock:
            row = self._read_one("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = self._order(row) if row is not None else None
            own_session = None
            if order is not None and order.session_id is not None:
                srow = self._read_one(
                    "SELECT * FROM sessions WHERE id = ?", (order.session_id,)
                )
                own_session = self._session(srow) if srow is not None else None
            current_session = self._ensure_current_session_locked()
            # Phase 7 §5.2: the owning intent's reason drives the side/reason-aware
            # gate. Fetched under the same lock so a concurrent transition can't
            # change it between the read and the CREATED -> SUBMITTING write.
            sell_reason = None
            if order is not None and order.sell_intent_id is not None:
                si_row = self._read_one(
                    "SELECT reason FROM sell_intents WHERE id = ?",
                    (order.sell_intent_id,),
                )
                sell_reason = SellReason(si_row["reason"]) if si_row is not None else None
            # ADR-001 (wave 3b): hold an autonomous BUY whose symbol is quarantined
            # by a broker overfill (derived from the event log under this lock).
            quarantined = False
            if order is not None:
                fill_event_rows = self._read_all(
                    "SELECT * FROM execution_events WHERE event_type = 'fill' "
                    "ORDER BY sequence"
                )
                quarantined = order.symbol in quarantined_symbols(
                    [self._execution_event(r) for r in fill_event_rows]
                )
            plan = plan_claim_order_for_submission(
                order=order,
                own_session=own_session,
                current_session=current_session,
                sell_reason=sell_reason,
                quarantined=quarantined,
            )
            if plan.outcome == CLAIM_CLAIMED:
                updated = plan.order
                with self._tx() as cur:
                    cur.execute(
                        "UPDATE orders SET status=?, updated_at=? WHERE id=?",
                        (updated.status.value, _dt(updated.updated_at), updated.id),
                    )
                    self._insert_event(
                        cur, plan.event.event_type, **plan.event.as_kwargs()
                    )
                return SubmissionClaim(CLAIM_CLAIMED, order=updated)
            if plan.outcome == CLAIM_BLOCKED:
                return SubmissionClaim(CLAIM_BLOCKED, reason=plan.reason)
            return SubmissionClaim(plan.outcome)  # CLAIM_SKIPPED

    # ------------------------------------------------------------------ #
    # Broker-submit recovery ledger (D-017)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _submit_recovery(row: sqlite3.Row) -> SubmitRecoveryRecord:
        return SubmitRecoveryRecord(
            id=row["id"],
            local_order_id=row["local_order_id"],
            broker_order_id=row["broker_order_id"],
            client_order_id=row["client_order_id"],
            symbol=row["symbol"],
            side=row["side"],
            quantity=row["quantity"],
            limit_price=row["limit_price"],
            failure_reason=row["failure_reason"],
            cleanup_status=row["cleanup_status"],
            retry_count=row["retry_count"],
            session_id=row["session_id"],
            created_at=row["created_at"],
            last_attempt_at=row["last_attempt_at"],
        )

    def _insert_submit_recovery(
        self, cur: sqlite3.Cursor, r: SubmitRecoveryRecord
    ) -> None:
        cur.execute(
            """INSERT INTO submit_recoveries
               (id, local_order_id, broker_order_id, client_order_id, symbol,
                side, quantity, limit_price, failure_reason, cleanup_status,
                retry_count, session_id, created_at, last_attempt_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r.id,
                r.local_order_id,
                r.broker_order_id,
                r.client_order_id,
                r.symbol,
                r.side.value,
                r.quantity,
                r.limit_price,
                r.failure_reason,
                r.cleanup_status,
                r.retry_count,
                r.session_id,
                _dt(r.created_at),
                _dt(r.last_attempt_at),
            ),
        )

    async def create_submit_recovery(
        self,
        *,
        local_order_id: str,
        broker_order_id: str,
        client_order_id: Optional[str] = None,
        symbol: str,
        side: OrderSide,
        quantity: int,
        limit_price: Optional[float] = None,
        failure_reason: str,
        session_id: Optional[str] = None,
        candidate_id: Optional[str] = None,
        cleanup_status: str = RECOVERY_UNRESOLVED,
        event_type: str = "submit_recovery_recorded",
        extra_payload: Optional[dict[str, Any]] = None,
    ) -> SubmitRecoveryRecord:
        require_recovery_status(cleanup_status)
        key = normalize_symbol(symbol)
        async with self._lock:
            record = SubmitRecoveryRecord(
                local_order_id=local_order_id,
                broker_order_id=broker_order_id,
                client_order_id=client_order_id,
                symbol=key,
                side=OrderSide(side),
                quantity=quantity,
                limit_price=limit_price,
                failure_reason=failure_reason,
                cleanup_status=cleanup_status,
                session_id=session_id,
            )
            payload: dict[str, Any] = {
                "broker_order_id": broker_order_id,
                "failure_reason": failure_reason,
                "cleanup_status": cleanup_status,
            }
            if extra_payload:
                payload.update(extra_payload)
            with self._tx() as cur:
                self._insert_submit_recovery(cur, record)
                self._insert_event(
                    cur,
                    event_type,
                    message=(
                        f"broker order {broker_order_id} for {key} needs "
                        f"recovery: {failure_reason}"
                    ),
                    symbol=key,
                    candidate_id=candidate_id,
                    order_id=local_order_id,
                    payload=payload,
                    session_id=session_id,
                )
            return record

    async def list_submit_recoveries(
        self, *, statuses: Optional[Iterable[str]] = None
    ) -> list[SubmitRecoveryRecord]:
        wanted = None if statuses is None else list(statuses)
        async with self._lock:
            if wanted is None:
                rows = self._read_all(
                    "SELECT * FROM submit_recoveries ORDER BY rowid"
                )
            elif not wanted:
                return []
            else:
                placeholders = ",".join("?" * len(wanted))
                rows = self._read_all(
                    f"SELECT * FROM submit_recoveries WHERE cleanup_status IN "
                    f"({placeholders}) ORDER BY rowid",
                    tuple(wanted),
                )
            return [self._submit_recovery(r) for r in rows]

    async def update_submit_recovery(
        self,
        recovery_id: str,
        *,
        cleanup_status: Optional[str] = None,
        bump_attempt: bool = False,
    ) -> SubmitRecoveryRecord:
        async with self._lock:
            row = self._read_one(
                "SELECT * FROM submit_recoveries WHERE id = ?", (recovery_id,)
            )
            if row is None:
                raise UnknownEntityError(
                    f"submit recovery {recovery_id} not found"
                )
            record = self._submit_recovery(row)
            terminal_event = recovery_status_event(
                record.cleanup_status, cleanup_status
            )
            updated = record.model_copy(deep=True)
            if bump_attempt:
                updated.retry_count += 1
                updated.last_attempt_at = utcnow()
            if cleanup_status is not None:
                updated.cleanup_status = cleanup_status
            with self._tx() as cur:
                cur.execute(
                    "UPDATE submit_recoveries SET cleanup_status=?, retry_count=?, "
                    "last_attempt_at=? WHERE id=?",
                    (
                        updated.cleanup_status,
                        updated.retry_count,
                        _dt(updated.last_attempt_at),
                        updated.id,
                    ),
                )
                if terminal_event is not None:
                    # SubmitRecoveryRecord carries no candidate_id (D-020 stays
                    # to one nullable Event field); resolve it from the local
                    # order for correlation — orders are never deleted, so this
                    # reliably resolves for the lifetime of the record.
                    order_row = cur.execute(
                        "SELECT candidate_id FROM orders WHERE id = ?",
                        (updated.local_order_id,),
                    ).fetchone()
                    self._insert_event(
                        cur,
                        terminal_event,
                        message=(
                            f"broker order {updated.broker_order_id} recovery "
                            f"{cleanup_status}"
                        ),
                        symbol=updated.symbol,
                        candidate_id=(
                            order_row["candidate_id"] if order_row is not None else None
                        ),
                        order_id=updated.local_order_id,
                        payload={
                            "broker_order_id": updated.broker_order_id,
                            "cleanup_status": cleanup_status,
                            "retry_count": updated.retry_count,
                        },
                        session_id=updated.session_id,
                    )
            return updated

    async def revert_candidate_approval(self, candidate_id: str) -> Candidate:
        async with self._lock:
            row = self._read_one(
                "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
            )
            if row is None:
                raise UnknownEntityError(f"candidate {candidate_id} not found")
            candidate = self._candidate(row)
            # No-op unless genuinely stranded APPROVED-with-no-order.
            if (
                candidate.status is not CandidateStatus.APPROVED
                or candidate.order_id is not None
            ):
                return candidate
            now = utcnow()
            with self._tx() as cur:
                cur.execute(
                    "UPDATE candidates SET status=?, approved_at=?, updated_at=? "
                    "WHERE id=?",
                    (CandidateStatus.PENDING.value, None, _dt(now), candidate_id),
                )
                self._insert_event(
                    cur,
                    "candidate_transition",
                    message="candidate approved -> pending (dispatch blocked)",
                    symbol=candidate.symbol,
                    candidate_id=candidate.id,
                    payload={
                        "from": "approved",
                        "to": "pending",
                        "reason": "dispatch_blocked",
                    },
                    session_id=candidate.session_id,
                )
            candidate.status = CandidateStatus.PENDING
            candidate.approved_at = None
            candidate.updated_at = now
            return candidate

    def _insert_order(self, cur: sqlite3.Cursor, o: Order) -> None:
        cur.execute(
            """INSERT INTO orders
               (id, candidate_id, sell_intent_id, symbol, side, order_type,
                quantity, limit_price, status, filled_quantity, replaces_order_id,
                broker_order_id, session_id, created_at, updated_at, submitted_at,
                filled_at, canceled_at, rejected_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                o.id,
                o.candidate_id,
                o.sell_intent_id,
                o.symbol,
                o.side.value,
                o.order_type.value,
                o.quantity,
                o.limit_price,
                o.status.value,
                o.filled_quantity,
                o.replaces_order_id,
                o.broker_order_id,
                o.session_id,
                _dt(o.created_at),
                _dt(o.updated_at),
                _dt(o.submitted_at),
                _dt(o.filled_at),
                _dt(o.canceled_at),
                _dt(o.rejected_at),
            ),
        )

    async def list_orders(
        self,
        *,
        session_id: Optional[str] = None,
        candidate_id: Optional[str] = None,
    ) -> list[Order]:
        clauses, params = [], []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if candidate_id is not None:
            clauses.append("candidate_id = ?")
            params.append(candidate_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        async with self._lock:
            rows = self._read_all(
                f"SELECT * FROM orders{where} ORDER BY rowid", tuple(params)
            )
            return [self._order(r) for r in rows]

    async def get_order(self, order_id: str) -> Optional[Order]:
        async with self._lock:
            row = self._read_one("SELECT * FROM orders WHERE id = ?", (order_id,))
            return self._order(row) if row else None

    async def transition_order(
        self,
        order_id: str,
        new_status: OrderStatus,
        *,
        filled_quantity: Optional[int] = None,
        broker_order_id: Optional[str] = None,
    ) -> Order:
        # No OrderStatus(new_status) coercion (AIR-009): plan_transition_order
        # validates the enum type itself, identically to InMemoryStateStore, so a
        # bare string is rejected here rather than silently coerced.
        async with self._lock:
            row = self._read_one("SELECT * FROM orders WHERE id = ?", (order_id,))
            if row is None:
                raise UnknownEntityError(f"order {order_id} not found")
            order = self._order(row)
            plan = plan_transition_order(
                order=order,
                new_status=new_status,
                filled_quantity=filled_quantity,
                broker_order_id=broker_order_id,
            )
            if plan.outcome == ORDER_TRANSITION_REJECT:
                raise plan.error
            if plan.outcome == ORDER_TRANSITION_NOOP:
                return order
            # APPLY — persist the fully-updated order + its one audit row
            # (order_transition or order_fill_progress) in one transaction.
            updated = plan.order
            with self._tx() as cur:
                cur.execute(
                    """UPDATE orders SET status=?, filled_quantity=?,
                       broker_order_id=?, updated_at=?, submitted_at=?, filled_at=?,
                       canceled_at=?, rejected_at=? WHERE id=?""",
                    (
                        updated.status.value,
                        updated.filled_quantity,
                        updated.broker_order_id,
                        _dt(updated.updated_at),
                        _dt(updated.submitted_at),
                        _dt(updated.filled_at),
                        _dt(updated.canceled_at),
                        _dt(updated.rejected_at),
                        updated.id,
                    ),
                )
                self._insert_event(cur, plan.event.event_type, **plan.event.as_kwargs())
            return updated

    # ------------------------------------------------------------------ #
    # Timeout-quarantine (ADR-002 / wave 3c) — evented order transitions
    # ------------------------------------------------------------------ #
    def _apply_order_evented_plan_locked(
        self, plan: OrderEventedTransitionPlan, order: Order
    ) -> Order:
        """Apply an :class:`OrderEventedTransitionPlan`: co-write the order-row
        flip + audit event + ExecutionEvent (durable truth) in ONE transaction."""

        if plan.outcome == ORDER_TRANSITION_REJECT:
            raise plan.error
        if plan.outcome == ORDER_TRANSITION_NOOP:
            return order
        updated = plan.order
        with self._tx() as cur:
            cur.execute(
                """UPDATE orders SET status=?, filled_quantity=?,
                   broker_order_id=?, updated_at=?, submitted_at=?, filled_at=?,
                   canceled_at=?, rejected_at=? WHERE id=?""",
                (
                    updated.status.value,
                    updated.filled_quantity,
                    updated.broker_order_id,
                    _dt(updated.updated_at),
                    _dt(updated.submitted_at),
                    _dt(updated.filled_at),
                    _dt(updated.canceled_at),
                    _dt(updated.rejected_at),
                    updated.id,
                ),
            )
            self._insert_event(
                cur, plan.audit_event.event_type, **plan.audit_event.as_kwargs()
            )
            self._insert_execution_event(cur, plan.execution_event)
        return updated

    async def quarantine_timed_out_order(
        self, order_id: str, *, reason: Optional[str] = None
    ) -> Order:
        async with self._lock:
            row = self._read_one("SELECT * FROM orders WHERE id = ?", (order_id,))
            if row is None:
                raise UnknownEntityError(f"order {order_id} not found")
            order = self._order(row)
            plan = plan_quarantine_timed_out_order(order, reason=reason)
            return self._apply_order_evented_plan_locked(plan, order)

    async def resolve_timeout_quarantine(
        self,
        order_id: str,
        new_status: OrderStatus,
        *,
        broker_order_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Order:
        async with self._lock:
            row = self._read_one("SELECT * FROM orders WHERE id = ?", (order_id,))
            if row is None:
                raise UnknownEntityError(f"order {order_id} not found")
            order = self._order(row)
            plan = plan_resolve_timeout_quarantine(
                order, new_status, broker_order_id=broker_order_id, reason=reason
            )
            return self._apply_order_evented_plan_locked(plan, order)

    async def reconcile_resolve_order(
        self,
        order_id: str,
        new_status: OrderStatus,
        *,
        reason: Optional[str] = None,
    ) -> Order:
        async with self._lock:
            row = self._read_one("SELECT * FROM orders WHERE id = ?", (order_id,))
            if row is None:
                raise UnknownEntityError(f"order {order_id} not found")
            order = self._order(row)
            plan = plan_reconcile_resolve_order(order, new_status, reason=reason)
            return self._apply_order_evented_plan_locked(plan, order)

    async def list_timeout_quarantined_orders(self) -> list[Order]:
        async with self._lock:
            rows = self._read_all(
                "SELECT * FROM execution_events WHERE event_type IN "
                "('timeout_quarantine','submitted','rejected','canceled','filled') "
                "ORDER BY sequence"
            )
            ids = timeout_quarantined_order_ids(
                [self._execution_event(r) for r in rows]
            )
            if not ids:
                return []
            order_rows = self._read_all("SELECT * FROM orders WHERE id IN (%s)"
                % ",".join("?" * len(ids)), tuple(sorted(ids)))
            return sorted(
                (self._order(r) for r in order_rows), key=lambda o: o.id
            )

    # ------------------------------------------------------------------ #
    # Fills (append-only)
    # ------------------------------------------------------------------ #
    async def append_fill(
        self,
        order_id: str,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: float,
        *,
        source_fill_id: Optional[str] = None,
        filled_at: Optional[Any] = None,
        session_id: Optional[str] = None,
        source: EventSource = EventSource.BROKER_REST,
        authority: EventAuthority = EventAuthority.BROKER_AUTHORITATIVE,
    ) -> FillAppendResult:
        key = normalize_symbol(symbol)
        side = OrderSide(side)
        async with self._lock:
            # Fetch the state the shared planner decides over (SQL form), then
            # apply its plan. Decision logic lives once in app/store/core.py; only
            # the fetch + the write primitive are store-specific here.
            order_row = self._read_one(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            )
            order = self._order(order_row) if order_row is not None else None
            prior_row = self._read_one(
                "SELECT COALESCE(SUM(quantity), 0) AS total FROM fills "
                "WHERE order_id = ?",
                (order_id,),
            )
            prior_filled = prior_row["total"] if prior_row else 0
            is_duplicate = False
            if source_fill_id is not None:
                is_duplicate = (
                    self._read_one(
                        "SELECT 1 FROM fills WHERE order_id = ? AND source_fill_id = ?",
                        (order_id, source_fill_id),
                    )
                    is not None
                )
            current = self._position_locked(key)
            plan = plan_append_fill(
                order_id=order_id,
                order=order,
                prior_filled=prior_filled,
                current_quantity=current.quantity,
                is_duplicate=is_duplicate,
                symbol=key,
                side=side,
                quantity=quantity,
                price=price,
                source_fill_id=source_fill_id,
                filled_at=filled_at,
                session_id=session_id,
                source=source,
                authority=authority,
            )

            if plan.outcome == FILL_REJECT:
                with self._tx() as cur:
                    self._insert_event(
                        cur, plan.event.event_type, **plan.event.as_kwargs()
                    )
                raise plan.error

            if plan.outcome == FILL_DUPLICATE:
                with self._tx() as cur:
                    event = self._insert_event(
                        cur, plan.event.event_type, **plan.event.as_kwargs()
                    )
                return FillAppendResult(status="duplicate", fill=None, event=event)

            # FILL_APPEND — one transaction: INSERT the fill row + its audit event
            # + the shadow ExecutionEvent (wave 3a), so the fill and its mirror in
            # the event log commit or roll back together (shadow parity).
            fill = plan.fill
            with self._tx() as cur:
                cur.execute(
                    """INSERT INTO fills
                       (id, order_id, symbol, side, quantity, price,
                        source_fill_id, session_id, filled_at, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        fill.id,
                        fill.order_id,
                        fill.symbol,
                        fill.side.value,
                        fill.quantity,
                        fill.price,
                        fill.source_fill_id,
                        fill.session_id,
                        _dt(fill.filled_at),
                        _dt(fill.created_at),
                    ),
                )
                event = self._insert_event(
                    cur, plan.event.event_type, **plan.event.as_kwargs()
                )
                if plan.execution_event is not None:
                    self._insert_execution_event(cur, plan.execution_event)
            return FillAppendResult(status="appended", fill=fill, event=event)

    async def list_fills(
        self,
        *,
        symbol: Optional[str] = None,
        order_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> list[Fill]:
        clauses, params = [], []
        if symbol is not None:
            clauses.append("symbol = ?")
            params.append(normalize_symbol(symbol))
        if order_id is not None:
            clauses.append("order_id = ?")
            params.append(order_id)
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        async with self._lock:
            rows = self._read_all(
                f"SELECT * FROM fills{where} ORDER BY rowid", tuple(params)
            )
            return [self._fill(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Positions (derived)
    # ------------------------------------------------------------------ #
    def _position_locked(self, symbol: str) -> Position:
        # Event-truth (wave 3a-truth): fold the symbol's FILL events from the
        # append-only execution-event log, not the fill table (now a
        # compatibility read-model). Backfill (see initialize) guarantees a FILL
        # event for every fill row, so this reproduces the legacy fold exactly.
        rows = self._read_all(
            "SELECT * FROM execution_events "
            "WHERE symbol = ? AND event_type = 'fill' ORDER BY sequence",
            (symbol,),
        )
        return project_symbol_position(
            [self._execution_event(r) for r in rows], symbol
        )

    async def get_position(self, symbol: str) -> Position:
        key = normalize_symbol(symbol)
        async with self._lock:
            return self._position_locked(key)

    async def list_positions(self) -> list[Position]:
        async with self._lock:
            rows = self._read_all(
                "SELECT DISTINCT symbol FROM execution_events "
                "WHERE event_type = 'fill' ORDER BY symbol"
            )
            return [self._position_locked(r["symbol"]) for r in rows]

    async def list_quarantined_symbols(self) -> set[str]:
        async with self._lock:
            rows = self._read_all(
                "SELECT * FROM execution_events WHERE event_type = 'fill' "
                "ORDER BY sequence"
            )
            return quarantined_symbols([self._execution_event(r) for r in rows])

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #
    async def append_event(
        self,
        event_type: str,
        *,
        message: str = "",
        symbol: Optional[str] = None,
        candidate_id: Optional[str] = None,
        order_id: Optional[str] = None,
        fill_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Event:
        async with self._lock:
            with self._tx() as cur:
                return self._insert_event(
                    cur,
                    event_type,
                    message=message,
                    symbol=symbol,
                    candidate_id=candidate_id,
                    order_id=order_id,
                    fill_id=fill_id,
                    payload=payload,
                    session_id=session_id,
                    correlation_id=correlation_id,
                )

    async def list_events(
        self,
        *,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        correlation_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Event]:
        clauses, params = [], []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if correlation_id is not None:
            clauses.append("correlation_id = ?")
            params.append(correlation_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        async with self._lock:
            rows = self._read_all(
                f"SELECT * FROM events{where} ORDER BY rowid", tuple(params)
            )
            events = [self._event(r) for r in rows]
            if limit is not None:
                events = events[-limit:]
            return events

    # ------------------------------------------------------------------ #
    # Execution-event log (Spine v2 — Phase 2)
    # ------------------------------------------------------------------ #
    def _insert_execution_event(
        self, cur: sqlite3.Cursor, event: ExecutionEvent
    ) -> ExecutionEvent:
        """Assign a sequence + INSERT (dedupe-aware) on an open cursor inside a
        ``_tx``. Shared by the public :meth:`append_execution_event` and the
        shadow write inside :meth:`append_fill` (which already holds a ``_tx``),
        so the fill row and its shadow event commit in the same transaction
        (wave 3a)."""

        dedupe_key = event.dedupe_key
        if dedupe_key is not None:
            existing = cur.execute(
                "SELECT * FROM execution_events WHERE dedupe_key = ?",
                (dedupe_key,),
            ).fetchone()
            if existing is not None:
                # INV-5: idempotent — no row written, no sequence consumed.
                return self._execution_event(existing)
        max_row = cur.execute(
            "SELECT MAX(sequence) AS m FROM execution_events"
        ).fetchone()
        next_sequence = (max_row["m"] or 0) + 1
        stored = event.model_copy(update={"sequence": next_sequence})
        cur.execute(
            """INSERT INTO execution_events
               (id, sequence, schema_version, event_type, source,
                authority, dedupe_key, ts_event, ts_init, symbol, side,
                quantity, price, order_id, primary_id, spawn_id,
                session_id, correlation_id, payload)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                stored.id,
                stored.sequence,
                stored.schema_version,
                stored.event_type.value,
                stored.source.value,
                stored.authority.value,
                stored.dedupe_key,
                _dt(stored.ts_event),
                _dt(stored.ts_init),
                stored.symbol,
                stored.side.value if stored.side is not None else None,
                stored.quantity,
                stored.price,
                stored.order_id,
                stored.primary_id,
                stored.spawn_id,
                stored.session_id,
                stored.correlation_id,
                json.dumps(stored.payload),
            ),
        )
        return stored

    async def append_execution_event(self, event: ExecutionEvent) -> ExecutionEvent:
        async with self._lock:
            with self._tx() as cur:
                return self._insert_execution_event(cur, event)

    async def get_execution_events(
        self, *, after_sequence: int = 0, limit: Optional[int] = None
    ) -> list[ExecutionEvent]:
        # Reject a negative limit identically to the in-memory store: SQL
        # LIMIT -1 means unlimited, which would silently diverge from a Python
        # slice (dual-store parity, see base.py).
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative")
        sql = (
            "SELECT * FROM execution_events WHERE sequence > ? ORDER BY sequence"
        )
        params: tuple = (after_sequence,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (after_sequence, limit)
        async with self._lock:
            rows = self._read_all(sql, params)
            return [self._execution_event(r) for r in rows]

    async def get_max_execution_sequence(self) -> int:
        async with self._lock:
            row = self._read_one(
                "SELECT MAX(sequence) AS m FROM execution_events", ()
            )
            return (row["m"] if row is not None else 0) or 0

    # ------------------------------------------------------------------ #
    # Sessions / control flags
    # ------------------------------------------------------------------ #
    async def get_current_session(self) -> SessionRecord:
        async with self._lock:
            return self._ensure_current_session_locked()

    async def get_session_by_date(self, day: date) -> Optional[SessionRecord]:
        target = day.isoformat()
        async with self._lock:
            row = self._read_one(
                "SELECT * FROM sessions WHERE session_date = ? "
                "ORDER BY rowid DESC LIMIT 1",
                (target,),
            )
            return self._session(row) if row else None

    async def get_session_by_id(self, session_id: str) -> Optional[SessionRecord]:
        async with self._lock:
            row = self._read_one(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            )
            return self._session(row) if row else None

    async def list_sessions(self) -> list[SessionRecord]:
        async with self._lock:
            rows = self._read_all("SELECT * FROM sessions ORDER BY rowid")
            return [self._session(r) for r in rows]

    def _apply_control_change_locked(
        self,
        cur: sqlite3.Cursor,
        session: SessionRecord,
        *,
        kill_switch: bool,
        buys_paused: bool,
        audit_event_type: str,
        audit_message: str,
        audit_payload: dict[str, Any],
        reason: str,
    ) -> None:
        """Co-write the derived ``trading_state`` + booleans + legacy audit event +
        (on a real transition) the ``TRADING_STATE_CHANGED`` ExecutionEvent, in one
        ``_tx`` (§8 / wave 3d). Mirrors ``InMemoryStateStore``."""

        tsc_events = self._trading_state_events_locked()
        prior_control = control_trading_state(tsc_events, session.id)
        exec_event = trading_state_change_event(
            session.id, prior_control=prior_control, kill_switch=kill_switch,
            buys_paused=buys_paused, reason=reason,
        )
        session.kill_switch = kill_switch
        session.buys_paused = buys_paused
        # Effective composes the new control state with the INDEPENDENT reconcile
        # driver (wave 4f / R2) — kill dominates a reconcile Reducing; a kill release
        # can't lift a Reducing pending reconciliation still requires.
        session.trading_state = compose_trading_state(
            TradingState.of(kill_switch=kill_switch, buys_paused=buys_paused),
            reconcile_trading_state(tsc_events, session.id),
        )
        session.updated_at = utcnow()
        cur.execute(
            "UPDATE sessions SET kill_switch=?, buys_paused=?, trading_state=?, "
            "updated_at=? WHERE id=?",
            (
                _bit(session.kill_switch),
                _bit(session.buys_paused),
                session.trading_state.value,
                _dt(session.updated_at),
                session.id,
            ),
        )
        self._insert_event(
            cur, audit_event_type, message=audit_message, session_id=session.id,
            payload=audit_payload,
        )
        if exec_event is not None:
            self._insert_execution_event(cur, exec_event)

    def _trading_state_events_locked(self) -> list[ExecutionEvent]:
        """All ``TRADING_STATE_CHANGED`` events in sequence order (for folding the
        control + reconcile drivers, wave 4f)."""

        rows = self._read_all(
            "SELECT * FROM execution_events WHERE event_type = "
            "'trading_state_changed' ORDER BY sequence"
        )
        return [self._execution_event(r) for r in rows]

    def _apply_reconcile_state_locked(
        self, cur: sqlite3.Cursor, session: SessionRecord, *,
        to: TradingState, reason: str,
    ) -> None:
        """Co-write a RECONCILE-driver TradingState change (wave 4f / R2): the
        composed effective ``trading_state`` column + a ``driver="reconcile"``
        ``TRADING_STATE_CHANGED`` ExecutionEvent — WITHOUT touching the booleans."""

        tsc_events = self._trading_state_events_locked()
        prior_reconcile = reconcile_trading_state(tsc_events, session.id)
        exec_event = reconcile_trading_state_event(
            session.id, prior_reconcile=prior_reconcile, to=to, reason=reason,
        )
        if exec_event is None:
            # Reconcile driver already at `to` — a no-op re-assert. The loop drives
            # this EVERY steady-parity tick, so appending an audit row + rewriting the
            # column here would grow the log unbounded (and quadratically slow the
            # per-tick log folds). Skip it: the composed effective column is already
            # correct (neither driver changed), matching the repo's "a transition that
            # doesn't change status writes no new audit row" discipline (docs/02).
            return
        session.trading_state = compose_trading_state(
            control_trading_state(tsc_events, session.id), to
        )
        session.updated_at = utcnow()
        cur.execute(
            "UPDATE sessions SET trading_state=?, updated_at=? WHERE id=?",
            (session.trading_state.value, _dt(session.updated_at), session.id),
        )
        self._insert_event(
            cur, "trading_state_reconcile",
            message=f"reconcile-driven trading state -> {to.value} ({reason})",
            session_id=session.id, payload={"to": to.value, "reason": reason},
        )
        self._insert_execution_event(cur, exec_event)

    async def set_kill_switch(self, engaged: bool) -> SessionRecord:
        require_bool(engaged, field="engaged")
        async with self._lock:
            session = self._ensure_current_session_locked()
            with self._tx() as cur:
                self._apply_control_change_locked(
                    cur, session, kill_switch=engaged, buys_paused=session.buys_paused,
                    audit_event_type="kill_switch_engaged" if engaged else "kill_switch_released",
                    audit_message=f"kill switch {'engaged' if engaged else 'released'}",
                    audit_payload={"kill_switch": engaged}, reason="kill_switch",
                )
            return session

    async def set_buys_paused(self, paused: bool) -> SessionRecord:
        require_bool(paused, field="paused")
        async with self._lock:
            session = self._ensure_current_session_locked()
            with self._tx() as cur:
                self._apply_control_change_locked(
                    cur, session, kill_switch=session.kill_switch, buys_paused=paused,
                    audit_event_type="buys_paused" if paused else "buys_resumed",
                    audit_message=f"buys {'paused' if paused else 'resumed'}",
                    audit_payload={"buys_paused": paused}, reason="buys_paused",
                )
            return session

    async def set_reconcile_trading_state(
        self, to: TradingState, *, reason: str
    ) -> SessionRecord:
        if to is TradingState.HALTED:
            raise ValueError("the reconcile driver never drives Halted (R3)")
        async with self._lock:
            session = self._ensure_current_session_locked()
            with self._tx() as cur:
                self._apply_reconcile_state_locked(
                    cur, session, to=to, reason=reason
                )
            return session

    def _current_trading_state_locked(self, session_id: str) -> TradingState:
        rows = self._read_all(
            "SELECT * FROM execution_events WHERE event_type = "
            "'trading_state_changed' ORDER BY sequence"
        )
        return current_trading_state(
            [self._execution_event(r) for r in rows], session_id
        )

    def _active_overrides_locked(self, session_id: str) -> set[str]:
        rows = self._read_all(
            "SELECT * FROM execution_events WHERE event_type IN "
            "('emergency_reduce_override','emergency_reduce_override_resolved') "
            "ORDER BY sequence"
        )
        return active_emergency_reduce_overrides(
            [self._execution_event(r) for r in rows], session_id
        )

    async def current_trading_state(self) -> TradingState:
        async with self._lock:
            session = self._ensure_current_session_locked()
            return self._current_trading_state_locked(session.id)

    def _write_emergency_reduce_override_locked(
        self, symbol: str, *, actor: str, reason: str, resolved: bool
    ) -> None:
        session = self._ensure_current_session_locked()
        event = emergency_reduce_override_event(
            session.id, symbol, actor=actor, reason=reason, resolved=resolved,
        )
        with self._tx() as cur:
            self._insert_execution_event(cur, event)
            self._insert_event(
                cur,
                "emergency_reduce_override_resolved" if resolved
                else "emergency_reduce_override_granted",
                message=(
                    f"emergency reduce override {'resolved' if resolved else 'granted'} "
                    f"for {symbol} by {actor}"
                ),
                symbol=symbol, session_id=session.id,
                payload={"actor": actor, "reason": reason},
            )

    async def grant_emergency_reduce_override(
        self, symbol: str, *, actor: str, reason: str
    ) -> None:
        async with self._lock:
            self._write_emergency_reduce_override_locked(
                normalize_symbol(symbol), actor=actor, reason=reason, resolved=False
            )

    async def resolve_emergency_reduce_override(
        self, symbol: str, *, actor: str, reason: str
    ) -> None:
        async with self._lock:
            self._write_emergency_reduce_override_locked(
                normalize_symbol(symbol), actor=actor, reason=reason, resolved=True
            )

    async def list_emergency_reduce_overrides(self) -> set[str]:
        async with self._lock:
            session = self._ensure_current_session_locked()
            return self._active_overrides_locked(session.id)

    async def authorize_emergency_reduce_override(
        self, symbol: str, *, actor: str
    ) -> None:
        key = normalize_symbol(symbol)
        async with self._lock:
            session = self._ensure_current_session_locked()
            if self._current_trading_state_locked(session.id) is not TradingState.HALTED:
                raise EmergencyReduceBlockedError(
                    f"emergency reduce of {key} refused: session is not halted "
                    "(use an ordinary flatten)"
                )
            if self._position_locked(key).quantity <= 0:
                raise EmergencyReduceBlockedError(
                    f"emergency reduce of {key} refused: no open position"
                )
            tq_rows = self._read_all(
                "SELECT * FROM execution_events WHERE event_type IN "
                "('timeout_quarantine','submitted','rejected','canceled','filled') "
                "ORDER BY sequence"
            )
            tq_ids = timeout_quarantined_order_ids(
                [self._execution_event(r) for r in tq_rows]
            )
            if tq_ids:
                placeholders = ",".join("?" * len(tq_ids))
                rows = self._read_all(
                    f"SELECT symbol FROM orders WHERE id IN ({placeholders})",
                    tuple(sorted(tq_ids)),
                )
                if any(r["symbol"] == key for r in rows):
                    raise EmergencyReduceBlockedError(
                        f"emergency reduce of {key} refused: an ambiguous "
                        "TIMEOUT_QUARANTINE order is unresolved (INV-3)"
                    )
            # Defensive (review): never stack a second grant on top of an active
            # one — an override authorizes exactly one flatten and is consumed by it.
            if key in self._active_overrides_locked(session.id):
                raise EmergencyReduceBlockedError(
                    f"emergency reduce of {key} refused: an override is already active"
                )
            self._write_emergency_reduce_override_locked(
                key, actor=actor, reason="emergency_reduce", resolved=False
            )

    async def close_session(
        self, session_id: Optional[str] = None
    ) -> SessionRecord:
        async with self._lock:
            if session_id is None:
                # The active session, without auto-creating one (closing when
                # nothing is active means there is nothing to close).
                row = self._read_one(
                    "SELECT * FROM sessions WHERE status = ? "
                    "ORDER BY rowid DESC LIMIT 1",
                    (SessionStatus.ACTIVE.value,),
                )
                if row is None:
                    raise SessionAlreadyClosedError("no active session to close")
                session = self._session(row)
            else:
                row = self._read_one(
                    "SELECT * FROM sessions WHERE id = ?", (session_id,)
                )
                if row is None:
                    raise UnknownEntityError(f"session {session_id} not found")
                session = self._session(row)
                if session.status is SessionStatus.CLOSED:
                    raise SessionAlreadyClosedError(
                        f"session {session.id} is already closed"
                    )

            now = utcnow()

            # Read what we'll touch *before* opening the transaction (reads are
            # consistent under the lock); the writes then all commit together.
            # Order preserved (rowid / symbol) so audit-event order is unchanged.
            open_candidates = [
                self._candidate(r)
                for r in self._read_all(
                    "SELECT * FROM candidates WHERE session_id = ? "
                    "AND status IN (?, ?) ORDER BY rowid",
                    (
                        session.id,
                        CandidateStatus.PENDING.value,
                        CandidateStatus.APPROVED.value,
                    ),
                )
            ]
            # Still-CREATED (never-submitted) **BUY** orders in this session are
            # cancelled at close (D-013a) so they cannot sit submittable afterward;
            # already-submitted orders are untouched and keep reconciling (D-011).
            # A CREATED **SELL** is a protective/flatten exit that must remain
            # submittable after close — protection is always-on (Phase 7 §5.2), so
            # it is filtered out here, in SQL.
            created_orders = [
                self._order(r)
                for r in self._read_all(
                    "SELECT * FROM orders WHERE session_id = ? AND status = ? "
                    "AND side = ? ORDER BY rowid",
                    (session.id, OrderStatus.CREATED.value, OrderSide.BUY.value),
                )
            ]
            # PENDING/APPROVED sell intents expire at close, like candidates.
            open_sell_intents = [
                self._sell_intent(r)
                for r in self._read_all(
                    "SELECT * FROM sell_intents WHERE session_id = ? "
                    "AND status IN (?, ?) ORDER BY rowid",
                    (
                        session.id,
                        SellIntentStatus.PENDING.value,
                        SellIntentStatus.APPROVED.value,
                    ),
                )
            ]
            nonzero_positions = []
            # Enumerate symbols from the event log (Rule-7 truth), matching
            # memory + list_positions, so a FILL event with no fill row is
            # snapshotted and the two stores agree.
            for r in self._read_all(
                "SELECT DISTINCT symbol FROM execution_events "
                "WHERE event_type = 'fill' ORDER BY symbol"
            ):
                pos = self._position_locked(r["symbol"])
                if pos.quantity != 0:
                    nonzero_positions.append(pos)

            plan = plan_close_session(
                session=session,
                open_candidates=open_candidates,
                created_orders=created_orders,
                open_sell_intents=open_sell_intents,
                nonzero_positions=nonzero_positions,
                now=now,
            )

            # Apply (read-then-write form): all UPDATEs/INSERTs commit together.
            with self._tx() as cur:
                for candidate, event in zip(open_candidates, plan.candidate_events):
                    cur.execute(
                        "UPDATE candidates SET status=?, expired_at=?, "
                        "updated_at=? WHERE id=?",
                        (
                            CandidateStatus.EXPIRED.value,
                            _dt(now),
                            _dt(now),
                            candidate.id,
                        ),
                    )
                    self._insert_event(cur, event.event_type, **event.as_kwargs())
                for order, event in zip(created_orders, plan.order_events):
                    cur.execute(
                        "UPDATE orders SET status=?, canceled_at=?, updated_at=? "
                        "WHERE id=?",
                        (
                            OrderStatus.CANCELED.value,
                            _dt(now),
                            _dt(now),
                            order.id,
                        ),
                    )
                    self._insert_event(cur, event.event_type, **event.as_kwargs())
                for intent, event in zip(open_sell_intents, plan.sell_intent_events):
                    cur.execute(
                        "UPDATE sell_intents SET status=?, expired_at=?, "
                        "updated_at=? WHERE id=?",
                        (
                            SellIntentStatus.EXPIRED.value,
                            _dt(now),
                            _dt(now),
                            intent.id,
                        ),
                    )
                    self._insert_event(cur, event.event_type, **event.as_kwargs())
                for snap in plan.snapshots:
                    cur.execute(
                        """INSERT INTO position_snapshots
                           (id, session_id, symbol, quantity, cost_basis,
                            average_price, captured_at)
                           VALUES (?,?,?,?,?,?,?)""",
                        (
                            snap.id,
                            snap.session_id,
                            snap.symbol,
                            snap.quantity,
                            snap.cost_basis,
                            snap.average_price,
                            _dt(snap.captured_at),
                        ),
                    )
                cur.execute(
                    "UPDATE sessions SET status=?, closed_at=?, updated_at=? "
                    "WHERE id=?",
                    (
                        SessionStatus.CLOSED.value,
                        _dt(now),
                        _dt(now),
                        session.id,
                    ),
                )
                self._insert_event(
                    cur, plan.close_event.event_type, **plan.close_event.as_kwargs()
                )

            session.status = SessionStatus.CLOSED
            session.closed_at = now
            session.updated_at = now
            return session

    async def list_position_snapshots(
        self, session_id: str
    ) -> list[PositionSnapshot]:
        async with self._lock:
            rows = self._read_all(
                "SELECT * FROM position_snapshots WHERE session_id = ? "
                "ORDER BY rowid",
                (session_id,),
            )
            return [self._snapshot(r) for r in rows]
