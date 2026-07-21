---
type: Work Order
title: Codex primary-seat engagement — review the prior seat's WO-0111/WO-0112, remediate all findings, close the recurring gap classes, reach merge-readiness
status: CLOSED
work_order_id: WO-0113
wave: R2 consolidation campaign (CAMPAIGN-0002), merge-readiness (Codex primary seat)
model_tier: strong
risk: high
disposition: [PKL_UPDATED, RESULT_SUMMARY_KEPT]
record_reconciliation: "WO-0120 (2026-07-20) verified REV-0033 RESOLVED at cdb7dd9 and operator merge 88833e3d; a canonical CLOSED ledger row is appended."
owner: Ameen
implementer_seat: Codex (primary implementation seat — durable operator decision, 2026-07-19)
review_seat: Claude or human (independent — NOT the implementer; REV-0033)
created: 2026-07-19
supersedes: the "findings only / do not push code" instruction inside work/review/REV-0031/request.md and work/review/REV-0032/request.md — under this WO the same seat records findings first, then implements the fixes
gated_surface: order submission/claim, candidate dispatch, manual flatten, autonomous protection exit, emergency-reduce authorization, envelope stage/terminal cleanup, recovery/event-log truth
---

# Work Order: WO-0113 — Codex primary-seat remediation to merge-readiness

> **Context for the implementer.** This repository is a **paper-trading simulator** — a FastAPI +
> SQLite / in-memory engine that models the lifecycle of stock orders (create → submit → fill →
> position) against a broker **paper** sandbox. There is no live trading, no real funds, and no
> network, credential, or authentication surface. "Safety" here means order-lifecycle **correctness
> invariants** (a submitted order is not a fill; only fill events change position quantity; one exit
> per symbol; a buy and an exit sell for one symbol are never both working at the venue). Every task
> below is ordinary defensive correctness engineering: confirm or refute a suspected bug with
> evidence, fix what is real, and pin it with a test that provably fails without the fix.

## Execution checkpoint

```yaml
execution_checkpoint:
  updated_at_utc: "2026-07-20T04:36:41Z"
  repository: "amujtabaa/automation-alpaca"
  branch: "consolidate/r2-canonical"
  local_head: "9215b08515d1f55204e7ef902a81477042933687"
  upstream_head: "9215b08515d1f55204e7ef902a81477042933687"
  pr_number: 9
  pr_head: "9215b08515d1f55204e7ef902a81477042933687"
  working_tree: CLEAN
  working_tree_detail: "closeout commit delivered; no source or test changes after the frozen implementation SHA"
  checkpoint_scope: "post-closeout delivery snapshot; the additive metadata-only reconciliation commit is reported with exact SHA and CI in the final response"
  staged_paths: []
  unstaged_paths: []
  final_implementation_range:
    base_sha: "194343c2cd2d5d96d4bf073cfc4e945dd43d71ab"
    head_sha: "9a7af3b08a2d050e324a862d59548ff2da747c48"
    changed_path_count: 86
    authoritative_inventory_command: "git diff --name-only 194343c2cd2d5d96d4bf073cfc4e945dd43d71ab..9a7af3b08a2d050e324a862d59548ff2da747c48"
  final_implementation_path_excerpt_note: "navigation excerpt only; the command and count above are authoritative"
  final_implementation_path_excerpt:
    - "app/broker/adapter.py"
    - "app/broker/alpaca_paper.py"
    - "app/broker/mock.py"
    - "app/broker/sim.py"
    - "app/events/projectors.py"
    - "app/models.py"
    - "app/monitoring.py"
    - "app/policy.py"
    - "app/reconciliation.py"
    - "app/store/base.py"
    - "app/store/core.py"
    - "app/store/memory.py"
    - "app/store/sqlite.py"
    - "pyproject.toml"
    - "docs/00_START_HERE.md"
    - "docs/05_REVIEW_CHECKLIST.md"
    - "docs/INVARIANTS.md"
    - "docs/MIGRATION_MATRIX.md"
    - "docs/adr/ADR-001-overfill-quarantine.md"
    - "docs/adr/ADR-002-timeout-quarantine.md"
    - "docs/adr/ADR-003-manual-flatten-halted-reducing.md"
    - "docs/adr/ADR-008-order-status-event-provenance.md"
    - "docs/adr/ADR-010-execution-envelope.md"
    - "pkl/log.md"
    - "pkl/process/migration-history.md"
    - "pkl/safety/invariants-rationale.md"
    - "tests/r2_conformance_oracle.py"
    - "tests/test_air_group_b.py"
    - "tests/test_alpaca_paper_order_status.py"
    - "tests/test_alpaca_paper_submit.py"
    - "tests/test_duplicate_fill.py"
    - "tests/test_eng002_quarantine_budget.py"
    - "tests/test_eng002b_quarantine_fairness.py"
    - "tests/test_input_validation.py"
    - "tests/test_monitoring.py"
    - "tests/test_rev0023_phase_a_pins.py"
    - "tests/test_spine_phase3b_overfill_quarantine.py"
    - "tests/test_spine_phase3c_timeout_quarantine.py"
    - "tests/test_spine_phase4_reconcile_acting.py"
    - "tests/test_spine_phase4_reconcile_event_truth.py"
    - "tests/test_spine_phase4_reconcile_notfound.py"
    - "tests/test_spine_phase4_reconcile_synthetic_throttle.py"
    - "tests/test_spine_phase4_reconciliation_engine.py"
    - "tests/test_sqlite_store.py"
    - "tests/test_store_core.py"
    - "tests/test_wave0_submission_claim.py"
    - "tests/test_wo0019_engine_seam.py"
    - "tests/test_wo0019a_broker_replace.py"
    - "tests/test_wo0021_envelope_chaos.py"
    - "tests/test_wo0036_r2_hostile_closure.py"
    - "tests/test_wo0113_acceptance_identity.py"
    - "tests/test_wo0113_attribution_repair.py"
    - "tests/test_wo0113_lifecycle_closure.py"
    - "tests/test_wo0113_monitoring_failclosed.py"
    - "tests/test_wo0113_store_parity.py"
    - "tests/test_wo0113_submit_acceptance_fallback.py"
    - "work/active/WO-0113-codex-primary-remediation.md"
    - "work/completed/delete-candidates/.gitkeep (deleted)"
  closeout_paths_committed_at_9215b08:
    - "docs/05_REVIEW_CHECKLIST.md"
    - "docs/INVARIANTS.md"
    - "docs/adr/ADR-001-overfill-quarantine.md"
    - "pkl/log.md"
    - "pkl/safety/invariants-rationale.md"
    - "work/ledger.jsonl"
    - "work/review/REV-0031/disposition.md"
    - "work/review/REV-0032/disposition.md"
    - "work/review/REV-0033/request.md"
    - "work/completed/keep/WO-0113-codex-primary-remediation.md"
  current_phase: "final implementation and closeout delivery remotely verified; REV-0033 queued"
  current_cluster: "none; no self-executable WO-0113 item remains"
  completed:
    - "Preflight reconciled local/upstream/PR head at 96d1c0242682a0cd8c197c1354c70857dd772fdb and base at 2aa377a35d35e85be120cf90cdb6c5bd85a8d546; exact-head CI was green."
    - "Mapped every accepted-submit producer and the fallback, repair, exposure, CAPI, claim, cancel, recovery-loop, and restart consumers."
    - "Centralized the canonical UNKNOWN fallback at the reconciliation dependency seam and routed ordinary plus envelope submit/replace acceptances through it."
    - "Canonicalized broker ids at every producer ingress and durable assignment boundary; blank post-call identity is ambiguous and quarantined rather than released as preflight rejection."
    - "Made canonical fallback ownership suppress stale SUBMITTING redrive before repair."
    - "Changed recovery cardinality to one exact canonical local/broker pair per row: one local may retain multiple concrete venue legs; every concrete broker id remains globally exclusive across order, recovery, and canonical-fallback representations."
    - "Pinned repair, SQLite restart, independent poll/cancel/resolve, and CAPI release 200->100->40 for distinct accepted legs."
    - "Changed fill-divergence recovery dedupe from any-local to exact accepted identity."
    - "Recorded all five operator semantic decisions RATIFIED_YES across the work order and affected ADR/INV/PKL/operator/review documentation."
    - "Authoritative accepted-ownership slice is 228/228 green across six files; the complete 12-file WO corpus plus timeout quarantine is 421/421 green."
    - "Concrete Alpaca direct and duplicate-recovery submit/replace acknowledgement handling is 48/48 green across its two complete adapter files."
    - "Persisted exact venue scope now authenticates to immutable Order/recovery identity before every poll, targeted query, mass reconciliation, recovery, or external-order suppression consumer."
    - "Mass reports preserve replace predecessor lineage and reject fractional managed fill levels; submit/replace ACKs reject unknown lifecycle or malformed cumulative state without rejecting broker overfill truth."
    - "Envelope scope capture uses the injected decision clock; the new dual-store boundary pin was red 2/2 before the fix and green 2/2 after it."
    - "ADR-001 broker-authoritative order/envelope overfill now records raw FILL plus explicit QUARANTINED truth atomically; exact fill replay dedupes, changed economics conflicts, LOCAL/SYNTHETIC excess rejects, and quarantine-key poison fails before mutation."
    - "Fresh integrated evidence: venue/reconciliation cluster 353 passed; overfill/store/monitoring cluster 212 passed; store parity follow-up 57 passed; touched production static checks are green."
    - "Source freeze declared after the final formatted 10-file corpus passed 598/598 on an external basetemp; the in-process independent source audit returned ACCEPT with no open P0/P1."
    - "T1.2 guard removal proved four new safety rails can fail: advanced mass material 1/1 red, immutable venue-scope owner poison 4/4 red, record-first overfill quarantine 2/2 red plus quarantine-key poison 4/4 red, and submit/replace ACK lifecycle 16/16 red; every mutation was restored and its same slice returned green."
    - "Exact Ruff check/format, mypy app (64 files), import-linter (6 kept/0 broken), and diff check are green. Ruff excludes only ignored .pytest* runtime artifacts after OS ACLs made those artifacts unreadable and undeletable."
    - "All 47 repository-suite regressions were traced to legacy fixtures/doubles that bypassed exact venue-scope semantics; no product defect was found. The 13-file repaired compatibility corpus passed 522/522, and the source-freeze corpus passed 598/598 again."
    - "Both conformance oracles are green (Codex 61/61; Claude 22 passed/6 documented skips), and review hardening is 12/12 green."
    - "The current scaling gate passed three consecutive runs with every gate true; runtime ratios were 1.3107, 0.8181, and 1.0266, startup elapsed ratios were 9.4612, 9.0201, and 8.8985, and startup select ratio remained 9.1022."
    - "The current full suite passed three consecutive times on the unchanged product tree in 336.551s, 379.071s, and 385.331s (3859 passed, 11 skipped, 1 xfailed; 3871 collected each run)."
    - "Current branch coverage passed at 93.50% against the configured 93.0% floor in 523.3s, with the same zero-failure full-suite outcome."
    - "AI-OS install/version/ledger/PKL/disposition/scope checks are green; context hygiene has zero violations and only the expected active-WO length advisory, which the required closeout move removes."
    - "The automated Codex review of 5ae2c75 reproduced one P1: SQLite's candidate-admission and final-claim quarantine reads selected only FILL facts, omitting explicit positive-position QUARANTINED truth that memory and the public list already consumed."
    - "Red-first dual-store pins failed exactly on SQLite at both gates (2 failed / 2 passed); the shared gate/list projection plus a SQLite reopen pin are 5/5 green, the complete Phase-3b file is 27/27, and independent admission/claim guard removals each failed only their SQLite node."
    - "Fresh post-remediation gates are green: relevant 10-file cluster 274/274; complete WO/quarantine corpus 580/580; Ruff check/format, mypy 64 files, import-linter 6/0, both oracles 61/61 and 22 passed/6 skips, hardening 12/12, and scaling 3/3."
    - "Fresh full suite passed three consecutive times: 3859 passed, 11 skipped, 1 xfailed (3871 collected) with XML suite times 336.551s, 379.071s, and 385.331s. Coverage repeated the full suite with zero failures/errors and met the 93.0% floor at 93.50% in 523.3s."
    - "Frozen final implementation SHA 9a7af3b08a2d050e324a862d59548ff2da747c48 is pushed on consolidate/r2-canonical; GitHub Actions run #482 succeeded on that exact SHA."
    - "Automated final-head review comment 5018668794 reviewed 9a7af3b08a and reported no major issues; all nine historical review threads remain resolved."
  active_findings:
    - id: "WO0113-SIBLING-DURABLE-VENUE-SCOPE-CORRELATION"
      severity: P1
      status: FIXED
      root_cause: "The persisted Order row is intent, not the exact rendered venue request. Poll/targeted/mass/replace consumers re-derived or incompletely compared type, price, extended-hours, advanced fields, predecessor lineage, and immutable owner quantity, allowing restart drift or scope poison to authenticate a foreign venue row."
      next_action: "Retain the source-frozen pins through repository-wide and exact-head remote gates."
    - id: "WO0113-SIBLING-ADR001-OVERFILL-CONFLICT-TRUTH"
      severity: P0
      status: FIXED
      root_cause: "Store twins rejected broker order excess, treated changed economics under one source_fill_id as a benign duplicate, and could persist record-first envelope overfill without explicit positive-position quarantine; a poisoned quarantine dedupe key could also suppress containment after raw truth mutation."
      next_action: "Retain the source-frozen pins through repository-wide and exact-head remote gates."
    - id: "WO0113-SIBLING-TARGETED-PRESENT-FILL-INGESTION"
      severity: P1
      status: FIXED
      root_cause: "Not-found reconciliation returned after a targeted client-id hit even though that response carries cumulative state without priced executions; a terminal fill absent from the mass OPEN report could remain scalar-only forever."
      next_action: "Retain the exact-identity direct-poll and budget-defer/converge pins in the final focused corpus."
    - id: "PR9-96D1C02-P1-ENVELOPE-ACCEPT-OWNERSHIP"
      severity: P1
      status: FIXED
      root_cause: "Envelope submit and replace duplicate accepted-ack finalization in reconciliation.py, while the canonical last-write UNKNOWN fallback lives only in monitoring.py's ordinary-submit handler. If SUBMITTED and recovery persistence both fail, the envelope path raises with no durable owner. The same ingress also preserves padded broker IDs instead of enforcing one canonical identity."
      resolution: "Shared dependency-safe fallback, exact context, normalized identity, dual-store/restart pins."
    - id: "WO0113-SIBLING-STALE-REDRIVE-FALLBACK"
      severity: P1
      status: FIXED
      root_cause: "Stale SUBMITTING reclaim excluded open recoveries but not the canonical accepted-submit fallback, allowing a second venue call before repair."
      resolution: "Selective canonical fallback lookup adds the order to already-covered ownership; guard-removal failed 2/2."
    - id: "WO0113-SIBLING-MULTIPLE-ACCEPTED-LEGS"
      severity: P1
      status: FIXED
      root_cause: "Both stores modeled recovery ownership as singular by local order even though INV-091 treats distinct broker ids as distinct possible venue legs."
      resolution: "Exact-pair rows, globally exclusive concrete broker ids, plural local index in memory, selective SQLite lookup without schema migration, independent repair/recovery/restart/CAPI pins."
    - id: "WO0113-SIBLING-FILL-DIVERGENCE-IDENTITY"
      severity: P1
      status: FIXED
      root_cause: "Fill-divergence escalation deduped on any local recovery, so one broker leg could suppress required ownership for another."
      resolution: "Exact local/broker identity lookup and dual-store mutation pin."
    - id: "WO0113-SIBLING-BLANK-POSTCALL-BROKER-ID"
      severity: P1
      status: FIXED
      root_cause: "A venue call returning blank identity was classified as BrokerError, releasing the claim even though acceptance may have occurred."
      resolution: "Classify as AmbiguousBrokerError at ordinary first submit, stale redrive, envelope submit, and envelope reprice; dual-store empty/whitespace pins quarantine and suppress redrive."
    - id: "WO0113-SIBLING-CROSS-REPRESENTATION-BROKER-IDENTITY"
      severity: P1
      status: FIXED
      root_cause: "Concrete broker-id exclusivity was enforced only recovery-to-recovery, so an order or canonical fallback under one local id could be rebound through another representation to a different local id."
      resolution: "Both stores now reject cross-local collisions across order, recovery, and canonical-fallback owners; same-pair representations coalesce and SQLite rebuilds both durable ownership indexes on restart."
    - id: "WO0113-SIBLING-STORE-BOUNDARY-BROKER-CANONICALIZATION"
      severity: P1
      status: FIXED
      root_cause: "Recovery and lifecycle store boundaries trusted already-normalized callers, so padded aliases could become distinct durable identities and whitespace-only recovery ids could appear concrete."
      resolution: "One canonicalization helper now binds order transition, timeout resolution, and recovery creation in both stores; alias and sentinel cases are dual-store mutation-pinned."
    - id: "WO0113-SIBLING-ALPACA-ACK-IDENTITY"
      severity: P1
      status: FIXED
      root_cause: "The concrete Alpaca adapter converted SDK ids with str() at four submit/replace success and duplicate-recovery exits; None became the apparently concrete identity 'None', while blank replace success was a retryable BrokerError."
      resolution: "One adapter-level canonical acknowledgement helper now returns a stripped concrete id or raises AmbiguousBrokerError at all four exits; 12 red-first and guard-removal cases pin None, empty, and whitespace responses."
    - id: "PR9-5AE2C75-P1-SQLITE-EXPLICIT-QUARANTINE-GATES"
      severity: P1
      status: FIXED
      root_cause: "SQLite's candidate-admission and final submission-claim gates independently selected only FILL facts before calling the shared quarantine projector. An explicit ADR-001 QUARANTINED fact for an order overfill that left position positive was therefore visible to list_quarantined_symbols and memory, but invisible to both SQLite autonomous-BUY gates."
      resolution: "Both stores now expose one lock-held quarantine projection to candidate admission, final claim, and the public list; SQLite selects both FILL and QUARANTINED facts. Dual-store positive-position intent/claim pins, a SQLite reopen pin, and independent guard removals close both consumers."
  last_red:
    command: ".venv/Scripts/python.exe -m pytest -q tests/test_spine_phase3b_overfill_quarantine.py::test_explicit_order_overfill_quarantine_blocks_new_buy_intent tests/test_spine_phase3b_overfill_quarantine.py::test_explicit_order_overfill_quarantine_blocks_existing_buy_claim --basetemp=<external>"
    decisive_output: "2 failed / 2 passed: memory blocked both paths; SQLite minted the autonomous BUY and claimed the pre-existing BUY because its gate queries discarded explicit QUARANTINED truth."
  last_green:
    command: ".venv/Scripts/python.exe -m pytest -q --cov=app --cov-branch --cov-report=term-missing --basetemp=<external>"
    decisive_output: "3859 passed, 11 skipped, 1 xfailed (3871 collected); configured 93.0% branch floor met at 93.50%; zero failures/errors; exit 0 in 523.3 seconds."
  last_mutation:
    mutation: "Disabled the shared explicit-quarantine projection at SQLite candidate admission and final claim independently; also reduced the shared SQLite projection to FILL-only."
    expected_test: "Each gate-specific positive-position pin must fail only for SQLite when its own guard is removed; the shared projection mutation must fail every SQLite/list/restart consumer while memory stays green."
    observed_result: "Admission mutation: 1 SQLite failure / 1 memory pass. Claim mutation: 1 SQLite failure / 1 memory pass. Shared FILL-only mutation: 3 exact SQLite failures. All edits restored in place; dual-store plus restart slice returned 5/5 green. Earlier mutation evidence remains retained below."
    restored_in_place: true
  last_completed_command: "GitHub Actions run #484: SUCCESS on closeout SHA 9215b08515d1f55204e7ef902a81477042933687; Python 3.11 and 3.12 jobs and every step succeeded"
  next_exact_command: "Write-Output 'No self-executable WO-0113 item remains; await independent REV-0033 and explicit operator merge'"
  pending_remote_checks: []
  operator_decisions:
    created_buy_targeting: RATIFIED_YES
    protection_deferral: RATIFIED_YES
    append_only_attribution: RATIFIED_YES
    emergency_capability: RATIFIED_YES
    accepted_submit_fallback: RATIFIED_YES
  pending_operator_items: []
  blockers: []
  resume_instructions:
    - "Treat 9a7af3b08a2d050e324a862d59548ff2da747c48 as the frozen implementation SHA; do not change source or tests during closeout."
    - "No self-executable WO-0113 item remains. Obtain an independent REV-0033 result/disposition."
    - "Only the operator may merge PR #9 after all required review gates are satisfied."
```

