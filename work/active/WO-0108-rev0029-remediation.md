---
type: Work Order
title: REV-0029 remediation — close the three execution-safety classes (P0-1/2/3) + P1-1/P1-2ext
status: ACTIVE
work_order_id: WO-0108
wave: R2 consolidation campaign (CAMPAIGN-0002), post-review remediation
model_tier: strong
risk: high
disposition: []
owner: Ameen
created: 2026-07-18
gated_surface: order submission/claim, manual flatten, candidate dispatch, event-log truth
---

# Work Order: REV-0029 remediation

## Goal

Close the three independently-reproduced execution-safety classes from the REV-0029 BLOCK
(`work/review/REV-0029/result.md`) plus the two accepted P1s, under the operator's 2026-07-18
policy ratifications (disposition.md): **Policy A** — full needs_review submission quarantine;
**Policy B** — flatten/protection stand down same-symbol BUY candidates + dispatch refusal +
cross-side claim rail. TDD, both stores, every pin red-first. The merge gate reopens only on
re-review ACCEPT.

## Scope (allowed_paths)

```yaml
allowed_paths:
  - work/active/WO-0108-rev0029-remediation.md
  - work/review/REV-0029/**
  - work/review/CAMPAIGN-0002-claude/**
  - work/ledger.jsonl
  - tests/**
  - app/store/core.py
  - app/store/base.py
  - app/store/memory.py
  - app/store/sqlite.py
  - app/policy.py
  - app/monitoring.py
  - app/reconciliation.py
  - app/facade/store_backed.py
  - docs/INVARIANTS.md
  - docs/adr/ADR-010-execution-envelope.md
  - pkl/**
  - .ai-os/core/15_CROSS_MODEL_REVIEW.md
```

The last two paths (added 2026-07-18, flagged D7-style widening) carry the **review-hardening
protocol amendment** the operator asked for as part of this WO's close-out — the durable process
change the REV-0029 post-mortem earned. `pkl/process/review-hardening.md` is the authoritative
page; `.ai-os/core/15_CROSS_MODEL_REVIEW.md` gets a one-line pointer to it (the core file only
checks for existence, not content-hash — `check_install` verified).

`app/policy.py` (added 2026-07-18, Step 2 P0-2, flagged) is the home of the new
`MAY_EXECUTE_ORDER_STATUSES` constant — the exact "may execute" set the operator ratified
(`open claims + broker-working + CANCEL_PENDING + TIMEOUT_QUARANTINE`, i.e. `NON_TERMINAL` minus
`CREATED`), placed directly beside its parent `NON_TERMINAL_ORDER_STATUSES`. This is mechanical
placement of an already-ratified policy concept, not a new decision; the `policy.py` import
contract (kernel + abstract market-data only) is unchanged — `lint-imports` verified 6 kept / 0
broken.

```yaml
forbidden_paths:
  - Any push/rebase/merge of a branch other than consolidate/r2-canonical.
```

## Build order (each step: red pins → fix → both stores → gate → commit)

1. **P0-1** — split `CANCELLABLE_BUY_STATUSES` (the current three) from
   `FLATTEN_BLOCKING_BUY_STATUSES` (+ `SUBMITTING`, `CANCEL_PENDING`, `TIMEOUT_QUARANTINE`).
   `flatten_position` signals `FLATTEN_BUYS_OPEN` while ANY blocking BUY is non-terminal; the
   facade retry cancels only the cancellable set and fails closed (409) when ambiguity persists —
   never blind-cancels `SUBMITTING`/`TIMEOUT_QUARANTINE`. Pins: every non-terminal BUY status ×
   flatten, the cancel→CANCEL_PENDING→late-fill interleaving, bound exhaustion, override survival.
