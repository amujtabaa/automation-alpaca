---
type: Review Request
rev_id: REV-0002
title: broker-adapter SDK method-name fix + flatten INV-034/INV-036 reconciliation
status: AWAITING_REVIEW
targets: [FINDING-alpaca-adapter-wrong-sdk-method, FINDING-flatten-inv034-live-protection]
human_gated_surfaces: [order-submission, manual-flatten]
commit_range: b619998 3d20e3d
reviewer_model: null
verdict: null
created: 2026-07-09
---

# Review Request REV-0002 — broker-adapter fix + flatten reconciliation

## Your role
You are the **independent review seat** — a different model from the author, on
purpose. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`: re-derive from the code, don't
rubber-stamp, **findings only — do not push fixes**. You have the full repo.

Both changes touch **human-gated surfaces** (order submission/reconciliation;
manual flatten). Human approval for both was recorded in the session that
authored them — confirm the diffs stay within what was approved.

## What you're reviewing
Two independent fixes, batched:

1. **Broker adapter (`b619998`)** — `app/broker/alpaca_paper.py` called
   `self._client.get_order_by_client_order_id`, which does NOT exist on alpaca-py
   0.43.5 (`TradingClient` has `get_order_by_client_id`). Against the real SDK it
   AttributeError'd on the D-017 idempotent duplicate-recovery path and the ADR-002
   timeout-quarantine reconciliation query. Fixed RED→GREEN (the two tests mocked the
   wrong name — the X-002 anti-pattern). Also cleared the SDK-union typing to
   un-grandfather both alpaca adapters (runtime-noop `cast`s).
2. **Flatten (`3d20e3d`)** — reconciled INV-034 (flatten always returns
   MANUAL_FLATTEN) with INV-036 (a genuinely-live protective order is left alone).
   Added a `manual_flatten_deferred` provenance event on the deferral;
   **deliberately did NOT tighten the "live" predicate** (see risk 3).

- Commits: `b619998` (alpaca), `3d20e3d` (flatten).
  ```
  git show b619998 3d20e3d
  ```
- Author's writeups: `work/review/FINDING-alpaca-adapter-wrong-sdk-method.md`,
  `work/review/FINDING-flatten-inv034-live-protection.md` (read, then verify).

## Where to look (curated pointers)
Broker adapter:
- `app/broker/alpaca_paper.py:271` and `:421` — the corrected `get_order_by_client_id`
  calls (duplicate-recovery + timeout-quarantine query). Confirm against the real
  SDK: `python -c "from alpaca.trading.client import TradingClient; import inspect; print(inspect.signature(TradingClient.get_order_by_client_id))"`.
- The `cast(AlpacaOrder/AlpacaPosition, ...)` sites — verify the client is never in
  `raw_data` mode, so a dict/str return can't actually occur (else the cast masks it).
- `tests/test_alpaca_paper_submit.py` — the two duplicate-recovery tests now mock
  `get_order_by_client_id` + `assert_called_once_with`. Confirm they'd fail against
  the old name (they did: RED→GREEN).

Flatten:
- `app/store/core.py::plan_flatten_position` — the PROTECTION_FLOOR deferral branch
  (`active_order.status is not OrderStatus.CREATED`) + the `deferral_event`.
- `app/store/memory.py` / `app/store/sqlite.py` — where FLATTEN_EXISTING now writes
  the `manual_flatten_deferred` event (same lock/atomic block, no state change).
- `app/models.py` — `EventType.MANUAL_FLATTEN_DEFERRED`.
- `docs/INVARIANTS.md` — **INV-034** (amended, with the INV-036 carve-out) + **INV-036**.
- `docs/adr/ADR-002-timeout-quarantine.md` — the blind-cancel / never-blind-redrive rule.
- `tests/test_phase7_flatten_atomic.py::test_live_protection_floor_deferral_records_provenance`
  and `tests/test_lifecycle_state_machine.py` (the reconciled `flatten` rule).

## Specific risks to probe
1. **Real-API correctness (alpaca).** `get_order_by_client_id`'s behavior against the
   real paper API is exercised only by env-gated integration tests, NOT CI. Is the
   corrected recovery + timeout-quarantine reconciliation end-to-end correct
   (signature, return shape, None/404 handling)?
2. **Cast safety (alpaca).** Any path where the SDK could actually return
   `dict`/`str` (raw mode, an error envelope) such that a `cast` would hide a real
   bug?
3. **Flatten predicate (the key judgment call).** The author kept the predicate
   deferring for ALL non-CREATED statuses, arguing that routing
   TIMEOUT_QUARANTINE/SUBMITTING to the supersede branch would LOCAL-CANCEL a
   possibly-live order — the ADR-002 blind-cancel hazard. **Verify or refute this.**
   Is deferring genuinely the safe action for every non-CREATED status, or is there
   a status (e.g. CANCEL_PENDING) where deferral wrongly reports "already exiting"
   for an order that won't flatten?
4. **Reconciliation faithfulness.** Does the amended INV-034 + the stateful-test
   assertion correctly encode INV-036 (permit PROTECTION_FLOOR only when the order
   is past CREATED), AND can the test still catch a real silently-substituted intent?
   Confirm no test was weakened to make code pass.
5. **Provenance additivity.** Is `manual_flatten_deferred` purely additive (no
   change to flatten's decision, return value, or any order/fill/position state)?
6. **Scope.** Any changed line in either diff that doesn't trace to the stated fix?

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder**, fill the
findings table + verdict, and state per target whether its gate may clear. Do not
edit `request.md`. State anything you could not verify (esp. the real-API behavior).
