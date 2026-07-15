"""Shared store *orchestration* — the domain-core layer.

``app/policy.py`` already extracts the pure input *predicates* both
stores share; ``app/transitions.py`` the state-machine tables;
``app/position.py`` the fold. This module extends that same "pure decision in
one place, storage wiring in each store" pattern up one level, to the multi-step
*pipelines* that were otherwise duplicated near-verbatim between
``InMemoryStateStore`` and ``SqliteStateStore``.

A **planner** here is a pure function: it takes state the store has already
fetched (an order, a prior-filled total, a position quantity, a dedup flag) and
returns a small immutable *plan* describing what to write and what to raise —
without touching any store. Each store then:

1. fetches the inputs its own way (dict lookup vs. ``SELECT``),
2. calls the planner,
3. applies the plan with its own primitives (``_atomic`` + dict mutation vs.
   ``_tx`` + SQL), inside its own atomicity boundary.

The two atomicity mechanisms, the dedup mechanism (an in-memory ``set`` vs. a
partial unique index), and the row⇄model mapping stay storage-specific — only
the *decision* is shared. The 76 ``any_store`` parity tests prove the two stores
still behave identically after each method is migrated here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from app.models import (
    Candidate,
    CandidateStatus,
    EventAuthority,
    EventSource,
    EventType,
    ExecutionEvent,
    ExecutionEventType,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSnapshot,
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_STATUSES,
    RECOVERY_TRANSITIONS,
    SellIntent,
    SellIntentStatus,
    SellReason,
    SessionRecord,
    SIGNAL_CONFLICT,
    SIGNAL_EXPIRED_AT_INGEST,
    SIGNAL_QUARANTINED_FRESHNESS,
    SIGNAL_QUARANTINED_VALIDATION,
    SIGNAL_RECEIVED_OK,
    SIGNAL_REPLAYED,
    SignalRecord,
    SignalStatus,
    TradingState,
    utcnow,
)
from app.position import would_go_negative
from app.store.base import (
    CLAIM_BLOCKED,
    CLAIM_CLAIMED,
    CLAIM_SKIPPED,
    COMMAND_ACTOR_SYSTEM,
    normalize_symbol,
    CandidateTransitionError,
    InvalidControlValueError,
    InvalidFillError,
    InvalidOrderError,
    InvalidStatusError,
    OrderIntentBlockedError,
    OrderTransitionError,
    RecoveryTransitionError,
    RiskLimitBlockedError,
    RiskLimits,
    SellIntentTransitionError,
    UnknownEntityError,
)
from app.transitions import ORDER_TIMESTAMP, ORDER_TRANSITIONS
from app.policy import (
    fill_order_match_reason,
    fill_value_reason,
    filled_quantity_reason,
    kill_switch_block_reason,
    limit_price_reason,
    order_intent_block_reason,
    order_session_resolution_reason,
    risk_limit_reason,
    session_submission_block_reason,
)


@dataclass(frozen=True)
class EventSpec:
    """A pure description of an audit event, decoupled from how it is written.

    Maps onto both stores' event writers — ``InMemoryStateStore.
    _append_event_unlocked`` and ``SqliteStateStore._insert_event`` share the
    identical keyword signature — via :meth:`as_kwargs` (everything except the
    positional ``event_type``).
    """

    event_type: str
    message: str = ""
    symbol: Optional[str] = None
    candidate_id: Optional[str] = None
    order_id: Optional[str] = None
    fill_id: Optional[str] = None
    payload: dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    # Lifecycle correlation key (D-020). Buy events leave this None and the store
    # writer defaults it to candidate_id; sell-side events (Phase 7, candidate_id
    # is None) set it explicitly to the owning sell_intent_id so a whole protective
    # exit is reconstructable via GET /api/events?correlation_id=<sell_intent_id>.
    correlation_id: Optional[str] = None

    def as_kwargs(self) -> dict[str, Any]:
        """Keyword args for a store's event writer (``event_type`` stays positional)."""
        return {
            "message": self.message,
            "symbol": self.symbol,
            "candidate_id": self.candidate_id,
            "order_id": self.order_id,
            "fill_id": self.fill_id,
            "payload": self.payload,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
        }


# ---- append_fill ---------------------------------------------------------- #

# FillPlan.outcome values. The store dispatches on these:
FILL_REJECT = "reject"        # write `event`; raise `error`
FILL_DUPLICATE = "duplicate"  # write `event`; return a FillAppendResult("duplicate", None, event)
FILL_APPEND = "append"        # atomically write `fill` (+dedup) and `event`; return "appended"


@dataclass(frozen=True)
class FillPlan:
    """Pure outcome of an :meth:`StateStore.append_fill` decision.

    ``outcome`` is one of :data:`FILL_REJECT` / :data:`FILL_DUPLICATE` /
    :data:`FILL_APPEND`. ``event`` is always the audit event to write. ``error``
    is the exception to raise (reject only). ``fill`` is the constructed row to
    append (append only).
    """

    outcome: str
    event: EventSpec
    error: Optional[Exception] = None
    fill: Optional[Fill] = None
    # Spine v2: the broker-authoritative FILL ExecutionEvent appended to the event
    # log *atomically with* the fill row (append path only). Post the wave-3a
    # event-truth flip (WO-0001: the fill flow is `event_truth`), position derives
    # from folding these FILL events (app/events/projectors.py); the fill table
    # persists as a parity-checked read model, kept in lockstep by the permanent
    # dual-store parity verifier. See pkl/process/migration-history.md.
    execution_event: Optional[ExecutionEvent] = None


def execution_event_for_fill(
    fill: Fill,
    *,
    source: EventSource = EventSource.BROKER_REST,
    authority: EventAuthority = EventAuthority.BROKER_AUTHORITATIVE,
) -> ExecutionEvent:
    """The ``FILL`` ExecutionEvent that mirrors a fill row.

    Single-sourced so the wave-3a shadow write (``plan_append_fill``) and the
    event-truth backfill (``StateStore`` init) build the SAME event for the same
    fill — a deterministic, replay-stable record. A normally-observed fill is a
    broker-reported fact (submitted orders fill and are observed via polling), so
    ``source``/``authority`` default to ``BROKER_REST``/``BROKER_AUTHORITATIVE``.
    A **reconciliation-inferred** fill (Phase 4) overrides them to
    ``RECONCILIATION``/``SYNTHETIC`` — provenance only; the ``dedupe_key`` stays the
    venue-execution identity, so a synthetic fill and the eventual real observation
    of the same execution dedup to one (INV-5), never a double-count. ``ts_event``
    is the fill time so the projected ``Position.updated_at`` matches the fold.

    **dedupe_key** must uniquely and deterministically identify the fill so the
    backfill can tell whether a fill already has an event (idempotent, additive
    reconcile — never a positional guess). For a fill with a venue
    ``source_fill_id`` (the production case — Alpaca fills always carry one), the
    key is ``fill:{order_id}:{source_fill_id}``, mirroring the fill table's
    per-(order_id, source_fill_id) dedup exactly (two orders may legitimately
    share a venue fill id — F1 — so the order id is part of the key). A fill with
    NO ``source_fill_id`` (tests / hypothetical) has no venue identity, so we key
    on its unique row id ``fill:{order_id}:@{fill.id}``: still unique per fill (so
    it never dedups against a different fill, matching the fill table's
    "null-source is never deduped") yet matchable, so backfill neither skips nor
    double-emits it. (The row-id key is store-local for null-source fills; this
    does not affect projected position, only the dedupe identity.)
    """

    if fill.source_fill_id is not None:
        dedupe_key = f"fill:{fill.order_id}:{fill.source_fill_id}"
    else:
        dedupe_key = f"fill:{fill.order_id}:@{fill.id}"
    return ExecutionEvent(
        event_type=ExecutionEventType.FILL,
        source=source,
        authority=authority,
        dedupe_key=dedupe_key,
        ts_event=fill.filled_at,
        symbol=fill.symbol,
        side=fill.side,
        quantity=fill.quantity,
        price=fill.price,
        order_id=fill.order_id,
        session_id=fill.session_id,
    )


def plan_append_fill(
    *,
    order_id: str,
    order: Optional[Order],
    prior_filled: int,
    current_quantity: int,
    is_duplicate: bool,
    symbol: str,
    side: OrderSide,
    quantity: int,
    price: float,
    source_fill_id: Optional[str],
    filled_at: Optional[Any],
    session_id: Optional[str],
    source: EventSource = EventSource.BROKER_REST,
    authority: EventAuthority = EventAuthority.BROKER_AUTHORITATIVE,
) -> FillPlan:
    """Decide the outcome of appending one fill — the shared logic that was
    duplicated between the two stores.

    ``symbol`` is already normalized and ``side`` already coerced by the caller.
    ``order`` is ``None`` when the referenced order does not exist.
    ``current_quantity`` is the symbol's derived position quantity.
    ``is_duplicate`` is whether ``(order_id, source_fill_id)`` was already
    recorded. The checks run in the same order the stores used, so a duplicate
    still short-circuits before the cumulative/overfill check (never mistaken
    for an overfill).

    ``source``/``authority`` set the FILL ExecutionEvent provenance — the default
    is a normally-observed broker fill; a reconciliation-inferred fill (Phase 4)
    passes ``RECONCILIATION``/``SYNTHETIC``. Provenance only: dedup/position are
    unchanged, so a synthetic fill still dedups against the real observation of the
    same execution (INV-5).
    """

    # 1) Intrinsic value validation: a non-finite/non-positive quantity or price
    #    would corrupt derived-position truth. Reject before anything is touched.
    value_reason = fill_value_reason(quantity, price)
    if value_reason is not None:
        return FillPlan(
            FILL_REJECT,
            EventSpec(
                "fill_rejected_invalid",
                message=f"fill for {symbol} rejected: {value_reason}",
                symbol=symbol,
                # This value check runs before the order-existence check, so the
                # order may be absent here; correlate when it is present so a
                # malformed-fill rejection still shows up in the candidate's
                # lifecycle (D-020), matching the other fill events below.
                candidate_id=order.candidate_id if order is not None else None,
                order_id=order_id,
                payload={"reason": value_reason, "quantity": quantity, "price": price},
                session_id=session_id,
            ),
            error=InvalidFillError(f"invalid fill for {symbol}: {value_reason}"),
        )

    # 2) The referenced order must exist.
    if order is None:
        return FillPlan(
            FILL_REJECT,
            EventSpec(
                "fill_rejected_invalid",
                message=f"fill rejected: unknown order {order_id}",
                symbol=symbol,
                order_id=order_id,
                payload={"reason": "unknown_order"},
                session_id=session_id,
            ),
            error=UnknownEntityError(f"order {order_id} not found"),
        )

    # 3) Duplicate protection (makes append idempotent). A replay short-circuits
    #    here before the cumulative check, so it is never mistaken for an overfill.
    if is_duplicate:
        return FillPlan(
            FILL_DUPLICATE,
            EventSpec(
                "fill_duplicate_ignored",
                message=f"duplicate fill {source_fill_id} for {symbol} ignored",
                symbol=symbol,
                candidate_id=order.candidate_id,
                order_id=order_id,
                payload={"source_fill_id": source_fill_id},
                session_id=session_id,
            ),
        )

    # 4) Symbol/side match + cumulative-quantity vs the order.
    match_reason = fill_order_match_reason(order, symbol, side, quantity, prior_filled)
    if match_reason is not None:
        return FillPlan(
            FILL_REJECT,
            EventSpec(
                "fill_rejected_invalid",
                message=f"fill for {symbol} rejected: {match_reason}",
                symbol=symbol,
                candidate_id=order.candidate_id,
                order_id=order_id,
                payload={
                    "reason": match_reason,
                    "order_symbol": order.symbol,
                    "order_side": OrderSide(order.side).value,
                    "order_quantity": order.quantity,
                    "prior_filled_quantity": prior_filled,
                    "quantity": quantity,
                },
                session_id=session_id,
            ),
            error=InvalidFillError(
                f"fill for {symbol} inconsistent with order {order_id}: {match_reason}"
            ),
        )

    # 5) + 6) Append. A sell that crosses a long-only position through flat is a
    #    broker-authoritative OVERFILL (ADR-001, wave 3b): intrinsic validity was
    #    already checked (step 1), so this is broker REALITY, not malformed local
    #    input. Rather than reject-and-drop it (the pre-wave-3b behavior), RECORD
    #    the fill + its FILL event and QUARANTINE the symbol. Position now derives
    #    from the event log, which projects the recorded short (apply_fill
    #    allow_short); `create_order_for_candidate` blocks autonomous BUY intent
    #    for a quarantined symbol, and the operator reconciles + manually reviews.
    #    The store writes fill row + audit event + FILL event atomically.
    is_overfill = would_go_negative(current_quantity, side, quantity)
    fill = Fill(
        order_id=order_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        source_fill_id=source_fill_id,
        session_id=session_id,
        filled_at=filled_at or utcnow(),
    )
    if is_overfill:
        event = EventSpec(
            "fill_overfill_quarantined",
            message=(
                f"broker overfill: sell of {quantity} {symbol} exceeds current "
                f"quantity {current_quantity} — recorded and quarantined (ADR-001)"
            ),
            symbol=symbol,
            candidate_id=order.candidate_id,
            order_id=order_id,
            fill_id=fill.id,
            payload={
                "side": side.value,
                "quantity": quantity,
                "price": price,
                "attempted_sell": quantity,
                "current_quantity": current_quantity,
                "quarantined": True,
            },
            session_id=session_id,
        )
    else:
        event = EventSpec(
            "fill_appended",
            message=f"fill {fill.quantity} {symbol} @ {fill.price}",
            symbol=symbol,
            candidate_id=order.candidate_id,
            order_id=order_id,
            fill_id=fill.id,
            payload={"side": side.value, "quantity": quantity, "price": price},
            session_id=session_id,
        )
    return FillPlan(
        FILL_APPEND, event, fill=fill,
        execution_event=execution_event_for_fill(fill, source=source, authority=authority),
    )


