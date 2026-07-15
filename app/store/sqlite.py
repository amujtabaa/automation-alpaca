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
from contextlib import contextmanager, nullcontext
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_UNRESOLVED,
    Candidate,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    CandidateStatus,
    Event,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
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
    ORDER_STATUS_EVENT_TYPES,
    active_emergency_reduce_overrides,
    compose_trading_state,
    control_trading_state,
    current_trading_state,
    project_order_status,
    project_symbol_position,
    quarantined_symbols,
    reconcile_trading_state,
    timeout_quarantined_order_ids,
)
from app.store.base import (
    CLAIM_BLOCKED,
    CLAIM_CLAIMED,
    COMMAND_ACTOR_SYSTEM,
    FLATTEN_CREATED,
    FLATTEN_EXISTING,
    FLATTEN_FLAT,
    CandidateTransitionError,
    EmergencyReduceBlockedError,
    FillAppendResult,
    FlattenBlockedError,
    FlattenResult,
    InvalidOrderError,
    OrderIntentBlockedError,
    ProtectionHaltedError,
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
    execution_event_for_routine_transition,
    order_status_backfill_event,
    FLATTEN_FLAT as _PLAN_FLATTEN_FLAT,
    FLATTEN_EXISTING as _PLAN_FLATTEN_EXISTING,
    FLATTEN_DENIED_HALTED,
    FLATTEN_SUPERSEDE_AND_CREATE,
    ENVELOPE_FILL_REJECT,
    ENVELOPE_TRANSITION_APPLY,
    STAGE_DIVERGENCE,
    STAGE_REFUSED_STALE,
    STAGE_STAGED,
    EnvelopeActionPausedError,
    EnvelopeActionStageResult,
    PlannedAction,
    plan_stage_envelope_action,
    ENVELOPE_TRANSITION_NOOP,
    ENVELOPE_TRANSITION_REJECT,
    EnvelopeTransitionError,
    EnvelopeTransitionPlan,
    ORDER_TRANSITION_APPLY,
    ORDER_TRANSITION_NOOP,
    ORDER_TRANSITION_REJECT,
    OrderEventedTransitionPlan,
    ENVELOPE_RELEASING_TERMINALS,
    VENUE_LIVE_ORDER_STATUSES,
    envelope_backing_intent_error,
    envelope_created_event,
    envelope_draft_reason,
    plan_envelope_fill,
    plan_envelope_transition,
    plan_supersede_envelope,
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
    ENVELOPE_TRANSITIONS,
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
    envelope_id     TEXT,
    primary_id      TEXT,
    spawn_id        TEXT,
    session_id      TEXT,
    correlation_id  TEXT,
    payload         TEXT NOT NULL DEFAULT '{}'
);

-- Execution envelopes (ADR-010 / WO-0016): the pre-approved, immutable,
-- bounded mandate for one sell intent. Bounds NEVER update in place —
-- amendment is a new row via the atomic supersede operation. Only status,
-- remaining_quantity (deduped-fill decrements ONLY), replaces_used,
-- supersession linkage, and timestamps change after insert. The
-- single-ACTIVE-per-intent partial unique index is created in initialize()
-- (after _migrate, matching the fills-index pattern).
CREATE TABLE IF NOT EXISTS execution_envelopes (
    id                       TEXT PRIMARY KEY,
    sell_intent_id           TEXT NOT NULL,
    symbol                   TEXT NOT NULL,
    side                     TEXT NOT NULL,
    reduce_only              INTEGER NOT NULL DEFAULT 1,
    qty_ceiling              INTEGER NOT NULL,
    remaining_quantity       INTEGER NOT NULL,
    floor_price              REAL NOT NULL,
    trail_distance_min       REAL NOT NULL,
    trail_distance_max       REAL NOT NULL,
    participation_rate_cap   REAL NOT NULL,
    aggressiveness           TEXT NOT NULL DEFAULT '[]',
    cooldown_floor_ms        INTEGER NOT NULL,
    cancel_replace_budget    INTEGER NOT NULL,
    replaces_used            INTEGER NOT NULL DEFAULT 0,
    max_outstanding_children INTEGER NOT NULL DEFAULT 1,
    expires_at               TEXT NOT NULL,
    allowed_session_phases   TEXT NOT NULL,
    expiry_disposition       TEXT NOT NULL,
    stale_data_disposition   TEXT NOT NULL,
    status                   TEXT NOT NULL,
    supersedes_id            TEXT,
    superseded_by_id         TEXT,
    session_id               TEXT,
    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL,
    approved_at              TEXT,
    activated_at             TEXT,
    frozen_at                TEXT,
    completed_at             TEXT,
    expired_at               TEXT,
    exhausted_at             TEXT,
    breached_at              TEXT,
    superseded_at            TEXT,
    cancelled_at             TEXT
);
CREATE INDEX IF NOT EXISTS idx_envelopes_intent
    ON execution_envelopes(sell_intent_id);
