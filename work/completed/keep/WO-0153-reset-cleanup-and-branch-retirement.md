---
type: Work Order
title: "Reset cleanup: retained WO-0149 evidence and branch retirement"
status: CLOSED
work_order_id: WO-0153
wave: RESET-CLEANUP
model_tier: strong
risk: high
disposition: [PKL_UPDATED, RESULT_SUMMARY_KEPT]
owner: Codex cleanup seat
created: 2026-08-05
branch: codex/arch-reset-2026-07-r1
base_sha: 192056d4e050517ad9b92bfb5f17bf2780e23a47
predecessor: "WO-0149 formal supersession; ADR-020 R2 and ADR-021 R2 ratification"
implementation_authority: AUTHORIZED_2026-08-05
---

# WO-0153 — Reset cleanup: retained WO-0149 evidence and branch retirement

`[FABLE • FULL • verification: DIRECT • task: documentation, evidence, and bounded repository retirement only]`

## Authority and boundary

This work order exists solely under the user's 2026-08-05 cleanup authority. It creates a clean,
committed, pushed post-WO-0149-supersession baseline while preserving evidence and retiring only
the explicitly listed generated material, worktrees, and refs. It does not activate or implement
WO-0150, WO-0151, WO-0152, M2, or any other product work.

The authoritative live remote inventory is exact `git ls-remote --heads origin` queries. Local
remote-tracking refs are cache only: do not run `git fetch --prune`, `git remote prune`, or broadly
delete cached refs; do not use a workaround for an environment restriction. A normal non-pruning
fetch is optional, but only live `ls-remote` may establish remote-ref absence. An exact remote deletion is complete
only when a follow-up exact `ls-remote` query shows the target absent. Any rejected deletion is
`DEFERRED — ENVIRONMENT CONTROL` and leaves its local fallback intact.

## Fable gate

```yaml
fable_gate:
  goal: "Retain all superseded WO-0149 source/test material outside active paths, distill the named branch-only knowledge, and retire only explicitly authorised disposable artifacts and refs."
  assumptions:
    - claim: "WO-0149 is formally superseded by ratified ADR-020 R2 and ADR-021 R2."
      status: VERIFIED
      evidence: "ARCH-RESET-2026-07-RATIFICATION.md and retained WO-0149 record."
    - claim: "WO-0150 through WO-0152 are DRAFT and inactive."
      status: VERIFIED
      evidence: "Their front matter and current PKL posture."
    - claim: "The reset branch local head equals the live exact remote head."
      status: VERIFIED
      evidence: "2026-08-05 exact git ls-remote query: 192056d4e050517ad9b92bfb5f17bf2780e23a47."
  approach: "Use static Git/file checks; capture an exact binary-safe retained patch and raw untracked source/test representations before targeted restoration; then distill, reconcile, commit, push, and retire only individually verified targets."
  out_of_scope:
    - "Application or test execution; SQL/DDL; database initialization; runtime wiring; credentials; Alpaca, broker, or application-network activity."
    - "WO-0150 through WO-0152 activation or implementation; M2; CI workflow changes; master merge; PR; rebase; force-push; git reset --hard; broad git clean; unlisted deletion."
  done_when:
    - behavior: "All retained/removal decisions are traceable to the exact cleanup authority and no active application/test implementation delta remains."
      test: "Static scope, hash, diff, worktree, ref, duplicate-path, cross-reference, PKL, ledger, and manifest checks pass."
    - behavior: "Only individually reverified eligible artifacts, worktrees, and refs are retired."
      test: "Exact live ref checks before and after each remote deletion; exact worktree/process/status checks before each local removal."
  rollback: "Preserve the committed pre-deletion baseline and retained evidence; do not recreate retired refs or delete any additional target after a failed gate."
```

## Allowed paths and actions

- Documentation, PKL, ledger, review evidence, `.gitignore`, and
  `work/queue/ARCH-RESET-2026-07-M1-BRANCH-RETIREMENT-MANIFEST.yaml` only as needed for this
  cleanup authority.
- `work/review/REV-0056/` for the retained WO-0149 source/test delta artifact.
- The eight tracked WO-0149 application/test paths and the two named untracked acquisition paths,
  only to preserve then restore/remove their superseded material.
- The exact cache, generated-evidence, worktree, local-branch, and remote-ref allowlists in the
  user authorization, only after their per-target gates pass.

## Required evidence and stopping conditions

1. Reconcile every main-worktree path before mutation. An unexplained mixed delta stops this work
   order as `BLOCKED — UNRECONCILED WORKTREE`; a local/live reset mismatch stops it as
   `BLOCKED — RESET BRANCH DIVERGED`.
2. Retain the complete superseded WO-0149 source/test delta before restoring/removing any of it.
3. Preserve historical records; make cross-reference repairs as current-posture amendments or
   manifest mappings, never historical-body rewrites.
4. Defer—not guess—any non-ancestor branch whose material value cannot be proved integrated,
   superseded, or distilled.
5. Do not declare M1 complete, master-landing ready, or a successor work order active.

## Closeout

Close only after the final committed reset head equals the live remote reset head, each target is
recorded as deleted, retained, deferred, or blocked, and the final static verification reports no
application/test implementation delta and WO-0150 through WO-0152 still DRAFT/inactive.

## Executed outcome

`PARTIAL CLEANUP - DEFERRED TARGETS REMAIN`. The cleanup's reconcilable scope is complete: the
pre-deletion baseline, retained WO-0149 artifact, canonical documentation/evidence reconciliation,
eleven exact live remote deletions, nine local branch deletions, four complete worktree removals,
and measured generated-file reclamation are recorded in
`work/review/REV-0056/WO-0153-EXECUTION-OUTCOME.md`. Five worktree remnants, 55 root cache
directories, and ten generated fixture files remain only because direct exact deletion returned
`AccessDenied`; no control bypass was attempted. WO-0150 through WO-0152 remain DRAFT/inactive.
