# WO-0154 dry run — no mutation performed

The complete frozen root and branch lists are in [WO-0154](../../active/WO-0154-residual-filesystem-cleanup.md). This dry run makes the per-operation shape explicit: fixed roots only, dynamic discovery only inside a verified root, and no recursive deletion.

## Fixtures (10)

For every frozen fixture root, the only planned chain is:

```text
<exact fixture root>/test_completed_folder_rejects_0/work/completed/keep/WO-0999-fixture.md
```

Potential permission components, in order: the literal root, then the five literal chain components. No component receives ownership or ACL change unless its own exact reparse check is negative and its access actually prevents verification.

If ownership is needed, its sole permitted syntax is `takeown.exe /F <exact-current-component>`: neither `/D` nor `/R` is permitted. If the recorded owner already equals `whoami`, ownership is a no-op.

Planned deletion actions: verify the sole leaf name/size/SHA; delete that literal leaf; then remove each verified empty literal directory bottom-up, ending with the exact fixture root. The fixture parent is never removed.

## Root caches (55)

For every frozen root-cache directory, the initially planned permission component is only the literal direct child of the repository root. A child component has no pre-authorized ACL operation: it may be inspected only after its parent passes, and may receive an exact one-component change only after containment and negative reparse checks. Planned deletion action is one verified regular file at a time followed by one verified empty directory at a time, bottom-up.

## Worktree remnants and branches (5)

| Literal remnant | Literal cache child | Literal local branch | Expected tip |
|---|---|---|---|
| `.claude/worktrees/codex-lane2-bootstrap` | `.pytest_cache` | `codex/lane2-bootstrap` | `ea3f75cec2e93a51ca100a8e83a5e658a2630300` |
| `.claude/worktrees/codex-lane2-docs` | `.pytest_cache` | `codex/lane2-docs` | `088d9b5a026a1a5d977d834e00c4e73ba5acc9aa` |
| `.claude/worktrees/codex-signal-tests-staging` | `.pytest_cache` | `codex/signal-tests-staging` | `24d3746a35e30f736a6c5e3541720f0d47b0d751` |
| `.claude/worktrees/codex-wo-0114` | `.pytest_cache` | `codex/wo-0114` | `0a97f51aee11721448dccbf4576c8308bf88f14e` |
| `.claude/worktrees/codex-wo-0124` | `.pytest-tmp-review-138e389-core` | `codex/wo-0124` | `3d8015f2bf10fa26ea767d70cab586c9e1b324ca` |

For each row: validate the frozen tip and cited WO-0153 proof; inspect the exact cache child under the exact remnant root; recheck process/handle indication, content state, and Git/worktree state; attempt normal exact `git worktree remove`; run local `git worktree prune`; then delete the exact local branch only if its worktree path and registration are absent. No remote operation is planned.

## Explicitly absent from the plan

No repository root, workspace root, evidence parent, `.git` path, test/application path, wildcard, `Remove-Item -Path`, `git clean`, `git reset`, fetch/prune, remote branch deletion, recursive ACL, recursive ownership, or process termination is planned.

## Manual-retirement amendment dry run

For each of the five table rows above, the post-activation shape is intentionally one root and one
branch, never a batch deletion:

1. Resolve and equality-check the row's literal canonical root under `.claude/worktrees`; check its
   root and readable descendants for reparse points, and recheck the frozen branch tip/proof.
2. If the row's named immediate cache child blocks inventory, record its owner/ACL and change only
   that literal child using nonrecursive `takeown /F` and non-inheriting `icacls` for the current
   user. Any deeper access failure stops the row.
3. Require a complete non-reparse descendant inventory and unchanged immediate pre-delete state.
4. Run only `Remove-Item -LiteralPath <that-one-canonical-root> -Recurse -Force -ErrorAction Stop`.
   The literal is substituted from the frozen row, not discovered from enumeration.
5. Require exact root absence and no registration, then run local `git worktree prune` and recheck
   the other four rows for unexpected change.
6. Require the matching branch still equals its frozen tip and run `git branch -d <exact-branch>`.
   If it refuses, retain it; no force-delete is planned.

No manual `.git` operation, re-registration, move, quarantine, remote action, fixture/root-cache
action, recursive ACL/ownership command, branch `-D`, process termination, or application/test/
database/runtime command is in this amendment.
