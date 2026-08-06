---
type: Work Order
title: "Residual filesystem cleanup: WO-0153 AccessDenied targets"
status: REVIEW
work_order_id: WO-0154
wave: RESET-CLEANUP
model_tier: strong
risk: high
disposition: []
owner: Codex cleanup seat
created: 2026-08-06
branch: codex/arch-reset-2026-07-r1
base_sha: d0bbec8808ddff46a617d919f2208e0841ccd4ab
predecessor: "Closed WO-0153 partial cleanup; exact user authorization for its deferred filesystem targets"
implementation_authority: AUTHORIZED_2026-08-06
---

# WO-0154 — Residual filesystem cleanup

`[FABLE • FULL • verification: DIRECT • task: bounded filesystem cleanup]`

## Goal

Clear only the 70 literal filesystem targets and five local fallback branches deferred by WO-0153, or retain an exact deferred/blocked record when a per-target safety gate fails.

## Context packet

- `AGENTS.md` and the permanent safety core in `CLAUDE.md`.
- `pkl/project/goals.md`.
- `work/completed/keep/WO-0153-reset-cleanup-and-branch-retirement.md`.
- `work/review/REV-0056/WO-0153-EXECUTION-OUTCOME.md`.
- `work/queue/ARCH-RESET-2026-07-M1-BRANCH-RETIREMENT-MANIFEST.yaml`.
- `work/review/REV-0056/WO-0154-HOSTILE-PREFLIGHT.md` and `WO-0154-DRY-RUN.md`.

## Fable gate

```yaml
fable_gate:
  goal: "Use fixed canonical roots and component-wise operations to remove only WO-0153's environment-controlled generated material and its five now-unregistered worktree remnants."
  assumptions:
    - claim: "Local and live reset heads are d0bbec8808ddff46a617d919f2208e0841ccd4ab."
      status: VERIFIED
      evidence: "2026-08-06 exact git rev-parse and git ls-remote --heads origin refs/heads/codex/arch-reset-2026-07-r1."
    - claim: "WO-0153 is CLOSED and these exact targets are its only AccessDenied residuals."
      status: VERIFIED
      evidence: "WO-0153 execution outcome and retirement manifest."
  approach: "Inspect first; reject reparse, tracked, changing, unsafe, or non-allowlisted paths; repair ACL only per exact verified component when required; delete individual verified files and empty directories bottom-up; preserve any target that fails a gate."
  alternatives_considered:
    - "Broad recursive deletion and Git cleanup commands — rejected as outside authority and non-auditable."
    - "Recursive ownership or ACL changes — rejected because they could alter unverified descendants."
    - "Declaring local handles absent — rejected: installed openfiles cannot enumerate local handles in this environment."
  out_of_scope:
    - "Application/test execution, SQL/DDL, database tooling, persistence/runtime wiring, credentials, broker/Alpaca/network activity."
    - "WO-0150 through WO-0152 activation or implementation, M2, master merge, PR, rebase, force-push, remote deletion, remote pruning, Git reset/clean, or any unlisted cleanup."
  done_when:
    - behavior: "Every frozen target and branch has a recorded terminal disposition."
      test: "Exact post-operation absence/status checks and baseline comparison."
      command: "Static Git, path, hash, ledger, disposition, YAML, duplicate-path, and cross-reference checks only."
    - behavior: "No ACL or ownership change reaches an unverified component."
      test: "Per-component owner/ACL-before record, negative reparse check, and exact command record."
      command: "Read-only Get-Item/Get-Acl followed only by exact nonrecursive takeown and icacls when needed."
  blast_radius: "Only the frozen untracked generated targets, five stale worktree remnants, five eligible local fallback branches, and required cleanup records."
  rollback: "Stop on the first unsafe condition for that target; retain existing state and record exact changed ACL components. Do not improvise ACL restoration, recreate artifacts, or broaden a command."
```

Docs-only activation exception: this activation changes no production code; TDD does not apply. The deletion workflow instead uses hostile static and file-level gates before each irreversible operation.

## Frozen literal allowlists

The fixture, root-cache, worktree, and branch lists below are complete. No target may be derived from enumeration.

### Fixture roots (10)

```text
work/review/REV-0050/evidence/adr023-root-final-gate-01/pytest-full
work/review/REV-0050/evidence/adr023-root-final-gate-02/pytest-full
work/review/REV-0050/evidence/adr023-root-final-gate-03/pytest-full
work/review/REV-0050/evidence/adr023-root-final-gate-04/pytest-full
work/review/REV-0050/evidence/adr023-root-final-gate-06/pytest-full
work/review/REV-0050/evidence/full-gate-01/pytest-full
work/review/REV-0050/evidence/full-gate-02/pytest-full
work/review/REV-0050/evidence/full-gate-03/pytest-full
work/review/REV-0050/evidence/py311-oracle-successor-full-01/pytest-temp
work/review/REV-0050/evidence/replay-retention-full-gate-01/pytest-full
```

