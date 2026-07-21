---
type: Work Order
title: "Recorder retention bound (max_segments=1) + bootstrap external-venv guard"
status: CLOSED
work_order_id: WO-0130
wave: ultra-batch remediation (post-review)
model_tier: mid
risk: low
disposition: [RESULT_SUMMARY_KEPT]
owner: Ameen / implementer: Codex remediation session
created: 2026-07-21
gated_surface: none (recorder is off-by-default disposable tape; bootstrap is dev tooling)
---

# Work Order: close two small tooling footguns from the batch self-review

## Goal

Two independent low-risk fixes the batch's own adversarial pass found: the tape recorder's
retention guarantee is violated for a valid config, and the bootstrap script can create a venv
outside the repo.

## Context packet

- `work/review/AUDIT-0002-priorwork/` conventions + `CLAUDE.md`
- Codex batch self-review P1-1 (recorder) + P2 (bootstrap) — reproduced by the planning seat
- `app/recorder/store.py` (the rotation logic) + `tests/test_tape_recorder.py`
- `harness/bootstrap.py:72` (the `--venv` path resolution)

## Allowed paths

```yaml
allowed_paths:
  - app/recorder/store.py
  - harness/bootstrap.py
  - tests/**
  - work/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/store/**
  - app/events/**
  - app/facade/**
  - app/api/**
```

## Required behavior

- [x] **Recorder (P1):** `TapeStore._rotate()` iterates `range(max_segments-1, 0, -1)`, which is
      EMPTY when `max_segments=1`, so the active file grows past `max_bytes` unbounded while the
      constructor accepts `max_segments >= 1` — the documented retention bound is violated for a
      valid config. Fix ONE of: (a) reject `max_segments < 2` consistently in code, config parse,
      and docs; or (b) implement active-file replacement so `max_segments=1` keeps exactly one
      bounded segment (truncate-and-restart on overflow). State which and why. Add the missing
      boundary test (`max_segments=1`, plus a `max_segments=2` rotation regression).
- [x] **Bootstrap (P2):** `harness/bootstrap.py:72` describes `--venv` as repo-relative but
      resolves `..\shared-venv` outside the repo and may create/install there. Constrain the
      resolved path to inside the repo, OR require an explicit `--allow-external-venv` opt-in;
      test the rejection/opt-in.
- [x] Both fixes red-first (a failing test that the fix turns green); recorder test proves the
      bound actually holds at `max_segments=1`.

## Acceptance criteria

- [x] Recorder retention bound holds for every accepted config (pinned at the boundary).
- [x] Bootstrap cannot silently create a venv outside the repo without explicit opt-in.
- [x] `ruff`/`mypy app/`/`pytest -q` green; Fable DONE + close-out + ledger with the work.

## Stop conditions

Stop if either fix would need to touch execution/store truth (it must not). Rollback: revert.
Independent of every other remediation WO; may run first (cheapest).

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]`.

## Fable verification and close-out

```yaml
fable_gate:
  goal: "Restore the accepted one-segment tape-retention bound and prevent bootstrap from silently targeting any path outside the checkout."
  assumptions:
    - "The recorder remains off by default, disposable, and isolated from execution/event-log truth."
    - "The documented --venv contract is repository-relative; external virtual environments are not an accepted implicit behavior."
    - "No credential, broker, database, execution store, live mode, or network action is needed."
  approach: "Keep max_segments=1 valid by replacing its active segment at the byte threshold; add a resolved-path strict-descendant guard before bootstrap performs any filesystem or subprocess action."
  out_of_scope:
    - "Execution stores, event truth, facade/API/cockpit behavior, broker access, credentials, and live trading."
    - "Changing the accepted max_segments configuration range or adding an external-venv opt-in."
  done_when:
    - "One-segment and two-segment retention boundaries are failure-capable and green."
    - "Relative escapes, absolute external paths, and the repository root itself fail before bootstrap executes a command."
    - "Focused and full repository gates pass from OS-temporary pytest bases."
  blast_radius: "isolated NDJSON recorder retention plus credential-free developer bootstrap path validation"
```

```yaml
fable_fix:
  symptom: "A TapeStore configured with max_segments=1 appended forever after crossing max_bytes."
  root_cause: "Rotation relied exclusively on range(max_segments - 1, 0, -1), whose one-segment range is empty; append then always reopened the unchanged active file in append mode."
  evidence: "The red boundary retained both sequence 1 and sequence 2 in tape.ndjson instead of only sequence 2."
  fix: "Preserve the accepted configuration and switch the overflowing one-segment write to truncate/restart mode; two-or-more segments continue through the existing archive rotation."
  regression_test: "test_store_replaces_active_segment_when_only_one_is_retained; test_store_rotates_and_replaces_oldest_when_two_segments_are_retained"
  red_green_verified: true
  attempt: 1
```

```yaml
fable_fix:
  symptom: "The repo-relative --venv option accepted .. and absolute paths, then could create and install into an external directory."
  root_cause: "The help text stated the boundary but main() only called Path.resolve(); no containment invariant was enforced before mkdir or subprocess execution."
  evidence: "All four initial resolver boundary nodes failed because no containment resolver existed; bypassing the completed resolver made the direct main-path pin fail at the attempted external venv command."
  fix: "Resolve the repository and candidate paths, require candidate.relative_to(root), reject equality with the checkout root, and wire main() through that guard before any filesystem/subprocess action."
  regression_test: "tests/test_bootstrap.py, including test_main_rejects_external_venv_before_running_any_command"
  red_green_verified: true
  attempt: 1
```

### Fresh evidence

| Classification | Command | Decisive output |
|---|---|---|
| UNVERIFIED | focused baseline with pytest default shared temp root | `PermissionError [WinError 5]` while enumerating the pre-existing OS-temp `pytest-of-amujt`; no product assertion failed. |
| VERIFIED | same baseline with a fresh unique OS-temp `--basetemp` | `8 passed`. |
| VERIFIED (RED) | new retention and bootstrap boundary nodes before production changes | `F.FFFF`: five intended failures; the existing two-segment behavior passed. |
| VERIFIED (GREEN) | exact red nodes after both fixes | `6 passed`. |
| VERIFIED (mutation RED) | temporarily bypass `_resolve_venv` in `main()` | direct main-path pin failed before a command could run; attempted target shown as `C:\\Users\\amujt\\dev\\shared-venv`. Mutation restored. |
| VERIFIED (restored) | `pytest` over `tests/test_bootstrap.py tests/test_tape_recorder.py` | `12 passed`. |
| VERIFIED | `ruff check .` | `All checks passed!` |
| VERIFIED | `mypy app/` | `Success: no issues found in 70 source files`. |
| VERIFIED | full `pytest -q -p no:cacheprovider --basetemp <unique OS temp>` | exit `0` after `385.9s`; `11 skipped`, `1 xfailed`; fresh collection counted `4105` nodes. |

```yaml
fable_done:
  task: "WO-0130 recorder retention and bootstrap external-venv remediation"
  done_when_results:
    - "VERIFIED: max_segments=1 keeps only the newest active segment after overflow, while max_segments=2 rotation still replaces the oldest archive."
    - "VERIFIED: bootstrap rejects relative and absolute escapes plus the checkout root before any command runs."
    - "VERIFIED: the main-path containment pin is mutation-proven and restored."
    - "VERIFIED: ruff, mypy, focused tests, and the full 4105-node corpus exited green."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "Red, green, mutation, restored, static, and full-corpus evidence above."
  status: VERIFIED
```
