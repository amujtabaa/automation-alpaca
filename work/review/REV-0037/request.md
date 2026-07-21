---
type: Review Request
rev_id: REV-0037
title: Durable bounded envelope-disposition cancel convergence and reprice-only budget
status: STAGED
reviewer_seat: Claude
targets: [WO-0124, ADR-010, INV-083, INV-090]
human_gated_surfaces: [cancel-replace, event-log-truth, accepted-ADR-text, invariant-record-text]
commit_range: 1af0ae7..a865a95
created: 2026-07-21
---

# Review Request REV-0037 — disposition-cancel convergence

## Reviewer role and output contract

You are the independent Claude review seat, different from the Codex implementer. Read
`AGENTS.md`, `CLAUDE.md`, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`, this request, and only the
curated targets below. Re-derive the behavior from code and fresh failure-capable probes; do not
accept the author's evidence as a verdict.

Produce findings only in `work/review/REV-0037/result.md`; do not edit this request, the work
order, code, tests, ADR-010, invariants, ledger, or another packet. Return exactly one verdict:
`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`. Each finding must identify file:line, why it matters, and
what resolves it. State anything you could not verify. Do not push fixes.

## Gate state and exact review range

WO-0124 changes cancel/replace behavior, append-only execution truth, accepted ADR-010, and
INV-083/090. D-0124 authorizes the narrow change and decides that disposition wind-down cancels
spend zero reprice budget. Independent review remains mandatory before beta reliance.

Review the frozen semantic range `1af0ae7..a865a95`:

- `044c583` — activation and narrow policy/model-comment path authorization
- `d1e8494` — red-first disposition/restart/projection/budget contract
- `0940d53` — corrected terminal human-review recovery authority (RED)
- `e7ea5fd` — monitoring, shared projection, and reprice-only implementation
- `a865a95` — ADR-010 + INV-083/090 amendments and escalation-failure pin

The later review-stage commit contains only this request and work/status evidence; it is excluded
so the packet does not review itself. If integration rewrites the semantic commits, the dispatcher
must replace the frontmatter range with the exact equivalent integrated range before review.

## Authority model to verify, not assume

1. Before **each** `adapter.cancel_order` for an expiry/stale disposition, the engine durably
   appends one `ENGINE`/`LOCAL` `ENVELOPE_ACTION` with `action=cancel`, exact
   envelope/order/broker/session/intent/material identity, disposition, and contiguous attempt.
2. That event is intent/attempt truth only: it is non-minting, never broker-terminal or fill truth,
   never moves position, and never spends the reprice budget.
3. Retry selection comes from the durable event log, including ACTIVE stale-data obligations after
   data clears or SQLite restarts. Cancellation still requires the shared exact-owner projection;
   symbol equality and venue uncertainty never authorize a target.
4. Automatic direct authority ends after three persisted attempts. On the third failed attempt,
   exactly one exact-pair recovery row is born directly `needs_review`, reason
   `envelope_disposition_cancel_exhausted`. No fourth direct cancel occurs even if that escalation
   write faults; a later tick retries only the atomic latch write.
5. The `needs_review` row is a terminal human-visible retention latch, not an `unresolved`
   submit-recovery owner. `_recover_unpersisted_submits` must not poll or cancel it. The canonical
   Order remains tracked by ordinary broker-authoritative reconciliation, which alone ingests its
   fills/status.
6. The pre-existing locally-terminal/broker-open interval branch remains a genuinely untracked
   interval and may retain its existing `unresolved` recovery semantics. Verify the new tracked-
   order latch did not silently change or duplicate that branch.

## Curated targets and boundaries

- Contract and authority: `work/active/WO-0124-envelope-disposition-cancel-convergence.md`
- Venue-call sequencing, retry selection/bound/escalation:
  `app/monitoring.py` (`_persist_disposition_cancel_attempt`,
  `_cancel_envelope_working_order`, `_converge_envelope_disposition_cancels`,
  `_run_one_envelope`)
- Non-minting exact identity: `app/store/core.py::project_envelope_obligation`
- Budget decision: `app/sellside/policy.py::_BUDGET_ACTIONS` and
  `project_envelope_replaces_used`
- Domain comment only: `app/models.py::ExecutionEnvelope.cancel_replace_budget`
- Tests: `tests/test_wo0124_disposition_cancel_convergence.py` and amended
  `tests/test_wo0126_replace_budget_single_source.py`
- Accepted record amendments: `docs/adr/ADR-010-execution-envelope.md` §2/§6 and
  `docs/INVARIANTS.md` INV-083/INV-090
- Incumbent regression truth: `tests/test_wo0019_engine_seam.py`,
  `tests/test_wo0036_execution_safety.py`, `tests/test_wo0036_r2_hostile_closure.py`,
  `tests/test_wo0113_safe_local_cancel.py`, `tests/r2_conformance_oracle.py`

Forbidden/out of scope: credentials; live venue; non-paper mode; adapter/facade/cockpit changes;
new config/dependency/field/enum/schema/DDL/migration; symbol-only or venue-uncertain cancel
authority; writing a disposition/ledger/close-out; reviewing unrelated branch work.

## New/amended invariant accounting and mandatory fresh probes

This range amends **INV-083** and **INV-090**. A rerun of the author's own WO-0124 tests is useful
regression evidence but does **not** satisfy the fresh-probe obligation. Add at least one new
scenario per invariant in `result.md`, with command/outcome and why it can fail.

### INV-083 fresh probes

1. Build a fresh integration scenario whose reprice budget is already exhausted, then invoke an
   approved expiry/stale wind-down cancel. Prove the exact cancel event and adapter call still
   occur while the next reprice remains exhausted. This simultaneously attacks the risk that
   `_BUDGET_ACTIONS`, a consumer, or a stage rail still charges cancel.
2. Instrument the adapter to inspect the store at every one of three failing calls, not merely the
   first. Each call must see its own just-appended attempt; attempt four must never occur. Then
   fault `create_submit_recovery` and run later convergence cadences: they may retry the latch
   write but must issue zero additional venue calls.

### INV-090 fresh probes

1. Create two same-symbol envelope children (or a valid legacy multi-child lineage) and forge a
   cancel fact that names child A's local order but child B's concrete broker id. The projection
   must mark the exact child invalid and monitoring must make zero cancel calls—symbol match is
   insufficient.
2. Poison an otherwise exact cancel sequence independently with a gap (`1,3`), a repeated attempt,
   or a mixed disposition. Prove the projection fails closed and that no new child/obligation is
   minted. Also verify one valid cancel fact leaves the canonical submit/reprice child and
   unresolved cardinality unchanged.

## Required mutation/disproof pass

Independently attempt at least these changes (temporary, restore each):

- count `cancel` in `_BUDGET_ACTIONS`;
- move/skip cancel-event append until after adapter IO;
- ignore persisted ACTIVE stale cancel intents during convergence;
- raise/remove the three-attempt bound or call venue after latch failure;
- create `RECOVERY_UNRESOLVED` instead of terminal `RECOVERY_NEEDS_REVIEW`;
- let `action=cancel` replace/mint the canonical child;
- remove exact broker-id validation or accept symbol-only scope.

If a relevant test/probe stays green under a mutant, report a finding; a test that cannot fail is
a P0 under the repository review rules.

## Author evidence to reproduce skeptically

- Focused amended contract: **20 passed**.
- Incumbent cancel/projection/R2 corpus: **351 passed**.
- Exact CI-form suite: **4029 passed, 11 skipped, 1 expected xfail**, branch coverage **93.05%**.
- `ruff check .`: passed; scoped format: 6 files already formatted.
- `mypy app/`: 70 source files clean.
- Import linter: 99 files / 485 dependencies, 6 contracts kept, 0 broken.
- Seven author mutants described in the work order turned RED and were restored.

Treat skips/xfail as claims to inspect, not automatic acceptance. Verify the changed tests are not
weakened, the event is actually persisted before IO in both stores, and the coverage floor is not
met by excluding the changed code.

## Questions to answer

1. Can any crash, concurrent cadence, dedupe collision, transition failure, or escalation-store
   failure produce an adapter cancel without its exact durable attempt, a fourth direct call, or a
   silent stranded exposure?
2. Can a malformed/missing/foreign/cross-envelope event widen cancel authority, replace the
   canonical child, release the SellIntent owner, or poison a healthy sibling incorrectly?
3. After a stale cancel succeeds and broker-terminal truth arrives, can the ACTIVE envelope resume
   safely, or does the durable event permanently suppress policy? Before terminal truth, can fresh
   data cause policy work to overtake the cancel obligation?
4. Does the `needs_review` latch stay outside automatic submit recovery while ordinary tracked-
   order reconciliation continues to ingest fills exactly once?
5. Do policy enforcement, facade-derived display, model comment, ADR-010, INV-083, and INV-090 all
   express the same reprice-only budget and cancel-attempt truth?
6. Did the range stay within its authorized paths and avoid adapter, facade, cockpit, config,
   dependency, field/enum/schema/migration, live-mode, reviewer-result, disposition, and ledger
   changes?

## Expected output

Write only `work/review/REV-0037/result.md`, findings first and then one verdict. Do not modify
`request.md`. `BLOCK` any unreproducible green claim, non-failing safety pin, pre-I/O truth gap,
fourth direct cancel, automatic recovery ownership of the tracked order, identity widening,
position/fill-truth substitution, or unapproved human-gated/schema/live-surface change.
