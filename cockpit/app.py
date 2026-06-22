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
from datetime import date

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
        "Mode is **paper** only (beta). Controls below persist a flag on the "
        "backend session; enforcement on order intent comes later."
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

    st.subheader(f"Current watchlist ({len(watchlist)})")
    hdr = st.columns([3, 2, 2, 2])
    hdr[0].markdown("**Symbol**")
    hdr[1].markdown("**State**")
    hdr[2].markdown("**Arm / Disarm**")
    hdr[3].markdown("**Remove**")
    for entry in watchlist:
        sym = entry["symbol"]
        armed = bool(entry["armed"])
        row = st.columns([3, 2, 2, 2])
        row[0].write(sym)
        row[1].write("🟢 armed" if armed else "⚪ disarmed")
        if armed:
            if row[2].button("Disarm", key=f"disarm_{sym}", width='stretch'):
                _do(lambda s=sym: api_client.upsert_watchlist(s, armed=False),
                    f"{sym} disarmed")
        else:
            if row[2].button("Arm", key=f"arm_{sym}", width='stretch'):
                _do(lambda s=sym: api_client.upsert_watchlist(s, armed=True),
                    f"{sym} armed")
        if row[3].button("Remove", key=f"rm_{sym}", width='stretch'):
            _do(lambda s=sym: api_client.remove_watchlist(s), f"{sym} removed")


def screen_candidates() -> None:
    st.header("Candidate Monitor")
    st.caption("Strategy-generated candidates awaiting review. Candidate "
               "generation arrives in Phase 3 — empty until then.")
    try:
        candidates = api_client.list_candidates()
    except BackendError as exc:
        st.error(str(exc))
        return
    if not candidates:
        st.info("No candidates yet. The strategy engine (Phase 5) will populate "
                "this once candidate generation (Phase 3) is built.")
        return
    st.dataframe(candidates, width='stretch', hide_index=True)


def screen_positions() -> None:
    st.header("Position Monitor")
    st.caption("Positions are derived from filled orders. Quantity changes only "
               "on fills — there are none yet.")
    try:
        positions = api_client.list_positions()
    except BackendError as exc:
        st.error(str(exc))
        return
    open_positions = [p for p in positions if p.get("quantity")]
    if not open_positions:
        st.info("No open positions. Positions appear here once fills are recorded "
                "(Phase 4).")
        return
    st.dataframe(open_positions, width='stretch', hide_index=True)


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