## Goal

The operator has moved the **primary implementation (coding) seat to Codex** — durably, not per-WO.
Rationale: across four review rounds (REV-0029 rounds 1–2, and three automated PR-review rounds on
PR #9), the reviewing seat repeatedly found real correctness gaps in or adjacent to the prior
implementer seat's work — a treadmill of per-instance fixes each followed by a sibling gap. This WO
ends the treadmill in four phases:

- **A.** Independently review the prior seat's two most recent change sets (WO-0111, WO-0112) via
  the queued packets REV-0031 and REV-0032.
- **B.** Remediate every confirmed finding — from Phase A, and from any automated PR review of
  subsequent commits — and implement every final design choice now ratified by the operator.
- **C.** Run the **recurring-gap-class sweep** (§Phase C below): verify each cross-cutting
  correctness property at every choke point, both stores, so the remaining sibling gaps are closed
  **by property**, not instance-by-instance.
- **D.** Bring `consolidate/r2-canonical` to merge-ready with fresh evidence, queue the independent
  review of your own changes (REV-0033), deliver the batched operator questions, and ship close-out.
  **The merge itself remains the operator's action.**

## Seat model (read first)

- **Implementer:** Codex. You write the code and the tests, commit, and push to
  `consolidate/r2-canonical` only.
- **Phase A is a genuine independent review**: the WO-0111/WO-0112 deltas were implemented by the
  Claude seat, so your review of them is cross-model by construction. Deposit `result.md` in each
  packet folder before changing the code they cover.
- **Your own implementation is never self-certified.** When Phases B–C are done, queue
  `work/review/REV-0033/` (request.md describing your change set and how to verify it) for the
  independent seat (Claude or human). In-process validation never counts as independent review.
- **Human-gated surfaces** (listed in the frontmatter) are touched throughout. The operator has
  **authorized this engagement** — the review, the remediation, and the sweep. That authorization
  does **not** pre-approve semantic policy changes on gated surfaces (see the Operator decision
  queue) and does not pre-approve the merge.

## State at handoff (2026-07-19)

- Branch `consolidate/r2-canonical` at **`194343c`**, in sync with origin; **CI green** (4/4 jobs);
  PR #9 open against `master` (base `2aa377a`), mergeable. Local full gate reproduced green at the
  same commit (full suite, both spec oracles, hardening gates, scaling gate, AI-OS hygiene).
- Recent history (all by the prior implementer seat, all gated green at push):
  - `4d607da` **WO-0111** — two automated-review findings on the WO-0109 code: monitoring's
    single-envelope lineage projection disowned a supersession successor's order (fills would skip
    `record_envelope_fill`); the emergency-reduce authorization refused re-authorization while its
    grant was still active, stranding the documented retry path. Record:
    `work/completed/WO-0111-pr9-review-round2-followups.md`.
  - `ba6be70` — queued REV-0031 (review packet for WO-0111).
  - `194343c` **WO-0112** — three automated-review findings, all pre-existing gaps: the exit-preempt
    stand-down missed already-dispatched CREATED buy orders (position re-grow after an exit, §5.3);
    `open_protection_exit` minted a sell while a same-symbol buy was venue-uncertain (wedge or
    mis-size); memory skipped the terminal-envelope late-fill cleanup that SQLite runs (store-parity
    divergence). Record: `work/completed/WO-0112-pr9-review-round3-followups.md`, plus the queued
    REV-0032 packet.
- **Queued review packets (Phase A inputs):**
  - `work/review/REV-0031/request.md` — WO-0111, range `7194f02..4d607da`.
  - `work/review/REV-0032/request.md` — WO-0112, range `ba6be70..194343c`.
  - Both say "produce findings only; do not push code." **Superseded by this WO**: record the
    findings first (the packet result is the durable record), then implement the fixes yourself.
- **Operator decisions:** all five semantic recommendations were ratified YES by the operator's
  2026-07-19 autonomous-completion mandate; see the durable record below.
- **Parked, out of scope:** PD-1 (needs-review reconciliation release valve) is a post-merge WO;
  paper-broker backfill verification is a pre-beta task. Do not pull them in.

## Operating discipline (Fable, every cluster — identical to WO-0109)

1. **Red first.** Write the failing test(s) before the fix. Each new safety pin must pass a
   **guard-removal (mutation) check**: delete or neuter the guarded branch and show the pin turns
   **red**; restore **by editing back in place** (never `git checkout` over uncommitted work) and
   show green. Record the mutation result in the commit message.
2. **Both stores.** Every state/order/fill/recovery/claim behavior is pinned on **both**
   `InMemoryStateStore` and `SqliteStateStore` (the `any_store` fixture), and any store change lands
   in both implementations in the same commit.
3. **Full gate per commit:** `ruff check .` · `ruff format --check .` · `mypy app/` · `lint-imports`
   · `pytest -q` (both stores) · the two spec oracles (`tests/r2_conformance_oracle.py`,
   `tests/test_r2_conformance_oracle_claude.py`) · `tests/test_review_hardening_gates.py` ·
   `python -m tests.performance.r2_scaling_gate` · the AI-OS hygiene scripts
   (`.ai-os/scripts/check_*`), including the scope check against this WO.
