---
type: Work Order
title: "One-click environment bootstrap: devcontainer + session-start recipe for cloud/away sessions"
status: CLOSED
work_order_id: WO-0119
wave: post-R2 beta-prep (infra; no product surface)
model_tier: mid
risk: low
disposition: [RESULT_SUMMARY_KEPT]
owner: Ameen / implementer: Codex session 2
created: 2026-07-20
gated_surface: none (no app code, no credentials, no data; CI workflow untouched)
---

# Work Order: make a fresh cloud/second-machine session ready-to-run in one step

## Goal

[FABLE • FULL • verification: DIRECT • task: WO-0119 cloud bootstrap]

```yaml
fable_gate:
  goal: "Provide one cross-platform command that creates a Python 3.12 venv, mirrors CI installation, and fails loudly on the three required smoke gates."
  assumptions:
    - "A Python 3.12 interpreter is available to the devcontainer and target host."
    - "The target can access the package index or an already-populated package cache for the initial install."
    - "The CI install lines in .github/workflows/ci.yml remain the authoritative dependency sequence."
  approach: "Add a host-agnostic Python bootstrapper, call it from a minimal Python 3.12 devcontainer, document the no-credentials/mock-default boundary, then prove fresh-run and rerun behavior in an OS-temp disposable checkout."
  out_of_scope:
    - "Application, test, CI, broker, credential, database, or data-file changes."
    - "Any live or paper venue interaction."
  done_when:
    - "Bootstrapper creates or reuses .venv, installs requirements under constraints, and runs ruff, mypy, and pytest collection."
    - "Fresh disposable checkout and rerun both finish with green smoke output and leave tracked files unchanged."
    - "Devcontainer and documentation satisfy the work-order constraints."
  blast_radius: "development-environment setup only"
```

TDD exception declaration: `tests/**` is forbidden by this work order. The red-first proof is
therefore an external invocation that fails because the required bootstrap command does not yet
exist; behavior is subsequently verified directly in a disposable checkout rather than by adding
an in-repo test file outside the allowed paths.

A fresh clone — Codespace, Codex Cloud, Claude Code web, or a new laptop — reaches "gates
runnable" (venv built, deps installed, smoke check green) with zero manual setup, so the
operator's home↔away workflow and future cloud agent sessions start warm instead of bare.

## Context packet

Read only these first:

- `CLAUDE.md` (stack pins: Python 3.12, ruff/mypy/pytest gate) + `AGENTS.md`
- `pyproject.toml` (the dependency + tool source of truth)
- `.github/workflows/ci.yml` (the canonical install/gate sequence to mirror — do NOT edit it)
- `.gitignore` (venvs/caches/data stay untracked; the recipe must not fight it)
- `work/queue/CODEX-KICKOFF-PD1-R2-HYGIENE-AUDIT.md` "Mode notes" (the cloud bootstrap this WO
  automates)

## Allowed paths

```yaml
allowed_paths:
  - .devcontainer/**           # devcontainer.json + setup script (Codespaces / devcontainer hosts)
  - harness/**                 # a plain, host-agnostic bootstrap script the devcontainer calls
  - docs/00_START_HERE.md      # ONE short "environment setup" pointer section
  - work/**                    # close-out
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**
  - tests/**
  - .github/workflows/**       # CI is the gate authority; the bootstrap mirrors it, never edits it
  - .claude/**                 # ClaudeFast kit config is operator-managed
```

## Required behavior

- [ ] One host-agnostic script (e.g. `harness/bootstrap.py` or `.sh`): create/activate a
      Python 3.12 venv, install the project + dev tools per `pyproject.toml` (mirror the CI
      install lines), then run a smoke gate — `ruff check .`, `mypy app/`,
      `pytest -q --collect-only` — and exit nonzero on any failure. Idempotent: safe to rerun
      on an already-bootstrapped clone.
