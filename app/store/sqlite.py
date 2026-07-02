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
* **Position is derived** — there is no positions table; positions are folded
  from the fill rows via the shared :func:`app.position.fold_fills`, the exact
  same code path the in-memory store uses (Rule 7).

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
from typing import Any, Iterator, Optional

from app.models import (
    Candidate,
    CandidateStatus,
    Event,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSnapshot,
    SessionRecord,
    SessionStatus,
    SubmitRecoveryRecord,
    TradingMode,
    WatchlistSymbol,
    utcnow,
)
from app.position import fold_fills
from app.store.base import (
    CLAIM_BLOCKED,
    CLAIM_CLAIMED,
    CandidateTransitionError,
    FillAppendResult,
    InvalidOrderError,
    RiskLimits,
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
    ORDER_TRANSITION_NOOP,
    ORDER_TRANSITION_REJECT,
    plan_append_fill,
    plan_claim_order_for_submission,
    plan_close_session,
    plan_create_order_for_candidate,
    plan_transition_order,
)
from app.store.transitions import (
    CANDIDATE_TIMESTAMP,
    CANDIDATE_TRANSITIONS,
)
from app.store.validation import (
    NON_TERMINAL_ORDER_STATUSES,
    existing_exposure,
    order_candidate_match_reason,
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

CREATE TABLE IF NOT EXISTS orders (
    id                TEXT PRIMARY KEY,
    candidate_id      TEXT NOT NULL,
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
    id           TEXT PRIMARY KEY,
    event_type   TEXT NOT NULL,
    message      TEXT NOT NULL DEFAULT '',
    symbol       TEXT,
    candidate_id TEXT,
    order_id     TEXT,
    fill_id      TEXT,
    payload      TEXT NOT NULL DEFAULT '{}',
    session_id   TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT PRIMARY KEY,
    session_date TEXT NOT NULL,
    mode         TEXT NOT NULL,
    session_type TEXT,
    status       TEXT NOT NULL,
    kill_switch  INTEGER NOT NULL DEFAULT 0,
    buys_paused  INTEGER NOT NULL DEFAULT 0,
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
            self._ensure_current_session_locked()

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
    def _order(row: sqlite3.Row) -> Order:
        return Order(
            id=row["id"],
            candidate_id=row["candidate_id"],
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
            created_at=row["created_at"],
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
    ) -> Event:
        event = Event(
            event_type=str(event_type),
            message=message,
            symbol=symbol,
            candidate_id=candidate_id,
            order_id=order_id,
            fill_id=fill_id,
            payload=payload or {},
            session_id=session_id,
        )
        cur.execute(
            """INSERT INTO events
               (id, event_type, message, symbol, candidate_id, order_id,
                fill_id, payload, session_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
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
                buys_paused, opened_at, closed_at, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                s.id,
                s.session_date,
                s.mode.value,
                s.session_type.value if s.session_type else None,
                s.status.value,
                _bit(s.kill_switch),
                _bit(s.buys_paused),
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
            clauses.append("status = ?")
            params.append(CandidateStatus(status).value)
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
        new_status = CandidateStatus(new_status)
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
    # Orders
    # ------------------------------------------------------------------ #
    async def create_order(
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
                session_id=session_id,
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
            for r in self._read_all("SELECT DISTINCT symbol FROM fills ORDER BY symbol")
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
            plan = plan_create_order_for_candidate(
                candidate=candidate,
                session=session,
                exposure_before_order=self._current_exposure_locked(),
                risk_limits=risk_limits,
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
            plan = plan_claim_order_for_submission(
                order=order,
                own_session=own_session,
                current_session=current_session,
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
    ) -> SubmitRecoveryRecord:
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
                session_id=session_id,
            )
            with self._tx() as cur:
                self._insert_submit_recovery(cur, record)
                self._insert_event(
                    cur,
                    "submit_recovery_recorded",
                    message=(
                        f"broker order {broker_order_id} for {key} needs "
                        f"recovery: {failure_reason}"
                    ),
                    symbol=key,
                    order_id=local_order_id,
                    payload={
                        "broker_order_id": broker_order_id,
                        "failure_reason": failure_reason,
                    },
                    session_id=session_id,
                )
            return record

    async def list_submit_recoveries(
        self, *, unresolved_only: bool = False
    ) -> list[SubmitRecoveryRecord]:
        async with self._lock:
            if unresolved_only:
                rows = self._read_all(
                    "SELECT * FROM submit_recoveries WHERE cleanup_status = ? "
                    "ORDER BY rowid",
                    ("unresolved",),
                )
            else:
                rows = self._read_all(
                    "SELECT * FROM submit_recoveries ORDER BY rowid"
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
            resolving = (
                cleanup_status is not None
                and cleanup_status != "unresolved"
                and cleanup_status != record.cleanup_status
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
                if resolving:
                    self._insert_event(
                        cur,
                        "submit_recovery_resolved",
                        message=(
                            f"broker order {updated.broker_order_id} recovery "
                            f"resolved: {cleanup_status}"
                        ),
                        symbol=updated.symbol,
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
               (id, candidate_id, symbol, side, order_type, quantity, limit_price,
                status, filled_quantity, replaces_order_id, broker_order_id,
                session_id, created_at, updated_at, submitted_at, filled_at,
                canceled_at, rejected_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                o.id,
                o.candidate_id,
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
        new_status = OrderStatus(new_status)
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

            # FILL_APPEND — one transaction: INSERT the fill row + its audit event.
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
        rows = self._read_all(
            "SELECT * FROM fills WHERE symbol = ? ORDER BY rowid", (symbol,)
        )
        return fold_fills(symbol, [self._fill(r) for r in rows])

    async def get_position(self, symbol: str) -> Position:
        key = normalize_symbol(symbol)
        async with self._lock:
            return self._position_locked(key)

    async def list_positions(self) -> list[Position]:
        async with self._lock:
            rows = self._read_all(
                "SELECT DISTINCT symbol FROM fills ORDER BY symbol"
            )
            return [self._position_locked(r["symbol"]) for r in rows]

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
                )

    async def list_events(
        self,
        *,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Event]:
        clauses, params = [], []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
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

    async def set_kill_switch(self, engaged: bool) -> SessionRecord:
        async with self._lock:
            session = self._ensure_current_session_locked()
            session.kill_switch = engaged
            session.updated_at = utcnow()
            with self._tx() as cur:
                cur.execute(
                    "UPDATE sessions SET kill_switch=?, updated_at=? WHERE id=?",
                    (_bit(engaged), _dt(session.updated_at), session.id),
                )
                self._insert_event(
                    cur,
                    "kill_switch_engaged" if engaged else "kill_switch_released",
                    message=f"kill switch {'engaged' if engaged else 'released'}",
                    session_id=session.id,
                    payload={"kill_switch": engaged},
                )
            return session

    async def set_buys_paused(self, paused: bool) -> SessionRecord:
        async with self._lock:
            session = self._ensure_current_session_locked()
            session.buys_paused = paused
            session.updated_at = utcnow()
            with self._tx() as cur:
                cur.execute(
                    "UPDATE sessions SET buys_paused=?, updated_at=? WHERE id=?",
                    (_bit(paused), _dt(session.updated_at), session.id),
                )
                self._insert_event(
                    cur,
                    "buys_paused" if paused else "buys_resumed",
                    message=f"buys {'paused' if paused else 'resumed'}",
                    session_id=session.id,
                    payload={"buys_paused": paused},
                )
            return session

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
            # Still-CREATED (never-submitted) orders in this session are cancelled
            # at close (D-013a) so they cannot sit submittable afterward; already-
            # submitted orders are untouched and keep reconciling (D-011).
            created_orders = [
                self._order(r)
                for r in self._read_all(
                    "SELECT * FROM orders WHERE session_id = ? AND status = ? "
                    "ORDER BY rowid",
                    (session.id, OrderStatus.CREATED.value),
                )
            ]
            nonzero_positions = []
            for r in self._read_all(
                "SELECT DISTINCT symbol FROM fills ORDER BY symbol"
            ):
                pos = self._position_locked(r["symbol"])
                if pos.quantity != 0:
                    nonzero_positions.append(pos)

            plan = plan_close_session(
                session=session,
                open_candidates=open_candidates,
                created_orders=created_orders,
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
