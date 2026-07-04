"""Regression tests for the AIR-001…AIR-011 adversarial remediation.

Each test pins a *verified defect* (reproduced firsthand on the pre-fix tree) so
it can never silently regress. Store-facing behavior is exercised against BOTH
stores via the ``any_store`` fixture — parity (identical accept/reject, persisted
value, readback, event, error class) is a hard invariant of this remediation.
"""

from __future__ import annotations

import math

import pytest

from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_RESOLVED,
    RECOVERY_UNRESOLVED,
    CandidateStatus,
    OrderSide,
    OrderStatus,
)
from app.store.base import InvalidStatusError, RecoveryTransitionError

pytestmark = pytest.mark.anyio


async def _recovery(store, **over):
    kw = dict(
        local_order_id="o1",
        broker_order_id="bk-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        limit_price=1.0,
        failure_reason="unpersisted",
    )
    kw.update(over)
    return await store.create_submit_recovery(**kw)


# --------------------------------------------------------------------------- #
# A1 · AIR-004 — recovery ledger: enum status + transition table
# --------------------------------------------------------------------------- #
class TestAir004RecoveryStatusTransitions:
    async def test_unknown_status_rejected_no_mutation(self, any_store):
        await any_store.initialize()
        rec = await _recovery(any_store)
        with pytest.raises(RecoveryTransitionError):
            await any_store.update_submit_recovery(rec.id, cleanup_status="typo_resolved")
        # No state change, no event emitted.
        after = (await any_store.list_submit_recoveries())[0]
        assert after.cleanup_status == RECOVERY_UNRESOLVED
        assert not [
            e for e in await any_store.list_events()
            if e.event_type.startswith("submit_recovery_") and e.event_type != "submit_recovery_recorded"
        ]

    @pytest.mark.parametrize(
        "new_status,event",
        [
            (RECOVERY_RESOLVED, "submit_recovery_resolved"),
            (RECOVERY_NEEDS_REVIEW, "submit_recovery_needs_review"),
        ],
    )
    async def test_allowed_automatic_transitions_emit_event(self, any_store, new_status, event):
        await any_store.initialize()
        rec = await _recovery(any_store)
        updated = await any_store.update_submit_recovery(rec.id, cleanup_status=new_status)
        assert updated.cleanup_status == new_status
        assert any(e.event_type == event for e in await any_store.list_events())

    @pytest.mark.parametrize("terminal", [RECOVERY_RESOLVED, RECOVERY_NEEDS_REVIEW])
    async def test_no_silent_reopen_of_terminal_record(self, any_store, terminal):
        await any_store.initialize()
        rec = await _recovery(any_store)
        await any_store.update_submit_recovery(rec.id, cleanup_status=terminal)
        events_before = len(await any_store.list_events())
        with pytest.raises(RecoveryTransitionError):
            await any_store.update_submit_recovery(rec.id, cleanup_status=RECOVERY_UNRESOLVED)
        after = (await any_store.list_submit_recoveries())[0]
        assert after.cleanup_status == terminal  # unchanged, no reopen
        assert len(await any_store.list_events()) == events_before  # no event

    async def test_bump_attempt_without_status_change_still_allowed(self, any_store):
        # The recovery loop bumps retry_count on an unresolved record every tick
        # with no status change — that must stay a legal no-op (no event, no error).
        await any_store.initialize()
        rec = await _recovery(any_store)
        updated = await any_store.update_submit_recovery(rec.id, bump_attempt=True)
        assert updated.retry_count == 1
        assert updated.cleanup_status == RECOVERY_UNRESOLVED


# --------------------------------------------------------------------------- #
# A4 · AIR-007 — one path into SUBMITTING (the atomic claim), not generic
# transition_order
# --------------------------------------------------------------------------- #
class TestAir007OnlyClaimEntersSubmitting:
    async def test_generic_transition_created_to_submitting_rejected(self, any_store):
        from app.models import CandidateStatus, OrderStatus
        from app.store.base import OrderTransitionError

        await any_store.initialize()
        cand = await any_store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=1.0
        )
        await any_store.transition_candidate(cand.id, CandidateStatus.APPROVED)
        order = await any_store.create_order_for_candidate(cand.id)
        # The generic transition path must NOT be a back door into SUBMITTING —
        # only claim_order_for_submission (with its atomic control re-check) may.
        with pytest.raises(OrderTransitionError):
            await any_store.transition_order(order.id, OrderStatus.SUBMITTING)
        assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED

    async def test_claim_still_enters_submitting(self, any_store):
        from app.models import CandidateStatus, OrderStatus
        from app.store.base import CLAIM_CLAIMED

        await any_store.initialize()
        cand = await any_store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=1.0
        )
        await any_store.transition_candidate(cand.id, CandidateStatus.APPROVED)
        order = await any_store.create_order_for_candidate(cand.id)
        claim = await any_store.claim_order_for_submission(order.id)
        assert claim.outcome == CLAIM_CLAIMED
        assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTING


