"""``SimBrokerAdapter`` — a richer, still fully IO-free test double.

Extends :class:`~app.broker.mock.MockBrokerAdapter` (never replaces it) with
the extra controls Wave 1's hardening tests need to *deterministically*
reproduce races and edge cases that are otherwise timing-dependent against a
real broker:

* ``set_on_submit`` — an async hook fired mid-``submit_order``, after the
  broker id is minted and live but before the call returns, so a test can flip
  a control (kill switch, session close) at the exact instant a real race
  would land (F-001/F-002).
* ``fail_submit_when`` / ``fail_cancel_when`` — raise at a specific call
  index, generalizing the inherited one-shot ``fail_next_submit`` /
  ``fail_next_cancel``.
* ``script`` — queue a sequence of ``BrokerOrderUpdate``\\ s for one order,
  consumed one per ``get_order_status`` call, with the last one sticking once
  exhausted. Models submitted->partial->partial->filled, a duplicate
  ``source_fill_id``, and a late fill arriving after ``cancel_pending``
  (CHAOS-1).
* ``disconnect_status_for`` — make the next N ``get_order_status`` calls raise
  (simulated feed drop), then recover automatically.
* ``is_live`` — whether a broker order id's *current* status is non-terminal;
  the hook a recovery-loop test uses to assert a stranded order was actually
  cancelled.

Like ``MockBrokerAdapter``, this module imports no SDK, makes no network
calls, and is never wired into any production factory — it lives in
``app/broker/`` purely as a richer test double.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Optional

from app.broker.adapter import BrokerError, BrokerOrderUpdate
from app.broker.mock import MockBrokerAdapter, _broker_id
from app.models import Order, OrderStatus

# Statuses beyond which an order no longer needs watching (mirrors the set
# implicit in OrderStatus's docstring: submitted/partially_filled/
# cancel_pending are all still "in flight").
_TERMINAL = frozenset({OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED})

OnSubmitHook = Callable[[Order, str], Awaitable[None]]
# A predicate returns a truthy value to force a failure: a BaseException
# instance to raise as-is, or any other truthy value to raise a generic
# BrokerError.
SubmitPredicate = Callable[[Order, int], object]
CancelPredicate = Callable[[str, int], object]


class SimBrokerAdapter(MockBrokerAdapter):
    def __init__(self) -> None:
        super().__init__()

        # Deliverable 1: accept-then-signal hook.
        self._on_submit: Optional[OnSubmitHook] = None

        # Deliverable 2: fail-at-a-point predicates (composes with the
        # inherited one-shot fail_next_submit/fail_next_cancel).
        self._submit_predicates: list[SubmitPredicate] = []
        self._cancel_predicates: list[CancelPredicate] = []
        self._submit_calls = 0
        self._cancel_calls = 0

        # Deliverable 3: scripted lifecycles, keyed by broker id (an order id
        # not yet submitted is stored under its deterministic would-be broker
        # id, f"broker-{order_id}", which is exactly what submit_order later
        # mints for it).
        self._scripts: dict[str, list[BrokerOrderUpdate]] = {}
        # The last update actually *consumed* by a get_order_status call for
        # a broker id — separate from self._scripts (the remaining queue) so
        # is_live can tell "has a script even been polled yet" from "is the
        # queue empty".
        self._script_last: dict[str, BrokerOrderUpdate] = {}

        # Deliverable 4: disconnect window — next N get_order_status calls
        # raise, then recover automatically.
        self._disconnect_remaining = 0

    # ------------------------------------------------------------------ #
    # BrokerAdapter overrides
    # ------------------------------------------------------------------ #
    async def submit_order(self, order: Order) -> str:
        call_index = self._submit_calls
        self._submit_calls += 1

        failure = self._submit_failure(order, call_index)
        if failure is not None:
            # Mirror MockBrokerAdapter: record the attempt but mint no id.
            self.submitted.append(order)
            raise failure

        # No forced failure of our own — delegate to the parent, which still
        # honors the inherited one-shot fail_next_submit (records the attempt
        # and raises without minting an id) or, on success, records the
        # attempt, mints+records the broker id, and seeds the default
        # SUBMITTED response. Either way broker_id_for/is_live are correct
        # the instant this returns.
        broker_order_id = await super().submit_order(order)

        if self._on_submit is not None:
            await self._on_submit(order, broker_order_id)
        return broker_order_id

    async def get_order_status(
        self,
        broker_order_id: str,
        *,
        recorded_quantity: int = 0,
        fallback_price: Optional[float] = None,
    ) -> BrokerOrderUpdate:
        # fallback_price (§7) is accepted for interface parity and ignored: the
        # sim's scripted/queued fills always carry an explicit price.
        # 1. Simulated disconnect window: raise, no matter what else is set.
        if self._disconnect_remaining > 0:
            self._disconnect_remaining -= 1
            self.status_queries.append(broker_order_id)
            raise BrokerError("simulated disconnect")

        # 2. A scripted lifecycle for this broker id takes precedence over
        #    the inherited _responses map.
        queue = self._scripts.get(broker_order_id)
        if queue:
            self.status_queries.append(broker_order_id)
            update = queue.pop(0)
            self._script_last[broker_order_id] = update
            return update
        if broker_order_id in self._script_last:
            # Script exhausted — the last (typically terminal) update sticks.
            self.status_queries.append(broker_order_id)
            return self._script_last[broker_order_id]

        # 3. No script ever set for this id — inherited behavior (_responses
        #    or the default SUBMITTED/0). super() records status_queries.
        return await super().get_order_status(
            broker_order_id, recorded_quantity=recorded_quantity
        )

    async def cancel_order(self, broker_order_id: str) -> None:
        call_index = self._cancel_calls
        self._cancel_calls += 1

        failure = self._cancel_failure(broker_order_id, call_index)
        if failure is not None:
            # Mirror MockBrokerAdapter: record the attempt before raising.
            self.canceled.append(broker_order_id)
            raise failure

        # Seed _responses from whatever a script last reported, if anything —
        # super().cancel_order only ever looks at _responses to preserve
        # prior fills, and a script's consumed state is more current than
        # whatever stale entry (e.g. submit_order's default SUBMITTED/0)
        # already sits in _responses.
        if broker_order_id in self._script_last:
            self._responses[broker_order_id] = self._script_last[broker_order_id]

        await super().cancel_order(broker_order_id)

        # A cancel always wins over a script: stop the queue from resuming
        # and make sure is_live sees the same terminal CANCELED super() just
        # wrote to _responses (with prior fills preserved).
        self._scripts.pop(broker_order_id, None)
        self._script_last[broker_order_id] = self._responses[broker_order_id]

    # ------------------------------------------------------------------ #
    # Test controls
    # ------------------------------------------------------------------ #
    def set_on_submit(self, hook: Optional[OnSubmitHook]) -> None:
        """Register (or clear, with ``None``) an async ``hook(order,
        broker_order_id)`` fired inside ``submit_order`` — after the broker id
        is minted and live, before ``submit_order`` returns. Only fires on a
        successful submit. This is the seam a test uses to flip a control
        (kill switch, session close) at the exact point a real F-001/F-002
        race would land."""

        self._on_submit = hook

    def fail_submit_when(self, predicate: SubmitPredicate) -> None:
        """Register ``predicate(order, call_index)`` (0-based), checked on
        every ``submit_order`` call. A truthy return forces ``submit_order``
        to raise: the value itself if it's a ``BaseException``, else a
        generic ``BrokerError``. Composes with (does not replace) the
        inherited ``fail_next_submit``."""

        self._submit_predicates.append(predicate)

    def fail_cancel_when(self, predicate: CancelPredicate) -> None:
        """Register ``predicate(broker_order_id, call_index)`` (0-based),
        checked on every ``cancel_order`` call. Same truthy-return contract as
        ``fail_submit_when``. Composes with the inherited
        ``fail_next_cancel``."""

        self._cancel_predicates.append(predicate)

    def script(self, order_id_or_broker_id: str, updates: list[BrokerOrderUpdate]) -> None:
        """Queue ``updates`` to be returned one-per-call from
        ``get_order_status`` for one order. Accepts either our order id or a
        broker id:

        * already-submitted order id -> resolved through ``_broker_ids``.
        * a broker id (e.g. obtained from ``broker_id_for``) -> used as-is.
        * a not-yet-submitted order id -> stored under its deterministic
          would-be broker id (``f"broker-{order_id}"``), which is exactly
          what ``submit_order`` mints for it, so the script resolves once the
          order is actually submitted.

        Once the queue is exhausted, the last update in ``updates`` keeps
        being returned (a terminal FILLED/CANCELED persists). A script takes
        precedence over the inherited ``_responses`` map for this broker id.
        """

        broker_id = self._resolve_broker_id(order_id_or_broker_id)
        self._scripts[broker_id] = list(updates)
        # A fresh script replaces any stale "last consumed" state so a
        # re-script doesn't accidentally stick to a previous script's tail.
        self._script_last.pop(broker_id, None)

    def disconnect_status_for(self, n_calls: int) -> None:
        """Make the next ``n_calls`` calls to ``get_order_status`` (any
        broker id) raise ``BrokerError("simulated disconnect")``, then recover
        automatically. Global across broker ids."""

        self._disconnect_remaining = n_calls

    def is_live(self, broker_order_id: str) -> bool:
        """True iff ``broker_order_id``'s *current* status is non-terminal
        (not FILLED/CANCELED/REJECTED).

        A broker id that was never actually submitted (never minted via
        ``submit_order``) is never live. Otherwise, prefers the last script
        update actually *consumed* by a ``get_order_status`` call (an unpolled
        script doesn't change state), then the plain ``_responses`` entry,
        then the implicit default for a submitted-but-never-polled order
        (SUBMITTED). ``cancel_order`` keeps this in sync — see its docstring.
        """

        if broker_order_id not in self._broker_ids.values():
            return False
        if broker_order_id in self._script_last:
            status = self._script_last[broker_order_id].status
        elif broker_order_id in self._responses:
            status = self._responses[broker_order_id].status
        else:
            status = OrderStatus.SUBMITTED
        return status not in _TERMINAL

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _resolve_broker_id(self, order_id_or_broker_id: str) -> str:
        if order_id_or_broker_id in self._broker_ids:
            return self._broker_ids[order_id_or_broker_id]
        if order_id_or_broker_id in self._broker_ids.values():
            return order_id_or_broker_id
        return _broker_id(order_id_or_broker_id)

    @staticmethod
    def _as_failure(result: object, message: str) -> BaseException:
        return result if isinstance(result, BaseException) else BrokerError(message)

    def _submit_failure(self, order: Order, call_index: int) -> Optional[BaseException]:
        for predicate in self._submit_predicates:
            result = predicate(order, call_index)
            if result:
                return self._as_failure(
                    result,
                    f"simulated submit failure for order {order.id!r} at call {call_index}",
                )
        return None

    def _cancel_failure(self, broker_order_id: str, call_index: int) -> Optional[BaseException]:
        for predicate in self._cancel_predicates:
            result = predicate(broker_order_id, call_index)
            if result:
                return self._as_failure(
                    result,
                    f"simulated cancel failure for {broker_order_id!r} at call {call_index}",
                )
        return None