Each must contain only `test_completed_folder_rejects_0/work/completed/keep/WO-0999-fixture.md`, exactly 142 bytes, SHA-256 `e4be50d7f1b25af9a664f21f8019d86935acfb75557aa4d04505b79d0d6b6d24`.

### Root cache directories (55)

```text
.pytest-tmp-r6a-final-signal-029
.pytest-tmp-r6a-fullcov-015
.pytest-tmp-r6a-fullcov-final-023
.pytest-tmp-r6a-fullcov-final-027
.pytest-tmp-r6a-green-no-scan-025
.pytest_tmp
.pytest_tmp_full_m0
.pytest_tmp_r2_m0
.pytest_tmp_wo0145_full_coverage_authorized_1
.pytest_tmp_wo0145_full_coverage_authorized_2
.pytest_tmp_wo0145_full_coverage_authorized_3
.pytest_tmp_wo0145_r2_authorized_1
.pytest_tmp_wo0145_r2_authorized_2
.pytest_tmp_wo0146_5a89841_readonly_audit_r2
.pytest_tmp_wo0146_full_10
.pytest_tmp_wo0146_full_10b
.pytest_tmp_wo0146_full_14
.pytest_tmp_wo0146_full_15
.pytest_tmp_wo0146_full_16
.pytest_tmp_wo0146_full_authorized_1
.pytest_tmp_wo0146_full_authorized_11
.pytest_tmp_wo0146_full_authorized_12
.pytest_tmp_wo0146_full_authorized_13
.pytest_tmp_wo0146_py311_fix_full_1
.pytest_tmp_wo0146_py311_fix_full_2
.pytest_tmp_wo0146_py311_fix_full_3
.pytest_tmp_wo0146_py311_fix_full_4
.pytest_tmp_wo0146_py311_fix_r2_1
.pytest_tmp_wo0146_py311_fix_r2_2
.pytest_tmp_wo0146_py311_fix_r2_3
.pytest_tmp_wo0146_r2_10
.pytest_tmp_wo0146_r2_11
.pytest_tmp_wo0146_r2_14
.pytest_tmp_wo0146_r2_16
.pytest_tmp_wo0146_r2_7
.pytest_tmp_wo0146_r2_8
.pytest_tmp_wo0146_r2_9
.pytest_tmp_wo0146_r2_authorized_1
.pytest_tmp_wo0146_r2_exact_final
.pytest_tmp_wo0146_r2_final
.pytest_tmp_wo0146_r2_nested_final
.pytest_tmp_wo0147_full_1
.pytest_tmp_wo0147_full_2
.pytest_tmp_wo0147_full_6
.pytest_tmp_wo0147_r2_1
.pytest_tmp_wo0147_r2_2
.pytest_tmp_wo0147_regate5_full_1
.pytest_tmp_wo0147_regate5_r2_1
.pytest_tmp_wo0147_regate6_full_1
.pytest_tmp_wo0147_regate6_full_2
.pytest_tmp_wo0147_regate6_r2_1
.pytest_tmp_wo0147_regate6_r2_2
.pytest_tmp_wo0147_rev0049_fix_full_1
.pytest_tmp_wo0147_rev0049_fix_r2_1
.pytest_tmp_wo0148_r2_1
```

### Worktree remnants and local branches (5)

```text
.claude/worktrees/codex-lane2-bootstrap | codex/lane2-bootstrap | ea3f75cec2e93a51ca100a8e83a5e658a2630300 | .pytest_cache
.claude/worktrees/codex-lane2-docs | codex/lane2-docs | 088d9b5a026a1a5d977d834e00c4e73ba5acc9aa | .pytest_cache
.claude/worktrees/codex-signal-tests-staging | codex/signal-tests-staging | 24d3746a35e30f736a6c5e3541720f0d47b0d751 | .pytest_cache
.claude/worktrees/codex-wo-0114 | codex/wo-0114 | 0a97f51aee11721448dccbf4576c8308bf88f14e | .pytest_cache
.claude/worktrees/codex-wo-0124 | codex/wo-0124 | 3d8015f2bf10fa26ea767d70cab586c9e1b324ca | .pytest-tmp-review-138e389-core
```

The five paths are intentionally **unregistered remnants**: WO-0153's normal removal deregistered each before its exact ignored-cache deletion failed. Registration absence is expected, not a new target.

## Allowed paths

```yaml
allowed_paths:
  - work/active/WO-0154-residual-filesystem-cleanup.md
  - work/completed/keep/WO-0154-residual-filesystem-cleanup.md
  - work/review/REV-0056/WO-0154-HOSTILE-PREFLIGHT.md
  - work/review/REV-0056/WO-0154-DRY-RUN.md
  - work/review/REV-0056/WO-0154-EXECUTION-OUTCOME.md
  - work/queue/ARCH-RESET-2026-07-M1-BRANCH-RETIREMENT-MANIFEST.yaml
  - pkl/project/goals.md
  - pkl/log.md
  - work/ledger.jsonl
```

