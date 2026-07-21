---
type: Work Order
title: "Envelope disposition cancel convergence + eventing/budget decision (SPEC-06/07, re-cut from WO-0029)"
status: REVIEW
work_order_id: WO-0124
wave: W3-debt closure (re-cut per O-1, AUDIT-0002 F005)
model_tier: strong
fable_mode: FULL
risk: medium
disposition: []
owner: Ameen / Codex implementer
created: 2026-07-20
gated_surface: cancel/replace (venue cancel convergence) — human-gated; independent review required
---

# Work Order: a disposition venue cancel must converge, be evented, and agree with the budget

## Goal

Close WO-0029's verified-open SPEC-06/SPEC-07: every envelope-disposition venue cancel
(expiry `CANCEL_AND_RETURN` AND the stale-data `CANCEL` disposition) gets a bounded
retry/convergence path — a failed cancel can never rest forever — and disposition cancels emit
`envelope_action` events with `envelope_id` provenance, with an explicit ratified decision on
whether they spend the cancel/replace budget (`_BUDGET_ACTIONS` and reality must agree).

## Context packet

- `work/review/FINDING-W3-envelope-lifecycle-eventing-gaps.md` (the authoritative finding)
- `work/completed/WO-0029-envelope-eventing-terminal-semantics.md` (superseded umbrella; B-cluster text)
- `work/review/AUDIT-0002-priorwork/report.md` F005 (what is verified-open vs landed)
- `app/monitoring.py` (`_converge_expired_envelope_cancels` — the WO-0036 arm scoped to EXPIRED
  only; the stale-data CANCEL path is the gap) + `_cancel_envelope_working_order` call sites
- `docs/adr/ADR-010-execution-envelope.md` §5/§6 (budget accounting, event family, refused_stale)
- `tests/test_wo0020_envelope_tick.py` + `tests/test_wo0036_execution_safety.py` (existing pins)

## Allowed paths

```yaml
allowed_paths:
  - app/monitoring.py
  - app/sellside/policy.py # D-0124: reprice-only _BUDGET_ACTIONS alignment
  - app/store/core.py        # only if the convergence predicate belongs in the shared planner
  - app/store/memory.py
  - app/store/sqlite.py
  - app/models.py            # comment-only budget alignment; no field/enum/schema/migration
  - tests/**
  - docs/adr/ADR-010-execution-envelope.md   # budget-decision amendment ships with the change
  - docs/INVARIANTS.md
  - work/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/adapters/**          # convergence uses the existing adapter cancel seam only
  - app/facade/**
  - cockpit/**
```

## Required behavior

- [x] GATE first: re-derive what WO-0036's `_converge_expired_envelope_cancels` already covers
      vs the stale-data `CANCEL` disposition path; do not rebuild what exists.
- [x] Bounded reconcile-driven convergence for every disposition cancel (retry → recovery-ledger
      escalation, mirroring the submit-recovery loop shape); never blind-resubmit, never blind-cancel
      a venue-uncertain order.
- [x] Disposition cancels emit `envelope_action` events carrying `envelope_id` provenance.
- [x] **Operator sub-decision (batch before implementation):** do disposition cancels spend the
      cancel/replace budget? Either answer is implementable; `_BUDGET_ACTIONS` and observed
      behavior must agree, and the ADR-010 budget text is amended to record the choice.
- [x] Red-first, both stores + restart; convergence pins include a failed-cancel-then-crash schedule.

## Fable FULL gate

`[FABLE • FULL • verification: DIRECT • task: WO-0124 disposition-cancel convergence]`

```yaml
fable_gate:
  goal: >-
    Make every expiry or stale-data disposition cancel durable, replayable,
    exact-identity-scoped, bounded, and restart-convergent without charging the
    reprice budget.
  assumptions:
    - D-0124 authorizes the cancel/replace and event-log behavior plus the ADR-010 amendment.
    - A fixed internal retry bound is sufficient; no new config surface is required.
    - The existing adapter cancel seam is idempotent for an exact validated broker identity.
    - Existing recovery storage may be used only as a terminal needs_review escalation latch.
  approach: >-
    Write dual-store/restart tests first; persist non-minting envelope_action cancel
    attempts before venue IO; derive retry state from durable events; revalidate the
    target through the shared obligation projection; escalate at the bound; make
    shared budget accounting reprice-only; then mutation-prove each safety pin.
  out_of_scope:
    - adapter, facade, cockpit, or live/paper venue integration changes
    - new configuration, dependency, field, enum, schema, DDL, or migration
    - widened symbol-only or venue-uncertain cancellation authority
    - reviewer result, disposition, ledger append, CLOSED status, or completed-folder move
  done_when:
    - both disposition paths persist envelope_action cancel provenance
    - failed cancel plus crash converges after restart on both stores where applicable
    - retries are bounded and unresolved exact exposure escalates once to needs_review
    - disposition cancels spend zero replace budget and ADR-010 agrees
    - exact-identity negative controls and required mutations turn red
    - full static, test, import, replay/parity, and coverage gates are green at at least 93 percent
    - REV-0037 request is staged and this work order remains REVIEW in work/active
  blast_radius: cancel convergence, envelope event truth, replace-budget accounting, ADR-010
```

