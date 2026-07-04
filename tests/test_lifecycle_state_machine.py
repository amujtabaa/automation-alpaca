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
from collections import Counter

import pytest
from hypothesis import event, settings, target
from hypothesis.control import currently_in_test_context
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
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_OPEN_STATUSES,
    CandidateStatus,
    OrderStatus,
    utcnow,
)
from app.monitoring import _submit_pending_orders, run_monitoring_tick
from app.store.base import (
    CLAIM_CLAIMED,
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

def _event(msg: str) -> None:
    """``hypothesis.event()`` for observability, but a no-op outside a Hypothesis
    test context — the deterministic driver at the bottom of this file invokes the
    rules directly, where ``event()`` (like ``target()``) raises."""

    if currently_in_test_context():
        event(msg)


# Cross-instance coverage ledger (AIR-010): shared across every machine instance
# and example in a run. The random machines emit ``event()`` markers and bump
# these counters purely for observability (``--hypothesis-show-statistics``); the
# HARD "a critical recovery branch is unreachable" guard is the deterministic
# driver at the bottom of this file, which invokes the self-contained rare-branch
# rules (crash_after_claim, force_submit_cancel_orphan, divergent_fill_and_reconcile)
# directly — no seed-flaky reliance on random search landing the sequence.
_COVERAGE: Counter = Counter()

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
        # Peak count of open recovery records seen this example — fed to
        # hypothesis target() ONCE at teardown (target() rejects a repeated label
        # within one example, so it can't live in a per-step invariant).
        self._max_open_recovery = 0
        self.store = self.new_store()
        self._run(self.store.initialize())

    def _run(self, coro):
        return self._loop.run_until_complete(coro)

    def _next_sfid(self) -> str:
        self._sfid += 1
        return f"sfid-{self._sfid}"

    def teardown(self) -> None:
        # AIR-010: bias Hypothesis toward interleavings richer in open recovery
        # activity — one target() per example (the peak seen), here at teardown
        # rather than in a per-step invariant (which would repeat the label).
        # Guarded: teardown is ALSO called by the deterministic driver below, which
        # runs outside a Hypothesis test context where target() would raise (and
        # abort teardown before closing the loop — a leaked-loop ResourceWarning).
        if currently_in_test_context():
            target(float(self._max_open_recovery), label="open_recovery_records")
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

        _COVERAGE["tick"] += 1
        self._run(run_monitoring_tick(self.store, self.sim, _SETTINGS))

    @rule()
    def crash_after_claim(self):
        """Model a crash between the atomic claim and the ``SUBMITTED`` persist
        (B2 / AIR-003): dispatch a candidate to a ``CREATED`` order, then claim it
        (→ ``SUBMITTING`` with ``broker_order_id=None``) but never submit. That is
        exactly the stale, id-less ``SUBMITTING`` row a restart inherits — excluded
        from both the CREATED submit sweep and the open-order reconcile poll —
        which the next ``monitoring_tick``'s re-drive step must recover (the sim's
        ``submit_order`` is idempotent by client_order_id, so re-drive is safe).

        Self-contained (own candidate → dispatch → claim) so the B2 precondition is
        reached whenever controls are clear, not only on the rare tick where a
        random bundle order happens to still be ``CREATED``. Skips silently under a
        closed session or a control stop — a legitimate interleaving."""

        try:
            cand = self._run(
                self.store.create_candidate(
                    "MSFT", suggested_quantity=5, suggested_limit_price=1.0
                )
            )
        except SessionClosedError:
            return
        self._run(self.store.transition_candidate(cand.id, CandidateStatus.APPROVED))
        try:
            order = self._run(
                self.store.create_order_for_candidate(cand.id, risk_limits=RiskLimits())
            )
        except (
            OrderIntentBlockedError,
            RiskLimitBlockedError,
            InvalidOrderError,
            CandidateTransitionError,
        ):
            self._run(self.store.revert_candidate_approval(cand.id))
            return
        claim = self._run(self.store.claim_order_for_submission(order.id))
        if claim.outcome == CLAIM_CLAIMED:
            _COVERAGE["crash_after_claim"] += 1
            _event("stale SUBMITTING created (crash after claim)")

    @rule()
    def divergent_fill_and_reconcile(self):
        """Model an unrecordable broker fill (B3 / AIR-002) end-to-end: the broker
        reports an order fully filled but exposes NO recordable fill row (the
        adapter withheld an un-priceable one), then a real reconcile tick runs. The
        tick must escalate to a durable ``needs_review`` reconciliation record and
        hold the order non-terminal — never fabricate the position from the broker
        scalar (positions still derive only from appended fills).

        Self-contained (its own candidate → clean submit → diverge → reconcile) so
        the B3 branch is exercised whenever controls are clear, instead of
        depending on a random pollable order surviving the aggressive orphaning
        the other rules do. Skips silently when the session is closed or a control
        stop blocks submission — itself a legitimate interleaving."""

        self.sim.set_on_submit(None)  # no orphan hook on this clean submit
        try:
            cand = self._run(
                self.store.create_candidate(
                    "AAPL", suggested_quantity=5, suggested_limit_price=1.0
                )
            )
        except SessionClosedError:
            return
        self._run(self.store.transition_candidate(cand.id, CandidateStatus.APPROVED))
        try:
            order = self._run(
                self.store.create_order_for_candidate(cand.id, risk_limits=RiskLimits())
            )
        except (
            OrderIntentBlockedError,
            RiskLimitBlockedError,
            InvalidOrderError,
            CandidateTransitionError,
        ):
            self._run(self.store.revert_candidate_approval(cand.id))
            return
        self._run(_submit_pending_orders(self.store, self.sim))
        o = self._run(self.store.get_order(order.id))
        if (
            o is None
            or o.broker_order_id is None
            or o.status not in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED)
        ):
            return  # a control stop held the submission this time — legitimate
        # Broker claims the full quantity filled but emits no fill row.
        self.sim.script(
            o.broker_order_id,
            [BrokerOrderUpdate(OrderStatus.FILLED, o.quantity, [])],
        )
        _COVERAGE["divergent_fill_scripted"] += 1
        self._run(run_monitoring_tick(self.store, self.sim, _SETTINGS))
        # The escalation must produce a needs_review record for this order, and
        # must NOT fabricate the position from the broker scalar (still 0 recorded).
        after = self._run(self.store.get_order(order.id))
        recs = self._run(self.store.list_submit_recoveries())
        if (
            after is not None
            and after.filled_quantity == 0
            and any(
                r.local_order_id == order.id
                and r.cleanup_status == RECOVERY_NEEDS_REVIEW
                for r in recs
            )
        ):
            _COVERAGE["fill_divergence_needs_review"] += 1
            _event("B3 fill divergence escalated to needs_review")

    @rule()
    def force_submit_cancel_orphan(self):
        """Deterministically construct the F-002 orphan (D-017): dispatch a fresh
        candidate to a ``CREATED`` order, arm the mid-submit cancel, and run ONLY
        the submit phase — leaving the broker order live while the local order is
        ``CANCELED``, reconciled solely by an open recovery record. Atomic and
        self-contained so the ``open_recovery`` invariant disjunct is reliably
        exercised, not left to a lucky arm→submit_pending_only interleaving. Skips
        silently under a closed session or a control stop."""

        try:
            cand = self._run(
                self.store.create_candidate(
                    "TSLA", suggested_quantity=5, suggested_limit_price=1.0
                )
            )
        except SessionClosedError:
            return
        self._run(self.store.transition_candidate(cand.id, CandidateStatus.APPROVED))
        try:
            self._run(
                self.store.create_order_for_candidate(cand.id, risk_limits=RiskLimits())
            )
        except (
            OrderIntentBlockedError,
            RiskLimitBlockedError,
            InvalidOrderError,
            CandidateTransitionError,
        ):
            self._run(self.store.revert_candidate_approval(cand.id))
            return

        async def cancel_mid_submit(order, broker_id):
            self.sim.set_on_submit(None)
            try:
                await self.store.transition_order(order.id, OrderStatus.CANCELED)
            except (OrderTransitionError, UnknownEntityError):
                pass

        self.sim.set_on_submit(cancel_mid_submit)
        # Submit ONLY (no recover) — the orphan is observable at the next
        # invariant checkpoint before a full tick would heal it.
        self._run(_submit_pending_orders(self.store, self.sim))

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
        for ev in self._run(self.store.list_events()):
            if ev.candidate_id is not None:
                assert ev.correlation_id == ev.candidate_id, (
                    f"event {ev.id} ({ev.event_type}) candidate_id "
                    f"{ev.candidate_id} != correlation_id {ev.correlation_id}"
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
                in_tracked = broker_id in tracked
                assert in_tracked or broker_id in open_recovery, (
                    f"live broker order {broker_id} is untracked (no order, no recovery)"
                )
                # AIR-010 coverage: record when the invariant is satisfied via the
                # open-recovery DISJUNCT (a live broker order the local order state
                # no longer tracks) — the F-002 orphan branch, dead code without
                # the arm_submit_cancel_race seam.
                if not in_tracked and broker_id in open_recovery:
                    _COVERAGE["orphan_via_open_recovery"] += 1
                    _event("live broker order tracked only via open recovery")

        # AIR-010: record + bias toward the durable needs_review escalations
        # (B2 terminal re-drive / B3 fill divergence). A stale, id-less SUBMITTING
        # order (crash_after_claim) is the B2 precondition; count it too.
        if any(r.cleanup_status == RECOVERY_NEEDS_REVIEW for r in recoveries):
            _COVERAGE["needs_review_present"] += 1
            _event("needs_review recovery record present")
        if any(
            o.status is OrderStatus.SUBMITTING and not o.broker_order_id
            for o in orders
        ):
            _COVERAGE["stale_submitting_present"] += 1
        # Accumulate the peak for teardown's single target() call.
        self._max_open_recovery = max(self._max_open_recovery, len(open_recovery))


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


# AIR-010: the harness must *prove* it reaches the rare recovery branches, not
# just pass its invariants on the happy path. The random TestCases above emit
# ``event()`` markers (visible in ``--hypothesis-show-statistics``) and accumulate
# ``_COVERAGE`` for observability — but asserting a random run reached a specific
# branch is inherently seed-flaky (a bad seed may just never sequence it). So the
# HARD "fails if a critical recovery branch is unreachable" guard lives here, in a
# DETERMINISTIC driver: it instantiates the real machine and invokes each
# rare-branch rule + the invariant that records it, with no random search. Each
# rule is self-contained (own candidate, clear controls on a fresh machine), so
# this reliably proves every critical branch is REACHABLE by the harness's own
# rules. If a refactor makes one unreachable (the AIR-010 failure mode — a harness
# that has gone blind to a recovery path), the matching assertion fails.
@pytest.mark.parametrize(
    "machine_cls", [MemoryLifecycleMachine, SqliteLifecycleMachine]
)
def test_harness_rules_reach_recovery_branches(machine_cls):
    machine = machine_cls()
    try:
        before = _COVERAGE.copy()

        # B2: a crash between claim and persist leaves a stale, id-less SUBMITTING
        # order; the invariant checkpoint must observe it.
        machine.crash_after_claim()
        machine.no_live_untracked_broker_order()
        assert _COVERAGE["crash_after_claim"] > before["crash_after_claim"], (
            "crash_after_claim rule did not create a stale SUBMITTING order"
        )
        assert (
            _COVERAGE["stale_submitting_present"] > before["stale_submitting_present"]
        ), "stale SUBMITTING order was not observed at an invariant checkpoint"

        # F-002: an orphan (broker live, local CANCELED) tracked ONLY by an open
        # recovery record — the open_recovery invariant disjunct.
        machine.force_submit_cancel_orphan()
        machine.no_live_untracked_broker_order()
        assert (
            _COVERAGE["orphan_via_open_recovery"] > before["orphan_via_open_recovery"]
        ), "F-002 orphan was not reconciled via the open-recovery branch"

        # B3: an unrecordable broker fill must escalate to a durable needs_review
        # record while the position stays derived only from (zero) recorded fills.
        machine.divergent_fill_and_reconcile()
        assert (
            _COVERAGE["divergent_fill_scripted"] > before["divergent_fill_scripted"]
        ), "divergent (unrecordable) broker fill was not set up"
        assert (
            _COVERAGE["fill_divergence_needs_review"]
            > before["fill_divergence_needs_review"]
        ), "B3 fill divergence did not escalate to a needs_review record"
    finally:
        machine.teardown()