4. **Injected clock / deterministic IDs / no unseeded randomness** in engine logic (repo rule).
5. **Never weaken a test to make code pass.** Fix the code or flag the conflict. Amending a test
   whose pinned behavior a fix legitimately changes requires an in-body citation of the finding and
   preservation (or strengthening) of the test's real invariant.
6. **Close-out ships with the work:** the commit that finishes a cluster updates this WO's progress
   log and flips any doc/INV/ADR/PKL claim the fix changes, in the same commit.
7. **Conflict rule:** if code, docs, and ADRs disagree on a gated surface, stop and record the
   decision gap in the Operator decision queue — do not silently pick a side.

## Scope (allowed_paths)

```yaml
allowed_paths:
  - work/queue/WO-0113-codex-primary-remediation.md
  - work/active/WO-0113-codex-primary-remediation.md    # move here on start
  - work/completed/keep/WO-0113-codex-primary-remediation.md  # required close-out move
  - work/review/REV-0031/**
  - work/review/REV-0032/**
  - work/review/REV-0033/**                             # your implementation's review packet
  - work/ledger.jsonl
  - work/completed/delete-candidates/.gitkeep       # flagged: remove the zero-byte placeholder so the canonical AI-OS delete-candidates hygiene gate can be green
  - tests/**
  - pyproject.toml                                  # flagged: Ruff must exclude ignored OS-ACL-protected .pytest* artifacts so the exact repository-wide static gates remain reproducible
  - app/broker/adapter.py                             # flagged: malformed post-call id is ambiguous in the abstract submit/replace contract
  - app/broker/alpaca_paper.py                        # flagged: canonicalize and fail closed on malformed SDK success/duplicate-recovery ids
  - app/broker/mock.py                                # flagged: keep the test adapter interface in parity with durable venue-scope correlation
  - app/broker/sim.py                                 # flagged: keep the deterministic simulator interface in parity with durable venue-scope correlation
  - app/monitoring.py
  - app/reconciliation.py
  - app/events/projectors.py                          # flagged: project accepted ADR-001 broker-authoritative overfill quarantine truth
  - app/transitions.py
  - app/policy.py
  - app/store/core.py
  - app/store/base.py
  - app/store/memory.py
  - app/store/sqlite.py
  - app/facade/store_backed.py
  - app/models.py
  - app/config.py                                      # flagged: stale-redrive setting comment must match the durable no-progress counter now enforced
  - docs/00_START_HERE.md                              # flagged: operator-facing lifecycle ownership summary must name the accepted-submit fallback
  - docs/05_REVIEW_CHECKLIST.md                        # flagged: review oracle must recognize the exact fallback owner
  - docs/MIGRATION_MATRIX.md                           # flagged: retained migration evidence must no longer call projected fill progress or broker-authoritative reconciliation fills deferred/synthetic
  - docs/INVARIANTS.md
  - docs/adr/**
  - pkl/**
  - tests/test_lifecycle_state_machine.py              # flagged: the universal live-order invariant must include the canonical fallback owner
```

```yaml
forbidden_paths:
  - Any push/rebase/merge of a branch other than consolidate/r2-canonical.
  - Any merge of PR #9 (operator action).
  - .agents/**, .codex/**  (the CI contamination guard fails the build if either is tracked).
```

If remediation or the sweep identifies a necessary change outside this list, add the specific file
with a one-line flagged justification in this WO's scope section — do not silently widen.

## Phase A — independent review of the prior seat's WO-0111 and WO-0112

Work the two queued packets exactly as written (their per-finding "closure by property" questions
and fresh probes), with one supersession: after depositing each `result.md`, you fix what you
confirmed rather than handing back.

- `work/review/REV-0031/request.md` — WO-0111 (`git diff 7194f02..4d607da`): the monitoring
  supersession-attribution change and the emergency-reduce re-authorization change.
- `work/review/REV-0032/request.md` — WO-0112 (`git diff ba6be70..194343c`): the exit-preempt
  CREATED-buy stand-down, the protection-open fail-closed gate, and the late-fill terminal-cleanup
  parity change.

For each packet: per-finding evidence (`file:line`, a concrete failing sequence for anything you
refute or confirm), the packet's fresh probes actually run (record harness + outcome), and a verdict
(`ACCEPT` / `ACCEPT-WITH-CHANGES` / `BLOCK`) — the verdict describes the prior seat's change set as
it stands; your own follow-on fixes then land under Phase B. You are free to conclude a prior fix is
wrong in shape and replace it (with citation and preserved-or-stronger pins), not just patch around
it.

## Phase B — remediation

1. Every finding your Phase-A review confirms.
2. Every finding any automated PR review raises on commits you push (triage each: fix what is real,
   refute with pasted evidence what is not — a written refutation in this WO's progress log is the
   record).
3. Every final design choice in the Operator decision queue: evaluate each on the merits, implement
   your recommended shape if it differs, and put the final recommendation (with rationale and
   evidence) in the queue for the operator's ratification.

## Phase C — the recurring-gap-class sweep (the point of this WO)

Four review rounds produced the same **shapes** of gap repeatedly. Close each shape by property.
For every class: enumerate the full surface, verify each cell, pin anything found (red-first,
guard-removal-checked, both stores), and record the completed matrix — including explicit "N/A
because…" cells — in this WO's progress log. An unexamined cell is an open item, not a pass.

- **C1 — Choke-point × property matrix (the "symmetric twin" class).** Guards have repeatedly landed
  at one choke point but not its siblings (flatten handled CREATED buys; envelope-stage/protection
  did not; the exit predicate counted sell orders but not open sell recoveries; declared recovery
  scope but not referenced-order scope). Build the matrix explicitly: choke points = candidate
  dispatch, order mint, submission claim, envelope stage, envelope final claim, manual flatten,
  autonomous protection open, emergency-reduce, cancel paths, recovery ingress, recovery
  resolution, session close. Properties = cross-side exposure (both directions), recovery-aware
  exposure (declared AND referenced scope), candidate/CREATED-order stand-down, single-flight /
  one-active-per-symbol, session/halt gating, quarantine blocking. Verify every cell on both stores.
- **C2 — Store decision-structure parity.** WO-0112 F2 was a branch-condition divergence between
  memory and SQLite (cleanup keyed on the transition in one store, on stored status in the other).
  For every write-path method with a memory/SQLite twin, compare the **decision structure** (branch
  conditions, cleanup triggers, event writes, rollback semantics), not just test outcomes. Pin any
  divergence-prone spot with a parity test that constructs the distinguishing state.
- **C3 — One-shot / consumable state lifecycle audit.** WO-0111's emergency-reduce wedge was a
  single-use grant stranded active by a fail-closed exit path. Enumerate every consumable or
  one-shot state (override grants, submission claims, single-flight rails, cancel/replace budgets,
  quarantine holds) and verify each has a defined, tested path out of **every** non-consuming exit
  (failure, deferral, restart) — no state that only a happy path can release.
- **C4 — Shared-projection scope audit.** WO-0111's monitoring bug fed owner-scoped inputs into a
  single-envelope projection. Audit every call site of the shared projections (store and monitoring)
  for scope mismatches between the selection universe and the projection target set.
- **C5 — Documented-exclusion compensating-control audit.** Several deliberate design exclusions
  (e.g. CREATED not in `MAY_EXECUTE_ORDER_STATUSES`) are safe only because a compensating control at
  another layer covers the excluded case. For each documented exclusion in `app/policy.py`,
  `app/store/core.py`, and the store comments: name the compensating control, verify it exists at
  every relevant choke point, and confirm it is pinned by a test that fails without it.

Where C1–C5 confirm a gap, fix it under Phase-B discipline. Where a cell is sound, the recorded
matrix row with its evidence is the deliverable.

## Phase D — merge-readiness and close-out

- Full gate green at the final HEAD (fresh pasted output for every command in Discipline §3).
- PR #9 CI green on the final push.
- `work/review/REV-0033/request.md` queued: your change-set summary, per-cluster verification
  instructions, and the same evidence standard the prior packets carry — for the independent seat.
