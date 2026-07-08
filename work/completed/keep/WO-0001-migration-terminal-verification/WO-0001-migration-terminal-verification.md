---
type: Work Order
title: Verify Spine v2 migration is terminal
status: CLOSED
work_order_id: WO-0001
wave: W1-audit
model_tier: mid
risk: low
disposition: [PKL_UPDATED, RESULT_SUMMARY_KEPT]
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-07
---

# Work Order: Verify Spine v2 migration is terminal

## Goal

Convert "the migration is complete" from claim to evidence: confirm no flow remains `legacy_truth`/`shadow_evented`, and inventory residual migration scaffolding.

## Context packet

Read only these first:

- `CLAUDE.md`
- `pkl/process/migration-history.md`
- `docs/MIGRATION_MATRIX.md`
- `docs/adr/ADR-004-event-log-truth-migration.md`

## Allowed paths

```yaml
allowed_paths:
  - "**"            # read-only everywhere
write_allowed:
  - work/active/WO-0001*/**
  - pkl/process/migration-history.md   # update last_verified + verified facts only
```

## Forbidden paths

```yaml
forbidden_paths:
  - "src/**"        # no source edits
  - "tests/**"      # no test edits
  - "docs/adr/**"   # findings only; ADR edits are a separate reviewed order
```

## Required behavior

- [ ] Enumerate every flow in `docs/MIGRATION_MATRIX.md` with its current state, verified against code (rg for `legacy_truth|shadow_evented|dual_write|parity` markers, feature flags, config).
- [ ] Inventory residual migration scaffolding: dual-store parity verifier status, shadow projections, compat read models, dead migration flags.
- [ ] Classify each residue: KEEP (permanent, e.g. parity verifier as regression tooling) | RETIRE-CANDIDATE (needs its own work order) | ALREADY-DEAD.
- [ ] Verdict: TERMINAL / NOT-TERMINAL with pasted evidence per flow.

## Required tests

- [ ] None to write (read-only). Run existing full suite once as baseline evidence: pasted summary.

## Required commands

```bash
pytest -q            # or repo's canonical test command — confirm in repo, paste output
rg -n "legacy_truth|shadow_evented|dual_write" --stats
```

## Acceptance criteria

- [ ] Every matrix flow has a code-verified state with evidence.
- [ ] Residue inventory complete with classifications.
- [ ] `pkl/process/migration-history.md` updated: claim → verified fact (or NOT-TERMINAL findings recorded).
- [ ] No source/test/ADR files modified.
- [ ] Fable DONE block with evidence.

## Model-tier rationale

Mid: mostly mechanical grep/read work, but matrix-to-code judgment needs competence.

## Notes

Exact test command unknown to the order author — implementer confirms from repo config and pastes it into the gate. If NOT-TERMINAL, stop after reporting; remediation is a new planned order, not scope creep here.

## Completion disposition

- [x] PKL_UPDATED — pkl/process/migration-history.md refreshed with the verified NOT-TERMINAL finding
- [x] RESULT_SUMMARY_KEPT — findings.md kept in work/completed/keep/
- [ ] ARCHIVED

Verdict: NOT-TERMINAL (narrow). Closed 2026-07-08 at commit 4eccaac; ledger appended. Evidence: ./findings.md.
