# Session Length and Context Hygiene

## Purpose

As sessions get longer, the OS must become more selective, not more verbose.

Long sessions create predictable failure modes:

- stale assumptions remain in recent context
- old work orders compete with current instructions
- agents over-read unrelated project material
- PKL pages become folklore instead of curated truth
- prompt templates multiply without evaluation
- status claims become detached from evidence
- sessions resume from memory instead of written state

The OS counters this with right-sizing budgets, lifecycle gates, and periodic hygiene passes.

## Core principle

The longer the session gets, the smaller the active context packet should become.

A mature session should rely on durable artifacts, not conversation memory.

## Context priority order

When sources conflict, use this authority order:

```text
1. Current code and tests
2. Contracts, schemas, migrations
3. Accepted ADRs
4. Current work order
5. Current PKL pages with high authority and recent verification
6. Recent Fable GATE/DONE/FIX blocks with evidence
7. Ledger entries and compact result records
8. Raw notes and archived prompts
9. Conversation memory
```

Conversation memory is last.

## Right-size budgets

These are defaults. Projects can tune them.

| Artifact | Recommended size | Rule |
|---|---:|---|
| Root `AGENTS.md` / `CLAUDE.md` shim | `root_instruction_max_lines` in `rules/ai-os-rules.yaml` | Router only. No full manuals. |
| Nested instruction file | 25-100 lines | Local module rules only. |
| Work order | 1-3 pages | Enough to execute; not a design novel. |
| Context packet | 5-9 items | Read list should fit the task. |
| PKL module page | 300-900 words | Canonical current truth, not history. |
| ADR | 1-2 pages | Decision, rationale, consequences. |
| Prompt template | 1 task pattern | Split if it handles multiple jobs. |
| Fable DONE block | compact evidence | Decisive command output, not full logs unless needed. |
| Ledger entry | 1 JSON line | Searchable trace, not prose. |

## Hygiene triggers

Run a hygiene pass whenever any trigger occurs:

- session exceeds a substantial length
- context compaction occurs
- agent appears to repeat or forget prior state
- a work order changes scope
- a wave completes
- a branch is merged
- a new agent/session resumes work
- PKL page seems stale or contradictory
- prompt template feels bloated
- work folder accumulates stale files

## The hygiene pass

Use this checklist:

```text
1. Identify current task and work order.
2. Confirm active context packet still matches the task.
3. Remove unrelated pages/files from the active read list.
4. Move completed work orders to disposition.
5. Delete low-value raw prompts after distillation.
6. Update PKL pages only with durable facts.
7. Convert decisions into ADRs.
8. Move transient findings to ledger/result record/deferred log.
9. Re-emit or regenerate a compact handoff state.
10. Continue from artifacts, not memory.
```

## Context packet pruning rules

Remove an item from the active context packet if:

- it is not needed to make the next decision
- it describes a completed task with no direct dependency
- it duplicates a PKL page or ADR
- it is a raw prompt whose knowledge was already distilled
- it is a placeholder or stale plan
- it introduces more ambiguity than it resolves

Add an item only if:

- the task is blocked without it
- a test/contract/schema depends on it
- a module boundary is unclear
- a relevant ADR or high-authority PKL page exists
- a reviewer specifically needs it to verify scope

## PKL cleanup rules

PKL pages should remain current and useful.

Delete or rewrite PKL content that is:

- outdated
- contradicted by code/tests
- duplicated across pages
- speculative but written as fact
- a transcript summary rather than durable knowledge
- unverified AI-generated synthesis
- too broad to help a future task

Prefer small canonical pages over large “everything we know” pages.

## Prompt Architecture cleanup rules

Prompt templates should be retained only if they improve performance, consistency, cost, or review quality.

Retire a prompt template if:

- it is unused for a wave
- it duplicates another template
- it encourages long context dumps
- agents frequently misapply it
- it produces work orders that require major correction
- it contains mostly generic advice

Useful prompt templates should become shorter over time.

## Work-order cleanup rules

Apply `12_WORK_ORDER_RETENTION_AND_DISPOSITION.md` after each merge or closed task.

Raw work orders are disposable once useful knowledge is distilled.

## Session handoff block

At session end, compaction, or major context reset, produce this:

```text
[AI-OS HANDOFF]
Current task: <work order id/title or none>
Current status: <DRAFT|READY|ACTIVE|REVIEW|MERGED|BLOCKED>
Source of truth: <files to trust next>
Do not trust: <old prompts/summaries that are stale>
Next action: <one concrete next step>
Open decisions: <human decisions pending>
Disposition needed: <work orders/prompts to distill/delete/archive>
Verification state: <last commands and status>
```

The next session must treat this as a pointer to artifacts, not as final truth. It should verify state against files, git, and tests.

## Right-sizing command

Use this in any model/runtime:

```text
ai-os hygiene

Run a context and artifact hygiene pass.
Do not implement features.
Identify stale, oversized, duplicate, or low-value work orders, PKL content, prompt templates, and instruction files.
Recommend one of: keep, shorten, distill, convert-to-ADR, summarize-result, archive, delete.
Do not delete files without listing the proposed deletions and receiving approval.
```

## Long-session operating rule

Never solve long-session drift by loading more history.

Solve it by:

- narrowing the active work order
- using a smaller context packet
- trusting canonical artifacts
- distilling useful state
- deleting low-value prompts
- re-running verification
