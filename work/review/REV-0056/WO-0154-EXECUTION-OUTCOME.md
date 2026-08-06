# WO-0154 execution checkpoint

## Status

`BLOCKED — UNREGISTERED FULL WORKTREE REMNANTS`

This is an in-flight checkpoint, not a WO closure. No M1-complete, master-landing, successor
activation, application/test, database, runtime, broker, credential, or network claim is made.

## Verified completed filesystem scope

- All 10 fixed REV-0050 fixture roots are absent. Each initially had the required one-file
  SHA-256/142-byte invariant before its leaf and empty directories were removed; the final exact
  roots were independently rechecked as empty non-reparse directories before removal.
- All 55 fixed repository-root cache directories are absent. Every successful one-root pass enforced
  literal direct-child membership, untracked status, Git-ignore status, component containment,
  non-reparse traversal, stable before/after metadata, per-file literal deletion, empty-directory
  bottom-up deletion, and clean Git baselines. No successful cache pass required ACL repair.
- Four cache roots have reclaimed-byte value `UNKNOWN`, not zero: `.pytest_tmp_wo0146_full_10b`,
  `.pytest_tmp_wo0146_full_14`, `.pytest_tmp_wo0146_full_15`, and
  `.pytest_tmp_wo0146_full_16`. A bounded batch reached the environment's 60-second command limit
  after clearing part of that set. Read-only reconciliation then proved the first three absent and
  completed the fourth's remaining 460 empty directories. No byte value is invented.
- The fixture pass required component ACL work because traversal was denied. The exact first-root
  pre/post record is retained in the command evidence: owner `HOMEPC\\CodexSandboxOffline`; before
  access was `OWNER RIGHTS`, `SYSTEM`, and `Administrators` Full Control; the exact root gained only
  `HOMEPC\\CodexSandboxOffline:FullControl`. A prior all-target attempt did not persist its complete
  in-memory per-component ACL log when a postcondition stopped it. This evidence gap is disclosed;
  no unrecorded ACL claim is used to accept the work order.

## Preserved blocker

All five residual paths are non-reparse, present full trees; each exact branch tip matches its
WO-0153 proof. They are intentionally unregistered, not stale registrations:

| Remnant | Local branch @ exact tip | Normal removal result |
|---|---|---|
| `.claude/worktrees/codex-lane2-bootstrap` | `codex/lane2-bootstrap` @ `ea3f75cec2e93a51ca100a8e83a5e658a2630300` | exit 128, not a working tree |
| `.claude/worktrees/codex-lane2-docs` | `codex/lane2-docs` @ `088d9b5a026a1a5d977d834e00c4e73ba5acc9aa` | exit 128, not a working tree |
| `.claude/worktrees/codex-signal-tests-staging` | `codex/signal-tests-staging` @ `24d3746a35e30f736a6c5e3541720f0d47b0d751` | exit 128, not a working tree |
| `.claude/worktrees/codex-wo-0114` | `codex/wo-0114` @ `0a97f51aee11721448dccbf4576c8308bf88f14e` | exit 128, not a working tree |
| `.claude/worktrees/codex-wo-0124` | `codex/wo-0124` @ `3d8015f2bf10fa26ea767d70cab586c9e1b324ca` | exit 128, not a working tree |

`git worktree list --porcelain` contains only the main reset worktree. Each residual contains normal
source/docs content plus multiple ignored cache/temp entries, so the WO-0153 cache-only forced-removal
condition is not met. No forced removal, re-registration, manual recursive deletion, branch deletion,
or `git worktree prune` was attempted after those failures.

## Other evidence

- The documentation-only activation `9d68825fea2568bb13f6b02e1aca23ad0b06cbae` and its two
  focused procedure corrections `10759a205496626d2438b07fea8b9f88c5602cd7` and
  `430326b5927d5db2af12d0fa1d8d554793ac6efb` were each pushed and live-ref verified before the
  relevant filesystem operations.
- The installed `openfiles.exe` facility cannot enumerate local handles because the system object
  list is disabled. It was recorded as unavailable, not as a no-handle result; no process was ended.
- A temporary fixed-input cache helper was hash-inspected (`d288619a4f7af4fa29e8bb04b3fd3f12eabf6ecddf0174a8717bd720fa43d694`), but normal execution policy refused it before it ran. No bypass was used; its exact file and empty temporary directory were then removed.
- Final checkpoint Git status, staged and unstaged tracked deltas, and `git diff HEAD -- app tests`
  are empty.

## Required next authority

Specify a safe disposition for the five unregistered full worktree roots: either an explicitly
authorized re-registration/removal workflow or separately bounded manual full-tree retirement with
fresh path/provenance gates. Do not delete the five local fallback branches unless the matching
remnant has first been safely retired.

## Standard Git repair re-gate — partial result

The authorization limited this pass to standard Git repair/removal and local fallback-branch
retirement after a matching path had safely retired. Its recovery gate passed exactly:

