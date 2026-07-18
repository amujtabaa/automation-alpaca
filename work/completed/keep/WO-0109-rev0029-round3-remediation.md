---
type: Work Order
title: REV-0029 round-3 remediation — close every confirmed round-2 finding (Codex implements)
status: REVIEW
work_order_id: WO-0109
wave: R2 consolidation campaign (CAMPAIGN-0002), post-review remediation (round 3)
model_tier: strong
risk: high
disposition: [PKL_UPDATED, RESULT_SUMMARY_KEPT]
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
  - work/completed/keep/WO-0109-rev0029-round3-remediation.md  # required close-out move
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

- [x] Clusters A–E implemented; every new safety pin **red-first and mutation-verified** on both stores.
- [x] The round-2 result's reproduction schedules (P0-1/2/3, P1-1, P1-2) re-run and now fail closed /
      are detected; `r2_scaling_gate` green (path 1) or a recorded operator-approved threshold (path 2).
- [x] Full native gate + both oracles + `test_review_hardening_gates.py` + coverage floor + AI-OS
      hygiene (incl. scope + the CI contamination guard) green.
- [x] Docs/INV/ADR flips shipped with their fixes; WO progress log current.
- [x] **Independent** round-3 review packet queued (`work/review/REV-0030/`, reviewed by Claude or a
      human — not Codex). Merge gate reopens only on that ACCEPT + operator merge.

## Progress log

- **ACTIVE 2026-07-18** — Codex implementer seat activated the authorized work order on
  `consolidate/r2-canonical`. Fable FULL gate loaded; beginning Cluster A with red dual-store pins
  before production changes.
- **Cluster A VERIFIED 2026-07-18** — root cause: `cancel_open_buys` chose a local-cancel branch
  from a stale `CREATED` snapshot, while flatten and final SELL claim projected BUY exposure from
  Order status only. Fix: store-atomic `transition_order(expected_from=CREATED)` plus one shared
  order-and-open-recovery BUY exposure projection consumed by flatten and final claim, in both
  stores. Red baseline: `tests/test_wo0109_round3_remediation.py` = **10 failed** (2 stale-CAS,
  4 flatten-recovery, 4 final-claim-recovery). Green: **10 passed**. Mutation proof: neutering the
  memory CAS and SQLite CAS independently made their exact race pin fail (1/1 each); deleting the
  monitoring caller's `expected_from` made both race pins fail (2/2); deleting each store's open
  recovery contribution made that store's unresolved/needs-review flatten and claim pins fail
  (4/4 each); restored suite returned 10/10 green. Full cluster gate: Ruff lint/format, mypy (64
  files), six import contracts, full `pytest -q` (exit 0, 278.5s), both spec oracles (61 green;
  22 green + 6 documented skips), hardening gates (5 green), all applicable AI-OS checks, scoped
  work-order check, and contamination guard passed. ADR-010 §4 and INV-081 corrected in the same
  cluster.

- **Cluster B VERIFIED 2026-07-18** — root cause: `create_submit_recovery` trusted caller-declared
  symbol/side even when the referenced local Order still existed, and the round-2 sibling test put
  its recovery on the order under claim rather than on the intended prior sibling. A pre-existing
  malformed direct recovery was also visible only through its declared scope. Fix: both store
  ingresses validate immutable recovery scope against an existing Order under the same lock or
  transaction and reject a mismatch without a write; genuinely missing local rows remain supported.
  Legacy open direct recoveries project through either their declared scope or the referenced
  Order's immutable SELL scope, so neither identity can suppress the other.
  The corrected schedules use a distinct terminal O1 recovery to block O2, plus a fresh owner whose
  direct sibling recovery appears before stage or between stage and final claim. Red baseline after
  fixture validation: the 4 public-ingress symbol/side mismatch cases failed while all 6 honest
  sibling schedules were already green; the audit-added raw legacy symbol/side cases then failed
  4/4. Green: all 14 Cluster B cases; restored cross-cluster target set **28 passed**, including the
  raw Envelope-corruption projection pin. Mutation proof: neutering each store's ingress guard
  failed its 2 exact mismatch cases; removing each store's referenced-Order scope arm failed its 2
  exact legacy cases; neutering the same-lineage stage consumer failed the
  existing exact memory/SQLite pin independently; neutering each same-lineage final-claim consumer
  failed its corrected prior-sibling pin; neutering each direct-exposure stage consumer failed its
  fresh-owner pre-stage pin; and neutering each direct-exposure final-claim consumer failed its
  between-stage-and-claim pin. Every mutant was restored and the 28-test target returned green. Full
  cluster gate: Ruff lint/format, mypy (64 files), six import contracts, full `pytest -q` (exit 0,
  255.0s), both spec oracles (61 green; 22 green + 6 documented skips), hardening gates (5 green),
  all applicable AI-OS checks, scoped work-order check, and contamination guard passed. ADR-010 §3
  and INV-090 now state the recovery-ingress invariant and the honest dual-store pins.

