# Session Type: Development

Use this session type for building new features, implementing plans, and standard development work.

---

## When to Use

- Building new features or functionality
- Implementing a planned design
- Adding new components, APIs, or integrations
- Standard coding work with clear requirements

---

## Session File Header

```markdown
**Session Type**: Development
**Status**: `PENDING`
```

---

## Workflow

**For complex work (5+ files, multi-phase, architectural):** /team-plan handles the full workflow -- session type detection, plan creation, team orchestration, and execution via /build. No manual session management needed.

**For moderate work (2-5 files, clear scope):** Create tasks manually using this template:

```markdown
- [ ] Task N: [Component Name]
  - Files: `exact/path/to/file.ts`
  - Action: [Create/Modify/Delete]
  - Details: [Specific implementation notes]
  - Done when: [Verification criteria]
```

| Requirement  | Description                                |
| ------------ | ------------------------------------------ |
| Task size    | 1-4 hours max (atomic)                     |
| Specificity  | Exact file paths, not abstractions         |
| Context      | Assume reader knows nothing about codebase |
| Verification | Each task has clear "done" criteria        |

### Checkpoint Cadence

Execute in batches of 3 tasks maximum. After each batch:

1. Do all changes compile/run?
2. Are tests passing?
3. Is the session file updated?

### Blocker triage

On a blocker, do not immediately return to the user. Reproduce or inspect it, classify attribution,
check the nearest working analogue, try safe in-scope alternatives, and re-gate a root correction.
Continue other independent work. Ask one batched question only when the blocker requires new
authority, an unapproved human-gated/destructive action, resolution of conflicting accepted
authority, or indispensable external human input.

---

## Quality Checklist

Before marking development session complete:

- [ ] All tasks have `[x]` checkboxes
- [ ] Code compiles without errors
- [ ] Tests pass (if applicable)
- [ ] Session file reflects actual state
- [ ] Verification evidence provided