# ---- TradingState control (§8 / wave 3d) ---------------------------------- #


def trading_state_change_event(
    session_id: str,
    *,
    prior_control: TradingState,
    kill_switch: bool,
    buys_paused: bool,
    reason: str,
) -> Optional[ExecutionEvent]:
    """The ``driver="control"`` ``TRADING_STATE_CHANGED`` ``ExecutionEvent`` for a
    kill/pause control change, or ``None`` when the CONTROL-driver state is unchanged
    (a redundant re-engage) — §8 / wave 3d.

    ``prior_control`` is the previous *control-driver* state (``control_trading_state``
    over the log), NOT the effective composed state — a control event records the
    control driver's own ``to`` and the projector composes it with the independent
    reconcile driver (wave 4f / R2). The durable truth of the control fact: the ``to``
    is what ``control_trading_state`` folds (latest-wins). The payload also stamps the
    resulting ``(kill_switch, buys_paused)`` tuple as context, but the two booleans
    remain co-written ``sessions`` columns (legacy read-models), NOT purely
    event-reconstructable: no event fires when a boolean toggle leaves the control
    state unchanged (e.g. pause toggled while already ``HALTED``), so the log alone
    cannot always rebuild them — runtime correctness (incl. independent-release) comes
    from the durable columns. A LOCAL/ENGINE control decision, not a broker fact."""

    new_state = TradingState.of(kill_switch=kill_switch, buys_paused=buys_paused)
    if new_state is prior_control:
        return None
    return ExecutionEvent(
        event_type=ExecutionEventType.TRADING_STATE_CHANGED,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=utcnow(),
        session_id=session_id,
        payload={
            "driver": "control",
            "from": prior_control.value,
            "to": new_state.value,
            "kill_switch": kill_switch,
            "buys_paused": buys_paused,
            "reason": reason,
        },
    )


def reconcile_trading_state_event(
    session_id: str,
    *,
    prior_reconcile: TradingState,
    to: TradingState,
    reason: str,
) -> Optional[ExecutionEvent]:
    """The ``driver="reconcile"`` ``TRADING_STATE_CHANGED`` ``ExecutionEvent`` (wave
    4f / R2), or ``None`` when the reconcile-driver state is unchanged.

    A SECOND, independent driver of the §8 FSM: startup mass-reconcile, stream
    reconnect, and parity signals drive ``trading_state`` to ``Reducing`` (pending
    reconciliation — the §8 default under degradation) or ``Active`` (parity restored)
    WITHOUT touching the kill/pause booleans (the wave-3d control driver). The
    projector composes this with the control driver via ``compose_trading_state``
    (``Halted > Reducing > Active``), so kill still dominates a reconcile-driven
    ``Reducing`` (R3: reconcile never auto-Halts — a held position stays exitable) and
    a kill *release* can't lift a ``Reducing`` that pending reconciliation still
    requires. ``to`` must be ``Reducing`` or ``Active`` (a reconcile signal never
    drives ``Halted``)."""

    if to is TradingState.HALTED:
        raise ValueError("the reconcile driver never drives Halted (R3)")
    if to is prior_reconcile:
        return None
    return ExecutionEvent(
        event_type=ExecutionEventType.TRADING_STATE_CHANGED,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=utcnow(),
        session_id=session_id,
        payload={
            "driver": "reconcile",
            "from": prior_reconcile.value,
            "to": to.value,
            "reason": reason,
        },
    )


def emergency_reduce_override_event(
    session_id: str,
    symbol: str,
    *,
    actor: str,
    reason: str,
    resolved: bool = False,
) -> ExecutionEvent:
    """The ``EMERGENCY_REDUCE_OVERRIDE`` (grant) or
    ``EMERGENCY_REDUCE_OVERRIDE_RESOLVED`` (consume) ``ExecutionEvent`` — the
    durable truth of an audited operator override that scopes ONE reduce-only exit
    while the session is ``Halted`` (ADR-003 / wave 3e).

    A LOCAL/ENGINE decision (an operator command, not a broker fact), scoped to
    ``{session_id, symbol}`` and carrying the ``actor`` + ``reason`` for audit. The
    global ``TradingState`` stays ``Halted`` throughout; the grant is what the
    claim gate consults (via ``active_emergency_reduce_overrides``) to let the one
    exit through, and ``resolved=True`` ends the scoped grant on resolution so a
    later flatten under ``Halted`` is denied again. Not deduped — each grant/resolve
    is a distinct control action; the projector folds latest-wins per symbol."""

    return ExecutionEvent(
        event_type=(
            ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE_RESOLVED
            if resolved
            else ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE
        ),
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=utcnow(),
        session_id=session_id,
        symbol=symbol,
        payload={"actor": actor, "reason": reason, "resolved": resolved},
    )


# ---- create_order_for_candidate ------------------------------------------- #

# CreateOrderPlan.outcome values:
CREATE_ORDER_REJECT = "reject"  # write `reject_event` (block case only); raise `error`
CREATE_ORDER_CREATE = "create"  # write `order` + candidate ORDERED transition + `events`


@dataclass(frozen=True)
class CreateOrderPlan:
    """Pure outcome of the APPROVED→ORDERED handoff *after* the store has handled
    the candidate-missing and ORDERED-idempotent cases (both need store fetches).

    ``reject``: raise ``error``; write ``reject_event`` first *only* when it is
    set (the kill-switch/pause block and the Phase 6 CAPI risk-limit block each
    write an audit row; the not-approved and invalid-qty/price rejections write
    nothing, matching the original stores).
    ``create``: append ``order``, transition the candidate to ORDERED linking it,
    and write ``events`` (``order_created`` then ``candidate_transition``) — all
    atomically.

    ``expire_intent``/``expire_event`` (X-002, sell-intent path only): on a
    rejection *after* the intent was genuinely ``approved`` (oversell, a
    vanished position, bad limit/market price coherence — never the "not
    approved" precondition reject, which has no ``approved`` state to heal
    from), the intent is atomically self-healed ``approved → expired`` alongside
    the reject event, so it is never left stranded ``approved`` poisoning the
    single-flight dedup forever (the ADR's "Self-heal (blocker)" clause). The
    store applies both writes in the SAME atomic block as the reject, before
    raising ``error``.
    """

    outcome: str
    error: Optional[Exception] = None
    reject_event: Optional[EventSpec] = None
    order: Optional[Order] = None
    events: tuple[EventSpec, ...] = ()
    expire_intent: Optional[SellIntent] = None
    expire_event: Optional[EventSpec] = None


def plan_create_order_for_candidate(
    *,
    candidate: Candidate,
    session: Optional[SessionRecord],
    exposure_before_order: float = 0.0,
    risk_limits: RiskLimits = RiskLimits(),
    quarantined: bool = False,
) -> CreateOrderPlan:
    """The shared validation cascade + order construction for the candidate→order
    dispatch. ``candidate`` is known to exist and *not* already ORDERED (the store
    handles those first). ``session`` is the candidate's own originating session.

    ``exposure_before_order`` is the store's current total CAPI exposure (every
    position's cost basis plus every non-terminal order's remaining notional —
    unscoped by session, since exposure is a live, cross-session concept; see
    ``app.policy.existing_exposure``, which the store computes this
    from before calling in). ``risk_limits`` bundles the Phase 6 CAPI risk gate's
    (D-016) independently-optional limits (``RiskLimits()`` = none enforced).
    """

    # The approved-only rule D-010 deferred to the gate lands here.
    if candidate.status is not CandidateStatus.APPROVED:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=CandidateTransitionError(
                f"cannot order candidate {candidate.id} in status "
                f"{candidate.status.value}; must be approved"
            ),
        )

    # Unresolved session (F-004): a candidate whose declared session no longer
    # resolves must not produce order intent. order_session_resolution_reason is
    # a *distinct* predicate from order_intent_block_reason(session) below — that
    # one deliberately treats None as "no live session to stop" for the
    # monitoring loop's current-session emergency-stop check, so it must NOT
    # block on None. create_candidate already rejects an explicit unresolvable
    # session id up front; this is the dispatch-time backstop, audited.
    session_reason = order_session_resolution_reason(session)
    if session_reason is not None:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=OrderIntentBlockedError(f"order intent blocked: {session_reason}"),
            reject_event=EventSpec(
                "order_intent_blocked",
                message=(
                    f"order intent for {candidate.symbol} blocked: {session_reason}"
                ),
                symbol=candidate.symbol,
                candidate_id=candidate.id,
                payload={"reason": session_reason},
                session_id=candidate.session_id,
            ),
        )

    # Safety controls (Rule 8): refuse new order intent when kill-switched /
    # buys-paused — gated at the backend boundary (not just the UI), and audited.
    block = order_intent_block_reason(session)
    if block is not None:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=OrderIntentBlockedError(f"order intent blocked: {block}"),
            reject_event=EventSpec(
                "order_intent_blocked",
                message=f"order intent for {candidate.symbol} blocked: {block}",
                symbol=candidate.symbol,
                candidate_id=candidate.id,
                payload={"reason": block},
                session_id=candidate.session_id,
            ),
        )

    # ADR-001 (wave 3b): block autonomous BUY intent for a symbol quarantined by
    # a broker-authoritative overfill — no new spawn while the primary is
    # quarantined. The operator must reconcile + review before trading resumes.
    if quarantined:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=OrderIntentBlockedError(
                f"order intent for {candidate.symbol} blocked: symbol quarantined "
                f"after a broker overfill (ADR-001)"
            ),
            reject_event=EventSpec(
                "order_intent_blocked_quarantine",
                message=(
                    f"order intent for {candidate.symbol} blocked: symbol "
                    f"quarantined after a broker overfill (ADR-001)"
                ),
                symbol=candidate.symbol,
                candidate_id=candidate.id,
                payload={"reason": "symbol_quarantined"},
                session_id=candidate.session_id,
            ),
        )

    qty = candidate.suggested_quantity
    if qty is None or qty <= 0:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=InvalidOrderError(
                f"candidate {candidate.id} has no positive suggested_quantity "
                f"to size an order"
            ),
        )

    # A LIMIT order requires a finite, positive limit price (F1 / BACKEND-1).
    limit_price = candidate.suggested_limit_price
    bad_price = limit_price_reason(limit_price)
    if bad_price is not None:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=InvalidOrderError(
                f"candidate {candidate.id} has no valid suggested_limit_price "
                f"for a limit order ({bad_price})"
            ),
        )
    # limit_price_reason rejects None / non-finite / non-positive above, so a
    # valid finite float remains (narrows Optional for the risk gate below).
    assert limit_price is not None

    # Phase 6 CAPI pre-trade risk gate (D-016): gate-and-reject, never resize.
    # Local-derived exposure only (folded positions + non-terminal orders'
    # remaining notional) — no live broker/market-data call on the order path.
    risk_block = risk_limit_reason(
        symbol=candidate.symbol,
        order_quantity=qty,
        order_limit_price=limit_price,
        exposure_before_order=exposure_before_order,
        max_shares_per_order=risk_limits.max_shares_per_order,
        max_notional_per_order=risk_limits.max_notional_per_order,
        max_total_exposure=risk_limits.max_total_exposure,
        allowlist=risk_limits.allowlist,
    )
    if risk_block is not None:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=RiskLimitBlockedError(f"risk limit blocked: {risk_block}"),
            reject_event=EventSpec(
                "risk_limit_blocked",
                message=f"order intent for {candidate.symbol} blocked: {risk_block}",
                symbol=candidate.symbol,
                candidate_id=candidate.id,
                payload={
                    "reason": risk_block,
                    "order_quantity": qty,
                    "order_limit_price": limit_price,
                },
                session_id=candidate.session_id,
            ),
        )

    # Long-only buy proposal (beta). Order type LIMIT; session order-type policy
    # (Rule 12) is enforced at submission time, not here.
    order = Order(
        candidate_id=candidate.id,
        symbol=candidate.symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=qty,
        limit_price=limit_price,
        session_id=candidate.session_id,
    )
    return CreateOrderPlan(
        CREATE_ORDER_CREATE,
        order=order,
        events=(
            EventSpec(
                "order_created",
                message=f"order created for {candidate.symbol}",
                symbol=candidate.symbol,
                candidate_id=candidate.id,
                order_id=order.id,
                session_id=candidate.session_id,
            ),
            EventSpec(
                "candidate_transition",
                message="candidate approved -> ordered",
                symbol=candidate.symbol,
                candidate_id=candidate.id,
                order_id=order.id,
                payload={"from": "approved", "to": "ordered"},
                session_id=candidate.session_id,
            ),
        ),
    )


# ---- sell-intent -> order handoff (Phase 7) ------------------------------- #

# Terminal order statuses (no outgoing transitions) — an ordered intent whose
# order has reached one of these is no longer in flight.
_TERMINAL_ORDER_STATUSES = frozenset(
    {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}
)