- **Cluster C VERIFIED 2026-07-18** — root cause: cancellation target discovery correctly used
  owner identities, but a malformed action selected only by the store's symbol projection appeared
  clean-empty in monitoring and emitted no R6 diagnostic; the prior correlation fixture also matched
  the order-owner key. Fix: correlation and referenced-order-owner hostile fixtures are mutually
  exclusive, both stores expose a locked read-only symbol-ambiguity view of the shared projection,
  and cancellation logs symbol-only ambiguity without adding any child to its owner-authorized
  target set. Red baseline: the 2 symbol-only dual-store probes failed while the 4 exclusive owner-
  key cases and SQLite restart remained green. Green: **7 passed**; each symbol-only case asserted
  one fail-closed warning containing the missing/invalid ids, zero broker cancels, and an unchanged
  `SUBMITTED` child. Mutation proof: deleting correlation discovery failed its 2 exact cases;
  deleting referenced-order-owner discovery failed its 2 exact cases; emptying the memory and
  SQLite symbol-diagnostic seams independently failed their exact store case; and neutering the
  monitoring warning branch failed both symbol-only cases. Every mutant was restored and 7/7
  returned green. Full cluster gate: Ruff lint/format, mypy (64 files), six import contracts, full
  `pytest -q` (exit 0, 287.8s), both spec oracles (61 green; 22 green + 6 documented skips),
  hardening gates (5 green), all applicable AI-OS checks, scoped work-order check, and contamination
  guard passed. An independent read-only audit found no issues. ADR-010 §3 and INV-090 now record
  the diagnostic-scope/cancel-authority split.

- **Cluster D VERIFIED 2026-07-18** — root cause: the parity canonicalizer collapsed every datetime
  and ISO timestamp, while T1.3 counted filenames containing text instead of executable producer and
  rail sites. Fix: parity now normalizes only generated 32-hex identities plus root audit
  `created_at` / execution `ts_init`; cross-store scripts freeze the core/memory/SQLite clock
  sources, preserving causal `ts_event` and payload `expires_at`. T1.3 parses executable AST sites
  for the real producer, four distinct memory/SQLite stage/final guards, and both
  `MAY_EXECUTE_ORDER_STATUSES` helper arguments. Red baseline: the semantic `ts_event` and payload-
  expiry comparisons failed 2/2 while the positive ingest-clock/id normalization case passed; the
  first semantic-helper pins failed before the AST helpers existed. An independent audit then
  demonstrated four false-positive shapes in the first AST implementation (nested dead raise,
  non-blocking `return None`, post-return guard, and post-return producer/consumer); the added
  adversarial pins failed 2/2 before reachability/direct-exit tightening. Green target:
  **37 passed** across the parity and hardening files; explicit hardening gate **12 passed**.
  Mutation proof: re-normalizing `ts_event` failed its semantic-time pin; restoring blanket ISO
  normalization failed the payload-expiry pin; separately omitting audit-clock, execution-clock, or
  ID normalization failed the positive pin. Emptying the real projection producer, neutering each
  of the four stage/final guards, and emptying each store's `MAY_EXECUTE` argument independently
  failed its exact AST entry after the audit correction; all mutants restored. Full cluster gate:
  Ruff lint/format, mypy (64 files), six import contracts, full `pytest -q` (exit 0, 254.9s), both
  spec oracles (61 green; 22 green + 6 documented skips), hardening gates (12 green), all applicable
  AI-OS checks, scoped work-order check, and contamination guard passed. Re-audit confirmed the P1
  resolved with no remaining code finding. ADR-010 §3, INV-090, and the T1.3 PKL process page now
  describe the fidelity and executable-site requirements.

