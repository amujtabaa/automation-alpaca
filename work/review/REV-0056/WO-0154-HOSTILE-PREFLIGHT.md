# WO-0154 hostile preflight

`[FABLE • FULL • verification: DIRECT • task: residual cleanup preflight]`

## Result

`ACCEPT — P0=0, P1=0`

This is a documentation-only, pre-mutation review of the frozen WO-0154 procedure. It authorizes no deletion by itself; the activation commit and exact live-ref equality remain required.

## Recovery evidence

- Local `HEAD`: `d0bbec8808ddff46a617d919f2208e0841ccd4ab`.
- Exact live query of `refs/heads/codex/arch-reset-2026-07-r1`: the same SHA after the first non-mutating query encountered a transient network failure and the one permitted retry succeeded.
- Unstaged and staged tracked deltas: empty. The sole status entries are the ten known untracked fixture leaves.
- WO-0153 is `CLOSED`; its declared completed/deferred counts and all five local fallback tips match its execution outcome and manifest. WO-0150 through WO-0152 remain `DRAFT`/inactive.

## Adversarial checks

| Challenge | Result | Evidence |
|---|---|---|
| Fixed count altered or target silently added | PASS | 10 fixture roots, 55 root-cache roots, 5 remnant/branch mappings; all are literal lists copied from WO-0153 records. |
| Root, parent, prefix collision, wildcard, rooted-relative, `.`/`..`, or ADS target | PASS | Canonical-component walker rejects equality and unsafe segments before any operation; direct-child assertion applies to all root caches. |
| Reparse traversal | PASS | All 70 current roots were exact-path probed as `NO_REPARSE`; every future descendant is rechecked before ACL or descent. |
| Tracked-file deletion | PASS | `git ls-files -- <exact-root>` returned zero for every fixture/cache root; status baseline contains only the ten allowlisted fixture leaves. |
| Changed/unstable target | PASS at preflight | Immediate roots are directories; live file/hash and re-enumeration checks are repeated immediately before each deletion. |
| Branch/worktree mismatch | PASS | Five local tips exactly match manifest. `git worktree list --porcelain` contains only the main worktree, which agrees with WO-0153's stated **unregistered-remnant** condition. |
| Recursive ACL/deletion or broad principal | PASS | Procedure permits exact-component `takeown`/`icacls` only, without `/R`, `/T`, inheritance flags, wildcard input, or broad principal. File/empty-directory removal is literal and nonrecursive. |
| Baseline comparison blind spot | PASS | Pre- and post- `git diff --name-only`, `git diff --cached --name-only`, and `git status --porcelain=v1 -uall` are compared; app/test delta is independently required empty. |
| Open-handle false negative | BOUNDED | `handle.exe` is not installed. Installed `openfiles.exe` reports that the system object list is disabled and cannot enumerate local opened files. This is not recorded as "no handles". Each target will be re-queried, checked for content changes, and deferred on a sharing/access conflict; no process will be terminated. |

## Focused corrective design

No P0/P1 was found. The handle-observability limitation is an environment control, not a reason to widen privilege or tooling. The root-level control is an explicit non-claim plus per-target change/sharing-conflict deferral—not a bypass or a cosmetic clean-handle assertion.

## Focused procedure correction — 2026-08-06

The first exact ACL-repair attempt was rejected before mutation because Windows accepts `takeown /D Y` only with recursive `/R`, while recursive ownership is forbidden. This is a procedure P1, not a target condition. The corrected root-level procedure is `takeown.exe /F <exact-current-component>` with neither `/D` nor `/R`; when the recorded owner is already the `whoami` principal, ownership is an intentional no-op and only exact-component access grant may be considered. No fixture, ACL, or ownership state changed in the rejected attempt. `takeown /?` is the focused non-mutating syntax check.

```yaml
fable_fix:
  symptom: "takeown rejected the proposed nonrecursive command before operating on the first fixture root."
  root_cause: "The dry run did not distinguish takeown's /D syntax constraint from its recursion switch."
  evidence: "takeown.exe returned: /D should be specified only with /R."
  fix: "Remove /D and /R; make already-current ownership an explicit no-op."
  regression_test: "takeown /? and exact work-order command review."
  red_green_verified: true
  attempt: 1
```

## Focused procedure correction — fixture-root final removal

The first verified fixture pass removed every expected leaf and nested chain directory but stopped at the ten exact empty fixture roots. The cause was a bottom-up list that omitted the root itself. Read-only inventory confirmed every retained root is an exact non-reparse empty directory and Git status is clean; no parent was touched. The corrected procedure appends the exact verified root as the final bottom-up component. This is narrower than the prior operation and is not recursive.