def sell_intent_is_active(
    intent: SellIntent,
    order: Optional[Order],
    *,
    order_needs_review: bool = False,
) -> bool:
    """Whether a sell intent is still 'in flight' for the single-flight dedup /
    ``active_sell_intent_for``. Active = ``pending``/``approved`` (not yet
    ordered), or ``ordered`` with an Order still in a non-terminal status AND
    without an open ``needs_review`` broker-submit recovery. ``rejected``/
    ``expired`` intents, ``ordered`` intents whose order reached a terminal
    state (filled/canceled/rejected), and an ``ordered`` intent whose order is
    stranded in ``needs_review`` are all inactive — the symbol is eligible for a
    fresh protective intent (the residual re-evaluation path).

    ``order_needs_review`` (X-003 / ADR "Stranded-order eligibility (blocker)"):
    the caller passes whether ``order`` currently carries an OPEN
    ``needs_review`` broker-submit recovery record (D-017) — a broker order
    accepted upstream that local state can't otherwise confirm as live.
    Treating that as still-active would let a single stuck ``needs_review``
    order permanently block re-protection for the symbol forever, even though
    the recovery record and its operator alert stay independently visible (this
    function only decides single-flight eligibility, never recovery
    visibility). This function stays pure — the store fetches the recovery
    state under its own lock and passes the boolean in, mirroring how ``order``
    itself is fetched and passed in rather than looked up here.
    """

    if intent.status in (SellIntentStatus.PENDING, SellIntentStatus.APPROVED):
        return True
    if intent.status is SellIntentStatus.ORDERED:
        if order is None or order.status in _TERMINAL_ORDER_STATUSES:
            return False
        return not order_needs_review
    return False


def plan_create_order_for_sell_intent(
    *,
    intent: SellIntent,
    live_position_quantity: int,
    order_type: OrderType,
    limit_price: Optional[float],
) -> CreateOrderPlan:
    """The shared validation cascade + SELL order construction for the
    sell-intent→order dispatch (Phase 7). ``intent`` is known to exist and *not*
    already ORDERED (the store handles those first). No CAPI risk gate and no
    kill-switch/session block here — a protective exit reduces risk and its
    submission is gated separately at claim time (see the side/reason-aware claim).

    ``live_position_quantity`` is the symbol's current derived position quantity,
    re-read by the store under its lock: a sell may never exceed it (never a
    short — Rule 7 / long-only). The order carries ``sell_intent_id`` and
    ``candidate_id=None`` (the XOR origin); the ``correlation_id`` on both events
    is the intent id, so the whole protective-exit lifecycle is one filterable key.
    """

    if intent.status is not SellIntentStatus.APPROVED:
        # A precondition violation, not a "the approved handoff failed" case —
        # there is no `approved` state to self-heal FROM (the intent is either
        # not yet approved, already ordered/terminal, or a caller-contract bug
        # elsewhere). No expire; matches the pre-X-002 behavior for this branch.
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=SellIntentTransitionError(
                f"cannot order sell intent {intent.id} in status "
                f"{intent.status.value}; must be approved"
            ),
        )

    def _reject_and_self_heal(error: Exception) -> CreateOrderPlan:
        """X-002: every rejection below is a genuine "the approved handoff
        failed" case — self-heal `approved -> expired` atomically alongside the
        rejection, so the intent is never left stranded `approved` poisoning the
        single-flight dedup forever (`no_sell_intent_stranded_approved`)."""

        now = utcnow()
        expired = intent.model_copy(deep=True)
        expired.status = SellIntentStatus.EXPIRED
        expired.expired_at = now
        expired.updated_at = now
        expire_event = EventSpec(
            "sell_intent_transition",
            message=(
                f"sell intent approved -> expired (order dispatch rejected: "
                f"{error})"
            ),
            symbol=intent.symbol,
            payload={
                "from": "approved",
                "to": "expired",
                "reason": "dispatch_rejected",
            },
            session_id=intent.session_id,
            correlation_id=intent.id,
        )
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=error,
            expire_intent=expired,
            expire_event=expire_event,
        )

    qty = intent.target_quantity
    if qty is None or qty <= 0:
        return _reject_and_self_heal(
            InvalidOrderError(
                f"sell intent {intent.id} has no positive target_quantity"
            )
        )
    # Never a short (Rule 7 / long-only): the exit cannot exceed the live
    # position. Re-checked here against the freshly-read quantity so a race that
    # reduced the position (another fill) between approve and order cannot oversell.
    if qty > live_position_quantity:
        return _reject_and_self_heal(
            InvalidOrderError(
                f"sell intent {intent.id} target_quantity {qty} exceeds the live "
                f"{intent.symbol} position quantity {live_position_quantity} "
                f"(would create a short)"
            )
        )

    # Order-type/price coherence (Rule 12 exit types): a LIMIT sell needs a
    # finite positive limit; a MARKET sell must carry NO limit price. Do NOT run
    # limit_price_reason unconditionally (it would reject the MARKET exit path).
    if order_type is OrderType.LIMIT:
        bad_price = limit_price_reason(limit_price)
        if bad_price is not None:
            return _reject_and_self_heal(
                InvalidOrderError(
                    f"limit sell for intent {intent.id} needs a valid limit_price "
                    f"({bad_price})"
                )
            )
    elif limit_price is not None:
        return _reject_and_self_heal(
            InvalidOrderError(
                f"{order_type.value} sell for intent {intent.id} must not carry a "
                f"limit_price (got {limit_price!r})"
            )
        )

    order = Order(
        sell_intent_id=intent.id,
        symbol=intent.symbol,
        side=OrderSide.SELL,
        order_type=order_type,
        quantity=qty,
        limit_price=limit_price,
        session_id=intent.session_id,
    )
    return CreateOrderPlan(
        CREATE_ORDER_CREATE,
        order=order,
        events=(
            EventSpec(
                "order_created",
                message=f"protective sell order created for {intent.symbol}",
                symbol=intent.symbol,
                order_id=order.id,
                session_id=intent.session_id,
                correlation_id=intent.id,
            ),
            EventSpec(
                "sell_intent_transition",
                message="sell intent approved -> ordered",
                symbol=intent.symbol,
                order_id=order.id,
                payload={"from": "approved", "to": "ordered"},
                session_id=intent.session_id,
                correlation_id=intent.id,
            ),
        ),
    )


# ---- flatten_position (X-001, atomic manual-flatten) ---------------------- #

# FlattenPlan.outcome values:
FLATTEN_FLAT = "flat"                                   # no open position
FLATTEN_EXISTING = "existing"                           # return an existing intent as-is
FLATTEN_SUPERSEDE_AND_CREATE = "supersede_and_create"    # stand down + create fresh
FLATTEN_DENIED_HALTED = "denied_halted"                  # ADR-003: Halted, no override


@dataclass(frozen=True)
class FlattenPlan:
    """Pure outcome of the manual-flatten decision (X-001).

    Evaluated over state the store fetched ENTIRELY under ONE lock hold, so no
    concurrent writer — most critically a protection tick's own
    ``create_sell_intent`` call — can interleave between "decide" and "act".
    That interleaving was the actual defect: the route used to read the active
    intent, then LATER call ``create_sell_intent(MANUAL_FLATTEN, ...)`` as a
    SEPARATE lock hold; a protection tick's own create call could win the
    single-flight race in the gap, and the route never verified the ``reason``
    of what it got back — so a human's flatten could silently be handed a
    ``protection_floor`` intent, which a kill switch would then hold
    unsubmitted. This planner's caller (``StateStore.flatten_position``) never
    releases the lock between fetching this input and applying this plan.

    ``flat``: no open position; the caller (route) surfaces a 409.

    ``existing``: return ``existing_intent``/``existing_order`` as-is — either
    it is ALREADY the caller's own ``manual_flatten`` and has a real order
    (``ORDERED``; idempotent), or a ``protection_floor`` exit that is
    genuinely LIVE at the broker (executing; left alone, never captured or
    duplicated).

    ``supersede_and_create``: any active exit that is NOT yet live is stood
    down first (``supersede_*`` fields, applied in the SAME atomic block as
    the create below), then a fresh ``manual_flatten`` intent for
    ``target_quantity`` is inserted directly and dispatched through the same
    order-handoff machinery ``create_order_for_sell_intent`` uses — so the
    returned intent's ``reason`` is GUARANTEED ``manual_flatten``, never a
    deduped intent of a different reason. "Not yet live" covers: a
    ``protection_floor`` intent with no order at all, or a still-``created``
    order; AND a ``manual_flatten`` intent stranded ``pending``/``approved``
    with no order — reachable only via a crash between two separate commits
    in ``SqliteStateStore.flatten_position`` (see the inline comment below),
    never in ordinary operation. This is what closes X-001: nothing else can
    write to this symbol's sell intents between the supersede and the create,
    because both happen without ever releasing the lock.
    """

    outcome: str
    existing_intent: Optional[SellIntent] = None
    existing_order: Optional[Order] = None
    # Provenance for the ``existing`` deferral to a live PROTECTION_FLOOR exit
    # (INV-036): the audit record that a human flatten was received and deferred,
    # so the "click reads as success" is truthful and traceable. None on the
    # idempotent MANUAL_FLATTEN re-return (that intent is already the caller's own).
    deferral_event: Optional[EventSpec] = None
    supersede_order_cancel: Optional[Order] = None
    supersede_cancel_event: Optional[EventSpec] = None
    supersede_intent_expire: Optional[SellIntent] = None
    supersede_expire_event: Optional[EventSpec] = None
    target_quantity: int = 0


def plan_flatten_position(
    *,
    position: Position,
    active_intent: Optional[SellIntent],
    active_order: Optional[Order],
    trading_state: TradingState = TradingState.ACTIVE,
    override_active: bool = False,
    actor: str = COMMAND_ACTOR_SYSTEM,
) -> FlattenPlan:
    """Decide the manual-flatten outcome for one symbol.

    ``position`` is the LIVE derived position; ``active_intent`` is the
    symbol's current *active* sell intent (already filtered through
    :func:`sell_intent_is_active`, including the X-003 ``needs_review``
    exclusion) or ``None``; ``active_order`` is its linked order (if any). All
    three are read by the caller under the SAME lock hold this plan is applied
    under — the decision and the eventual write can never straddle a
    concurrent mutation.

    ADR-003 / wave 3e: ``trading_state`` is the current session's §8 FSM and
    ``override_active`` whether an audited emergency-reduce override is active for
    this symbol (both read under the same lock). An ordinary manual flatten is
    **denied in ``Halted``** (``FLATTEN_DENIED_HALTED`` → the store raises
    :class:`FlattenBlockedError` → 409) unless the override is active; it stays
    allowed in ``Active``/``Reducing`` (the pre-3e behavior). Gating at *creation*
    means a ``MANUAL_FLATTEN`` order is never even minted under ``Halted`` without
    authorization — and since ``flatten_position`` is the only producer of that
    reason, an existing manual-flatten order (born only when creation was allowed)
    stays claimable, so the submission gate is untouched.

    ``actor`` (REV-0002 F-002) is a pure pass-through: the store resolves the
    command actor and hands it in, and it is only stamped into the
    ``manual_flatten_deferred`` event's payload here — this planner never resolves
    identity itself, keeping it a pure function of its inputs.
    """

    if position.quantity <= 0:
        return FlattenPlan(FLATTEN_FLAT)

    if trading_state is TradingState.HALTED and not override_active:
        return FlattenPlan(FLATTEN_DENIED_HALTED)

    if active_intent is not None:
        if (
            active_intent.reason is SellReason.MANUAL_FLATTEN
            and active_intent.status is SellIntentStatus.ORDERED
        ):
            return FlattenPlan(
                FLATTEN_EXISTING,
                existing_intent=active_intent,
                existing_order=active_order,
            )
        # A protection_floor exit is active with an order that has left CREATED
        # (submitted/partially-filled/cancel-pending/timeout-quarantine): it is in
        # flight or live at the broker (INV-036), so LEAVE IT ALONE — never
        # double-exit, and never blind-cancel a possibly-live order (ADR-002:
        # a SUBMITTING / TIMEOUT_QUARANTINE order may already be working at the
        # venue, so routing it to the local-cancel supersede path below would be
        # exactly the unsafe blind action the quarantine machinery exists to
        # avoid). Deferring is the safe action for every non-CREATED status.
        # Record provenance so the human's flatten is auditable even though we
        # defer (closing the "click reads as success with no record" gap). The
        # payload carries the deferred order's status so a reader can tell a
        # confirmed-live exit from an in-flight/ambiguous one.
        if (
            active_intent.reason is SellReason.PROTECTION_FLOOR
            and active_order is not None
            and active_order.status is not OrderStatus.CREATED
        ):
            deferral_event = EventSpec(
                EventType.MANUAL_FLATTEN_DEFERRED.value,
                message=(
                    f"manual flatten for {position.symbol} deferred to the in-flight "
                    f"protection_floor exit (order {active_order.status.value})"
                ),
                symbol=position.symbol,
                order_id=active_order.id,
                payload={
                    "reason": "deferred_to_live_protection",
                    "order_status": active_order.status.value,
                    "deferred_intent_reason": active_intent.reason.value,
                    # Who commanded the flatten (REV-0002 F-002) — passed IN by the
                    # store, never resolved inside this pure planner.
                    "actor": actor,
                },
                session_id=active_order.session_id,
                correlation_id=active_intent.id,
            )
            return FlattenPlan(
                FLATTEN_EXISTING,
                existing_intent=active_intent,
                existing_order=active_order,
                deferral_event=deferral_event,
            )
        # Not live: supersede. A CREATED order cancels locally; a stranded
        # pending/approved intent with no order at all expires. This also
        # covers a MANUAL_FLATTEN intent found here at PENDING/APPROVED (not
        # ORDERED) with no order (X-001 follow-up, adversarial re-review
        # finding): in normal operation a fresh MANUAL_FLATTEN only sits at
        # PENDING/APPROVED transiently, mid-dispatch, under the SAME
        # continuous lock this function is always called within — reaching
        # here on a LATER call means a hard crash landed between the
        # intent-approve commit and the order-dispatch commit
        # (SqliteStateStore.flatten_position commits those as two separate
        # transactions; InMemoryStateStore's single _atomic() block cannot
        # produce this state at all). Treating a stranded MANUAL_FLATTEN as
        # "the existing exit" would silently no-op forever — HTTP 200,
        # order=None — and permanently poison single-flight dedup for the
        # symbol. Self-healing it here (same as a stranded protection_floor
        # intent) closes that window: the dead intent expires and a real
        # exit is created in its place.
        now = utcnow()
        supersede_order_cancel = None
        supersede_cancel_event = None
        supersede_intent_expire = None
        supersede_expire_event = None
        if active_order is not None:
            updated_order = active_order.model_copy(deep=True)
            updated_order.status = OrderStatus.CANCELED
            updated_order.canceled_at = now
            updated_order.updated_at = now
            supersede_order_cancel = updated_order
            supersede_cancel_event = EventSpec(
                "order_transition",
                message=(
                    f"order {active_order.symbol} created -> canceled "
                    f"(superseded by manual flatten)"
                ),
                symbol=active_order.symbol,
                order_id=active_order.id,
                payload={
                    "from": "created",
                    "to": "canceled",
                    "reason": "superseded_by_manual_flatten",
                },
                session_id=active_order.session_id,
                correlation_id=active_intent.id,
            )
        elif active_intent.status in (
            SellIntentStatus.PENDING,
            SellIntentStatus.APPROVED,
        ):
            updated_intent = active_intent.model_copy(deep=True)
            updated_intent.status = SellIntentStatus.EXPIRED
            updated_intent.expired_at = now
            updated_intent.updated_at = now
            supersede_intent_expire = updated_intent
            supersede_expire_event = EventSpec(
                "sell_intent_transition",
                message=(
                    f"sell intent {active_intent.status.value} -> expired "
                    f"(superseded by manual flatten)"
                ),
                symbol=active_intent.symbol,
                payload={
                    "from": active_intent.status.value,
                    "to": "expired",
                    "reason": "superseded_by_manual_flatten",
                },
                session_id=active_intent.session_id,
                correlation_id=active_intent.id,
            )
        return FlattenPlan(
            FLATTEN_SUPERSEDE_AND_CREATE,
            supersede_order_cancel=supersede_order_cancel,
            supersede_cancel_event=supersede_cancel_event,
            supersede_intent_expire=supersede_intent_expire,
            supersede_expire_event=supersede_expire_event,
            target_quantity=position.quantity,
        )

    return FlattenPlan(
        FLATTEN_SUPERSEDE_AND_CREATE, target_quantity=position.quantity
    )