**Activation authority (2026-07-21):** the operator-pasted D-0124 decision expressly ratifies
reprice-only `_BUDGET_ACTIONS` semantics and the matching ADR-010 text. That authority also resolves
the preflight path gap narrowly: `app/sellside/policy.py` is allowed for the constant change and
`app/models.py` for its accounting comment only. It does not authorize any field, enum, config,
schema, migration, adapter, facade, cockpit, or widened cancel-authority change.

## Acceptance criteria

- [x] No disposition failure is silent: direct retries converge or latch the exact exposure for
      human review without reopening automatic cancel authority (pinned).
- [x] Eventing replayable; budget accounting matches the ratified decision; ADR amendment shipped.
- [x] Full gates green; independent review packet REV-0037 staged before beta reliance.
- [x] Fable DONE recorded for the REVIEW handoff. Close-out, disposition, ledger, and move remain
      deferred until the independent result and human disposition.

## Stop conditions

Stop on any need to widen cancel authority beyond validated identity (INV-090 Cluster C rules) —
that is a design change, not this WO. Sequenced AFTER Lane P (WO-0114): shared store/monitoring files.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT, ADR_CREATED]` (amendment).

Not applied at this gate. REV-0037 and human disposition remain outstanding, so WO-0124 stays in
`work/active/` with an empty disposition, no ledger append, no reviewer result, and no completed
move.

## Evidence and Fable handoff

### GATE re-derivation and authority correction

WO-0036 already re-drove `EXPIRED + CANCEL_AND_RETURN` through the exact shared obligation
projection, but it made a one-shot, non-evented stale-data cancel and had no durable attempt state
or bound. WO-0124 retains that projection/cancel seam, adds stale/restart selection from durable
facts, and does not add a symbol-only target, adapter method, venue mode, config, or schema.

The initial RED design proposed an `unresolved` submit-recovery record at exhaustion. Re-derivation
stopped production work: `_recover_unpersisted_submits` polls with `recorded_quantity=0` and models
an otherwise-untracked submit, so giving it a still-tracked canonical disposition order could
duplicate ownership and misclassify fills. The approved correction creates one exact-pair record
directly in terminal `needs_review` on the third failed attempt. Normal tracked-order reconcile
remains the only automatic broker/fill observer; the submit-recovery loop excludes the latch.
Both stores' existing `create_submit_recovery` seam creates record + audit atomically, validates
order scope, dedupes the exact local/broker pair, and writes nothing on identity conflict.

### Red-first evidence

```yaml
evidence:
  - command: "pytest -q tests/test_wo0124_disposition_cancel_convergence.py tests/test_wo0126_replace_budget_single_source.py before production edits"
    result: FAIL
    decisive_output: "14 failed, 4 passed: cancel counted as budget; no pre-IO event; valid cancel provenance poisoned projection; stale failure was forgotten after clear/restart; five direct cancels escaped the requested bound."
  - command: "corrected needs_review recovery-authority pins before production edits"
    result: FAIL
    decisive_output: "2 failed: five direct venue calls were observed instead of three; no terminal needs_review latch existed."
```

### Mutation evidence

Every mutant was applied alone, produced the stated RED, and was immediately restored with a clean
tree before the next mutant:

```yaml
mutations:
  - mutant: "add cancel back to _BUDGET_ACTIONS"
    killed_by: "test_disposition_cancel_does_not_spend_reprice_budget"
    decisive_output: "projected 2 instead of 1"
  - mutant: "bypass append_execution_event before cancel IO"
    killed_by: "test_cancel_event_is_durable_before_venue_io_and_replayable"
    decisive_output: "adapter observer saw no durable event before its call"
  - mutant: "restrict convergence selection to EXPIRED envelopes"
    killed_by: "test_stale_cancel_failure_then_sqlite_restart_converges"
    decisive_output: "reopened ACTIVE stale obligation made zero cancel calls"
  - mutant: "raise direct retry limit from 3 to 4"
    killed_by: "test_direct_cancel_retries_are_bounded_then_escalate_once"
    decisive_output: "four direct calls observed instead of three"
  - mutant: "let cancel enter the canonical child-minting action path"
    killed_by: "test_cancel_event_is_non_minting_and_preserves_exact_child_projection"
    decisive_output: "the exact child became invalid"
  - mutant: "remove cancel broker-order-id comparison"
    killed_by: "test_cancel_event_with_foreign_broker_identity_fails_projection_closed"
    decisive_output: "foreign broker identity projected valid"
  - mutant: "create RECOVERY_UNRESOLVED instead of terminal RECOVERY_NEEDS_REVIEW"
    killed_by: "test_direct_cancel_retries_are_bounded_then_escalate_once"
    decisive_output: "no needs_review record existed; automatic recovery ownership would reopen"