- [ ] `.devcontainer/devcontainer.json`: Python 3.12 base image, `postCreateCommand` invoking
      the script. Nothing else clever — no extensions mandates, no secrets blocks.
- [ ] **Never** touches, requires, or references credentials (`ALPACA_*`), `data/`, or any
      `*.db`; runs fully offline-after-install; `BROKER_ADAPTER` untouched (default `auto`
      degrades to mock without keys — state this in the doc pointer).
- [ ] Nothing new tracked that `.gitignore` says is untracked; `git status` clean after a
      bootstrap run on a fresh clone.
- [ ] Doc pointer: a short "Environment setup" note in `docs/00_START_HERE.md` (script, what
      it does, what it deliberately does not do).

## Acceptance criteria

- [ ] Fresh-clone proof: from a clean checkout in a disposable location, the script runs to a
      green smoke gate — full output pasted.
- [ ] Rerun proof: second invocation is a fast no-op/refresh, also pasted.
- [ ] `git status` clean after both runs; diff touches allowed paths only.
- [ ] Fable DONE block with evidence; close-out + ledger in the same commit.

## Stop conditions

Stop if the bootstrap would need a credential, a schema/data file, or a CI edit to work —
that's a design smell, not a workaround target. Rollback: revert the commit; nothing external
to unwind.

## Model-tier rationale

`mid` — small surface, but it must faithfully mirror CI's install/gate contract and fail loudly
rather than half-bootstrap.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]`.

## Fable verification and close-out

```yaml
fable_fix:
  symptom: "The initial disposable fresh-run proof stopped before dependency installation completed."
  root_cause: "The restricted sandbox denied package-index sockets; a normal temporary Windows clone also exceeded the host path limit on already-tracked .claude files. Neither condition was caused by the bootstrapper."
  evidence: "Restricted run reached `pip install -r requirements.txt -c constraints.txt` and exited 1 with WinError 10013; a normal temporary clone reported `Filename too long`."
  fix: "Retried the same CI-mirroring command with approved package-index access in an OS-temp archive checkout, then initialized a disposable Git baseline with core.longpaths enabled solely to verify tracked-file cleanliness."
  regression_test: "Fresh and second bootstrap invocations in the disposable checkout both returned 0; the second invocation reported reused installed requirements and completed all smoke gates."
  red_green_verified: true
  attempt: 1
```

```yaml
evidence:
  command: "Before implementation: python harness/bootstrap.py --help"
  result: FAIL
  decisive_output: "can't open file ...\\harness\\bootstrap.py: [Errno 2] No such file or directory; RED_EXIT_CODE=2"
---
evidence:
  command: "C:\\Users\\amujt\\dev\\automation-alpaca\\.venv\\Scripts\\python.exe -m ruff check harness/bootstrap.py; ... -m mypy harness/bootstrap.py"
  result: PASS
  decisive_output: "All checks passed!; Success: no issues found in 1 source file"
---
evidence:
  command: "Fresh OS-temp archive checkout: python harness/bootstrap.py; repeat the command; git status --short"
  result: PASS
  decisive_output: "Fresh install completed; ruff: All checks passed!; mypy: Success: no issues found in 64 source files; pytest collection completed; RERUN_EXIT_CODE=0; final git status output was empty."
```

```yaml
fable_done:
  task: "WO-0119 cloud bootstrap"
  done_when_results:
    - "harness/bootstrap.py finds or requires Python 3.12, creates/reuses .venv, mirrors the two CI pip commands, and executes the three required smoke gates."
    - ".devcontainer/devcontainer.json supplies a Python 3.12 image and runs the bootstrapper after creation."
    - "docs/00_START_HERE.md points operators to the command and states its credential-free, mock-default boundary."
    - "Fresh and rerun disposable verification passed with no tracked-file changes."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "Fresh and rerun direct evidence above."
    - "Focused ruff and mypy evidence above."
  status: VERIFIED
```