# --------------------------------------------------------------------------- #
# A3 · AIR-006 — the ungated low-level create_order is off the public surface
# --------------------------------------------------------------------------- #
class TestAir006CreateOrderQuarantined:
    def test_create_order_not_on_public_statestore_contract(self):
        from app.store.base import StateStore

        # It was a public abstract method that accepted qty=-100 and bypassed all
        # gates, with no production caller. It must no longer be part of the
        # StateStore contract at all.
        assert not hasattr(StateStore, "create_order")
        assert "create_order" not in getattr(StateStore, "__abstractmethods__", frozenset())

    def test_no_production_code_calls_create_order_for_test(self):
        # The test-only helper must never be *called* from app/ (routes,
        # monitoring, services) — only from tests. (Its own method definition +
        # docstrings live on the store classes, so we look for a call site
        # `.create_order_for_test(`, not a bare mention.)
        import pathlib
        import re

        app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
        call = re.compile(r"\.create_order_for_test\(")
        offenders = [
            str(p) for p in app_dir.rglob("*.py") if call.search(p.read_text())
        ]
        assert offenders == [], f"create_order_for_test called in production: {offenders}"


# --------------------------------------------------------------------------- #
# A5 · AIR-009 — enum/string parity at the store boundary (require enum
# instances; reject strings/bools/None identically in both stores)
# --------------------------------------------------------------------------- #
class TestAir009EnumStringParity:
    @pytest.mark.parametrize("bad", ["pending", True, 0])
    async def test_list_candidates_rejects_non_enum_status(self, any_store, bad):
        await any_store.initialize()
        await any_store.create_candidate("AAPL")
        with pytest.raises(InvalidStatusError):
            await any_store.list_candidates(status=bad)

    async def test_list_candidates_none_returns_all(self, any_store):
        await any_store.initialize()
        await any_store.create_candidate("AAPL")
        assert len(await any_store.list_candidates()) == 1
        assert len(await any_store.list_candidates(status=None)) == 1

    async def test_list_candidates_enum_filter_still_works(self, any_store):
        await any_store.initialize()
        await any_store.create_candidate("AAPL")
        assert len(await any_store.list_candidates(status=CandidateStatus.PENDING)) == 1
        assert len(await any_store.list_candidates(status=CandidateStatus.APPROVED)) == 0

    @pytest.mark.parametrize("bad", ["approved", True, None])
    async def test_transition_candidate_rejects_non_enum_status(self, any_store, bad):
        await any_store.initialize()
        cand = await any_store.create_candidate("AAPL")
        with pytest.raises(InvalidStatusError):
            await any_store.transition_candidate(cand.id, bad)
        # No mutation.
        assert (await any_store.get_candidate(cand.id)).status is CandidateStatus.PENDING

    @pytest.mark.parametrize("bad", ["submitted", True, None])
    async def test_transition_order_rejects_non_enum_status(self, any_store, bad):
        await any_store.initialize()
        cand = await any_store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=1.0
        )
        await any_store.transition_candidate(cand.id, CandidateStatus.APPROVED)
        order = await any_store.create_order_for_candidate(cand.id)
        with pytest.raises(InvalidStatusError):
            await any_store.transition_order(order.id, bad)
        assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED


# --------------------------------------------------------------------------- #
# A2 · AIR-005 — strict booleans on all four control/flag surfaces (store +
# route), no silent coercion (a "false" string must NOT engage an emergency stop)
# --------------------------------------------------------------------------- #
# The full coercion class the setters must reject.
_NON_BOOLS = ["true", "false", "0", "1", "on", "off", "yes", "no", 0, 1, [], {}, None]


