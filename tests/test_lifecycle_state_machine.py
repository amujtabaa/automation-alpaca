"""Wave 1 Part B (D-018) — a Hypothesis state-machine harness over the whole
candidate/order/fill/session/kill-switch lifecycle, driven against BOTH stores
and the controllable :class:`SimBrokerAdapter`.

Every serious defect in this project's history was a *temporal-sequence* bug
found by luck of tracing the right interleaving (session orphaning D-009, the
kill-switch date-rollover bypass D-013a, the F-001 submit TOCTOU, the F-002
orphaned broker order). A ``RuleBasedStateMachine`` attacks that whole class by
*generating* interleavings: it fires the real store/loop operations in random
orders and asserts a set of safety invariants after **every** action. The
invariants below are the system's steady-state safety contract, distilled from
``docs/01_ARCHITECTURE.md``'s non-negotiables, D-013a, D-016, and the Wave 0
fixes.

Async note: Hypothesis rules are synchronous, so each machine instance owns one
persistent asyncio event loop and runs every store/loop coroutine on it via
``self._run`` — one loop for the instance's whole life keeps the store's
``asyncio.Lock`` (and the SQLite connection) valid across rules. The machine is
run against memory and SQLite as two ``TestCase`` subclasses; the SQLite one
closes its connection on teardown (ResourceWarning is an error, F-008).
"""

from __future__ import annotations

import asyncio
import os
import tempfile

from hypothesis import settings
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    invariant,
    multiple,
    rule,
)
from hypothesis import strategies as st

from app.broker.adapter import BrokerFill, BrokerOrderUpdate
from app.broker.sim import SimBrokerAdapter
from app.config import Settings
from app.models import (
    RECOVERY_OPEN_STATUSES,
    CandidateStatus,
    OrderStatus,
    utcnow,
)
from app.monitoring import _submit_pending_orders, run_monitoring_tick
from app.store.base import (
    CandidateTransitionError,
    InvalidOrderError,
    OrderIntentBlockedError,
    OrderTransitionError,
    RiskLimitBlockedError,
    RiskLimits,
    SessionAlreadyClosedError,
    SessionClosedError,
    UnknownEntityError,
)
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

_SYMBOLS = ["AAPL", "MSFT", "TSLA"]
_SETTINGS = Settings()

# Statuses from which a manual cancel makes sense (mirrors routes_trading).
_CANCELLABLE = frozenset(
    {
        OrderStatus.CREATED,
        OrderStatus.SUBMITTING,
        OrderStatus.SUBMITTED,
        OrderStatus.PARTIALLY_FILLED,
    }
)