```

### Fresh implementation and gate evidence

```yaml
evidence:
  - command: "focused WO-0124 plus amended WO-0126 budget corpus"
    result: PASS
    decisive_output: "20 passed in 2.4s"
  - command: "WO-0019, WO-0036 safety/hostile, WO-0113 safe-local-cancel, and R2 conformance corpus"
    result: PASS
    decisive_output: "351 passed in 20.9s"
  - command: "pytest --cov=app --cov-branch --cov-report=term-missing"
    result: PASS
    decisive_output: "4029 passed, 11 skipped, 1 expected xfail; 93.05 percent coverage; exit 0 in 359.84s"
  - command: "ruff check . --no-cache; scoped ruff format --check"
    result: PASS
    decisive_output: "All checks passed; 6 changed Python files already formatted"
  - command: "mypy app/"
    result: PASS
    decisive_output: "Success: no issues found in 70 source files"
  - command: "lint-imports --no-cache"
    result: PASS
    decisive_output: "Analyzed 99 files and 485 dependencies; 6 contracts kept, 0 broken"
constraints:
  credentials_used: false
  live_trading_used: false
  adapter_or_facade_changed: false
  config_or_dependency_changed: false
  field_enum_schema_or_migration_changed: false
  reviewer_result_or_disposition_written: false
```

```yaml
fable_fix:
  symptom: "The first escalation design assigned a still-tracked disposition order to the unresolved submit-recovery loop."
  root_cause: "That loop assumes an otherwise-untracked submit and polls with recorded_quantity zero, which is the wrong owner and fill-accounting model for this canonical tracked order."
  fix: "Create one exact-pair terminal needs_review latch on the third failed direct attempt; ordinary order reconcile remains authoritative and automatic recovery excludes the latch."
  regression_test: "test_direct_cancel_retries_are_bounded_then_escalate_once plus test_failed_human_escalation_never_reopens_venue_authority"
  red_green_verified: true
  attempt: 1
```

```yaml
fable_done:
  task: "WO-0124 durable bounded disposition-cancel convergence and budget alignment"
  done_when_results:
    - item: "Expiry and stale-data disposition cancels append exact non-minting provenance before every adapter call"
      status: MET
      evidence: "Dual-store adapter observer plus per-attempt observer are green; append-bypass mutation turns RED."
    - item: "Failed cancel survives clear/restart and direct authority is bounded"
      status: MET
      evidence: "SQLite crash/reopen reaches attempt 2; both stores stop at attempts 1,2,3 and latch exactly once."
    - item: "Projection never broadens cancel authority or mints a child"
      status: MET
      evidence: "Exact broker positive/foreign negative, contiguous-attempt, and non-minting controls are green; two projection mutants turn RED."
    - item: "Disposition cancels spend zero reprice budget and accepted records agree"
      status: MET
      evidence: "Shared policy/facade/restart count is reprice-only; ADR-010 and INV-083/090 carry dated pending-review amendments."
    - item: "Static, import, regression, full-suite, and coverage gates are green"
      status: MET
      evidence: "4029 passed at 93.05 percent; Ruff, scoped format, mypy, and all six import contracts passed."
    - item: "Independent human-gated review is staged without self-certification"
      status: MET
      evidence: "REV-0037 targets frozen semantic range 1af0ae7..a865a95; WO remains REVIEW."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
    live_or_nonpaper_behavior_changed: false
    adapter_facade_cockpit_changed: false
    config_dependency_schema_migration_changed: false
  deferred:
    - "Independent REV-0037 result and author/human disposition"
    - "Ledger append, completion disposition, CLOSED status, and move to work/completed"
    - "Beta reliance on this human-gated cancel/event/ADR change"
  status: VERIFIED
```

Evidence status: **VERIFIED** for the author semantic range and staged review handoff.
**UNVERIFIED** by design: the independent verdict and human disposition. **NEEDS-INPUT:** none for
the implementation; REV-0037 remains the mandatory next gate.
