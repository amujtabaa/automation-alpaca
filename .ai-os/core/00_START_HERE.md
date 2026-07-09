# AI Project Operating System — v0.9.1

Package release: v0.9.1  
Release date: 2026-07-07  
Canonical version source: `VERSION.md` and `AI_OS_MANIFEST.yaml`

This package refines the AI Project Operating System after a targeted research pass focused on actual in-use performance: context efficiency, repository instructions, Prompt Architecture, deterministic enforcement, Project Knowledge Layer design, model-tier economics, Fable integration, and an optional MCP control plane.

## Operating thesis

The system should not try to make every agent session smarter by loading more context. It should make each session safer and cheaper by giving it the smallest useful context, then enforcing outcomes with tests, hooks, work-order limits, and review gates.

## Layer map

```text
AI Project Operating System
├── 01 Research Findings
├── 02 Decision Register
├── 03 In-Use Structure
├── 04 Project Knowledge Layer (PKL)
├── 05 Agent Instruction Strategy
├── 06 Fable v3 Execution Protocol
├── 07 Harness / Rules / CI
├── 08 Worktrees and Model-Tier Orchestration
├── 09 Evals and Continuous Improvement
├── 10 Implementation Checklist
├── 11 Prompt Architecture
├── 12 Work Order Retention and Disposition
├── 13 Session Length and Context Hygiene
├── 14 MCP Control Plane
└── templates, prompts, rules, scripts, adapters, mcp
```

## Fast-start sequence

1. Install repo-local adapter shims as marked blocks from `adapters/claude/CLAUDE.md.stub` (into `CLAUDE.md`) and `adapters/codex/AGENTS.md.stub` (into `AGENTS.md`), or use `INSTALL_AGENT.md`. File placement is declared by `install_map` in `AI_OS_MANIFEST.yaml`.
2. Keep the neutral OS core under `.ai-os/`; adapter files are not canonical.
3. Create `pkl/` using `04_PROJECT_KNOWLEDGE_LAYER.md` and `templates/pkl-page.md`.
4. Use `templates/work-order.md` for every worktree task.
5. Use `templates/fable-core-v3.md` or an adapter-specific skill for agent execution discipline.
6. Use `11_PROMPT_ARCHITECTURE.md` and `templates/prompts/` to convert human intent into consistent work orders and execution prompts.
7. Add deterministic checks from `rules/ai-os-rules.yaml` and `scripts/` before trusting agent completion claims.
8. Review every wave with `templates/review-checklist.md`.
9. After every merge or closed task, apply `12_WORK_ORDER_RETENTION_AND_DISPOSITION.md`.
10. During long sessions, compaction, or handoff, apply `13_SESSION_LENGTH_AND_CONTEXT_HYGIENE.md`.
11. If using MCP, treat `14_MCP_CONTROL_PLANE.md` and `mcp/` as the optional access/control layer; the repo-installed OS remains canonical.

## Definitions

- **PKL — Project Knowledge Layer:** OKF-compatible repository memory. It stores curated project truth, not chat history.
- **Fable:** model-agnostic execution discipline protocol. It governs agent behavior while completing a work order. It was derived from the uploaded Fable material but is no longer Claude-centered.
- **Work order:** temporary execution ticket for the smallest coherent unit of implementation. It gives the agent exact scope, required tests, allowed paths, and context packet; after completion it is distilled, summarized, archived, or deleted.
- **Prompt Architecture:** reusable prompt templates and routing rules that convert human intent into work orders, implementation prompts, review prompts, and PKL update prompts.
- **Harness:** deterministic scripts/hooks/CI that validate behavior and scope. It turns some instructions into enforceable checks.
- **Disposition:** final handling of a work order after completion. The vocabulary is defined canonically in `rules/ai-os-rules.yaml` (`valid_work_order_dispositions`).
- **MCP control plane:** optional local server/interface that exposes targeted AI OS resources, prompts, and tools. It improves access and context routing; it is not the source of truth.

## Non-goals

- Not a giant prompt.
- Not a microservice architecture template.
- Not a replacement for tests.
- Not a replacement for human review.
- Not a proprietary Claude-only or Codex-only process.

## Source anchors

This package was informed by the uploaded Fable v2/Core material and current sources on AGENTS.md, Codex hooks/skills, context engineering, OKF, and coding-agent guidance research. See `01_DEEP_RESEARCH_FINDINGS.md`.