# ---- submit-recovery ledger (D-017) --------------------------------------- #


def require_recovery_status(value: str, *, field: str = "cleanup_status") -> None:
    """Reject a recovery ``cleanup_status`` that is not one of the closed
    ``RECOVERY_STATUSES`` (AIR-004) — the same domain error the transition
    validator raises, so a record can never be *born* in an invalid state either.
    """

    if value not in RECOVERY_STATUSES:
        raise RecoveryTransitionError(
            f"{field} {value!r} is not a valid recovery status; "
            f"must be one of {sorted(RECOVERY_STATUSES)}"
        )


def recovery_status_event(
    prev_status: str, new_status: Optional[str]
) -> Optional[str]:
    """Validate a recovery ``cleanup_status`` transition and return the audit
    event type to write, or ``None`` when nothing should change (AIR-004).

    ``new_status is None`` is a bump-only update (retry_count) with no status
    change — a legal no-op that emits no event, regardless of the current status.
    A same-status "change" is likewise a no-op. Otherwise the transition must be
    one of the explicit allowed moves in ``RECOVERY_TRANSITIONS``
    (``unresolved -> resolved_canceled`` / ``unresolved -> needs_review``); an
    **unknown** status value or a **disallowed** move (notably reopening a
    terminal record back to ``unresolved``) raises
    :class:`RecoveryTransitionError` and the caller must leave the record and its
    audit trail unchanged. A move to needs-review writes
    ``submit_recovery_needs_review`` (a real untracked position — not "resolved");
    a clean cancel writes ``submit_recovery_resolved``. Shared so both stores
    validate and emit identically.
    """

    if new_status is None or new_status == prev_status:
        return None
    if new_status not in RECOVERY_STATUSES:
        raise RecoveryTransitionError(
            f"unknown recovery cleanup_status {new_status!r}; "
            f"must be one of {sorted(RECOVERY_STATUSES)}"
        )
    if new_status not in RECOVERY_TRANSITIONS.get(prev_status, frozenset()):
        raise RecoveryTransitionError(
            f"illegal recovery transition {prev_status!r} -> {new_status!r} "
            f"(no silent reopen of a terminal record)"
        )
    if new_status == RECOVERY_NEEDS_REVIEW:
        return "submit_recovery_needs_review"
    return "submit_recovery_resolved"


# ---- claim_order_for_submission (D-017) ----------------------------------- #


@dataclass(frozen=True)
class ClaimPlan:
    """Pure outcome of the submission-claim decision (the store has already
    fetched the order and both sessions). ``outcome`` is one of
    :data:`CLAIM_CLAIMED` / :data:`CLAIM_BLOCKED` / :data:`CLAIM_SKIPPED`. On a
    claim, ``order`` is the updated (``SUBMITTING``) copy the store persists and
    ``event`` the ``order_submission_claimed`` audit row. On a block, ``reason``
    is set and nothing is written.
    """

    outcome: str
    order: Optional[Order] = None
    event: Optional[EventSpec] = None
    reason: Optional[str] = None


def _buy_claim_hold_reason(
    own_session: Optional[SessionRecord],
    current_session: Optional[SessionRecord],
) -> Optional[str]:
    """The original Rule 8 submission gate, unchanged: a held order is blocked
    against its OWN session (D-013a) and, failing that, the live session as a
    process-wide emergency stop. This is exactly the pre-Phase-7 logic, extracted
    verbatim so every BUY caller and its tests are provably byte-for-byte
    untouched (§5.2) — the sell-side branch is layered *around* it, never inside
    it."""

    hold = session_submission_block_reason(own_session)
    if hold is None:
        current_block = order_intent_block_reason(current_session)
        if current_block is not None:
            hold = f"current_{current_block}"
    return hold


def _claim_hold_reason(
    order: Order,
    own_session: Optional[SessionRecord],
    current_session: Optional[SessionRecord],
    sell_reason: Optional[SellReason],
    *,
    quarantined: bool = False,
) -> Optional[str]:
    """Why this ``CREATED`` order must not be claimed for submission, or ``None``.

    Phase 7 side/reason-aware gate (§5.2 / D-P2). A well-formed protective/flatten
    SELL short-circuits the BUY control checks based on its owning intent's
    ``reason``. The qualifying gate is deliberately strict — ``side is SELL`` AND
    ``sell_intent_id`` set AND ``candidate_id`` is ``None`` AND a *known* reason —
    so a mislabeled or origin-corrupt order can never inherit the bypass; it falls
    through to the strict BUY path instead (fail-safe).

    * ``MANUAL_FLATTEN`` → never held at *submission*: a manual-flatten order,
      once it EXISTS, always reaches the broker. ADR-003 (wave 3e) moved the
      ``Halted``-denial to *creation* (``plan_flatten_position``): a
      ``MANUAL_FLATTEN`` order is only ever minted when the flatten was authorized
      (``Active``/``Reducing``, or an emergency-reduce override under ``Halted``),
      and ``flatten_position`` is its sole producer — so an existing one is, by
      construction, already authorized and stays claimable here. **Deliberate,
      documented scoping (wave 3e review LOW):** an order created while ``Active``
      is still submitted if the kill switch engages before the submission sweep
      claims it — the Halted-deny is at *issuance*, and a locally-``CREATED`` order
      (not yet at the venue, so not literally "in-flight") is an exit the operator
      already commanded, not new intent. Asymmetric with autonomous
      ``PROTECTION_FLOOR`` (still held by the kill switch here) BY DESIGN: a human
      command outranks autonomous protection (D-P2). Pinned by
      ``test_manual_flatten_created_in_active_submits_under_later_halt``.
      Buys-paused / closed / unknown-session are likewise bypassed (D-P2 spirit).
    * ``PROTECTION_FLOOR`` → bypass ``buys_paused`` / ``session_closed`` /
      ``unknown_session`` (a lingering position must stay exitable after close),
      **but stays blocked by the kill switch** on EITHER the own or the current
      session — the operator's all-stop halts even autonomous protection, which is
      then wound down separately (a held protective order is expired, not left
      forever).
    * Anything else (a BUY, or a degenerate SELL) → quarantine gate, then the
      unchanged BUY gate.

    ``quarantined`` (wave 3b / ADR-001): the order's symbol is quarantined by a
    broker overfill. An autonomous exposure-increasing BUY must be HELD — "no new
    autonomous spawn while quarantined" applies to a *pre-existing* CREATED order
    too, not only to newly-created intent (``create_order_for_candidate`` already
    blocks the latter). Protective/flatten SELLs above are exempt: an exit reduces
    risk (and the position guards already stop a sell of a non-positive book), so
    the operator can always wind risk down. Checked before the buy control gate so
    the (more actionable) quarantine reason surfaces.
    """

    is_protective_sell = (
        OrderSide(order.side) is OrderSide.SELL
        and order.sell_intent_id is not None
        and order.candidate_id is None
        and sell_reason is not None
    )
    if is_protective_sell:
        if sell_reason is SellReason.MANUAL_FLATTEN:
            return None
        if sell_reason is SellReason.PROTECTION_FLOOR:
            if kill_switch_block_reason(own_session) is not None:
                return "kill_switch"
            if kill_switch_block_reason(current_session) is not None:
                return "current_kill_switch"
            return None
        # An unrecognized future reason falls through to the strict path.
    if quarantined:
        return "symbol_quarantined"
    return _buy_claim_hold_reason(own_session, current_session)


def plan_claim_order_for_submission(
    *,
    order: Optional[Order],
    own_session: Optional[SessionRecord],
    current_session: Optional[SessionRecord],
    sell_reason: Optional[SellReason] = None,
    quarantined: bool = False,
) -> ClaimPlan:
    """Decide whether a ``CREATED`` order may be claimed for submission.

    ``own_session`` is the order's originating session (D-013a: a held order is
    gated against its OWN session, not merely the live one, so a kill-switched
    order from a prior session can't slip through after a date rollover mints a
    fresh permissive session). ``current_session`` is the live session, checked
    as a process-wide emergency stop. ``sell_reason`` is the owning
    ``SellIntent.reason`` for a SELL order (``None`` for a BUY, or when the intent
    can't be resolved) — the store fetches it under the same lock. ``quarantined``
    is whether the order's symbol is quarantined by a broker overfill (ADR-001,
    wave 3b) — the store derives it from the event log under the same lock; it
    holds an autonomous BUY but never a protective/flatten exit. The store calls
    this under its lock, so the control state read here cannot change between the
    decision and the ``CREATED → SUBMITTING`` write the store then applies.
    """

    if order is None or order.status is not OrderStatus.CREATED:
        # No longer submittable: a session close cancelled it, it was already
        # claimed, or it never existed. Nothing to do.
        return ClaimPlan(CLAIM_SKIPPED)

    hold = _claim_hold_reason(
        order, own_session, current_session, sell_reason, quarantined=quarantined
    )
    if hold is not None:
        return ClaimPlan(CLAIM_BLOCKED, reason=hold)

    updated = order.model_copy(deep=True)
    updated.status = OrderStatus.SUBMITTING
    updated.updated_at = utcnow()
    event = EventSpec(
        "order_submission_claimed",
        message=f"submission claimed for {order.symbol}",
        symbol=order.symbol,
        candidate_id=order.candidate_id,
        order_id=order.id,
        payload={"from": "created", "to": "submitting"},
        session_id=order.session_id,
    )
    return ClaimPlan(CLAIM_CLAIMED, order=updated, event=event)


# ---- transition_order ----------------------------------------------------- #

# OrderTransitionPlan.outcome values:
ORDER_TRANSITION_REJECT = "reject"  # raise `error`
ORDER_TRANSITION_NOOP = "noop"      # nothing changed; store returns the order unchanged
ORDER_TRANSITION_APPLY = "apply"    # persist `order` (fully updated) + write `event`


@dataclass(frozen=True)
class OrderTransitionPlan:
    """Pure outcome of :meth:`StateStore.transition_order` (the order already
    fetched by the store). ``order`` on an ``apply`` is the fully-updated copy —
    status/filled_quantity/broker_order_id and the relevant terminal timestamp
    already set — so the store just persists it and writes ``event``.
    """

    outcome: str
    error: Optional[Exception] = None
    order: Optional[Order] = None
    event: Optional[EventSpec] = None


