---
type: Work Order
title: "Reconcile accepted safety-doc labels with current state (REV-0033 + import/mypy ratchets)"
status: REVIEW
work_order_id: WO-0121
wave: post-R2 beta-prep
model_tier: mid
risk: medium
disposition: []
owner: Ameen (ratifies) / implementer: Codex / from AUDIT-0002 F003 + F004
created: 2026-07-20
gated_surface: accepted ADR + INVARIANTS text (human-gated: ADR change + event-log-truth records)
---

# Work Order: make the accepted safety records describe what actually shipped

> **HUMAN-GATED.** Edits accepted ADRs and `docs/INVARIANTS.md` → requires explicit operator
> approval and an independent cross-model review packet (`REV-00xx`) before beta reliance.
> Every edit is a dated, additive note that makes the record MATCH already-shipped, already-
> reviewed behavior — **zero semantic change, no new decision.** If any edit would change a
> decision rather than record a completed one, STOP and escalate.

## Goal

Remove two classes of stale label from the accepted safety contract: text that still says
WO-0113 behavior is "pending REV-0033" (it is RESOLVED), and ADR-006/007 current-state claims
that describe weaker gates than the ones now live.

## Context packet

- `CLAUDE.md` (human-gated surfaces) + `work/queue/AUDIT-0002-REMEDIATION-BATCH.md`
- `work/review/AUDIT-0002-priorwork/report.md` F003 (exact cited lines) + F004
- `work/review/REV-0033/disposition.md` (RESOLVED — the evidence the labels are stale)
- `docs/adr/ADR-002/003/006/007/008` + `docs/INVARIANTS.md` (cited blocks) + `.importlinter` + `pyproject.toml`

## Allowed paths

```yaml
allowed_paths:
  - docs/adr/ADR-002-timeout-quarantine.md
  - docs/adr/ADR-003-manual-flatten-halted-reducing.md
  - docs/adr/ADR-006-import-boundaries.md
  - docs/adr/ADR-007-mypy-typecheck-gate.md
  - docs/adr/ADR-008-order-status-event-provenance.md
  - docs/INVARIANTS.md
  - pyproject.toml       # F004: remove one contradictory comment only; no config-value change
  - work/**            # review packet, close-out
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**             # not one line of behavior changes here
  - tests/**
  - .github/**
```

## Required behavior

- [x] **F003:** at each cited block (`ADR-002:19,64`; `ADR-003:21,36-37`; `ADR-008:77`;
  `INVARIANTS.md:127,146,422,535,686`), append a dated note that REV-0033 returned
  ACCEPT-WITH-CHANGES and is dispositioned RESOLVED (link `work/review/REV-0033/disposition.md`),
  so the WO-0113 behavior is reviewed-and-accepted, not pending. Preserve the original decision
  history verbatim; do NOT delete the "pending" sentence, annotate it as closed.
- [x] **F004:** add dated amendments recording that the import-linter contract count is 6 (not 5)
  including the pure-sellside contract, and that the mypy grandfather punch-list is fully burned
  down with `warn_unused_ignores = true` live; remove the contradictory "consider flipping" config
  comment. Retain the original baseline text as history.
- [x] **No semantic drift:** every edit is annotation/record. A reviewer must be able to confirm
  each note against `REV-0033/disposition.md`, `.importlinter`, `pyproject.toml`, and a green
  `mypy app/` — not against any new decision.

## Acceptance criteria

- [x] Every cited stale label carries an accurate dated closure note; no decision changed. The
      current-tree scan also closed the identical stale labels on INV-091/092/094.
- [x] `ruff`/`mypy app/`/`lint-imports`/`pytest -q` green (nothing behavioral moved).
- [x] Operator approval recorded and independent review packet REV-0036 staged. Per the batch's
      explicit review-gated exception, its result/disposition remains outstanding and no beta
      reliance is claimed.
- [x] Fable DONE block recorded for the REVIEW handoff; close-out, ledger, disposition, and move
      remain deferred until REV-0036 and human disposition.

