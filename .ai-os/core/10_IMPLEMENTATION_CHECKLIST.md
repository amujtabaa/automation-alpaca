# Implementation Checklist

## Phase 0 — Install the OS shell

- [ ] Add the root `AGENTS.md` marked block from `adapters/codex/AGENTS.md.stub` (and `CLAUDE.md` from `adapters/claude/CLAUDE.md.stub`).
- [ ] Add `.ai-os/` or equivalent folder for scripts/rules/templates.
- [ ] Add `pkl/` folder with index and log.
- [ ] Add Fable Core v3 or adapter-specific skill.

## Phase 1 — Create project truth

- [ ] Create project goals page.
- [ ] Create architecture map.
- [ ] Create testing model.
- [ ] Create default architecture ADR.
- [ ] Create module pages for initial modules.

## Phase 2 — Enforce the basics

- [ ] Add PKL frontmatter lint script.
- [ ] Add work-order scope check script.
- [ ] Add work-order disposition check script.
- [ ] Add context hygiene report script.
- [ ] Add Fable DONE/evidence check script.
- [ ] Wire checks into pre-commit or CI.

## Phase 3 — Use worktrees

- [ ] Create work order for each feature.
- [ ] Create one branch/worktree per work order.
- [ ] Assign model tier per work order.
- [ ] Merge one branch at a time after full review.

## Phase 4 — Improve by evals

- [ ] Create synthetic bug-fix probes.
- [ ] Run agent with current OS.
- [ ] Record failure modes.
- [ ] Patch minimal guidance or harness.
- [ ] Re-run probes.

## Prompt Architecture implementation

- [ ] Add `11_PROMPT_ARCHITECTURE.md` to the OS package.
- [ ] Add `templates/prompts/00_prompt-router.md`.
- [ ] Add implementation, debugging, reviewer, refactor, test-hardener, architecture-review, PKL curator, handoff, and prompt-improver templates.
- [ ] Add `rules/prompt-rules.yaml`.
- [ ] Add `evals/prompt-evals.md`.
- [ ] Update work-order template to include `Prompt type`.
- [ ] Log prompt-template performance after each wave.
- [ ] Retire prompt templates that do not improve success, cost, or review quality.


## Phase 5 — Keep the OS right-sized

- [ ] Add `12_WORK_ORDER_RETENTION_AND_DISPOSITION.md`.
- [ ] Add `13_SESSION_LENGTH_AND_CONTEXT_HYGIENE.md`.
- [ ] Create `work/queue`, `work/active`, `work/review`, `work/completed/keep`, `work/completed/delete-candidates`, and `work/archive`.
- [ ] Create `work/ledger.jsonl`.
- [ ] Add `templates/work-result.md`.
- [ ] Add `templates/disposition-review.md`.
- [ ] After each merge, assign a work-order disposition from the vocabulary in `rules/ai-os-rules.yaml` (`valid_work_order_dispositions`).
- [ ] Delete routine, duplicate, placeholder, irrelevant, or low-value prompts after distillation.
- [ ] Run a hygiene pass after each wave and before long-session handoff.
- [ ] Keep `AGENTS.md` / `CLAUDE.md` adapter shims short and move detail into OS core, skills, PKL, or templates.


## Phase 6 — Optional MCP control plane

- [ ] Add `14_MCP_CONTROL_PLANE.md`.
- [ ] Add `mcp/README.md`.
- [ ] Add MCP resource, prompt, and tool specs.
- [ ] Add starter schema files for context packet, doctor report, disposition review, and work-order validation.
- [ ] Add local stdio server scaffold under `mcp/server/`.
- [ ] Keep MCP read-only for MVP.
- [ ] Do not enable MCP write tools without explicit approval.
- [ ] Ensure all OS workflows still work without MCP.
- [ ] Review whether `ai_os_get_context_packet` produces smaller and better task context than manual file-reading.
