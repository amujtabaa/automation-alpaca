# Handoff Prompt

```text
Create a handoff for the next session.

Include:
1. Work order ID
2. Branch/worktree
3. Current status
4. Completed steps with evidence
5. Files changed
6. Tests added or run
7. Current blocker or exact next step
8. Open decisions
9. Deferred out-of-scope items
10. PKL pages that may need update

Do not claim completion unless DONE evidence exists.
```


## Hygiene check

Before handoff, identify:

- stale context that the next session should not trust
- completed work orders needing disposition
- raw prompts that can be deleted after distillation
- PKL pages that need updating or shortening
- ADRs that need to be created
- the smallest context packet the next session should read

Do not hand off broad conversation history when a smaller artifact list is available.
