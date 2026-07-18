---
type: Work Order
title: REV-0029 round-3 remediation — close every confirmed round-2 finding (Codex implements)
status: QUEUED
work_order_id: WO-0109
wave: R2 consolidation campaign (CAMPAIGN-0002), post-review remediation (round 3)
model_tier: strong
risk: high
disposition: []
owner: Ameen
implementer_seat: Codex
review_seat: Claude or human (independent — NOT the implementer)
created: 2026-07-18
supersedes: the incomplete round-1/round-2 fixes tracked in WO-0108 (which the REV-0029 round-2 review BLOCKED)
gated_surface: order submission/claim, manual flatten, buy cancellation, recovery/event-log truth
---

# Work Order: REV-0029 round-3 remediation

> **Context for the implementer.** This repository is a **paper-trading simulator** — a FastAPI +
> SQLite engine that models the lifecycle of stock orders (create → submit → fill → position)
> against a broker **paper** sandbox. There is no live trading, no real funds, and no network,
> credential, or authentication surface. "Safety" here means order-lifecycle **correctness
> invariants** (a submitted order is not a fill; only fill events change position quantity; one exit
> per symbol; a flatten must not mint a sell beside a still-fillable buy). Every task below is
> ordinary defensive correctness engineering: fix a confirmed bug, then pin it with a test that
> provably fails without the fix.

## Goal

Close **every** finding the REV-0029 **round-2** review confirmed BLOCK-worthy
(`work/review/REV-0029/result-round2.md`), each of which was **independently re-verified** by the
Claude seat's triage (evidence inline below). WO-0108's round-1 fixes were partly pinned by tests
and gates that could not fail; round 3 fixes the code **and** re-pins it with **mutation-verified**
tests. On completion the branch returns to independent review; the merge gate reopens only on that
review's ACCEPT.

## Seat model for this work order (read first)

- **Implementer:** Codex. You write the code and the tests.
- **Independent review:** Claude or a human — **never Codex reviewing its own implementation.** The
  cross-model value is lost if the author reviews the author. When you finish, hand off for an
  independent round-3 review (new packet `work/review/REV-0030/` or a clearly-scoped continuation);
  do not self-certify the merge gate.
- **Human-gated surfaces** (order submission/claim, manual flatten, buy cancellation, recovery/
  event-log truth) are touched here. The operator (Ameen) has **authorized this remediation**. That
  authorization covers doing the work along the acceptance criteria below; it does **not** pre-approve
  the merge — the changes still pass independent review and an explicit operator merge.

## Operating discipline (Fable, every cluster)

1. **Red first.** Write the failing test(s) before the fix. Each new safety pin must be
   **mutation-verified**: delete or neuter the guarded branch and show the pin turns **red**; restore
   and show green. Record the mutation result in the commit message. A pin that stays green when its
   guard is removed does not count (this is the exact defect round 2 found in WO-0108 — NEW-P0-1,
   NEW-P1-1).
2. **Both stores.** Every state/order/recovery/claim behavior is pinned on **both** `InMemoryStateStore`
   and `SqliteStateStore` (the `any_store` fixture), and any store change lands in both
   implementations in the same commit.
3. **Full gate per commit:** `ruff check .` · `ruff format --check .` · `mypy app/` · `lint-imports` ·
   `pytest -q` (both stores) · the two spec oracles (`tests/r2_conformance_oracle.py`,
   `tests/test_r2_conformance_oracle_claude.py`) · `tests/test_review_hardening_gates.py` · the AI-OS
   hygiene scripts (`.ai-os/scripts/check_*`) including `check_work_order_scope.py` against this WO.
4. **Injected clock / deterministic IDs / no unseeded randomness** in engine logic (repo rule).
5. **Never weaken a test to make code pass.** Fix the code or flag the conflict.
6. **Close-out ships with the work:** the commit that finishes a cluster updates this WO's progress
   log and flips any doc/INV/ADR claim the fix changes, in the same commit.

## Scope (allowed_paths)

