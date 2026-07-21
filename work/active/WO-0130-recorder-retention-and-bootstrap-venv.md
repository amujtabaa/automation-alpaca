---
type: Work Order
title: "Recorder retention bound (max_segments=1) + bootstrap external-venv guard"
status: ACTIVE
work_order_id: WO-0130
wave: ultra-batch remediation (post-review)
model_tier: mid
risk: low
disposition: []
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

- [ ] **Recorder (P1):** `TapeStore._rotate()` iterates `range(max_segments-1, 0, -1)`, which is
      EMPTY when `max_segments=1`, so the active file grows past `max_bytes` unbounded while the
      constructor accepts `max_segments >= 1` — the documented retention bound is violated for a
      valid config. Fix ONE of: (a) reject `max_segments < 2` consistently in code, config parse,
      and docs; or (b) implement active-file replacement so `max_segments=1` keeps exactly one
      bounded segment (truncate-and-restart on overflow). State which and why. Add the missing
      boundary test (`max_segments=1`, plus a `max_segments=2` rotation regression).
- [ ] **Bootstrap (P2):** `harness/bootstrap.py:72` describes `--venv` as repo-relative but
      resolves `..\shared-venv` outside the repo and may create/install there. Constrain the
      resolved path to inside the repo, OR require an explicit `--allow-external-venv` opt-in;
      test the rejection/opt-in.
- [ ] Both fixes red-first (a failing test that the fix turns green); recorder test proves the
      bound actually holds at `max_segments=1`.

## Acceptance criteria

- [ ] Recorder retention bound holds for every accepted config (pinned at the boundary).
- [ ] Bootstrap cannot silently create a venv outside the repo without explicit opt-in.
- [ ] `ruff`/`mypy app/`/`pytest -q` green; Fable DONE + close-out + ledger with the work.

## Stop conditions

Stop if either fix would need to touch execution/store truth (it must not). Rollback: revert.
Independent of every other remediation WO; may run first (cheapest).

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]`.
