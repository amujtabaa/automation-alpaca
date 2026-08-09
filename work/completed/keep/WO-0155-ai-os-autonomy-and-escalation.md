---
type: Work Order
title: Persist autonomous execution and bounded escalation policy
status: CLOSED
work_order_id: WO-0155
wave: AI-OS-0.9.2
model_tier: strong
risk: medium
disposition: [PKL_UPDATED, RESULT_SUMMARY_KEPT]
owner: Codex implementation seat
created: 2026-08-08
execution_authority: "User explicitly authorized durable AI-OS and Claude-workflow improvements, including removal of any temporary Terra/Sol escalation rule. Ordinary in-scope reversible implementation, tests, records, commit, and normal push are authorized."
---

# Work Order: Persist autonomous execution and bounded escalation policy

## Goal

Convert the ARCH-RESET M1 process lessons into versioned, test-pinned AI-OS and Claude/Codex
workflow policy: continue solving within granted authority, ask only for genuinely missing authority
or an irreducible human decision, and use no mandatory named-model escalation ladder.

## Context packet

- `AGENTS.md`
- `CLAUDE.md`
- `.ai-os/core/06_FABLE_V3_EXECUTION_PROTOCOL.md`
- `.ai-os/core/08_WORKTREES_AND_MODEL_ORCHESTRATION.md`
- `.ai-os/core/11_PROMPT_ARCHITECTURE.md`
- `.ai-os/templates/fable-core-v3.md`
- `.ai-os/rules/prompt-rules.yaml`
- `.claude/skills/fable/SKILL.md`
- `.claude/commands/build.md`
- `.claude/skills/session-management/session-types/development.md`
- `.claude/skills/session-management/session-types/debugging.md`

## Allowed paths

```yaml
allowed_paths:
  - AGENTS.md
  - CLAUDE.md
  - .ai-os/AI_OS_MANIFEST.yaml
  - .ai-os/VERSION.md
  - .ai-os/core/00_START_HERE.md
  - .ai-os/core/03_IN_USE_STRUCTURE.md
  - .ai-os/core/06_FABLE_V3_EXECUTION_PROTOCOL.md
  - .ai-os/core/08_WORKTREES_AND_MODEL_ORCHESTRATION.md
  - .ai-os/core/10_IMPLEMENTATION_CHECKLIST.md
  - .ai-os/core/11_PROMPT_ARCHITECTURE.md
  - .ai-os/core/15_CROSS_MODEL_REVIEW.md
  - .ai-os/core/19_AUTONOMY_AND_ESCALATION.md
  - .ai-os/evals/prompt-evals.md
  - .ai-os/rules/ai-os-rules.yaml
  - .ai-os/rules/prompt-rules.yaml
  - .ai-os/scripts/check_version_consistency.py
  - .ai-os/scripts/ai_os_paths.py
  - .ai-os/scripts/tests/conftest.py
  - .ai-os/scripts/tests/test_promoted_scripts.py
  - .ai-os/scripts/tests/test_scripts.py
  - .ai-os/scripts/tests/test_phase3_checks.py
  - .ai-os/templates/fable-core-v3.md
  - .ai-os/templates/work-order.md
  - .ai-os/templates/prompts/00_prompt-router.md
  - .ai-os/templates/prompts/implementation.md
  - .ai-os/templates/prompts/debugger.md
  - .ai-os/templates/prompts/work-order-generator.md
  - .ai-os/adapters/claude/CLAUDE.md.stub
  - .ai-os/adapters/codex/AGENTS.md.stub
  - .ai-os/adapters/generic/SESSION_PROMPT.md
  - .claude/skills/fable/SKILL.md
  - .claude/commands/build.md
  - .claude/commands/team-build.md
  - .claude/commands/workflow-build.md
  - .claude/skills/session-management/SKILL.md
  - .claude/skills/session-management/session-types/development.md
  - .claude/skills/session-management/session-types/debugging.md
  - tests/test_ai_os_autonomy_policy.py
  - pkl/log.md
  - work/ledger.jsonl
  - work/active/WO-0155-ai-os-autonomy-and-escalation.md
  - work/completed/keep/WO-0155-ai-os-autonomy-and-escalation.md
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**
  - .github/workflows/**
  - docs/adr/**
  - work/review/REV-0058/**
  - work/review/REV-0059/**
  - work/review/REV-0060/**
  - work/active/WO-0154-residual-filesystem-cleanup.md
```