class LifecycleMachine(RuleBasedStateMachine):
    """Drives the real backend through random lifecycle interleavings.

    Subclassed per store implementation (see the bottom of the file). Rules
    catch only the exceptions that are a *legitimate* outcome of a racing
    interleaving (a closed session, an illegal transition because state moved,
    a control block); anything else propagates and fails the test — which is the
    whole point.
    """

    candidates = Bundle("candidates")
    orders = Bundle("orders")

    # Overridden per store subclass.
    def new_store(self):  # pragma: no cover - overridden
        raise NotImplementedError

    def __init__(self) -> None:
        super().__init__()
        self._loop = asyncio.new_event_loop()
        self.sim = SimBrokerAdapter()
        self._sfid = 0  # monotonic source_fill_id counter (global uniqueness)
        self.store = self.new_store()
        self._run(self.store.initialize())

    def _run(self, coro):
        return self._loop.run_until_complete(coro)

    def _next_sfid(self) -> str:
        self._sfid += 1
        return f"sfid-{self._sfid}"

    def teardown(self) -> None:
        try:
            # Close the SQLite connection synchronously (teardown has no
            # concurrency; awaiting close() from this loop is also fine). Avoids
            # a ResourceWarning (promoted to an error suite-wide, F-008).
            conn = getattr(self.store, "_conn", None)
            if conn is not None:
                conn.close()
            db_path = getattr(self, "_db_path", None)
            if db_path and os.path.exists(db_path):
                os.remove(db_path)
        finally:
            self._loop.close()

    # ------------------------------------------------------------------ #
    # Rules — each returns bundle members via multiple() (possibly empty)
    # ------------------------------------------------------------------ #
    @rule(
        target=candidates,
        symbol=st.sampled_from(_SYMBOLS),
        quantity=st.integers(min_value=1, max_value=50),
        limit=st.floats(min_value=0.5, max_value=50.0),
    )
    def create_candidate(self, symbol, quantity, limit):
        try:
            cand = self._run(
                self.store.create_candidate(
                    symbol, suggested_quantity=quantity, suggested_limit_price=round(limit, 2)
                )
            )
        except SessionClosedError:
            return multiple()  # closed session — no candidate, expected
        return multiple(cand.id)

    @rule(target=orders, candidate=candidates)
    def approve_and_dispatch(self, candidate):
        """Model the approve route: transition APPROVED, dispatch, and revert on
        any post-approval failure (never strand APPROVED)."""

        cand = self._run(self.store.get_candidate(candidate))
        if cand is None or cand.status is not CandidateStatus.PENDING:
            return multiple()
        self._run(self.store.transition_candidate(candidate, CandidateStatus.APPROVED))
        try:
            order = self._run(
                self.store.create_order_for_candidate(candidate, risk_limits=RiskLimits())
            )
        except (
            OrderIntentBlockedError,
            RiskLimitBlockedError,
            InvalidOrderError,
            CandidateTransitionError,
        ):
            self._run(self.store.revert_candidate_approval(candidate))
            return multiple()
        return multiple(order.id)

    @rule()
    def monitoring_tick(self):
        """The real submit(claim) + reconcile + recover tick — the integration
        heart. Never raises (the loop is crash-proof by contract)."""

        self._run(run_monitoring_tick(self.store, self.sim, _SETTINGS))

    @rule()
    def submit_pending_only(self):
        """Run ONLY the submit phase (claim + submit), not reconcile/recover.

        In isolation from the recovery phase, an armed mid-submit cancel race
        (see ``arm_submit_cancel_race``) leaves the F-002 orphan *observable
        between rules*: the broker order live upstream, its local order terminal,
        and an open recovery record — the exact state
        ``no_live_untracked_broker_order`` guards, with the invariant now passing
        via its ``open_recovery`` disjunct rather than trivially via ``tracked``.
        A full ``monitoring_tick`` submits AND recovers in one call, healing the
        orphan before any invariant checkpoint could observe it."""

        self._run(_submit_pending_orders(self.store, self.sim))

    @rule()
    def arm_submit_cancel_race(self):
        """Arm a one-shot F-002 race: the next order to reach the broker is
        manually canceled *inside* ``submit_order`` — after its broker id is
        minted and live, before the local ``SUBMITTED`` persist — so it ends
        ``CANCELED`` locally while live at the broker. That is the orphan the
        durable recovery ledger (D-017) exists to reconcile.

        Without this seam the random machine can never construct the orphan:
        every submit persists ``SUBMITTED`` uninterrupted, so the recovery path
        (and ``no_live_untracked_broker_order``'s ``open_recovery`` branch) would
        be dead code. The hook disarms itself so only the next submit races."""

        async def cancel_mid_submit(order, broker_id):
            self.sim.set_on_submit(None)  # one-shot: only this submit races
            try:
                await self.store.transition_order(order.id, OrderStatus.CANCELED)
            except (OrderTransitionError, UnknownEntityError):
                # Raced to terminal another way between claim and hook — no orphan
                # this time, itself a legitimate interleaving.
                pass

        self.sim.set_on_submit(cancel_mid_submit)

    @rule(order=orders, portion=st.floats(min_value=0.1, max_value=1.0))
    def script_broker_fill(self, order, portion):
        """Queue a (partial or full) fill on the broker for an open order; the
        next monitoring_tick reconciles it into the store."""

        o = self._run(self.store.get_order(order))
        if o is None or o.broker_order_id is None:
            return
        if o.status not in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
            return
        remaining = o.quantity - o.filled_quantity
        if remaining <= 0:
            return
        delta = max(1, min(remaining, round(remaining * portion)))
        cumulative = o.filled_quantity + delta
        status = OrderStatus.FILLED if cumulative >= o.quantity else OrderStatus.PARTIALLY_FILLED
        self.sim.script(
            o.broker_order_id,
            [
                BrokerOrderUpdate(
                    status,
                    cumulative,
                    [BrokerFill(self._next_sfid(), delta, o.limit_price or 1.0, utcnow())],
                )
            ],
        )

    @rule(order=orders)
    def cancel_order(self, order):
        """Model the manual-cancel route: a never-submitted order cancels
        locally; a live one goes cancel_pending after asking the broker."""

        o = self._run(self.store.get_order(order))
        if o is None or o.status not in _CANCELLABLE:
            return
        try:
            if o.broker_order_id is None:
                self._run(self.store.transition_order(order, OrderStatus.CANCELED))
            else:
                self._run(self.sim.cancel_order(o.broker_order_id))
                self._run(self.store.transition_order(order, OrderStatus.CANCEL_PENDING))
        except (OrderTransitionError, UnknownEntityError):
            # Raced to a terminal state between the read and the transition.
            pass

    @rule(engaged=st.booleans())
    def set_kill_switch(self, engaged):
        self._run(self.store.set_kill_switch(engaged))

    @rule(paused=st.booleans())
    def set_buys_paused(self, paused):
        self._run(self.store.set_buys_paused(paused))

    @rule()
    def close_session(self):
        try:
            self._run(self.store.close_session())
        except SessionAlreadyClosedError:
            pass

    # ------------------------------------------------------------------ #
    # Invariants — checked after EVERY rule
    # ------------------------------------------------------------------ #
    @invariant()
    def position_never_negative(self):
        for pos in self._run(self.store.list_positions()):
            assert pos.quantity >= 0, f"negative position {pos.symbol}={pos.quantity}"

    @invariant()
    def filled_quantity_bounded_and_whole(self):
        for o in self._run(self.store.list_orders()):
            assert isinstance(o.filled_quantity, int)
            assert 0 <= o.filled_quantity <= o.quantity, (
                f"order {o.id} filled_quantity {o.filled_quantity} out of [0,{o.quantity}]"
            )

    @invariant()
    def order_filled_matches_recorded_fills(self):
        for o in self._run(self.store.list_orders()):
            recorded = sum(
                f.quantity for f in self._run(self.store.list_fills(order_id=o.id))
            )
            assert o.filled_quantity == recorded, (
                f"order {o.id} filled_quantity {o.filled_quantity} != recorded {recorded}"
            )

    @invariant()
    def no_candidate_stranded_approved(self):
        # A completed approve action resolves to ORDERED or (on block) reverts to
        # PENDING — a candidate is never left APPROVED between actions.
        for c in self._run(self.store.list_candidates()):
            assert c.status is not CandidateStatus.APPROVED, (
                f"candidate {c.id} stranded APPROVED"
            )

    @invariant()
    def correlation_id_matches_owning_candidate(self):
        # D-020: every event that names a candidate carries that candidate's id
        # as its correlation_id, so one filter reconstructs a whole lifecycle.
        # Holding this across every random interleaving proves the derive rule
        # (correlation_id defaults to candidate_id) is applied uniformly in both
        # stores, not just on the happy path.
        for event in self._run(self.store.list_events()):
            if event.candidate_id is not None:
                assert event.correlation_id == event.candidate_id, (
                    f"event {event.id} ({event.event_type}) candidate_id "
                    f"{event.candidate_id} != correlation_id {event.correlation_id}"
                )

    @invariant()
    def every_order_has_a_resolvable_session(self):
        for o in self._run(self.store.list_orders()):
            assert o.session_id is not None
            assert self._run(self.store.get_session_by_id(o.session_id)) is not None, (
                f"order {o.id} has unresolvable session {o.session_id}"
            )

    @invariant()
    def no_live_untracked_broker_order(self):
        """Every broker order the sim still considers *live* must be tracked —
        either a local order references it, or an open recovery record does.
        This is the F-002 orphan guard: a live-at-broker order the local state
        knows nothing about is the exact failure D-017 exists to prevent."""

        orders = self._run(self.store.list_orders())
        recoveries = self._run(self.store.list_submit_recoveries())
        tracked = {o.broker_order_id for o in orders if o.broker_order_id is not None}
        open_recovery = {
            r.broker_order_id
            for r in recoveries
            if r.cleanup_status in RECOVERY_OPEN_STATUSES
        }
        for broker_id in list(self.sim._broker_ids.values()):
            if self.sim.is_live(broker_id):
                assert broker_id in tracked or broker_id in open_recovery, (
                    f"live broker order {broker_id} is untracked (no order, no recovery)"
                )


class MemoryLifecycleMachine(LifecycleMachine):
    def new_store(self):
        return InMemoryStateStore()


class SqliteLifecycleMachine(LifecycleMachine):
    def new_store(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._db_path = path
        return SqliteStateStore(path)


# A moderate budget: enough interleavings to exercise the races without making
# the suite slow (SQLite is the slower of the two).
_MACHINE_SETTINGS = settings(max_examples=60, stateful_step_count=30, deadline=None)

TestMemoryLifecycle = MemoryLifecycleMachine.TestCase
TestMemoryLifecycle.settings = _MACHINE_SETTINGS
TestSqliteLifecycle = SqliteLifecycleMachine.TestCase
TestSqliteLifecycle.settings = _MACHINE_SETTINGS
