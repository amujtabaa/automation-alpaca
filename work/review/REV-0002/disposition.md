---
type: Review Disposition
rev_id: REV-0002
verdict_received: ACCEPT-WITH-CHANGES
date: 2026-07-09
---

# Disposition — REV-0002 (broker-adapter SDK fix + flatten reconciliation)

Reviewer: GPT-5 (Codex), verdict **ACCEPT-WITH-CHANGES**. The broker-adapter
method-name fix (`get_order_by_client_id`) and its non-raw/paper-only cast safety
were verified clean by the reviewer — no change required. The three P1 findings were
confirmed against the code and remediated under **WO-0014** + **WO-0015** (commit
`a7b012d`). Independently re-verified by the 6-agent adversarial pass (all PASS).

## Changes Applied
- [x] **F-003 (P1) — market-data truncation** (the bug the WO-0012 cleanup introduced):
  `int((existing.volume or 0) + trade.size)` truncated fractional `trade.size` before
  the min-volume gate → **Fixed** under **WO-0014** in `a7b012d`: `volume` is `float`
  end-to-end (`MarketSnapshot`, `MarketSnapshotView`, the fake, seed annotations); the
  `int()` is removed. RED→GREEN: fractional accumulation preserved (100 + 0.5 = 100.5)
  and a fractional volume round-trips through the API view without a Pydantic error.
- [x] **F-001 (P1) — deferral masqueraded as a submitted flatten**: a manual flatten
  safely deferred to a live protection order reported "flatten submitted" → **Fixed**
  under **WO-0015** in `a7b012d`: an explicit `FlattenResult.deferred` /
  `FlattenResponse.deferred` + `deferred_order_status`, keyed on the deferral event
  (so an idempotent own-flatten stays `deferred=False`), and the cockpit renders a
  distinct "no manual order submitted — already exiting; monitoring" message. Purely
  additive — the no-blind-cancel decision and all order/fill/position state are
  byte-identical (INV-9). Dual-store + facade + cockpit RED→GREEN, parametrized over
  SUBMITTED / CANCEL_PENDING / TIMEOUT_QUARANTINE.
- [x] **F-002 (P1) — actor dropped from the audit event** → **Fixed** under **WO-0015**
  in `a7b012d`: the command actor is threaded route→facade→store→planner and recorded
  on both the `manual_flatten_deferred` (deferred path) and the created manual-flatten's
  `sell_intent_created` (create path) payloads, in both stores; defaults to `"system"`,
  and the protection-tick create stays `"system"`. `docs/INVARIANTS.md` INV-034/036
  follow-ups flipped to Resolved.

## Disputed Items
- None. (The reviewer's risk-3 judgment — that the flatten predicate should stay broad
  to avoid the ADR-002 blind-cancel hazard — was upheld; the fix surfaces the deferral
  explicitly rather than changing the decision.)

## Verification
- Tests added/extended: `tests/test_alpaca_marketdata_stream.py`,
  `tests/test_marketdata_route.py`, `tests/test_phase7_flatten_atomic.py`,
  `tests/test_phase6e_command_facade.py`, `tests/test_cockpit_positions.py` (all RED→GREEN;
  the SUBMITTED-only deferral test was strengthened into the dual-status parametrized form,
  no assertion weakened).
- Gates: full suite green (0 failed), `ruff check` clean, `mypy app/` Success,
  `import-linter` 5/0.
- Adversarial re-verification: `wf_eb46fdce-662` (VER-14/15a/15b/X) — all **PASS**.

## Follow-up
- **F-001/F-002 touch manual-flatten (human-gated) — gate CLEARED by REV-0003.** Those
  changes queued with the event-truth work in the re-review packet; **REV-0003 (Codex ACCEPT
  for WO-0015) cleared the gate** — see `work/review/REV-0003/disposition.md`. F-003
  (market-data) is not a human-gated surface (sizing-adjacent working data; no
  order/fill/position state).
- Ledger updated (`work/ledger.jsonl`: WO-0014, WO-0015).