```yaml
fable_fix:
  symptom: "All ten fixture target roots remained empty after their verified leaves and descendants were removed."
  root_cause: "The bottom-up deletion list contained only descendants, not the exact target root."
  evidence: "Post-pass literal inventory: ten directories, each non-reparse with child_count=0; git status clean."
  fix: "Verify and remove the exact empty fixture root as the final literal component."
  regression_test: "Per-root postcondition: Test-Path -LiteralPath <exact-root> is false."
  red_green_verified: true
  attempt: 2
```

```yaml
evidence:
  phase: MANUAL_QA
  command: "Static exact-root, Git, reparse, tracked-path, worktree-tip, and installed-handle-facility checks; no application/test/database command."
  result: PASS
  decisive_output: "10 fixture + 55 cache + 5 remnant roots literal/non-reparse/untracked; five tips exact; P0=0/P1=0."
```

```yaml
fable_done:
  task: "WO-0154 pre-mutation hostile preflight"
  done_when_results:
    - item: "Path and target authorization controls"
      status: MET
      evidence: "Fixed-list count and canonical-component probes."
    - item: "Safe deletion procedure and stop rules"
      status: MET
      evidence: "WO-0154 required behavior and dry run."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  debt_check: "Local handle enumeration is environment-limited and explicitly deferred rather than hidden."
  deferred: ["Actual per-target execution and closeout."]
  status: VERIFIED
```

## Manual-retirement critical preflight

`ACCEPT - P0=0, P1=0 for documentation-only activation; per-target destructive gates remain mandatory.`

The user authorized actual retirement of only the five frozen full-tree remnants and later deletion
of a matching local fallback branch only after its path is proven absent. The standard-Git repair
re-gate had already established that each root has no authentic `.git` marker or worktree-admin
entry. This amendment does not attempt to recreate either; it uses a manual filesystem procedure
only after a new exact documentation baseline is live.

Frozen target tuples, copied without expansion from WO-0154 and the retirement manifest:

- `.claude/worktrees/codex-lane2-bootstrap` -> `codex/lane2-bootstrap` @ `ea3f75cec2e93a51ca100a8e83a5e658a2630300`
- `.claude/worktrees/codex-lane2-docs` -> `codex/lane2-docs` @ `088d9b5a026a1a5d977d834e00c4e73ba5acc9aa`
- `.claude/worktrees/codex-signal-tests-staging` -> `codex/signal-tests-staging` @ `24d3746a35e30f736a6c5e3541720f0d47b0d751`
- `.claude/worktrees/codex-wo-0114` -> `codex/wo-0114` @ `0a97f51aee11721448dccbf4576c8308bf88f14e`
- `.claude/worktrees/codex-wo-0124` -> `codex/wo-0124` @ `3d8015f2bf10fa26ea767d70cab586c9e1b324ca`

| Critical challenge | Required control | Result |
|---|---|---|
| Full-tree command reaches a parent, a prefix-collision path, or an added target | Five literal canonical roots only; relative-component equality, no rooted/`..`/ADS input, and one-target command construction | PASS |
| Reparse path redirects a recursive operation | Reparse scan of root and every readable descendant before access repair and again immediately before removal | PASS design; target-specific execution required |
| Protected cache leads to a broad permission change | At most its frozen immediate cache child may receive nonrecursive `takeown` and non-inheriting `icacls` after owner/ACL capture | PASS |
| Metadata loss is papered over | No `.git` or `.git/worktrees` creation/edit; registration absence remains a required postcondition | PASS |
| Branch is removed despite retained tree or unmerged history | Root absence + no registration + frozen tip + `git branch -d` only; no `-D` authority | PASS |
| Handle tool limitation is misrepresented | Record `openfiles`/process limitations; defer on any sharing or access failure; never end a process | PASS |
| Previously completed fixture/cache work is repeated | Those 65 outcomes and their known evidence limits are immutable inputs, not targets | PASS |

```yaml
fable_recheck:
  task: "WO-0154 manual full-tree retirement activation"
  local_and_live_reset_head: "c6cfaee6be7443e0a6f42d961efc08c5989b2edc"
  target_count: 5
  review_result: "ACCEPT - P0=0, P1=0"
  constraints:
    - "One exact literal root at a time; no parent, wildcard, or dynamic root."
    - "No .git/worktrees modification or worktree reconstruction."
    - "No recursive ownership or ACL command; no branch force deletion."
    - "A documentation-only commit and exact live-ref equality precede mutation."
  deferred_to_execution: "Target-by-target reparse, access, inventory, sharing, postcondition, and branch-deletion gates."
```
