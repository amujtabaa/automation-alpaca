---
type: Work Order
title: "One-click environment bootstrap: devcontainer + session-start recipe for cloud/away sessions"
status: ACTIVE
work_order_id: WO-0119
wave: post-R2 beta-prep (infra; no product surface)
model_tier: mid
risk: low
disposition: []
owner: Ameen / implementer: Codex session 2
created: 2026-07-20
gated_surface: none (no app code, no credentials, no data; CI workflow untouched)
---

# Work Order: make a fresh cloud/second-machine session ready-to-run in one step

## Goal

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