```yaml
allowed_paths:
  - work/queue/WO-0109-rev0029-round3-remediation.md
  - work/active/WO-0109-rev0029-round3-remediation.md   # when you move it to active on start
  - work/review/REV-0029/**
  - work/review/REV-0030/**                             # round-3 independent-review packet
  - work/ledger.jsonl
  - tests/**
  - app/monitoring.py
  - app/reconciliation.py
  - app/transitions.py
  - app/policy.py
  - app/store/core.py
  - app/store/base.py
  - app/store/memory.py
  - app/store/sqlite.py
  - app/facade/store_backed.py
  - app/models.py
  - docs/INVARIANTS.md
  - docs/adr/**                                         # a new ADR if a mechanism warrants one
  - pkl/**
```

```yaml
forbidden_paths:
  - Any push/rebase/merge of a branch other than consolidate/r2-canonical.
  - .agents/**, .codex/**  (the CI contamination guard fails the build if either is tracked).
```

If a performance profile (Cluster E) identifies a hot path outside this list, add the specific file
with a one-line flagged justification in this WO's scope section — do not silently widen.

## Build order

Dependency order: **A → B** first (the P0 safety core; B's test fix depends on A's exposure model),
then **C, D, E** (independent), then **F** (docs/close-out ships continuously with each cluster).

---

### Cluster A — P0-1 + P0-2: the flatten/cancel stale-snapshot race and recovery-blind exit claim

**Confirmed defect (re-verified by triage).**
- `cancel_open_buys` (`app/monitoring.py:263`) snapshots orders via `list_orders()`, then **branches
  on the stale snapshot status** (`app/monitoring.py:272`): for a snapshot-`CREATED` BUY it calls
  `transition_order(id, CANCELED)`.