- The Operator decision queue delivered as one batched list (this WO's section updated).
- Close-out ships with the work: progress log complete (including the C1–C5 matrices), WO moved to
  `work/completed/keep/`, ledger row appended, docs/INV/ADR/PKL claims current.
- **No merge of PR #9. No push to any other branch.**

## Operator decisions (all ratified YES on 2026-07-19)

1. **WO-0112 F3 targeting — RATIFIED YES** every recovery-free, event-projected CREATED BUY,
   regardless of cached `filled_quantity`. A CREATED scalar is not venue absence and a fill scalar
   is not lifecycle truth; broker identity/open recovery are the actual local-cancel exclusions,
   and projected-CREATED with a concrete broker id remains venue exposure at every SELL choke.
   Evidence: `test_wo0113_primary_remediation.py` and `test_wo0113_safe_local_cancel.py`.
   **Operator ratification: YES (2026-07-19 autonomous-completion mandate).**
2. **WO-0112 F1 shape — RATIFIED YES** audited `None` plus next-tick recomputation when a
   same-symbol BUY is venue-uncertain. Raising would still leave the position without an exit;
   minting immediately can wedge or mis-size it. The durable deferral makes no SELL artifact and
   retries from the later live position. Evidence: protection/primary pins.
   **Operator ratification: YES (2026-07-19 autonomous-completion mandate).**
3. **Append-only missed attribution — RATIFIED YES** `ENVELOPE_FILL_ATTRIBUTED` as a globally
   deduped, non-position-folding repair marker for one immutable order-scoped canonical `FILL` and
   one validated envelope. Every NEW/repair/replay validates the complete contiguous remaining-
   quantity chain; cadence also validates direct-attributed facts from a durable tail checkpoint
   that advances only after a clean batch. Alternative is permanent quarantine/manual accounting
   for every missed bridge. Evidence: attribution file **58 passed** and exact
   conflict/chain/direct/checkpoint mutations.
   **Operator ratification: YES (2026-07-19 autonomous-completion mandate).**
4. **Emergency grant capability — RATIFIED YES** capability-bound reuse/consumption as the
   ADR-003 clarification: reauthorization rechecks all preconditions, creates no second grant, and
   only the explicit emergency path may observe/consume it. Grant, intent, order, and resolution
   remain bound to the same lock-held session; an explicit foreign session is rejected rather than
   coerced. Ordinary flatten stays denied Halted. Evidence: emergency override **20 passed** and
   the Phase-3e corpus.
   **Operator ratification: YES (2026-07-19 autonomous-completion mandate).**
5. **Accepted-submit last-write ownership — RATIFIED YES** an `ENGINE`/`LOCAL`
   `UNKNOWN_RECONCILE_REQUIRED` execution fact whenever accepted-submit recovery ownership cannot
   be written; the ordinary acceptance audit may or may not already have succeeded. It carries the
   exact local/broker identity, folds neither status nor position,
   remains venue exposure at every opposite-side boundary, and is deterministically adopted or
   recovered before later venue work (including across SQLite restart). For an accepted BUY, the
   exact UNKNOWN/open-recovery owner contributes its remaining same-side CAPI exposure once per
   distinct broker identity; fills allocate once across identities and malformed numeric scope
   cannot shrink the referenced order. Either side's final claim refuses its own pre-existing
   broker id/fallback fact. Evidence: fallback **62 passed**, store parity **36 passed**,
   acceptance identity **49 passed**, CAPI **16 passed**, and repair scaling **13 passed**; producer, projection, claim, multiplicity,
   normalization, cache, and repair guard-removal mutations each failed the exact pins. This is
   operator-ratified branch behavior; REV-0033 independent review remains required.
   **Operator ratification: YES (2026-07-19 autonomous-completion mandate).**

## Done-when

- [x] REV-0031 and REV-0032 `result.md` deposited, per-finding evidence + verdicts; every confirmed
      finding remediated (or replaced with a better shape, cited).
- [x] All automated PR-review findings on new commits triaged: fixed or refuted with evidence.
- [x] C1–C5 sweeps executed; matrices with per-cell outcomes recorded in the progress log; every
      confirmed gap fixed with red-first, guard-removal-checked, dual-store pins.
- [x] Full gate + both oracles + hardening gates + scaling gate + AI-OS hygiene green at final HEAD;
      PR #9 CI green.
- [x] `work/review/REV-0033/` queued for the independent seat; no self-certification.
- [x] Operator decision queue recorded as five RATIFIED_YES decisions.
- [x] Close-out shipped with the work (WO moved to completed/keep, ledger row, doc/INV/ADR/PKL flips).
- [x] No merge performed; no branch other than `consolidate/r2-canonical` pushed.

## Progress log

- **[FABLE • FULL • verification: DIRECT • task: WO-0113 remediation and gap-class closure]**

  ```yaml
  fable_gate:
    goal: "Independently review WO-0111/WO-0112, remediate every confirmed gap, close C1-C5 by property, and leave PR #9 merge-ready without merging it."
    assumptions:
      - claim: "The operator's 2026-07-19 autonomous-completion mandate authorizes the named gated surfaces and ratifies all five recorded semantic choices YES."
        status: VERIFIED
        evidence: "Operator decisions and pre-authorizations in the autonomous-completion prompt."
      - claim: "Existing event-log facts are append-only; repair markers may add truth but may not rewrite an old FILL in place."
        status: VERIFIED
        evidence: "INV-076/INV-091 and the dual-store execution-event append paths."
      - claim: "A BUY candidate born or blocked during an active exit-preemption epoch must not revive after that exit; a genuinely new candidate born after terminal convergence is outside that epoch."
        status: VERIFIED
        evidence: "ADR-010 and the WO-0113 primary-remediation epoch pins."
    approach: "Phase A durable findings first; then red-first, dual-store property clusters with guard-removal checks; then C1-C5 matrices and the full final gate."
    alternatives_considered:
      - "Patch only the newest envelope exception path; rejected because ordinary, stale-redrive, direct-SELL, envelope, cancellation, restart, and repair paths share the accepted-ownership invariant."
      - "Treat malformed or uncorrelated acknowledgements as retryable rejection; rejected because the venue call may already have accepted risk."
    out_of_scope:
      - "PD-1 needs-review release valve"
      - "paper-broker backfill verification"
      - "merging PR #9 or pushing any other branch"
    done_when:
      - behavior: "REV-0031/0032 confirmed findings are dispositioned against the frozen implementation SHA."
        test: "Both packet dispositions map every finding to executable evidence without changing request.md or result.md."
        command: "git diff --check"
      - behavior: "Every confirmed C1-C5 and accepted-submit sibling gap is pinned across its relevant producer/consumer/store/restart surface."
        test: "Focused WO-0113, adapter, reconciliation, hardening, oracle, and full-suite gates pass on the final tree."
        command: ".venv\\Scripts\\python.exe -m pytest -q"
      - behavior: "The frozen implementation has green local gates and exact-SHA PR CI, and REV-0033 is queued without self-certification."
        test: "Local/remote SHAs reconcile and work/review/REV-0033/request.md names the frozen implementation SHA."
        command: "git rev-parse HEAD"
      - behavior: "WO lifecycle, ledger, docs, PKL, ratifications, and Git state agree; PR #9 is not merged."
        test: "AI-OS hygiene/scope checks and a clean-tree status pass after the closeout push."
        command: "git status --short --branch"
    blast_radius: "order/fill/envelope/candidate/grant lifecycle behavior on both stores and their tests/docs"
    rollback: "Revert only the additive WO-0113 implementation commit on consolidate/r2-canonical; retain append-only review/evidence records and do not rewrite broker/event truth."
  ```

- **PR #9 exact-head P1 / SCOPE-TRACE-DIAGNOSE CONFIRMED 2026-07-19** - risk HIGH.
  Scope: the primary seam is envelope venue-acceptance finalization in
  `app/reconciliation.py`; the dependency-safe shared fallback and bounded repair tail also touch
  `app/monitoring.py`. Inbound dependencies are the paper adapter, staged order/envelope facts,
  state-store transition/recovery/event APIs, and accepted-event provenance policy. Outbound
  consumers are restart repair, exposure projection, cross-side/same-side gates, BUY CAPI,
  self-claim, and safe-local-cancel. Accepted-submit producers are ordinary candidate BUY,
  direct SELL, protection/manual-flatten SELL, stale-SUBMITTING redrive, envelope initial submit,
  and envelope replace/redrive; no live-trading surface exists or is enabled.

  Trace: a durable envelope child reaches SUBMITTING; the paper venue returns a concrete broker
  ID; the first SUBMITTED write fails; the best-effort audit may itself fail; the retry fails; and
  submit-recovery creation fails. The envelope helper then raises without the canonical
  UNKNOWN_RECONCILE_REQUIRED last-write fact. After restart the broker-accepted child can therefore
  be invisible to ownership consumers. Submit and replace share this same helper. The adjacent
  ingress also accepts whitespace-padded broker IDs, so event, recovery, order, and venue identity
  need not be canonical.

  Diagnose: this is not a store bug or an adapter fault. The earliest causal defect is duplicated
  accepted-ack finalization: ordinary submissions own the canonical fallback in `monitoring.py`,
  while envelope submissions in `reconciliation.py` stop after recovery failure. Moving that
  writer to the lower dependency seam and calling it from both paths closes the producer class
  without a reverse import. Red-first evidence after correcting an initially invalid weekend
  fixture clock: exact envelope selection **14 failed** for only the intended reasons - zero
  fallback facts in the 8 dual-store/audit variants and 2 SQLite restart variants, plus padded
  identity in the 4 dual-store normalization variants. No production code was edited before this
  decisive red.

- **PHASE A COMPLETE 2026-07-19** — deposited `work/review/REV-0031/result.md`
  (`ACCEPT-WITH-CHANGES`) and `work/review/REV-0032/result.md` (`BLOCK`) before any
  production-code remediation. Fresh packet tests passed `10/10`; both requested new scenarios
  passed on memory and SQLite. Adversarial probes confirmed: inert no-stack and active-precondition
  pins; irreparable unattributed envelope fills; unbound ordinary consumption of emergency grants;
  non-durable candidate preemption; claimable nonzero-filled CREATED buys; recovery-unaware local
  cancellation; envelope-stage stale sizing; SQLite raw-status selection divergence; unsafe
  cancellation of the fill-source child; double owner reconciliation; and loss of the injected
  stage clock. The F1 protection `None`+audit+retry design is endorsed; the F3
  `filled_quantity == 0` targeting is rejected in favor of every recovery-free projected CREATED
  BUY. Phase B begins from these recorded findings.

- **PHASE B / CLUSTER A VERIFIED 2026-07-19** - exit-preemption now closes the
  proposal-to-order epoch on both stores: candidate admission refuses while an exit may execute;
  the final candidate-dispatch backstop expires (rather than parks) an active proposal; envelope
  staging defers on order- or recovery-derived venue-uncertain BUY exposure; and a successfully
  staged exit cancels every recovery-free, event-projected CREATED BUY regardless of the cached
  `filled_quantity` scalar. SQLite selection now starts from immutable symbol/side scope rather
  than the raw status cache, and the injected stage clock owns candidate/order companion writes.
  Red evidence before production edits: `pytest -q tests/test_wo0113_primary_remediation.py` =
  `14 failed`. Green evidence after repair: WO-0112 plus WO-0113 focused suite = `20 passed`.
  Guard-removal evidence (each mutation restored by an in-place edit): nonzero-fill filter
  `2 failed`; stage BUY rail `4 failed` across the recovery-owned and SUBMITTING pins; SQLite raw
  status prefilter `1 failed, 1 passed`; candidate-admission rail `2 failed`; terminal dispatch
  expiry `2 failed`; injected-clock threading `2 failed`. Restored focused result: `14 passed`;
  `ruff check` passed and the new test was formatted by ruff. Operator-queue recommendation 1 is
  therefore **replace the `filled_quantity == 0` heuristic with recovery-free projected CREATED**;
  recommendation 2 remains **endorse audited `None` + retry for venue-uncertain protection**.

- **PHASE B / EMERGENCY CAPABILITY VERIFIED 2026-07-19** - emergency reduction is now an
  explicit capability all the way through the facade and `flatten_position`; an ordinary caller
  cannot consume a raw active grant. Reauthorization revalidates every Halted/position/quarantine
  precondition, reuses one still-active grant without stacking, and exactly one authorized outcome
  resolves it. Red baseline: `tests/test_wo0113_emergency_override.py` produced the expected
  dual-store failures before the capability flag was threaded. A later read-only preflight found
  that resolution still committed before its authorized outcome and that SQLite could re-read a
  rollover session while resolving. Resolution now shares the FLAT/EXISTING/CREATE rollback unit
  and the already-decided session on both stores. A final scope audit also bound the resulting
  intent/order/resolution to the lock-held grant session and rejects an explicit foreign session
  instead of silently coercing it. Then-current restored green: **16 passed**; the final file after
  the session/capability sibling pins is **20 passed**.
  Guard removal independently failed the no-capability-consumption, no-stack, single-consumption,
  resolved-grant, rollback, rollover-binding, and foreign-session pins on both stores (**7/7**
  across the final session/capability rails);
  the related Phase-3e/flatten regression slice remained green (**74 passed**).

- **C2 STORE DECISION-PARITY VERIFIED 2026-07-19** - the full twin audit found and closed nine
  distinguishing divergences: memory protection idempotency now projects lifecycle truth; a
  source-less SQLite fill excludes no empty dedupe identity; caller event-id collisions are domain
  errors; audit/execution/recovery payloads share SQLite's established JSON serialization domain;
  session bootstrap survives later control rollback; malformed multi-owner reconciliation is
  deterministically ordered; kill freeze order is explicit; SQLite supersede reports exact lineage
  ambiguity before a foreign obligation; and recovery ingress now gives each concrete
  broker/local identity one owner. Exact replays return the original row without another audit,
  each concrete broker id rebound to another local order fails closed, one local order may own
  multiple distinct concrete broker legs, exact-pair replay is idempotent, and the empty unknown-id
  sentinel is deliberately local-order scoped rather than globally unique. Original distinguishing
  pins were red before each fix and `tests/test_wo0113_store_parity.py` is **28 passed**. Grouped
  guard removal produced **26 exact failures** (14 original parity/kill/supersede, 10 ownership,
  2 empty-sentinel); every branch was restored in place with Ruff/mypy/diff checks green.

- **C3 ONE-SHOT LIFECYCLES VERIFIED 2026-07-19** - an unpriceable stale `SUBMITTING` claim now
  consumes the same durable no-progress cap as broker deferrals. A priceable broker re-drive first
  commits `STALE_SUBMITTING_REDRIVE_STARTED`; if that write fails, the venue call is suppressed, so
  a broken audit path cannot erase progress and cause unbounded resubmission. Broker acceptance is durably
  audited before recovery ownership, repaired before any next-tick venue action and before a
  reconcile gate may lift `ACTIVE`, and reconstructed after SQLite restart without duplicate
  submit/cancel. Existing broker identity suppresses false historical recovery even after terminal
  order state. Startup repair failure stays `REDUCING`. Unexpected candidate-dispatch exceptions
  revert approval, while cleanup failure cannot replace the original exception. The repair carries
  envelope/kind context into the recovery audit. Focused green: **19 passed**. Grouped removal of
  the cap, audit/recovery fail-closed branch, tick/gate/startup repair rails, represented-identity
  skips, adoption/context branches, and cleanup-error preservation produced **15 exact failures**;
  restoration returned **19 passed** and Ruff green; neutralizing the write-ahead reservation
  independently failed **2/2** broker-suppression pins.

  Final gap-class review extended this lifecycle beyond the ordinary audit: whenever recovery
  ownership cannot be written after broker acceptance, one source-faithful
  `UNKNOWN_RECONCILE_REQUIRED` execution fact retains exact ownership whether or not the ordinary
  audit succeeded, blocks opposite-side venue work, and repairs without another submit
  after cadence or SQLite restart. Generic quarantine/SUBMITTED persistence faults now enter the
  same durable paths; cancellation still propagates. Attribution scan/record faults and same-pass
  poison stop cadence after canonical ingestion. Driven reconciliation runs before venue work,
  requires a committed/verified driver write even when kill composes HALTED, and an exhausted query
  budget sets REDUCING then aborts rather than proceeding without parity. A planned inferred-fill
  lookup or append failure likewise forbids parity/ACTIVE classification, verifies REDUCING, and
  stops same-tick venue work. Then-current focused green: lifecycle **44**, monitoring fail-closed
  **20**, fallback/restart **3**. Final file totals after the sibling sweep are monitoring **24**,
  fallback/restart **49**, acceptance identity **49**, CAPI **16**, and repair scaling **13**.
  Producer, exposure,
  repair, early-reconcile, gate, budget, and generic-exception guard removals all failed their exact
  dual-store pins before restoration. The later fallback expansion separately made accepted-SELL
  projection fail **3/3**, the audit-only producer fail **4/4**, and malformed-truth rejection fail
  **8/8**; restoring each guard returned the then-current fallback file to **18/18**, and the final
  file is **49/49**. The final sibling sweep also proved exact accepted-submit multiplicity,
  conservative immutable-order numeric scope,
  one-time fill allocation, self-owned broker/fallback claim refusal, canonical broker-id ingress,
  rollback-safe accepted-fact caches, and bounded repair/index paths on both stores.

- **ACCEPTED-SUBMIT ROOT-CAUSE CLASS CLOSED LOCALLY 2026-07-19** - the exact-head PR finding
  exposed duplicated accepted-ack ownership protocols: ordinary submits had a private
  last-write fallback in monitoring, while envelope submit/replace raised after recovery failure
  with no durable owner. The fallback now lives at the reconciliation dependency seam and every
  acceptance producer uses it. The sibling sweep found and fixed seven additional manifestations:
  blank post-call broker identity was released as a preflight error; fallback-owned stale claims
  could redrive before repair; recovery storage incorrectly forced one concrete broker leg per
  local order; fill-divergence escalation let one leg suppress another; cross-representation
  collisions could bind an order or fallback's broker id to a different local order; and direct
  store callers could persist padded identity aliases; and the concrete Alpaca adapter could turn
  a missing SDK id into `"None"` or a retryable replace error at direct and duplicate-recovery
  exits. The cardinality is now one exact canonical
  local/broker pair per recovery, one local may own multiple concrete legs, each concrete broker id
  is globally exclusive across order/recovery/fallback representations, and each leg survives
  restart and polls/cancels/resolves independently. SQLite rebuilds bounded process-local ownership
  indexes from durable rows on restart. No dependency or schema migration was added.

  Red-first evidence covered envelope submit/reprice double-persistence failure and normalization
  (**14 failed**), malformed post-call ids (**8 failed**), stale fallback redrive (**2 failed**),
  distinct-leg repair/restart (**2 failed**), and exact fill-divergence ownership (**2 failed**).
  Guard removal independently failed fallback creation (**10/10**), producer normalization
  (**4/4**),
  ambiguity classification (**8/8**), stale-redrive coverage (**2/2**), memory/SQLite exact-pair
  cardinality, exact fill-divergence dedupe (**2/2**), and plural CAPI representation (memory failed
  exactly at `200 != 100`; SQLite remained green). The later cross-representation audit separately
  failed ordinary/stale malformed-id classification (**8/8**), global owner checks (**8/8**),
  durable-boundary canonicalization (**4/4**), and SQLite order-owner restart reconstruction
  (**1/1**). The adapter acknowledgement validator was red first and failed **12/12** again when
  removed. Every mutation was restored in place. The accepted-ownership slice is **228/228
  passed**; the complete 12-file WO-0113 corpus plus the legacy timeout-quarantine suite is
  **421/421 passed**. Repository-wide gates remain pending.

- **C4 APPEND-ONLY ATTRIBUTION REPAIR VERIFIED 2026-07-19** - a canonical `FILL` remains
  immutable. If record-first attribution was missed, a globally deduped
  `ENVELOPE_FILL_ATTRIBUTED` marker may apply that one order-scoped, identity-matching fill to one
  envelope; the marker never folds position or order quantity. Only a validated already-attributed
  replay is a no-op. Before every NEW application, repair, or replay, the sequence-ordered
  FILL/marker facts must form one contiguous chain from `qty_ceiling` exactly to stored remaining.
  Malformed, foreign, unscoped, non-FILL, marker-without-fill, and wrong-fill-reference shapes fail
  closed.
  Both stores are pinned for record-first, same-pass terminal repair, inferred-fill repair, and a
  cadence/startup sweep validates direct-attributed and uniquely parented orphan FILLs from a
  durable high-water tail; poison leaves the checkpoint unchanged for restart. Focused green:
  **58 passed**. Making every conflict
  idempotent and suppressing both new/repair application failed the then-current **24/24** exact
  nodes; accepting integer-but-impossible remaining facts independently failed **4/4**; emitting
  the marker as `FILL` independently failed **2/2** position-truth nodes. Neutralizing same-pass,
  inferred, and cadence/startup repair independently failed the new **6/6** nodes. All mutations were
  restored in place. Additional pre-new/pre-repair chain, direct-cadence, tail-seek, and
  no-advance-on-poison mutations failed **10/10** exact dual-store nodes; the file returned green.

- **C1/C5 RAW SELL AND LOCAL-CANCEL BOUNDARIES VERIFIED 2026-07-19** - direct/decomposed
  `MANUAL_FLATTEN` intent cannot bypass Halted, raw sell dispatch rechecks Halted and order- or
  recovery-derived same-symbol BUY exposure, self-heals a refused intent to `EXPIRED`, and on
  success atomically closes candidate and safely-local CREATED BUY epochs. All local CREATED
  cancellation paths delegate one primitive whose proof is: projected `CREATED`, no broker
  identity, and no open unresolved/needs-review recovery. The facade and monitoring use a
  compare-and-set and act on the returned projected state; a concrete broker id on projected
  CREATED and an unrepresented accepted-submit fact remain blocking exposure. Fill cleanup excludes
  the fill source,
  cancels only distinct safe siblings, and reconciles once; session close selects immutable BUY
  scope before projection. Focused green: raw SELL **16 passed**; safe local cancel **24 passed**.
  Concrete-broker CREATED guard removal failed **6/6**
  in addition to the prior raw-SELL **10/10**. Removing locality/CAS/source/close rails failed **18**
  exact cancellation nodes; removing durable audit/execution facts failed **10**; removing rollback
  failed the strengthened raw-row assertion **2/2**. Every edit was restored in place; both files
  and Ruff returned green.

  The final sibling audit extended the same property to the last-write fallback owner: an accepted
  direct SELL cannot be canceled as safely local, and its exact UNKNOWN identity remains in direct
  SELL single-flight at intent mint and final claim even if a corrupt local terminal fact masks the
  order row. Red baseline: **6/6 failed** across memory/SQLite and both later choke points. Removing
  the fallback local-cancel rail failed **2/2** and removing fallback from direct-SELL exposure
  failed **4/4**; both were restored in place and the acceptance-identity file returned green.

- **REGRESSION ADAPTATION VERIFIED 2026-07-19** - the first post-change full run identified only
  obsolete test scaffolding/expectations: synthetic late SELL fills were prepared as terminal
  sources before an exit owned the symbol; candidate tests now preserve the intended downstream
  choke point or assert the stronger admission rail; and terminal-envelope tests distinguish a
  fail-closed fill source from a safely cancelable sibling. No production behavior was relaxed.
  Fresh focused evidence: the three admission/quarantine files **64 passed**; the two hostile
  envelope files **208 passed**; the earlier WO-0019/WO-0034 late-fill adaptations **8 passed**.

- **POST-IMPLEMENTATION PREFLIGHT REMEDIATED 2026-07-19** - a findings-only read-through of the
  then-current final tree found four sibling gap classes (five concrete P1s): a first-and-only
  terminal or inferred fill could miss parent attribution; emergency resolution preceded the
  authorized outcome and SQLite could bind it to a rollover session; recovery ingress could create
  duplicate owners; and a failed stale-redrive audit erased the retry-cap progress. All were
  confirmed, red-pinned, fixed on both stores where stateful, mutation-checked, and included in the
  matrices above/below. Primary follow-up also distinguished the empty broker-id sentinel from a
  concrete venue identity. This is internal preflight evidence only, not the independent REV-0033
  certification.

  A second findings-only gap-class pass then found and remediated the remaining siblings:
  projected-CREATED BUY with concrete broker identity; immutable emergency grant-session scope;
  non-contiguous/masked attribution chains and direct-attributed cadence validation; generic
  quarantine, repair, and SUBMITTED-persist exceptions; same-pass post-ingest marker poison;
  reconcile-driver writes hidden by composed HALTED; ordinary driven-cadence state-write failures;
  exhausted reconcile budget; unbounded full-log attribution scans; and accepted-submit audit plus
  recovery double failure. Each received a red dual-store pin (plus SQLite restart where durable),
  an exact guard-removal failure, in-place restoration, and focused green evidence above. No result
  from these in-process lenses is treated as the independent REV-0033 certification.

  A final read-only adversarial pass found three more property siblings and no others: accepted
  direct-SELL fallback could be locally canceled and disappear from same-side single-flight; the
  two bounded repair consumers could checkpoint each other's checkpoint forever; and global CAPI
  filtered raw order status instead of lifecycle projection. Red-first additions failed **6/6**,
  **2/2**, and **4/4**, respectively, across both stores (the checkpoint case includes SQLite
  reopen). Production now treats fallback as cancel/single-flight ownership, skips checkpoint-only
  transport pages, and bulk-projects lifecycle status for CAPI. Exact in-place guard removals
  reproduced **2/2**, **4/4**, **2/2**, and **4/4** failures before restoration. A separate first
  full-suite run exposed 16 timeout-quarantine fixture failures: the test-only LIMIT order omitted
  its candidate's price and the new final CAPI claim correctly held it. The fixture now carries
  `limit_price=1.0` with an in-body WO citation; the complete timeout file is **45 passed** and no
  production risk rail was relaxed. The nine-file cross-cutting slice is **233 passed**.

- **PHASE C / C1 CHOKE-POINT MATRIX COMPLETE 2026-07-19** - `V M/S` means the cell was
  verified on memory and SQLite; `N/A M/S` states why that choke cannot perform the property.
  Cross-side cells name `SELL->BUY` and `BUY->SELL` separately rather than treating one direction
  as proof of the other. Abbreviated evidence: `primary` =
  `test_wo0113_primary_remediation.py`; `sell` = `test_wo0113_sell_boundary.py`; `cancel` =
  `test_wo0113_safe_local_cancel.py`; `fallback` =
  `test_wo0113_submit_acceptance_fallback.py`; `emergency` =
  `test_wo0113_emergency_override.py`; `monitoring` =
  `test_wo0113_monitoring_failclosed.py`; `recovery` = WO-0108/0110 hostile recovery pins;
  `legacy` = the existing Phase-3/WO-0036 conformance corpus. Every cited WO-0113 test uses
  `any_store` unless it is an explicit SQLite restart pin.

  | Choke point | Cross-side exposure, both directions | Recovery declared + referenced scope | Candidate / CREATED stand-down | Single-flight / one active | Session / Halt | Quarantine |
  |---|---|---|---|---|---|---|
  | Candidate dispatch | V M/S: `SELL->BUY` exit predicate blocks; `BUY->SELL` N/A here (BUY-only choke), covered at SELL mints (`primary`, WO-0110) | V M/S: open SELL recovery matches declared or referenced Order scope (`recovery`) | V M/S: dispatch-time refusal expires the proposal; successful SELL paths expire pending proposals (`primary`, `sell`) | V M/S: symbol/session candidate idempotency plus dispatch CAS (`legacy`) | V M/S: close and control state block BUY dispatch (`legacy`) | V M/S: the shared FILL+explicit-`QUARANTINED` projection prevents the dispatch from minting a BUY (`phase3b` 5/5) |
  | Order mint | V M/S: BUY mint rechecks exit; SELL mint rechecks projected/broker-owned/UNKNOWN BUY exposure (`primary`, `sell`, `fallback`) | V M/S: both direct SELL and BUY exposure helpers include declared/referenced recovery (`sell`, `recovery`) | V M/S: candidate mint closes its own proposal; SELL mint closes same-symbol BUY epoch (`primary`, `sell`) | V M/S: candidate/sell-intent links permit one linked order (`legacy`) | V M/S: BUY controls and SELL Halted rails are lock/transaction local (`sell`, `legacy`) | V M/S: candidate-origin BUY mint consumes the shared FILL+explicit-`QUARANTINED` projection; deliberate reduce-only SELL remains allowed unless ambiguity prevents safe sizing (`phase3b` 5/5, `sell`) |
  | Submission claim | V M/S: final BUY claim sees exits and exact-identity accepted BUY CAPI exposure; final SELL claim sees status, broker-id, recovery, and accepted-UNKNOWN BUY exposure (`primary`, `sell`, `fallback`, identity/CAPI pins) | V M/S: own/sibling open recovery, an order's own concrete broker id or accepted fallback fact, and declared/referenced scope block claims on both sides (`recovery`, identity pins) | N/A M/S: claim never cleans unrelated intent; preceding mint/stage stand-down plus refusal is the compensating control | V M/S: CREATED->SUBMITTING CAS, event projection, and rollback-safe accepted-fact cache make repeated claim idempotent without decoding unrelated UNKNOWN history (`legacy`, repair-scaling pins) | V M/S: BUY claim obeys control/session/risk-limit gates; authorized reduce-only SELL is explicit (`legacy`, CAPI pins) | V M/S: final candidate-origin BUY claim consumes the same shared FILL+explicit-`QUARANTINED` projection under the claim lock/transaction; restart stays blocked with `symbol_quarantined` (`phase3b` 5/5) |
  | Envelope stage | V M/S: `BUY->SELL` status/broker-id/recovery/UNKNOWN rail; `SELL->BUY` N/A at this SELL-only choke, covered by candidate dispatch (`primary`, `sell`, `fallback`) | V M/S: BUY recovery declared/referenced scope pauses stage (`primary`, `recovery`) | V M/S: successful stage expires candidates and cancels safe local CREATED BUYs in one unit (`primary`) | V M/S: one valid envelope action child/budget claim (`legacy`) | V M/S: session phase and Halted checked before/inside transaction (`legacy`) | V M/S: timeout/needs-review/ambiguous lineage pauses stage (`legacy`) |
  | Envelope final claim | V M/S: `BUY->SELL` status/broker-id/recovery/UNKNOWN exposure rechecked after staging; `SELL->BUY` N/A for envelope child, covered by BUY claim (`sell`, `fallback`) | V M/S: exact/sibling recovery and claim uncertainty block (`recovery`) | N/A M/S: final claim refuses rather than mutating siblings; stage/terminal cleanup own stand-down | V M/S: event-owned child and claim CAS prevent double submit (`legacy`) | V M/S: Halted and immutable session/action rails rechecked (`legacy`) | V M/S: timeout/lineage ambiguity refuses claim (`legacy`) |
  | Manual flatten | V M/S: `BUY->SELL` all status/broker-id/recovery/UNKNOWN BUYs block; `SELL->BUY` N/A at SELL-only choke (`sell`, `fallback`) | V M/S: declared/referenced BUY recovery blocks sizing; direct SELL recovery preserves one-exit rule (`sell`, `recovery`) | V M/S: successful flatten cancels safe CREATED BUYs and candidates (`primary`, `legacy`) | V M/S: atomic existing-intent/position decision returns one exit (`legacy`) | V M/S: ordinary flatten denied Halted (`sell`, ADR-003 corpus) | V M/S: unresolved timeout/overfill ambiguity fails closed; reduce-only exit otherwise remains available (`legacy`) |
  | Autonomous protection open | V M/S: `BUY->SELL` defers on status/broker-id/recovery/UNKNOWN exposure with audit/retry; `SELL->BUY` N/A here (`primary`, `fallback`) | V M/S: declared/referenced BUY recovery defers the exit (`primary`) | V M/S: successful open cancels safe CREATED BUYs and proposals (`primary`) | V M/S: active protection intent/order is idempotently returned with projected status (`store-parity`) | V M/S: Halted refuses new protection intent; always-on session policy otherwise permits exit (`legacy`) | V M/S: venue/recovery ambiguity defers; autonomous BUY quarantine does not prevent a safe reduce-only exit (`legacy`) |
  | Emergency reduce | V M/S: same status/broker-id/recovery/UNKNOWN BUY rails as flatten; `SELL->BUY` N/A at reduce-only choke (`emergency`, `sell`, `fallback`) | V M/S: recovery-aware flatten and timeout preconditions rechecked on every authorization (`emergency`) | V M/S: authorized flatten uses the same safe stand-down primitives (`emergency`, `primary`) | V M/S: one reusable active grant, one authorized exit, one resolution (`emergency`) | V M/S: only explicit capability may operate while Halted; grant/outcome share the lock-held session and foreign scope is rejected (`emergency`) | V M/S: unresolved timeout quarantine blocks grant/reuse (`emergency`, Phase-3e pins) |
  | Cancel paths | N/A M/S: cancellation removes exposure and never mints the opposite side | V M/S: local cancel refuses broker identity and unresolved/needs-review recovery; resolved recovery releases (`cancel`) | V M/S: one shared primitive covers direct, envelope, stand-down, and close paths (`cancel`) | V M/S: CANCELED/CANCEL_PENDING replay is idempotent; CAS loses safely to claim (`cancel`, legacy) | V M/S: risk-reducing cancel remains available across session/Halt state (`legacy`) | V M/S: timeout-quarantined order uses targeted reconcile, never blind local cancel (`cancel`, legacy) |
  | Accepted-submit fallback ingress | V M/S: accepted BUY blocks SELL and accepted SELL blocks BUY; every exact local/broker acceptance remains distinct, while BUY scope contributes conservative remaining notional to same-side CAPI (`fallback`, identity/CAPI pins) | V M/S: immutable referenced scope cannot be shrunk by malformed declared quantity/price; exact local/broker identity repairs into normal recovery ownership without a venue call (`fallback`, identity pins) | V M/S: the fallback makes local CREATED cancel ineligible on either side; it cannot be erased before ownership/reconciliation (`identity` cancel pin) | V M/S: same broker identity dedupes, distinct identities remain additive, known fills allocate once, accepted direct SELL remains in single-flight, and either side's own broker/fallback blocks reclaim (`fallback`, identity pins) | V M/S: ingress/repair cannot lift controls; startup gate precedes repair; rollback-safe accepted-fact caches exclude unrelated UNKNOWN history (`monitoring`, repair-scaling pins) | V M/S: uncertainty is an intentional fail-closed hold until exact ownership repair and broker-authoritative resolution (`fallback`) |
  | Recovery ingress | N/A M/S: ingress records existing venue exposure; it cannot mint either side | V M/S: immutable referenced Order scope must match declared symbol/side; both identities remain visible for legacy rows (`recovery`) | N/A M/S: ingress deliberately retains uncertain work; stage/mint/claim rails stand down or refuse around it | V M/S: exact canonical broker/local pair replay is idempotent; one local may own multiple concrete legs, but a concrete id is exclusive across order/recovery/fallback owner kinds and after restart; empty unknown id is local-scoped (`store-parity`, `fallback`) | V M/S: immutable session scope is retained; ingress does not lift Halt (`legacy`) | V M/S: recovery uncertainty feeds quarantine/exposure projections (`legacy`) |
  | Recovery resolution | V M/S: terminal resolution removes the relevant side exposure and allows the opposite side only afterward (`recovery`) | V M/S: resolution facts validate recovery id, claim occurrence, and immutable scope (`legacy`) | N/A M/S: resolution releases ownership; it does not cancel unrelated intent | V M/S: terminal recovery states cannot reopen; duplicate terminal facts validate identity (`legacy`) | V M/S: resolution does not alter control driver/session (`legacy`) | V M/S: only authoritative terminal evidence releases timeout/recovery holds (`legacy`) |
  | Session close | V M/S: closes establishing BUY work while sparing protective/reduce-only CREATED SELLs (`cancel`, session-close corpus) | V M/S: open recovery prevents local cancel and retains the owner; resolved recovery permits cleanup (`cancel`) | V M/S: projection-first candidate and safe CREATED BUY cleanup, exact counts (`cancel`) | V M/S: second close is rejected/idempotently terminal (`legacy`) | V M/S: immutable session scope closes once; no post-close BUY candidate/order (`legacy`) | V M/S: quarantined/recovery-owned work is retained for reconciliation, not silently canceled (`cancel`, legacy) |

- **PHASE C / C2 TWIN-WRITE DECISION MATRIX COMPLETE 2026-07-19** - every public twin and the
  private mutation seams it consumes were compared by predicate, cleanup, emitted facts,
  rollback, and deterministic ordering. `V` means structurally matched after remediation; the
  distinguishing tests are dual-store even where only one backend was deliberately poisoned.

  | Twin write-path inventory | Branch predicates | Cleanup / downstream trigger | Durable facts | Rollback + ordering | Distinguishing evidence / disposition |
  |---|---|---|---|---|---|
  | `initialize`; session bootstrap | same migration/backfill/projection basis and one date session | owner/symbol convergence before use | session-open audit + execution state | bootstrap is prerequisite truth outside a later command rollback; deterministic owner order | V: rollover fault pin; multi-owner pin; startup/restart corpus |
  | watchlist add/arm/remove/set | normalized symbol, existing row, boolean/status validation | no order cleanup | matching audit facts and actors | session bootstrap survives command failure; atomic row+audit | V: code-structure audit plus watchlist/atomicity corpus; no distinguishing divergence found |
  | candidate create/transition/revert approval | session/closed, numeric, exit-preempt, transition CAS | dispatch refusal expires/revert restores only stranded APPROVED | candidate transition/expiry/revert audit | row and facts one unit; injected timestamps | V: `primary`, `lifecycle`, candidate single-flight/approve-revert corpus |
  | sell-intent create/transition | one active symbol, direct/envelope exposure, Halted reason | refusal self-heals PENDING/APPROVED; owner reconciliation | same transition reason/actor/correlation | atomic in both; newest/owner selection deterministic | V: `sell`, sell-intent and hostile-closure corpus |
  | envelope create/transition/supersede/approve | identical owner/scope/direct/foreign/exact-ambiguity precedence | terminal/supersede safe-child cleanup and one owner reconcile | envelope audit + execution vocabulary | one lock/transaction; exact ambiguity precedes foreign obligation | V: hostile supersede distinguishing pin; full envelope transition corpus |
  | envelope fill/stage/final claim | same validation clock, position, projection, recovery, Halted and budget rails | source-excluding terminal cleanup; safe sibling cancel; stage BUY-epoch stand-down | canonical fill, attribution marker, repair checkpoint, action/transition/cancel facts | record + decrement + cleanup atomic; repair checkpoint advances only after the complete selected tail; action order stable | V: `primary`, attribution **58 passed**, `cancel`, WO-0016/19/36 corpus |
  | order creation: candidate/test/sell/protection/flatten | same numeric/risk/cross-side/recovery/session predicates, including concrete broker-owned CREATED, accepted-submit UNKNOWN exposure, and the shared FILL+explicit-`QUARANTINED` projection before candidate-origin BUY mint | safe stand-down at each SELL mint; projection on idempotent return; uncertain accepted BUY is retained | order row + audit/execution lifecycle facts | atomic link/write; memory protection return fixed to projected state; SQLite reopen reconstructs explicit quarantine | V: projection distinguishing pin plus `primary`/`sell`/`fallback`/legacy lifecycle tests and Phase-3b 5/5 |
  | submission claim | same event-projected status, concrete broker identity, accepted-submit UNKNOWN/recovery exposure, current CAPI risk limits, envelope hard rails, and shared FILL+explicit-`QUARANTINED` projection | refusal leaves row unclaimed; explicit quarantine returns `symbol_quarantined`; accepted path owns SUBMITTING; failed recovery ownership leaves a durable UNKNOWN seed whether or not the ordinary audit succeeded | claim execution/audit facts or exact UNKNOWN fallback | CAS/transaction and sequence order; quarantine is reprojected under the deciding lock/transaction and after SQLite restart; deterministic exact-identity fallback dedupe; distinct identities remain additive; fills allocate once; malformed scope is conservative; own identity and same-side direct SELL fallback refuse claim; CAPI projects lifecycle facts rather than raw status | V: claim gates, fallback **62**, store parity **36**, identity **49**, CAPI **16**, stale-CAS, WO-0108/0110 recovery pins, and Phase-3b 5/5 |
  | recovery create/update | declared scope must match referenced order; exact concrete broker/local identity is immutable; empty broker id is absence | owner reconcile on create/resolve; exact replay emits no duplicate audit | recovery row, creation/status/resolution facts with canonical JSON payload | ownership check+insert+facts atomic; claim occurrence deterministic | V: ownership/conflict/sentinel pins, scope-ingress, JSON, restart and terminal-fact corpus |
  | order transition/quarantine/resolve/reconcile | event projection first; common local CREATED eligibility; legal FSM | terminal envelope owner cleanup, timeout resolution, safe local cancel | audit plus execution transition facts | row+both logs atomic; injected transition clock | V: `cancel` including raw rollback; quarantine/reconcile corpus |
  | fill/audit/execution append | identical validation/dedupe/id-collision/JSON domain; complete attribution chain validated in sequence order | fill-only position fold; marker ignored by position; durable readers resume strictly after their high-water mark | append-only canonical records plus bounded repair checkpoints | caller-id conflict is domain error; poison leaves checkpoint stationary; sequence/row order explicit | V: JSON/id/source-less-fill pins; attribution **58 passed**; fill/oracle corpus |
  | kill/buys-paused/reconcile-state controls | boolean/state validation and event-derived precedence | kill freezes every active envelope and cancels only safe staged work; driven reconciliation must durably reach REDUCING before venue actions and cannot proceed on exhausted budget | control + trading-state + envelope facts | session bootstrap outside rollback; SQLite freeze `ORDER BY rowid`; state write is read back before continuation | V: rollover and reverse-unordered-selects pins; monitoring **24 passed**; Phase-3d corpus |
  | emergency grant/resolve/authorize | identical Halted, position, timeout, lock-held current-session, and active-grant reuse predicates; foreign explicit session rejected | authorized outcome consumes once; failure leaves reusable grant | grant/resolution audit + execution facts share the decided session | one atomic capability state; no stacked grant or cross-session outcome | V: emergency **20 passed** and Phase-3e corpus |
  | session close | projection-first BUY scope, owner retention, exact counts | candidate/safe BUY/pre-activation cleanup; protective SELL spared | close/snapshot/transition facts | one atomic close; immutable row order | V: `cancel` session-close distinguisher plus full close corpus |
  | private seams: local cancel, staged cleanup, BUY stand-down, owner reconcile, raw event append, accepted-submit/attribution repair tails | same shared predicates/helpers and exact provenance validation | callers select source exclusions and reconcile exactly once; repair consumers use bounded durable tails and selective exact lookups; checkpoint-only transport is never treated as new repair work | same helper-generated events and checkpoints | callers own rollback; sorted owner/order traversal; checkpoint after complete success only; accepted-fact indexes/caches restore on rollback; idle consumers converge across SQLite restart | V: grouped mutation failures (18, 10, 2, 8, 8, 4, 1), attribution **58 passed**, fallback **62 passed**, store parity **36 passed**, identity **49 passed**, repair scaling **13 passed**, multi-owner and payload pins |

- **PHASE C / C3 CONSUMABLE-STATE MATRIX COMPLETE 2026-07-19** - every failure, deferral, and
  restart exit has either an automatic durable release or an intentional operator/reconciliation
  hold. No row below depends on the happy path as its only release.

  | Consumable / one-shot state | Non-consuming exits audited | Defined path out | M/S evidence |
  |---|---|---|---|
  | Emergency grant | BUY uncertainty, retry, deduped existing/flat outcome, downstream write fault, foreign requested session, session rollover, restart | retain one active grant on deferral; reauthorize with full precondition check; reject foreign scope; consume in the same rollback unit and lock-held decided session as the first authorized outcome | V: emergency **20 passed**, Phase-3e restart/event projection |
  | Submission claim (`CREATED->SUBMITTING`) | price unavailable, broker transient/terminal error, progress-audit failure, accepted broker id but recovery ownership persistence fails with or without a successful ordinary audit, restart | unpriceable durable deferral or priceable write-ahead attempt -> capped needs-review; no durable attempt means no broker call; recovery owner or exact UNKNOWN fallback (plus any successful audit) -> adoption/recovery before next action/ACTIVE | V: lifecycle **44 passed**, fallback audit-only/double-failure pins, stale-submitting/recovery corpus |
  | Candidate approval/dispatch claim | mapped block, unexpected exception, cleanup exception, `asyncio.CancelledError`, process retry | cancellation-shielded cleanup reverts only stranded APPROVED to reusable PENDING; preserve the original exception/cancellation; ORDERED is idempotent | V: lifecycle approval, cancellation-propagation, and approve-revert pins |
  | Candidate/sell-intent/envelope single-flight | stale existing owner, terminal child, foreign/direct/recovery ambiguity | event projection returns active owner or expires/releases it; ambiguity intentionally retains for reconcile/human | V: primary/sell/hostile-closure corpus |
  | Envelope action/tranche budget | validation divergence, transient submit release, stale redrive, cancel/replace refusal, restart | action fact atomically spends budget; transient release redrives; deterministic refusal cancels local child; exhausted budget terminalizes per disposition | V: WO-0019/21/36 engine/redrive/budget tests |
  | Cancel/replace claim | broker failure, late fill, CANCEL_PENDING restart | unchanged row retries; cancel intent reconciles; fills remain authoritative; terminal replay no-op | V: sim-chaos, envelope chaos, cancel file |
  | Timeout quarantine | query failure/not-found/recent ambiguity, generic quarantine-transition failure, `asyncio.CancelledError`, restart | targeted broker query/retry; generic transition failure creates a durable `needs_review` owner; cancellation propagates; only authoritative terminal fact resolves; needs-review is intentional human retention | V: monitoring **24 passed** plus Phase-3c/4 reconciliation corpus |
  | Submit recovery hold | poll/cancel failure, terminal result, malformed scope, accepted-submit fallback seed, restart | cadence retries unresolved; each exact broker acceptance is adopted or converted to recovery without another venue call; terminal fact -> resolved; retry exhaustion -> needs-review; terminal states never reopen; own broker/fallback identity blocks blind reclaim; accepted direct SELL cannot be locally canceled or replaced | V: recovery ingress/terminal/restart, fallback **62 passed**, store parity **36 passed**, identity **49 passed** |
  | Attribution-repair checkpoint | malformed direct attribution, forged or incomplete marker chain, ambiguous lineage, generic repair fault, restart | validate every selected fact and the complete prior chain; append repairs first; advance high-water only after the whole tail succeeds; poison retries from the stationary checkpoint | V: attribution **58 passed**, including tail-seek and swallow/advance mutations |
  | Accepted-submit repair checkpoint | malformed fallback provenance/scope, adoption/recovery write fault, restart, large unrelated UNKNOWN history, alternating idle repair consumers | retain the exact UNKNOWN seed and prior checkpoint; retry before ACTIVE/venue actions; select bounded accepted-fact pages and checkpoint only the completely repaired tail; poison keeps the checkpoint stationary; checkpoint-only pages are skipped without ping-pong writes | V: fallback **62 passed**, monitoring **24 passed**, repair scaling **13 passed** |
  | Driven reconciliation gate/budget | state-write failure, composed HALTED state, budget below the two required calls, planned inferred-fill lookup/append failure | set and verify REDUCING before any venue action; HALTED cannot mask a failed write; exhausted budget or incomplete inference stops the tick before ACTIVE classification/submission | V: monitoring fail-closed and lifecycle pins, including `test_failed_inferred_fill_cannot_be_classified_as_parity` |
  | Protection deferral (`None`) | same-symbol BUY may execute, no priceable snapshot | audited no order/no grant; next tick recomputes from live position after BUY converges | V: `primary` plus protection loop pins; operator-ratified YES on 2026-07-19 |

- **PHASE C / C4 PROJECTION-SCOPE MATRIX COMPLETE 2026-07-19** - selection universe and
  projection target are recorded separately; no caller feeds owner/symbol-wide facts into an exact
  target without an explicit diagnostic projection.

  | Projection / consumer | Selection universe | Projection target and exclusion | Result / evidence |
  |---|---|---|---|
  | Per-order lifecycle | all execution facts for exact `order_id`, sequence ordered | one immutable Order; scalar status ignored when event truth exists | V: event/read-flip corpus and protection idempotent-return pin |
  | Symbol position | all `FILL` events for normalized symbol | one symbol; optional exact self-dedupe exclusion only for overfill pre-state | V: position/fill oracles; source-less SQLite distinguisher |
  | Symbol quarantine projection | memory's complete execution log; SQLite's selected `FILL` + explicit `QUARANTINED` facts | one normalized symbol set shared by the public quarantine list, candidate-origin BUY order mint, and final BUY submission claim; SQLite reopen reconstructs all three consumers | V: Phase-3b dual-store/restart **5/5**; independent admission and claim mutations each failed the SQLite node, and the FILL-only shared-reader mutation failed **3/3** SQLite consumers |
  | Exact envelope obligation | exact envelope plus directly linked lineage neighbours, action children, referenced orders/recoveries | one envelope id; foreign parents diagnosed, never adopted | V: hostile exact-lineage corpus |
  | Owner-lineage obligation | envelopes/actions/orders for one sell-intent identity | one owner; parented known sibling action excluded from exact child ownership | V: WO-0111 supersession tests and REV-0031 probes |
  | Symbol diagnostic obligation | immutable envelope/action/order symbol arms | diagnostic symbol only; never grants cancel authority | V: WO-0109 symbol-only hostile tests |
  | Monitoring fill attribution | validated exact lineage for record-first; bounded canonical FILL/action/marker tail after a durable high-water mark | zero or one envelope; direct attribution and the full sequence-ordered marker chain are validated; same-pass terminal/inferred repair plus cadence/startup replay; ambiguity remains unowned and checkpoint-stationary | V: REV-0031 probes plus attribution **58 passed** |
  | Emergency/trading state | active session control/reconcile/grant execution facts | current session and normalized symbol capability | V: Phase-3d/e and emergency tests |
  | Timeout/quarantine/recovery | exact order id plus declared and referenced immutable scopes | order/symbol exposure; resolved terminal facts excluded from open set | V: C1 recovery pins and cancel eligibility tests |
  | Canonical fill + repair marker | global exact fill dedupe and global derived marker dedupe, selected through a durable bounded tail | one order-scoped canonical fill -> at most one validated envelope; every NEW/repair/replay must continue the exact quantity chain; marker excluded from position; orphan canonical fact remains a restart seed; poison cannot advance the checkpoint | V: attribution **58 passed**; grouped conflict/apply, remaining-fact, marker-as-fill, chain, tail-seek, and swallow/advance mutations failed exactly |
  | Accepted-submit uncertainty | accepted UNKNOWN facts selected from the dedicated rollback-safe accepted-fact cache/index, plus event-projected represented orders, recoveries, and fills | an exact canonical order/open recovery/fallback for one broker id coalesces as one accepted leg rather than releasing exposure; a concrete id cannot move to another local owner kind; distinct broker identities are additive; opposite-side and same-side single-flight hold until ownership/reconciliation, while BUY CAPI uses conservative immutable-order scope and broker-authoritative resolution; known fills allocate once across the aggregate | V: fallback **62**, store parity **36**, acceptance identity **49**, CAPI **16**, repair scaling **13** on both stores plus SQLite restart; producer, projection, repair, self-claim, direct-SELL ownership, multiplicity, canonical-boundary, cross-owner, numeric-scope, raw-status, cache, and no-double-count pins |

- **PHASE C / C5 EXCLUSION-COMPENSATION MATRIX COMPLETE 2026-07-19** - each deliberate exclusion
  has a named compensating control at every relevant choke point; mutation evidence above proves the
  cited pins are not decorative.

  | Deliberate exclusion | Why excluded | Compensating controls | Verified failure pin |
  |---|---|---|---|
  | `CREATED` outside `MAY_EXECUTE_ORDER_STATUSES` | local rows normally have not crossed the venue claim | admission/dispatch/stage epoch closure; common safe local cancel only when there is no broker identity, recovery, or accepted-submit fallback; a broker/fallback-owned CREATED row remains exposure on either side; final claim rechecks after CREATED->SUBMITTING | `primary`, `sell`, `cancel`, `identity`; broker/fallback-owned CREATED pins; raw SELL mutation 10/10, cancel mutation 18, fallback-cancel mutation 2/2 |
  | `FILLED` outside reconcile status resolution | only individual fill facts may change quantity | append/record every fill first; lifecycle status follows event truth and never synthesizes quantity | fill append-only/oracle/hostile completion tests |
  | CREATED envelope children outside venue-working sets | no broker cancel is valid without venue identity | common local-only proof; recovery/claim uncertainty retains owner; redrive and terminal cleanup use exact source exclusions | `cancel` recovery-owned terminal child and CAS race pins |
  | CREATED SELL spared at session close | protective/reduce-only exits remain available after the bell | all SELL mints remain reduce-only, cross-side/recovery/single-flight gated; BUY close selection is projection-first | session-close and sell-boundary tests |
  | Broker identity/open recovery excluded from local cancel | local cancellation cannot prove venue absence | facade/monitoring route to broker cancel or targeted recovery/reconcile; local primitive refuses | `cancel` identity and unresolved/needs-review pins |
  | Autonomous BUY blocked by symbol quarantine; reduce-only SELL not categorically blocked | containment must not prevent lowering a known long position | public listing, candidate-origin BUY order mint, and final BUY claim consume one lock-held FILL+explicit-`QUARANTINED` projection in both stores and after SQLite reopen; SELL sizing uses live position and all cross-side/recovery/timeout rails; ambiguous exits fail closed | Phase-3b exact **5/5**; independent consumer mutations plus FILL-only reader mutation (**3/3** SQLite red); flatten/protection/emergency tests |
  | Terminal envelope excluded from `BREACHED` transition | immutable terminal disposition is historical truth even if a cancel raced a fill | late fill is still recorded/decrements remaining; position overfill quarantine is independent; safe sibling cleanup still runs | WO-0034 late-fill and WO-0112/0113 source-sibling pins |
  | `needs_review` may release one owner monopoly while retaining execution exposure | human review cannot fabricate a working mandate, but broker exposure may remain | stage/claim/flatten/close projections retain recovery/uncertain order exposure by declared and referenced scope | WO-0036 hostile closure and C1 recovery pins |
  | Accepted-submit UNKNOWN outside ordinary order-status sets | local SUBMITTED persistence may have failed after venue acceptance, so no projected status can represent the exposure | accepted BUY blocks SELL and accepted SELL blocks BUY; each exact broker/local identity feeds same-side single-flight, cannot be locally canceled or blindly reclaimed, and accepted BUY contributes conservative remaining CAPI; exact order/recovery/fallback coalesce one leg, distinct acceptances remain additive, fills allocate once, and bounded repair adopts ownership without another submit | fallback/restart, acceptance-identity, CAPI, and repair-scaling producer/projection/repair/local-cancel/self-claim/single-flight/multiplicity/numeric/cache/no-double-count pins |
  | `ENVELOPE_FILL_ATTRIBUTED` excluded from `FILL` and position folding | the marker is a local attribution decision, never a second broker quantity fact | one canonical `FILL` remains the sole position mutation; marker creation/replay validates its exact fill reference and the complete contiguous remaining-quantity chain | attribution **58 passed**; changing the marker into `FILL` failed the exact **2/2** position-truth mutation pins |
  | Facts at or below a repair checkpoint excluded from routine cadence scans | a successfully validated prefix should not make every tick rescan an unbounded append-only log | a checkpoint-free bootstrap walks the existing prefix in bounded 256-event pages; later pages begin strictly after durable high-water; checkpoint-only transport pages are skipped and alternating consumers converge; malformed facts remain visible and retryable | attribution **58 passed** and repair scaling **13 passed**, including positive `after_sequence`, bounded-page, index-use, idle-restart convergence, and stationary-poison pins |

- **RECOVERY CHECKPOINT 2026-07-19 (post-sleep, durable resume point)** — branch/HEAD remain
  `consolidate/r2-canonical` at `8708f585c095222eb706407eb05a1f04d717a37b`; all WO edits are
  present and unstaged, `git diff --check` is clean, and the mutation-residue search found only
  the intentional hardening-gate fixtures. The complete WO-0113 slice is **312 passed** across
  12 files (acceptance identity 41, attribution 58, CAPI 12, emergency 20, lifecycle 44,
  monitoring 24, primary 14, repair scaling 11, safe cancel 24, SELL boundary 16, store parity
  28, fallback 20). The combined late focused set (identity/CAPI/fallback/monitoring/repair) is
  **108 passed**; `mypy app` is green.

  The final accepted-submit sibling sweep is implemented on both stores: malformed numeric owner
  scope cannot shrink referenced exposure; distinct broker acceptances remain distinct while fills
  allocate once; broker ids are normalized once at adapter ingress; a CREATED BUY or SELL with its
  own broker id or fallback fact cannot be reclaimed; and routine uncertainty/CAPI decisions use a
  rollback/restart-safe accepted-fact cache instead of materializing all UNKNOWN history. Initial
  red was **33 failed / 8 passed**; restored file is **41 passed**. Exact edit-in-place mutations
  failed as required: numeric scope 8/8, identity multiplicity 2/2, broker-id normalization 3/3,
  concrete self-claim 8/8, fallback self-claim 8/8, bounded history 4/4. The earlier collision
  validator failed 2/2 when neutered and is restored. Driven inferred-fill persistence is now a
  parity prerequisite; its branch mutation failed 4/4 and restored green. Repair performance
  mutations failed batching 4/4, selective identity reads 2/2, and the memory event-id index 1/1;
  restored `test_wo0113_repair_scaling.py` is 11 passed.

  **Resume sequence:** (1) refresh C1–C5 rows/counts and stale wording for the final identity/cache
  cluster; (2) run Ruff check/format, mypy, import-linter, both conformance oracles, hardening gates,
  scaling gate three times, then the full suite three consecutive times plus coverage; (3) create
  the implementation commit; (4) substitute its SHA, write REV-0031/0032 dispositions, queue
  REV-0033 with genuinely new probes for INV-021/022/023/060/076/081/091/092/093/094, append the
  ledger/Fable DONE, and move this WO to `work/completed/keep/`; (5) make the closeout commit, push
  only this branch, and triage PR #9 CI/automated review. Do not merge.

- **RECOVERY CHECKPOINT 2 2026-07-19 (post-final-audit)** — the three final audit findings are
  red-pinned, fixed on both stores, mutation-checked, and restored. Current WO file totals are
  acceptance identity **47**, CAPI **16**, and repair scaling **13**; together with safe cancel,
  SELL boundary, store parity, fallback, monitoring, and the legacy timeout-quarantine file, the
  latest cross-cutting run is **233 passed**. The complete 12-file WO-0113 slice is **324 passed**;
  timeout quarantine alone is **45 passed**. Ruff check,
  Ruff format check, `mypy app`, import-linter, and `git diff --check` are green. No mutation marker
  remains in production. After the late fixes, both oracles and hardening are green, all three
  scaling runs report `passed: true`, and the consecutive full-suite gate is **3/3 green**
  (397.1, 409.7, and 473.8 seconds; expected skips/xfail only). The interruption-safe coverage
  rerun is also green: **3488 passed, 11 skipped, 1 xfailed** in 717.07 seconds, with the required
  93% branch-coverage gate met at **93.84%** (`pytest --cov=app --cov-branch`, exit 0).

  **Resume sequence now:** (1) run AI-OS hygiene, final static gates, and inspect the final diff;
  (2) commit/push the implementation, wait for PR #9 CI and automated review, and remediate any
  real finding; (3) freeze the final implementation SHA, write
  REV-0031/0032 dispositions and REV-0033 request, ledger/Fable close-out, move this WO to
  `work/completed/keep/`; (4) commit/push close-out and reverify PR #9 without merging.

- **RECOVERY CHECKPOINT 3 2026-07-19 (cross-representation and adapter-boundary late audit;
  supersedes checkpoint 2 for the current uncommitted tree)** — a final read-only root-class audit found four sibling gaps
  after checkpoint 2: ordinary first-submit and stale-redrive malformed post-call ids were still
  retryable/non-quarantined; concrete broker-id exclusivity did not span order, recovery, and
  canonical-fallback owner kinds; store boundaries trusted caller-normalized identity; and the
  Alpaca adapter converted malformed SDK acknowledgements at direct and duplicate-recovery
  submit/replace exits (`None` became `"None"`, while blank replace was retryable). SQLite's
  initial global recovery scan was also replaced with restart-rebuilt, process-local identity
  indexes so the safety check adds no schema migration or unindexed per-create scan.

  Red-first pins failed exactly on both stores. In-place guard removals then failed malformed-id
  classification **8/8**, cross-owner checks **8/8**, canonical boundary normalization **4/4**,
  SQLite order-owner restart reconstruction **1/1**, and adapter acknowledgement validation
  **12/12**. The earlier SQLite recovery-cache restart
  and query-plan mutations also failed their exact pins. Every mutation was restored; the combined
  late orchestration/store guard set is **19/19 green**, the two changed store/fallback files are
  **98/98 green**, and the complete adapter files are **48/48 green**. The six-file
  accepted-ownership slice is **228/228 green** (49 identity + 44 lifecycle + 24 monitoring + 13
  scaling + 36 store parity + 62 fallback), and the complete 12-file WO corpus plus legacy timeout
  quarantine is **421/421 green** (376 + 45). Architecture, reviewer, PKL, and operator docs now
  state all four producer paths, canonical durable boundaries, and cross-representation identity
  exclusivity. Checkpoint 2's static/oracle/scaling/full-suite/coverage results are historical only;
  the newest production and documentation changes require every repository-wide gate to run again.

  **Resume sequence now:** (1) source-freeze review and fresh Ruff/format/mypy/import/static gates;
  (2) both conformance oracles, hardening, three consecutive scaling runs, and AI-OS hygiene; (3)
  three consecutive full-suite runs plus coverage; (4) implementation commit/push and exact-SHA
  CI/automated-review disposition; (5) freeze that SHA, write REV-0031/0032 dispositions, queue
  REV-0033, append ledger/Fable close-out, move this WO to `work/completed/keep/`, and push the
  closeout commit. Do not merge.

- **ACTIVE 2026-07-19** — Codex fetched `origin`, verified clean HEAD
  `8708f585c095222eb706407eb05a1f04d717a37b` on `consolidate/r2-canonical`, read the
  always-on safety contract and this work order, and moved WO-0113 from `work/queue/` to
  `work/active/` before beginning Phase A.

- **QUEUED 2026-07-19 (historical)** — drafted by the Claude seat at the operator's direction: the primary
  implementation seat moves to Codex durably; Claude's WO-0111/WO-0112 stand as pushed, gated work
  whose disposition now belongs to this WO's Phase-A review. Handoff point `194343c` verified: CI
  green (4/4), local full gate reproduced green. Codex subsequently moved this WO to
  `work/active/` and began Phase A, as recorded above.

- **PR #9 FINAL-HEAD P1 REMEDIATED AND REMOTELY VERIFIED 2026-07-19** — automated review
  `PRR_kwDOTCRcJM8AAAABGgvpCw` of exact implementation SHA
  `5ae2c75c1c4700364cf2c7337c9d05c876479b19` reproduced a SQLite-only ADR-001
  containment gap. Candidate admission and final submission claim each queried only `FILL` facts
  before calling `quarantined_symbols()`. An order-level broker overfill can leave position
  positive and express containment only through an explicit `QUARANTINED` fact, so SQLite could
  report `AAPL` quarantined publicly while still minting or claiming an autonomous AAPL BUY;
  memory consumed the full event log and blocked both.

  Red-first evidence was exact: the two new dual-store nodes returned **2 failed / 2 passed**, with
  only SQLite failing (unsafe mint and `claimed` rather than `blocked/symbol_quarantined`). The
  remediation gives each store one lock-held quarantine projection used by candidate admission,
  final claim, and the public list; SQLite selects both `FILL` and `QUARANTINED`. A SQLite close/
  reopen pin proves both gates retain the explicit fact. Restored evidence: dual-store plus restart
  **5/5**, complete Phase-3b **27/27**, relevant 10-file cluster **274/274**, and complete WO/
  quarantine corpus **580/580**. Independent in-place guard removals failed only the SQLite
  admission node **1/1** and claim node **1/1**; reducing the shared reader to FILL-only failed
  **3/3** SQLite/list/restart consumers. Every mutation was restored.

  Fresh unchanged-tree gates after the fix: Ruff check and format (**258 files**), mypy
  (**64 source files**), import-linter (**6 kept / 0 broken**), Codex conformance **61/61**,
  Claude conformance **22 passed / 6 documented skips**, hardening **12/12**, and scaling **3/3**
  with runtime ratios **1.3107 / 0.8181 / 1.0266**, startup elapsed ratios
  **9.4612 / 9.0201 / 8.8985**, and startup selects **9.1022**. The full suite passed three
  consecutive times (**3859 passed, 11 skipped, 1 xfailed; 3871 collected**) with XML suite times
  **336.551s / 379.071s / 385.331s**. Coverage repeated the same zero-failure suite and met the
  configured 93.0% branch floor at **93.50%** in **523.3s**. One post-success Hypothesis
  `StopTest` teardown diagnostic appeared after full run 3, did not affect exit/result, and did not
  reproduce in the isolated property test or coverage rerun. The frozen remediation implementation
  SHA is `9a7af3b08a2d050e324a862d59548ff2da747c48`; GitHub Actions run #482 succeeded on that exact SHA.
  Automated final-head review comment 5018668794 reviewed `9a7af3b08a` and reported no major issues.
  All nine historical review threads are resolved; no merge is authorized.

- **CLOSEOUT DELIVERED / INDEPENDENT REVIEW QUEUED 2026-07-19** — REV-0031 and REV-0032 retain
  their independent `result.md` verdicts and now have separate per-finding dispositions that map all
  twelve accepted findings to the frozen implementation. REV-0033 requests a fresh independent
  spec-first review of `194343c2cd2d5d96d4bf073cfc4e945dd43d71ab..9a7af3b08a2d050e324a862d59548ff2da747c48`
  and instructs that seat to create only `result.md`. INV-002, ADR-001, the review checklist, and PKL
  now name the shared public-list/candidate-BUY-mint/final-BUY-claim quarantine projection. The
  ledger and completion disposition record `PKL_UPDATED` plus `RESULT_SUMMARY_KEPT`. The frozen
  implementation remains unchanged. Closeout SHA `9215b08515d1f55204e7ef902a81477042933687`
  passed GitHub Actions run #484 on Python 3.11 and 3.12; PR #9 remains open, unmerged, mergeable,
  and explicitly operator-gated.

```yaml
fable_done:
  task: "WO-0113 root-cause remediation, recurring-gap closure, and independent-review handoff"
  done_when_results:
    - item: "REV-0031 and REV-0032 findings dispositioned and every confirmed finding remediated"
      status: MET
      evidence: "Separate dispositions map all 12 findings to frozen SHA 9a7af3b08a2d050e324a862d59548ff2da747c48"
    - item: "C1-C5 and accepted-submit sibling sweeps completed with load-bearing dual-store evidence"
      status: MET
      evidence: "580/580 focused; final explicit-quarantine slice 5/5; guard removals and three-node shared-reader mutation failed exactly"
    - item: "Full local verification and exact implementation-head remote gates green"
      status: MET
      evidence: "Three full runs at 3859 passed/11 skipped/1 xfailed; 93.50% coverage; oracles, hardening, scaling, static and AI-OS green; implementation CI #482 SUCCESS; automated final-head review clean; closeout CI #484 SUCCESS"
    - item: "Operator decisions durably recorded"
      status: MET
      evidence: "All five decisions are RATIFIED_YES in the WO, affected ADR/INV/PKL text, and REV-0033 request"
    - item: "Independent review queued without self-certification or merge"
      status: MET
      evidence: "REV-0033 targets the frozen 194343c..9a7af3b range; PR #9 remains open and unmerged"
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  debt_check: "No new product debt; one non-result-affecting Hypothesis teardown diagnostic is disclosed for independent assessment"
  deferred:
    - "Independent REV-0033 result and disposition"
    - "Explicit operator merge of PR #9"
  status: VERIFIED
```