## Forbidden paths and operations

```yaml
forbidden_paths:
  - app/**
  - tests/**
  - docs/adr/**
  - .github/workflows/**
  - work/queue/WO-0150-*
  - work/queue/WO-0151-*
  - work/queue/WO-0152-*
forbidden_operations:
  - "git clean, git reset, fetch --prune, remote prune, remote branch deletion, or remote-tracking ref cleanup"
  - "wildcards, globbed or dynamic deletion roots, Remove-Item -Path, broad recursive deletion"
  - "recursive takeown/icacls, ACL reset, inheritance propagation, broad-principal grants, process termination"
  - "application/test/SQL/database/runtime/broker/Alpaca/network activity"
```

## Required behavior

1. Canonical-component checks reject repository/evidence-root equality, rooted relative inputs, `.`/`..`, ADS, reparse points, and path-prefix collisions.
2. Before each ownership, ACL, or deletion command, exact-path inspect the root/component, tracked state, handle/activity state, and reparse state.
3. If access repair is necessary, record original owner and accessible ACL; run `takeown.exe /F <exact-current-component>` with neither `/D` nor `/R`, then exact-component `icacls` only for the current verified component and `whoami` principal. When the recorded owner already equals `whoami`, ownership is a documented no-op rather than a redundant command. Never restore ACLs speculatively.
4. Fixtures: walk only the specified chain, verify size/SHA twice, remove its leaf only, then remove every empty directory bottom-up **including the exact fixture root** and never its parent, without recursion.
5. Caches: breadth-first inspect only descendants of one verified literal root; reject reparse, tracked, escaping, unstable, or unexpected material; delete individual files and empty directories bottom-up without recursion.
6. Worktrees: verify stored tip and WO-0153 proof, cache-only condition, status, registration absence, and post-removal absence; use normal exact `git worktree remove` before any recorded cache-only force condition; delete a branch only after path/registration absence.
7. The installed local-handle facility cannot list local opens. Do not claim a negative result; recheck it, recheck content, and defer on a sharing/access conflict. Never terminate a process.

## Acceptance criteria

- [ ] The documentation-only activation is committed/pushed and the exact live reset ref equals its activation SHA before deletion.
- [ ] Every 70 filesystem targets and five branches has a recorded terminal status.
- [ ] No unlisted, tracked, or reparse path is modified.
- [ ] WO-0153 remains historical; records make no M1-complete, master-landing, or successor implementation-activation claim.

## Execution checkpoint — BLOCKED, 2026-08-06

The 10 fixture targets and 55 root-cache targets are now absent. This work order is not closed:
the five remaining paths are full, unregistered worktree remnants. Their exact local branch tips
match the WO-0153 manifest, but `git worktree list --porcelain` contains only the main worktree and
each required normal `git worktree remove <exact-path>` call returned `fatal: '<path>' is not a
working tree`. The recorded cache-only force condition is therefore false. This work order does not
authorize re-registration, manual recursive removal of those full trees, or fallback-branch deletion.

`work/review/REV-0056/WO-0154-EXECUTION-OUTCOME.md` is the current evidence record. A later human
authorization must resolve the unregistered-full-worktree disposition before this work order can
continue or close.

## Execution checkpoint — partial standard-Git repair re-gate

The later bounded authorization permitted only standard `git worktree repair` where the current
filesystem and Git administrative evidence first classified a remnant as `REPAIRABLE`. Recovery
matched checkpoint commit `3da1dc381827d4ab7812925d085dce3388c791a7`, the exact live reset ref,
all five frozen fallback-branch tips, and a clean main worktree. WO-0150 through WO-0152 remained
`DRAFT` with `implementation_authority: NOT_GRANTED`.

All five remnant roots still exist at their exact canonical literal paths, remain under
`.claude/worktrees`, and are non-reparse at the root. None has a `.git` marker, a registered
worktree entry, or a corresponding `.git/worktrees/<id>` administrative entry. Recursive
read-only content inspection stops at the retained ACL-protected ignored-cache directory for each
path; `openfiles.exe` cannot enumerate local handles in this environment and the process query is
access denied. Those are recorded as limitations, not no-handle claims.

Each path is therefore `D — UNSAFE_OR_UNREPRESENTABLE`, specifically
`DEFERRED — METADATA UNAUTHENTICATED`. It is not eligible for `git worktree repair`; no repair,
removal, prune, branch deletion, ACL/ownership change, filesystem deletion, fixture/cache retry,
or other cleanup command was run in this re-gate. The five fallback branches remain retained at
their frozen tips. The historical fixture ACL evidence limitation and four `UNKNOWN` cache-byte
totals remain unchanged. This work order remains `REVIEW` and cannot close under this authority.

## Completion disposition

- [ ] PKL_UPDATED
- [ ] RESULT_SUMMARY_KEPT

## Deletion decision

Retain this work order under `work/completed/keep/` on closure: it records privileged component-wise cleanup and exact residual dispositions.