class TestAir005StrictBooleansStore:
    @pytest.mark.parametrize("bad", _NON_BOOLS)
    async def test_set_kill_switch_rejects_non_bool(self, any_store, bad):
        from app.store.base import InvalidControlValueError

        await any_store.initialize()
        with pytest.raises(InvalidControlValueError):
            await any_store.set_kill_switch(bad)
        # The emergency stop is NOT engaged by a stray value (the inversion bug).
        assert (await any_store.get_current_session()).kill_switch is False

    @pytest.mark.parametrize("bad", _NON_BOOLS)
    async def test_set_buys_paused_rejects_non_bool(self, any_store, bad):
        from app.store.base import InvalidControlValueError

        await any_store.initialize()
        with pytest.raises(InvalidControlValueError):
            await any_store.set_buys_paused(bad)
        assert (await any_store.get_current_session()).buys_paused is False

    @pytest.mark.parametrize("bad", _NON_BOOLS)
    async def test_add_watchlist_symbol_rejects_non_bool_armed(self, any_store, bad):
        from app.store.base import InvalidControlValueError

        await any_store.initialize()
        with pytest.raises(InvalidControlValueError):
            await any_store.add_watchlist_symbol("AAPL", armed=bad)

    @pytest.mark.parametrize("bad", _NON_BOOLS)
    async def test_set_watchlist_armed_rejects_non_bool(self, any_store, bad):
        from app.store.base import InvalidControlValueError

        await any_store.initialize()
        await any_store.add_watchlist_symbol("AAPL", armed=False)
        with pytest.raises(InvalidControlValueError):
            await any_store.set_watchlist_armed("AAPL", bad)
        # State unchanged.
        wl = {w.symbol: w for w in await any_store.list_watchlist()}
        assert wl["AAPL"].armed is False

    async def test_real_bools_still_accepted(self, any_store):
        await any_store.initialize()
        assert (await any_store.set_kill_switch(True)).kill_switch is True
        assert (await any_store.set_kill_switch(False)).kill_switch is False
        assert (await any_store.set_buys_paused(True)).buys_paused is True
        w = await any_store.add_watchlist_symbol("AAPL", armed=True)
        assert w.armed is True
        assert (await any_store.set_watchlist_armed("AAPL", False)).armed is False


class TestAir005StrictBooleansRoute:
    def _client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        from app.store.memory import InMemoryStateStore

        return TestClient(create_app(InMemoryStateStore()))

    def test_kill_switch_route_rejects_false_string(self):
        with self._client() as client:
            # {"engaged":"false"} meant to DISENGAGE must be a clean 422, never
            # silently coerced (the emergency-stop inversion).
            resp = client.post("/api/controls/kill-switch", json={"engaged": "false"})
            assert resp.status_code == 422, resp.text
            # And the switch was never touched.
            assert client.get("/api/session").json()["kill_switch"] is False

    @pytest.mark.parametrize("bad", ["true", "false", "1", 1, 0])
    def test_kill_switch_route_rejects_coercion_class(self, bad):
        with self._client() as client:
            assert client.post(
                "/api/controls/kill-switch", json={"engaged": bad}
            ).status_code == 422

    @pytest.mark.parametrize("bad", ["true", "false", 1, 0])
    def test_watchlist_route_rejects_non_bool_armed(self, bad):
        with self._client() as client:
            assert client.post(
                "/api/watchlist", json={"symbol": "AAPL", "armed": bad}
            ).status_code == 422

    def test_kill_switch_route_accepts_real_bool(self):
        with self._client() as client:
            assert client.post(
                "/api/controls/kill-switch", json={"engaged": True}
            ).status_code == 200
            assert client.get("/api/session").json()["kill_switch"] is True