- checkpoint commit, local `HEAD`, and live `refs/heads/codex/arch-reset-2026-07-r1` were all
  `3da1dc381827d4ab7812925d085dce3388c791a7`;
- main-worktree staged, unstaged, ordinary-untracked, and `app`/`tests` deltas were empty;
- `git worktree list --porcelain` listed only the main reset worktree;
- WO-0150, WO-0151, and WO-0152 remained `DRAFT` with implementation authority not granted; and
- the five fallback refs still exactly matched their frozen manifest tips and READY provenance.

Every literal path passed canonical-component containment and root non-reparse checks, but failed
the required authentication gate. For each target, `.git` is absent, no `git worktree list`
registration exists, and no `.git/worktrees/<id>` administrative directory points to the target.
Read-only descendant inspection is also denied at the preserved ignored-cache root. The installed
`openfiles.exe` facility reports that the system object-list flag is disabled, and the attempted
process query reports access denied; neither is presented as a no-handle result.

| Remnant | Branch @ frozen tip | Classification | Standard repair | Branch action |
|---|---|---|---|---|
| `.claude/worktrees/codex-lane2-bootstrap` | `codex/lane2-bootstrap` @ `ea3f75cec2e93a51ca100a8e83a5e658a2630300` | `DEFERRED — METADATA UNAUTHENTICATED` | Not attempted: no authentic marker or admin metadata | Retained |
| `.claude/worktrees/codex-lane2-docs` | `codex/lane2-docs` @ `088d9b5a026a1a5d977d834e00c4e73ba5acc9aa` | `DEFERRED — METADATA UNAUTHENTICATED` | Not attempted: no authentic marker or admin metadata | Retained |
| `.claude/worktrees/codex-signal-tests-staging` | `codex/signal-tests-staging` @ `24d3746a35e30f736a6c5e3541720f0d47b0d751` | `DEFERRED — METADATA UNAUTHENTICATED` | Not attempted: no authentic marker or admin metadata | Retained |
| `.claude/worktrees/codex-wo-0114` | `codex/wo-0114` @ `0a97f51aee11721448dccbf4576c8308bf88f14e` | `DEFERRED — METADATA UNAUTHENTICATED` | Not attempted: no authentic marker or admin metadata | Retained |
| `.claude/worktrees/codex-wo-0124` | `codex/wo-0124` @ `3d8015f2bf10fa26ea767d70cab586c9e1b324ca` | `DEFERRED — METADATA UNAUTHENTICATED` | Not attempted: no authentic marker or admin metadata | Retained |

No target was `REPAIRABLE`, so no `git worktree repair`, `git worktree remove`, forced removal,
`git worktree prune`, branch deletion, or filesystem operation was authorized to run. This is not
a recovery mismatch: the frozen state matched. It is the required safe disposition for
unrepresentable metadata. A later separately authorized manual-retirement procedure would be
needed to alter these five full trees; the present authorization explicitly excluded it.

```yaml
fable_done:
  task: "WO-0154 residual filesystem cleanup checkpoint"
  done_when_results:
    - item: "Ten fixture and 55 root-cache targets absent"
      status: MET
      evidence: "Exact literal postcondition checks with clean Git/app/test delta."
    - item: "Five worktree remnants and matching local branches safely retired"
      status: BLOCKED
      evidence: "All normal exact git worktree remove calls returned not-a-working-tree; cache-only force condition is false."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  debt_check: "Fixture component ACL evidence and four cache byte values are explicitly incomplete; no acceptance claim relies on them."
  deferred:
    - "Safe human-authorized disposition for the five unregistered full worktree remnants."
  status: BLOCKED
```

```yaml
fable_recheck:
  task: "WO-0154 standard Git repair re-gate"
  recovery: "RECONCILED at 3da1dc381827d4ab7812925d085dce3388c791a7"
  result: "PARTIAL_CLEANUP_MANUAL_RETIREMENT_REQUIRED"
  deferred:
    - "Separately authorized manual-retirement procedure for the five full remnants with absent Git metadata."
  scope_check:
    repair_removal_prune_branch_deletion_run: false
    unapproved_operations_run: false
```

## Manual-retirement access-gate outcome

The activation baseline `36c7fa5c71062b4260730eaeb129ef56d5780830` was pushed and exact live-ref
verified before this pass. For each frozen row, the root and named immediate cache child passed
literal canonical containment and non-reparse checks; the matching fallback branch still had its
frozen tip, no worktree registration existed, no `.git` marker existed, and `git ls-files` found no
tracked main-worktree path beneath the root. The cache child could not be listed or read for ACL
data (`UnauthorizedAccessException`), and the one authorized nonrecursive ownership command then
failed without effect: `takeown.exe /F <exact-cache-child>` -> `ERROR: Access is denied`.

