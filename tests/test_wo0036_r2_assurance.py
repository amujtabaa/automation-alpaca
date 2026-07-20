"""WO-0036 R2 assurance: exact parity and generated projection contracts.

The ordinary R2 tests parameterize behavior over both stores.  This module
adds the stronger differential claim: after normalizing opaque identifiers and
non-business wall-clock offsets, the memory and SQLite stores must expose the
same persisted R2 state and event stream after *every* lifecycle step. It also
checks timestamp causality before normalization and exercises the shared obligation
projection over generated boundary values so a copy-pasted defect in both
stores cannot make the parity test vacuously green.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from itertools import count
from typing import Any
from uuid import UUID

import pytest
from hypothesis import HealthCheck, given, settings as hyp_settings, strategies as st

import app.models as models
from app.models import (
    RECOVERY_RESOLVED,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    SellReason,
)
from app.sellside.types import ActionKind
from app.store.core import EnvelopeObligationProjection, project_envelope_obligation
from app.store.base import CLAIM_CLAIMED
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore
from tests.test_wo0036_r2_lifecycle_link import _action, _draft

pytestmark = pytest.mark.anyio

T0 = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)


class _DeterministicDateTime(datetime):
    """Freshly reset monotonic clock used by one differential store run."""

    ticks = count()

    @classmethod
    def reset(cls) -> None:
        cls.ticks = count()

    @classmethod
    def now(cls, tz=None):  # noqa: ANN001 - mirrors datetime.now
        # Persist/ingest time follows the explicitly injected logical action
        # times below; otherwise the final-claim staleness rail correctly
        # rejects an impossible event whose ts_event is in the future.
        value = T0 + timedelta(hours=1, microseconds=next(cls.ticks))
        return value if tz is not None else value.replace(tzinfo=None)


def _install_determinism(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make model defaults deterministic without adding a production clock seam."""

    _DeterministicDateTime.reset()
    ids = count(1)
    monkeypatch.setattr(models, "datetime", _DeterministicDateTime)
    monkeypatch.setattr(models.uuid, "uuid4", lambda: UUID(int=next(ids)))


def _canonicalize(value: Any, id_roles: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize(item, id_roles) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonicalize(item, id_roles) for item in value]
    if isinstance(value, tuple):
        return tuple(_canonicalize(item, id_roles) for item in value)
    if isinstance(value, str):
        for identifier, role in sorted(
            id_roles.items(), key=lambda pair: len(pair[0]), reverse=True
        ):
            value = value.replace(identifier, role)
    return value


def _dump(item: Any, id_roles: dict[str, str]) -> dict[str, Any]:
    return _canonicalize(item.model_dump(mode="json"), id_roles)