## Stop conditions

Stop if any edit would alter a decision, rail, threshold, or invariant meaning rather than record
a completed one — that is a different WO with a real design gate. Rollback: revert; docs-only.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]` (ADR/INV are amended-in-place, not newly created).

Not applied at this gate. REV-0036 and the human disposition remain outstanding, so WO-0121 stays
in `work/active/` with no ledger append or completion move.

## Evidence and Fable handoff

### Red-first contract probe

```text
RED: closure annotations 0/11
RED: ADR-006 lacks six-contract current-state record
RED: ADR-007 lacks completed mypy-ratchet record
RED: pyproject retains contradictory future-step comment
RED: REV-0036 request missing
```

### Fresh semantic and negative-control evidence

```text
PASS: closure annotations 11/11 with canonical verdict/disposition
PASS: ADR-006 six-contract record
PASS: ADR-007 completed-ratchet record
PASS: pyproject stale comment absent; live value unchanged; no ignore_errors assignment
PASS: REV-0036 staged
CONTRACT CHECK PASSED
```

Removing only the inserted WO-0121 blocks from the candidate files reproduces the pre-WO safety
documents exactly:

```text
PASS additive-only: docs/adr/ADR-002-timeout-quarantine.md
PASS additive-only: docs/adr/ADR-003-manual-flatten-halted-reducing.md
PASS additive-only: docs/adr/ADR-008-order-status-event-provenance.md
PASS additive-only: docs/INVARIANTS.md
PASS appended-current-record-only: docs/adr/ADR-006-import-boundaries.md
PASS appended-current-record-only: docs/adr/ADR-007-mypy-typecheck-gate.md
PASS pyproject exactly one stale-comment deletion
ADDITIVE RECORD PROOF PASSED
```

```text
git diff --name-only eab9e57 | python .ai-os/scripts/check_work_order_scope.py work/active/WO-0121-safety-doc-label-reconciliation.md
SCOPE CHECK PASSED
Changed-path negative control: zero app/, tests/, or .github/ paths.
git diff --check eab9e57: PASS
pyproject.toml numstat: 0 insertions, 1 deletion; diff is only the stale comment.
```

### Fresh live-gate evidence

All commands used the repository's Python 3.12 virtual environment; cache/scratch outputs were
disabled or directed to OS temp.

```text
ruff check . --no-cache
All checks passed!

mypy app/ --cache-dir %TEMP%\codex-wo0121-mypy-cache
Success: no issues found in 64 source files

lint-imports --no-cache
Contracts: 6 kept, 0 broken.

python .ai-os/scripts/check_pkl.py pkl
PKL CHECK PASSED
python .ai-os/scripts/check_work_order_disposition.py
DISPOSITION CHECK PASSED
python .ai-os/scripts/check_ledger.py
LEDGER CHECK PASSED
python .ai-os/scripts/check_install.py
INSTALL CHECK PASSED
python .ai-os/scripts/check_fable_done.py work/active/WO-0121-safety-doc-label-reconciliation.md
FABLE CHECK PASSED

pytest .ai-os/scripts/tests/test_phase3_checks.py -q -p no:cacheprovider --basetemp %TEMP%\codex-wo0121-phase3
.................                                                        [100%]

