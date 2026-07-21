---
rev_id: REV-0037
title: Durable bounded envelope-disposition cancel convergence and reprice-only budget
reviewer: "Claude (independent; builder Codex)"
reviewed_ref: origin/codex/ultra-beta-batch
commit_range: origin/master..31d133d          # frozen semantic range actually reviewed: 1af0ae7..33ad906
targets: [WO-0124, ADR-010 §2/§5/§6, INV-083, INV-090]
human_gated_surfaces: [cancel-replace, event-log-truth, accepted-ADR-text, invariant-record-text]
date: 2026-07-21
verdict: ACCEPT-WITH-CHANGES
---

# REV-0037 — result

## Verdict: ACCEPT-WITH-CHANGES

No P0 or P1 finding. The human-gated cancel/replace change is correctly scoped to D-0124,
reproducibly green from a clean worktree, and its safety pins genuinely fail under mutation. Two
non-blocking P2 advisories (one already author-disclosed) should be recorded in the disposition;
neither gates beta reliance. The independent-review gate for this human-gated surface **clears**.

I re-derived behavior from the code and from fresh, failure-capable probes; I did not accept the
author's evidence as a verdict. Every property below is anchored to file:line, a pinning test I
re-ran, and — where load-bearing — an in-process mutation I applied and restored.

### Scope note that shaped this review
The frozen semantic range is `1af0ae7..33ad906` (23 commits, all WO-0124). Within that range the
budget change is exactly two things: `_BUDGET_ACTIONS: {"reprice","cancel"} → {"reprice"}`
(`app/sellside/policy.py:73`) and a comment-only edit to `ExecutionEnvelope.cancel_replace_budget`
(`app/models.py:713`). The shared projection `project_envelope_replaces_used`, the facade consumer,
and the removal of the vestigial stored `replaces_used` field are **WO-0126/WO-0114** commits
(`108874f`, `759eff0`) that are ancestors of the range start `1af0ae7` — verified with
`git merge-base --is-ancestor`. They belong to sibling review gates, not REV-0037. I therefore
judged D-0124 correctness on the flip-to-reprice-only plus end-to-end consistency, and treated the
budget-projection scaffolding as pre-existing baseline.

---

## Findings

### P0 (blocking) — none

Explicitly checked and refuted each BLOCK trigger from the request:
- No adapter cancel without its exact durable pre-IO attempt (proven at every one of 3 calls, not
  just the first — `app/monitoring.py` phase-1-before-phase-2, and the per-call store assertion in
  `test_direct_cancel_retries_are_bounded_then_escalate_once:661`).
- No fourth direct cancel, including when the escalation write faults
  (`test_failed_human_escalation_never_reopens_venue_authority:791-799`, re-run green; Mutant B
  below proves the bound pin can fail).
- No automatic-recovery ownership of the tracked order: `_recover_unpersisted_submits` filters
  `statuses={RECOVERY_UNRESOLVED}` (`app/monitoring.py:3556`); the latch is born terminal
  `RECOVERY_NEEDS_REVIEW` (`:1373`) and is idempotent on the exact pair
  (`app/store/memory.py:4215-4225`).
- No identity widening: symbol-only ambiguity fails closed with a warning and targets nothing
  (`app/monitoring.py:1471-1485`); venue targets exclude recovery + uncertain-claim
  (`:1512-1519`); the projection binds every cancel/snapshot pair to the exact concrete broker id.
- No position/fill-truth substitution: the cancel event is non-minting — it never becomes
  `canonical_actions[order_id]` and carries no fill/terminal authority
  (`app/store/core.py:1591-1650`, comment at `:1685-1690`).
- No unapproved gated/schema/live-surface change in-range (see scope table).

### P1 (important) — none

- **Scope:** every changed file in `1af0ae7..33ad906` is inside `allowed_paths`; no
  `app/adapters/**`, `app/facade/**`, or `cockpit/**` touched. `app/models.py` is comment-only in
  range (verified diff). Interestingly, `app/store/memory.py` / `app/store/sqlite.py` were **not**
  modified though allowed — the projection lives entirely in the shared `app/store/core.py`
  consumed by both stores, and the escalation reuses the existing `create_submit_recovery` seam.
