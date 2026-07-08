"""Phase 6e — direct unit tests for the migrated trading *command* facade.

Wave P6e moved the manual-flatten, emergency-reduce, and manual-cancel command
logic out of ``app.api.routes_trading`` and behind
``StoreBackedCommandFacade`` (ADR-005 route boundary; the last three
route->backend edges in the import-linter ratchet). The HTTP round-trip is still
exercised by ``test_orders_api.py`` / ``test_phase7_routes.py``; THIS file pins
the facade methods directly, covering:

* the defensive ``broker is None`` guards (a partial app that wired no broker —
  ``get_command_facade`` reads it defensively, so the guard is real);
* the domain-error -> ``FacadeError`` mapping the route relies on
  (``FlattenBlockedError``/``InvalidOrderError`` -> 409, bad ticker -> 422,
  ``OrderTransitionError`` -> 409);
* the transient-window race branches (position went flat under the store lock
  after the pre-check; a fill landed between ``get_order`` and the cancel
  transition) — driven with a hand-stubbed store method (CLAUDE.md §12: prefer
  hand stubs over pragma/no-cover so the branch is *proven*, not hidden).

The behavior is byte-for-byte what the old route produced; see the route
docstrings in ``routes_trading.py`` for the ADR references.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.facade.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidInputError,
)
from app.facade.store_backed import StoreBackedCommandFacade
from app.models import OrderSide, OrderStatus, SellReason, SessionType
import app.monitoring as monitoring
from app.store.base import (
    FLATTEN_FLAT,
    InvalidOrderError,
    OrderTransitionError,
)

pytestmark = pytest.mark.anyio


async def _hold(store, symbol: str, qty: int, *, avg: float = 10.0) -> None:
    """Establish a real long position of ``qty`` via a filled+canceled BUY."""
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session.id
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)


def _regular(monkeypatch) -> None:
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.REGULAR)


def _facade(store, *, broker=None) -> StoreBackedCommandFacade:
    return StoreBackedCommandFacade(store, broker=broker, settings=Settings())


# --------------------------------------------------------------------------- #
# create_exit (manual flatten)
# --------------------------------------------------------------------------- #
async def test_create_exit_without_broker_raises(any_store):
    """A partial app that wired no broker: the guard fires before any store I/O."""
    await any_store.initialize()
    with pytest.raises(RuntimeError, match="broker adapter not available"):
        await _facade(any_store, broker=None).create_exit(symbol="AAPL", actor="op")


async def test_create_exit_bad_symbol_is_422(any_store):
    await any_store.initialize()
    facade = _facade(any_store, broker=MockBrokerAdapter())
    with pytest.raises(InvalidInputError):
        await facade.create_exit(symbol="not a ticker!!", actor="op")


async def test_create_exit_flat_symbol_is_409(any_store):
    await any_store.initialize()
    facade = _facade(any_store, broker=MockBrokerAdapter())
    with pytest.raises(ConflictError, match="no open AAPL position"):
        await facade.create_exit(symbol="AAPL", actor="op")


async def test_create_exit_halted_is_409(any_store):
    """ADR-003: an ordinary flatten is denied while Halted -> FlattenBlockedError
    -> ConflictError (409). The operator exits via emergency-reduce instead."""
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    await any_store.set_kill_switch(True)  # -> HALTED
    facade = _facade(any_store, broker=MockBrokerAdapter())
    with pytest.raises(ConflictError):
        await facade.create_exit(symbol="AAPL", actor="op")


async def test_create_exit_success(any_store, monkeypatch):
    _regular(monkeypatch)
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    facade = _facade(any_store, broker=MockBrokerAdapter())
    resp = await facade.create_exit(symbol="AAPL", actor="op")
    assert resp.intent.reason is SellReason.MANUAL_FLATTEN
    assert resp.order is not None


async def test_create_exit_race_to_flat_after_buy_cancel_is_409(any_store, monkeypatch):
    """Transient window: the pre-check saw a position, but by the time the atomic
    ``flatten_position`` ran under its own lock the symbol was flat (a concurrent
    sell). The facade surfaces that FLATTEN_FLAT outcome as 409, never a 500."""
    _regular(monkeypatch)
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)  # pre-check passes (qty > 0)
    facade = _facade(any_store, broker=MockBrokerAdapter())

    async def _flat(_symbol):
        return SimpleNamespace(outcome=FLATTEN_FLAT, intent=None, order=None)

    monkeypatch.setattr(any_store, "flatten_position", _flat)
    with pytest.raises(ConflictError, match="no open AAPL position"):
        await facade.create_exit(symbol="AAPL", actor="op")


# --------------------------------------------------------------------------- #
# emergency_reduce_override
# --------------------------------------------------------------------------- #
async def test_emergency_reduce_without_broker_raises(any_store):
    await any_store.initialize()
    with pytest.raises(RuntimeError, match="broker adapter not available"):
        await _facade(any_store, broker=None).emergency_reduce_override(
            symbol="AAPL", actor="op"
        )


async def test_emergency_reduce_not_halted_is_409(any_store):
    """ADR-003 / INV-3 precondition: the override is only grantable while Halted;
    an Active session -> EmergencyReduceBlockedError -> ConflictError (409)."""
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)  # session Active
    facade = _facade(any_store, broker=MockBrokerAdapter())
    with pytest.raises(ConflictError):
        await facade.emergency_reduce_override(symbol="AAPL", actor="op")


async def test_emergency_reduce_halted_success_stays_halted(any_store, monkeypatch):
    _regular(monkeypatch)
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    await any_store.set_kill_switch(True)  # -> HALTED
    facade = _facade(any_store, broker=MockBrokerAdapter())
    resp = await facade.emergency_reduce_override(symbol="AAPL", actor="op")
    assert resp.intent.reason is SellReason.MANUAL_FLATTEN
    # Scoped grant consumed; global state never left Halted.
    assert await any_store.list_emergency_reduce_overrides() == set()


async def test_emergency_reduce_flatten_invalid_after_grant_is_409(
    any_store, monkeypatch
):
    """Defense-in-depth: even after a granted override, a flatten that the store
    refuses (e.g. an unpriceable/oversell InvalidOrderError) surfaces as 409, not
    a leaked 500."""
    _regular(monkeypatch)
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    await any_store.set_kill_switch(True)
    facade = _facade(any_store, broker=MockBrokerAdapter())

    async def _boom(_symbol):
        raise InvalidOrderError("unpriceable exit")

    monkeypatch.setattr(any_store, "flatten_position", _boom)
    with pytest.raises(ConflictError, match="unpriceable exit"):
        await facade.emergency_reduce_override(symbol="AAPL", actor="op")


# --------------------------------------------------------------------------- #
# cancel (manual order cancel) — the transient-race branch only; the 404/409/502
# paths are covered end-to-end in test_orders_api.py through the HTTP route.
# --------------------------------------------------------------------------- #
async def test_cancel_without_broker_raises(any_store):
    """Parity with the sibling command guards + the old route (get_broker_adapter's
    hard Depends -> 500 when unwired): a broker-less facade must NOT 200-succeed a
    local CREATED cancel nor map a submitted cancel to a misleading 502 — a missing
    broker is a wiring fault (RuntimeError -> 500), checked before any store read."""
    await any_store.initialize()
    with pytest.raises(RuntimeError, match="broker adapter not available"):
        await _facade(any_store, broker=None).cancel(order_id="anything", actor="op")


async def test_cancel_unknown_order_is_404(any_store):
    await any_store.initialize()
    facade = _facade(any_store, broker=MockBrokerAdapter())
    with pytest.raises(EntityNotFoundError):
        await facade.cancel(order_id="no-such-order", actor="op")


async def test_cancel_race_fill_landed_first_is_409(any_store, monkeypatch):
    """Transient window: a CREATED (never-submitted) order is canceled locally, but
    a fill landed first so ``transition_order`` rejects CREATED->CANCELED. The
    facade maps that OrderTransitionError to 409, not a 500."""
    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    order = await any_store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 10, session_id=session.id
    )
    assert order.broker_order_id is None  # never-submitted: local-cancel path

    async def _reject(_order_id, _new_status):
        raise OrderTransitionError("a fill landed first")

    monkeypatch.setattr(any_store, "transition_order", _reject)
    facade = _facade(any_store, broker=MockBrokerAdapter())
    with pytest.raises(ConflictError, match="a fill landed first"):
        await facade.cancel(order_id=order.id, actor="op")