## Required behavior

- [x] An explicit implementation request or ACTIVE work order authorizes ordinary, reversible,
      in-scope work without repeated permission requests.
- [x] Missing facts trigger bounded investigation and safe assumptions before `NEEDS-INPUT`.
- [x] Failed attempts trigger root-cause re-gating, not an automatic return to the human.
- [x] Human escalation remains mandatory for new authority, human-gated surfaces without approval,
      irreversible/destructive actions, unresolved authority conflicts, and unavailable external
      secrets or decisions.
- [x] Surprise root causes may be addressed when they remain necessary to the authorized outcome and
      inside safety/architecture boundaries; material expansion is batched for human decision.
- [x] No fixed Terra/Sol or other named-model ladder is required; model choice inherits by default and
      may be overridden only for a concrete task reason.
- [x] Historical SOL incident/provenance records remain byte-stable and are not mistaken for routing.

## Required tests

- [x] RED/GREEN regression test pins machine-readable autonomy policy and adapter propagation.
- [x] Negative assertions reject the prior unconditional approval/stop wording.
- [x] Existing AI-OS script tests and project governance checks pass.

## Required commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_ai_os_autonomy_policy.py -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest -q .ai-os/scripts/tests -p no:cacheprovider
.\.venv\Scripts\python.exe .ai-os/scripts/check_version_consistency.py
.\.venv\Scripts\python.exe .ai-os/scripts/check_ledger.py
.\.venv\Scripts\python.exe .ai-os/scripts/check_pkl.py pkl
.\.venv\Scripts\python.exe .ai-os/scripts/check_work_order_disposition.py
```

## Acceptance criteria

- [x] Canonical policy, prompts, Claude workflows, and Codex shim agree on the escalation boundary.
- [x] The old unconditional stop/permission phrases are absent from active execution paths.
- [x] AI Project OS is versioned as v0.9.2 with consistent manifest/rule/script markers.
- [x] The process lesson is recorded in prompt evals, PKL log, ledger, and future-session memory.
- [x] No product, CI workflow, safety invariant, historical review packet, or WO-0154 change occurs.

## Model-tier rationale

The change is documentation/configuration-heavy but alters agent authority interpretation across
multiple runtimes, so it needs architecture-level judgment. This is capability selection, not a
mandatory named-model escalation sequence.

## Completion disposition

- [x] PKL_UPDATED
- [x] RESULT_SUMMARY_KEPT

## Distillation checklist

- [x] Durable process facts captured in canonical AI-OS policy.
- [x] Claude and Codex entrypoints reference the canonical policy.
- [x] Prompt-eval failure lesson recorded.
- [x] Ledger updated.
- [x] Work order retained as a compact governance result.

## Outcome summary

AI Project OS v0.9.2 now treats recorded execution authority as reusable, requires investigation
and root-cause re-gating before human escalation, and has no mandatory named-model escalation
ladder. The policy is canonical in core, machine-readable in rules, propagated to Claude/Codex/Fable
entrypoints, and protected by failure-capable regression tests. Verification also exposed and fixed
a package/install path-resolution defect in the AI-OS harness without changing product code.

## Fable DONE

```yaml
fable_done:
  task: "WO-0155 — persist autonomous execution and bounded escalation policy"
  done_when_results:
    - item: "canonical and machine-readable autonomy policy"
      status: MET
      evidence: "40 focused AI-OS/autonomy tests passed"
    - item: "Claude, Codex, Fable, and prompt propagation"
      status: MET
      evidence: "entrypoint marker and obsolete-rule negative controls passed"
    - item: "model-neutral routing"
      status: MET
      evidence: "live-policy regression rejects a mandatory named-model ladder"
    - item: "governance and install integrity"
      status: MET
      evidence: "version, install, ledger, PKL, disposition, Ruff, and diff checks passed"
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  status: VERIFIED
```

## Evidence

```yaml
evidence:
  command: ".\\.venv\\Scripts\\python.exe -m pytest -q tests/test_ai_os_autonomy_policy.py .ai-os/scripts/tests -p no:cacheprovider"
  result: PASS
  decisive_output: "40 passed"
```
