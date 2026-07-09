# Codex Handoff — Independent Phase 0 Review

> **Superseded (2026-07-09):** this Phase-0 handoff is historical. Cross-model
> review now runs through **review packets** — see
> `.ai-os/core/15_CROSS_MODEL_REVIEW.md` and `work/review/REV-*/`. The output path
> below (`docs/review/CODEX_PHASE0_REVIEW.md`) was never created; reviewer output
> now goes into a packet's `result.md`, which is tracked and checkable
> (`check_review_packet.py`). Kept for provenance.

You are an independent review seat. Do not implement changes unless explicitly instructed after review.

## Review inputs

Read:

1. root `CLAUDE.md`
2. `docs/00_START_HERE_SPINE_UPGRADE.md`
3. `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md`
4. `docs/SPINE_V2_ACCEPTED_DECISIONS_ADDENDUM.md`
5. `docs/MIGRATION_MATRIX.md`
6. `docs/REARCHITECTURE_ROADMAP.md`
7. `docs/adr/ADR-001-overfill-quarantine.md`
8. `docs/adr/ADR-002-timeout-quarantine.md`
9. `docs/adr/ADR-003-manual-flatten-halted-reducing.md`
10. `docs/adr/ADR-004-event-log-truth-migration.md`
11. `docs/adr/ADR-005-api-facade-boundaries.md`
12. `docs/SPINE_PHASE0_INVENTORY.md`
13. `docs/SPINE_PHASE0_MIGRATION_PLAN.md`

## Task

Review Claude Code's Phase 0 output for:

- missing inventory areas;
- accidental production behavior changes;
- incomplete stale-artifact cleanup;
- false claims of test coverage;
- boundary violations that were missed;
- ADR contradictions;
- risks in proposed Phase 1 scope.

## Output

Produce `docs/review/CODEX_PHASE0_REVIEW.md` with:

1. Findings by severity.
2. Evidence with file paths.
3. Whether Phase 1 may begin.
4. Required fixes before Phase 1, if any.
5. Suggested Phase 1 scope reduction if the plan is too broad.

Do not begin implementation.