CREATE INDEX IF NOT EXISTS idx_envelopes_symbol
    ON execution_envelopes(symbol);
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
            conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fills_symbol ON fills(symbol)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_fills_session ON fills(session_id)"
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
            # WO-0007b read-flip: get_order folds a per-order event query
            # (WHERE order_id=?); index it so the flipped read stays cheap.
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_exec_events_order "
                "ON execution_events(order_id)"
            )
            # ADR-010 (WO-0016): per-envelope event queries (replay/audit of one
            # mandate) and the structural single-ACTIVE-per-intent invariant —
            # the DB-level twin of the in-memory store's under-lock check.
            # Created here (after _migrate) so they exist on migrated DBs too.
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_exec_events_envelope "
                "ON execution_events(envelope_id)"
            )
            # WO-0032 / REV-0023 P0: the single-ACTIVE mandate is per SYMBOL, not
            # per sell_intent_id (a second intent for the same symbol — e.g.
            # across a session boundary that expired the first intent — must not
            # be able to double-book the exit). Drop the old intent-scoped index
            # first so a re-init/migrated DB adopts the symbol-scoped one.
            conn.execute("DROP INDEX IF EXISTS idx_envelopes_one_active")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_envelopes_one_active "
                "ON execution_envelopes(symbol) WHERE status = 'active'"
            )
            self._backfill_fill_events_locked()
            self._backfill_trading_state_events_locked()
            self._backfill_order_status_events_locked()
            self._ensure_current_session_locked()

    def _backfill_order_status_events_locked(self) -> None:
        """WO-0007b read-flip migration (mirror of the in-memory backfill): an order
        whose status predates WO-0007a eventing has no lifecycle events, so post-flip
        get_order would project CREATED. Emit one synthetic reconstruction event per
        such order so the projection yields its (pre-flip authoritative) column
        status. Runs AFTER the fill backfill. Only touches orders with NO lifecycle
        events (projection==CREATED, column!=CREATED); idempotent (deterministic
        dedupe_key + the projection sees prior backfill events on re-init)."""

        order_rows = self._read_all("SELECT * FROM orders")
        if not order_rows:
            return
        event_rows = self._read_all("SELECT * FROM execution_events ORDER BY sequence")
        events = [self._execution_event(r) for r in event_rows]
        with self._tx() as cur:
            for row in order_rows:
                order = self._order(row)
                # WO-0013 (F-002): reconstruct ONLY orders with zero status-lifecycle
                # events (mirror of the in-memory backfill). A released order projects
                # CREATED but HAS events, so the old projected==CREATED predicate
                # wrongly re-backfilled it; a FILL is excluded, so a pre-eventing FILLED
                # order (fills present, no lifecycle event) is still reconstructed.
                # Reuses the already-loaded `events` list — no extra per-order query.
                has_status_events = any(
                    e.order_id == order.id and e.event_type in ORDER_STATUS_EVENT_TYPES
                    for e in events
                )
                if not has_status_events and order.status is not OrderStatus.CREATED:
                    event = order_status_backfill_event(order)
                    if event is not None:
                        self._insert_execution_event(cur, event)

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
                        session.id,
                        prior_control=control_prior,
                        kill_switch=session.kill_switch,
                        buys_paused=session.buys_paused,
                        reason="backfill",
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

        exec_event_cols = {
            r["name"]
            for r in conn.execute("PRAGMA table_info(execution_events)").fetchall()
        }
        if "envelope_id" not in exec_event_cols:  # added in W3 (ADR-010 / WO-0016)
            # The owning execution envelope. Additive + nullable: pre-envelope
            # events simply have NULL, replay stays valid within schema_version 1
            # (no bump — the version marks INCOMPATIBLE shape changes). Fresh DBs
            # get it from SCHEMA; its index is created in initialize().
            conn.execute("ALTER TABLE execution_events ADD COLUMN envelope_id TEXT")

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
    def _envelope(row: sqlite3.Row) -> ExecutionEnvelope:
        return ExecutionEnvelope(
            id=row["id"],
            sell_intent_id=row["sell_intent_id"],
            symbol=row["symbol"],
            side=row["side"],
            reduce_only=bool(row["reduce_only"]),
            qty_ceiling=row["qty_ceiling"],
            remaining_quantity=row["remaining_quantity"],
            floor_price=row["floor_price"],
            trail_distance_min=row["trail_distance_min"],
            trail_distance_max=row["trail_distance_max"],
            participation_rate_cap=row["participation_rate_cap"],
            aggressiveness=json.loads(row["aggressiveness"]),
            cooldown_floor_ms=row["cooldown_floor_ms"],
            cancel_replace_budget=row["cancel_replace_budget"],
            replaces_used=row["replaces_used"],
            max_outstanding_children=row["max_outstanding_children"],
            expires_at=row["expires_at"],
            allowed_session_phases=json.loads(row["allowed_session_phases"]),
            expiry_disposition=row["expiry_disposition"],
            stale_data_disposition=row["stale_data_disposition"],
            status=row["status"],
            supersedes_id=row["supersedes_id"],
            superseded_by_id=row["superseded_by_id"],
            session_id=row["session_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            approved_at=row["approved_at"],
            activated_at=row["activated_at"],
            frozen_at=row["frozen_at"],
            completed_at=row["completed_at"],
            expired_at=row["expired_at"],
            exhausted_at=row["exhausted_at"],
            breached_at=row["breached_at"],
            superseded_at=row["superseded_at"],
            cancelled_at=row["cancelled_at"],
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
            envelope_id=row["envelope_id"],
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
            "SELECT * FROM sessions WHERE session_date = ? ORDER BY rowid DESC LIMIT 1",
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
                found = self._session(row) if row is not None else None
                if found is None:
                    raise UnknownEntityError(
                        f"session {session_id} does not exist; cannot create candidate"
                    )
                session = found
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
            # W2-CAND (REV-0013/0014 / single-flight): refuse a SECOND active
            # (PENDING/APPROVED) candidate for the same symbol+session — return the
            # existing one idempotently, under the SAME lock as the insert, mirroring
            # create_sell_intent. Closes the strategy-loop TOCTOU / dev-inject /
            # retry double-candidate -> double-BUY-intent gap: buy-side single-flight
            # is now a store invariant, not a caller-side convention. "Active" =
            # PENDING/APPROVED (strategy_loop._OPEN_CANDIDATE_STATUSES); an ORDERED/
            # rejected/expired candidate no longer blocks a fresh proposal (re-buy).
            existing = self._active_candidate_locked(key, session_id)
            if existing is not None:
                return existing
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

    def _active_candidate_locked(
        self, symbol: str, session_id: str
    ) -> Optional[Candidate]:
        """The current active (PENDING/APPROVED) candidate for symbol+session, or
        None — the single-flight predicate for create_candidate (W2-CAND), the
        buy-side analogue of _active_sell_intent_locked. Newest-first so a legacy
        pre-invariant duplicate resolves deterministically to the latest."""
        row = self._read_one(
            "SELECT * FROM candidates WHERE symbol = ? AND session_id = ? "
            "AND status IN (?, ?) ORDER BY rowid DESC LIMIT 1",
            (
                symbol,
                session_id,
                CandidateStatus.PENDING.value,
                CandidateStatus.APPROVED.value,
            ),
        )
        return self._candidate(row) if row is not None else None

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

    def _insert_envelope(self, cur: sqlite3.Cursor, env: ExecutionEnvelope) -> None:
        cur.execute(
            """INSERT INTO execution_envelopes
               (id, sell_intent_id, symbol, side, reduce_only, qty_ceiling,
                remaining_quantity, floor_price, trail_distance_min,
                trail_distance_max, participation_rate_cap, aggressiveness,
                cooldown_floor_ms, cancel_replace_budget, replaces_used,
                max_outstanding_children, expires_at, allowed_session_phases,
                expiry_disposition, stale_data_disposition, status,
                supersedes_id, superseded_by_id, session_id, created_at,
                updated_at, approved_at, activated_at, frozen_at, completed_at,
                expired_at, exhausted_at, breached_at, superseded_at,
                cancelled_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                       ?,?,?,?,?,?,?,?,?)""",
            (
                env.id,
                env.sell_intent_id,
                env.symbol,
                env.side.value,
                _bit(env.reduce_only),
                env.qty_ceiling,
                env.remaining_quantity,
                env.floor_price,
                env.trail_distance_min,
                env.trail_distance_max,
                env.participation_rate_cap,
                json.dumps(list(env.aggressiveness)),
                env.cooldown_floor_ms,
                env.cancel_replace_budget,
                env.replaces_used,
                env.max_outstanding_children,
                _dt(env.expires_at),
                json.dumps([p.value for p in env.allowed_session_phases]),
                env.expiry_disposition.value,
                env.stale_data_disposition.value,
                env.status.value,
                env.supersedes_id,
                env.superseded_by_id,
                env.session_id,
                _dt(env.created_at),
                _dt(env.updated_at),
                _dt(env.approved_at),
                _dt(env.activated_at),
                _dt(env.frozen_at),
                _dt(env.completed_at),
                _dt(env.expired_at),
                _dt(env.exhausted_at),
                _dt(env.breached_at),
                _dt(env.superseded_at),
                _dt(env.cancelled_at),
            ),
        )

    def _update_envelope(self, cur: sqlite3.Cursor, env: ExecutionEnvelope) -> None:
        """Persist the MUTABLE surface only. Bounds are deliberately absent
        from this UPDATE — the storage layer structurally cannot amend them
        (ADR-010: amendment is by supersession, never in place)."""

        cur.execute(
            """UPDATE execution_envelopes SET status=?, remaining_quantity=?,
               replaces_used=?, supersedes_id=?, superseded_by_id=?,
               updated_at=?, approved_at=?, activated_at=?, frozen_at=?,
               completed_at=?, expired_at=?, exhausted_at=?, breached_at=?,
               superseded_at=?, cancelled_at=?
               WHERE id=?""",
            (
                env.status.value,
                env.remaining_quantity,
                env.replaces_used,
                env.supersedes_id,
                env.superseded_by_id,
                _dt(env.updated_at),
                _dt(env.approved_at),
                _dt(env.activated_at),
                _dt(env.frozen_at),
                _dt(env.completed_at),
                _dt(env.expired_at),
                _dt(env.exhausted_at),
                _dt(env.breached_at),
                _dt(env.superseded_at),
                _dt(env.cancelled_at),
                env.id,
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
            needs_review = order is not None and self._order_needs_review_locked(
                order.id
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
        actor: str = COMMAND_ACTOR_SYSTEM,
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
            payload={
                "reason": reason.value,
                "target_quantity": target_quantity,
                # Who commanded a created MANUAL_FLATTEN (REV-0002 F-002); the
                # default keeps a protection-tick create_sell_intent at "system".
                "actor": actor,
            },
        )
        return intent

    def _transition_sell_intent_locked(
        self,
        cur: sqlite3.Cursor,
        intent: SellIntent,
        new_status: SellIntentStatus,
        *,
        order_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Apply a sell-intent status transition in place + persist it (assumes
        the caller already holds ``self._lock`` and is inside a
        ``with self._tx() as cur:`` block). Returns ``False`` for a
        same-status no-op (nothing applied, no event written); ``True`` if it
        actually transitioned. Raises :class:`SellIntentTransitionError` for an
        illegal transition (nothing mutated, nothing persisted). ``reason``
        (WO-0036 R2) lands in the event payload so an envelope-driven
        transition is distinguishable from a legacy one."""

        current = intent.status
        if new_status is current:
            return False
        if new_status not in SELL_INTENT_TRANSITIONS.get(current, set()):
            raise SellIntentTransitionError(
                f"illegal sell intent transition {current.value} -> {new_status.value}"
            )
        intent.status = new_status
        intent.updated_at = utcnow()
        ts_field = SELL_INTENT_TIMESTAMP.get(new_status)
        if ts_field:
            setattr(intent, ts_field, utcnow())
        if new_status is SellIntentStatus.ORDERED and order_id is not None:
            intent.order_id = order_id
        self._update_sell_intent(cur, intent)
        payload: dict = {"from": current.value, "to": new_status.value}
        if reason is not None:
            payload["reason"] = reason
        self._insert_event(
            cur,
            "sell_intent_transition",
            message=f"sell intent {current.value} -> {new_status.value}",
            symbol=intent.symbol,
            order_id=order_id,
            payload=payload,
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
            # ENG-001 / INV-060: the kill switch blocks NEW autonomous order intent.
            # A PROTECTION_FLOOR exit must not be created while Halted — checked here
            # under the SAME lock as the insert so a kill landing during the
            # protection tick's own awaits cannot race the create (the tick's
            # pre-check can go stale). An already-active exit was returned above and
            # stays idempotent; manual flatten has its own Halted-deny.
            if reason is SellReason.PROTECTION_FLOOR:
                session = self._ensure_current_session_locked()
                if (
                    self._current_trading_state_locked(session.id)
                    is TradingState.HALTED
                ):
                    raise ProtectionHaltedError(
                        f"autonomous protection exit for {key} refused: trading "
                        "halted (kill switch engaged)"
                    )
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
            # WO-0036 R2 exclusive driver: while a LIVE envelope backs the
            # intent, the envelope alone drives its lifecycle (activation
            # normalizes it, terminal release expires it) — an out-of-band
            # transition here would desync the two lifecycles.
            live_env = self._live_envelope_for_intent_locked(intent_id)
            if live_env is not None:
                raise SellIntentTransitionError(
                    f"sell intent {intent_id} is bound to live execution "
                    f"envelope {live_env}; its lifecycle is driven by the "
                    "envelope (WO-0036 R2 link)"
                )
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

    # ------------------------------------------------------------------ #
    # Execution envelopes (ADR-010 / WO-0016)
    # ------------------------------------------------------------------ #
    def _other_live_envelope_for_symbol_locked(
        self, cur: sqlite3.Cursor, symbol: str, *, excluding: str
    ) -> Optional[str]:
        """Id of any OTHER envelope for this SYMBOL currently LIVE — ACTIVE or
        FROZEN (WO-0036 R2; the idx_envelopes_one_active partial unique index
        stays the ACTIVE-level storage backstop, this explicit check gives the
        clean domain error and extends the rail to FROZEN).

        Scoped to symbol, not sell_intent_id (WO-0032 / REV-0023 P0): at most
        one live selling mandate per symbol/position — see the InMemoryStateStore
        twin ``_other_live_envelope_for_symbol_unlocked`` for the rationale
        (INV-087; FROZEN counts because a kill-frozen mandate's child may still
        rest at the venue)."""

        row = cur.execute(
            "SELECT id, status FROM execution_envelopes WHERE symbol = ? "
            "AND status IN (?, ?) AND id != ? LIMIT 1",
            (
                normalize_symbol(symbol),
                EnvelopeStatus.ACTIVE.value,
                EnvelopeStatus.FROZEN.value,
                excluding,
            ),
        ).fetchone()
        return row["id"] if row is not None else None

    def _live_envelope_for_intent_locked(
        self, intent_id: str, cur: Optional[sqlite3.Cursor] = None
    ) -> Optional[str]:
        """Id of the LIVE (ACTIVE/FROZEN) envelope backing ``intent_id``, or
        None — the R2 exclusive-driver predicate: while it exists, the envelope
        alone drives the intent's lifecycle and dispatch. Works on an open
        ``_tx`` cursor or (``cur=None``) as a plain locked read."""

        sql = (
            "SELECT id FROM execution_envelopes WHERE sell_intent_id = ? "
            "AND status IN (?, ?) LIMIT 1"
        )
        params = (
            intent_id,
            EnvelopeStatus.ACTIVE.value,
            EnvelopeStatus.FROZEN.value,
        )
        row = (
            cur.execute(sql, params).fetchone()
            if cur is not None
            else self._read_one(sql, params)
        )
        return row["id"] if row is not None else None

    def _validate_backing_intent_locked(
        self, cur: sqlite3.Cursor, envelope: ExecutionEnvelope
    ) -> SellIntent:
        """Load + validate the backing intent for an activation (WO-0036 R2 /
        Codex PR#8 #8) on the open transaction: it must exist, match the
        symbol, and be PENDING or APPROVED. Returns the intent (the caller
        normalizes PENDING→APPROVED via ``_link_backing_intent_locked``);
        raises the shared planner error otherwise. Runs on EVERY entry into
        ACTIVE — approve, generic transition, resume — mirroring
        ``InMemoryStateStore._validate_backing_intent_unlocked``."""

        row = cur.execute(
            "SELECT * FROM sell_intents WHERE id = ?", (envelope.sell_intent_id,)
        ).fetchone()
        intent = self._sell_intent(row) if row is not None else None
        error = envelope_backing_intent_error(
            intent, symbol=envelope.symbol, envelope_id=envelope.id
        )
        if error is not None:
            raise error
        assert intent is not None  # narrowed by the validator
        return intent

    def _link_backing_intent_locked(
        self, cur: sqlite3.Cursor, intent: SellIntent
    ) -> None:
        """Normalize a PENDING backing intent to APPROVED atomically with the
        envelope's activation (the envelope approval IS the human approval of
        the exit — WO-0036 R2); a no-op for an already-APPROVED intent."""

        if intent.status is SellIntentStatus.PENDING:
            self._transition_sell_intent_locked(
                cur, intent, SellIntentStatus.APPROVED, reason="envelope_activation"
            )

    def _release_intent_for_terminal_envelope_locked(
        self, cur: sqlite3.Cursor, envelope: ExecutionEnvelope
    ) -> None:
        """WO-0036 R2 terminal propagation: an envelope entering a RELEASING
        terminal (COMPLETED/EXPIRED/EXHAUSTED/BREACHED/CANCELLED — never
        SUPERSEDED, the successor keeps the intent) expires its backing intent
        so the symbol becomes eligible for fresh protection. Runs inside the
        SAME transaction as the envelope's own transition. Skips when: the
        envelope never activated, the intent is already terminal/ORDERED, or
        ANOTHER live envelope still carries the mandate, or a child of THIS
        envelope may still be live at the venue. Mirrors
        ``InMemoryStateStore._release_intent_for_terminal_envelope_unlocked``."""

        if envelope.status not in ENVELOPE_RELEASING_TERMINALS:
            return
        if envelope.activated_at is None:
            return  # never activated — it never owned the intent
        row = cur.execute(
            "SELECT * FROM sell_intents WHERE id = ?", (envelope.sell_intent_id,)
        ).fetchone()
        if row is None:
            return
        intent = self._sell_intent(row)
        if intent.status not in (
            SellIntentStatus.PENDING,
            SellIntentStatus.APPROVED,
        ):
            return
        other = cur.execute(
            "SELECT id FROM execution_envelopes WHERE sell_intent_id = ? "
            "AND status IN (?, ?) AND id != ? LIMIT 1",
            (
                envelope.sell_intent_id,
                EnvelopeStatus.ACTIVE.value,
                EnvelopeStatus.FROZEN.value,
                envelope.id,
            ),
        ).fetchone()
        if other is not None:
            return  # the mandate lives on in another envelope
        # BREACHED/EXHAUSTED/REST_AT_FLOOR (and an EXPIRED cancel mid-
        # convergence) leave the working order RESTING at the venue: releasing
        # the symbol then would let fresh protection double-book it. Defer to
        # the child-terminal hook, which completes the release when that last
        # obligation ends.
        if self._envelope_has_live_child_locked(cur, envelope):
            return  # a resting/ambiguous child is still a live obligation
        self._transition_sell_intent_locked(
            cur, intent, SellIntentStatus.EXPIRED, reason="envelope_terminal"
        )

    def _release_intent_for_terminal_child_locked(
        self, cur: sqlite3.Cursor, order: Order
    ) -> None:
        """The child-terminal half of the R2 release: an envelope in a
        releasing terminal may still hold the symbol through a RESTING child
        (see above) — when that child reaches a venue terminal, re-run the
        release against its envelope in the SAME transaction as the order
        write. No-ops for non-envelope orders and for envelopes still live."""

        if order.status not in (
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.REJECTED,
        ):
            return
        row = cur.execute(
            "SELECT envelope_id FROM execution_events WHERE order_id = ? "
            "AND event_type = ? AND envelope_id IS NOT NULL LIMIT 1",
            (order.id, ExecutionEventType.ENVELOPE_ACTION.value),
        ).fetchone()
        if row is None:
            return
        env_row = cur.execute(
            "SELECT * FROM execution_envelopes WHERE id = ?", (row["envelope_id"],)
        ).fetchone()
        if env_row is None:
            return
        self._release_intent_for_terminal_envelope_locked(cur, self._envelope(env_row))

    def _envelope_has_live_child_locked(
        self, cur: sqlite3.Cursor, envelope: ExecutionEnvelope
    ) -> bool:
        """Whether the envelope's working order MAY be live at the venue
        (CREATED is local-only staging; TIMEOUT_QUARANTINE IS live, ADR-002).
        The flatten preemption's skip predicate — mirrors
        ``InMemoryStateStore._envelope_has_live_child_unlocked``."""

        try:
            _, working = self._envelope_action_context_locked(cur, envelope)
        except EnvelopeActionPausedError:
            return True  # quarantined child — MAY be live
        return working is not None and working.status is not OrderStatus.CREATED

    def _live_envelope_exit_locked(
        self, symbol: str
    ) -> tuple[Optional[Order], Optional[SellIntent]]:
        """(live-at-venue child order, its envelope's backing intent) for the
        symbol's LIVE envelopes, or (None, None) — the flatten planner's R2
        input (Codex PR#8 #4). The newest venue-live child wins (latest
        ENVELOPE_ACTION sequence), mirroring the working-order convention."""

        live_statuses = ",".join("?" for _ in VENUE_LIVE_ORDER_STATUSES)
        row = self._read_one(
            "SELECT o.*, env.sell_intent_id AS r2_owner_intent_id "
            "FROM execution_events ev "
            "JOIN execution_envelopes env ON env.id = ev.envelope_id "
            "JOIN orders o ON o.id = ev.order_id "
            "WHERE ev.event_type = ? AND env.symbol = ? "
            "AND env.status IN (?, ?) "
            f"AND o.status IN ({live_statuses}) "
            "ORDER BY ev.sequence DESC LIMIT 1",
            (
                ExecutionEventType.ENVELOPE_ACTION.value,
                symbol,
                EnvelopeStatus.ACTIVE.value,
                EnvelopeStatus.FROZEN.value,
                *sorted(s.value for s in VENUE_LIVE_ORDER_STATUSES),
            ),
        )
        if row is None:
            return None, None
        child = self._order(row)
        intent_row = self._read_one(
            "SELECT * FROM sell_intents WHERE id = ?", (row["r2_owner_intent_id"],)
        )
        intent = self._sell_intent(intent_row) if intent_row is not None else None
        return child, intent

    def _apply_envelope_transition_locked(
        self, cur: sqlite3.Cursor, plan: EnvelopeTransitionPlan
    ) -> ExecutionEnvelope:
        """Persist an APPLY-outcome transition plan on an open ``_tx`` cursor.
        The caller has already dispatched NOOP/REJECT and run the
        single-ACTIVE check where the target is ACTIVE.

        WO-0036 R2: this is the ONE choke point every envelope status write
        flows through (supersession excepted — SUPERSEDED transfers, never
        releases), so the terminal propagation lives here: entering a
        releasing terminal expires the backing intent in the SAME transaction,
        sequenced after the envelope's own events."""

        assert plan.envelope is not None
        assert plan.execution_event is not None and plan.audit_event is not None
        self._update_envelope(cur, plan.envelope)
        self._insert_execution_event(cur, plan.execution_event)
        self._insert_event(
            cur, plan.audit_event.event_type, **plan.audit_event.as_kwargs()
        )
        self._release_intent_for_terminal_envelope_locked(cur, plan.envelope)
        return plan.envelope

    async def create_envelope(
        self,
        envelope: ExecutionEnvelope,
        *,
        actor: str = COMMAND_ACTOR_SYSTEM,
    ) -> ExecutionEnvelope:
        bad = envelope_draft_reason(envelope)
        if bad is not None:
            raise InvalidOrderError(bad)
        key = normalize_symbol(envelope.symbol)
        async with self._lock:
            with self._tx() as cur:
                existing = cur.execute(
                    "SELECT 1 FROM execution_envelopes WHERE id = ?",
                    (envelope.id,),
                ).fetchone()
                if existing is not None:
                    raise InvalidOrderError(f"envelope {envelope.id} already exists")
                stored = envelope.model_copy(update={"symbol": key})
                self._insert_envelope(cur, stored)
                self._insert_execution_event(
                    cur, envelope_created_event(stored, actor=actor)
                )
                self._insert_event(
                    cur,
                    "envelope_created",
                    message=f"execution envelope created for {key}",
                    symbol=key,
                    session_id=stored.session_id,
                    correlation_id=stored.sell_intent_id,
                    payload={"actor": actor, "envelope_id": stored.id},
                )
                return stored

    async def get_envelope(self, envelope_id: str) -> Optional[ExecutionEnvelope]:
        async with self._lock:
            row = self._read_one(
                "SELECT * FROM execution_envelopes WHERE id = ?", (envelope_id,)
            )
            return self._envelope(row) if row is not None else None

    async def list_envelopes(
        self,
        *,
        sell_intent_id: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[EnvelopeStatus] = None,
    ) -> list[ExecutionEnvelope]:
        if status is not None:
            require_status_enum(status, EnvelopeStatus, field="status filter")
        sql = "SELECT * FROM execution_envelopes WHERE 1=1"
        params: list[Any] = []
        if sell_intent_id is not None:
            sql += " AND sell_intent_id = ?"
            params.append(sell_intent_id)
        if symbol is not None:
            sql += " AND symbol = ?"
            params.append(normalize_symbol(symbol))
        if status is not None:
            sql += " AND status = ?"
            params.append(status.value)
        async with self._lock:
            rows = self._read_all(sql, tuple(params))
            return [self._envelope(r) for r in rows]

    async def transition_envelope(
        self,
        envelope_id: str,
        new_status: EnvelopeStatus,
        *,
        actor: str = COMMAND_ACTOR_SYSTEM,
        reason: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> ExecutionEnvelope:
        require_status_enum(new_status, EnvelopeStatus, field="new_status")
        async with self._lock:
            # F2 (WO-0035): pre-transaction read-only validation + session
            # bootstrap — _ensure_current_session_locked opens its OWN
            # transaction on a date rollover and crashed the first
            # FROZEN->ACTIVE resume of a new day when nested in the tx below.
            # Ordering mirrors InMemoryStateStore (unknown-id / reject / noop
            # paths have NO session side effect); the lock is held throughout.
            pre_row = self._read_one(
                "SELECT * FROM execution_envelopes WHERE id = ?", (envelope_id,)
            )
            if pre_row is None:
                raise UnknownEntityError(f"envelope {envelope_id} not found")
            pre_plan = plan_envelope_transition(
                self._envelope(pre_row), new_status, actor=actor, reason=reason, now=now
            )
            if pre_plan.outcome == ENVELOPE_TRANSITION_REJECT:
                assert pre_plan.error is not None
                raise pre_plan.error
            # Codex PR#8 F3: return a same-status NOOP BEFORE the session
            # bootstrap, mirroring InMemoryStateStore (and the comment above). A
            # NOOP ACTIVE->ACTIVE must have no session side effect — otherwise a
            # date rollover mints a spurious session/`session_opened` for an
            # idempotent re-activation.
            if pre_plan.outcome == ENVELOPE_TRANSITION_NOOP:
                return self._envelope(pre_row)
            session = (
                self._ensure_current_session_locked()
                if new_status is EnvelopeStatus.ACTIVE
                else None
            )
            with self._tx() as cur:
                row = cur.execute(
                    "SELECT * FROM execution_envelopes WHERE id = ?",
                    (envelope_id,),
                ).fetchone()
                if row is None:
                    raise UnknownEntityError(f"envelope {envelope_id} not found")
                env = self._envelope(row)
                plan = plan_envelope_transition(
                    env, new_status, actor=actor, reason=reason, now=now
                )
                if plan.outcome == ENVELOPE_TRANSITION_REJECT:
                    assert plan.error is not None
                    raise plan.error
                if plan.outcome == ENVELOPE_TRANSITION_NOOP:
                    return env
                if new_status is EnvelopeStatus.ACTIVE:
                    # ADR-010 §4 / INV-060: activation OR resume is new
                    # standing order intent — refused while HALTED, checked
                    # inside the SAME transaction as the write (resume after
                    # release is explicit human action, never automatic).
                    assert session is not None  # ensured pre-tx (F2)
                    if (
                        self._current_trading_state_locked(session.id)
                        is TradingState.HALTED
                    ):
                        raise OrderIntentBlockedError(
                            f"envelope {env.id} cannot enter ACTIVE: trading "
                            "halted (kill switch engaged)"
                        )
                    clash = self._other_live_envelope_for_symbol_locked(
                        cur, env.symbol, excluding=env.id
                    )
                    if clash is not None:
                        raise EnvelopeTransitionError(
                            f"envelope {clash} is already live for symbol "
                            f"{env.symbol} (per-symbol single-ACTIVE mandate, "
                            "INV-087)"
                        )
                    # WO-0036 R2: EVERY entry into ACTIVE (first activation
                    # AND resume) validates the backing-intent link — this
                    # generic edge must not be the one activation path with a
                    # bypass. The PENDING→APPROVED normalization joins this
                    # same transaction, before the envelope's own write.
                    backing_intent = self._validate_backing_intent_locked(cur, env)
                    self._link_backing_intent_locked(cur, backing_intent)
                if new_status is EnvelopeStatus.CANCELLED:
                    # Codex PR#8 #5 (twin of the in-memory guard): refuse a
                    # store-only CANCELLED while a child order is live at the
                    # venue — else a FROZEN mandate stops being monitored while
                    # its submitted SELL keeps working. Quarantined = live.
                    try:
                        _, working = self._envelope_action_context_locked(cur, env)
                        live_child = working is not None
                    except EnvelopeActionPausedError:
                        live_child = True
                    if live_child:
                        raise EnvelopeTransitionError(
                            f"envelope {env.id} cannot be CANCELLED while a child "
                            "order is live at the venue — wind it down first "
                            "(flatten / kill switch), then cancel"
                        )
                stored = self._apply_envelope_transition_locked(cur, plan)
                # A freeze is never exited by a fill: an envelope fully filled
                # while FROZEN completes HERE, on resume, atomically with it.
                if (
                    stored.status is EnvelopeStatus.ACTIVE
                    and (stored.remaining_quantity or 0) == 0
                ):
                    chain = plan_envelope_transition(
                        stored,
                        EnvelopeStatus.COMPLETED,
                        actor="engine",
                        reason="fully filled while frozen; completed on resume",
                        now=now,
                    )
                    assert chain.outcome == ENVELOPE_TRANSITION_APPLY
                    stored = self._apply_envelope_transition_locked(cur, chain)
                return stored

    async def supersede_envelope(
        self,
        old_envelope_id: str,
        successor: ExecutionEnvelope,
        *,
        actor: str = COMMAND_ACTOR_SYSTEM,
        reason: Optional[str] = None,
    ) -> ExecutionEnvelope:
        async with self._lock:
            with self._tx() as cur:
                row = cur.execute(
                    "SELECT * FROM execution_envelopes WHERE id = ?",
                    (old_envelope_id,),
                ).fetchone()
                if row is None:
                    raise UnknownEntityError(f"envelope {old_envelope_id} not found")
                old = self._envelope(row)
                dup = cur.execute(
                    "SELECT 1 FROM execution_envelopes WHERE id = ?",
                    (successor.id,),
                ).fetchone()
                if dup is not None:
                    raise InvalidOrderError(
                        f"successor envelope {successor.id} already exists"
                    )
                normalized = successor.model_copy(
                    update={"symbol": normalize_symbol(successor.symbol)}
                )
                _, working = self._envelope_action_context_locked(cur, old)
                plan = plan_supersede_envelope(
                    old,
                    normalized,
                    actor=actor,
                    reason=reason,
                    working_order=working,
                )
                if plan.outcome == ENVELOPE_TRANSITION_REJECT:
                    assert plan.error is not None
                    raise plan.error
                assert plan.old_envelope is not None and plan.new_envelope is not None
                clash = self._other_live_envelope_for_symbol_locked(
                    cur, old.symbol, excluding=old.id
                )
                if clash is not None:
                    raise EnvelopeTransitionError(
                        f"envelope {clash} is already live for symbol "
                        f"{old.symbol} (per-symbol single-ACTIVE mandate, "
                        "INV-087)"
                    )
                # One atomic unit: A leaves ACTIVE and B enters it in the same
                # transaction — no two-ACTIVE window, and a concurrent second
                # supersede loses at "old is no longer ACTIVE".
                self._update_envelope(cur, plan.old_envelope)
                self._insert_envelope(cur, plan.new_envelope)
                for event in plan.execution_events:
                    self._insert_execution_event(cur, event)
                assert plan.audit_event is not None
                self._insert_event(
                    cur,
                    plan.audit_event.event_type,
                    **plan.audit_event.as_kwargs(),
                )
                # WO-0027: the superseded mandate's staged CREATED orders die
                # with it, in the SAME transaction (live venue orders were
                # refused by the planner — nothing of the old mandate
                # survives).
                self._cancel_staged_envelope_orders_locked(
                    cur, [plan.old_envelope.id], actor=actor
                )
                return plan.new_envelope

    async def record_envelope_fill(
        self,
        envelope_id: str,
        *,
        quantity: int,
        dedupe_key: str,
        price: float,
        order_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ts_event: Optional[datetime] = None,
        source: EventSource = EventSource.BROKER_REST,
        authority: EventAuthority = EventAuthority.BROKER_AUTHORITATIVE,
        now: Optional[datetime] = None,
    ) -> ExecutionEnvelope:
        """Apply one deduped fill fact — the ONLY remaining_quantity writer.
        A dedupe hit (same ``dedupe_key`` already in the log) applies NOTHING:
        that fill was already counted (exactly-once, INV-5)."""

        async with self._lock:
            with self._tx() as cur:
                row = cur.execute(
                    "SELECT * FROM execution_envelopes WHERE id = ?",
                    (envelope_id,),
                ).fetchone()
                if row is None:
                    raise UnknownEntityError(f"envelope {envelope_id} not found")
                env = self._envelope(row)
                plan = plan_envelope_fill(
                    env,
                    quantity=quantity,
                    dedupe_key=dedupe_key,
                    price=price,
                    order_id=order_id,
                    session_id=session_id,
                    ts_event=ts_event,
                    source=source,
                    authority=authority,
                    now=now,
                )
                if plan.outcome == ENVELOPE_FILL_REJECT:
                    assert plan.error is not None
                    raise plan.error
                assert plan.envelope is not None and plan.fill_event is not None
                already = cur.execute(
                    "SELECT 1 FROM execution_events WHERE dedupe_key = ?",
                    (dedupe_key,),
                ).fetchone()
                if already is not None:
                    return env
                self._insert_execution_event(cur, plan.fill_event)
                self._update_envelope(cur, plan.envelope)
                stored = plan.envelope
                if plan.transition is not None:
                    assert plan.transition.outcome == ENVELOPE_TRANSITION_APPLY
                    stored = self._apply_envelope_transition_locked(
                        cur, plan.transition
                    )
                return stored

    def _envelope_action_context_locked(
        self, cur: sqlite3.Cursor, envelope: ExecutionEnvelope
    ) -> tuple[list[ExecutionEvent], Optional[Order]]:
        """(action events, current working order) for one envelope, read on an
        open ``_tx`` cursor. Raises :class:`EnvelopeActionPausedError` if any
        of the envelope's orders is in TIMEOUT_QUARANTINE (ADR-002 pause).
        Mirrors ``InMemoryStateStore._envelope_action_context_unlocked``."""

        rows = cur.execute(
            "SELECT * FROM execution_events WHERE envelope_id = ? AND "
            "event_type = ? ORDER BY sequence",
            (envelope.id, ExecutionEventType.ENVELOPE_ACTION.value),
        ).fetchall()
        actions = [self._execution_event(r) for r in rows]
        working: Optional[Order] = None
        for event in actions:
            if event.order_id is None:
                continue
            order_row = cur.execute(
                "SELECT * FROM orders WHERE id = ?", (event.order_id,)
            ).fetchone()
            if order_row is None:
                continue
            order = self._order(order_row)
            if order.status is OrderStatus.TIMEOUT_QUARANTINE:
                raise EnvelopeActionPausedError(
                    f"envelope {envelope.id} is paused: order {order.id} is in "
                    "timeout quarantine (resolve it before any further action)"
                )
            if order.status not in (
                OrderStatus.FILLED,
                OrderStatus.CANCELED,
                OrderStatus.REJECTED,
            ):
                working = order
        return actions, working

    async def stage_envelope_action(
        self,
        envelope_id: str,
        action: PlannedAction,
        *,
        snapshot_fingerprint: str,
        actor: str = COMMAND_ACTOR_SYSTEM,
        session_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> EnvelopeActionStageResult:
        """WO-0019: the write-time half of D-3, one lock hold + ONE SQL
        transaction (a failure anywhere rolls back the order row AND the
        accounting event together). See
        :func:`app.store.core.plan_stage_envelope_action`."""

        async with self._lock:
            # Validate the envelope EXISTS before ensuring the session (parity-1 /
            # REV-0023): _ensure_current_session_locked runs its OWN committed tx,
            # so on a date rollover it would otherwise leak a new session row +
            # session_opened event for a stage that only ever raises
            # UnknownEntityError — a divergence from InMemoryStateStore, which
            # checks the envelope first. Both stores now have no session side
            # effect on an unknown-id stage.
            if (
                self._read_one(
                    "SELECT 1 FROM execution_envelopes WHERE id = ?", (envelope_id,)
                )
                is None
            ):
                raise UnknownEntityError(f"envelope {envelope_id} not found")
            session = self._ensure_current_session_locked()
            with self._tx() as cur:
                row = cur.execute(
                    "SELECT * FROM execution_envelopes WHERE id = ?",
                    (envelope_id,),
                ).fetchone()
                if row is None:
                    raise UnknownEntityError(f"envelope {envelope_id} not found")
                env = self._envelope(row)
                # INV-060: staging is new order intent — refused while HALTED,
                # checked inside the SAME transaction as the writes below.
                if (
                    self._current_trading_state_locked(session.id)
                    is TradingState.HALTED
                ):
                    raise OrderIntentBlockedError(
                        "envelope action refused: trading halted (kill switch engaged)"
                    )
                actions, working = self._envelope_action_context_locked(cur, env)
                sid = session_id if session_id is not None else session.id
                plan = plan_stage_envelope_action(
                    env,
                    action,
                    history=actions,
                    working_order=working,
                    session_id=sid,
                    snapshot_fingerprint=snapshot_fingerprint,
                    actor=actor,
                    now=now,
                    # WO-0026: live fill-derived position, read inside the
                    # SAME transaction — the reduce-only hard rail's truth.
                    current_position=self._position_locked(env.symbol).quantity,
                )
                if plan.error is not None:
                    raise plan.error
                if plan.outcome == STAGE_DIVERGENCE:
                    assert plan.freeze is not None
                    frozen = self._apply_envelope_transition_locked(cur, plan.freeze)
                    assert plan.divergence_event is not None
                    assert plan.audit_event is not None
                    self._insert_execution_event(cur, plan.divergence_event)
                    self._insert_event(
                        cur,
                        plan.audit_event.event_type,
                        **plan.audit_event.as_kwargs(),
                    )
                    return EnvelopeActionStageResult(STAGE_DIVERGENCE, envelope=frozen)
                if plan.outcome == STAGE_REFUSED_STALE:
                    # WO-0029A: benign stale-plan refusal — evented, envelope
                    # untouched, no order, zero venue calls.
                    assert plan.action_event is not None
                    assert plan.audit_event is not None
                    self._insert_execution_event(cur, plan.action_event)
                    self._insert_event(
                        cur,
                        plan.audit_event.event_type,
                        **plan.audit_event.as_kwargs(),
                    )
                    return EnvelopeActionStageResult(STAGE_REFUSED_STALE, envelope=env)
                assert plan.order is not None and plan.action_event is not None
                assert plan.audit_event is not None
                self._insert_order(cur, plan.order)
                self._insert_execution_event(cur, plan.action_event)
                self._insert_event(
                    cur,
                    plan.audit_event.event_type,
                    **plan.audit_event.as_kwargs(),
                )
                return EnvelopeActionStageResult(
                    STAGE_STAGED,
                    envelope=env,
                    order=plan.order,
                    working_order=working,
                )

    async def approve_envelope_activation(
        self,
        draft: ExecutionEnvelope,
        *,
        actor: str = COMMAND_ACTOR_SYSTEM,
    ) -> ExecutionEnvelope:
        """The WO-0017 approval surface: dedup/idempotency → HALTED check →
        create → approve → activate → events, ONE lock hold + ONE transaction
        (ENG-001 shape; mirrors InMemoryStateStore). A kill that lands first
        blocks the op with ZERO artifacts (the transaction never opens a
        write); re-approving an ACTIVE envelope is an idempotent no-op."""

        async with self._lock:
            # F2 (WO-0035): read-only validation + session bootstrap BEFORE the
            # main transaction. _ensure_current_session_locked opens its OWN
            # transaction on a date rollover, so nesting it inside the tx below
            # crashed the FIRST approval of a new calendar day ("cannot start a
            # transaction within a transaction"). Ordering mirrors
            # InMemoryStateStore exactly: status/draft rejects leave NO side
            # effect; the session bootstrap runs only once they pass. The lock
            # is held throughout, so the authoritative re-read inside the
            # transaction cannot observe different state.
            pre_row = self._read_one(
                "SELECT * FROM execution_envelopes WHERE id = ?", (draft.id,)
            )
            pre = self._envelope(pre_row) if pre_row is not None else None
            if pre is not None:
                if pre.status is EnvelopeStatus.ACTIVE:
                    return pre  # idempotent re-approve
                if pre.status not in (
                    EnvelopeStatus.PENDING,
                    EnvelopeStatus.APPROVED,
                ):
                    raise EnvelopeTransitionError(
                        f"cannot approve envelope {draft.id}: it is {pre.status.value}"
                    )
            else:
                bad = envelope_draft_reason(draft)
                if bad is not None:
                    raise InvalidOrderError(bad)
            session = self._ensure_current_session_locked()
            with self._tx() as cur:
                row = cur.execute(
                    "SELECT * FROM execution_envelopes WHERE id = ?",
                    (draft.id,),
                ).fetchone()
                stored = self._envelope(row) if row is not None else None
                if stored is not None:
                    if stored.status is EnvelopeStatus.ACTIVE:
                        return stored  # idempotent re-approve
                    if stored.status not in (
                        EnvelopeStatus.PENDING,
                        EnvelopeStatus.APPROVED,
                    ):
                        raise EnvelopeTransitionError(
                            f"cannot approve envelope {draft.id}: it is "
                            f"{stored.status.value}"
                        )
                else:
                    bad = envelope_draft_reason(draft)
                    if bad is not None:
                        raise InvalidOrderError(bad)
                # INV-060: the kill switch blocks NEW standing order intent —
                # checked inside the SAME transaction as every write below.
                if (
                    self._current_trading_state_locked(session.id)
                    is TradingState.HALTED
                ):
                    raise OrderIntentBlockedError(
                        "envelope activation refused: trading halted "
                        "(kill switch engaged)"
                    )
                symbol = (stored or draft).symbol
                clash = self._other_live_envelope_for_symbol_locked(
                    cur, symbol, excluding=draft.id
                )
                if clash is not None:
                    raise EnvelopeTransitionError(
                        f"envelope {clash} is already live for symbol "
                        f"{symbol} (per-symbol single-ACTIVE mandate, "
                        "INV-087)"
                    )
                # WO-0036 R2 (Codex PR#8 #8): LOAD + validate the backing
                # intent before anything is minted — a typo'd sell_intent_id
                # or symbol must never produce an owner-less ACTIVE mandate.
                # A raise here rolls the transaction back: zero artifacts.
                backing_intent = self._validate_backing_intent_locked(
                    cur,
                    (stored or draft).model_copy(
                        update={"symbol": normalize_symbol(symbol)}
                    ),
                )
                if stored is None:
                    key = normalize_symbol(draft.symbol)
                    stored = draft.model_copy(update={"symbol": key})
                    self._insert_envelope(cur, stored)
                    self._insert_execution_event(
                        cur, envelope_created_event(stored, actor=actor)
                    )
                    self._insert_event(
                        cur,
                        "envelope_created",
                        message=(f"execution envelope created for {stored.symbol}"),
                        symbol=stored.symbol,
                        session_id=stored.session_id,
                        correlation_id=stored.sell_intent_id,
                        payload={"actor": actor, "envelope_id": stored.id},
                    )
                # R2 link: the envelope approval IS the intent approval —
                # normalized atomically with the activation chain below.
                self._link_backing_intent_locked(cur, backing_intent)
                current = stored
                if current.status is EnvelopeStatus.PENDING:
                    plan = plan_envelope_transition(
                        current, EnvelopeStatus.APPROVED, actor=actor
                    )
                    assert plan.outcome == ENVELOPE_TRANSITION_APPLY
                    current = self._apply_envelope_transition_locked(cur, plan)
                plan = plan_envelope_transition(
                    current, EnvelopeStatus.ACTIVE, actor=actor
                )
                assert plan.outcome == ENVELOPE_TRANSITION_APPLY
                return self._apply_envelope_transition_locked(cur, plan)

    def _cancel_symbol_envelopes_locked(
        self, cur: sqlite3.Cursor, symbol: str, *, actor: str, reason: str
    ) -> None:
        """ADR-010 §4 / D-2: cancel every non-terminal envelope for ``symbol``
        through legal edges (ACTIVE via FROZEN) on an open ``_tx`` cursor —
        the manual-flatten preemption, committing in the SAME transaction as
        the flatten's own writes (mirrors InMemoryStateStore).

        WO-0036 R2: an envelope whose child MAY be live at the venue is
        SKIPPED (evented), never cancelled out from under it — the internal
        twin of the public transition_envelope→CANCELLED live-child guard
        (Codex PR#8 #5); see the InMemoryStateStore twin for the rationale."""

        rows = cur.execute(
            "SELECT * FROM execution_envelopes WHERE symbol = ?", (symbol,)
        ).fetchall()
        preempted: list[str] = []
        for row in rows:
            env = self._envelope(row)
            if not ENVELOPE_TRANSITIONS.get(env.status):
                continue  # terminal — nothing to preempt
            if self._envelope_has_live_child_locked(cur, env):
                self._insert_event(
                    cur,
                    "envelope_preemption_deferred",
                    message=(
                        f"envelope {env.id} preemption deferred: its child may "
                        "be live at the venue (wind it down first)"
                    ),
                    symbol=symbol,
                    payload={
                        "envelope_id": env.id,
                        "reason": "live_child_at_venue",
                        "preemption_reason": reason,
                        "actor": actor,
                    },
                    session_id=env.session_id,
                    correlation_id=env.sell_intent_id,
                )
                continue
            current = env
            if current.status is EnvelopeStatus.ACTIVE:
                plan = plan_envelope_transition(
                    current, EnvelopeStatus.FROZEN, actor=actor, reason=reason
                )
                assert plan.outcome == ENVELOPE_TRANSITION_APPLY
                current = self._apply_envelope_transition_locked(cur, plan)
            plan = plan_envelope_transition(
                current, EnvelopeStatus.CANCELLED, actor=actor, reason=reason
            )
            assert plan.outcome == ENVELOPE_TRANSITION_APPLY
            self._apply_envelope_transition_locked(cur, plan)
            preempted.append(env.id)
        # WO-0024: a preempted mandate's obligations die with it — its staged
        # CREATED orders are cancelled in the SAME transaction, sequenced
        # AFTER the envelope cancellation events
        # (FINDING-W3-staged-order-outlives-preemption).
        self._cancel_staged_envelope_orders_locked(cur, preempted, actor=actor)

    def _cancel_staged_envelope_orders_locked(
        self, cur: sqlite3.Cursor, envelope_ids: list[str], *, actor: str
    ) -> None:
        """Locally CANCEL every CREATED order staged by the given envelopes
        (WO-0024), on the caller's open transaction. CREATED means never
        venue-submitted, so this is a pure local-truth write — no venue call
        belongs here. SUBMITTING/SUBMITTED orders are untouched: venue-side
        wind-down stays with the monitoring loop."""

        if not envelope_ids:
            return
        marks = ",".join("?" for _ in envelope_ids)
        rows = cur.execute(
            "SELECT DISTINCT order_id FROM execution_events "
            f"WHERE envelope_id IN ({marks}) AND event_type = ? "
            "AND order_id IS NOT NULL",
            (*envelope_ids, ExecutionEventType.ENVELOPE_ACTION.value),
        ).fetchall()
        for (order_id,) in rows:
            order_row = cur.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            if order_row is None:
                continue
            order = self._order(order_row)
            if order.status is not OrderStatus.CREATED:
                continue
            plan = plan_transition_order(
                order=order,
                new_status=OrderStatus.CANCELED,
                filled_quantity=None,
                broker_order_id=None,
                actor=actor,
            )
            assert plan.outcome == ORDER_TRANSITION_APPLY
            assert plan.order is not None and plan.event is not None
            cur.execute(
                "UPDATE orders SET status=?, canceled_at=?, updated_at=? WHERE id=?",
                (
                    OrderStatus.CANCELED.value,
                    _dt(plan.order.canceled_at),
                    _dt(plan.order.updated_at),
                    plan.order.id,
                ),
            )
            self._insert_event(cur, plan.event.event_type, **plan.event.as_kwargs())
            exec_event = execution_event_for_routine_transition(
                order, plan.order.status, plan.order.filled_quantity
            )
            if exec_event is not None:
                self._insert_execution_event(cur, exec_event)

    def _dispatch_order_for_sell_intent_locked(
        self,
        intent: SellIntent,
        *,
        order_type: OrderType,
        limit_price: Optional[float],
        cur: Optional[sqlite3.Cursor] = None,
    ) -> Order:
        """The plan+apply body of the APPROVED->ORDERED handoff (assumes the
        caller already holds ``self._lock`` — either the public
        ``create_order_for_sell_intent`` or ``flatten_position``, X-001, which
        needs this same dispatch inlined into its own single lock hold rather
        than calling the public method and re-acquiring the lock).

        When ``cur`` is given (the ``flatten_position`` path) every write joins
        the caller's open transaction, so the whole supersede+create+approve+
        dispatch sequence commits — or rolls back — as ONE unit
        (REV-0006-F-001 / INV-050): a dispatch reject then rolls the caller's
        fresh intent insert+approve back too, never stranding it APPROVED with
        no order (matching the in-memory store). When ``cur`` is ``None`` (the
        ``create_order_for_sell_intent`` path) each write opens its own tx.

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
                with nullcontext(cur) if cur is not None else self._tx() as c:
                    if plan.reject_event is not None:
                        self._insert_event(
                            c,
                            plan.reject_event.event_type,
                            **plan.reject_event.as_kwargs(),
                        )
                    if plan.expire_intent is not None:
                        self._update_sell_intent(c, plan.expire_intent)
                        assert plan.expire_event is not None
                        self._insert_event(
                            c,
                            plan.expire_event.event_type,
                            **plan.expire_event.as_kwargs(),
                        )
            assert plan.error is not None
            raise plan.error
        assert plan.order is not None  # non-REJECT dispatch sets the order
        order = plan.order
        now = utcnow()
        intent.status = SellIntentStatus.ORDERED
        intent.order_id = order.id
        intent.ordered_at = now
        intent.updated_at = now
        with nullcontext(cur) if cur is not None else self._tx() as c:
            self._insert_order(c, order)
            self._update_sell_intent(c, intent)
            for event in plan.events:
                self._insert_event(c, event.event_type, **event.as_kwargs())
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
            # WO-0036 R2 exclusive driver: an envelope-backed intent is
            # dispatched ONLY by the envelope executor (staged, budgeted,
            # write-time re-validated) — the legacy single-order handoff on
            # top of it would be a second exit for the same mandate.
            live_env = self._live_envelope_for_intent_locked(intent_id)
            if live_env is not None:
                raise SellIntentTransitionError(
                    f"sell intent {intent_id} is bound to live execution "
                    f"envelope {live_env}; the envelope drives its dispatch "
                    "(WO-0036 R2 link)"
                )
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
                # WO-0007b: project status on this idempotent read-return too, so
                # EVERY order-returning path derives status from the event log.
                return self._project_order_locked(self._order(order_row))
            return self._dispatch_order_for_sell_intent_locked(
                intent, order_type=order_type, limit_price=limit_price
            )

    async def open_protection_exit(
        self,
        *,
        symbol: str,
        target_quantity: int,
        floor_price: Optional[float] = None,
        observed_price: Optional[float] = None,
        average_price: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> Optional[Order]:
        key = normalize_symbol(symbol)
        bad = whole_count_reason(target_quantity)
        if bad is not None or target_quantity <= 0:
            raise InvalidOrderError(
                f"protection exit for {key} needs a positive whole "
                f"target_quantity (got {target_quantity!r})"
            )
        async with self._lock:
            # Single-flight (atomic dedup): an exit already in flight for this
            # symbol short-circuits — nothing new is written, mirroring
            # create_sell_intent's active-check. Checked BEFORE the kill gate so an
            # exit created while ACTIVE (before the kill) still returns idempotently.
            active = self._active_sell_intent_locked(key)
            if active is not None:
                if active.order_id is None:
                    return None
                order_row = self._read_one(
                    "SELECT * FROM orders WHERE id = ?", (active.order_id,)
                )
                if order_row is None:
                    return None
                return self._project_order_locked(self._order(order_row))
            # ENG-001 / INV-060 (REV-0019-F-001): the kill switch blocks NEW
            # autonomous order intent. The whole create+approve+dispatch+audit
            # below shares ONE _tx() with no await after this check, so a kill
            # landing during the tick's earlier awaits is caught here (nothing
            # written) and one landing later cannot interleave — the decomposed
            # sequence's post-create HALTED window is closed. A dispatch reject
            # (oversell) rolls the whole transaction back (matching the in-memory
            # store), so no protection_triggered event ever describes a
            # non-existent exit.
            session = self._ensure_current_session_locked()
            if self._current_trading_state_locked(session.id) is TradingState.HALTED:
                raise ProtectionHaltedError(
                    f"autonomous protection exit for {key} refused: trading "
                    "halted (kill switch engaged)"
                )
            if session_id is None:
                session_id = session.id
            with self._tx() as cur:
                intent = self._insert_sell_intent_locked(
                    cur,
                    symbol=key,
                    reason=SellReason.PROTECTION_FLOOR,
                    target_quantity=target_quantity,
                    floor_price=floor_price,
                    observed_price=observed_price,
                    session_id=session_id,
                )
                self._transition_sell_intent_locked(
                    cur, intent, SellIntentStatus.APPROVED
                )
                order = self._dispatch_order_for_sell_intent_locked(
                    intent, order_type=OrderType.MARKET, limit_price=None, cur=cur
                )
                self._insert_event(
                    cur,
                    "protection_triggered",
                    message=(
                        f"protection floor breached for {key}: last "
                        f"{observed_price} <= floor {floor_price}; exiting "
                        f"{target_quantity} shares"
                    ),
                    symbol=key,
                    order_id=order.id,
                    payload={
                        "average_price": average_price,
                        "floor_price": floor_price,
                        "observed_price": observed_price,
                        "quantity": target_quantity,
                    },
                    session_id=session_id,
                    correlation_id=intent.id,
                )
            return order

    async def flatten_position(
        self,
        symbol: str,
        *,
        session_id: Optional[str] = None,
        actor: str = COMMAND_ACTOR_SYSTEM,
    ) -> FlattenResult:
        key = normalize_symbol(symbol)
        async with self._lock:
            # Every read this decision depends on happens under this ONE lock
            # hold, continuously through to the writes below — a concurrent
            # protection tick's own create_sell_intent call cannot interleave
            # anywhere in between (X-001): the continuous lock hold is what makes
            # this safe against the CONCURRENCY race; never a double-sell (this is
            # verified for real races). Independently, the SUPERSEDE_AND_CREATE
            # branch below commits its supersede + create + approve + dispatch
            # writes as ONE SQL transaction (REV-0006-F-001 / INV-050), so a hard
            # CRASH — or a dispatch reject — anywhere inside it rolls the whole
            # thing back rather than durably stranding the fresh MANUAL_FLATTEN
            # intent APPROVED with no order (matching the in-memory store's single
            # _atomic() block). The self-heal path in plan_flatten_position
            # (app/store/core.py) still covers a MANUAL_FLATTEN intent stranded by
            # any OTHER route — it treats one found here as "existing" only when
            # already ORDERED, and supersedes a stranded pending/approved one on
            # the next flatten call, exactly like a stranded PROTECTION_FLOOR
            # intent (docs/INVARIANTS.md INV-038).
            position = self._position_locked(key)
            active = self._active_sell_intent_locked(key)
            active_order = None
            if active is not None and active.order_id is not None:
                order_row = self._read_one(
                    "SELECT * FROM orders WHERE id = ?", (active.order_id,)
                )
                active_order = self._order(order_row) if order_row is not None else None
            # WO-0036 R2 (Codex PR#8 #4): an envelope-backed exit's live child
            # is invisible on the intent (order_id=None) — read it via the
            # envelope linkage under this SAME lock hold so the planner can
            # defer to it instead of double-booking a second SELL.
            envelope_child, envelope_intent = self._live_envelope_exit_locked(key)

            # ADR-003 / wave 3e: current session's §8 FSM + whether an
            # emergency-reduce override is active for this symbol, read under the
            # same continuous lock hold as the decision above.
            current_session = self._ensure_current_session_locked()
            trading_state = self._current_trading_state_locked(current_session.id)
            override_active = key in self._active_overrides_locked(current_session.id)

            plan = plan_flatten_position(
                position=position,
                active_intent=active,
                active_order=active_order,
                trading_state=trading_state,
                override_active=override_active,
                actor=actor,
                envelope_child=envelope_child,
                envelope_intent=envelope_intent,
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
                # ADR-010 §4 / D-2: even with nothing to exit, a stale envelope
                # must never outlive the human's direct backstop.
                with self._tx() as cur:
                    self._cancel_symbol_envelopes_locked(
                        cur, key, actor=actor, reason="manual_flatten_preemption"
                    )
                return FlattenResult(FLATTEN_FLAT)
            if plan.outcome == _PLAN_FLATTEN_EXISTING:
                # Provenance for a deferral to a live PROTECTION_FLOOR exit
                # (INV-036): one audit row recording the human flatten was received
                # and deferred, no state mutated — in this same lock hold.
                if plan.deferral_event is not None:
                    with self._tx() as cur:
                        self._insert_event(
                            cur,
                            plan.deferral_event.event_type,
                            **plan.deferral_event.as_kwargs(),
                        )
                return FlattenResult(
                    FLATTEN_EXISTING,
                    intent=plan.existing_intent,
                    order=plan.existing_order,
                    # A deferral to a live protection exit (REV-0002 F-001) — key
                    # on the deferral event, NOT the outcome: the idempotent
                    # own-manual-flatten re-return is ALSO FLATTEN_EXISTING but has
                    # no deferral_event, so it correctly reads deferred=False.
                    deferred=plan.deferral_event is not None,
                )

            assert plan.outcome == FLATTEN_SUPERSEDE_AND_CREATE
            if session_id is None:
                session_id = self._ensure_current_session_locked().id

            # REV-0006-F-001 / INV-050: the whole supersede + create + approve +
            # dispatch sequence commits as ONE transaction. A hard crash — or a
            # dispatch reject — anywhere inside it rolls the entire thing back,
            # so a MANUAL_FLATTEN intent is never durably stranded APPROVED with
            # no order (which previously also stood the autonomous protection
            # tick down on a non-existent exit). This matches the in-memory
            # store's single ``_atomic()`` block; the continuous lock hold
            # (X-001) still provides the concurrency guarantee independently.
            superseded = False
            with self._tx() as cur:
                # ADR-010 §4: envelope preemption FIRST, same transaction —
                # the preemption events sequence before the flatten's own
                # supersede/create writes (asserted by WO-0017 tests).
                self._cancel_symbol_envelopes_locked(
                    cur, key, actor=actor, reason="manual_flatten_preemption"
                )
                if plan.supersede_order_cancel is not None:
                    # A supersede-cancel implies the stranded active_order exists
                    # and the planner produced its cancel audit event (narrows both).
                    assert (
                        active_order is not None
                        and plan.supersede_cancel_event is not None
                    )
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
                    # WO-0007a Stage 3: co-write the routine CANCELED
                    # ExecutionEvent (SAME shared helper + dedupe_key format as
                    # transition_order's ->CANCELED) in the SAME transaction.
                    # `active_order` is the PRE-transition order (its `.status`
                    # is still CREATED — `plan.supersede_order_cancel` is a
                    # separate deep copy already mutated to CANCELED by the
                    # planner), exactly what the helper needs.
                    exec_event = execution_event_for_routine_transition(
                        active_order,
                        OrderStatus.CANCELED,
                        active_order.filled_quantity,
                    )
                    if exec_event is not None:
                        self._insert_execution_event(cur, exec_event)
                    superseded = True
                if plan.supersede_intent_expire is not None:
                    assert plan.supersede_expire_event is not None
                    # WO-0036 R2: the envelope preemption above may have ALREADY
                    # expired this intent (terminal propagation). Re-read the
                    # live row and only apply the planner's expiry if it is
                    # still pending/approved — the event log must carry exactly
                    # ONE terminal transition per intent, never two.
                    live_row = cur.execute(
                        "SELECT status FROM sell_intents WHERE id = ?",
                        (plan.supersede_intent_expire.id,),
                    ).fetchone()
                    if live_row is not None and live_row["status"] in (
                        SellIntentStatus.PENDING.value,
                        SellIntentStatus.APPROVED.value,
                    ):
                        self._update_sell_intent(cur, plan.supersede_intent_expire)
                        self._insert_event(
                            cur,
                            plan.supersede_expire_event.event_type,
                            **plan.supersede_expire_event.as_kwargs(),
                        )
                    superseded = True

                intent = self._insert_sell_intent_locked(
                    cur,
                    symbol=key,
                    reason=SellReason.MANUAL_FLATTEN,
                    target_quantity=plan.target_quantity,
                    session_id=session_id,
                    actor=actor,
                )
                self._transition_sell_intent_locked(
                    cur, intent, SellIntentStatus.APPROVED
                )
                # Dispatch joins THIS transaction (cur=cur) so a reject rolls the
                # fresh intent's insert+approve back too — no stranded partial.
                order = self._dispatch_order_for_sell_intent_locked(
                    intent, order_type=OrderType.MARKET, limit_price=None, cur=cur
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
        fills = [
            self._fill(r) for r in self._read_all("SELECT * FROM fills ORDER BY rowid")
        ]
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
                assert plan.error is not None
                raise plan.error

            # CREATE — one transaction covers the order insert, the candidate
            # ORDERED transition, and both audit events (the atomic "candidate
            # approval + order creation + audit event" group from docs/02).
            assert plan.order is not None  # APPROVED create path sets it
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
            if order is not None:
                # WO-0013 (F-001): gate on event-log truth, not the co-written column
                # (mirror of the in-memory store; see its claim_order_for_submission).
                # _project_order_locked runs its own indexed per-order event query.
                projected = self._project_order_locked(order)
                # Defense-in-depth (REV-0002 adversarial-verify): pin the co-write
                # invariant in code (mirror of the in-memory store). A raw column past
                # CREATED that still projects CREATED means the log is missing this
                # order's lifecycle events; claiming it would blind-resubmit a possibly-
                # live order. Unreachable today; fail loud rather than re-submit.
                assert not (
                    order.status is not OrderStatus.CREATED
                    and projected.status is OrderStatus.CREATED
                ), (
                    f"claim_order_for_submission: order {order_id} column status "
                    f"{order.status.value!r} projects CREATED (no lifecycle events) — "
                    "co-write invariant violated; refusing to avoid a blind re-submit"
                )
                order = projected
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
                sell_reason = (
                    SellReason(si_row["reason"]) if si_row is not None else None
                )
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
                # CLAIM_CLAIMED guarantees a claimable order + its plan artifacts
                # (narrows the Optionals mypy can't infer from the outcome).
                assert (
                    order is not None
                    and plan.order is not None
                    and plan.event is not None
                )
                updated = plan.order
                with self._tx() as cur:
                    cur.execute(
                        "UPDATE orders SET status=?, updated_at=? WHERE id=?",
                        (updated.status.value, _dt(updated.updated_at), updated.id),
                    )
                    self._insert_event(
                        cur, plan.event.event_type, **plan.event.as_kwargs()
                    )
                    # WO-0007a Stage 1: co-write a SUBMIT_PENDING ExecutionEvent
                    # in the SAME transaction as the order-row + audit-event
                    # write. `occurrence` = count of PRIOR SUBMIT_PENDING events
                    # for this order_id, read inside this same transaction
                    # (which the store's `self._lock` already serializes
                    # against any concurrent claim on this order), so repeats
                    # via the claim/release cycle get gapless, uniquely-keyed
                    # events.
                    occurrence_row = cur.execute(
                        "SELECT COUNT(*) AS n FROM execution_events "
                        "WHERE order_id = ? AND event_type = ?",
                        (order_id, ExecutionEventType.SUBMIT_PENDING.value),
                    ).fetchone()
                    occurrence = occurrence_row["n"] if occurrence_row else 0
                    exec_event = execution_event_for_routine_transition(
                        order, OrderStatus.SUBMITTING, None, occurrence=occurrence
                    )
                    if exec_event is not None:
                        self._insert_execution_event(cur, exec_event)
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
                rows = self._read_all("SELECT * FROM submit_recoveries ORDER BY rowid")
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
                raise UnknownEntityError(f"submit recovery {recovery_id} not found")
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
            return [self._project_order_locked(self._order(r)) for r in rows]

    def _project_order_locked(self, order: Order) -> Order:
        """Return ``order`` with ``status`` derived from the ExecutionEvent log
        (WO-0007b read-flip): folds the order's lifecycle events via
        project_order_status, exactly as ``_position_locked`` folds FILL events for
        position. The ``orders.status`` column is a co-written read-model (WO-0007a
        co-write + init heal); a stale column can never surface as an order's status.

        ``filled_quantity`` stays column-sourced (co-written, monotonic-bound-checked);
        it is not universally the FILL-event sum, so event-sourcing it is a separate
        follow-up — see the InMemoryStateStore counterpart + design-decision.md."""

        rows = self._read_all(
            "SELECT * FROM execution_events WHERE order_id = ? ORDER BY sequence",
            (order.id,),
        )
        events = [self._execution_event(r) for r in rows]
        proj = project_order_status(events, order.id, order.quantity)
        projected = order.model_copy(deep=True)
        projected.status = proj.status
        return projected

    async def get_order(self, order_id: str) -> Optional[Order]:
        async with self._lock:
            row = self._read_one("SELECT * FROM orders WHERE id = ?", (order_id,))
            return self._project_order_locked(self._order(row)) if row else None

    async def transition_order(
        self,
        order_id: str,
        new_status: OrderStatus,
        *,
        filled_quantity: Optional[int] = None,
        broker_order_id: Optional[str] = None,
        actor: str = COMMAND_ACTOR_SYSTEM,
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
                actor=actor,
            )
            if plan.outcome == ORDER_TRANSITION_REJECT:
                assert plan.error is not None
                raise plan.error
            if plan.outcome == ORDER_TRANSITION_NOOP:
                return order
            # APPLY: plan.order + plan.event are set for this outcome (narrows the
            # Optional plan fields for the rest of the method; mypy can't infer it
            # from the outcome check).
            assert plan.order is not None and plan.event is not None
            # WO-0007a Stage 2: also co-write the routine order-status
            # ExecutionEvent (if any) in the SAME transaction, mirroring
            # Stage 1's claim-path pattern. `order` here is still the
            # PRE-transition order (fetched above, before plan.order), which is
            # exactly what `execution_event_for_routine_transition` needs — both
            # for the TIMEOUT_QUARANTINE defense-in-depth guard and to tell a
            # first entry into PARTIALLY_FILLED apart from the same-status
            # fill-progress self-loop.
            #
            # `plan.event.event_type` is plan_transition_order's own signal for
            # which branch it took: "order_transition" (status_changed) vs
            # "order_fill_progress" (same status, filled_quantity and/or
            # broker_order_id changed) — using it here keeps this call in exact
            # lockstep with the planner's branching instead of re-deriving it.
            updated = plan.order
            exec_event = None
            if plan.event.event_type == "order_transition":
                # WO-0007b: the SUBMITTING -> CREATED release is occurrence-keyed
                # like the claim, so a repeated claim/release cycle stays gapless.
                # Read the prior SUBMIT_RELEASED count under self._lock (held here),
                # before the write tx — no concurrent writer can interleave.
                occurrence = None
                if updated.status is OrderStatus.CREATED:
                    crow = self._read_one(
                        "SELECT COUNT(*) AS n FROM execution_events "
                        "WHERE order_id = ? AND event_type = ?",
                        (order_id, ExecutionEventType.SUBMIT_RELEASED.value),
                    )
                    occurrence = crow["n"] if crow else 0
                exec_event = execution_event_for_routine_transition(
                    order,
                    updated.status,
                    updated.filled_quantity,
                    occurrence=occurrence,
                )
            elif (
                plan.event.event_type == "order_fill_progress"
                and order.status is OrderStatus.PARTIALLY_FILLED
                and updated.status is OrderStatus.PARTIALLY_FILLED
                and updated.filled_quantity != order.filled_quantity
            ):
                exec_event = execution_event_for_routine_transition(
                    order, updated.status, updated.filled_quantity
                )
            # APPLY — persist the fully-updated order + its one audit row
            # (order_transition or order_fill_progress), plus the ExecutionEvent
            # (if any), in one transaction.
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
                if exec_event is not None:
                    self._insert_execution_event(cur, exec_event)
                # WO-0036 R2: a venue-terminal envelope child may be its
                # mandate's LAST live obligation — complete the intent release
                # in the same transaction (no-op for non-envelope orders).
                self._release_intent_for_terminal_child_locked(cur, updated)
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
            assert plan.error is not None
            raise plan.error
        if plan.outcome == ORDER_TRANSITION_NOOP:
            return order
        assert (
            plan.order is not None
            and plan.audit_event is not None
            and plan.execution_event is not None
        )
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
            # WO-0036 R2: same child-terminal release as transition_order —
            # the evented paths (quarantine resolution, reconcile) are the
            # other door a child takes to a venue terminal.
            self._release_intent_for_terminal_child_locked(cur, updated)
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
            order_rows = self._read_all(
                "SELECT * FROM orders WHERE id IN (%s)" % ",".join("?" * len(ids)),
                tuple(sorted(ids)),
            )
            return sorted(
                (self._project_order_locked(self._order(r)) for r in order_rows),
                key=lambda o: o.id,
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
            order_row = self._read_one("SELECT * FROM orders WHERE id = ?", (order_id,))
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
            # concurrency-0 ROOT form (WO-0035): overfill judged against the
            # position EXCLUDING this fill's own event — the record-first
            # envelope bridge may have already folded THIS fill under the same
            # canonical dedupe identity. Self-derived here (no caller-supplied
            # prior_position), so no call site can reintroduce the phantom
            # fill_overfill_quarantined by forgetting a parameter. NULL-safe:
            # dedupe_key IS NULL rows must stay in the fold.
            self_key = (
                f"fill:{order_id}:{source_fill_id}"
                if source_fill_id is not None
                else ""
            )
            pos_rows = self._read_all(
                "SELECT * FROM execution_events "
                "WHERE symbol = ? AND event_type = 'fill' "
                "AND (dedupe_key IS NULL OR dedupe_key != ?) ORDER BY sequence",
                (key, self_key),
            )
            overfill_position = project_symbol_position(
                [self._execution_event(r) for r in pos_rows], key
            ).quantity
            plan = plan_append_fill(
                order_id=order_id,
                order=order,
                prior_filled=prior_filled,
                current_quantity=overfill_position,
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
                assert plan.error is not None
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
            assert plan.fill is not None  # FILL_APPEND builds the fill row
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
        return project_symbol_position([self._execution_event(r) for r in rows], symbol)

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
                quantity, price, order_id, envelope_id, primary_id, spawn_id,
                session_id, correlation_id, payload)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                stored.envelope_id,
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
        sql = "SELECT * FROM execution_events WHERE sequence > ? ORDER BY sequence"
        params: tuple = (after_sequence,)
        if limit is not None:
            sql += " LIMIT ?"
            params = (after_sequence, limit)
        async with self._lock:
            rows = self._read_all(sql, params)
            return [self._execution_event(r) for r in rows]

    async def get_max_execution_sequence(self) -> int:
        async with self._lock:
            row = self._read_one("SELECT MAX(sequence) AS m FROM execution_events", ())
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
            row = self._read_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
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
            session.id,
            prior_control=prior_control,
            kill_switch=kill_switch,
            buys_paused=buys_paused,
            reason=reason,
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
            cur,
            audit_event_type,
            message=audit_message,
            session_id=session.id,
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
        self,
        cur: sqlite3.Cursor,
        session: SessionRecord,
        *,
        to: TradingState,
        reason: str,
    ) -> None:
        """Co-write a RECONCILE-driver TradingState change (wave 4f / R2): the
        composed effective ``trading_state`` column + a ``driver="reconcile"``
        ``TRADING_STATE_CHANGED`` ExecutionEvent — WITHOUT touching the booleans."""

        tsc_events = self._trading_state_events_locked()
        prior_reconcile = reconcile_trading_state(tsc_events, session.id)
        exec_event = reconcile_trading_state_event(
            session.id,
            prior_reconcile=prior_reconcile,
            to=to,
            reason=reason,
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
            cur,
            "trading_state_reconcile",
            message=f"reconcile-driven trading state -> {to.value} ({reason})",
            session_id=session.id,
            payload={"to": to.value, "reason": reason},
        )
        self._insert_execution_event(cur, exec_event)

    async def set_kill_switch(
        self, engaged: bool, *, actor: str = COMMAND_ACTOR_SYSTEM
    ) -> SessionRecord:
        require_bool(engaged, field="engaged")
        async with self._lock:
            session = self._ensure_current_session_locked()
            with self._tx() as cur:
                self._apply_control_change_locked(
                    cur,
                    session,
                    kill_switch=engaged,
                    buys_paused=session.buys_paused,
                    audit_event_type="kill_switch_engaged"
                    if engaged
                    else "kill_switch_released",
                    audit_message=f"kill switch {'engaged' if engaged else 'released'}",
                    audit_payload={"kill_switch": engaged, "actor": actor},
                    reason="kill_switch",
                )
                if engaged:
                    # ADR-010 §4: the kill freezes every ACTIVE envelope in
                    # the SAME transaction as the control change. Release
                    # never auto-resumes (FROZEN -> ACTIVE is an explicit
                    # human action, itself refused while HALTED).
                    rows = cur.execute(
                        "SELECT * FROM execution_envelopes WHERE status = ?",
                        (EnvelopeStatus.ACTIVE.value,),
                    ).fetchall()
                    frozen: list[str] = []
                    for row in rows:
                        env = self._envelope(row)
                        plan = plan_envelope_transition(
                            env,
                            EnvelopeStatus.FROZEN,
                            actor=actor,
                            reason="kill_switch",
                        )
                        assert plan.outcome == ENVELOPE_TRANSITION_APPLY
                        self._apply_envelope_transition_locked(cur, plan)
                        frozen.append(env.id)
                    # WO-0024: the kill blocks new order intent (INV-060) — a
                    # staged CREATED order IS pending order intent, so it dies
                    # in the same transaction as the freeze.
                    self._cancel_staged_envelope_orders_locked(cur, frozen, actor=actor)
            return session

    async def set_buys_paused(
        self, paused: bool, *, actor: str = COMMAND_ACTOR_SYSTEM
    ) -> SessionRecord:
        require_bool(paused, field="paused")
        async with self._lock:
            session = self._ensure_current_session_locked()
            with self._tx() as cur:
                self._apply_control_change_locked(
                    cur,
                    session,
                    kill_switch=session.kill_switch,
                    buys_paused=paused,
                    audit_event_type="buys_paused" if paused else "buys_resumed",
                    audit_message=f"buys {'paused' if paused else 'resumed'}",
                    audit_payload={"buys_paused": paused, "actor": actor},
                    reason="buys_paused",
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
                self._apply_reconcile_state_locked(cur, session, to=to, reason=reason)
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
            session.id,
            symbol,
            actor=actor,
            reason=reason,
            resolved=resolved,
        )
        with self._tx() as cur:
            self._insert_execution_event(cur, event)
            self._insert_event(
                cur,
                "emergency_reduce_override_resolved"
                if resolved
                else "emergency_reduce_override_granted",
                message=(
                    f"emergency reduce override {'resolved' if resolved else 'granted'} "
                    f"for {symbol} by {actor}"
                ),
                symbol=symbol,
                session_id=session.id,
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
            if (
                self._current_trading_state_locked(session.id)
                is not TradingState.HALTED
            ):
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
        self,
        session_id: Optional[str] = None,
        *,
        actor: str = COMMAND_ACTOR_SYSTEM,
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
            # PENDING/APPROVED sell intents expire at close, like candidates —
            # EXCEPT one backed by a LIVE (ACTIVE/FROZEN) envelope (WO-0036
            # R2): its mandate keeps working the exit across the boundary, so
            # expiring it would orphan the envelope (the treadmill audit's
            # P0). Spared intents are counted into the close event's payload.
            open_sell_intents = [
                self._sell_intent(r)
                for r in self._read_all(
                    "SELECT * FROM sell_intents WHERE session_id = ? "
                    "AND status IN (?, ?) AND NOT EXISTS ("
                    "  SELECT 1 FROM execution_envelopes e "
                    "  WHERE e.sell_intent_id = sell_intents.id "
                    "  AND e.status IN (?, ?)"
                    ") ORDER BY rowid",
                    (
                        session.id,
                        SellIntentStatus.PENDING.value,
                        SellIntentStatus.APPROVED.value,
                        EnvelopeStatus.ACTIVE.value,
                        EnvelopeStatus.FROZEN.value,
                    ),
                )
            ]
            spared_row = self._read_one(
                "SELECT COUNT(*) AS n FROM sell_intents WHERE session_id = ? "
                "AND status IN (?, ?) AND EXISTS ("
                "  SELECT 1 FROM execution_envelopes e "
                "  WHERE e.sell_intent_id = sell_intents.id "
                "  AND e.status IN (?, ?)"
                ")",
                (
                    session.id,
                    SellIntentStatus.PENDING.value,
                    SellIntentStatus.APPROVED.value,
                    EnvelopeStatus.ACTIVE.value,
                    EnvelopeStatus.FROZEN.value,
                ),
            )
            spared_sell_intents = int(spared_row["n"]) if spared_row else 0
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
                actor=actor,
                spared_sell_intents=spared_sell_intents,
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
                    # WO-0007a Stage 3: co-write the routine CANCELED
                    # ExecutionEvent (SAME shared helper + dedupe_key format as
                    # transition_order's ->CANCELED) in the SAME transaction as
                    # the order-row + audit-event write. `order` here is still
                    # the PRE-transition object read above (status CREATED) —
                    # the UPDATE above only touched the DB row, not this
                    # in-memory object — exactly what the helper needs.
                    exec_event = execution_event_for_routine_transition(
                        order, OrderStatus.CANCELED, order.filled_quantity
                    )
                    if exec_event is not None:
                        self._insert_execution_event(cur, exec_event)
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

    async def list_position_snapshots(self, session_id: str) -> list[PositionSnapshot]:
        async with self._lock:
            rows = self._read_all(
                "SELECT * FROM position_snapshots WHERE session_id = ? ORDER BY rowid",
                (session_id,),
            )
            return [self._snapshot(r) for r in rows]