| Remnant | Named protected child | Branch @ frozen tip | Manual result | Branch action |
|---|---|---|---|---|
| `.claude/worktrees/codex-lane2-bootstrap` | `.pytest_cache` | `codex/lane2-bootstrap` @ `ea3f75cec2e93a51ca100a8e83a5e658a2630300` | `DEFERRED - ACCESS REPAIR FAILED` | Retained |
| `.claude/worktrees/codex-lane2-docs` | `.pytest_cache` | `codex/lane2-docs` @ `088d9b5a026a1a5d977d834e00c4e73ba5acc9aa` | `DEFERRED - ACCESS REPAIR FAILED` | Retained |
| `.claude/worktrees/codex-signal-tests-staging` | `.pytest_cache` | `codex/signal-tests-staging` @ `24d3746a35e30f736a6c5e3541720f0d47b0d751` | `DEFERRED - ACCESS REPAIR FAILED` | Retained |
| `.claude/worktrees/codex-wo-0114` | `.pytest_cache` | `codex/wo-0114` @ `0a97f51aee11721448dccbf4576c8308bf88f14e` | `DEFERRED - ACCESS REPAIR FAILED` | Retained |
| `.claude/worktrees/codex-wo-0124` | `.pytest-tmp-review-138e389-core` | `codex/wo-0124` @ `3d8015f2bf10fa26ea767d70cab586c9e1b324ca` | `DEFERRED - ACCESS REPAIR FAILED` | Retained |

This gate made no successful ownership or ACL change. Because no complete descendant inventory was
possible, no full-tree `Remove-Item` command was eligible. No `icacls`, worktree prune, branch
deletion, metadata operation, fixture/root-cache revisit, process action, or broader retry ran.
All five targets remain deferred; no fallback branch is eligible for deletion.

```yaml
fable_manual_retirement:
  activation_sha: "36c7fa5c71062b4260730eaeb129ef56d5780830"
  target_count: 5
  terminal_result: "PARTIAL_CLEANUP_ACCESS_REPAIR_FAILED"
  successful_access_repairs: 0
  successful_full_tree_retirements: 0
  successful_branch_retirements: 0
  prohibited_or_broadened_operations: false
  status: REVIEW
```

## Elevated manual-retirement update and serial-batch amendment

The earlier access-gate result is retained as historical environment evidence. It was followed by
two independently rerun exact-root procedures in the user's elevated local PowerShell session:

| Remnant | Fresh complete inventory | Root result | Fallback branch result |
|---|---:|---|---|
| `.claude/worktrees/codex-lane2-bootstrap` | 989 items | `DELETED` | Retained at `ea3f75cec2e93a51ca100a8e83a5e658a2630300`; normal `git branch -d` refused because the branch is unmerged. |
| `.claude/worktrees/codex-lane2-docs` | 983 items | `DELETED` | Retained at `088d9b5a026a1a5d977d834e00c4e73ba5acc9aa`; no branch-delete command ran. |

Local postcondition checks confirm both exact roots are absent, the two fallback refs remain at the
listed frozen tips, the main worktree's tracked/staged/status baselines are clean, and Git registers
only the main reset worktree. No force branch deletion, remote operation, worktree metadata change,
or wider cleanup occurred.

The user then authorized one saved-script serial batch for the three remaining fixed roots:
`.claude/worktrees/codex-signal-tests-staging`, `.claude/worktrees/codex-wo-0114`, and
`.claude/worktrees/codex-wo-0124`. It must contain three explicit literal stages, pause for a
separate exact confirmation at each stage, rerun every per-root gate, and stop before a later stage
if any earlier stage fails. It adds no branch deletion; all fallback refs remain retained. A fresh
documentation-only exact-live baseline is required before that batch starts.

## Final serial-batch result

The user completed every authorized stage in the elevated local PowerShell session:

| Remnant | Fresh complete inventory | Root result | Fallback branch result |
|---|---:|---|---|
| `.claude/worktrees/codex-signal-tests-staging` | 805 items | `DELETED` | Retained at `24d3746a35e30f736a6c5e3541720f0d47b0d751` |
| `.claude/worktrees/codex-wo-0114` | 974 items | `DELETED` | Retained at `0a97f51aee11721448dccbf4576c8308bf88f14e` |
| `.claude/worktrees/codex-wo-0124` | 27,250 items | `DELETED` | Retained at `3d8015f2bf10fa26ea767d70cab586c9e1b324ca` |

Fresh local postcondition verification confirms all five frozen worktree roots are absent, every
fallback ref remains at its exact frozen tip, the main worktree has no tracked/staged/status delta,
and `git worktree list --porcelain` registers only the main reset worktree. No branch deletion,
force deletion, remote operation, metadata action, or broader cleanup occurred.

`WO-0154` therefore has `ROOT-RETIREMENT COMPLETE / BRANCH-DISPOSITION DEFERRED` status. It remains
in `REVIEW` rather than closing because the original close condition requires the five branches to
be absent, and the serial-batch authority intentionally retained them. No implementation or product
authority is implied.
