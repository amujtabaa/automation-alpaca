# Context, Prompt, Loop, Goal, and Harness Plan

## Why this matters

This project has high agent-drift risk: long history, legacy prompts, mature existing code, new target architecture, and safety-critical execution behavior. Prompting alone is not enough. The workflow must use context, loop, goal, and harness engineering as guardrails.

## Context engineering

Keep active context small and canonical:

1. root `CLAUDE.md`;
2. Spine v2 spec;
3. accepted ADRs;
4. migration matrix;
5. phase roadmap;
6. current code/tests for the touched flow.

Legacy implementation prompts are historical unless explicitly reactivated.

## Prompt engineering

Each Claude Code session should use a bounded phase prompt. Avoid broad prompts like “upgrade the repo.” A good prompt says:

- phase objective;
- files to read;
- allowed changes;
- forbidden changes;
- tests to run;
- stop condition.

## `/goal` engineering

Use a narrow goal per session, for example:

```text
/goal Phase 0 only: install Spine v2 docs, archive stale prompts, fix stale links, run pytest collection, and stop. Do not change production behavior.
```

## Loop engineering

Use the same loop every time:

1. read canonical docs;
2. inventory current code;
3. characterize current behavior with tests;
4. implement the smallest migration seam;
5. run memory + SQLite relevant tests;
6. update docs/migration matrix;
7. stop for independent review.

## Harness engineering

Harnesses should catch drift mechanically:

- import-boundary checks;
- pytest collection;
- selected unit/property tests;
- replay/parity verifier once implemented;
- stale-link checks;
- `CLAUDE.md` import resolution checks.

Do not treat a harness smoke pass as proof of production correctness. It is an early warning layer.