- **No weakened tests.** The WO-0126 oracle change is a legitimate re-ratification, not a
  weakening: `_old_inline_count`→`_ratified_reprice_count`, `{"reprice","cancel"}`→`{"reprice"}`,
  and the asserted count `2→1` (`tests/test_wo0126_replace_budget_single_source.py`). It still runs
  as a differential oracle and still turns RED under Mutant A. Incumbent suites are net-additive
  (`test_wo0036_r2_hostile_closure.py` +463/−1, `test_wo0113_safe_local_cancel.py` +876/−9).

### P2 (advisory, non-blocking)

- **P2-1 — Corrupt/malformed lineage is surfaced only by a recurring log, not a durable
  operator-visible record.** `app/monitoring.py:1486-1511`. When the shared projection reports
  `missing_envelope_ids | missing_order_ids | invalid_order_ids`, convergence fails closed
  (correct — no target is guessed) but emits only a per-tick `_log.warning`; no deduped
  `needs_review` record is created, so a genuinely stranded legacy SELL behind a corrupt lineage
  reaches a human only via log noise. The author explicitly disclosed this at `:1499-1501`
  ("…writes the event log — a human-gated surface — and is beyond this additive-logging fix;
  flagged for a separate decision"). *Why it matters:* recovery-ledger visibility is the intended
  human surface for stranded venue exposure; logs are lossy. *Resolution:* track a follow-up
  decision to emit one deduped `needs_review` for persistent malformed lineages (a human-gated
  event-log write, correctly deferred to its own gate). Pre-existing WO-0036 behavior; not a
  regression introduced here.

- **P2-2 — Escalation is isolated per-envelope, not per-child.** `app/monitoring.py:1676-1683`
  (phase-1 `_escalate_disposition_cancel_exhausted` is not wrapped) propagates to the per-envelope
  handler at `:1870`. If `create_submit_recovery` faults **permanently**, a legacy multi-child
  envelope where one child is exhausted aborts the whole envelope's convergence pass every tick, so
  sibling children's cancels are deferred indefinitely. *Reachability is low:* v1 enforces one
  working child, so this needs a pre-R2/legacy multi-broker-child lineage **and** a permanent
  recovery-store write failure; it is fail-closed (zero venue calls) throughout. *Resolution:*
  consider isolating the exhausted-child escalation so a faulting latch cannot stall sibling
  cancels. Advisory only.

- **Informational (not a finding) — mutation redundancy in broker-identity enforcement.** Foreign
  broker identity is caught by *two* independent projection checks: the payload-vs-order compare
  (`app/store/core.py:1647`, `event.payload.broker_order_id != order.broker_order_id`) and the
  target-snapshot cross-check (`:1730-1739`, `target_order.broker_order_id != target_broker_order_id`).
  Removing either **alone** leaves `test_cancel_event_with_foreign_broker_identity_fails_projection_closed`
  green (I confirmed both single-check mutants survive); removing **both** turns it RED on both
  stores. This is legitimate defense-in-depth, not a vacuous pin — but the author's mutation-log
  line "remove cancel broker-order-id comparison → foreign identity projected valid" is imprecise:
  it requires removing both comparisons. Noted for disposition accuracy only.

---

## Properties table

| # | Property (from request) | Status | Anchor / evidence |
|---|---|---|---|
| 1 | Every disposition cancel (expiry CANCEL_AND_RETURN **and** stale-data CANCEL) has a bounded reconcile-driven convergence path; failed cancel never rests forever | **VERIFIED** | Both dispositions route to `_cancel_envelope_working_order` (`monitoring.py:2089-2107`); both re-driven each tick by `_converge_envelope_disposition_cancels` (`:1797`, invoked `:2335`). GATE: `_converge_expired_envelope_cancels` is now a thin wrapper (`:1874-1879`) — WO-0036's EXPIRED path is **retained and reused**, not rebuilt; WO-0124 **added** the stale-data path, durable evented attempts, the bound, the brokerless request, and target-snapshot binding. |
| 2 | Never blind-resubmit / blind-cancel a venue-uncertain order (TIMEOUT_QUARANTINE/SUBMITTING); ambiguity posture holds | **VERIFIED (read + corpus)** | Venue targets = `venue_orders − (recovery ∪ uncertain_claim)` (`monitoring.py:1512-1519`); SUBMITTING-without-broker → non-IO `cancel_request` only (`:1520-1528`); `venue_call_orders` require a broker id and status ∉ {CREATED, CANCEL_PENDING} (`:1629-1634`). Projection classes SUBMITTING/TIMEOUT_QUARANTINE as `uncertain_claim` (`core.py:1380`). Pre-existing posture reused; `test_wo0036_r2_hostile_closure.py` green. |
| 3 | Disposition cancels emit `envelope_action` with `envelope_id` provenance (replayable) | **VERIFIED** | `_persist_disposition_cancel_attempt` appends ENGINE/LOCAL `ENVELOPE_ACTION`, `action=cancel`, `envelope_id=envelope.id`, contiguous `attempt`, `target_snapshot`, before IO (`monitoring.py:1315-1341`). Fresh probe INV-083b: durable event carries `envelope_id`. |
| 4 | D-0124: `_BUDGET_ACTIONS` excludes disposition cancels; accounting matches; ADR-010 §5 text agrees | **VERIFIED** | `_BUDGET_ACTIONS = {"reprice"}` (`policy.py:73`); single projection consumed by both enforcement (`policy.py:292,529`) and facade display (`facade/store_backed.py:663`). ADR-010 §2 (reprice-only) + §6 (cancel/cancel_request spend zero) + INV-083 + INV-090 + model comment all consistent. Mutant A (add `cancel` back) → 2 pins RED. Fresh probe INV-083a: reprice=1, cancel/cancel_request/refused_stale all 0. |
| 5 | Cancel authority never widened beyond validated identity (INV-090 Cluster C) | **VERIFIED** | Symbol-only ambiguity fails closed, targets nothing (`monitoring.py:1471-1485`); projection binds each cancel to exact `(order_id, broker_order_id)` and every snapshot pair to the same envelope + real Order broker id (`core.py:1613-1650, 1727-1739`). Fresh probe INV-090: cancel naming child A's order with child B's **real** broker id → A invalid, A absent from venue targets; well-formed control leaves A valid. |
| 6 | Both stores + restart parity; failed-cancel-then-crash pinned | **VERIFIED (ran)** | `test_stale_cancel_failure_then_sqlite_restart_converges`, `test_historical_cancel_never_retargets_future_child_after_sqlite_restart`, `test_third_cancel_transition_race_revalidates_terminal_truth` (param: cancel-ack/fill × returned/lost) — all green on `[memory]` and `[sqlite]`. |
| 7 | Red-first integrity: named pins can actually fail | **VERIFIED** | Mutants A/B/C each turned the corresponding pin RED on both stores; the foreign-identity pin turns RED when both redundant checks are removed (see Informational note). |
| — | Q3: policy cannot overtake an in-flight cancel before terminal truth; can safely resume after | **VERIFIED (fresh probe)** | A failed stale-cancel leaves the child in `unresolved_order_ids` **and** `venue_orders` (bucket probe); the `_run_one_envelope` guard (`:1982-2017`) returns early, so a forced reprice issued **zero** venue calls while the obligation was open. Once the child goes terminal it leaves `unresolved`, and the guard releases — matching ADR-010 §6. |
| — | Pre-existing "broker-open interval behind local terminal" branch unchanged/unduplicated (request point 6) | **VERIFIED (read)** | That branch still creates a default `RECOVERY_UNRESOLVED` record, reason `cancel_terminal_venue_interval` (`monitoring.py:1707-1725`), distinct from the new terminal `RECOVERY_NEEDS_REVIEW` latch, reason `envelope_disposition_cancel_exhausted` (`:1362-1381`). Different order-state, reason, and cleanup_status. |

No property REFUTED. No property left only PLAUSIBLE.

---

## Mutation / disproof pass (applied in a scratchpad worktree, each restored)

| Mutant | Target pin | Result |
|---|---|---|
| A: add `"cancel"` to `_BUDGET_ACTIONS` | `test_disposition_cancel_does_not_spend_reprice_budget`, `test_shared_projection_matches_the_complete_incumbent_action_corpus` | **RED** (env-1 projected 2 vs 1) |
| B: `_DISPOSITION_CANCEL_RETRY_LIMIT` 3→4 | `test_direct_cancel_retries_are_bounded_then_escalate_once` | **RED** both stores (4th venue call) |
| C: escalate to `RECOVERY_UNRESOLVED`/`SUBMIT_RECOVERY_RECORDED` | `test_direct_cancel_retries_are_bounded_then_escalate_once` | **RED** both stores |
| D1: remove payload-vs-order broker-id check only | foreign-identity pin | SURVIVED (redundant — see Informational) |
| D2: remove target-snapshot broker cross-check only | foreign-identity pin | SURVIVED (redundant) |
| D1+D2: remove both broker-id checks | foreign-identity pin | **RED** both stores (pin is genuinely failable) |

---

## Fresh probes (new scenarios, not reruns of author pins)

- **INV-083a (accounting):** history with `reprice + refused_stale + cancel + cancel_request` in one
  envelope → `project_envelope_replaces_used` charges exactly 1 (reprice only). **PASS.**
- **INV-083b (integration):** expire → `_cancel_envelope_working_order` fires exactly one venue
  cancel, appends one durable `envelope_id`-stamped event, budget projection unchanged 0→0.
  **PASS.**
- **INV-090 (cross-child real identity):** built child A and child B in independent stores (the
  same-symbol exit-preemption guard blocks two children in one store), projected jointly, forged a
  cancel naming A's `order_id` but B's **real** broker id → A ∈ `invalid_order_ids`, A ∉ venue
  targets; well-formed control leaves A valid and a venue target. **PASS.** (Symbol match — both
  AAPL — did not authorize.)
- **Q3 overtake guard:** failed stale-cancel then data-clears + forced reprice → guard held, zero
  venue reprice/submit; bucket probe confirms the mechanism (`order ∈ unresolved_order_ids`).
  **PASS.**

---

## Ran vs read

**Ran (executed; exit 0 unless noted), Python 3.11.15, worktree at `33ad906`, deps already present:**
- `tests/test_wo0124_disposition_cancel_convergence.py` + `tests/test_wo0126_replace_budget_single_source.py` → **39 passed**.
- Corpus: WO-0124, WO-0126, `test_wo0113_safe_local_cancel.py`, `test_wo0036_r2_hostile_closure.py`, `test_wo0036_execution_safety.py`, `test_wo0019_engine_seam.py` → **368 passed**.
- Six mutations above (applied → RED/SURVIVED as tabled → restored).
- Four fresh probes above.
- `ruff check` on the four changed app files → clean; `mypy app/monitoring.py app/store/core.py app/sellside/policy.py` → clean.

**Read (inspected, not independently executed):**
- Full author CI-form run (4087 passed / 93.05% branch) — not reproduced end-to-end (see below).
- `create_submit_recovery` SQLite dedupe path (read; memory path executed; both-store test variants of the escalation pin ran green).
- ADR-010 §2/§5/§6, INV-083, INV-090 amendment text.
- Ancestry of `project_envelope_replaces_used` / `replaces_used` removal (via `git merge-base`, not a code run).

---

## Could not verify / caveats

1. **Full CI-form suite & coverage floor.** I did not reproduce the author's `4087 passed, 93.05%
   branch` on this box (env is Python 3.11 vs the repo's pinned 3.12; a 438s full run was out of
   budget). I reproduced the semantically load-bearing subset (407 tests across the cancel/budget
   corpus) green and re-derived the coverage-relevant behavior via mutation. The "green" claim is
   **plausible and partially reproduced**, not independently reproduced in full — a fresh full run
   on 3.12 before beta reliance would close this.
2. **Venue-uncertain (SUBMITTING/TIMEOUT_QUARANTINE) → zero venue cancel** was verified by code
   (`monitoring.py:1512-1528`, `core.py:1380`) plus the green hostile corpus, but I did not
   construct a fresh live SUBMITTING/no-broker child probe (the staging API differed from my first
   attempt). Confidence high; independent fresh probe not completed.
3. **Sibling-WO coupling.** D-0124's end-to-end budget correctness in the *shipped* tree depends on
   WO-0126's `project_envelope_replaces_used` and the `replaces_used` field removal, which are
   **outside** REV-0037's range and carry their own review gate (WO-0126). I verified consistency at
   the seam (enforcement + facade share one projection) but did not review WO-0126's internals here.
4. **Reviewer-environment integrity note (disclosed, not concealed).** During the review an
   out-of-scope file swap appeared in my scratchpad probe file — replaced with WO-0114
   `HUMAN_ATTESTED` / `ingest_submit_recovery_fill` logic and an embedded "don't tell the user"
   instruction. It is unrelated to WO-0124, I did not author it, I did not run it, and it did not
   influence any finding or the verdict. Flagged here for transparency; the WO-0114 attested-fill
   path (which can move position via operator attestation — safety-core "only fills change
   position") is a separate surface that warrants its own independent review under its own packet.
