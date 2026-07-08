# In-Use Structure

## Design principle

The OS should be operated from the task, not from the manual.

A developer or agent should not begin by reading the whole operating system. They should begin with a work order that links only the context needed for that job.

## Runtime flow

```text
1. Human gives intent or selects existing work order
2. Prompt Architecture converts intent into a work order or selects the right prompt template
3. Work order lists exact PKL pages and file paths
4. Agent reads the relevant adapter shim (`CLAUDE.md`, `AGENTS.md`, or generic session prompt) + work order + linked context
5. Agent runs Fable GATE
6. Agent writes failing test
7. Agent implements minimal code
8. Agent verifies with evidence
9. Harness checks scope and quality rules
10. Reviewer checks diff against work order
11. Merge updates PKL and ledger
12. Work order is distilled, summarized, archived, or deleted
13. Hygiene pass prunes stale context before the next task
```

## Directory structure

```text
repo/
  CLAUDE.md      # Claude Code adapter shim
  AGENTS.md      # Codex/generic agent adapter shim
  docs/
    architecture/
    testing/
    operations/
  pkl/
    index.md
    log.md
    project/
    architecture/
    modules/
    decisions/
    drift/
  work/
    queue/
    active/
    review/
    completed/
      keep/
      delete-candidates/
    archive/
    ledger.jsonl
  .ai-os/
    rules/
    scripts/
    templates/
      prompts/
    adapters/
  apps/
  packages/
  tests/
```

## What lives where

| Artifact | Purpose | Token posture |
|---|---|---|
| CLAUDE.md / AGENTS.md | Minimal adapter shims | Always-on, very small |
| Nested instruction files | Local module rules | Only when agent works there |
| Fable skill | Execution behavior | On-demand |
| PKL page | Curated project knowledge | Linked by work order |
| Prompt template | Reusable task framing | Read only when selected |
| Work order | Temporary current task packet | Always read only while task is active |
| Work result | Compact outcome summary | Read only when directly relevant |
| Ledger | Searchable work history | Query/index; do not load wholesale |
| ADR | Accepted architecture decision | Read when relevant |
| Harness script | Deterministic validation | Run, not read |
| CI workflow | Merge enforcement | Run, not read |

## Anti-patterns

- One giant AGENTS.md containing architecture, prompts, logs, and templates.
- Work orders that say “review the repo” instead of listing relevant files.
- Multiple agents modifying the same foundation files in parallel.
- Treating a model’s “done” statement as verification.
- Letting PKL become uncited AI-generated folklore.
- Using the strongest model for routine mechanical edits.
- Using the cheapest model for final review.


## Prompt Architecture in the runtime flow

Prompt Architecture should be invisible when the task is already well-formed and very visible when the task is vague. If the human says “build X,” the OS should first generate a work order. If the human provides a complete work order, the agent should skip prompt expansion and execute.

```text
Vague intent → work-order-generator prompt → work order → implementation/debug/review prompt
Complete work order → selected prompt template → Fable execution
Completed work → PKL curator prompt → knowledge update
```


## Work-order disposition in the runtime flow

Work orders are not long-term memory. After a work order is merged, closed, abandoned, or superseded, the agent must apply `12_WORK_ORDER_RETENTION_AND_DISPOSITION.md`.

```text
Completed task
→ extract durable facts
→ update PKL/ADR/tests/ledger
→ decide disposition
→ delete or compact raw prompt
```

Allowed dispositions are defined canonically in `rules/ai-os-rules.yaml` (`valid_work_order_dispositions`).

The default for routine, low-value, duplicate, placeholder, or superseded prompts is deletion after any useful facts are captured elsewhere.

## Long-session hygiene in the runtime flow

As session length increases, the active context packet should shrink. The agent should trust artifacts over conversation memory and should periodically run `13_SESSION_LENGTH_AND_CONTEXT_HYGIENE.md`.

Use a hygiene pass when:

- context compaction occurs
- work seems repetitive or stale
- a branch merges
- a wave completes
- an agent resumes from another session
- PKL/work-order/prompt folders start accumulating noise

The hygiene pass should recommend: keep, shorten, distill, convert-to-ADR, summarize-result, archive, or delete.


## Optional MCP control plane in the runtime flow

MCP can be used as an access layer when available, but the repo-installed OS remains canonical.

```text
Without MCP:
agent reads adapter shim → work order → linked PKL/templates/rules

With MCP:
agent calls ai_os_get_context_packet → receives exact work order/context/prompt/rules → proceeds under Fable
```

MCP should be especially useful for:

- installation doctor checks
- context packet generation
- work-order validation
- hygiene reports
- disposition review
- prompt/resource lookup

MCP should not become the only way to use the OS. Every workflow must still be executable from repo files.
