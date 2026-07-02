"""Streamlit cockpit entrypoint.

Run with:  streamlit run cockpit/app.py

Five screens (see docs/03_UI_WORKFLOW.md): Session Control, Watchlist Input,
Candidate Monitor, Position Monitor, Daily Review. Watchlist Input is fully
functional; the other monitors render real (currently empty) backend data with
clear empty states — never mock data.

Thin-client discipline: no business state in st.session_state beyond view
concerns; every render reads fresh from the backend; every action is an API
call via cockpit.api_client.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

import streamlit as st

from cockpit import api_client
from cockpit.api_client import BackendError

st.set_page_config(page_title="Alpaca CAPI Cockpit", page_icon="📈", layout="wide")

SCREENS = [
    "Session Control",
    "Watchlist Input",
    "Candidate Monitor",
    "Position Monitor",
    "Daily Review",
]


def _parse_symbols(raw: str) -> list[str]:
    """Split a pasted blob into symbols (commas / whitespace / newlines).

    Light view-side tidy only; the backend is the authority on normalization.
    """

    tokens = re.split(r"[\s,;]+", raw.strip())
    seen: list[str] = []
    for tok in tokens:
        sym = tok.strip().upper()
        if sym and sym not in seen:
            seen.append(sym)
    return seen


def _backend_banner() -> bool:
    """Show backend connection status in the sidebar. Returns True if reachable."""

    try:
        health = api_client.get_health()
    except BackendError as exc:
        st.sidebar.error(f"Backend offline\n\n{exc}")
        return False
    st.sidebar.success(f"Backend OK · v{health.get('version', '?')}")
    st.sidebar.caption(f"API: {api_client.base_url()}")
    return True


# --------------------------------------------------------------------------- #
# Screens
# --------------------------------------------------------------------------- #
def screen_session_control() -> None:
    st.header("Session Control")
    st.caption(
        "Mode is **paper** only (beta). The kill switch and pause-buys are "
        "**enforced** on the order path — new order intent is refused and order "
        "submission is held while engaged. (CAPI risk sizing is Phase 6.)"
    )
    try:
        session = api_client.get_session()
    except BackendError as exc:
        st.error(str(exc))
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Mode", str(session.get("mode", "—")).upper())
    c2.metric("Session type", session.get("session_type") or "—")
    c3.metric("Kill switch", "ENGAGED" if session.get("kill_switch") else "off")
    c4.metric("Buys", "PAUSED" if session.get("buys_paused") else "active")

    st.divider()
    kill_on = bool(session.get("kill_switch"))
    paused = bool(session.get("buys_paused"))

    a, b, c = st.columns(3)
    with a:
        if kill_on:
            if st.button("Release kill switch", width='stretch'):
                _do(lambda: api_client.set_kill_switch(False), "Kill switch released")
        else:
            if st.button("🛑 Engage kill switch", type="primary",
                         width='stretch'):
                _do(lambda: api_client.set_kill_switch(True), "Kill switch engaged")
    with b:
        if st.button("Pause buys", disabled=paused, width='stretch'):
            _do(api_client.pause_buys, "Buys paused")
    with c:
        if st.button("Resume buys", disabled=not paused, width='stretch'):
            _do(api_client.resume_buys, "Buys resumed")

    with st.expander("Raw session record"):
        st.json(session)


def screen_watchlist() -> None:
    st.header("Watchlist Input")
    st.caption("Add or remove symbols and arm/disarm them. Backed by real "
               "`/api/watchlist` endpoints.")

    with st.form("add_symbols", clear_on_submit=True):
        raw = st.text_area(
            "Paste symbols (comma, space, or newline separated)",
            placeholder="AAPL, MSFT\nNVDA TSLA",
        )
        arm_on_add = st.checkbox("Arm symbols on add", value=False)
        submitted = st.form_submit_button("Add to watchlist")
    if submitted:
        symbols = _parse_symbols(raw)
        if not symbols:
            st.warning("No valid symbols found.")
        else:
            added, failed = [], []
            for sym in symbols:
                try:
                    api_client.upsert_watchlist(sym, armed=arm_on_add)
                    added.append(sym)
                except BackendError as exc:
                    failed.append(f"{sym} ({exc})")
            if added:
                st.success(f"Saved: {', '.join(added)}")
            if failed:
                st.error("Failed: " + "; ".join(failed))

    st.divider()
    try:
        watchlist = api_client.list_watchlist()
    except BackendError as exc:
        st.error(str(exc))
        return

    if not watchlist:
        st.info("Watchlist is empty. Paste symbols above to get started.")
        return

    # Phase 5: last price / % move next to each armed symbol, display only.
    # pct_move is computed by the BACKEND (GET /api/marketdata/snapshots, via
    # app/features.py — the same function the Strategy Engine decides on) and
    # only formatted here; the cockpit never re-derives the number, so what's
    # shown always matches what the strategy actually saw (Streamlit stays a
    # pure display client, per 01_ARCHITECTURE.md).
    try:
        snapshots = {s["symbol"]: s for s in api_client.list_marketdata_snapshots()}
    except BackendError:
        snapshots = {}

    st.subheader(f"Current watchlist ({len(watchlist)})")
    hdr = st.columns([2, 2, 2, 2, 2, 2])
    hdr[0].markdown("**Symbol**")
    hdr[1].markdown("**State**")
    hdr[2].markdown("**Last**")
    hdr[3].markdown("**% Move**")
    hdr[4].markdown("**Arm / Disarm**")
    hdr[5].markdown("**Remove**")
    for entry in watchlist:
        sym = entry["symbol"]
        armed = bool(entry["armed"])
        snap = snapshots.get(sym)
        last_display = f"${snap['last_price']:.2f}" if snap and snap.get("last_price") is not None else "—"
        move_display = "—"
        if snap and snap.get("pct_move") is not None:
            move_display = f"{snap['pct_move']:+.1f}%"
        if snap and snap.get("stale"):
            last_display += " ⚠️"

        row = st.columns([2, 2, 2, 2, 2, 2])
        row[0].write(sym)
        row[1].write("🟢 armed" if armed else "⚪ disarmed")
        row[2].write(last_display)
        row[3].write(move_display)
        if armed:
            if row[4].button("Disarm", key=f"disarm_{sym}", width='stretch'):
                _do(lambda s=sym: api_client.upsert_watchlist(s, armed=False),
                    f"{sym} disarmed")
        else:
            if row[4].button("Arm", key=f"arm_{sym}", width='stretch'):
                _do(lambda s=sym: api_client.upsert_watchlist(s, armed=True),
                    f"{sym} armed")
        if row[5].button("Remove", key=f"rm_{sym}", width='stretch'):
            _do(lambda s=sym: api_client.remove_watchlist(s), f"{sym} removed")


def screen_candidates() -> None:
    st.header("Candidate Monitor")
    st.caption(
        "Proposals awaiting human review — the Approval Gate's human-in-the-loop "
        "mode. Approving a candidate creates a **paper** order record that the "
        "backend monitoring loop then submits to Alpaca **paper** (no live trading, "
        "ever). Rejecting dismisses it."
    )

    with st.expander("➕ Inject mock candidate (dev)"):
        st.caption(
            "DEV/MOCK scaffolding for hand-testing an exact candidate. The "
            "real Strategy Engine generates candidates independently — this "
            "is for testing states it wouldn't naturally produce."
        )
        with st.form("inject_candidate", clear_on_submit=True):
            symbol_input = st.text_input("Symbol", placeholder="AAPL")
            qty_input = st.number_input("Suggested quantity", min_value=1, value=10, step=1)
            inject_submitted = st.form_submit_button("Inject candidate")
        if inject_submitted:
            sym = symbol_input.strip().upper()
            if not sym:
                st.warning("Symbol is required.")
            else:
                try:
                    api_client.create_mock_candidate(sym, suggested_quantity=int(qty_input))
                    st.toast(f"Mock candidate injected for {sym}")
                    st.rerun()
                except BackendError as exc:
                    st.error(str(exc))

    st.divider()
    try:
        candidates = api_client.list_candidates()
    except BackendError as exc:
        st.error(str(exc))
        return

    if not candidates:
        st.info(
            "No candidates yet. Inject one above (dev), or arm a watchlist "
            "symbol and wait for the Strategy Engine to propose one during "
            "premarket/after-hours."
        )
        return

    st.subheader(f"Candidates ({len(candidates)})")

    # Column widths: symbol, status, strategy, reason, risk, qty, price, actions
    hdr = st.columns([2, 2, 2, 4, 3, 1, 2, 3])
    hdr[0].markdown("**Symbol**")
    hdr[1].markdown("**Status**")
    hdr[2].markdown("**Strategy**")
    hdr[3].markdown("**Reason**")
    hdr[4].markdown("**Risk decision**")
    hdr[5].markdown("**Qty**")
    hdr[6].markdown("**Limit price**")
    hdr[7].markdown("**Action**")

    for candidate in candidates:
        cid = candidate["id"]
        symbol = candidate.get("symbol", "—")
        status = candidate.get("status", "—")
        strategy = candidate.get("strategy") or "—"
        reason = candidate.get("reason") or "—"
        risk_decision = candidate.get("risk_decision") or "—"
        qty = candidate.get("suggested_quantity", "—")
        price = candidate.get("suggested_limit_price")
        price_display = f"${price:.2f}" if price is not None else "—"

        row = st.columns([2, 2, 2, 4, 3, 1, 2, 3])
        row[0].write(symbol)
        row[1].write(status)
        row[2].write(strategy)
        row[3].write(reason)
        row[4].write(risk_decision)
        row[5].write(str(qty))
        row[6].write(price_display)

        if status == "pending":
            with row[7]:
                btn_cols = st.columns(2)
                if btn_cols[0].button("Approve", key=f"approve_{cid}", type="primary"):
                    _do(
                        lambda cid=cid: api_client.approve_candidate(cid),
                        f"{symbol} approved → ordered",
                    )
                if btn_cols[1].button("Reject", key=f"reject_{cid}"):
                    _do(
                        lambda cid=cid: api_client.reject_candidate(cid),
                        f"{symbol} rejected",
                    )
        else:
            row[7].write(status)


def _format_age(created_at: str) -> str:
    """Return a human-readable age string from an ISO timestamp. Display-only."""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta_seconds = int((now - dt).total_seconds())
        if delta_seconds < 0:
            return "just now"
        if delta_seconds < 60:
            return f"{delta_seconds}s"
        minutes = delta_seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        return f"{hours}h {minutes % 60}m"
    except Exception:
        return "—"


# Order statuses that are still live/actionable and must be shown (F-006): a
# never-submitted `created` order (held by a control, or just awaiting the
# submit tick) and a claimed `submitting` order are durable non-terminal state
# the operator was previously blind to — not just submitted/partially_filled.
_DISPLAY_ORDER_STATUSES = (
    "created",
    "submitting",
    "submitted",
    "partially_filled",
    "cancel_pending",
)


def _order_operational_label(status: str, block_reason: str | None) -> str:
    """A human-readable operational state for the order list (F-006).

    Wave 0 derives this in the cockpit from the order status + the latest
    ``order_submission_blocked`` reason; Wave 2 (D-020) moves the classification
    server-side so the UI stops interpreting lifecycle at all.
    """

    if status == "created":
        if block_reason is None:
            return "created · awaiting submission"
        if block_reason in ("kill_switch", "current_kill_switch"):
            return "created · held by kill switch"
        if block_reason in ("buys_paused", "current_buys_paused"):
            return "created · held (buys paused)"
        if "session_closed" in block_reason:
            return "created · held (session closed)"
        return f"created · held ({block_reason})"
    if status == "submitting":
        return "submitting · claimed, sending to broker"
    return status


def screen_positions() -> None:
    st.header("Position Monitor")
    st.caption(
        "Positions are derived from filled orders — quantity changes only on "
        "fills. The Phase 5 price feed exists (see the Watchlist screen), but "
        "P/L computation from it is not yet wired into this screen."
    )

    # ------------------------------------------------------------------ #
    # A) POSITIONS
    # ------------------------------------------------------------------ #
    try:
        positions = api_client.list_positions()
    except BackendError as exc:
        st.error(str(exc))
        return

    open_positions = [p for p in positions if p.get("quantity")]

    st.subheader("Positions")
    if not open_positions:
        st.info(
            "No open positions. Positions appear here once fills are recorded "
            "(Phase 4)."
        )
    else:
        hdr = st.columns([2, 2, 2, 3, 3])
        hdr[0].markdown("**Symbol**")
        hdr[1].markdown("**Quantity**")
        hdr[2].markdown("**Avg Price**")
        hdr[3].markdown("**P/L**")
        hdr[4].markdown("**Action**")

        for pos in open_positions:
            sym = pos.get("symbol", "—")
            qty = pos.get("quantity", 0)
            avg = pos.get("average_price")
            avg_display = f"${avg:.2f}" if avg is not None else "—"

            row = st.columns([2, 2, 2, 3, 3])
            row[0].write(sym)
            row[1].write(str(qty))
            row[2].write(avg_display)
            # The Phase 5 price feed exists (see the Watchlist screen), but
            # computing unrealized P/L from it here is a deliberate small scope
            # decision, not yet built — not an oversight.
            row[3].caption("P/L: not yet wired to the live price feed")
            with row[4]:
                st.button(
                    "Flatten",
                    key=f"flatten_{sym}",
                    disabled=True,
                    help=(
                        "Placeholder — position flatten is wired in Phase 7 "
                        "(Sell-Side Protection owns exits); not functional yet."
                    ),
                )

    st.divider()

    # ------------------------------------------------------------------ #
    # B) OPEN ORDERS
    # ------------------------------------------------------------------ #
    st.subheader("Open Orders")

    try:
        all_orders = api_client.list_orders()
    except BackendError as exc:
        st.error(str(exc))
        return

    # Show every durable non-terminal order (F-006): not only submitted/
    # partially_filled/cancel_pending, but also `created` (held by a control or
    # awaiting the submit tick) and `submitting` (claimed) — orders the operator
    # was previously blind to. cancel_pending stays visible until terminal.
    open_orders = [o for o in all_orders if o.get("status") in _DISPLAY_ORDER_STATUSES]

    # Broker-submit recovery records (D-017 / F-002): a broker order accepted
    # upstream the local state can't otherwise show. Surfaced prominently.
    try:
        recoveries = api_client.list_order_recoveries()
    except BackendError as exc:
        st.error(str(exc))
        return

    if recoveries:
        st.error(
            f"⚠️ {len(recoveries)} broker order(s) need recovery — accepted by the "
            "broker but not tracked locally. The monitoring loop is cancelling "
            "them; verify at the broker if this persists."
        )
        for rec in recoveries:
            st.caption(
                f"• {rec.get('symbol', '—')} broker id "
                f"{rec.get('broker_order_id', '—')} — {rec.get('cleanup_status', '—')} "
                f"(attempts: {rec.get('retry_count', 0)})"
            )

    # Per-order hold reason, from the latest order_submission_blocked event.
    try:
        block_events = api_client.list_events(event_type="order_submission_blocked")
    except BackendError as exc:
        st.error(str(exc))
        return
    block_reason_by_order: dict[str, str] = {}
    for e in block_events:
        oid = e.get("order_id")
        reason = (e.get("payload") or {}).get("reason")
        if oid and reason:
            block_reason_by_order[oid] = reason  # later events overwrite earlier

    # Build stale-order set from events, filtered server-side to just
    # order_stale — NOT a raw recent-N window: the audit log accumulates
    # across days (docs/02) and, post-Phase-5, the strategy loop writes far
    # more events per tick (market_data_stale/recovered + candidate events
    # across every armed symbol) than order events, so a fixed-size recent
    # window could scroll a still-open order's one-time order_stale event
    # out of view long before the order actually resolves.
    try:
        events = api_client.list_events(event_type="order_stale")
    except BackendError as exc:
        st.error(str(exc))
        return

    stale_order_ids: set[str] = {
        e["order_id"]
        for e in events
        if e.get("event_type") == "order_stale" and e.get("order_id")
    }

    if not open_orders:
        st.caption("No open orders.")
    else:
        hdr = st.columns([2, 1, 2, 2, 1, 2, 3])
        hdr[0].markdown("**Symbol**")
        hdr[1].markdown("**Qty**")
        hdr[2].markdown("**Limit Price**")
        hdr[3].markdown("**Status**")
        hdr[4].markdown("**Filled**")
        hdr[5].markdown("**Age**")
        hdr[6].markdown("**Action**")

        for order in open_orders:
            order_id = order.get("id", "")
            symbol = order.get("symbol", "—")
            qty = order.get("quantity", "—")
            limit_price = order.get("limit_price")
            price_display = f"${limit_price:.2f}" if limit_price is not None else "—"
            status_val = order.get("status", "—")
            filled_qty = order.get("filled_quantity", 0)
            created_at = order.get("created_at", "")
            age_display = _format_age(created_at) if created_at else "—"
            label = _order_operational_label(
                status_val, block_reason_by_order.get(order_id)
            )

            is_stale = order_id in stale_order_ids

            if is_stale:
                st.warning(f"⚠️ STALE order detected for {symbol} (id: {order_id})")

            row = st.columns([2, 1, 2, 2, 1, 2, 3])
            row[0].write(symbol)
            row[1].write(str(qty))
            row[2].write(price_display)
            row[3].write(label)
            row[4].write(str(filled_qty))
            row[5].write(age_display)

            confirm_key = f"pending_cancel_{order_id}"
            with row[6]:
                if status_val == "cancel_pending":
                    # Cancel already requested; the backend loop is winding it
                    # down. No button — re-cancelling is a no-op.
                    st.caption("⏳ cancel requested")
                elif st.session_state.get(confirm_key):
                    st.caption("⚠️ Confirm cancel?")
                    if st.button("Yes, cancel", key=f"confirm_cancel_{order_id}"):
                        st.session_state[confirm_key] = False
                        _do(
                            lambda oid=order_id: api_client.cancel_order(oid),
                            f"{symbol} order cancel requested",
                        )
                else:
                    if st.button("Cancel", key=f"cancel_{order_id}"):
                        st.session_state[confirm_key] = True
                        st.rerun()


def screen_review() -> None:
    st.header("Daily Review")
    st.caption("Review the current session or a past one by date. History "
               "persists across days.")
    chosen = st.date_input("Session date", value=date.today())
    try:
        review = api_client.get_review(date=chosen.isoformat())
    except BackendError as exc:
        st.error(str(exc))
        return

    session = review.get("session")
    if session is None:
        st.info(f"No session recorded for {review.get('date')}.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidates", len(review.get("candidates", [])))
    c2.metric("Orders", len(review.get("orders", [])))
    c3.metric("Fills", len(review.get("fills", [])))
    c4.metric("Events", len(review.get("events", [])))

    st.subheader("Session")
    st.json(session)

    sections = [
        ("Candidates", review.get("candidates", [])),
        ("Orders", review.get("orders", [])),
        ("Fills", review.get("fills", [])),
        ("Positions", review.get("positions", [])),
        ("Events", review.get("events", [])),
    ]
    for title, rows in sections:
        st.subheader(title)
        if rows:
            st.dataframe(rows, width='stretch', hide_index=True)
        else:
            st.caption("— none —")


# --------------------------------------------------------------------------- #
# Action helper + router
# --------------------------------------------------------------------------- #
def _do(action, success_message: str) -> None:
    """Run a backend mutation, toast the result, and refresh the screen."""

    try:
        action()
    except BackendError as exc:
        st.error(str(exc))
        return
    st.toast(success_message)
    st.rerun()


def main() -> None:
    st.sidebar.title("📈 Alpaca CAPI Cockpit")
    reachable = _backend_banner()
    screen = st.sidebar.radio("Screen", SCREENS, label_visibility="collapsed")
    st.sidebar.caption("Thin client · paper-only · no Alpaca calls from here")

    if not reachable:
        st.warning(
            "The backend is not reachable. Start it first:\n\n"
            "`uvicorn app.main:app --reload`"
        )
        return

    {
        "Session Control": screen_session_control,
        "Watchlist Input": screen_watchlist,
        "Candidate Monitor": screen_candidates,
        "Position Monitor": screen_positions,
        "Daily Review": screen_review,
    }[screen]()


main()