- `transition_order` has **no compare-and-swap** (no `expected_from`; verified across
  `base.py:901`, `memory.py:3712`, `sqlite.py:5199`) and `SUBMITTING → CANCELED` **is legal**
  (`app/transitions.py:111-121`; the comment there literally reads "manual cancel raced the
  submit"). So if the submission sweep claims that BUY (`CREATED → SUBMITTING`) between the snapshot
  and the transition, the stale branch drives the now-live order to `CANCELED` **locally**, without a
  broker cancel — a locally-terminal but **venue-live** BUY (in flight, or owned by an open
  `SubmitRecoveryRecord`).
- Flatten detection and the cross-side exit-SELL claim both read **projected Order status only**
  (`memory.py:2588-2610`, `sqlite.py:3819-3837`), not open BUY recoveries, so the exit SELL mints and
  claims beside the venue-live BUY (P0-2). Reproduced deterministically in both stores by the review.

**Acceptance criteria (invariants that must hold).**
1. A local buy cancellation must be **atomic and conditional**: a stale caller may never terminalize a
   BUY that has advanced past `CREATED`. If the row is no longer `CREATED` at apply time, the operation
   must not local-cancel — it must fall through to the broker-cancel / `CANCEL_PENDING` path (or
   re-loop), so a venue-live order is never silently marked `CANCELED` locally.
2. Same-symbol BUY **execution exposure** is defined over projected Order state **and** open
   `SubmitRecoveryRecord` state (`unresolved` **and** `needs_review`), and that single definition is
   consumed by **both** flatten detection and the final exit-SELL claim. An exit SELL cannot claim
   while a same-symbol BUY is live at the venue by *either* signal.

**Recommended mechanism** (implementer may choose an equivalent that meets the criteria):
- Give `transition_order` an optional `expected_from: OrderStatus | frozenset` compare-and-swap
  argument (validated under the store lock, both stores), and have `cancel_open_buys` pass
  `expected_from=CREATED` on the local-cancel branch; on mismatch, take the broker-cancel branch.
  *(A dedicated `cancel_created_buy_if_unclaimed` store method is an acceptable alternative.)*
- Extend the same-symbol BUY-exposure helper (the one behind `_cross_side_claim_block_reason` and the
  flatten `FLATTEN_BLOCKING` scan) to also count open BUY `SubmitRecoveryRecord`s. Keep the existing
  `MAY_EXECUTE_ORDER_STATUSES` semantics for the Order-status portion; add the recovery portion.
- If the compare-and-swap changes the `transition_order` contract materially, record it in a short
  ADR amendment.

**Red pins (mutation-verified, both stores).** The exact review schedule: snapshot a `CREATED` BUY;
claim it to `SUBMITTING`; run the stale local-cancel; assert the BUY is **not** locally `CANCELED`
(stays claimable/recovers) and no exit SELL is minted/claimed beside a venue-live BUY. Plus: an exit
SELL is blocked while an open BUY recovery exists (both `unresolved` and `needs_review`), on both
flatten and final-claim paths.

---

### Cluster B — P0-3 recovery-scope ingress + NEW-P0-1 inert sibling pin

**Confirmed defect.**
- `create_submit_recovery` (`memory.py:3417`, sqlite twin) accepts `symbol`/`side` as free parameters
  and builds the record **without validating them against the referenced `local_order_id`'s order**.
  A recovery whose declared scope contradicts its order de-indexes the real SELL from the order-id
  exposure scan while the recovery scan looks under the (wrong) declared scope → a second same-symbol
  SELL reaches `SUBMITTING`. *Reachability caveat: all five current application producers copy scope
  from the order, so this is a **fail-closed-at-ingress** gap, not a current-call-graph path — but the
  repo standard is that the store ingress fails closed on malformed internal state.*
- NEW-P0-1: `tests/test_wo0108_rev0029_remediation.py:268-319` puts the `needs_review` recovery on the
  **claimed** order (`staged2.order.id`), so the block comes from the current-order guard, not the
  intended prior-sibling consumer. Deleting the sibling consumer leaves the test green — inert.

**Acceptance criteria.**
1. `create_submit_recovery` validates the record's immutable scope (symbol/side) against the existing
   local order **in the same lock/transaction**; on mismatch it fails closed (reject) or quarantines
   **both** the referenced order's scope and the declared scope — one identity may never suppress the
   other. Both stores.
2. The final-claim sibling rail is pinned by a test where the `needs_review` recovery belongs to a
   **distinct prior sibling** (not the order being claimed), plus a fresh-owner stage-before-latch and
   between-stage-and-claim schedule. Each stage and each final-claim consumer is **mutation-verified
   independently** in both stores.

**Red pins.** The corrected sibling schedule (O1 staged then canceled; O2 staged; `needs_review`
latched on O1; claim O2 → blocked with the explicit sibling reason), mutation-checked; and the
scope-mismatch ingress (declare a contradictory symbol/side → rejected/both-quarantined, second SELL
does **not** reach `SUBMITTING`), both stores.

---

### Cluster C — P1-1 monitoring symbol-scoped diagnostic + mutually-exclusive pins

**Confirmed defect.** Monitoring's `_validated_envelope_lineage` deliberately excludes the symbol key,
so a malformed action the store quarantines by **symbol only** (no correlation, no order-owner, no
parent to the envelope) projects clean-empty in monitoring → no R6 malformed-lineage warning, live
child left untouched. INV-090's "no monitoring path derives a neighboring definition / never
clean-and-empty for work the store quarantines" is therefore false. Also: the round-1 correlation pin
is **non-exclusive** — `_seed_owner_keyed_hostile_lineage` sets `child.sell_intent_id=owner.id`
always, so the order-owner key catches the `key="correlation"` case too.

**Acceptance criteria.**
1. Monitoring surfaces the R6 malformed-lineage **diagnostic** for a symbol-only malformed action the
   store quarantines (matching the store's symbol selector, `memory.py:1103-1106` /
   `sqlite.py:2015-2017`), while continuing to **refuse any broker cancel** unless owner/order identity
   validates — a symbol-scoped diagnostic that never guesses a cancel target.
2. The correlation and referenced-order-owner discovery keys are pinned by **mutually-exclusive**
   fixtures (the correlation case must NOT also satisfy the order-owner key), each mutation-verified.

**Red pins.** The symbol-only hostile-lineage probe (store quarantines; monitoring must now warn,
cancel nothing) and the two exclusive owner-key pins, both stores.

---

### Cluster D — P1-2 comparator fidelity + NEW-P1-1 real producer/consumer gate

**Confirmed defect.** The close-parity canonicalizer collapses **every** timestamp (regex + any
`isoformat`), erasing semantic `ExecutionEvent.ts_event` and deterministic payload timestamps like
`expires_at` — a payload mutation slips through undetected (instance-only, not a property check). And
`tests/test_review_hardening_gates.py:85-116` counts **basenames containing a substring**, so deleting
the real producer assignment or a rail consumer (leaving an import/comment) keeps T1.3 green.

**Acceptance criteria.**
1. The parity comparator normalizes **only** genuinely nondeterministic identity and ingest-clock
   fields; it preserves causal/event times (`ts_event`) and deterministic timestamp-bearing payload
   fields (`expires_at`). Equivalent acceptable: inject shared ID/clock sources into the two-store
   script and compare full raw dumps. Pin with a payload-timestamp mutation that the comparator now
   catches.
2. The T1.3 producer/consumer gate identifies **assignment and executable use sites** (AST-based, or
   equivalent), with **distinct** stage-consumer and final-claim-consumer entries per store. Each
   mutation in the round-2 table (remove the producer assignment; remove a stage consumer; remove a
   final-claim consumer; empty the `MAY_EXECUTE` expression leaving import/comment) must turn the gate
   **red**. Keep the effective T1.1 enum gates.

---

### Cluster E — P1-3 performance (folded in per operator direction)

**Confirmed status.** `python -m tests.performance.r2_scaling_gate` is red on two wall-clock ratios:
runtime p95 scale ratio ≈ **4.02 > `RUNTIME_SCALE_LIMIT = 3.0`** (`r2_scaling_gate.py:52`) and startup
elapsed scale ratio ≈ **20.37 > `STARTUP_SCALE_LIMIT = 12.0`** (line 53); the structural
scan/query/heap gates pass. The gate's own docstring states a measured failure "is a request for a
separately approved performance work order" — this cluster is that approval.

**Acceptance criteria (either path, evidence required).**
1. **Optimize to green:** profile the obligation-projection runtime hot path and the startup
   re-projection path; land minimal, behavior-preserving optimizations so both ratios fall under their
   limits with `tests/performance/r2_scaling_gate.py` green — **no behavior/invariant change** (the
   full suite + both oracles stay green). *(The indexed projection precedent from Part B is the model:
   asymptotic wins without semantic change.)* OR
2. **Re-justify the limits:** if the ratios reflect irreducible structural cost at the tested scale,
   propose operator-approved limit changes with profiling evidence, an ADR note, and the reasoning —
   never silently loosen a threshold.

Behavior-preserving performance changes are not a human-gated surface; a **threshold change (path 2)
is** an operator decision — surface it, don't self-approve.

---

### Cluster F — docs / invariants / close-out (ships with each cluster)

As each fix lands, update in the same commit: **INV-081, INV-090, ADR-010 §3/§4** (flip the round-2
"still-open / false" statements to accurate closed wording), any new ADR a mechanism warrants, and
this WO's progress log. When all clusters are green, write the round-3 close-out and the ledger entry,
and move this WO to `work/completed/`.

## Done-when

- [ ] Clusters A–E implemented; every new safety pin **red-first and mutation-verified** on both stores.
- [ ] The round-2 result's reproduction schedules (P0-1/2/3, P1-1, P1-2) re-run and now fail closed /
      are detected; `r2_scaling_gate` green (path 1) or a recorded operator-approved threshold (path 2).
- [ ] Full native gate + both oracles + `test_review_hardening_gates.py` + coverage floor + AI-OS
      hygiene (incl. scope + the CI contamination guard) green.
- [ ] Docs/INV/ADR flips shipped with their fixes; WO progress log current.
- [ ] **Independent** round-3 review packet queued (`work/review/REV-0030/`, reviewed by Claude or a
      human — not Codex). Merge gate reopens only on that ACCEPT + operator merge.

## Progress log

- **QUEUED 2026-07-18** — drafted by the Claude seat from its independent triage of
  `result-round2.md` (all eight round-2 findings confirmed; NEW-P1-2 contamination already removed in
  `e0da97d`, CI guard added in `aba8052`). Awaiting Codex to move to `work/active/` and begin at
  Cluster A.