- **Cluster E VERIFIED 2026-07-18** — unprofiled red baseline reproduced both approved performance
  findings: runtime p95 growth **6.63× > 3×** and startup elapsed growth **19.89× > 12×**. Profiling
  identified two asymptotic multipliers: both stores' order-status migration scanned the complete
  event log once per Order, and SQLite's owner/symbol action queries walked the global
  `ENVELOPE_ACTION` corpus through a `LEFT JOIN`/`OR` predicate on every projection. Fix: both
  backfills build one lifecycle-order-id set; SQLite decomposes the exact immutable-identity formula
  into indexed parent, event owner/symbol, and referenced-Order owner/symbol arms, intersects owner
  and symbol identity sets when both selectors are present, deduplicates by event id, applies
  exclusion after composition, and restores sequence order. New Order symbol/owner and event
  correlation indexes make each arm seekable. Referenced-Order event reads are chunked below the
  connection's SQLite variable ceiling. No threshold or retention/action-authority behavior changed.
  Red-first deterministic pins: the legacy nested backfill read lifecycle fields **324 times** against
  a linear bound of 72 on each store; the unbounded linked-Order query raised `OperationalError: too
  many SQL variables` under a reduced limit. Green: backfill target **8 passed**, full hostile-closure
  **200 passed**, and the scaling gate passed three sequential unprofiled runs with runtime ratios
  **0.58–1.01×** and startup ratios **9.13–10.26×**. Mutation proof: restoring the legacy global
  action query made the gate red (startup **14.51×**); forcing the symbol arm onto the type-only
  global index made both the structural scan gate and runtime ratio red (**5.33×**); restoring the
  nested backfill made the deterministic dual-store work counter fail 2/2. Independently removing
  event-correlation, referenced-Order-owner, event-symbol, or referenced-Order-symbol discovery
  failed its exclusive memory/SQLite pin. Broadening owner∩symbol to union, dropping parent override,
  losing dedupe, bypassing exclusion, or removing sequence sort each failed the selector matrix;
  an unbounded bind list and a first-chunk-only mutant each failed the reduced-limit pin. All mutants
  were restored. Full cluster gate: Ruff lint/format (243 files), mypy (64 files), six import
  contracts, full `pytest -q` (exit 0, **317.5s**), both spec oracles (61 green; 22 green + 6
  documented skips), hardening gates (12 green), scaling gate, and all AI-OS checks passed. An
  independent re-audit found and then verified closure of the bind-limit/test-quality issue and
  returned **ACCEPT**. ADR-010, INV-090, and the testing-model PKL page record the behavior-preserving
  selector and deterministic scaling evidence.

- **QUEUED 2026-07-18** — drafted by the Claude seat from its independent triage of
  `result-round2.md` (all eight round-2 findings confirmed; NEW-P1-2 contamination already removed in
  `e0da97d`, CI guard added in `aba8052`). Awaiting Codex to move to `work/active/` and begin at
  Cluster A.

- **ROUND-3 IMPLEMENTATION CLOSED / REVIEW QUEUED 2026-07-18** — commits `5b4e742`, `1e14189`,
  `3f85656`, `d12596d`, and `51dee57` close Clusters A–E. Final native suite: **3,146 passed, 11
  skipped, 1 expected xfail**; branch coverage **93.92% ≥ 93%** (487.03s). Both spec oracles,
  hardening, scaling, Ruff, mypy, import contracts, PKL/ledger/disposition/version/install checks,
  work-order scope, and contamination guard are green. The unrelated hygiene reporter still sees
  the pre-existing tracked `work/completed/delete-candidates/.gitkeep`; while the work order was
  active it also emitted the expected length advisory, which no longer applies after completion.
  Neither finding was changed or hidden. Durable lessons are in code/tests, ADR-010, INV-081,
  INV-090, the testing/review PKL pages, and the ledger. `work/review/REV-0030/request.md` queues the
  required independent Claude/human review of `7e59a9e..51dee57`. No merge or push was performed;
  the merge gate remains closed pending an independent ACCEPT and explicit operator merge.

```yaml
fable_done:
  task: "WO-0109 round-3 implementation and independent-review handoff"
  done_when_results:
    - item: "Clusters A-E implemented with red/green and mutation evidence"
      status: MET
      evidence: "Five scoped commits; per-cluster evidence above"
    - item: "Full gate, coverage, performance, and both oracles green"
      status: MET
      evidence: "3146 passed; 93.92% branch coverage; scaling gate green; oracles 61 and 22+6 skips"
    - item: "Independent review queued without self-review or merge"
      status: MET
      evidence: "REV-0030 targets 7e59a9e..51dee57; result.md intentionally awaits the review seat"
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  debt_check: "No new debt; pre-existing hygiene findings disclosed above"
  deferred:
    - "Independent REV-0030 verdict and disposition"
    - "Explicit operator merge/push"
  status: VERIFIED
```