# --------------------------------------------------------------------------- #
# A2 · AIR-008 — candidate numerics validated at the store boundary (both
# stores reject the full coercion class identically; no non-finite persists)
# --------------------------------------------------------------------------- #
class TestAir008CandidateNumerics:
    @pytest.mark.parametrize(
        "qty", [math.nan, math.inf, -math.inf, 0, -5, 2.5, True, "5"]
    )
    async def test_create_candidate_rejects_bad_quantity(self, any_store, qty):
        from app.store.base import InvalidOrderError

        await any_store.initialize()
        with pytest.raises(InvalidOrderError):
            await any_store.create_candidate(
                "AAPL", suggested_quantity=qty, suggested_limit_price=1.0
            )
        assert await any_store.list_candidates() == []  # nothing persisted

    @pytest.mark.parametrize(
        "price", [math.nan, math.inf, -math.inf, 0, 0.0, -1.5, True, "5.0"]
    )
    async def test_create_candidate_rejects_bad_price(self, any_store, price):
        from app.store.base import InvalidOrderError

        await any_store.initialize()
        with pytest.raises(InvalidOrderError):
            await any_store.create_candidate(
                "AAPL", suggested_quantity=10, suggested_limit_price=price
            )
        assert await any_store.list_candidates() == []

    async def test_none_and_valid_still_accepted(self, any_store):
        await any_store.initialize()
        c1 = await any_store.create_candidate("AAPL")  # both absent
        assert c1.suggested_quantity is None and c1.suggested_limit_price is None
        c2 = await any_store.create_candidate(
            "MSFT", suggested_quantity=10, suggested_limit_price=1.5
        )
        assert c2.suggested_quantity == 10 and c2.suggested_limit_price == 1.5

    async def test_nan_price_parity_both_reject_none_persist(self, any_store):
        # The parity break: memory used to roundtrip nan, SQLite roundtripped
        # None. Now BOTH reject at the boundary — identical, nothing stored.
        from app.store.base import InvalidOrderError

        await any_store.initialize()
        with pytest.raises(InvalidOrderError):
            await any_store.create_candidate(
                "AAPL", suggested_quantity=10, suggested_limit_price=math.nan
            )
        assert await any_store.list_candidates() == []


# --------------------------------------------------------------------------- #
# A2 · AIR-008 (serialization) — an API response never emits a non-JSON float,
# even if a non-finite value was persisted by a legacy/other path.
# --------------------------------------------------------------------------- #
class TestAir008SerializationGuard:
    def test_candidate_with_persisted_inf_serializes_as_null(self):
        import json

        from app.models import Candidate

        # A model holding a non-finite float (as a legacy row would) must dump to
        # valid JSON with `null`, never `Infinity` (invalid JSON / a crash).
        c = Candidate.model_construct(
            symbol="AAPL", suggested_limit_price=math.inf, suggested_quantity=10
        )
        raw = c.model_dump_json()
        assert "Infinity" not in raw and "NaN" not in raw
        parsed = json.loads(raw)  # must be valid JSON (would raise otherwise)
        assert parsed["suggested_limit_price"] is None

    def test_order_with_persisted_inf_serializes_as_null(self):
        import json

        from app.models import Order, OrderSide, OrderType

        o = Order.model_construct(
            candidate_id="c1", symbol="AAPL", side=OrderSide.BUY,
            order_type=OrderType.LIMIT, quantity=10, limit_price=math.inf,
        )
        raw = o.model_dump_json()
        assert "Infinity" not in raw
        assert json.loads(raw)["limit_price"] is None

    def test_sqlite_readback_of_inf_price_is_valid_json_via_api(self):
        # A candidate row persisted with inf (bypassing the write guard, as
        # legacy data could be) must not crash readback or emit invalid JSON
        # through the actual FastAPI response path — the model-level guard
        # above only proves `model_dump_json`, not FastAPI's response encoder.
        import json
        import os
        import tempfile

        from fastapi.testclient import TestClient

        from app.main import create_app
        from app.store.sqlite import SqliteStateStore

        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = SqliteStateStore(path)
            app = create_app(store)
            with TestClient(app) as client:  # lifespan initializes the store
                session_id = client.get("/api/session").json()["id"]
                # Insert a candidate carrying a non-finite price directly,
                # bypassing the write guard the way a legacy row would.
                store._conn.execute(
                    "INSERT INTO candidates (id, symbol, status, session_id, "
                    "suggested_limit_price, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    ("cid", "AAPL", "pending", session_id, float("inf"),
                     "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
                )
                store._conn.commit()

                resp = client.get("/api/candidates")
                assert resp.status_code == 200, resp.text
                assert "Infinity" not in resp.text and "NaN" not in resp.text
                body = json.loads(resp.text)  # valid JSON or this raises
                row = next(c for c in body if c["id"] == "cid")
                assert row["suggested_limit_price"] is None
        finally:
            os.remove(path)
