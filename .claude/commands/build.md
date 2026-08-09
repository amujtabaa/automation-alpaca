---
description: Execute an implementation plan from a spec file
argument-hint: [path-to-plan]
---

# Build

Follow the `Workflow` to implement the `PATH_TO_PLAN` then `Report` the completed work.

## Variables

PATH_TO_PLAN: $ARGUMENTS

## Workflow

- If no `PATH_TO_PLAN` is provided, STOP immediately and ask the user to provide it (AskUserQuestion).
- Read and execute the plan at `PATH_TO_PLAN`. Think hard about the plan and implement it into the codebase.
- Follow the Team Orchestration section if present - use Task tools to coordinate team members.
- Follow the Step by Step Tasks in order, respecting dependencies.
- Use the Validation Commands to verify your work.

### Persistence and permission discipline

- Treat the user's implementation request or an `ACTIVE` work order as authority for ordinary,
  reversible actions within the plan. Do not pause for a second approval after reading the plan.
- Investigate missing context, unexpected failures, and necessary root causes before asking the
  user. Update the gate/task record and continue when the correction remains inside the authorized
  outcome and safety boundaries.
- After repeated failed attempts, stop the patch loop and re-gate a materially different approach;
  do not abandon the task or return to the user merely because it is difficult.
- Ask only when the next material action needs new authority, an unapproved human-gated/destructive
  action, resolution of conflicting accepted authority, or indispensable external human input.
- Batch related questions. Keep completing independent safe work before returning `NEEDS-INPUT`.

### Mandatory Plan Reading for Sub-Agents

**Every sub-agent you spawn MUST read the full plan file before starting any work.** This is non-negotiable.

When deploying a sub-agent via the Task tool, always include this instruction at the top of the prompt:

```
MANDATORY FIRST STEP: Read the full plan file at [PATH_TO_PLAN] before doing anything else. The plan contains critical architectural decisions, patterns, and conventions that you must follow. Do not skip sections -- read the entire document, then begin your assigned work.
```

**Why this matters:** The plan contains project-wide decisions (caching strategy, naming conventions, architectural patterns) that individual task descriptions may not repeat. Sub-agents that skip the plan will default to their own assumptions, causing drift from the intended architecture. Reading the full plan ensures every agent works from the same source of truth.

### Verification Before Completion

**Evidence before claims, always.** Before marking any task complete or claiming work is done:

1. Identify the verification command (build, test, lint, run)
2. Execute it NOW (not from memory, not from a previous run)
3. Read the complete output (exit code, errors, warnings)
4. Only claim completion when output confirms the claim

Red flag phrases that require immediate verification: "should pass now", "probably works", "seems to be working", "I believe it's fixed". If you catch yourself or a sub-agent using these, STOP and run the verification command.

See `.claude/skills/session-management/practices/verification.md` for the full protocol.

### Source UI/UX Context Injection (Repo-Port Sessions)

**When the plan contains a "Source UI/UX Reference" section**, every frontend agent prompt MUST include UX context. Detect the section's presence in the plan and prepend it automatically.

When deploying a frontend-specialist or any UI-building agent via the Task tool, add this block to the top of the prompt (after the mandatory plan reading instruction):

```
SOURCE UI/UX CONTEXT: This task ports from an existing repository. The plan contains a
"Source UI/UX Reference" section with layout patterns, interaction flows, and component
patterns from the source app.

CRITICAL INSTRUCTIONS:
1. After reading the full plan, pay special attention to the "Source UI/UX Reference" section
2. Read the source component files listed in "Source Files to Read" BEFORE writing any code
3. Match the source app's layout and interaction patterns -- not default DataTable/Sheet/Drawer patterns
4. If the source uses a two-panel split, build a two-panel split. If it uses tabbed cards, build tabbed cards.
5. The goal is to match or exceed the source app's UX quality, not just make it functional
```

**Why:** Without explicit injection, frontend agents default to their standard patterns (DataTable for lists, Sheet for details, basic grids). The source app almost always has more sophisticated UX designed for specific user workflows. The agents are capable -- they just need the context.

## Report

- Present the `## Report` section of the plan with actual results filled in.
