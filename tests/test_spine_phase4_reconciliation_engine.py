"""Spine v2 Phase 4 wave 4b — the pure reconciliation engine (§7).

Deterministic, IO-free unit + property tests. Nothing is wired yet (waves 4d/4e);
this pins the §7 decision logic + the load-bearing safeguards: absence never
becomes a reject here (only a targeted-query request), a position divergence is
surfaced never overwritten, no $0 synthetic fill is fabricated, and the plan is
deterministic (§12).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from app.broker.adapter import (
    BrokerFill,
    BrokerOrderReport,
    BrokerPositionReport,
    VenueOrderScope,
)
from app.models import Order, OrderSide, OrderStatus, OrderType, Position
from app.reconciliation import OPEN_STATUSES, plan_reconciliation

_NOW = datetime(2026, 7, 7, 15, 30, tzinfo=timezone.utc)
_OLD = _NOW - timedelta(hours=1)  # well outside recent-order protection


def _order(**kw) -> Order:
    defaults = dict(
        id="o1",
        candidate_id="c1",
        sell_intent_id=None,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        status=OrderStatus.SUBMITTED,
        filled_quantity=0,
        broker_order_id="b1",
        updated_at=_OLD,
    )
    defaults.update(kw)
    return Order(**defaults)


def _report(**kw) -> BrokerOrderReport:
    defaults = dict(
        broker_order_id="b1",
        client_order_id="o1",
        symbol="AAPL",
        side=OrderSide.BUY,
        status=OrderStatus.SUBMITTED,
        filled_quantity=0,
        fills=[],
    )
    defaults.update(kw)
    return BrokerOrderReport(**defaults)


def _plan(
    orders=None,
    positions=None,
    breports=None,
    bpositions=None,
    now=_NOW,
    scopes=None,
):
    return plan_reconciliation(
        local_open_orders=orders or [],
        local_positions=positions or [],
        broker_orders=breports or [],
        broker_positions=bpositions or [],
        now=now,
        venue_scopes_by_order_id=scopes,
    )


# --------------------------------------------------------------------------- #
# Order matching + resolution
# --------------------------------------------------------------------------- #
def test_matched_broker_canceled_resolves():
    plan = _plan([_order()], breports=[_report(status=OrderStatus.CANCELED)])
    assert [(r.order_id, r.new_status) for r in plan.resolutions] == [
        ("o1", OrderStatus.CANCELED)
    ]
    assert plan.needs_targeted_query == []


def test_matched_broker_rejected_resolves():
    plan = _plan([_order()], breports=[_report(status=OrderStatus.REJECTED)])
    assert plan.resolutions[0].new_status is OrderStatus.REJECTED


def test_matched_broker_filled_is_NOT_a_bare_status_flip():
    # FILLED must flow through a fill (with a price), never a bare status flip
    # (Rule 7). A report saying FILLED with a priced fill infers the fill; with no
    # price it asks for a targeted poll — but never emits a FILLED resolution.
    plan = _plan(
        [_order()],
        breports=[_report(status=OrderStatus.FILLED, filled_quantity=100)],
    )
    assert plan.resolutions == []  # no bare FILLED flip
    assert plan.needs_targeted_query == ["o1"]  # fetch the price


def test_matches_by_client_order_id_when_no_broker_id():
    # An order whose ack we lost (no broker_order_id) is still matched by client id.
    order = _order(broker_order_id=None)
    plan = _plan([order], breports=[_report(status=OrderStatus.CANCELED)])
    assert plan.resolutions[0].new_status is OrderStatus.CANCELED


def test_known_broker_id_rejects_foreign_report_even_when_client_id_matches():
    report = _report(
        broker_order_id="foreign-broker",
        client_order_id="o1",
        symbol="MSFT",
        side=OrderSide.SELL,
        status=OrderStatus.FILLED,
        filled_quantity=100,
        fills=[
            BrokerFill(
                source_fill_id="foreign-broker:100",
                quantity=100,
                price=321.0,
                filled_at=_NOW,
            )
        ],
    )

    plan = _plan([_order(broker_order_id="expected-broker")], breports=[report])

    assert plan.inferred_fills == []
    assert plan.resolutions == []
    assert plan.needs_targeted_query == ["o1"]
    assert [external.broker_order_id for external in plan.external_orders] == [
        "foreign-broker"
    ]


def test_exact_broker_id_requires_immutable_scope_and_client_correlation():
    report = _report(
        broker_order_id="b1",
        client_order_id="foreign-client",
        symbol="MSFT",
        side=OrderSide.SELL,
    )

    plan = _plan([_order()], breports=[report])

    assert plan.resolutions == []
    assert plan.inferred_fills == []
    assert plan.needs_targeted_query == ["o1"]
    assert [external.broker_order_id for external in plan.external_orders] == ["b1"]


def test_client_id_match_requires_symbol_and_side_agreement():
    for incompatible_report in (
        _report(broker_order_id="foreign-symbol", symbol="MSFT"),
        _report(broker_order_id="foreign-side", side=OrderSide.SELL),
    ):
        plan = _plan(
            [_order(broker_order_id=None)],
            breports=[incompatible_report],
        )

        assert plan.resolutions == []
        assert plan.needs_targeted_query == ["o1"]
        assert [external.broker_order_id for external in plan.external_orders] == [
            incompatible_report.broker_order_id
        ]


def test_mass_report_requires_exact_durable_replace_predecessor():
    order = _order(limit_price=10.0)
    scope = VenueOrderScope(
        client_order_id=order.id,
        symbol=order.symbol,
        side=OrderSide(order.side),
        quantity=order.quantity,
        order_type=OrderType.LIMIT,
        limit_price=10.0,
        extended_hours=False,
        replaces_broker_order_id="predecessor-broker",
    )
    exact = dict(
        quantity=100,
        order_type="limit",
        limit_price=10.0,
        time_in_force="day",
        order_class="simple",
        asset_class="us_equity",
        quantity_mode="qty",
        extended_hours=False,
        has_legs=False,
        position_intent="buy_to_open",
    )

    foreign = _report(
        **exact,
        replaces_broker_order_id="foreign-predecessor",
    )
    plan = _plan([order], breports=[foreign], scopes={order.id: scope})
    assert plan.needs_targeted_query == [order.id]
    assert [item.broker_order_id for item in plan.external_orders] == ["b1"]
    assert plan.external_orders[0].replaces_broker_order_id == "foreign-predecessor"

    matching = _report(
        **exact,
        replaces_broker_order_id="predecessor-broker",
    )
    matched = _plan([order], breports=[matching], scopes={order.id: scope})
    assert matched.needs_targeted_query == []
    assert matched.external_orders == []


def test_fractional_managed_fill_level_cannot_drive_fill_truth():
    report = _report(
        filled_quantity=0.5,
        fills=[BrokerFill("fractional-poison", 1, 10.0, _NOW)],
    )

    plan = _plan([_order()], breports=[report])

    assert plan.inferred_fills == []
    assert plan.needs_targeted_query == ["o1"]
    assert [item.broker_order_id for item in plan.external_orders] == ["b1"]


def test_advanced_mass_scope_cannot_be_absorbed_as_managed():
    report = _report(advanced_fields=("stop_price",))

    plan = _plan([_order()], breports=[report])

    assert plan.inferred_fills == []
    assert plan.resolutions == []
    assert plan.needs_targeted_query == ["o1"]
    assert [item.advanced_fields for item in plan.external_orders] == [("stop_price",)]


# --------------------------------------------------------------------------- #
# Absence NEVER becomes a reject here (§7 safeguard)
# --------------------------------------------------------------------------- #
def test_absent_local_order_requests_targeted_query_not_reject():
    plan = _plan([_order()], breports=[])  # order open locally, absent at venue
    assert plan.needs_targeted_query == ["o1"]
    assert plan.resolutions == []  # NEVER auto-rejected from a bare absence


# --------------------------------------------------------------------------- #
# Recent-order protection
# --------------------------------------------------------------------------- #
def test_recent_order_is_skipped():
    fresh = _order(updated_at=_NOW - timedelta(milliseconds=100))  # within 5s
    plan = _plan([fresh], breports=[])
    assert plan.skipped_recent == ["o1"]
    assert plan.needs_targeted_query == []  # not even queried while settling


# --------------------------------------------------------------------------- #
# External / unmanaged orders
# --------------------------------------------------------------------------- #
def test_unmatched_broker_order_is_external():
    plan = _plan(
        [],
        breports=[_report(broker_order_id="bX", client_order_id="external-1")],
    )
    assert len(plan.external_orders) == 1
    assert plan.external_orders[0].broker_order_id == "bX"


def test_our_order_is_never_external():
    plan = _plan([_order()], breports=[_report()])
    assert plan.external_orders == []


# --------------------------------------------------------------------------- #
# Inferred (synthetic) fills
# --------------------------------------------------------------------------- #
def test_inferred_fill_from_priced_report_fill():
    report = _report(
        status=OrderStatus.PARTIALLY_FILLED,
        filled_quantity=40,
        fills=[
            BrokerFill(source_fill_id="b1:40", quantity=40, price=9.5, filled_at=_NOW)
        ],
    )
    plan = _plan([_order()], breports=[report])
    assert len(plan.inferred_fills) == 1
    f = plan.inferred_fills[0]
    assert f.quantity == 40 and f.price == 9.5
    # Identity is the execution's OWN venue id — same the real poll would carry, so
    # a synthetic fill and the eventual real observation dedup (INV-5 / R8), never
    # double-count.
    assert f.source_fill_id == "b1:40"


def test_filled_qty_delta_with_no_price_asks_for_targeted_query():
    # No fabricated $0 fill — surface the price-less divergence for a targeted poll.
    report = _report(status=OrderStatus.PARTIALLY_FILLED, filled_quantity=40, fills=[])
    plan = _plan([_order()], breports=[report])
    assert plan.inferred_fills == []
    assert plan.needs_targeted_query == ["o1"]


def test_inferred_fill_identity_matches_real_poll_identity():
    # The inferred fill carries the report execution's own id — byte-identical to
    # what a real get_order_status poll would carry (alpaca_paper: {broker_id}:{cum}).
    # So both derive the SAME fill-event dedup key and collapse to one (no double-count).
    report = _report(
        status=OrderStatus.PARTIALLY_FILLED,
        filled_quantity=40,
        fills=[
            BrokerFill(source_fill_id="b1:40", quantity=40, price=9.5, filled_at=_NOW)
        ],
    )
    inferred = _plan([_order()], breports=[report]).inferred_fills[0]
    real_poll_source_fill_id = "b1:40"  # {broker_order_id}:{cumulative}
    assert inferred.source_fill_id == real_poll_source_fill_id


# --------------------------------------------------------------------------- #
# Position parity (surfaced, never overwritten)
# --------------------------------------------------------------------------- #
def test_position_quantity_mismatch_surfaced():
    plan = _plan(
        positions=[Position(symbol="AAPL", quantity=100, average_price=10.0)],
        bpositions=[
            BrokerPositionReport(symbol="AAPL", quantity=90, average_price=10.0)
        ],
    )
    assert len(plan.position_mismatches) == 1
    m = plan.position_mismatches[0]
    assert m.kind == "quantity" and m.local_quantity == 100 and m.broker_quantity == 90


def test_position_avg_within_tolerance_is_ok():
    # 0.01% tolerance: 10.00 vs 10.0009 is within.
    plan = _plan(
        positions=[Position(symbol="AAPL", quantity=100, average_price=10.0)],
        bpositions=[
            BrokerPositionReport(symbol="AAPL", quantity=100, average_price=10.0009)
        ],
    )
    assert plan.position_mismatches == []


def test_position_avg_beyond_tolerance_surfaced():
    plan = _plan(
        positions=[Position(symbol="AAPL", quantity=100, average_price=10.0)],
        bpositions=[
            BrokerPositionReport(symbol="AAPL", quantity=100, average_price=10.5)
        ],
    )
    assert plan.position_mismatches[0].kind == "avg_price"


def test_symbol_only_at_broker_is_a_quantity_mismatch():
    plan = _plan(bpositions=[BrokerPositionReport(symbol="AAPL", quantity=50)])
    assert plan.position_mismatches[0].kind == "quantity"
    assert plan.position_mismatches[0].local_quantity == 0


# --------------------------------------------------------------------------- #
# Property tests (§12) — determinism + load-bearing safeguards over interleavings
# --------------------------------------------------------------------------- #
_STATUSES = st.sampled_from(sorted(OPEN_STATUSES, key=lambda s: s.value))


@st.composite
def _orders(draw):
    n = draw(st.integers(min_value=0, max_value=6))
    out = []
    for i in range(n):
        has_bid = draw(st.booleans())
        out.append(
            _order(
                id=f"o{i}",
                broker_order_id=(f"b{i}" if has_bid else None),
                status=draw(_STATUSES),
                filled_quantity=draw(st.integers(min_value=0, max_value=100)),
                quantity=100,
                updated_at=_OLD,
            )
        )
    return out


@st.composite
def _reports(draw):
    n = draw(st.integers(min_value=0, max_value=6))
    out = []
    for i in range(n):
        out.append(
            _report(
                broker_order_id=f"b{i}",
                client_order_id=draw(st.sampled_from([f"o{i}", f"other{i}", None])),
                status=draw(st.sampled_from(list(OrderStatus))),
                filled_quantity=draw(st.integers(min_value=0, max_value=100)),
                fills=[],
            )
        )
    return out


@settings(max_examples=300)
@given(orders=_orders(), reports=_reports())
def test_property_deterministic_and_safe(orders, reports):
    plan1 = _plan(orders, breports=reports)
    plan2 = _plan(orders, breports=reports)
    assert plan1 == plan2  # deterministic (§12)

    local_by_id = {o.id: o for o in orders}
    local_ids = set(local_by_id)
    # Every targeted-query request is a real local open order — absence never
    # silently becomes anything else here.
    for oid in plan1.needs_targeted_query:
        assert oid in local_ids
    # The engine only ever resolves to a non-position terminal (cancel/reject),
    # never FILLED/PARTIALLY_FILLED via a bare status flip (Rule 7).
    for res in plan1.resolutions:
        assert res.new_status in (OrderStatus.CANCELED, OrderStatus.REJECTED)
    # A report carrying a local client id is external only when its concrete broker
    # identity conflicts or its immutable symbol/side scope does not agree.
    for ext in plan1.external_orders:
        local = local_by_id.get(ext.client_order_id)
        if local is not None:
            assert (
                (
                    local.broker_order_id is not None
                    and local.broker_order_id != ext.broker_order_id
                )
                or ext.symbol != local.symbol
                or ext.side != local.side
            )