def require_bool(value: object, *, field: str) -> None:
    """Reject a non-``bool`` control/flag value at the store boundary (AIR-005).

    Strict: only ``True``/``False`` pass. A string (``"false"``), an int
    (``0``/``1`` — note ``isinstance(1, bool)`` is ``False``), a list/dict, or
    ``None`` is rejected with :class:`InvalidControlValueError` and no mutation.
    This is what stops a ``{"engaged": "false"}`` payload — a truthy non-empty
    string — from *engaging* the kill switch (an emergency-stop inversion).
    """

    if not isinstance(value, bool):
        raise InvalidControlValueError(
            f"{field} must be a bool, not {type(value).__name__} {value!r}"
        )


def require_status_enum(value: object, enum_cls: type, *, field: str) -> None:
    """Reject a non-enum status argument at the store boundary (AIR-009).

    ``value`` must be an actual member of ``enum_cls`` — a bare string like
    ``"pending"`` does **not** qualify even though ``enum_cls`` is a ``str``-enum
    (``isinstance("pending", CandidateStatus)`` is ``False``). This is what makes
    both stores reject strings/bools/``None`` identically instead of one silently
    coercing and the other leaking ``AttributeError``. Raises
    :class:`InvalidStatusError`; performs no mutation.
    """

    if not isinstance(value, enum_cls):
        raise InvalidStatusError(
            f"{field} must be a {enum_cls.__name__} instance, not "
            f"{type(value).__name__} {value!r}"
        )


def plan_transition_order(
    *,
    order: Order,
    new_status: OrderStatus,
    filled_quantity: Optional[int],
    broker_order_id: Optional[str],
    actor: str = COMMAND_ACTOR_SYSTEM,
) -> OrderTransitionPlan:
    """Decide an order transition — the shared logic (legality, monotonic
    filled-quantity, the true-no-op rule, and the D-008 ``order_transition`` vs
    ``order_fill_progress`` audit split) that was duplicated between the stores.

    ``new_status`` must be an ``OrderStatus`` instance (AIR-009): a bare string
    or a bool/None is rejected up front, before any legality check, so both
    stores behave identically.
    """

    require_status_enum(new_status, OrderStatus, field="new_status")
    current = order.status
    status_changed = new_status is not current
    if status_changed and new_status not in ORDER_TRANSITIONS.get(current, set()):
        return OrderTransitionPlan(
            ORDER_TRANSITION_REJECT,
            error=OrderTransitionError(
                f"illegal order transition {current.value} -> {new_status.value}"
            ),
        )

    # AIR-001: reaching SUBMITTED means the broker accepted the order and handed
    # back an id — the only key we can poll/cancel by. A status change *into*
    # SUBMITTED without a non-empty broker id would persist an untrackable
    # "submitted" order, so reject it here in the shared planner (both stores
    # enforce it identically, not just the monitoring caller). The effective id
    # is the one being assigned, falling back to whatever the order already
    # carries; a same-status no-op/reaffirm is not re-validated.
    if status_changed and new_status is OrderStatus.SUBMITTED:
        effective_broker_id = (
            broker_order_id if broker_order_id is not None else order.broker_order_id
        )
        if not (isinstance(effective_broker_id, str) and effective_broker_id.strip()):
            return OrderTransitionPlan(
                ORDER_TRANSITION_REJECT,
                error=OrderTransitionError(
                    f"cannot mark order {order.id} SUBMITTED without a non-empty "
                    f"broker_order_id (AIR-001)"
                ),
            )

    # Bound + monotonic filled_quantity (Fix 5). Out-of-range or backward progress
    # raises and writes nothing. Equality is allowed (handled as a no-op below).
    if filled_quantity is not None:
        bad = filled_quantity_reason(order, filled_quantity)
        if bad is not None:
            return OrderTransitionPlan(
                ORDER_TRANSITION_REJECT,
                error=InvalidOrderError(
                    f"invalid filled_quantity {filled_quantity} for order "
                    f"{order.id} (qty {order.quantity}, current "
                    f"{order.filled_quantity}): {bad}"
                ),
            )

    qty_changed = filled_quantity is not None and filled_quantity != order.filled_quantity
    broker_changed = (
        broker_order_id is not None and broker_order_id != order.broker_order_id
    )

    # True no-op (status unchanged and nothing else changed): write no audit row
    # and mutate nothing — same rule transition_candidate uses (D-008).
    if not status_changed and not qty_changed and not broker_changed:
        return OrderTransitionPlan(ORDER_TRANSITION_NOOP)

    previous_filled = order.filled_quantity
    updated = order.model_copy(deep=True)
    if qty_changed:
        assert filled_quantity is not None  # qty_changed implies filled_quantity set
        updated.filled_quantity = filled_quantity
    if broker_changed:
        updated.broker_order_id = broker_order_id
    if status_changed:
        updated.status = new_status
        ts_field = ORDER_TIMESTAMP.get(new_status)
        if ts_field and getattr(updated, ts_field) is None:
            setattr(updated, ts_field, utcnow())
    updated.updated_at = utcnow()

    if status_changed:
        event = EventSpec(
            "order_transition",
            message=f"order {current.value} -> {new_status.value}",
            symbol=updated.symbol,
            candidate_id=updated.candidate_id,
            order_id=updated.id,
            # UC-002 (REV-0002 F-002 class): stamp the command actor so a manual
            # cancel's audit event records who did it; routine engine transitions
            # default to COMMAND_ACTOR_SYSTEM.
            payload={"from": current.value, "to": new_status.value, "actor": actor},
            session_id=updated.session_id,
        )
    else:
        # Same status, but fill progressed (or a broker id was assigned). Not a
        # no-op — record it with the before/after quantity, not a generic
        # same-status row (D-008).
        payload: dict[str, Any] = {
            "status": current.value,
            "previous_filled_quantity": previous_filled,
            "filled_quantity": updated.filled_quantity,
        }
        if broker_changed:
            payload["broker_order_id"] = broker_order_id
        event = EventSpec(
            "order_fill_progress",
            message=(
                f"order {updated.symbol} fill progress "
                f"{previous_filled} -> {updated.filled_quantity}"
            ),
            symbol=updated.symbol,
            candidate_id=updated.candidate_id,
            order_id=updated.id,
            payload=payload,
            session_id=updated.session_id,
        )
    return OrderTransitionPlan(ORDER_TRANSITION_APPLY, order=updated, event=event)


# ---- routine order-status ExecutionEvent emission (WO-0007a) -------------- #
#
# Additive: `plan_transition_order`/`plan_claim_order_for_submission` above are
# UNTOUCHED (their signatures, legality, and existing test surface stay exactly
# as they were). The store applies the plan as before, then ALSO calls this
# helper and appends the resulting ExecutionEvent (if any) in the SAME atomic
# write as the existing order-row + audit-event write, so the routine
# claim/ack/fill/cancel/reject lifecycle finally has a corroborating entry in
# the durable execution_events log (closing the reconstructability gap for
# WO-0007b), without making `orders.status` itself event-sourced. See
# work/active/WO-0007a-order-status-eventing/design-decision.md.
#
# PROVENANCE (source/authority): derived per transition from `(old_status,
# new_status)` by `_routine_event_provenance` below (WO-0009 — faithful
# provenance, replacing WO-0007a's conservative uniform ENGINE/LOCAL). It follows
# the same convention the rest of the log uses (`execution_event_for_fill`,
# `plan_resolve_timeout_quarantine`, `plan_reconcile_resolve_order`):
#   * ENGINE/LOCAL for the genuinely engine-local transitions — the claim
#     (`CREATED -> SUBMITTING`, a pre-broker engine decision) and a `CANCELED` of
#     an order the broker never confirmed (no `broker_order_id`): a never-submitted
#     `CREATED` order cancelled locally (session close, flatten supersede, manual),
#     OR the `SUBMITTING -> CANCELED` release when a submit failed before the venue
#     returned an id — the no-zombie cancel of a BUY whose session closed mid-submit
#     (`app/monitoring.py`). `broker_order_id` is assigned only when `SUBMITTED` is
#     recorded, so its absence reliably means the broker never saw this order.
#   * BROKER_REST/BROKER_AUTHORITATIVE for the broker-OBSERVED facts — `SUBMITTED`
#     (only reached with a broker id, AIR-001), `PARTIALLY_FILLED`/`FILLED` (fills
#     seen via the reconcile poll), `REJECTED` (broker rejection via poll/TQ), and
#     a broker-confirmed `CANCELED` (old status past `CREATED`). `authority` is the
#     ADR-001-critical field (`BROKER_AUTHORITATIVE` wins conflicts); it is correct
#     in every case here, and the engine paths never over-claim it.
#   * `source` is `BROKER_REST` because every routine broker observation currently
#     arrives via REST poll/ack — no `transition_order`/`claim_order_for_submission`
#     caller is websocket-driven (verified: every caller in app/monitoring.py and
#     app/facade is REST/local). A future stream-ingestion path would pass
#     `BROKER_STREAM`; threading that from the callers is deferred until such a
#     path exists (WO-0009 gate, "alternative rejected"). This is NOT the read-flip
#     (WO-0007b) — `orders.status` stays authoritative; no projector consumes these.

_EXECUTION_EVENT_FOR_ROUTINE_STATUS: dict[OrderStatus, ExecutionEventType] = {
    OrderStatus.SUBMITTED: ExecutionEventType.SUBMITTED,
    OrderStatus.PARTIALLY_FILLED: ExecutionEventType.PARTIALLY_FILLED,
    OrderStatus.FILLED: ExecutionEventType.FILLED,
    OrderStatus.CANCELED: ExecutionEventType.CANCELED,
    OrderStatus.REJECTED: ExecutionEventType.REJECTED,
}

# These three share their dedupe_key FORMAT (`f"{status.value}:{order_id}"`)
# with `plan_resolve_timeout_quarantine` / `plan_reconcile_resolve_order`
# (`_EXECUTION_EVENT_FOR_RESOLVED_STATUS` / `_RECONCILE_RESOLVE_EXEC` above).
# Safe today only because at most one writer family ever reaches a given
# terminal status for a given order (design doc item 5) — enforced below by
# the TIMEOUT_QUARANTINE guard, not merely argued in a comment.
_SHARED_FORMAT_KEY_STATUSES = frozenset(
    {OrderStatus.SUBMITTED, OrderStatus.CANCELED, OrderStatus.REJECTED}
)


def _routine_event_provenance(
    order: Order, new_status: OrderStatus
) -> tuple[EventSource, EventAuthority]:
    """Faithful ``(source, authority)`` for a routine order-status event (WO-0009).
    See the PROVENANCE note above.

    Engine-local iff the transition is the pre-broker claim, or a ``CANCELED`` of an
    order the broker never confirmed — one with no ``broker_order_id``. That covers
    both a never-submitted ``CREATED`` order (session close / flatten supersede /
    manual never-submitted cancel) AND the ``SUBMITTING -> CANCELED`` release when a
    submit failed before the venue returned an id (the no-zombie cancel of a BUY
    whose session closed mid-submit — ``app/monitoring.py``). ``broker_order_id`` is
    assigned only when ``SUBMITTED`` is recorded, so its absence reliably means the
    broker never saw this order. Every other routine-emitted status
    (``SUBMITTED``/``PARTIALLY_FILLED``/``FILLED``/``REJECTED`` and a broker-confirmed
    ``CANCELED``) is a broker-observed fact.

    (Using ``broker_order_id is None`` rather than ``old_status is CREATED`` fixes a
    real over-claim the WO-0009 adversarial-verify pass found: the
    ``SUBMITTING -> CANCELED`` submit-failure release is engine-local but has old
    status ``SUBMITTING``, so the old proxy stamped it BROKER_AUTHORITATIVE.)
    """

    # Engine-INITIATED, pre-broker-confirmation statuses: the claim
    # (CREATED->SUBMITTING), the claim release (SUBMITTING->CREATED, WO-0007b), and
    # a cancel REQUEST (->CANCEL_PENDING, WO-0007b). None of these is a
    # broker-authored fact — CANCEL_PENDING especially must not be authoritative, or
    # it would wrongly win an ADR-001 conflict against a real late broker FILL
    # (transitions.py: CANCEL_PENDING->FILLED).
    if new_status in (
        OrderStatus.SUBMITTING,
        OrderStatus.CREATED,
        OrderStatus.CANCEL_PENDING,
    ):
        return EventSource.ENGINE, EventAuthority.LOCAL
    if new_status is OrderStatus.CANCELED and order.broker_order_id is None:
        return EventSource.ENGINE, EventAuthority.LOCAL
    return EventSource.BROKER_REST, EventAuthority.BROKER_AUTHORITATIVE


