---
type: Work Order
title: ADR synthesis + project-state report
status: draft   # becomes ready only after WO-0001..0005 complete with in-process validation
work_order_id: WO-0006
wave: W1-audit
model_tier: strong
risk: medium
disposition: []
owner: Ameen (planning) / Claude (implementer) / independent seat (discretionary, per CLAUDE.md Review policy)
created: 2026-07-07
---

# Work Order: ADR synthesis + project-state report

## Goal

Merge the reviewed findings of WO-0001…WO-0005 into: (a) approved ADR amendments/creations, (b) a verified project-state report that becomes the input to beta roadmapping.

## Context packet

Read only these first:

- `CLAUDE.md`
- Findings reports from `work/review/WO-0001…WO-0005` with in-process validation annotations
- `pkl/project/goals.md`
- Existing `docs/adr/` set

## Allowed paths

```yaml
allowed_paths:
  - "**"    # read-only everywhere
write_allowed:
  - docs/adr/**                       # ONLY human-approved amendments/creations
  - pkl/**                            # last_verified refresh, verified facts
  - work/active/WO-0006*/**           # project-state report
```

## Forbidden paths

```yaml
forbidden_paths:
  - "src/**"
  - "tests/**"
```

## Required behavior

- [ ] Deduplicate and reconcile cross-layer findings (a drift seen from both engine and store sides is one finding).
- [ ] For each DRIFTED verdict: propose resolve-toward-ADR (code fix order) or resolve-toward-code (ADR amendment) with rationale; **human decides each**; drift on safety surfaces is flagged NEEDS-INPUT, never auto-resolved.
- [ ] Draft candidate new ADRs from the audit lists using the repo ADR format; mark proposed until accepted.
- [ ] Refresh `last_verified` on PKL pages the audit confirmed; correct any PKL facts the audit contradicted.
- [ ] Produce the project-state report: verified architecture state, open drift items (with owner orders), test-suite health baseline, retired-scaffolding inventory, and a "known-unknowns" list for roadmap planning.
- [ ] Tag every finding/amendment touching a human-gated safety surface, and every ADR amendment, into the independent-review queue per CLAUDE.md Review policy.

## Required tests

- [ ] None to write. Paste the fresh full-suite run from the report baseline.

## Required commands

```bash
pytest -q   # confirm canonical command; paste output
```

## Acceptance criteria

- [ ] Every WO-0001..0005 finding dispositioned: ADR amended | new ADR proposed | code-fix order drafted | rejected-with-reason.
- [ ] Zero ADR edits without explicit human approval recorded in this order's notes.
- [ ] Project-state report complete and stored; PKL refreshed.
- [ ] Safety-surface findings and ADR amendments queued for independent review per CLAUDE.md Review policy (quality-engineer validation does not satisfy that queue).
- [ ] Fable DONE block with evidence.

## Model-tier rationale

Strong: cross-cutting judgment, ADR drafting, and roadmap-shaping synthesis — the one order in the wave where reasoning quality dominates cost.

## Notes

Gate: start after WO-0001…0005 complete with in-process validation (Fable evidence + quality-engineer pass); independent review of safety-surface findings and ADR amendments is queued per CLAUDE.md Review policy rather than blocking this order. If WO-0001 returned NOT-TERMINAL, remediation orders precede this synthesis. Code-fix orders drafted here go to `work/queue/` as W2; they are not executed within this order (Iron Law 4).

## Ledger

On close, append disposition entries for WO-0001..0006 to `work/ledger.jsonl` per `.ai-os/mcp/schemas/ledger_entry.schema.json` vocabulary in `rules/ai-os-rules.yaml`; run `python .ai-os/scripts/check_ledger.py` and `check_work_order_disposition.py` and paste output as evidence.

## Completion disposition

- [ ] ADR_CREATED
- [ ] PKL_UPDATED
- [ ] RESULT_SUMMARY_KEPT
