---
type: Module Knowledge
title: Spine v2 Migration — History and Retired Process
status: active
authority: medium
owner: Ameen
last_verified: 2026-07-07
tags: [migration, history, retired-process]
source_refs: [docs/MIGRATION_MATRIX.md, docs/REARCHITECTURE_ROADMAP.md, docs/adr/ADR-004-event-log-truth-migration.md]
supersedes: []
superseded_by: null
---

# Spine v2 Migration — History and Retired Process

## Summary

The salvage → re-architect → phased-migration program that produced Spine v2 is complete and integrated (per project owner, 2026-07). This page records what the migration-era process was and what its completion means, so the always-on contract no longer carries it.

## Rules / facts

- Retired from the always-on contract (formerly CLAUDE.md §0/§6 and read-order §1):
  - Phase discipline (one branch/one phase, Phase N review gates, phase start documents).
  - `legacy_truth` / `shadow_evented` / `event_truth` flow routing via `docs/MIGRATION_MATRIX.md`.
  - Mandatory characterization tests before behavior change (superseded by the standing testing model — see `pkl/architecture/testing-model.md`).
  - The mandated 7-document read order for spine work; work orders now name their own context packets.
- **Not yet independently verified:** that every flow is `event_truth` and no `shadow_evented` / dual-write scaffolding remains. WO-0001 verifies this with evidence; until then, treat "migration complete" as a high-confidence claim, not a fact.
- Migration docs (`MIGRATION_MATRIX.md`, `REARCHITECTURE_ROADMAP.md`, phase prompts) remain in `docs/` as historical evidence; stale `IMPLEMENTATION_PROMPT_*` files go to `docs/archive/legacy_implementation_prompts/` per the stale-artifact guide. Never delete decision logs, ADRs, tests, or source without explicit human confirmation.
- What the migration permanently left behind: event-log-as-truth (ADR-004), the layer seams and single-writer rule, dual-store parity testing, and the quarantine decisions (ADR-001/002/003).

## Rationale

Carrying dead process in the always-on file is how important rules get skimmed past. History belongs here; only live rules belong in the shim.

## Applies to

- Documentation handling; interpretation of phase-named tests and legacy docs.

## Related pages

- `pkl/project/goals.md`
- `work/queue/WO-0001` (migration-terminal verification)

## Change log

- 2026-07-07: Created; migration-era process formally retired from CLAUDE.md.
