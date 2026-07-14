"""Thin HTTP client for the backend API.

This is the cockpit's *only* contact with truth. It performs no logic beyond
issuing requests and surfacing errors — no trading decisions, no Alpaca calls,
no position math. Keeping all of that here (and nowhere else in the cockpit)
makes the thin-client boundary easy to audit.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
TIMEOUT_SECONDS = 5.0


def base_url() -> str:
    return os.environ.get("ALPACA_API_BASE", DEFAULT_BASE_URL).rstrip("/")


# ADR-009 A-1 / WO-0102 (Codex PR #5 round-5): the operator credential header, read
# from the environment. When the Signal Seat flag is ON the backend enforces the
# operator key on EVERY sensitive route — reads included — so the browser client
# MUST send it or the operator's kill-switch / flatten / candidate / watchlist
# controls would answer 401 the moment enforcement flips on (invariant 11 — no
# lockout window). When unset (flag off, localhost no-auth), no header is sent and
# behavior is unchanged. This is the credential plumbing that lands in the SAME
# change as the auth flip; the signal UI itself is WO-0103.
OPERATOR_KEY_HEADER = "X-Operator-Key"


def _operator_headers() -> dict[str, str]:
    key = os.environ.get("OPERATOR_API_KEY")
    return {OPERATOR_KEY_HEADER: key} if key and key.strip() else {}


class BackendError(RuntimeError):
    """A backend call failed (unreachable, timeout, or non-2xx response)."""


def _request(method: str, path: str, **kwargs: Any) -> Any:
    url = f"{base_url()}{path}"
    # Merge the operator credential into any caller-supplied headers (caller wins
    # on an explicit clash, though nothing sets X-Operator-Key itself).
    headers = {**_operator_headers(), **(kwargs.pop("headers", None) or {})}
    if headers:
        kwargs["headers"] = headers
    try:
        resp = requests.request(method, url, timeout=TIMEOUT_SECONDS, **kwargs)
    except requests.exceptions.RequestException as exc:
        raise BackendError(
            f"Could not reach the backend at {base_url()}. Is it running? "
            f"({exc.__class__.__name__})"
        ) from exc
    if not resp.ok:
        detail = ""
        try:
            detail = resp.json().get("detail", "")
        except ValueError:
            detail = resp.text
        raise BackendError(f"{method} {path} -> {resp.status_code}: {detail}")
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


# --- System --------------------------------------------------------------- #
def get_health() -> dict:
    return _request("GET", "/api/health")


def get_session() -> dict:
    return _request("GET", "/api/session")


# --- Watchlist ------------------------------------------------------------ #
def list_watchlist() -> list[dict]:
    return _request("GET", "/api/watchlist")


def upsert_watchlist(symbol: str, armed: bool = False) -> dict:
    return _request("POST", "/api/watchlist", json={"symbol": symbol, "armed": armed})


def remove_watchlist(symbol: str) -> None:
    _request("DELETE", f"/api/watchlist/{symbol}")


# --- Market data (Phase 5, read-only) -------------------------------------- #
def list_marketdata_snapshots() -> list[dict]:
    return _request("GET", "/api/marketdata/snapshots")


# --- Candidates ----------------------------------------------------------- #
def list_candidates() -> list[dict]:
    return _request("GET", "/api/candidates")


def get_candidate(candidate_id: str) -> dict:
    return _request("GET", f"/api/candidates/{candidate_id}")


def approve_candidate(candidate_id: str) -> dict:
    return _request("POST", f"/api/candidates/{candidate_id}/approve")


def reject_candidate(candidate_id: str) -> dict:
    return _request("POST", f"/api/candidates/{candidate_id}/reject")


def create_mock_candidate(symbol: str, suggested_quantity: int = 10,
                          suggested_limit_price: float = 1.0) -> dict:
    """DEV/MOCK scaffolding: hand-inject an exact candidate for manual testing.
    The real Strategy Engine (Phase 5) generates candidates independently;
    this remains useful for testing states it wouldn't naturally produce."""
    return _request("POST", "/api/dev/candidates", json={
        "symbol": symbol,
        "suggested_quantity": suggested_quantity,
        "suggested_limit_price": suggested_limit_price,
    })


# --- Read-only trading views ---------------------------------------------- #
def list_positions() -> list[dict]:
    return _request("GET", "/api/positions")


def get_protection() -> dict:
    """Sell-Side Protection status (Phase 7): ``{"config": {...}, "positions":
    [...]}`` — the effective config plus each open position classified
    server-side (floor, observed price, breaching, paused_by_kill_switch,
    stalled, active_sell_intent). The cockpit renders it verbatim."""

    return _request("GET", "/api/protection")


def flatten_position(symbol: str) -> dict:
    """Manually flatten a position (Phase 7 / D-P2). Returns
    ``{"intent": {...}, "order": {...}, "deferred": bool,
    "deferred_order_status": str|None}``. ``deferred=True`` means NO manual order
    was submitted — the flatten was safely deferred to an already in-flight
    protection exit (REV-0002 F-001). Always works — bypasses the kill switch /
    pause / closed session at the backend."""

    return _request("POST", f"/api/positions/{symbol}/flatten")


def list_orders() -> list[dict]:
    return _request("GET", "/api/orders")


def get_order(order_id: str) -> dict:
    return _request("GET", f"/api/orders/{order_id}")


def cancel_order(order_id: str) -> dict:
    return _request("POST", f"/api/orders/{order_id}/cancel")


def list_order_recoveries(open_only: bool = True) -> list[dict]:
    """Broker-submit recovery records (D-017 / F-002). By default only the
    *open* ones — unresolved (loop still working) + needs-review (a real
    untracked position a human must reconcile)."""

    params = {"open_only": "true" if open_only else "false"}
    return _request("GET", "/api/order-recoveries", params=params)


def list_operator_orders() -> dict:
    """The operator's single source of order-lifecycle truth (D-020).

    Returns ``{"orders": [...], "recoveries": [...]}`` where every durable
    non-terminal order is already classified server-side (``operational_status``,
    hold ``reason``, ``cancelable``, ``stale``) and every open recovery record
    is included. The cockpit renders this verbatim — it no longer interprets
    order lifecycle or owns the "which statuses are open" filter."""

    return _request("GET", "/api/operator/orders")


def list_events(limit: Optional[int] = None, event_type: Optional[str] = None) -> list[dict]:
    params: dict = {}
    if limit:
        params["limit"] = limit
    if event_type:
        params["event_type"] = event_type
    return _request("GET", "/api/events", params=params or None)


def get_review(date: Optional[str] = None) -> dict:
    params = {"date": date} if date else None
    return _request("GET", "/api/review", params=params)


# --- Controls ------------------------------------------------------------- #
def set_kill_switch(engaged: bool) -> dict:
    return _request("POST", "/api/controls/kill-switch", json={"engaged": engaged})


def pause_buys() -> dict:
    return _request("POST", "/api/controls/pause-buys")


def resume_buys() -> dict:
    return _request("POST", "/api/controls/resume-buys")
