# WO-0153 cleanup execution outcome

## Status

`PARTIAL CLEANUP - DEFERRED TARGETS REMAIN`

WO-0153 completed every reconcilable documentation, evidence-retention, remote-ref, and local-branch
action within its authority. It does not claim M1 completion, master-landing readiness, or activation
of WO-0150, WO-0151, or WO-0152. The remaining targets are all filesystem-access controlled; no
ACL, ownership, or other bypass was attempted.

## Immutable baseline and remote evidence

- Starting reset SHA: `192056d4e050517ad9b92bfb5f17bf2780e23a47`.
- Pre-deletion documentation baseline: `4c655be69ddb19e844c2c8d1ae077844acab8968`, pushed after
  exact live reset-ref equality before and after the push.
- Every remote deletion below was individually preceded by an exact
  `git ls-remote --heads origin refs/heads/<branch>` SHA match and followed by the same exact query
  returning no ref. No fetch, fetch-prune, remote-prune, remote-tracking-ref deletion, workaround,
  tag, bundle, or replacement archive ref was used.
- A later post-deletion retained-ref query encountered a transient GitHub connection failure. Its
  result is not used as proof; exact deletion absence evidence is retained above and all retained
  refs require a fresh successful check before the final closeout push.

## Completed retirements

### Remote refs deleted with exact live absence

- `archive/consolidate-r2-canonical-codex` @ `accfc2072b7d0997a4b497f5710c9fabd5d86d3e`
- `archive/collab-sol-0001` @ `38180e1d594a961372b5854bfac9f097ac6910b1`
- `freeze/20260715-master-preconsolidation` @ `80250e09be65115b8fc483b2444b297e2b86b2c9`
- `freeze/20260715-pr8-head` @ `22617f4ccf28970d553d5cc65cbffdf42ea4b7cd`
- `freeze/20260715-r2-claude` @ `ba1cea7547e98d03c4216546d5a9069171726698`
- `claude/signal-r4-kickoff-planning-354qc0` @ `95c997f6a1e15375f1022f2d775b8c93ba32a2eb`
- `claude/wo-0148-clean-room-p06lq6` @ `b56ce60043e0609bd73989f8429b573539cedd93`
- `codex/signal-r5a-foundation` @ `b2a5667172a63c201ba7f3062a3a01a6a28018fb`
- `codex/signal-r5b1-producer-ingest` @ `bbc7e96356b582d410105f5d86291b952acd6158`
- `codex/signal-r5b2-operator-auth` @ `d28cabd0d661b9a71bcd50c7a473c7a1fabd67a7`
- `codex/signal-tests-staging` @ `24d3746a35e30f736a6c5e3541720f0d47b0d751`

The local `refs/remotes/origin/*` cache contains no entry for these deleted targets after ordinary
push-delete handling. This observation is not a pruning claim and was not used to decide deletion.

### Local worktrees removed

- `codex/lane2-core` @ `dcefeafd76924b1ae175d797f99786155c917efe`
- `codex/wo-0114-coverage-fix` @ `b4f88c3fe1eb1114965d3281136cf84763111b76`
- `codex/wo-0118` @ `93ed305b563593473ae36ea5730013abb94d1b7b`
- `codex/wo-0126` @ `8c252692c94ee323780964dd157d2690d65a698d`

Each had the expected registered path and tip, no tracked or ordinary untracked change, only
authorized ignored categories, and no process-path hit immediately before the normal Git removal.

### Local branches deleted

Normal deletion (master ancestor):

- `codex/beta-prep-sweep` @ `e5b2dd997ec9ca86112eff8f91f289c06e6d493b`
- `codex/signal-r4-store` @ `b9ebc9ba750633fded4bcc03e7583022e748ee86`
- `codex/signal-r5a-foundation` @ `b2a5667172a63c201ba7f3062a3a01a6a28018fb`
- `codex/signal-r5b1-producer-ingest` @ `bbc7e96356b582d410105f5d86291b952acd6158`
- `codex/signal-r5b2-operator-auth` @ `d28cabd0d661b9a71bcd50c7a473c7a1fabd67a7`

Authorized `git branch -D` after committed integration/supersession proof:

- `codex/lane2-core` @ `dcefeafd76924b1ae175d797f99786155c917efe`
- `codex/wo-0114-coverage-fix` @ `b4f88c3fe1eb1114965d3281136cf84763111b76`
- `codex/wo-0118` @ `93ed305b563593473ae36ea5730013abb94d1b7b`
- `codex/wo-0126` @ `8c252692c94ee323780964dd157d2690d65a698d`

`git worktree prune` was run only for local worktree metadata.

## Measured generated-artifact cleanup

- 42 hash-verified root coverage/JUnit files: `83,334,228` bytes removed.
- REV-0050 captured non-Markdown raw evidence: `2,924,572,432` bytes removed.
- 14 REV-0050 root XML files and two stale goal-baseline files: `4,163,518` bytes removed.
- Exact measured file reclamation: `3,012,070,178` bytes.
- 27 additional approved root cache directories were removed. Their reclaimable byte total was not
  recorded per directory before deletion, so this report intentionally makes no invented byte claim.

The source/test delta from superseded WO-0149 was captured byte-for-byte in
`wo-0149-superseded-partial-delta/`, validated with `git apply --check --binary`, then removed from
active `app/` and `tests/` paths. Its patch and raw copies remain evidence only.

## Deferred targets - environment control

All normal worktree-removal preconditions passed. Git deregistered each of the five roots below but
reported `Directory not empty`; the retained roots have no `.git` marker and later exact removal was
rejected by the filesystem on the named ignored cache. Local fallback branches remain intentionally.

- `codex/lane2-bootstrap` / `.claude/worktrees/codex-lane2-bootstrap` - `.pytest_cache` AccessDenied
- `codex/lane2-docs` / `.claude/worktrees/codex-lane2-docs` - `.pytest_cache` AccessDenied
- `codex/signal-tests-staging` / `.claude/worktrees/codex-signal-tests-staging` - `.pytest_cache` AccessDenied
- `codex/wo-0114` / `.claude/worktrees/codex-wo-0114` - `.pytest_cache` AccessDenied
- `codex/wo-0124` / `.claude/worktrees/codex-wo-0124` - `.pytest-tmp-review-138e389-core` AccessDenied

55 exact immediate root cache directories remain after direct `Remove-Item -Recurse -Force` returned
`UnauthorizedAccessException`; they are all inside the explicit cache allowlist:

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

Ten generated REV-0050 test-fixture files (1,420 bytes total, all SHA-256
`e4be50d7f1b25af9a664f21f8019d86935acfb75557aa4d04505b79d0d6b6d24`) also remain because their
exact pytest-temporary parents rejected direct removal. They are not canonical evidence.

No permission, ACL, ownership, process, remote-tracking, or filesystem workaround was attempted.
