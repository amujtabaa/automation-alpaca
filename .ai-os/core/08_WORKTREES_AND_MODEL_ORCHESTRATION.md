# Worktrees and Model-Tier Orchestration

## Rule

One worktree = one branch = one work order = one primary implementation agent.

## Good parallelization

```text
wt-auth-login      -> feature/auth-login
wt-report-create   -> feature/report-create
wt-audit-adapter   -> feature/audit-adapter
wt-review-wave-1   -> review/wave-1
```

## Bad parallelization

```text
Agent A modifies shared config
Agent B modifies shared config
Agent C modifies shared config
Agent D modifies tests after implementation
```

## Model assignment matrix

| Task | Model tier | Reason |
|---|---|---|
| Mechanical rename | cheap | exact paths, low judgment |
| Fixture generation | cheap | bounded and testable |
| Simple endpoint from work order | mid | multi-file integration |
| New module boundary | strong | architecture judgment |
| Auth/authz change | strong | security-sensitive |
| Ambiguous bug | strong | diagnosis required |
| Final branch review | strong | subtle integration defects |
| PKL index/log update | cheap/mid | structured maintenance |
| PKL contradiction resolution | strong | authority judgment |

## Cost rule

The cheapest model is not always cheapest if it takes multiple repair turns. Choose model tier by:

```text
ambiguity + blast radius + number of files + need for diagnosis + required review judgment
```

## Dispatch format

Every delegated agent receives:

```text
- work order ID
- current branch/worktree
- exact allowed paths
- exact forbidden paths
- required PKL pages
- required tests
- acceptance criteria
- Fable mode
- model tier rationale
```

## Wave integration

After each wave:

1. Merge one branch at a time.
2. Run full suite.
3. Cold-read full diff.
4. Update PKL module pages and drift log.
5. Generate next wave from current reality.