def execution_event_for_routine_transition(
    order: Order,
    new_status: OrderStatus,
    filled_quantity: Optional[int],
    occurrence: Optional[int] = None,
) -> Optional[ExecutionEvent]:
    """The ``ExecutionEvent`` (if any) the ROUTINE order-lifecycle write path —
    ``claim_order_for_submission``, ``transition_order``, ``plan_close_session``'s
    CREATED-BUY cancel, and ``plan_flatten_position``'s supersede-cancel — should
    co-append alongside its existing order-row + audit-event write.

    ``order`` is the order's state BEFORE this transition (i.e. its ``.status``
    is the OLD status) — needed to (a) detect the ``PARTIALLY_FILLED ->
    PARTIALLY_FILLED`` same-status fill-progress self-loop versus first entry
    into ``PARTIALLY_FILLED``, and (b) enforce the TIMEOUT_QUARANTINE
    defense-in-depth guard below. Returns ``None`` when ``new_status`` isn't one
    this WO instruments, so a caller can invoke this unconditionally after every
    successful apply and simply skip appending on ``None``.

    ``occurrence`` is 0-based and only meaningful for ``CREATED -> SUBMITTING``
    (the claim), the one transition that can repeat (the single cycle in the
    order-status graph, design doc item 1) — the caller must supply the count of
    PRIOR ``SUBMIT_PENDING`` execution events for this order_id so each repeat
    gets a distinct, gapless dedupe_key (``submit_pending:{order_id}:{n}``).
    ``None``/omitted defaults to ``0`` (a bare first claim).

    ``source``/``authority`` are derived per transition by
    ``_routine_event_provenance`` (WO-0009) from ``(order.status, new_status)`` —
    see the PROVENANCE note above.
    """

    source, authority = _routine_event_provenance(order, new_status)

    # Defense-in-depth (WO-0007b, adversarial-verify finding): TIMEOUT_QUARANTINE is
    # a legal ORDER_TRANSITIONS edge from SUBMITTING, but it is set ONLY via the
    # evented path (plan_transition_order_evented, which co-writes the
    # TIMEOUT_QUARANTINE ExecutionEvent). A routine transition_order that reached it
    # would flip orders.status with NO event, silently diverging the order-status
    # projection (project_order_status would reconstruct the prior status). No call
    # site does this today; this refuses it loudly rather than leaving a footgun
    # for the read-flip (Stage D). The order stays un-transitioned (the helper runs
    # before the store's atomic write).
    assert new_status is not OrderStatus.TIMEOUT_QUARANTINE, (
        "execution_event_for_routine_transition: TIMEOUT_QUARANTINE must be set via "
        "the evented path (plan_transition_order_evented), not routine "
        f"transition_order (order {order.id}) — the routine path emits no "
        "TIMEOUT_QUARANTINE event, which would diverge the order-status projection"
    )

    if new_status is OrderStatus.SUBMITTING:
        n = occurrence if occurrence is not None else 0
        return ExecutionEvent(
            event_type=ExecutionEventType.SUBMIT_PENDING,
            source=source,
            authority=authority,
            dedupe_key=f"submit_pending:{order.id}:{n}",
            symbol=order.symbol,
            side=OrderSide(order.side),
            order_id=order.id,
            session_id=order.session_id,
        )

    if new_status is OrderStatus.CREATED and order.status is OrderStatus.SUBMITTING:
        # WO-0007b: the SUBMITTING -> CREATED claim release — the only ->CREATED
        # transition_order edge (transitions.py: CREATED is a target of SUBMITTING
        # alone). Guarded on old status SUBMITTING so a same-status/other call is
        # not mistaken for a release. Occurrence-keyed like the claim so repeated
        # claim/release cycles stay gapless (`release:{order_id}:{n}`, n = prior
        # SUBMIT_RELEASED count, supplied by the caller). Without this event a
        # released order projects as SUBMITTING under latest-wins and the claim
        # gate strands it.
        n = occurrence if occurrence is not None else 0
        return ExecutionEvent(
            event_type=ExecutionEventType.SUBMIT_RELEASED,
            source=source,
            authority=authority,
            dedupe_key=f"release:{order.id}:{n}",
            symbol=order.symbol,
            side=OrderSide(order.side),
            order_id=order.id,
            session_id=order.session_id,
        )

    if new_status is OrderStatus.CANCEL_PENDING:
        # WO-0007b: entry into CANCEL_PENDING (cancel requested at the broker). Emit
        # ONCE on entry so a live pending-cancel order is representable in the
        # projection. The self-loop (CANCEL_PENDING -> CANCEL_PENDING, a late fill
        # progressing) leaves status unchanged and emits nothing — latest-wins
        # already yields CANCEL_PENDING. CANCEL_PENDING is not re-enterable
        # (transitions.py), so a bare `cancel_pending:{order_id}` key is unique.
        if order.status is OrderStatus.CANCEL_PENDING:
            return None
        return ExecutionEvent(
            event_type=ExecutionEventType.CANCEL_PENDING,
            source=source,
            authority=authority,
            dedupe_key=f"cancel_pending:{order.id}",
            symbol=order.symbol,
            side=OrderSide(order.side),
            order_id=order.id,
            session_id=order.session_id,
        )

    if new_status is OrderStatus.PARTIALLY_FILLED and order.status is OrderStatus.PARTIALLY_FILLED:
        # Same-status fill-progress self-loop. `filled_quantity` is monotonic
        # (bound-checked by `plan_transition_order`), so this key is guaranteed
        # distinct per repeat.
        return ExecutionEvent(
            event_type=ExecutionEventType.PARTIALLY_FILLED,
            source=source,
            authority=authority,
            dedupe_key=f"order_fill_progress:{order.id}:{filled_quantity}",
            symbol=order.symbol,
            side=OrderSide(order.side),
            order_id=order.id,
            session_id=order.session_id,
        )

    exec_type = _EXECUTION_EVENT_FOR_ROUTINE_STATUS.get(new_status)
    if exec_type is None:
        return None

    if new_status in _SHARED_FORMAT_KEY_STATUSES:
        # Defense-in-depth (design-review Finding D): refuse to build a
        # shared-format key for an order currently in TIMEOUT_QUARANTINE — that
        # key format is reserved for `plan_resolve_timeout_quarantine` /
        # `plan_reconcile_resolve_order`. Cannot happen today (no routine call
        # site drives a TIMEOUT_QUARANTINE order through this path), but this
        # enforces the invariant in code rather than leaving it as doc-only
        # reasoning a future refactor could silently violate.
        assert order.status is not OrderStatus.TIMEOUT_QUARANTINE, (
            "execution_event_for_routine_transition: refusing to build a "
            f"shared-format {new_status.value!r} key for order {order.id} — it "
            "is currently TIMEOUT_QUARANTINE, and that key format is reserved "
            "for plan_resolve_timeout_quarantine / plan_reconcile_resolve_order "
            "(WO-0007a design doc, item 5)"
        )

    return ExecutionEvent(
        event_type=exec_type,
        source=source,
        authority=authority,
        dedupe_key=f"{new_status.value}:{order.id}",
        symbol=order.symbol,
        side=OrderSide(order.side),
        order_id=order.id,
        session_id=order.session_id,
    )


# ---- order-status backfill (WO-0007b Stage D read-flip migration) --------- #
#
# After the read-flip, get_order derives status from project_order_status. An order
# whose status predates WO-0007a eventing has NO lifecycle events, so it would
# project CREATED (the default) — a regression. At init the store backfills a
# single synthetic reconstruction event for each such order so the projection yields
# its (pre-flip authoritative) column status. Mirrors the FILL backfill
# (_backfill_fill_events) and the trading-state column heal. Only fires for orders
# with NO lifecycle events (projection==CREATED) whose column is non-CREATED — it
# never overrides an order that already has events, so it cannot mis-heal a genuine
# divergence. Deterministic dedupe_key => idempotent across re-init / replay.
_STATUS_TO_BACKFILL_EVENT: dict[OrderStatus, ExecutionEventType] = {
    OrderStatus.SUBMITTING: ExecutionEventType.SUBMIT_PENDING,
    OrderStatus.SUBMITTED: ExecutionEventType.SUBMITTED,
    OrderStatus.PARTIALLY_FILLED: ExecutionEventType.PARTIALLY_FILLED,
    OrderStatus.CANCEL_PENDING: ExecutionEventType.CANCEL_PENDING,
    OrderStatus.FILLED: ExecutionEventType.FILLED,
    OrderStatus.CANCELED: ExecutionEventType.CANCELED,
    OrderStatus.REJECTED: ExecutionEventType.REJECTED,
    OrderStatus.TIMEOUT_QUARANTINE: ExecutionEventType.TIMEOUT_QUARANTINE,
}


def order_status_backfill_event(order: Order) -> Optional[ExecutionEvent]:
    """The synthetic reconstruction event that makes ``project_order_status`` yield
    ``order.status`` for a pre-WO-0007a order that has no lifecycle events. Returns
    ``None`` for ``CREATED`` (the projector's default — no event needed). Provenance
    is ``RECONCILIATION``/``SYNTHETIC`` (a deterministic migration-time inference,
    not a live broker/engine fact)."""

    event_type = _STATUS_TO_BACKFILL_EVENT.get(order.status)
    if event_type is None:
        return None
    return ExecutionEvent(
        event_type=event_type,
        source=EventSource.RECONCILIATION,
        authority=EventAuthority.SYNTHETIC,
        dedupe_key=f"backfill_status:{order.id}",
        symbol=order.symbol,
        side=OrderSide(order.side),
        order_id=order.id,
        session_id=order.session_id,
    )


# ---- evented order transition (wave 3c: TIMEOUT_QUARANTINE, ADR-002) ------ #


@dataclass(frozen=True)
class OrderEventedTransitionPlan:
    """Pure outcome of an order status transition whose **first durable write is
    an ``ExecutionEvent``** (wave 3c / ADR-002), co-written atomically with a
    specific audit event and the order-row read-model flip.

    Legality + the fully-updated order come from :func:`plan_transition_order`
    (so the shared ``ORDER_TRANSITIONS`` machine and the AIR-001 broker-id guard
    still apply); this attaches the ``ExecutionEvent`` that is the durable truth
    and a caller-chosen audit event. ``outcome`` reuses the ``ORDER_TRANSITION_*``
    constants: REJECT (illegal — writes nothing, raise ``error``), NOOP (same
    status — writes nothing), APPLY (persist ``order`` + ``audit_event`` +
    ``execution_event`` in ONE atomic block).
    """

    outcome: str
    error: Optional[Exception] = None
    order: Optional[Order] = None
    audit_event: Optional[EventSpec] = None
    execution_event: Optional[ExecutionEvent] = None


def plan_transition_order_evented(
    *,
    order: Order,
    new_status: OrderStatus,
    execution_event_type: ExecutionEventType,
    audit_event_type: str,
    dedupe_key: str,
    source: EventSource,
    authority: EventAuthority,
    broker_order_id: Optional[str] = None,
    reason: Optional[str] = None,
    ts_event: Optional[datetime] = None,
) -> OrderEventedTransitionPlan:
    """Plan a status transition that records an ``ExecutionEvent`` as its durable
    truth (the status column becomes a co-written read-model — the honest scope of
    ``event_truth`` for an order-lifecycle fact; see docs/SPINE_WAVE3C_PLAN.md C5).

    Reuses :func:`plan_transition_order` for legality (the transition must be in
    ``ORDER_TRANSITIONS``) and the updated order (status/timestamps/broker id +
    the AIR-001 "SUBMITTED needs a broker id" guard). ``dedupe_key`` makes the
    append idempotent on replay (INV-5): re-applying the same quarantine/resolution
    is a no-op at the event-log layer.
    """

    base = plan_transition_order(
        order=order,
        new_status=new_status,
        filled_quantity=None,
        broker_order_id=broker_order_id,
    )
    if base.outcome == ORDER_TRANSITION_REJECT:
        return OrderEventedTransitionPlan(ORDER_TRANSITION_REJECT, error=base.error)
    if base.outcome == ORDER_TRANSITION_NOOP:
        return OrderEventedTransitionPlan(ORDER_TRANSITION_NOOP)

    execution_event = ExecutionEvent(
        event_type=execution_event_type,
        source=source,
        authority=authority,
        dedupe_key=dedupe_key,
        ts_event=ts_event,
        symbol=order.symbol,
        side=OrderSide(order.side),
        order_id=order.id,
        session_id=order.session_id,
    )
    payload: dict[str, Any] = {"from": order.status.value, "to": new_status.value}
    if reason is not None:
        payload["reason"] = reason
    if broker_order_id is not None:
        payload["broker_order_id"] = broker_order_id
    audit_event = EventSpec(
        audit_event_type,
        message=(
            f"order {order.symbol} {order.status.value} -> {new_status.value}"
            + (f" ({reason})" if reason else "")
        ),
        symbol=order.symbol,
        candidate_id=order.candidate_id,
        order_id=order.id,
        payload=payload,
        session_id=order.session_id,
    )
    return OrderEventedTransitionPlan(
        ORDER_TRANSITION_APPLY,
        order=base.order,
        audit_event=audit_event,
        execution_event=execution_event,
    )


def plan_quarantine_timed_out_order(
    order: Order, *, reason: Optional[str] = None
) -> OrderEventedTransitionPlan:
    """``SUBMITTING → TIMEOUT_QUARANTINE`` for an ambiguous submit (ADR-002). The
    quarantine is OUR local decision (the submit's outcome is unknown), hence
    ``ENGINE``/``LOCAL`` provenance — it is not a broker-reported fact."""

    return plan_transition_order_evented(
        order=order,
        new_status=OrderStatus.TIMEOUT_QUARANTINE,
        execution_event_type=ExecutionEventType.TIMEOUT_QUARANTINE,
        audit_event_type="order_timeout_quarantined",
        dedupe_key=f"timeout_quarantine:{order.id}",
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        reason=reason,
    )


_EXECUTION_EVENT_FOR_RESOLVED_STATUS: dict[OrderStatus, ExecutionEventType] = {
    OrderStatus.SUBMITTED: ExecutionEventType.SUBMITTED,
    OrderStatus.REJECTED: ExecutionEventType.REJECTED,
    OrderStatus.CANCELED: ExecutionEventType.CANCELED,
}


