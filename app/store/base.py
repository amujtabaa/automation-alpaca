"""The ``StateStore`` interface — the only way callers touch persisted truth.

Two implementations exist: :class:`~app.store.memory.InMemoryStateStore` (tests,
IO-free) and :class:`~app.store.sqlite.SqliteStateStore` (the running app).
Swapping SQLite for Postgres later touches only the implementation, not these
signatures or any caller.

Key structural guarantees the interface is shaped to enforce:

* Candidate transitions accept only :class:`CandidateStatus`; order transitions
  only :class:`OrderStatus`. There is no method to put a broker-execution state
  on a candidate.
* Fills are *append-only*: there is exactly one fill-writing method
  (:meth:`StateStore.append_fill`) and no update/delete for fills.
* Position is read-only and derived — no ``set_position`` exists.
* Every mutating method that writes more than one row is atomic (see each
  implementation) and writes an audit/event row.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Literal, Optional

from app.models import (
    RECOVERY_UNRESOLVED,
    Candidate,
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
    SubmitRecoveryRecord,
    WatchlistSymbol,
)


# A bounded ticker domain: a leading letter then up to nine more of
# letters/digits/dot/dash (covers e.g. AAPL, BRK.B, BF-B). Keeps overly long,
# unicode, whitespace, path-like, or SQL-looking strings out of durable trading
# data (DATA-2). SQL is already parameterized; this is a data-quality/blast-
# radius guard, not an injection fix.
_SYMBOL_RE = re.compile(r"[A-Z][A-Z0-9.\-]{0,9}")


def normalize_symbol(symbol: str) -> str:
    """Canonical symbol form used as the watchlist/position key.

    Normalization lives in the store so every caller (and both
    implementations) keys symbols identically — the UI never has to. Rejects a
    blank or out-of-domain symbol with ``ValueError`` (route handlers surface it
    as 422).
    """

    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("symbol must be a non-empty string")
    if not _SYMBOL_RE.fullmatch(normalized):
        raise ValueError(
            f"symbol {symbol!r} is not a valid ticker (expected 1-10 chars: a "
            f"leading letter then letters/digits/'.'/'-')"
        )
    return normalized


class StoreError(Exception):
    """Base class for StateStore errors."""


class UnknownEntityError(StoreError):
    """Referenced entity (candidate, order, ...) does not exist."""


class CandidateTransitionError(StoreError):
    """An illegal candidate lifecycle transition was attempted.

    e.g. approving a candidate that is already ``rejected``/``expired`` without
    an explicit return to ``pending`` (beta provides no such return).
    """


class OrderTransitionError(StoreError):
    """An illegal order lifecycle transition was attempted."""


class SellIntentTransitionError(StoreError):
    """An illegal sell-intent lifecycle transition was attempted (Phase 7) —
    e.g. ordering an intent that is not ``approved``, or reviving a terminal
    (``rejected``/``expired``/``ordered``) one."""


class RecoveryTransitionError(StoreError):
    """An illegal submit-recovery ``cleanup_status`` transition was attempted
    (AIR-004): an unknown status value, or a disallowed move such as reopening a
    terminal (``resolved_canceled``/``needs_review``) record back to
    ``unresolved``. The record and its audit trail are left unchanged.
    """


class InvalidStatusError(StoreError):
    """A status argument was not a proper enum member (AIR-009).

    ``list_candidates(status=)``, ``transition_candidate`` and
    ``transition_order`` require a real ``CandidateStatus`` / ``OrderStatus``
    instance. A raw string (``"pending"``/``"approved"``) — which a ``str``-enum
    would otherwise *silently* match in SQLite while ``InMemoryStateStore``
    diverged (empty result / ``AttributeError``) — or a ``bool``/``None`` where a
    status is required is rejected here, so both stores accept and reject
    identically with no mutation.
    """


class InvalidControlValueError(StoreError):
    """A control/flag setter received a non-``bool`` value (AIR-005).

    ``set_kill_switch``/``set_buys_paused``/``set_watchlist_armed`` and
    ``create_watchlist(armed=)`` take a real ``bool`` only — a string like
    ``"false"`` or an int like ``0`` is rejected here rather than silently
    coerced (memory would store the truthy string, SQLite would coerce to
    ``True``, so ``{"engaged": "false"}`` meant to *disengage* would engage the
    switch — an emergency-stop inversion).
    """


class InvalidFillError(StoreError):
    """A fill was rejected at the store boundary for a bad value or a mismatch
    against its order (D-010).

    Covers: non-positive ``quantity``/``price``; a fill whose symbol or side
    does not match the referenced order; and cumulative filled quantity for an
    order exceeding the order's quantity. A *missing* order is reported as
    :class:`UnknownEntityError`, and a sell that would go short remains
    :class:`~app.position.NegativePositionError`; this error is specifically
    "the fill itself is malformed or inconsistent with its order."
    """


class InvalidOrderError(StoreError):
    """An order operation was rejected for invalid inputs (D-010).

    Raised by ``create_order_for_candidate`` when the order's symbol does not
    match its candidate; by ``create_order_for_sell_intent``/
    ``flatten_position`` for an oversell, a non-positive/fractional quantity,
    an unpriceable LIMIT, or a MARKET order carrying a limit price (each such
    rejection also self-heals the sell-intent ``approved -> expired``, X-002 —
    see ``docs/INVARIANTS.md`` INV-033); and by ``transition_order`` when
    ``filled_quantity`` is out of range (`0 <= filled_quantity <=
    order.quantity`) or would move backward (no broker-correction path exists
    in beta). A *missing* candidate/order is reported as
    :class:`UnknownEntityError`.
    """


class SessionAlreadyClosedError(StoreError):
    """``close_session`` was called on a session that is already closed.

    Closing is deliberately not idempotent (unlike candidate approve/reject):
    re-closing would re-snapshot a position that may have changed, so the second
    call is rejected explicitly.
    """


class OrderIntentBlockedError(StoreError):
    """New order intent was blocked by a safety control (Rule 8).

    Raised by ``create_order_for_candidate`` when the candidate's session has the
    kill switch engaged (blocks *all* new order intent) or buys paused (blocks
    new BUY intent — beta orders are long-only buys). The flag is persisted state
    the backend owns; enforcing it here (not only in the UI) means every order-
    intent producer — the approve route now, a future auto-buy engine — is gated,
    and the block is recorded as an audit event. Distinct from
    :class:`RiskLimitBlockedError` (Phase 6 CAPI): this is a binary on/off
    control-flag check with no numeric limits involved.
    """


class RiskLimitBlockedError(StoreError):
    """New order intent was blocked by a Phase 6 CAPI risk limit (D-016).

    Raised by ``create_order_for_candidate`` when the proposed order's symbol
    isn't on the trading allowlist, or would exceed the configured max
    shares/notional per order or max total exposure — computed from local
    state only (folded positions + non-terminal orders' remaining notional; see
    ``app.policy.risk_limit_reason``), never a live broker/market-data
    call. Beta gates-and-rejects: a breach blocks the order outright, it is
    never silently resized to fit. Distinct from :class:`OrderIntentBlockedError`
    (Rule 8's binary kill-switch/pause-buys control, no numeric limits).
    """


class SessionClosedError(StoreError):
    """A new candidate was attempted against a *closed* session.

    Closing a session ends the trading day (D-009): ``create_candidate`` refuses
    to attach a fresh candidate to a closed session, since it would sit outside
    the point-in-time review snapshot captured at close. This guard is on
    candidate *creation* only. It deliberately does **not** block order dispatch,
    fill append, or order transitions for an order that already exists — those
    must keep working after close so an in-flight order is tracked to a terminal
    state (D-011). In practice dispatch can't happen in a closed session anyway,
    because close expires every open (pending/approved) candidate first. Distinct
    from :class:`SessionAlreadyClosedError`, which is specifically about
    re-closing.
    """


@dataclass(frozen=True)
class FillAppendResult:
    """Outcome of :meth:`StateStore.append_fill`.

    ``status`` is ``"appended"`` when a new fill row was written, or
    ``"duplicate"`` when a fill with the same ``source_fill_id`` already existed
    (no row written, position untouched, a duplicate-ignored audit event
    recorded). A sell that would go negative does not return here — it raises
    :class:`~app.position.NegativePositionError`.
    """

    status: Literal["appended", "duplicate"]
    fill: Optional[Fill]
    event: Event


@dataclass(frozen=True)
class RiskLimits:
    """The Phase 6 CAPI limits for one :meth:`StateStore.create_order_for_candidate`
    call (D-016). Bundled into one object — rather than four separate keyword
    arguments threaded individually through the abstract method, both store
    implementations, the shared planner, and the route (which needs the same
    values twice: the pre-check and the authoritative call) — so a future
    limit type is one field added in one place, not a signature edited in five.

    Every field is independently optional: ``None`` means "not enforced." The
    zero-argument default, ``RiskLimits()``, is fully unenforced — this is what
    keeps ``create_order_for_candidate``'s ~20 pre-existing test call sites
    (written before Phase 6, none of which pass a ``risk_limits`` argument)
    behaviorally unchanged. Production code (the approve route) always builds
    one from ``Settings``, which rejects a non-finite/non-positive numeric
    limit at load — see ``app.config.load_settings``.
    """

    max_shares_per_order: Optional[float] = None
    max_notional_per_order: Optional[float] = None
    max_total_exposure: Optional[float] = None
    # Empty/None both mean "no restriction beyond the watchlist" — a
    # genuinely meaningful empty state, unlike the three numeric limits above.
    allowlist: Optional[frozenset[str]] = None


# SubmissionClaim.outcome values (D-017). The monitoring loop dispatches on these:
CLAIM_CLAIMED = "claimed"   # order transitioned CREATED -> SUBMITTING; submit it
CLAIM_BLOCKED = "blocked"   # a control blocks submission; no state change, reason set
CLAIM_SKIPPED = "skipped"   # order was no longer CREATED (already claimed/cancelled)


@dataclass(frozen=True)
class SubmissionClaim:
    """Outcome of :meth:`StateStore.claim_order_for_submission` (D-017).

    A ``claimed`` result means the order was atomically moved ``CREATED ->
    SUBMITTING`` under one lock hold *after* re-checking every control, so the
    monitoring loop may now call the broker knowing no kill-switch/pause/close
    flip could have slipped in undetected. ``blocked`` means a control held it
    (``reason`` is set; no state changed). ``skipped`` means it was no longer
    ``CREATED`` when the lock was acquired (a session close cancelled it, or it
    was already claimed) — nothing to do.
    """

    outcome: str
    order: Optional[Order] = None
    reason: Optional[str] = None


# FlattenResult.outcome values (X-001). The route dispatches on these:
FLATTEN_FLAT = "flat"        # no open position; route surfaces 409
FLATTEN_EXISTING = "existing"  # an existing intent returned as-is (idempotent
                               # own manual_flatten, or a genuinely-live
                               # protection_floor exit left untouched)
FLATTEN_CREATED = "created"  # a fresh manual_flatten intent was created + ordered
                             # (superseding a non-live protection_floor exit first,
                             # if one was active)


@dataclass(frozen=True)
class FlattenResult:
    """Outcome of :meth:`StateStore.flatten_position` (X-001).

    ``flat``: no open position for the symbol (the route surfaces a 409).
    ``existing``: ``intent``/``order`` are returned as-is — no new intent was
    created. ``created``: a fresh ``manual_flatten`` intent (``intent``) and its
    SELL order (``order``) were created, atomically superseding any non-live
    ``protection_floor`` exit first (``superseded`` is ``True`` when that
    supersede happened — an observability flag, not part of the contract).

    In BOTH ``existing`` and ``created``, ``intent.reason`` is **guaranteed**
    to be ``manual_flatten`` UNLESS ``existing`` is returning a genuinely-live
    ``protection_floor`` exit that was already executing — the caller can tell
    the two apart via ``intent.reason`` itself. This is the whole point of the
    method: no caller of ``flatten_position`` can ever be handed a *newly
    created/deduped* intent whose reason isn't what was asked for (X-001).
    """

    outcome: str
    intent: Optional[SellIntent] = None
    order: Optional[Order] = None
    superseded: bool = False


class StateStore(ABC):
    """Abstract persistence interface. All methods are async."""

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def initialize(self) -> None:
        """Idempotent setup (create schema, ensure a current session exists).

        Safe to call on every startup.
        """

    async def close(self) -> None:  # pragma: no cover - default no-op
        """Release resources (e.g. a SQLite connection). Default: no-op."""

    # ------------------------------------------------------------------ #
    # Watchlist
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def add_watchlist_symbol(
        self, symbol: str, *, armed: bool = False
    ) -> WatchlistSymbol:
        """Add a symbol (idempotent: returns the existing row if present)."""

    @abstractmethod
    async def list_watchlist(self) -> list[WatchlistSymbol]:
        ...

    @abstractmethod
    async def get_watchlist_symbol(self, symbol: str) -> Optional[WatchlistSymbol]:
        ...

    @abstractmethod
    async def set_watchlist_armed(
        self, symbol: str, armed: bool
    ) -> WatchlistSymbol:
        """Arm/disarm a symbol. Raises :class:`UnknownEntityError` if absent."""

    @abstractmethod
    async def remove_watchlist_symbol(self, symbol: str) -> bool:
        """Delete a symbol (explicit command). Returns True if it existed."""

    # ------------------------------------------------------------------ #
    # Candidates (proposal lifecycle: pending/approved/rejected/expired/ordered)
    # ------------------------------------------------------------------ #
    @abstractmethod
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
        ...

    @abstractmethod
    async def list_candidates(
        self,
        *,
        session_id: Optional[str] = None,
        status: Optional[CandidateStatus] = None,
    ) -> list[Candidate]:
        ...

    @abstractmethod
    async def get_candidate(self, candidate_id: str) -> Optional[Candidate]:
        ...

    @abstractmethod
    async def transition_candidate(
        self,
        candidate_id: str,
        new_status: CandidateStatus,
        *,
        order_id: Optional[str] = None,
    ) -> Candidate:
        """Atomically transition a candidate and write an audit event.

        ``new_status`` is typed as :class:`CandidateStatus`, so a broker state
        cannot be passed here.
        """

    # ------------------------------------------------------------------ #
    # Sell intents (Phase 7 — Sell-Side Protection). The sell-side analogue of
    # candidates: a first-class exit decision with its own lifecycle, producing
    # one SELL order. See docs/archive/legacy_implementation_prompts/IMPLEMENTATION_PROMPT_PHASE_7.md.
    # ------------------------------------------------------------------ #
    @abstractmethod
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
        """Create a sell intent (an exit decision) atomically + audited.

        **Single-flight (atomic dedup).** The active-intent check and the insert
        happen under ONE lock hold: if an *active* sell intent already exists for
        ``symbol`` — see :meth:`active_sell_intent_for` for the exact "active"
        definition, kept in that one place so this docstring can't drift from it
        again (X-003) — the existing intent is returned and nothing is written.
        Validates a positive whole ``target_quantity`` and a real
        :class:`SellReason`.

        **This alone does not close the X-001 race** for a *specific* reason
        (``MANUAL_FLATTEN``): this method's dedup returns *whatever* intent is
        active regardless of the ``reason`` requested, so a caller that needs a
        guaranteed ``MANUAL_FLATTEN`` outcome — even racing a concurrent
        ``PROTECTION_FLOOR`` intent's own creation — must use
        :meth:`flatten_position` instead, which performs the whole
        supersede-then-create sequence as one atomic unit and verifies the
        reason of what it returns.
        """

    @abstractmethod
    async def transition_sell_intent(
        self,
        intent_id: str,
        new_status: SellIntentStatus,
        *,
        order_id: Optional[str] = None,
    ) -> SellIntent:
        """Atomically transition a sell intent and write an audit event. Mirrors
        :meth:`transition_candidate` (enum-typed status, idempotent same-status
        no-op, audited genuine transitions). ``approved -> expired`` is the
        self-heal used when the intent->order handoff is rejected — no intent is
        ever left stranded ``approved`` with no order."""

    @abstractmethod
    async def get_sell_intent(self, intent_id: str) -> Optional[SellIntent]:
        ...

    @abstractmethod
    async def list_sell_intents(
        self,
        *,
        session_id: Optional[str] = None,
        status: Optional[SellIntentStatus] = None,
        symbol: Optional[str] = None,
    ) -> list[SellIntent]:
        ...

    @abstractmethod
    async def active_sell_intent_for(self, symbol: str) -> Optional[SellIntent]:
        """The current active (in-flight) sell intent for ``symbol``, or ``None``.

        **This is the ONE canonical "active" definition** — every other
        docstring in this class refers back to this one rather than restating
        it, so the store's behavior and this definition cannot drift apart
        again the way they did before X-003 (the code used to silently drop the
        ``needs_review`` clause the ADR always specified).

        Active = ``pending``/``approved``, or ``ordered`` with a still-open
        (non-terminal) Order that does **not** carry an OPEN ``needs_review``
        broker-submit recovery record (D-017 / X-003). Once the linked Order
        reaches a terminal state (filled/canceled/rejected), OR is stranded in
        ``needs_review`` (a broker order accepted upstream that local state
        can't confirm as live — the recovery loop has escalated it for a human,
        not left it "still working"), the intent is no longer active and the
        symbol is eligible for a fresh protective intent (the residual
        re-evaluation path) — so neither a partial-then-canceled exit nor a
        stuck ``needs_review`` order can permanently block re-protection for a
        still-breaching symbol. The recovery record and its operator alert stay
        independently visible regardless (this definition only decides
        single-flight eligibility, never recovery visibility). An ``unresolved``
        recovery (the loop still actively working it) does NOT free the symbol —
        only the terminal-for-automation ``needs_review`` escalation does.

        Used for the single-flight dedup (:meth:`create_sell_intent`) and the
        operator/protection status surface.
        """

    @abstractmethod
    async def create_order_for_sell_intent(
        self,
        intent_id: str,
        *,
        order_type: OrderType,
        limit_price: Optional[float] = None,
    ) -> Order:
        """Atomic ``APPROVED -> ORDERED`` handoff for a sell intent — the sell-side
        analogue of :meth:`create_order_for_candidate`.

        Creates the SELL :class:`Order` (``side=SELL``, ``sell_intent_id`` set,
        ``candidate_id=None`` — the XOR origin), transitions the intent to
        ``ordered`` linking it, and writes both audit events, atomically. **No
        CAPI risk gate** (a protective exit reduces risk). **Re-reads the live
        derived position under the lock and rejects an oversell** (never a short:
        ``target_quantity`` may not exceed the current position quantity).
        ``order_type`` is a placeholder here (``MARKET`` for the full-exit intent);
        the concrete session-conditional type is (re)decided at submission time
        (Rule 12 / D-015 — see monitoring). For ``LIMIT`` a positive
        ``limit_price`` is required; for ``MARKET`` it must be ``None``.

        **Idempotent:** an intent already ``ORDERED`` returns its existing order.
        Raises :class:`UnknownEntityError` (unknown intent),
        :class:`SellIntentTransitionError` (not ``approved``), or
        :class:`InvalidOrderError` (oversell / bad limit-vs-market).
        """

    @abstractmethod
    async def flatten_position(
        self, symbol: str, *, session_id: Optional[str] = None
    ) -> FlattenResult:
        """Atomically open (or return the existing) ``manual_flatten`` exit for
        ``symbol`` — the whole "read the live position, stand down any
        non-live exit (a ``protection_floor`` intent, OR a stranded
        ``manual_flatten`` intent that never got as far as having an order —
        docs/INVARIANTS.md INV-038), create + approve + dispatch a fresh
        ``manual_flatten``" sequence, evaluated and applied under ONE lock hold
        (X-001). "The existing" one is only ever returned as-is when it is
        already ``ORDERED`` (has a real order) — never a merely
        ``pending``/``approved`` one, which would mean nothing actually exits.

        This is the ONLY correct way to flatten a position from a route or any
        other caller that must guarantee it gets back a ``manual_flatten``
        intent. Calling :meth:`create_sell_intent` directly with
        ``reason=manual_flatten`` does NOT give this guarantee: its
        single-flight dedup returns *whatever* intent is active regardless of
        the requested reason, so a concurrent protection tick's own
        ``create_sell_intent(protection_floor, ...)`` call can win the race in
        the gap between a caller's own separate "check active" and "create"
        calls, silently handing the caller a ``protection_floor`` intent
        instead — which a kill switch then holds unsubmitted (the exact defect
        this method exists to close). ``flatten_position`` has no such gap:
        every read this decision depends on, and every write it performs, share
        one lock hold from start to finish.

        Does **not** cancel a LIVE (broker-submitted) BUY order — that needs a
        broker call, which must never happen while this lock is held (the
        concurrency model: no network call under the store lock). Callers
        cancel open buys via ``app.monitoring.cancel_open_buys`` (best-effort,
        idempotent) BEFORE calling this method; this method re-reads the live
        position under its own lock regardless, so sizing always reflects
        whatever the buy-cancel step actually achieved — never oversized, never
        racing a partial fill.

        Returns :class:`FlattenResult`. ``session_id`` seeds a freshly-created
        intent only (ignored when returning an existing one).
        """

    # ------------------------------------------------------------------ #
    # Orders (broker lifecycle: created/submitted/partially_filled/filled/...)
    # ------------------------------------------------------------------ #
    # NOTE (AIR-006): the low-level ``create_order(candidate_id, symbol, side,
    # quantity, ...)`` used to live on this public contract. It has **no
    # production caller** (every real order goes through
    # ``create_order_for_candidate`` above, which enforces the approved-only rule
    # and the CAPI/control gates), yet it accepted ``quantity=-100`` and bypassed
    # every gate — a latent public-contract hazard. It has been removed from the
    # public ``StateStore`` surface and survives only as
    # ``create_order_for_test`` on the concrete stores, a clearly non-production
    # test-setup helper. Do not add it back to this ABC.

    @abstractmethod
    async def create_order_for_candidate(
        self,
        candidate_id: str,
        *,
        risk_limits: RiskLimits = RiskLimits(),
    ) -> Order:
        """Atomic ``APPROVED → ORDERED`` handoff — the candidate→order dispatch.

        ``docs/02_DATA_AND_PERSISTENCE.md`` lists *"candidate approval + order
        creation + audit event"* as one atomic group, so this is a single store
        operation (one SQL transaction in :class:`SqliteStateStore`; one lock
        acquisition in :class:`InMemoryStateStore`), not two sequential calls.
        It is deliberately separate from ``transition_candidate`` and from the
        Approval Gate: the ``ordered`` transition is never buried inside either
        (Phase 3 prompt §3 / D-006).

        On an ``APPROVED`` candidate it: creates the paper order (a long-only
        ``BUY`` ``LIMIT`` order whose quantity/limit come from the candidate's
        ``suggested_quantity`` / ``suggested_limit_price``), transitions the
        candidate to ``ORDERED`` linking the new order, and writes both the
        ``order_created`` and ``candidate_transition`` audit events — all
        atomically. No network call (Phase 4 submits to Alpaca).

        **Idempotent:** a candidate already ``ORDERED`` returns its existing order
        and writes nothing (no second order). This is what keeps the approve
        endpoint idempotent.

        ``risk_limits`` is the Phase 6 CAPI risk gate (D-016): its default,
        ``RiskLimits()``, is fully unenforced, so the interface itself supports
        an unrestricted mode, but the approve route always passes real,
        validated-positive values loaded from ``Settings``. A breach raises
        :class:`RiskLimitBlockedError` and writes a ``risk_limit_blocked``
        audit event (see ``app.policy.risk_limit_reason`` for the
        exact checks and their order).

        Raises :class:`UnknownEntityError` if the candidate does not exist;
        :class:`CandidateTransitionError` if it is not ``APPROVED`` (e.g. still
        ``PENDING``, or ``REJECTED``/``EXPIRED``); :class:`InvalidOrderError` if it
        carries no positive ``suggested_quantity`` to size the order;
        :class:`OrderIntentBlockedError` if the candidate's session is
        kill-switched or buys are paused; :class:`RiskLimitBlockedError` if a
        CAPI limit above is breached. This is where the *approved-only* rule
        that ``create_order`` deliberately deferred (D-010) is finally enforced.
        """

    @abstractmethod
    async def current_exposure(self) -> float:
        """Total current CAPI exposure (D-016b), read as one atomic snapshot.

        Every position's cost basis plus every non-terminal order's remaining
        notional — see ``app.policy.existing_exposure`` for the pure
        computation this wraps. Exists as its own store method (rather than
        making a caller combine ``list_positions()`` + ``list_orders()``
        itself) specifically so a caller *outside* the store's lock — the
        approve route's risk-limit pre-check — gets one consistent snapshot
        under a single lock acquisition, not a torn read across two separate
        lock-acquire/release cycles. ``create_order_for_candidate``'s own
        authoritative check computes this the same way, inside its own single
        lock hold, for the same reason.
        """

    @abstractmethod
    async def claim_order_for_submission(self, order_id: str) -> SubmissionClaim:
        """Atomically claim a ``CREATED`` order for submission (D-017).

        Under a **single lock hold** — mirroring ``set_kill_switch``'s idiom, not
        a new locking primitive — this re-reads the order, re-reads the current
        session **and** the order's own originating session, and re-checks every
        control (kill-switch, buys-paused, session-closed, session-unknown, and
        that the order is still ``CREATED``). Then:

        * order no longer ``CREATED`` → ``SubmissionClaim(CLAIM_SKIPPED)``, no
          state change (a session close cancelled it, or it was already claimed);
        * a control blocks it → ``SubmissionClaim(CLAIM_BLOCKED, reason=...)``,
          no state change (the loop audits the hold once, as before);
        * all clear → transition ``CREATED → SUBMITTING``, write an
          ``order_submission_claimed`` audit event, and return
          ``SubmissionClaim(CLAIM_CLAIMED, order=<the SUBMITTING order>)``.

        Because the control mutation (``set_kill_switch`` etc.) and this claim
        serialize through the same lock, a flip can no longer land *inside* the
        claim→broker-call window undetected: it lands before the claim (order
        stays ``CREATED``, held) or after ``SUBMITTING`` (already committed to
        submission — the human approved it and the backend atomically claimed it
        before the stop). This is the F-001/F-002 fix; the monitoring loop calls
        this first and only submits ``CLAIM_CLAIMED`` orders.
        """

    @abstractmethod
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
        """Durably record a broker truth the local order state cannot otherwise
        reconcile, surfaced to the operator. Atomic + audited. Two incident kinds
        share this one ledger:

        * **Submission orphan (D-017 / F-002 / AIR-003):** a broker order accepted
          upstream but whose local ``SUBMITTING → SUBMITTED`` persist failed, or a
          stale ``SUBMITTING`` order whose idempotent re-drive hit a terminal
          error. Born ``RECOVERY_UNRESOLVED`` (default): the monitoring tick's
          recovery step polls/cancels ``broker_order_id`` until resolved.
        * **Fill divergence (AIR-002):** the broker reports more filled than we
          could record (e.g. an un-priceable fill). Born ``cleanup_status=
          RECOVERY_NEEDS_REVIEW`` — a real untracked position a human must
          reconcile; the recovery loop must not auto-cancel it.

        ``cleanup_status`` must be a valid recovery status (``RECOVERY_STATUSES``);
        ``event_type`` names the creation audit event and ``extra_payload`` is
        merged into it (e.g. the broker/local fill counts for a divergence).

        ``candidate_id`` (D-020) correlates the creation event to the owning
        candidate's lifecycle. It is not stored on :class:`SubmitRecoveryRecord`
        itself (D-020 stays to one nullable ``Event`` field, not a new entity
        column) — ``update_submit_recovery`` resolves it later by looking up the
        local order via ``local_order_id`` (orders are never deleted, so this
        reliably resolves).
        """

    @abstractmethod
    async def list_submit_recoveries(
        self, *, statuses: Optional[Iterable[str]] = None
    ) -> list[SubmitRecoveryRecord]:
        """Broker-submit recovery records (newest last), optionally filtered to a
        set of ``cleanup_status`` values.

        ``statuses=None`` returns all. The recovery loop passes
        ``{RECOVERY_UNRESOLVED}`` (records it should still act on); the operator
        surface passes ``RECOVERY_OPEN_STATUSES`` (unresolved **and**
        needs-review — everything still needing attention, since a needs-review
        record holds a real untracked position a human must reconcile).
        """

    @abstractmethod
    async def update_submit_recovery(
        self,
        recovery_id: str,
        *,
        cleanup_status: Optional[str] = None,
        bump_attempt: bool = False,
    ) -> SubmitRecoveryRecord:
        """Update a recovery record (atomic). ``bump_attempt`` increments
        ``retry_count`` and stamps ``last_attempt_at`` (recording that the
        recovery loop tried this cadence). Setting ``cleanup_status`` to a
        resolved value writes a ``submit_recovery_resolved`` audit event. Raises
        :class:`UnknownEntityError` if the id is unknown.
        """

    @abstractmethod
    async def revert_candidate_approval(self, candidate_id: str) -> Candidate:
        """Atomically revert ``APPROVED → PENDING`` when dispatch was refused.

        Recovery for the approve/dispatch race (D-013): if a safety control flips
        between the approve transition and the order-creation handoff, the store
        refuses the order (``OrderIntentBlockedError``) but the candidate is
        already ``APPROVED`` — stranded ``APPROVED`` with no order under a safety
        stop. The approve route calls this to put it back to ``PENDING`` (still
        rejectable / re-approvable). Acts **only** on an ``APPROVED`` candidate
        with no linked order; otherwise it is an idempotent no-op (so a candidate
        that actually became ``ORDERED`` is never disturbed). Atomic + audited.
        """

    @abstractmethod
    async def list_orders(
        self,
        *,
        session_id: Optional[str] = None,
        candidate_id: Optional[str] = None,
    ) -> list[Order]:
        ...

    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[Order]:
        ...

    @abstractmethod
    async def transition_order(
        self,
        order_id: str,
        new_status: OrderStatus,
        *,
        filled_quantity: Optional[int] = None,
        broker_order_id: Optional[str] = None,
    ) -> Order:
        """Atomically transition an order and write an audit event."""

    # ------------------------------------------------------------------ #
    # Timeout-quarantine (ADR-002 / wave 3c) — evented order transitions
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def quarantine_timed_out_order(
        self, order_id: str, *, reason: Optional[str] = None
    ) -> Order:
        """``SUBMITTING → TIMEOUT_QUARANTINE`` for an ambiguous submit (ADR-002).

        Atomically flips the order-row status (a read-model), writes an
        ``order_timeout_quarantined`` audit event, AND appends a
        ``TIMEOUT_QUARANTINE`` ``ExecutionEvent`` — the FIRST durable write and
        the ``event_truth`` for this fact (idempotent on its
        ``timeout_quarantine:{order_id}`` dedupe_key). Raises
        :class:`OrderTransitionError` if the order is not ``SUBMITTING``.
        """

    @abstractmethod
    async def resolve_timeout_quarantine(
        self,
        order_id: str,
        new_status: OrderStatus,
        *,
        broker_order_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Order:
        """``TIMEOUT_QUARANTINE → {SUBMITTED, REJECTED, CANCELED}`` from a read-only
        targeted ``client_order_id`` query (ADR-002). Co-writes the matching
        lifecycle ``ExecutionEvent`` + an ``order_timeout_quarantine_resolved``
        audit event with the order-row flip. Resolving to ``SUBMITTED`` requires
        ``broker_order_id`` (AIR-001); the normal reconcile poll then ingests any
        fills. Raises :class:`OrderTransitionError` if the order is not
        ``TIMEOUT_QUARANTINE`` or ``new_status`` is not a legal resolution.
        """

    @abstractmethod
    async def list_timeout_quarantined_orders(self) -> list[Order]:
        """Orders currently in ``TIMEOUT_QUARANTINE`` (ADR-002), derived from the
        event log (an order whose latest lifecycle ``ExecutionEvent`` is
        ``TIMEOUT_QUARANTINE``), so it is replay-stable and dual-store-consistent.
        """

    # ------------------------------------------------------------------ #
    # Fills (append-only; the only thing that mutates position)
    # ------------------------------------------------------------------ #
    @abstractmethod
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
        """Append a fill atomically (append + dedup check + audit event).

        * If ``source_fill_id`` duplicates an existing fill: no row is written,
          position is untouched, a duplicate-ignored event is recorded, and the
          result's ``status`` is ``"duplicate"``.
        * If the fill is a sell that would drive the symbol's quantity below
          zero: no row is written, a rejection event is recorded, and
          :class:`~app.position.NegativePositionError` is raised.
        * Otherwise the fill is appended and ``status`` is ``"appended"``.
        """

    @abstractmethod
    async def list_fills(
        self,
        *,
        symbol: Optional[str] = None,
        order_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> list[Fill]:
        ...

    # ------------------------------------------------------------------ #
    # Positions (derived, read-only — folded from fills)
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def get_position(self, symbol: str) -> Position:
        """Derived position for one symbol (flat Position if no fills)."""

    @abstractmethod
    async def list_positions(self) -> list[Position]:
        """Derived positions for every symbol that has fills."""

    @abstractmethod
    async def list_quarantined_symbols(self) -> set[str]:
        """Symbols quarantined by a broker-authoritative overfill (ADR-001,
        Spine v2 wave 3b): a recorded FILL crossed the long-only position through
        flat into short. Derived purely from the event log (a negative projected
        position), so it is replay-stable. Autonomous BUY order intent for a
        quarantined symbol is blocked until the operator reconciles and reviews.
        """

    # ------------------------------------------------------------------ #
    # Events / audit log (append-only)
    # ------------------------------------------------------------------ #
    @abstractmethod
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
        """``correlation_id`` ties a whole candidate (or sell-intent) lifecycle
        together for incident reconstruction (D-020). When not passed it
        defaults to ``candidate_id`` (the owning candidate's id is the
        correlation key), so every event that names a candidate correlates
        automatically. When ``candidate_id`` is also absent but ``order_id`` is
        present, it resolves instead from that order's ``sell_intent_id``
        (X-004) — so a protective-sell order's claim/submit/stale/fill/recovery
        events correlate on the sell intent, not just its creation events. See
        ``docs/INVARIANTS.md`` INV-041."""
        ...

    @abstractmethod
    async def list_events(
        self,
        *,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        correlation_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Event]:
        """``event_type``, when given, filters to exactly that
        :class:`EventType` value (e.g. ``"order_stale"``) — the audit log
        accumulates across days (``docs/02``) and a caller that only cares
        about one rare event type shouldn't have to pull the full log (or an
        arbitrarily-sized recent window that a high write-rate producer, like
        the Phase 5 strategy loop's per-tick staleness/candidate events, can
        scroll a rare event out of) just to find it.
        """

    # ------------------------------------------------------------------ #
    # Execution-event log (Spine v2 — Phase 2 event-sourcing scaffolding)
    #
    # The append-only ``ExecutionEvent`` log (Spine v2 §11), DISTINCT from the
    # audit event log above. Phase 2 is additive/shadow: the log exists and is
    # proven correct in isolation (dual-store parity, replay), but no production
    # flow writes to it yet and nothing treats it as authoritative. Phase 3
    # flips migrated flows to event-truth (``docs/MIGRATION_MATRIX.md``).
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def append_execution_event(self, event: ExecutionEvent) -> ExecutionEvent:
        """Append ``event`` to the durable execution-event log, assigning a
        monotonic per-store ``sequence`` (``max_sequence + 1``) under the write
        lock. The passed ``event.sequence`` is ignored and overwritten.

        **Idempotent by ``dedupe_key`` (INV-5).** If ``event.dedupe_key`` is
        non-``None`` and already present in the log, no row is written, no
        sequence is consumed, and the *existing* event is returned unchanged.
        A ``None`` ``dedupe_key`` is never deduped (every such append is a new
        row). Returns the appended (or pre-existing) event, with its assigned
        ``sequence``.

        The append is atomic: sequence read + assignment + write happen under
        the same lock/transaction as any other multi-row mutation, so concurrent
        appends can never collide on a sequence or observe a gap.
        """

    @abstractmethod
    async def get_execution_events(
        self, *, after_sequence: int = 0, limit: Optional[int] = None
    ) -> list[ExecutionEvent]:
        """Events with ``sequence > after_sequence``, in ascending sequence
        order (replay order). ``after_sequence=0`` (default) returns the whole
        log; a snapshot-based recovery passes the snapshot's ``up_to_sequence``
        to replay only the tail. ``limit`` caps the batch size (oldest-first)
        for chunked replay of a large log.

        A negative ``limit`` raises ``ValueError`` in *both* stores — it is
        nonsensical input, and left unguarded it would diverge (a Python slice
        ``out[:-1]`` drops the tail while SQL ``LIMIT -1`` means unlimited),
        violating the strict dual-store parity mandate.
        """

    @abstractmethod
    async def get_max_execution_sequence(self) -> int:
        """The highest assigned ``sequence`` in the log, or ``0`` if empty."""

    # ------------------------------------------------------------------ #
    # Sessions / control flags
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def get_current_session(self) -> SessionRecord:
        """The active session (creating today's if none is active)."""

    @abstractmethod
    async def get_session_by_date(self, day: date) -> Optional[SessionRecord]:
        ...

    @abstractmethod
    async def get_session_by_id(self, session_id: str) -> Optional[SessionRecord]:
        """The session with this id, or ``None``.

        Used by the monitoring loop to gate a held order's submission against its
        **own** originating session (D-013a), independent of which session is
        currently live.
        """

    @abstractmethod
    async def list_sessions(self) -> list[SessionRecord]:
        ...

    @abstractmethod
    async def set_kill_switch(self, engaged: bool) -> SessionRecord:
        """Persist the kill-switch flag on the active session (atomic + audit).

        Beta only persists the flag; enforcement on order intent arrives with
        the order path (out of scope now — see the implementation prompt).
        """

    @abstractmethod
    async def set_buys_paused(self, paused: bool) -> SessionRecord:
        """Persist the pause-buys flag on the active session (atomic + audit)."""

    @abstractmethod
    async def close_session(
        self, session_id: Optional[str] = None
    ) -> SessionRecord:
        """Close a session (default: the active one). Atomically:

        1. Transition every ``PENDING``/``APPROVED`` candidate in this session
           to ``EXPIRED`` (terminal candidates are left untouched).
        2. Cancel every still-``CREATED`` (never-submitted) order in this
           session (D-013a) — a clean terminal state instead of a zombie
           ``CREATED`` order the per-order-session submission gate would
           otherwise hold forever. Already-``SUBMITTED`` orders are untouched
           and keep reconciling after close (D-011).
        3. Snapshot current positions — every symbol with a nonzero derived
           quantity — into ``position_snapshots``, keyed by this session id.
        4. Set ``status=CLOSED`` and ``closed_at=now``.
        5. Write one audit event recording the close, how many candidates
           were expired, and how many orders were canceled.

        Raises :class:`SessionAlreadyClosedError` if the session is already
        closed, and :class:`UnknownEntityError` if ``session_id`` is unknown.
        Automatic, window-driven close is out of scope here (needs a monitoring
        loop) — this is the manual trigger only.
        """

    @abstractmethod
    async def list_position_snapshots(
        self, session_id: str
    ) -> list[PositionSnapshot]:
        """The position snapshots captured when ``session_id`` was closed."""
