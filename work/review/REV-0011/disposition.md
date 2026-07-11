---
type: Review Disposition
rev_id: REV-0011
verdict_received: ACCEPT
disposition_status: RESOLVED
date: 2026-07-10
---

# Disposition — REV-0011 (BROKER)

Reviewer: GPT-5 Codex, verdict **ACCEPT** (UC-001-refuted class confirmed). Re-derived independently on
Python 3.12.3.

## Findings

- [x] **UC-001 refuted class (no blind resubmit)** → **CONFIRMED.**
  - Deterministic `client_order_id = order.id`: real adapter `alpaca_paper.py:245`/`:255`; mock
    `broker-<order.id>` (`mock.py:31-32`, `:88`); interface contract `adapter.py:172-176`.
  - Idempotent resubmit: on a duplicate-`client_order_id` rejection the real adapter looks up the
    existing order and returns the existing venue id (`alpaca_paper.py:270-285`); the mock collapses N
    submits of one `order.id` to ONE venue order. Repro:
    ```
    two submits of same order.id -> identical broker id ; distinct venue orders = 1
    ambiguous submit (HTTP 504) -> read-only reconcile by client_order_id ; submit calls stay 1 (ZERO resubmit)
    ```
  - Timeout/ambiguous → `TIMEOUT_QUARANTINE` + strictly read-only reconcile: classification in
    `alpaca_paper.py:305-332`; monitoring quarantines and explicitly does not resubmit
    (`monitoring.py:700-727`, SELL mirror `:894-906`); `_resolve_timeout_quarantine` resolves via
    `get_order_by_client_order_id` only (`monitoring.py:985`), never mutating a venue order, and an
    inconclusive query is never read as "absent" (`:986-999`).

## Disputed Items
- None.

## Verification
- Code + mock-adapter probe (pasted above). The *real* adapter's idempotency rests on Alpaca honoring
  `client_order_id` uniqueness — the 409/422 duplicate-rejection branch is present and correct but was
  not exercised against live Alpaca (a human-gated / out-of-scope surface).

## Follow-up
- **BROKER gate CLEARS.**
- **Beta pre-flight (not a code change):** confirm with the live Alpaca paper venue that a duplicate
  `client_order_id` is rejected for **all** order states incl. post-fill (the one external assumption
  UC-001's safety rests on). Carried from the Wave-1 roadmap.
- Ledger updated (`work/ledger.jsonl`: REV-0011 outcome).