pytest -q -p no:cacheprovider --basetemp %TEMP%\codex-wo0121-full
100%; exit 0 in 322.1s (11 skipped, 1 expected xfail; zero failures)
pytest --collect-only -q -o addopts= -p no:cacheprovider --basetemp %TEMP%\codex-wo0121-collect
3873 tests collected in 2.34s; exit 0
Derived fresh full result: 3861 passed / 11 skipped / 1 xfailed.
```

```yaml
fable_gate:
  task: "WO-0121 annotation-only safety-record reconciliation and REV-0036 staging"
  mode: FULL
  assumptions:
    - "The ULTRA batch assignment is operator approval for exactly the annotation-only WO contract."
    - "REV-0033 disposition is the sole authority for the ACCEPT-WITH-CHANGES / RESOLVED gate-state record."
    - "Live .importlinter and pyproject.toml plus fresh commands are the current-state truth for ADR-006/007 annotations."
  out_of_scope:
    - "Any ADR or invariant semantic change"
    - "Application, test, CI, event-vocabulary, threshold, or configuration-value changes"
    - "Independent REV-0036 result, disposition, ledger close-out, or beta reliance"
  done_when: "Historical text is preserved, every stale current-tree label is annotated, ratchet records match live gates, the config change is one comment deletion, and REV-0036 is staged with fresh failure-capable evidence."
  red_evidence: "The five-clause pre-edit probe failed on all missing records and the absent packet."
```

```yaml
fable_fix:
  symptom: "F004 required deleting one contradictory pyproject.toml comment, but the WO allowed-path list omitted pyproject.toml."
  root_cause: "The drafted scope listed the accepted record files and work packet but omitted the evidence/config file named by its own required behavior."
  fix: "Added a narrow allowed-path entry authorizing only that comment deletion; no configuration value changed."
  regression_test: "The pre/post comparison proves pyproject.toml has exactly 0 insertions and 1 deletion: the stale comment."
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "The current-tree scan found three additional WO-0113 pending labels at INV-091, INV-092, and INV-094 beyond AUD2-F003's five invariant anchors."
  root_cause: "The audit anchor list reflected an earlier/currently incomplete set of WO-0113-labeled invariant blocks."
  fix: "Applied the identical dated record-only annotation to all eight current invariant blocks, without changing any rule, rationale, or pin."
  regression_test: "The closure checker requires 11 total ADR/INV block annotations and the subtractive byte comparison reproduces the pre-WO INVARIANTS file exactly."
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "The first static batch could not invoke lint-imports because the isolated shell PATH did not expose the console script."
  root_cause: "The isolated worktree shell was using system Python 3.14 rather than the repository's Python 3.12 virtual environment."
  fix: "Re-ran every static gate explicitly through the repository .venv and invoked its lint-imports.exe with cache disabled."
  regression_test: "Ruff passed, mypy found no issues in 64 files, and import-linter reported 6 kept / 0 broken."
  red_green_verified: false
  attempt: 1
```

```yaml
fable_done:
  task: "WO-0121 annotation-only safety-record reconciliation and REV-0036 staging"
  done_when_results:
    - item: "Every current WO-0113 pending label has an accurate dated closure record"
      status: MET
      evidence: "11/11 annotations carry ACCEPT-WITH-CHANGES, RESOLVED, and the canonical disposition link."
    - item: "ADR-006/007 describe the stronger already-shipped import and mypy gates"
      status: MET
      evidence: "Fresh import-linter is 6 kept/0 broken; mypy is clean across 64 source files; warn_unused_ignores remains true."
    - item: "No accepted decision or invariant meaning changed"
      status: MET
      evidence: "Subtracting inserted blocks reproduces all six pre-WO safety documents byte-for-byte; pyproject has one comment deletion."
    - item: "Required local and governance gates are green"
      status: MET
      evidence: "Ruff, mypy, import-linter, full 3,873-test suite, collect-only, scope, PKL, disposition, ledger, install, and diff checks passed."
    - item: "Independent review is staged without self-certification"
      status: MET
      evidence: "REV-0036 targets eab9e57..64886f9 for the Claude seat; WO-0121 remains REVIEW."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  deferred:
    - "Independent REV-0036 result and disposition"
    - "Human disposition and beta reliance"
    - "Ledger append, completion disposition, and move to work/completed"
  status: VERIFIED
```

Evidence status: **VERIFIED** for the annotation-only semantic range and staged packet.
**UNVERIFIED** by design: the independent correctness verdict and human disposition.
**NEEDS-INPUT:** none for WO-0121. **P0:** none observed.
