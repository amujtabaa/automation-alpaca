---
type: Work Order
title: PR #9 Codex-review round-3 follow-ups — exit-preempt CREATED-buy self-cross, protection fail-closed, late-fill cleanup parity
status: COMPLETED
work_order_id: WO-0112
wave: R2 consolidation campaign (CAMPAIGN-0002), PR #9 merge-review follow-up (round 3)
model_tier: strong
risk: high
disposition: [RESULT_SUMMARY_KEPT]
owner: Ameen
implementer_seat: Claude
review_seat: Codex PR reviewer (re-reviews the pushed delta on PR #9)
created: 2026-07-18
gated_surface: exit-preempt / order cancellation, autonomous protection exit, envelope terminal cleanup
---

# Work Order: PR #9 review round-3 follow-ups

> Paper-trading simulator; order-lifecycle correctness only. Operator authorized addressing the three
> findings the Codex automated reviewer raised on the PR #9 delta (`ba6be70`). All three are
> PRE-EXISTING R2 safety-surface gaps (not introduced by WO-0109/0111); Codex surfaced them while
> re-reviewing the full PR. Each was empirically confirmed before any change.

## Findings & fixes (all verified real; F1/F3 both stores, F2 memory-only parity)

- **F3 (P1 — §5.3 self-cross re-grow).** The exit-preempt stand-down
  (`_stand_down_symbol_buy_candidates_*`) only expired PENDING/APPROVED BUY *candidates*. A
  same-symbol BUY already dispatched to a **CREATED order under an ORDERED candidate** was neither
  stood down (its candidate is ORDERED) nor blocking to the exit's claim (`MAY_EXECUTE_ORDER_STATUSES`
  deliberately excludes CREATED). So the exit SELL claimed and filled, and after it went terminal the
  untouched CREATED buy could claim and **re-grow the exited position** — the self-cross flatten
  already prevents (`FLATTEN_BLOCKING_BUY_STATUSES` includes CREATED). *Empirically confirmed on both
  stores* (the CREATED buy survived an envelope-stage exit).
  **Fix:** a new companion `_stand_down_symbol_created_buys_*` locally CANCELs every same-symbol,
  still-unexecuted (`filled_quantity == 0`) CREATED BUY order in the same atomic unit as the exit's
  candidate stand-down, both stores (reuses the `_cancel_staged_envelope_orders_*` mechanism). CREATED
  == never venue-submitted → a pure local write; SUBMITTING+ (venue-uncertain) buys are left to the
  claim rail / F1 fail-closed path; `filled_quantity == 0` spares an establishing-BUY stub. The
  documented MAY_EXECUTE design is left intact — the gap is closed by cancellation at preempt time
  (the flatten precedent), not by counting CREATED as may-execute.

- **F1 (P1 — protection wedge / mis-size).** `open_protection_exit` minted the `PROTECTION_FLOOR`
  SELL even when a same-symbol BUY may execute, unlike `flatten_position` which fails closed. The
  cross-side claim rail then wedged that SELL, or (if the BUY later filled) it was sized to the
  pre-fill quantity.
  **Fix:** before minting, if a same-symbol BUY is in `MAY_EXECUTE_ORDER_STATUSES` (venue-uncertain,
  not locally cancellable), fail closed — return `None` (already a valid signal for this
  `Optional[Order]` method) with an audited `protection_open_deferred` event — so the monitoring loop
  retries next tick, by which point the BUY is terminal and the exit sizes to the true position. Both
  stores. F1 (MAY_EXECUTE fail-closed) and F3 (CREATED cancel) together cover the full non-terminal
  BUY set, matching flatten's coverage with the right action per status.

- **F2 (P2 — memory/SQLite parity).** On a late fill against an already-terminal envelope
  (`plan.transition is None`), memory skipped the staged-child cancel + owner-reconcile because that
  cleanup was nested under the transition-only branch; SQLite runs it whenever the stored envelope is
  terminal. A legacy/crash-recovery terminal envelope with a live CREATED child was thus cleaned under
  SQLite but not memory — an `any_store` divergence. *Confirmed:* the F2 pin is red on memory, green
  on SQLite pre-fix.
  **Fix:** memory keys the terminal cleanup on `not ENVELOPE_TRANSITIONS.get(stored.status)` (mirroring
  SQLite), so it runs on a transition-less late fill too, and exactly once when a terminal transition
  already ran (that path used `reconcile_owner=False`).

## Evidence

- **Empirical repro first** (F3 + F2 probes on both stores), then red-first:
  `tests/test_wo0112_pr9_review_round3.py` (F3, F1 × both stores; F2 red on memory / green on SQLite).
- **Mutation-verified** (in-place edit-back, never `git checkout`): neuter each — the F3 created-buy
  stand-down call (memory & SQLite), the F1 fail-closed `buy_hit` gate (memory & SQLite), the F2
  terminal-cleanup condition (memory) — turns its exact pin red; restored green. Five mutations.
- **Full gate green:** `ruff check` + `ruff format --check`; `mypy app/` (64 files); `lint-imports`
  (6 contracts); full `pytest` suite (100%, exit 0) incl. both spec oracles + review-hardening gates;
  perf gate `passed: true` (limits unchanged); AI-OS hygiene all pass; contamination guard clean.

## Design choices flagged for review (F1/F3 touch human-gated safety surfaces)

- **F3 targets `filled_quantity == 0` CREATED BUY orders only** — a deliberate choice so an
  establishing-BUY stub `append_fill` may leave parked in CREATED (shares already folded) is untouched;
  only a buy's *future* execution is the re-grow risk. It cancels CREATED buys during **every**
  exit-preempt caller (envelope-stage, protection-open, flatten); redundant-but-harmless for flatten,
  which already handled CREATED.
- **F1 defers (returns `None`) rather than raising** — protection is autonomous and re-attempted each
  monitoring tick, so a silent-but-audited deferral (retry after the buy clears) is the fail-closed
  behavior consistent with flatten; it leaves the position momentarily unprotected until the buy
  resolves, which is the safe trade vs. minting a wedged/mis-sized exit.

## Done-when

- [x] F3 + F1 fixed on both stores; F2 on memory (SQLite already correct); red-first + mutation-verified.
- [x] Full native gate + oracles + hardening gates + perf gate + AI-OS hygiene green.
- [ ] Pushed to `consolidate/r2-canonical` (PR #9 head); Codex PR reviewer re-reviews the delta;
      operator ratifies the F1/F3 design choices and merges after the re-review is clean.