2. **P0-2 (Policy B)** — (a) flatten + protection-open atomically stand down PENDING/APPROVED
   same-symbol BUY candidates (audited `candidate_transition … reason=exit_preemption`);
   (b) candidate dispatch refuses while a same-symbol exit obligation may execute; (c) final
   submission claim gains the symmetric cross-side same-symbol rail (BUY blocked while an exit may
   execute; SELL blocked while a BUY may execute — "may execute" includes open claims,
   broker-working intervals, `CANCEL_PENDING`, `TIMEOUT_QUARANTINE`). Pins: the approval-pause
   race, post-mint BUY creation, both claim orderings, manual + protection paths, the full sweep.
3. **P0-3 (Policy A)** — envelope stage AND final claim fail closed on same-lineage
   `needs_review_child_order_ids`; direct-SELL dispatch/claim exposure scans widen to
   `RECOVERY_OPEN_STATUSES`. Pins: recovery latched before stage; appearing between stage and
   claim; both lanes (same-envelope, fresh-owner); both stores.
4. **P1-1** — monitoring's `_validated_envelope_lineage` loads the store projector's bounded
   identity universe (parent / owner-correlation / order-owner / symbol), warns on ambiguity,
   cancels nothing unvalidated. Pins: correlation-keyed + order-owner-keyed hostile shapes.
5. **P1-2 extension** — close-parity script gains retry/restart + rollback-injection variants.
6. Docs: flip each 2026-07-18 "OPEN DEFECT" correction (ADR-010 §3/§4, INV-090, INV-081, plan
   OBS-2, PD-1 premise) to amended-and-closed wording as its fix lands — same commit.

## Done-when

- [ ] Steps 1–5 implemented, red-first pins green on both stores; step-6 doc flips shipped with each.
- [ ] Reviewer's reproduction scenarios (result.md P0-1/2/3 probes) re-run and now fail closed.
- [ ] Full native gate + coverage floor + AI-OS hygiene green.
- [ ] Re-review packet queued (REV-0029 round 2 or REV-0030) — merge gate reopens only on ACCEPT.

## Progress log

- **Step 1 (P0-1) DONE** — commit "WO-0108 step 1": `FLATTEN_BLOCKING_BUY_STATUSES` superset in
  core; both stores detect it; facade fails closed on venue-uncertain buys, never blind-cancels
  (zero-venue-calls pinned). Full suite 3080/0/0/12.
- **Step 3 (P0-3, Policy A) DONE** — commit "WO-0108 step 3": scans widened to
  `RECOVERY_OPEN_STATUSES` (Lane B closes at creation); stage + final-claim rails on
  `needs_review_child_order_ids` (Lane A + latched-after-stage race). 22/22 WO-0108 pins; two
  X-003-era pins amended with citations; full suite 3086/0/0/12.
- **Step 2 (P0-2, Policy B) DONE** — commit "WO-0108 step 2": three-layer "exit preempts" on both
  stores. (a) Cross-side same-symbol claim rail as the FINAL claim gate — a BUY and an exit SELL for
  one symbol can never both pass. "BUY may execute" = new `MAY_EXECUTE_ORDER_STATUSES` (`app/policy.py`)
  = `NON_TERMINAL` minus `CREATED` — the exact reviewer set (open claim / broker-working /
  CANCEL_PENDING / TIMEOUT_QUARANTINE); CREATED is excluded because a pre-claim BUY is blocked at its
  OWN claim while the exit is live (asymmetric: the exit set stays full `NON_TERMINAL`, so a freshly
  minted CREATED exit already preempts). The rail runs last (only on an otherwise-claimable order), so
  a symbol-wide overfill quarantine (ADR-001) or a Rule-8 stop keeps precedence and reports its reason
  first. (b) Flatten (SUPERSEDE_AND_CREATE) + protection-open atomically stand down same-symbol
  PENDING/APPROVED BUY candidates (audited `candidate_transition … reason=exit_preemption`).
  (c) `create_order_for_candidate` refuses dispatch while a same-symbol exit may execute
  (`candidate_dispatch_blocked` → `OrderIntentBlockedError`). 14 P0-2 pins (7×2 stores); reviewer's
  result.md P0-2 reproduction re-run fails closed (1 SELL / 0 live BUY, candidate EXPIRED, dispatch
  refused). **Zero existing tests needed Policy-B amendment** — the 198 pre-fix failures were all
  fixture-artifact (establishing BUY parked in `CREATED`, now excluded by MAY_EXECUTE) or reason-
  precedence (fixed by running the rail last), never the unsafe behavior. Full suite 3088/0/0
  (11 skip, 1 xfail); ruff + mypy(app, 64 files) + lint-imports(6·0) + both oracles green; scope
  widened to `app/policy.py` (flagged — MAY_EXECUTE home, import contract unchanged). Docs: ADR-010 §4
  + INVARIANTS self-cross corrections flipped P0-1/P0-2 → amended-and-closed.
