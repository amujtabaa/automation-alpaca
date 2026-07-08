# Fable v3 — Model-Agnostic Agent Execution Protocol

## Purpose

Fable is the agent execution discipline layer. It makes skipped engineering practices visible and reviewable.

## Model-agnostic terminology

| Old / tool-specific | New neutral term |
|---|---|
| Claude | agent |
| Claude Code | coding runtime |
| CLAUDE.md | instruction file |
| Skill | capability bundle |
| /goal | evaluator loop |
| Hook | lifecycle enforcement script |
| Subagent | delegated agent |

## Five Iron Laws

1. No production code before a failing test, unless an explicit exception is declared.
2. No completion claim without fresh evidence.
3. No fix without diagnosed root cause.
4. Touch only what the task requires.
5. Surface assumptions before building.

## Required blocks

### Block grammar dialects

The YAML blocks below are the **canonical grammar** for machine checking (`scripts/check_fable_done.py` parses them). Platform skill editions may emit an equivalent **prose dialect** — `[GATE]`, `[FIX]`, `[DONE] ... STATUS: VERIFIED|UNVERIFIED|BLOCKED|NEEDS-INPUT` — which checkers must also accept. The dialects are equivalent; do not mix them within one task.

### Task start

```text
[FABLE • FULL|LITE • verification: DIRECT|DELEGATED • task: <name>]
```

### Gate

```yaml
fable_gate:
  goal: ""
  assumptions:
    - claim: ""
      status: VERIFIED|UNVERIFIED
      evidence: ""
  approach: ""
  alternatives_considered: []
  out_of_scope: []
  done_when:
    - behavior: ""
      test: ""
      command: ""
  blast_radius: "none|describe"
  rollback: ""
```

### Evidence

```yaml
evidence:
  phase: RED|GREEN|REFACTOR|FULL_SUITE|MANUAL_QA
  command: ""
  result: PASS|FAIL|BLOCKED|NOT_RUN
  decisive_output: ""
```

### Fix

```yaml
fable_fix:
  symptom: ""
  root_cause: ""
  evidence: ""
  fix: ""
  regression_test: ""
  red_green_verified: true|false
  attempt: 1
```

### Done

```yaml
fable_done:
  task: ""
  done_when_results:
    - item: ""
      status: MET|NOT_MET|BLOCKED
      evidence: ""
  scope_check:
    allowed_paths_respected: true|false
    drive_by_edits: true|false
  debt_check: "clean|items listed"
  deferred: []
  status: VERIFIED|UNVERIFIED|BLOCKED|NEEDS-INPUT
```

## Exceptions

TDD exceptions require explicit declaration.

Allowed with declaration:

- throwaway spike
- generated code
- pure config
- mechanical rename
- docs-only change

Never exempt without strong review:

- auth/authz
- input validation
- data deletion
- money/trading/financial execution
- secrets
- migrations
- file upload/path handling

## Integration rule

Fable does not store project truth. It must read project truth from code, tests, ADRs, PKL, and work orders.