def plan_resolve_timeout_quarantine(
    order: Order,
    new_status: OrderStatus,
    *,
    broker_order_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> OrderEventedTransitionPlan:
    """``TIMEOUT_QUARANTINE → {SUBMITTED, REJECTED, CANCELED}`` resolved by a
    read-only targeted ``client_order_id`` query (ADR-002). The venue's answer is
    a broker-authoritative fact (``BROKER_REST``/``BROKER_AUTHORITATIVE``).
    Resolving to ``SUBMITTED`` requires the ``broker_order_id`` the query
    returned (AIR-001); the normal reconcile poll then ingests any fills, so
    ``FILLED`` is reached via ``SUBMITTED``, never directly (INV-9 — conflict C4)."""

    exec_type = _EXECUTION_EVENT_FOR_RESOLVED_STATUS.get(new_status)
    if exec_type is None:
        raise ValueError(
            f"cannot resolve a timeout quarantine to {new_status.value}; must be "
            f"one of {sorted(s.value for s in _EXECUTION_EVENT_FOR_RESOLVED_STATUS)}"
        )
    return plan_transition_order_evented(
        order=order,
        new_status=new_status,
        execution_event_type=exec_type,
        audit_event_type="order_timeout_quarantine_resolved",
        dedupe_key=f"{new_status.value}:{order.id}",
        source=EventSource.BROKER_REST,
        authority=EventAuthority.BROKER_AUTHORITATIVE,
        broker_order_id=broker_order_id,
        reason=reason,
    )


# ---- reconcile not-found resolution (wave 4e-3) --------------------------- #

# The only terminals the mass-report reconcile may resolve an absent open order to.
# FILLED is deliberately excluded — a position-affecting terminal must flow through
# a fill (INV-9), never a bare status flip.
_RECONCILE_RESOLVE_EXEC: dict[OrderStatus, ExecutionEventType] = {
    OrderStatus.REJECTED: ExecutionEventType.REJECTED,
    OrderStatus.CANCELED: ExecutionEventType.CANCELED,
}


def plan_reconcile_resolve_order(
    order: Order,
    new_status: OrderStatus,
    *,
    reason: Optional[str] = None,
) -> OrderEventedTransitionPlan:
    """``SUBMITTED → REJECTED`` / ``PARTIALLY_FILLED → CANCELED`` (fills preserved)
    for an open order that a read-only targeted ``client_order_id`` query confirmed
    ABSENT at the venue, after the ``open_check_missing_retries`` bound (§7 / wave
    4e-3). The venue's confirmed-absence is a broker-authoritative fact
    (``BROKER_REST`` / ``BROKER_AUTHORITATIVE``); the order-status column becomes a
    co-written read-model of the ``ExecutionEvent`` (the honest ``event_truth`` scope
    for an order-lifecycle fact, mirror of wave 3c). ``FILLED`` is never a target —
    a position-affecting terminal flows through a fill (INV-9)."""

    exec_type = _RECONCILE_RESOLVE_EXEC.get(new_status)
    if exec_type is None:
        raise ValueError(
            f"cannot reconcile-resolve an order to {new_status.value}; must be one "
            f"of {sorted(s.value for s in _RECONCILE_RESOLVE_EXEC)}"
        )
    return plan_transition_order_evented(
        order=order,
        new_status=new_status,
        execution_event_type=exec_type,
        audit_event_type="order_reconcile_resolved",
        dedupe_key=f"reconcile_resolve:{order.id}:{new_status.value}",
        source=EventSource.BROKER_REST,
        authority=EventAuthority.BROKER_AUTHORITATIVE,
        reason=reason,
    )


# ---- close_session -------------------------------------------------------- #


@dataclass(frozen=True)
class SessionClosePlan:
    """Pure plan for closing a session (the store has already resolved and
    validated the session and fetched what will be touched).

    ``candidate_events`` is parallel to the ``open_candidates`` the store passed
    in (one per candidate, same order); ``order_events`` parallel to
    ``created_orders``. ``snapshots`` are the position rows to insert.
    ``close_event`` is the single ``session_closed`` summary. The store applies
    the actual mutations (EXPIRED / CANCELED / CLOSED + timestamps) with its own
    primitive, using ``now`` — kept storage-specific because one store mutates
    live objects in place and the other UPDATEs by id.
    """

    candidate_events: tuple[EventSpec, ...]
    order_events: tuple[EventSpec, ...]
    sell_intent_events: tuple[EventSpec, ...]
    snapshots: tuple[PositionSnapshot, ...]
    close_event: EventSpec


def plan_close_session(
    *,
    session: SessionRecord,
    open_candidates: list[Candidate],
    created_orders: list[Order],
    open_sell_intents: list[SellIntent],
    nonzero_positions: list[Position],
    now: datetime,
    actor: str = COMMAND_ACTOR_SYSTEM,
) -> SessionClosePlan:
    """Build the audit events + position snapshots for a session close (D-007 /
    D-013a). ``open_candidates`` are this session's PENDING/APPROVED candidates,
    ``created_orders`` its still-CREATED (never-submitted) **BUY** orders (a
    CREATED SELL is a protective/flatten exit that must remain submittable
    post-close, Phase 7 — the store filters those out), ``open_sell_intents`` its
    PENDING/APPROVED sell intents (expired like candidates), and
    ``nonzero_positions`` every symbol with a nonzero derived position. The
    counts drive the summary event.
    """

    candidate_events = tuple(
        EventSpec(
            "candidate_transition",
            message=f"candidate {candidate.status.value} -> expired (session close)",
            symbol=candidate.symbol,
            candidate_id=candidate.id,
            payload={
                "from": candidate.status.value,
                "to": "expired",
                "reason": "session_close",
            },
            session_id=session.id,
        )
        for candidate in open_candidates
    )
    order_events = tuple(
        EventSpec(
            "order_transition",
            message=f"order {order.symbol} created -> canceled (session close)",
            symbol=order.symbol,
            candidate_id=order.candidate_id,
            order_id=order.id,
            payload={"from": "created", "to": "canceled", "reason": "session_close"},
            session_id=session.id,
        )
        for order in created_orders
    )
    sell_intent_events = tuple(
        EventSpec(
            "sell_intent_transition",
            message=f"sell intent {si.status.value} -> expired (session close)",
            symbol=si.symbol,
            order_id=None,
            payload={
                "from": si.status.value,
                "to": "expired",
                "reason": "session_close",
            },
            session_id=session.id,
            correlation_id=si.id,
        )
        for si in open_sell_intents
    )
    snapshots = tuple(
        PositionSnapshot(
            session_id=session.id,
            symbol=pos.symbol,
            quantity=pos.quantity,
            cost_basis=pos.cost_basis,
            average_price=pos.average_price,
            captured_at=now,
        )
        for pos in nonzero_positions
    )
    close_event = EventSpec(
        "session_closed",
        message=(
            f"session closed ({len(open_candidates)} candidates expired, "
            f"{len(created_orders)} created orders canceled, "
            f"{len(open_sell_intents)} sell intents expired, "
            f"{len(snapshots)} positions snapshotted)"
        ),
        session_id=session.id,
        payload={
            "expired_candidates": len(open_candidates),
            "canceled_orders": len(created_orders),
            "expired_sell_intents": len(open_sell_intents),
            "position_snapshots": len(snapshots),
            # W2-SESS (REV-0013): who closed the session — so the audit can
            # attribute a manual close to the operator (default "system" for an
            # engine/automatic close). Mirrors the kill-switch / buys-paused /
            # cancel (UC-002) actor stamping.
            "actor": actor,
        },
    )
    return SessionClosePlan(
        candidate_events=candidate_events,
        order_events=order_events,
        sell_intent_events=sell_intent_events,
        snapshots=snapshots,
        close_event=close_event,
    )


# =========================================================================== #
# Signal Seat ingest (ADR-009 / WO-0102, spec 01-schema + 02-lifecycle)
#
# Pure decision + event construction for external-producer signal ingestion,
# shared verbatim by InMemoryStateStore and SqliteStateStore so the two stores
# behave identically (dual-store parity) and every signal is reconstructable
# purely from its SIGNAL_* events (event-truth / replay).
# =========================================================================== #

# A-3 freshness bounds (spec 02-lifecycle §3). Defaults; the server_max_ttl is
# Settings-tunable and passed in per call. Skew/ttl bounds are spec constants.
SIGNAL_FUTURE_SKEW_SECONDS = 30
SIGNAL_STALE_SECONDS = 24 * 3600
SIGNAL_TTL_MIN_SECONDS = 30
SIGNAL_TTL_MAX_SECONDS = 86400

# SignalIngestResult.outcome values live on the leaf model kernel (app.models) so
# the route can share them without importing app.store (import-linter contract 5);
# re-exported here for the store/planner call sites.


def signal_dedupe_key(prefix: str, *parts: str) -> str:
    """Collision-safe composite ``ExecutionEvent.dedupe_key`` (auto-reviewer P1
    #2). A naive ``":"``-joined key is ambiguous: ``("a:b", "c")`` and
    ``("a", "b:c")`` both join to ``"a:b:c"`` — and a producer-supplied
    (including validation-quarantined, never format-checked) ``signal_id`` can
    itself contain ``":"``, so two genuinely distinct ``(producer_id,
    signal_id)`` pairs could collide onto ONE dedupe key. That collision is not
    cosmetic: ``append_execution_event``/``_insert_execution_event`` treat a
    dedupe-key match as "already appended" and silently drop the SECOND
    creation event — the second record persists in the read path (a live
    insert) but never replays back from the event log (replay/live divergence),
    and any rail/budget fold that keys off the event log undercounts it.

    Each part is length-prefixed (netstring-style: ``"<decimal length>:<part>"``,
    joined by ``"|"``) — an INJECTIVE encoding: two different tuples of strings
    always encode to different strings, regardless of any separator characters
    embedded in a part, because the length prefix pins exactly where each part
    ends. Used for EVERY signal event dedupe key this module composes."""

    encoded = "|".join(f"{len(part)}:{part}" for part in parts)
    return f"{prefix}:{encoded}"


def safe_quarantine_symbol(raw_symbol: str) -> str:
    """A findable, ticker-domain symbol for a quarantine record, or ``"UNKNOWN"``.

    The canonical ``normalize_symbol`` domain is the store's — a route cannot
    import it (import-linter contract 5) — so the quarantine symbol is normalized
    HERE (round-13). A non-ASCII value is never upper-cased into a different
    ticker; an ASCII-but-out-of-domain value (``"."``, ``"$BAD"``, over-length)
    that ``normalize_symbol`` rejects becomes ``"UNKNOWN"`` rather than being
    stored as an instrument the ``?symbol=`` filter can never match."""

    stripped = raw_symbol.strip()
    if not stripped or not stripped.isascii():
        return "UNKNOWN"
    try:
        return normalize_symbol(stripped)
    except ValueError:
        return "UNKNOWN"


def signal_canonical_hash(payload: dict[str, Any]) -> str:
    """Deterministic sha256 over the canonical proposal JSON (dedupe/conflict
    detection). Keys sorted, compact separators, datetimes as ISO-8601 — so an
    identical proposal always hashes identically across processes and both
    stores, and any content change flips the hash (duplicate-conflict)."""

    def _default(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError(f"unhashable proposal value: {value!r}")

    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=_default
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_signal_proposal_payload(
    *,
    signal_id: str,
    symbol: str,
    direction: str,
    issued_at: Optional[datetime],
    ttl_seconds: Optional[int],
    suggested_quantity: Optional[int],
    suggested_limit_price: Optional[float],
    thesis: str,
    provenance: dict[str, str],
    raw_fields: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """The canonical proposal dict both stores hash (and embed in the
    duplicate-conflict event). Excludes ``producer_id`` (the namespace, not
    content) and any server-computed field, so the hash reflects only what the
    producer sent — identical resend → identical hash (idempotent replay), any
    change → conflict.

    ``raw_fields`` (auto-reviewer P1 #1) is the raw offending content of a
    validation-quarantine (``app.models.SignalRecord.raw_fields`` — the same
    value, not a second copy). For a MALFORMED-with-usable-signal_id request the
    route normalizes every unparseable/absent field to ``None`` regardless of
    what was actually sent, so two structurally-different malformed bodies
    (e.g. ``issued_at: "not-date"`` vs ``issued_at: "also-not-date"``) would
    otherwise hash IDENTICALLY on their normalized fields alone — the second
    would then read as an idempotent 200 replay of the first, silently dropping
    a distinct attributable fact and never debiting the A-4 invalid budget.
    Folding ``raw_fields`` into the hash (``None`` for a well-formed proposal,
    which never changes its hash) makes any distinct malformed content correctly
    diverge into the existing SIGNAL_DUPLICATE_CONFLICT path instead."""

    return {
        "signal_id": signal_id,
        "symbol": symbol,
        "direction": direction,
        "issued_at": issued_at,
        "ttl_seconds": ttl_seconds,
        "suggested_quantity": suggested_quantity,
        "suggested_limit_price": suggested_limit_price,
        "thesis": thesis,
        "provenance": provenance,
        "raw_fields": raw_fields,
    }


@dataclass(frozen=True)
class SignalFreshness:
    """A-3 freshness classification of a well-formed proposal (pure)."""

    expires_at: Optional[datetime]
    status: SignalStatus  # RECEIVED | QUARANTINED | EXPIRED
    event_type: Optional[ExecutionEventType]
    quarantine_reason: Optional[str]
    detected_by: Optional[str]  # "ingest" for DOA expiry
    ttl_nulled: bool  # ttl_out_of_range → store ttl_seconds NULL + raw_fields
    raw_fields: Optional[dict[str, str]]


def effective_signal_status(record: SignalRecord, *, now: datetime) -> SignalStatus:
    """Lazy expiry at read (02-lifecycle rule A4; auto-reviewer P2 #3): a
    RECEIVED record whose ``expires_at`` has already elapsed is EFFECTIVELY
    ``EXPIRED`` even before WO-0104's periodic sweep durably transitions it.
    ``GET /api/signals`` (and the future WO-0103 approve path) must treat
    ``now >= expires_at`` as EXPIRED regardless of the stored status — the
    operator panel must never present a stale thesis as still actionable.

    Pure and read-only: it returns the EFFECTIVE status for display, never
    mutates the record or appends an event (a real transition to EXPIRED is
    either the durable sweep, WO-0104, or the atomic re-check inside a future
    approval command, WO-0103). Any non-RECEIVED (already-terminal) status, or a
    RECEIVED record not yet past its deadline, is returned unchanged. A
    RECEIVED record with no ``expires_at`` (should not occur — every RECEIVED
    record has one) is left as-is defensively rather than raising."""

    if (
        record.status is SignalStatus.RECEIVED
        and record.expires_at is not None
        and now >= record.expires_at
    ):
        return SignalStatus.EXPIRED
    return record.status


def classify_signal_freshness(
    *,
    issued_at: datetime,
    ttl_seconds: int,
    received_at: datetime,
    server_max_ttl_seconds: int,
) -> SignalFreshness:
    """Server-owned freshness (spec 02-lifecycle §3), injected clock via
    ``received_at``. Order: ttl-bounds (must be valid to compute a deadline),
    then future/stale skew, then ``expires_at = min(received_at + server_max_ttl,
    issued_at + ttl_seconds)``, then dead-on-arrival. A stale/expired signal can
    never be approved (rule A3) because it never reaches RECEIVED."""

    if ttl_seconds < SIGNAL_TTL_MIN_SECONDS or ttl_seconds > SIGNAL_TTL_MAX_SECONDS:
        return SignalFreshness(
            expires_at=None,
            status=SignalStatus.QUARANTINED,
            event_type=ExecutionEventType.SIGNAL_QUARANTINED,
            quarantine_reason="ttl_out_of_range",
            detected_by=None,
            ttl_nulled=True,
            raw_fields={"ttl_seconds": str(ttl_seconds)},
        )
    if issued_at > received_at + timedelta(seconds=SIGNAL_FUTURE_SKEW_SECONDS):
        return SignalFreshness(
            expires_at=None,
            status=SignalStatus.QUARANTINED,
            event_type=ExecutionEventType.SIGNAL_QUARANTINED,
            quarantine_reason="issued_at_future",
            detected_by=None,
            ttl_nulled=False,
            raw_fields=None,
        )
    if issued_at < received_at - timedelta(seconds=SIGNAL_STALE_SECONDS):
        return SignalFreshness(
            expires_at=None,
            status=SignalStatus.QUARANTINED,
            event_type=ExecutionEventType.SIGNAL_QUARANTINED,
            quarantine_reason="issued_at_stale",
            detected_by=None,
            ttl_nulled=False,
            raw_fields=None,
        )
    expires_at = min(
        received_at + timedelta(seconds=server_max_ttl_seconds),
        issued_at + timedelta(seconds=ttl_seconds),
    )
    if expires_at <= received_at:
        return SignalFreshness(
            expires_at=expires_at,
            status=SignalStatus.EXPIRED,
            event_type=ExecutionEventType.SIGNAL_EXPIRED,
            quarantine_reason=None,
            detected_by="ingest",
            ttl_nulled=False,
            raw_fields=None,
        )
    return SignalFreshness(
        expires_at=expires_at,
        status=SignalStatus.RECEIVED,
        event_type=ExecutionEventType.SIGNAL_RECEIVED,
        quarantine_reason=None,
        detected_by=None,
        ttl_nulled=False,
        raw_fields=None,
    )


def signal_record_event(
    record: SignalRecord,
    event_type: ExecutionEventType,
    *,
    cycle_budget_limit: Optional[int] = None,
    detected_by: Optional[str] = None,
) -> ExecutionEvent:
    """The per-record creation ExecutionEvent (SIGNAL_RECEIVED / terminal-at-ingest
    SIGNAL_QUARANTINED / SIGNAL_EXPIRED). Carries the full record snapshot so replay
    reconstructs the SignalRecord byte-identically in both stores. All signal events
    are EngineSource/LOCAL (nothing broker-authoritative). ``dedupe_key`` makes the
    single creation append idempotent (defense-in-depth); a later transition event
    (WO-0103/0104) uses a distinct key. ``cycle_budget_limit`` is stamped on every
    attributable-terminal-at-ingest rejection (spec 02-lifecycle §2) so the
    non-refilling budget is reconstructable from the log alone (WO-0104 folds it)."""

    payload: dict[str, Any] = {"record": record.model_dump(mode="json")}
    if cycle_budget_limit is not None:
        payload["cycle_budget_limit"] = cycle_budget_limit
    if detected_by is not None:
        payload["detected_by"] = detected_by
    return ExecutionEvent(
        event_type=event_type,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        dedupe_key=signal_dedupe_key(
            "signal_create", record.producer_id, record.signal_id
        ),
        symbol=record.symbol,
        payload=payload,
    )


def signal_duplicate_conflict_event(
    *,
    existing: SignalRecord,
    new_payload_hash: str,
    conflicting_proposal: dict[str, Any],
    cycle_budget_limit: int,
) -> ExecutionEvent:
    """The audit-only SIGNAL_DUPLICATE_CONFLICT event: a different-payload replay
    of an existing (producer_id, signal_id). EXCLUDED from the lifecycle fold — the
    original record's state is untouched (live path AND replay). Coalesced to one
    event per (producer_id, signal_id, new_hash) via ``dedupe_key``."""

    # JSON-safe the embedded proposal (datetimes → ISO) so the SQLite payload
    # round-trips identically to the in-memory dict (dual-store parity).
    safe_proposal = {
        key: (value.isoformat() if isinstance(value, datetime) else value)
        for key, value in conflicting_proposal.items()
    }
    return ExecutionEvent(
        event_type=ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        dedupe_key=signal_dedupe_key(
            "signal_conflict",
            existing.producer_id,
            existing.signal_id,
            new_payload_hash,
        ),
        symbol=existing.symbol,
        payload={
            "producer_id": existing.producer_id,
            "signal_id": existing.signal_id,
            "original_record_id": existing.id,
            "original_payload_hash": existing.payload_hash,
            "new_payload_hash": new_payload_hash,
            "conflicting_proposal": safe_proposal,
            "cycle_budget_limit": cycle_budget_limit,
        },
    )


@dataclass(frozen=True)
class SignalIngestPlan:
    """Pure outcome of an ingest decision (existing record fetched by the store)."""

    outcome: str
    record: Optional[SignalRecord]        # to insert (new records only)
    event: Optional[ExecutionEvent]       # to append (None for idempotent replay)
    result_record: SignalRecord           # what the caller returns (new or existing)


def plan_signal_ingest(
    *,
    existing: Optional[SignalRecord],
    producer_id: str,
    signal_id: str,
    symbol: str,
    direction: str,
    issued_at: Optional[datetime],
    ttl_seconds: Optional[int],
    suggested_quantity: Optional[int],
    suggested_limit_price: Optional[float],
    thesis: str,
    provenance: dict[str, str],
    payload_hash: str,
    canonical_proposal: dict[str, Any],
    validation_failed: bool,
    raw_fields: Optional[dict[str, str]],
    received_at: datetime,
    server_max_ttl_seconds: int,
    cycle_budget_limit: int,
) -> SignalIngestPlan:
    """Decide a signal ingest (pure). Dedupe on (producer_id, signal_id):

    * existing + identical ``payload_hash`` → idempotent replay (no event).
    * existing + different hash → SIGNAL_DUPLICATE_CONFLICT (audit-only, no row).
    * new + Pydantic-validation-failed → terminal QUARANTINED("validation") + raw.
    * new + well-formed → A-3 freshness classification (RECEIVED / skew|ttl
      QUARANTINED / DOA EXPIRED).
    """

    if existing is not None:
        if existing.payload_hash == payload_hash:
            return SignalIngestPlan(
                outcome=SIGNAL_REPLAYED,
                record=None,
                event=None,
                result_record=existing,
            )
        return SignalIngestPlan(
            outcome=SIGNAL_CONFLICT,
            record=None,
            event=signal_duplicate_conflict_event(
                existing=existing,
                new_payload_hash=payload_hash,
                conflicting_proposal=canonical_proposal,
                cycle_budget_limit=cycle_budget_limit,
            ),
            result_record=existing,
        )

    # New record. Malformed-but-attributable (Pydantic verdict from the route) is a
    # terminal validation-quarantine: the raw offender is preserved in raw_fields
    # and expires_at is uncomputable/NULL (never approvable, so no deadline). The
    # typed freshness fields carry whatever the route's safe accessors extracted —
    # which is None IFF that field itself is malformed, and the valid parsed value
    # otherwise (auto-review round 8: null only the field that is actually
    # malformed, mirroring SignalRecord's nullability contract; advisory fields
    # were already preserved this way).
    if validation_failed:
        # A well-typed but OUT-OF-RANGE ttl_seconds (positive, yet outside
        # [MIN, MAX]) is not valid freshness data to surface as normalized typed
        # data on the quarantine record: null it and record it as an offender,
        # matching the freshness path's ttl_out_of_range handling (auto-review
        # round 10). A valid in-range ttl is preserved (round-8 fidelity).
        record_raw_fields = dict(raw_fields or {})
        record_ttl = ttl_seconds
        if record_ttl is not None and not (
            SIGNAL_TTL_MIN_SECONDS <= record_ttl <= SIGNAL_TTL_MAX_SECONDS
        ):
            record_raw_fields.setdefault("ttl_seconds", str(record_ttl))
            record_ttl = None
        record = SignalRecord(
            producer_id=producer_id,
            signal_id=signal_id,
            status=SignalStatus.QUARANTINED,
            # Normalize to the ticker domain (or UNKNOWN) so the quarantine record
            # is findable by ?symbol= and never carries an impossible instrument
            # (round-13 :138).
            symbol=safe_quarantine_symbol(symbol),
            direction=direction,
            issued_at=issued_at,
            ttl_seconds=record_ttl,
            expires_at=None,
            received_at=received_at,
            raw_fields=record_raw_fields,
            suggested_quantity=suggested_quantity,
            suggested_limit_price=suggested_limit_price,
            thesis=thesis,
            provenance=provenance,
            payload_hash=payload_hash,
            quarantine_reason="validation",
            quarantined_at=received_at,
            created_at=received_at,
            updated_at=received_at,
        )
        return SignalIngestPlan(
            outcome=SIGNAL_QUARANTINED_VALIDATION,
            record=record,
            event=signal_record_event(
                record,
                ExecutionEventType.SIGNAL_QUARANTINED,
                cycle_budget_limit=cycle_budget_limit,
            ),
            result_record=record,
        )

    assert issued_at is not None and ttl_seconds is not None
    fresh = classify_signal_freshness(
        issued_at=issued_at,
        ttl_seconds=ttl_seconds,
        received_at=received_at,
        server_max_ttl_seconds=server_max_ttl_seconds,
    )
    record = SignalRecord(
        producer_id=producer_id,
        signal_id=signal_id,
        status=fresh.status,
        symbol=symbol,
        direction=direction,
        issued_at=issued_at,
        ttl_seconds=None if fresh.ttl_nulled else ttl_seconds,
        expires_at=fresh.expires_at,
        received_at=received_at,
        raw_fields=fresh.raw_fields,
        suggested_quantity=suggested_quantity,
        suggested_limit_price=suggested_limit_price,
        thesis=thesis,
        provenance=provenance,
        payload_hash=payload_hash,
        quarantine_reason=fresh.quarantine_reason,
        quarantined_at=(
            received_at if fresh.status is SignalStatus.QUARANTINED else None
        ),
        expired_at=received_at if fresh.status is SignalStatus.EXPIRED else None,
        created_at=received_at,
        updated_at=received_at,
    )
    if fresh.status is SignalStatus.RECEIVED:
        outcome = SIGNAL_RECEIVED_OK
        event = signal_record_event(record, ExecutionEventType.SIGNAL_RECEIVED)
    elif fresh.status is SignalStatus.EXPIRED:
        outcome = SIGNAL_EXPIRED_AT_INGEST
        event = signal_record_event(
            record,
            ExecutionEventType.SIGNAL_EXPIRED,
            cycle_budget_limit=cycle_budget_limit,
            detected_by="ingest",
        )
    else:  # freshness QUARANTINED (skew / ttl_out_of_range)
        outcome = SIGNAL_QUARANTINED_FRESHNESS
        event = signal_record_event(
            record,
            ExecutionEventType.SIGNAL_QUARANTINED,
            cycle_budget_limit=cycle_budget_limit,
        )
    return SignalIngestPlan(
        outcome=outcome, record=record, event=event, result_record=record
    )
