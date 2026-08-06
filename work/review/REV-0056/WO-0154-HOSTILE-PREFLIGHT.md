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