def _timestamp_topology(value: Any) -> Any:
    """Ignore clock-call offsets, while retaining every injected logical time."""

    if isinstance(value, dict):
        return {key: _timestamp_topology(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_timestamp_topology(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_timestamp_topology(item) for item in value)
    if not isinstance(value, str) or "T" not in value:
        return value
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    # The deterministic default clock lives in this one-second window.  The
    # stores legitimately call it a different number of times internally;
    # those ingestion offsets are not persisted business truth. Explicit
    # action/terminal/expiry times remain byte-compared below.
    if T0 + timedelta(hours=1) <= parsed < T0 + timedelta(hours=1, seconds=1):
        return "<wall-clock>"
    return value


def _projection_dump(
    projection: EnvelopeObligationProjection, id_roles: dict[str, str]
) -> dict[str, Any]:
    return _canonicalize(
        {
            "linked": projection.linked,
            "retains_intent": projection.retains_intent,
            "unresolved_order_ids": projection.unresolved_order_ids,
            "missing_envelope_ids": projection.missing_envelope_ids,
            "missing_order_ids": projection.missing_order_ids,
            "invalid_order_ids": projection.invalid_order_ids,
            "recovery_order_ids": projection.recovery_order_ids,
            "uncertain_claim_order_ids": projection.uncertain_claim_order_ids,
            "venue_orders": tuple(
                _dump(order, id_roles) for order in projection.venue_orders
            ),
            "claimable_order_ids": projection.claimable_order_ids,
            "acknowledgeable_order_ids": projection.acknowledgeable_order_ids,
        },
        id_roles,
    )


async def _snapshot(store) -> dict[str, Any]:
    """Canonical R2 state; no store-local field or event attribute is omitted."""

    intents = await store.list_sell_intents(symbol="AAPL")
    envelopes = await store.list_envelopes(symbol="AAPL")
    sessions = await store.list_sessions()
    session_ids = {session.id for session in sessions}
    candidates = [
        candidate
        for candidate in await store.list_candidates()
        if candidate.symbol == "AAPL" and candidate.session_id in session_ids
    ]
    orders = [
        order
        for order in await store.list_orders()
        if order.symbol == "AAPL" and order.session_id in session_ids
    ]
    fills = [
        fill
        for fill in await store.list_fills(symbol="AAPL")
        if fill.session_id in session_ids
    ]
    position_snapshots = [
        snapshot
        for session in sessions
        for snapshot in await store.list_position_snapshots(session.id)
        if snapshot.symbol == "AAPL"
    ]
    intent_ids = {intent.id for intent in intents}
    envelope_ids = {envelope.id for envelope in envelopes}
    candidate_ids = {candidate.id for candidate in candidates}
    order_ids = {order.id for order in orders}
    fill_ids = {fill.id for fill in fills}
    recoveries = [
        recovery
        for recovery in await store.list_submit_recoveries()
        if recovery.local_order_id in order_ids
    ]
    execution_events = [
        event
        for event in await store.get_execution_events()
        if event.correlation_id in intent_ids
        or event.envelope_id in envelope_ids
        or event.order_id in order_ids
    ]
    audit_events = [
        event
        for event in await store.list_events()
        if event.correlation_id in intent_ids
        or event.candidate_id in candidate_ids
        or event.order_id in order_ids
        or event.fill_id in fill_ids
        or (event.event_type == "session_closed" and event.session_id in session_ids)
    ]
    identified = (
        *sessions,
        *candidates,
        *intents,
        *envelopes,
        *orders,
        *fills,
        *position_snapshots,
        *recoveries,
        *execution_events,
        *audit_events,
    )
    identifiers = [item.id for item in identified]
    assert len(identifiers) == len(set(identifiers)), "snapshot ids are not injective"
    for event in execution_events:
        assert event.ts_init.tzinfo is not None
        if event.ts_event is not None:
            assert event.ts_event.tzinfo is not None
            assert event.ts_event <= event.ts_init
    id_roles: dict[str, str] = {}
    for prefix, items in (
        ("session", sessions),
        ("candidate", candidates),
        ("intent", intents),
        ("envelope", envelopes),
        ("order", orders),
        ("fill", fills),
        ("position-snapshot", position_snapshots),
        ("recovery", recoveries),
        ("execution-event", execution_events),
        ("audit-event", audit_events),
    ):
        id_roles.update(
            {item.id: f"<{prefix}-{index}>" for index, item in enumerate(items)}
        )
    if isinstance(store, InMemoryStateStore):
        projection = store._envelope_obligation_unlocked(symbol="AAPL")
    else:
        projection = store._envelope_obligation_locked(symbol="AAPL")
    active = await store.active_sell_intent_for("AAPL")
    snapshot = {
        "sessions": tuple(_dump(item, id_roles) for item in sessions),
        "candidates": tuple(_dump(item, id_roles) for item in candidates),
        "sell_intents": tuple(_dump(item, id_roles) for item in intents),
        "envelopes": tuple(_dump(item, id_roles) for item in envelopes),
        "orders": tuple(_dump(item, id_roles) for item in orders),
        "fills": tuple(_dump(item, id_roles) for item in fills),
        "position_snapshots": tuple(
            _dump(item, id_roles) for item in position_snapshots
        ),
        "recoveries": tuple(_dump(item, id_roles) for item in recoveries),
        "execution_events": tuple(_dump(item, id_roles) for item in execution_events),
        "audit_events": tuple(_dump(item, id_roles) for item in audit_events),
        "projection": _projection_dump(projection, id_roles),
        "active_sell_intent": (_dump(active, id_roles) if active is not None else None),
    }
    return _timestamp_topology(snapshot)


async def _prepare_owner(store):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        100,
        session_id=session.id,
    )
    await store.append_fill(
        buy.id,
        "AAPL",
        OrderSide.BUY,
        100,
        10.0,
        source_fill_id="r2-assurance-hold",
        session_id=session.id,
    )
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    return session, intent


async def _activate(store, *, logical_now: datetime = T0):
    session, intent = await _prepare_owner(store)
    envelope = await store.approve_envelope_activation(
        _draft(
            intent.id,
            session_id=session.id,
            expires_at=logical_now + timedelta(hours=2),
        ),
        actor="operator-a",
    )
    return session, intent, envelope


async def _script_submit_reprice_terminal(store) -> list[dict[str, Any]]:
    _, _, envelope = await _activate(store)
    states = [await _snapshot(store)]
    predecessor = await store.stage_envelope_action(
        envelope.id,
        _action(),
        snapshot_fingerprint="r2-assurance-submit",
        now=T0 + timedelta(seconds=1),
    )
    states.append(await _snapshot(store))
    claim = await store.claim_order_for_submission(predecessor.order.id)
    assert claim.outcome == CLAIM_CLAIMED, claim.reason
    states.append(await _snapshot(store))
    await store.transition_order(
        predecessor.order.id,
        OrderStatus.SUBMITTED,
        broker_order_id="broker-predecessor",
    )
    states.append(await _snapshot(store))
    replacement = await store.stage_envelope_action(
        envelope.id,
        _action(ActionKind.REPRICE, price=9.8),
        snapshot_fingerprint="r2-assurance-reprice",
        now=T0 + timedelta(seconds=2),
    )
    states.append(await _snapshot(store))
    claim = await store.claim_order_for_submission(replacement.order.id)
    assert claim.outcome == CLAIM_CLAIMED, claim.reason
    states.append(await _snapshot(store))
    await store.transition_order(replacement.order.id, OrderStatus.REJECTED)
    states.append(await _snapshot(store))
    await store.transition_envelope(
        envelope.id,
        EnvelopeStatus.BREACHED,
        reason="assurance terminal",
        now=T0 + timedelta(seconds=3),
    )
    states.append(await _snapshot(store))
    await store.transition_order(predecessor.order.id, OrderStatus.CANCELED)
    states.append(await _snapshot(store))
    return states


async def _script_supersession_and_close(store) -> list[dict[str, Any]]:
    session, intent, old = await _activate(store)
    states = [await _snapshot(store)]
    successor = _draft(
        intent.id,
        qty_ceiling=90,
        remaining_quantity=90,
        floor_price=9.1,
        session_id=session.id,
    )
    current = await store.supersede_envelope(
        old.id,
        successor,
        actor="operator-a",
        reason="assurance bounded amendment",
    )
    states.append(await _snapshot(store))
    await store.close_session(session.id, actor="operator-a")
    states.append(await _snapshot(store))
    await store.transition_envelope(
        current.id,
        EnvelopeStatus.BREACHED,
        reason="assurance successor terminal",
        now=T0 + timedelta(seconds=4),
    )
    states.append(await _snapshot(store))
    return states


async def _script_recovery_window(store) -> list[dict[str, Any]]:
    session, _, envelope = await _activate(store)
    staged = await store.stage_envelope_action(
        envelope.id,
        _action(),
        snapshot_fingerprint="r2-assurance-recovery",
        now=T0 + timedelta(seconds=1),
    )
    claim = await store.claim_order_for_submission(staged.order.id)
    assert claim.outcome == CLAIM_CLAIMED, claim.reason
    await store.transition_envelope(
        envelope.id,
        EnvelopeStatus.BREACHED,
        reason="assurance terminal before recovery",
        now=T0 + timedelta(seconds=2),
    )
    states = [await _snapshot(store)]
    recovery = await store.create_submit_recovery(
        local_order_id=staged.order.id,
        broker_order_id="broker-recovery",
        client_order_id=staged.order.id,
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        limit_price=9.9,
        failure_reason="accepted before local acknowledgement",
        session_id=session.id,
    )
    states.append(await _snapshot(store))
    await store.update_submit_recovery(recovery.id, cleanup_status=RECOVERY_RESOLVED)
    states.append(await _snapshot(store))
    return states


async def _run_deterministic(
    monkeypatch: pytest.MonkeyPatch,
    store_factory: Callable[[], Any],
    script: Callable[[Any], Awaitable[list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    with monkeypatch.context() as deterministic:
        _install_determinism(deterministic)
        store = store_factory()
        try:
            return await script(store)
        finally:
            await store.close()


@pytest.mark.parametrize(
    "script",
    [
        _script_submit_reprice_terminal,
        _script_supersession_and_close,
        _script_recovery_window,
    ],
    ids=["submit-reprice-terminal", "supersession-close", "recovery-window"],
)
async def test_r2_dual_store_snapshots_are_exact_after_every_step(
    tmp_path, monkeypatch, script
):
    memory = await _run_deterministic(monkeypatch, InMemoryStateStore, script)
    sqlite = await _run_deterministic(
        monkeypatch,
        lambda: SqliteStateStore(tmp_path / f"{script.__name__}.db"),
        script,
    )

    assert memory == sqlite, _first_difference(memory, sqlite)
    assert len(memory) > 1


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
async def test_fault_snapshot_includes_session_scoped_audit_events(tmp_path, kind):
    store = _new_store(kind, tmp_path / f"snapshot-audit-{kind}.db")
    try:
        session, _ = await _prepare_owner(store)
        before = await _snapshot(store)
        await store.append_event(
            "session_closed",
            message="session-scoped event with no intent or order identity",
            session_id=session.id,
        )
        after = await _snapshot(store)
        assert len(after["audit_events"]) == len(before["audit_events"]) + 1
        assert after != before
    finally:
        await store.close()


def _first_difference(left: Any, right: Any, path: str = "root") -> str:
    """Compact path-oriented diagnostic for a deeply canonical snapshot."""

    if type(left) is not type(right):
        return f"{path}: type {type(left).__name__} != {type(right).__name__}"
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return f"{path}: keys {left.keys()} != {right.keys()}"
        for key in left:
            if left[key] != right[key]:
                return _first_difference(left[key], right[key], f"{path}.{key}")
        return f"{path}: dictionaries compare unequal without a differing item"
    if isinstance(left, (list, tuple)):
        if len(left) != len(right):
            return f"{path}: length {len(left)} != {len(right)}"
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
            if left_item != right_item:
                return _first_difference(left_item, right_item, f"{path}[{index}]")
        return f"{path}: sequences compare unequal without a differing item"
    return f"{path}: {left!r} != {right!r}"


class _InjectedWriteFailure(BaseException):
    """Simulated process death at one durable write boundary."""


class _WriteProbe:
    def __init__(self, fail_at: int | None) -> None:
        self.fail_at = fail_at
        self.calls: list[str] = []

    def hit(self, label: str) -> None:
        self.calls.append(label)
        if self.fail_at == len(self.calls):
            raise _InjectedWriteFailure(label)


class _FaultCursor:
    """SQLite cursor proxy that can crash after any mutating statement."""

    _MUTATIONS = {"INSERT", "UPDATE", "DELETE", "REPLACE"}

    def __init__(self, cursor: Any, probe: _WriteProbe) -> None:
        self._cursor = cursor
        self._probe = probe

    def execute(self, sql: str, parameters: Any = ()) -> Any:
        verb = sql.lstrip().split(maxsplit=1)[0].upper()
        result = self._cursor.execute(sql, parameters)
        if verb in self._MUTATIONS:
            self._probe.hit(" ".join(sql.split()))
        return result

    def executemany(self, sql: str, parameters: Any) -> Any:
        verb = sql.lstrip().split(maxsplit=1)[0].upper()
        result = self._cursor.executemany(sql, parameters)
        if verb in self._MUTATIONS:
            self._probe.hit(" ".join(sql.split()))
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


def _install_write_probe(
    store: Any, *, fail_at: int | None
) -> tuple[_WriteProbe, Callable[[], None]]:
    probe = _WriteProbe(fail_at)
    if isinstance(store, InMemoryStateStore):
        names = ("_append_event_unlocked", "_append_execution_event_unlocked")
        originals = {name: getattr(store, name) for name in names}
        for name, original in originals.items():

            def wrapped(*args, _name=name, _original=original, **kwargs):
                result = _original(*args, **kwargs)
                probe.hit(_name)
                return result

            setattr(store, name, wrapped)

        def restore() -> None:
            for name, original in originals.items():
                setattr(store, name, original)

        return probe, restore

    original_tx = store._tx

    @contextmanager
    def faulting_tx():
        with original_tx() as cursor:
            yield _FaultCursor(cursor, probe)

    store._tx = faulting_tx
    return probe, lambda: setattr(store, "_tx", original_tx)


async def _prepare_fault_operation(
    store: Any, operation: str
) -> Callable[[Any], Awaitable[Any]]:
    session, intent = await _prepare_owner(store)
    logical_now = datetime.fromisoformat(f"{session.session_date}T18:00:00+00:00")
    if operation == "activation":
        draft = _draft(
            intent.id,
            session_id=session.id,
            expires_at=logical_now + timedelta(hours=2),
        )

        async def activate(target):
            return await target.approve_envelope_activation(
                draft.model_copy(deep=True), actor="operator-a"
            )

        return activate

    envelope = await store.approve_envelope_activation(
        _draft(
            intent.id,
            session_id=session.id,
            expires_at=logical_now + timedelta(hours=2),
        ),
        actor="operator-a",
    )
    if operation == "stage":

        async def stage(target):
            return await target.stage_envelope_action(
                envelope.id,
                _action(),
                snapshot_fingerprint="fault-stage",
                now=logical_now,
            )

        return stage

    if operation in {"claim", "acknowledge", "recovery-resolution", "fill"}:
        staged = await store.stage_envelope_action(
            envelope.id,
            _action(),
            snapshot_fingerprint=f"fault-{operation}",
            now=logical_now,
        )
        assert staged.order is not None, (
            staged.outcome,
            staged.envelope.status,
            (await store.list_events())[-1].payload,
        )
        if operation == "claim":

            async def claim(target):
                return await target.claim_order_for_submission(staged.order.id)

            return claim
        claim_result = await store.claim_order_for_submission(staged.order.id)
        assert claim_result.outcome == CLAIM_CLAIMED, claim_result.reason
        if operation == "acknowledge":

            async def acknowledge(target):
                return await target.transition_order(
                    staged.order.id,
                    OrderStatus.SUBMITTED,
                    broker_order_id="broker-fault-ack",
                )

            return acknowledge
        if operation == "fill":
            await store.transition_order(
                staged.order.id,
                OrderStatus.SUBMITTED,
                broker_order_id="broker-fault-fill",
            )

            async def fill(target):
                return await target.record_envelope_fill(
                    envelope.id,
                    quantity=100,
                    dedupe_key=f"fill:{staged.order.id}:fault-sweep",
                    price=9.9,
                    order_id=staged.order.id,
                    session_id=session.id,
                    now=logical_now + timedelta(milliseconds=100),
                )

            return fill
        await store.transition_envelope(
            envelope.id,
            EnvelopeStatus.BREACHED,
            reason="fault recovery terminal",
            now=logical_now + timedelta(milliseconds=100),
        )
        recovery = await store.create_submit_recovery(
            local_order_id=staged.order.id,
            broker_order_id="broker-fault-recovery",
            client_order_id=staged.order.id,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=100,
            limit_price=9.9,
            failure_reason="fault sweep accepted race",
            session_id=session.id,
        )

        async def resolve_recovery(target):
            return await target.update_submit_recovery(
                recovery.id, cleanup_status=RECOVERY_RESOLVED
            )

        return resolve_recovery
    if operation == "terminal":

        async def terminal(target):
            return await target.transition_envelope(
                envelope.id,
                EnvelopeStatus.BREACHED,
                reason="fault terminal",
                now=logical_now + timedelta(milliseconds=100),
            )

        return terminal
    if operation == "supersede":
        successor = _draft(
            intent.id,
            qty_ceiling=90,
            remaining_quantity=90,
            floor_price=9.1,
            session_id=session.id,
            expires_at=logical_now + timedelta(hours=2),
        )

        async def supersede(target):
            return await target.supersede_envelope(
                envelope.id,
                successor.model_copy(deep=True),
                actor="operator-a",
                reason="fault bounded amendment",
            )

        return supersede
    assert operation == "close"

    async def close(target):
        return await target.close_session(session.id, actor="operator-a")

    return close


def _new_store(kind: str, path: Any) -> Any:
    if kind == "memory":
        return InMemoryStateStore()
    return SqliteStateStore(path)


async def _trace_operation_writes(kind: str, operation: str, path: Any) -> int:
    store = _new_store(kind, path)
    try:
        mutate = await _prepare_fault_operation(store, operation)
        probe, restore = _install_write_probe(store, fail_at=None)
        try:
            await mutate(store)
        finally:
            restore()
        return len(probe.calls)
    finally:
        await store.close()


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
@pytest.mark.parametrize(
    "operation",
    [
        "activation",
        "stage",
        "claim",
        "acknowledge",
        "terminal",
        "supersede",
        "recovery-resolution",
        "fill",
        "close",
    ],
)
async def test_every_observed_r2_write_boundary_rolls_back_and_retries(
    tmp_path, monkeypatch, kind, operation
):
    _install_determinism(monkeypatch)
    write_count = await _trace_operation_writes(
        kind, operation, tmp_path / f"trace-{kind}-{operation}.db"
    )
    assert write_count > 0, f"{kind}/{operation} exercised no injected write"

    clean_store = _new_store(kind, tmp_path / f"clean-success-{kind}-{operation}.db")
    try:
        clean_mutate = await _prepare_fault_operation(clean_store, operation)
        await clean_mutate(clean_store)
        clean_success = await _snapshot(clean_store)
    finally:
        await clean_store.close()

    for fail_at in range(1, write_count + 1):
        path = tmp_path / f"fault-{kind}-{operation}-{fail_at}.db"
        store = _new_store(kind, path)
        try:
            mutate = await _prepare_fault_operation(store, operation)
            before = await _snapshot(store)
            probe, restore = _install_write_probe(store, fail_at=fail_at)
            try:
                with pytest.raises(_InjectedWriteFailure):
                    await mutate(store)
            finally:
                restore()
            assert len(probe.calls) == fail_at

            if kind == "sqlite":
                await store.close()
                store = SqliteStateStore(path)
                await store.initialize()
            after = await _snapshot(store)
            assert after == before, (
                f"{kind}/{operation} leaked write {fail_at}/{write_count}: "
                f"{_first_difference(before, after)}"
            )

            await mutate(store)
            retried = await _snapshot(store)
            assert retried == clean_success, (
                f"{kind}/{operation} retry after write {fail_at}/{write_count} "
                f"diverged from a clean commit: "
                f"{_first_difference(clean_success, retried)}"
            )
        finally:
            await store.close()


def _terminal_envelope(*, ceiling: int, floor: float) -> ExecutionEnvelope:
    return _draft(
        "owner-1",
        id="envelope-1",
        qty_ceiling=ceiling,
        remaining_quantity=ceiling,
        floor_price=floor,
        session_id="session-1",
    ).model_copy(
        update={
            "status": EnvelopeStatus.BREACHED,
            "approved_at": T0 - timedelta(seconds=1),
            "activated_at": T0 - timedelta(seconds=1),
            "breached_at": T0,
        }
    )


def _bounded_child(
    envelope: ExecutionEnvelope,
    *,
    quantity: int,
    price: float,
    status: OrderStatus,
) -> tuple[Order, ExecutionEvent]:
    order = Order(
        id="child-1",
        sell_intent_id=envelope.sell_intent_id,
        symbol=envelope.symbol,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=quantity,
        limit_price=price,
        status=status,
        session_id=envelope.session_id,
    )
    action = ExecutionEvent(
        sequence=1,
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=T0,
        ts_init=T0,
        symbol=order.symbol,
        side=order.side,
        quantity=quantity,
        price=price,
        order_id=order.id,
        envelope_id=envelope.id,
        session_id=order.session_id,
        correlation_id=envelope.sell_intent_id,
        payload={"action": "submit", "snapshot_fingerprint": "generated"},
    )
    return order, action


@pytest.mark.parametrize("uncertainty", ["claim", "recovery"])
def test_claim_and_recovery_uncertainty_cannot_release_terminal_child(uncertainty):
    envelope = _terminal_envelope(ceiling=100, floor=9.0)
    order, action = _bounded_child(
        envelope, quantity=100, price=9.9, status=OrderStatus.CANCELED
    )
    order_events = []
    open_recoveries = frozenset()
    if uncertainty == "claim":
        order_events.append(
            ExecutionEvent(
                sequence=2,
                event_type=ExecutionEventType.SUBMIT_PENDING,
                source=EventSource.ENGINE,
                authority=EventAuthority.LOCAL,
                ts_event=T0,
                ts_init=T0,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=order.limit_price,
                order_id=order.id,
                envelope_id=envelope.id,
                session_id=order.session_id,
                correlation_id=envelope.sell_intent_id,
                payload={"claim_occurrence": 0},
            )
        )
    else:
        open_recoveries = frozenset({order.id})

    projected = project_envelope_obligation(
        envelopes=[envelope],
        action_events=[action],
        orders_by_id={order.id: order},
        order_events=order_events,
        open_recovery_order_ids=open_recoveries,
    )

    assert projected.retains_intent is True
    assert projected.unresolved_order_ids == (order.id,)
    if uncertainty == "claim":
        assert projected.uncertain_claim_order_ids == (order.id,)
    else:
        assert projected.recovery_order_ids == (order.id,)
    assert projected.claimable_order_ids == ()
    assert projected.acknowledgeable_order_ids == ()


@given(
    ceiling=st.integers(min_value=1, max_value=10_000),
    quantity=st.integers(min_value=1, max_value=10_000),
    floor=st.integers(min_value=1, max_value=10_000).map(lambda value: value / 100),
    price_delta=st.integers(min_value=-100, max_value=100).map(
        lambda value: value / 100
    ),
    status=st.sampled_from(list(OrderStatus)),
)
@hyp_settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_generated_child_bounds_never_release_an_unsafe_delegation(
    ceiling, quantity, floor, price_delta, status
):
    price = max(0.01, floor + price_delta)
    envelope = _terminal_envelope(ceiling=ceiling, floor=floor)
    order, action = _bounded_child(
        envelope, quantity=quantity, price=price, status=status
    )

    projected = project_envelope_obligation(
        envelopes=[envelope],
        action_events=[action],
        orders_by_id={order.id: order},
    )

    bounded = quantity <= ceiling and price >= floor
    terminal = status in {
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
    }
    assert projected.retains_intent is not (bounded and terminal)
    if not bounded:
        assert projected.invalid_order_ids == (order.id,)
    elif not terminal:
        assert projected.unresolved_order_ids == (order.id,)


@pytest.mark.parametrize(
    "defect",
    [
        "missing-order",
        "wrong-owner",
        "wrong-symbol",
        "wrong-session",
        "wrong-source",
        "wrong-authority",
        "missing-parent",
    ],
)
def test_one_identity_defect_always_fails_closed(defect):
    envelope = _terminal_envelope(ceiling=100, floor=9.0)
    order, action = _bounded_child(
        envelope, quantity=100, price=9.9, status=OrderStatus.CANCELED
    )
    orders = {order.id: order}
    envelopes = [envelope]
    if defect == "missing-order":
        orders = {}
    elif defect == "wrong-owner":
        order = order.model_copy(update={"sell_intent_id": "foreign-owner"})
        orders = {order.id: order}
    elif defect == "wrong-symbol":
        action = action.model_copy(update={"symbol": "MSFT"})
    elif defect == "wrong-session":
        action = action.model_copy(update={"session_id": "foreign-session"})
    elif defect == "wrong-source":
        action = action.model_copy(update={"source": EventSource.BROKER_REST})
    elif defect == "wrong-authority":
        action = action.model_copy(
            update={"authority": EventAuthority.BROKER_AUTHORITATIVE}
        )
    else:
        envelopes = []

    first = project_envelope_obligation(
        envelopes=envelopes, action_events=[action], orders_by_id=orders
    )
    second = project_envelope_obligation(
        envelopes=list(reversed(envelopes)),
        action_events=[action],
        orders_by_id=dict(reversed(list(orders.items()))),
    )

    assert first == second
    assert first.linked is True
    assert first.retains_intent is True
    assert (
        first.missing_envelope_ids or first.missing_order_ids or first.invalid_order_ids
    )
