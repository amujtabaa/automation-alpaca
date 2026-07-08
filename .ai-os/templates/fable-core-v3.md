# Fable Core v3 — Compact Model-Agnostic Protocol

Use this for engineering tasks when no platform-specific skill is available.

## Iron Laws

1. No production code before a failing test, unless a declared exception applies.
2. No completion claim without fresh evidence.
3. No fix without diagnosed root cause.
4. Touch only what the task requires.
5. Surface assumptions before building.

## Required task header

`[FABLE • FULL|LITE • verification: DIRECT|DELEGATED • task: <name>]`

## FULL gate

```yaml
fable_gate:
  goal: ""
  assumptions: []
  approach: ""
  out_of_scope: []
  done_when: []
  blast_radius: "none"
```

## Evidence

```yaml
evidence:
  command: ""
  result: PASS|FAIL|NOT_RUN
  decisive_output: ""
```

## Bug fix block

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

## Done block

```yaml
fable_done:
  task: ""
  done_when_results: []
  scope_check:
    allowed_paths_respected: true|false
    drive_by_edits: true|false
  evidence: []
  status: VERIFIED|UNVERIFIED|BLOCKED|NEEDS-INPUT
```

If you cannot follow a rule, declare the deviation. Silent deviation is failure.