- **Step 4 (P1-1) DONE** — commit "WO-0108 step 4": monitoring's `_validated_envelope_lineage` now
  discovers actions through the store's OWNER-SCOPED identity universe (parent envelope + owner
  correlation + referenced-order owner, matching the gates' `action_in_scope`; owners resolved for
  every order any action references), not an exact-`envelope_id` subset. An owner-keyed malformed
  action with a wrong/missing parent — which the store quarantines — is now projected malformed in
  monitoring too, so `_cancel_envelope_working_order` fails closed with the R6 diagnostic instead of
  projecting clean-empty and silently stranding it. Projection stays envelope-scoped; the symbol key
  is deliberately excluded (per-envelope owner-scoped convergence — the store omits it when keyed by
  intent). 5 red-first pins (correlation-keyed + order-owner-keyed × both stores + sqlite restart) in
  `tests/test_wo0036_r2_hostile_closure.py`. Full suite 3093/0/0 (11 skip, 1 xfail); ruff + mypy(app)
  + lint-imports green. Docs: INVARIANTS INV-090 correction flipped P0-3 + P1-1 → amended-and-closed.
- **NEXT — Step 5 (P1-2 ext)**: the close-parity full-fidelity comparison already landed (commit
  321320c, uncontested-fixes split); add the retry/restart + rollback-injection VARIANTS the reviewer
  asked for to `tests/test_wo0036_r2_close_and_recovery_ownership.py`.
- **Then**: Step 6 remaining doc flips (ADR-010 §3, INV-081, plan OBS-2 as their fixes are confirmed),
  the review-hardening Tier-1 CI gates (enum-total classification + producer/consumer grep, blocking),
  then the REV-0029 round-2 re-review packet (merge gate reopens only on ACCEPT).

## Batched ratifications (Ameen, 2026-07-18 — up-front, to run remediation→re-review without stops)

- **P0-2 = Exit preempts.** Flatten AND autonomous protection atomically STAND DOWN (cancel,
  audited `candidate_transition … reason=exit_preemption`) same-symbol PENDING/APPROVED BUY
  candidates; the cross-side claim rail (both stores, both directions) makes exits wait for any
  live BUY order to terminalize. "BUY may execute" = open claims + broker-working + CANCEL_PENDING
  + TIMEOUT_QUARANTINE. Layered: (a) claim rail = hard venue gate, (b) stand-down = preempt
  semantics + don't starve the exit, (c) dispatch-refuse = no new BUY order appears mid-exit.
- **Review-hardening gates = Blocking where cheap now.** Enum-total classification (the
  `FLATTEN_BLOCKING_BUY_STATUSES` pin) + producer/consumer grep for new safety fields are
  CI-blocking immediately; mutation-check + N-run are review-checklist items until automated
  (follow-up process WO). Recorded in `pkl/process/review-hardening.md`.
- **PD-1 = Keep parked** (post-merge WO with its own EventSource/EventAuthority design + review).
  Quarantine is fail-closed after P0-3; nothing forces the valve now.
- **Re-review = Same Codex session, round 2** (finder verifies the fixes are closed; one
  continuation round per the packet protocol).
- **Terminal (flagged, not decisions):** operator commissions the round-2 review; operator merges
  on ACCEPT.
