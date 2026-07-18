"""REV-0029 review-hardening — Tier-1 mechanical gates (CI-blocking).

`pkl/process/review-hardening.md` T1.1 + T1.3, ratified CI-blocking by Ameen on
2026-07-18. These are DETERMINISTIC, no-model-judgment gates: they exist because
REV-0029 found a safety-enum SUBSET gating a decision (P0-1 — `CANCEL_PENDING`
outside the flatten-block set) and a projection field with ZERO rail consumers
(P0-3) that six in-process lenses missed — both catchable without judgment. Adding
an unclassified enum member, shrinking a totality set, or adding a safety field no
rail consumes must break the build HERE, at review time, not at the venue.

Tier-1's other two rules (T1.2 mutation-check, T1.4 N-run) remain review-checklist
items until automated (follow-up process WO) per the same ratification.
"""

from __future__ import annotations

from pathlib import Path

from app.models import OrderStatus
from app.policy import MAY_EXECUTE_ORDER_STATUSES, NON_TERMINAL_ORDER_STATUSES
from app.store.core import FLATTEN_BLOCKING_BUY_STATUSES, OPEN_BUY_STATUSES

_APP = Path(__file__).resolve().parent.parent / "app"


# --------------------------------------------------------------------------- #
# T1.1 — enum-total classification. Every safety-gating set over OrderStatus is
# TOTAL over the enum: a new member (or a member dropped from a totality set)
# breaks the build until explicitly classified. This is the gate that would have
# caught P0-1.
# --------------------------------------------------------------------------- #


def test_t1_1_order_status_partitions_into_terminal_and_non_terminal():
    """`NON_TERMINAL_ORDER_STATUSES` (derived from the transition table) and its
    complement partition the FULL enum: every member is in exactly one bucket, so
    no status is silently unclassified."""
    terminal = {s for s in OrderStatus if s not in NON_TERMINAL_ORDER_STATUSES}
    assert terminal | NON_TERMINAL_ORDER_STATUSES == set(OrderStatus)
    assert terminal & NON_TERMINAL_ORDER_STATUSES == set()
    # Terminal is exactly the settled trio; a change here is a deliberate
    # lifecycle change, not an accident.
    assert {s.value for s in terminal} == {"filled", "canceled", "rejected"}


def test_t1_1_flatten_blocks_every_non_terminal_buy_status():
    """P0-1's class. A flatten must block on EVERY status in which a BUY can still
    fill — the WHOLE non-terminal set, never a subset. `FLATTEN_BLOCKING_BUY_
    STATUSES` must therefore equal `NON_TERMINAL_ORDER_STATUSES`; a new non-
    terminal status not added to the flatten-block set breaks this pin, exactly
    the gap REV-0029 found (`CANCEL_PENDING` was outside `OPEN_BUY_STATUSES`)."""
    assert FLATTEN_BLOCKING_BUY_STATUSES == NON_TERMINAL_ORDER_STATUSES
    # The cancellable subset the caller may act on is a STRICT subset: the
    # venue-uncertain statuses (SUBMITTING / CANCEL_PENDING / TIMEOUT_QUARANTINE)
    # block the flatten but must never be blind-cancelled.
    assert OPEN_BUY_STATUSES < FLATTEN_BLOCKING_BUY_STATUSES
    assert FLATTEN_BLOCKING_BUY_STATUSES - OPEN_BUY_STATUSES == {
        OrderStatus.SUBMITTING,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.TIMEOUT_QUARANTINE,
    }


def test_t1_1_may_execute_is_total_over_order_status():
    """P0-2's set. 'A BUY may execute at the venue' = every non-terminal status
    EXCEPT `CREATED` (a pre-claim BUY is blocked at its own claim). Totality:
    every OrderStatus is may-execute, or `CREATED`, or terminal — no member is
    left unclassified, and a new non-terminal venue status is auto-included
    (fail-safe by derivation)."""
    assert MAY_EXECUTE_ORDER_STATUSES == NON_TERMINAL_ORDER_STATUSES - {
        OrderStatus.CREATED
    }
    terminal = {s for s in OrderStatus if s not in NON_TERMINAL_ORDER_STATUSES}
    classified = MAY_EXECUTE_ORDER_STATUSES | {OrderStatus.CREATED} | terminal
    assert classified == set(OrderStatus)


# --------------------------------------------------------------------------- #
# T1.3 — producer/consumer for new safety fields. A projection/store safety field
# must have real RAIL consumers, verified by a FRESH grep (never by sampling
# positives). Zero-consumer-while-docs-claim-"every-choke" is the P0-3 defect.
# --------------------------------------------------------------------------- #


def _grep_app_files(needle: str) -> set[str]:
    """Basenames of app/*.py files that mention ``needle`` (fresh grep, source
    only — never the built tree)."""
    files: set[str] = set()
    for path in _APP.rglob("*.py"):
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if needle in text:
            files.add(path.name)
    return files


def test_t1_3_needs_review_child_order_ids_is_consumed_by_both_store_rails():
    """P0-3's class. The `needs_review_child_order_ids` projection field must be
    produced (store/core.py) AND consumed by the submission rails of BOTH stores;
    a producer with no rail consumer is exactly the P0-3 defect the widened-
    predicate doc claim ('every sell-side choke') papered over."""
    files = _grep_app_files("needs_review_child_order_ids")
    assert "core.py" in files, f"producer missing (found in: {sorted(files)})"
    assert "memory.py" in files, f"memory rail consumer missing: {sorted(files)}"
    assert "sqlite.py" in files, f"sqlite rail consumer missing: {sorted(files)}"


def test_t1_3_may_execute_order_statuses_is_consumed_where_defined():
    """The P0-2 safety set must be consumed, not orphaned: it is defined in
    `policy.py` and read by BOTH stores' cross-side claim rails."""
    files = _grep_app_files("MAY_EXECUTE_ORDER_STATUSES")
    assert "policy.py" in files, f"producer missing: {sorted(files)}"
    assert "memory.py" in files, f"memory consumer missing: {sorted(files)}"
    assert "sqlite.py" in files, f"sqlite consumer missing: {sorted(files)}"
