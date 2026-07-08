---
type: Work Order
title: Facade + API layer ADR audit
status: ready
work_order_id: WO-0004
wave: W1-audit
model_tier: mid
risk: low
disposition: []
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-07
---

# Work Order: Facade + API layer ADR audit

## Goal

Audit facade/ and api/ (FastAPI routes behind typed command/query facades) against its governing ADRs and invariants; report CONFIRMED / DRIFTED / SUPERSEDED per ADR clause, plus candidate new ADRs, with code evidence.

## Context packet

Read only these first:

- `CLAUDE.md`
- `pkl/architecture/architecture-map.md`
- Governing ADRs: ADR-005
- The layer's source and tests (src/facade/**, src/api/**, and their tests, read-only)

## Allowed paths

```yaml
allowed_paths:
  - "**"                       # read-only everywhere
write_allowed:
  - work/active/WO-0004*/**   # findings report only
```

## Forbidden paths

```yaml
forbidden_paths:
  - "app/**"                    # backend source (repo uses app/, not src/)
  - "cockpit/**"                # UI source (Streamlit)
  - "tests/**"
  - "docs/adr/**"    # findings only; ADR amendments are separate reviewed orders
```

## Required behavior

- [ ] Per governing ADR clause: verdict CONFIRMED (code matches, cite file:line) | DRIFTED (cite divergence) | SUPERSEDED (cite what replaced it).
- [ ] Audit focus areas: All routes behind typed facades, DTO and domain-error mapping, auth on mutating endpoints, no engine/store internals leaking through api.
- [ ] List undocumented significant decisions found in code -> candidate new ADRs, each with evidence and a one-line proposed decision.
- [ ] Check boundary compliance for this layer (import seams per architecture map); note import-linter gaps.
- [ ] Note stale docs referencing pre-migration behavior of this layer.

## Required tests

- [ ] None to write (read-only). Run this layer's test subset once; paste summary as baseline evidence.

## Required commands

```bash
pytest -q <layer test path>   # confirm exact path/command from repo, paste output
# plus rg/import inspection commands as needed (paste decisive output)
```

## Acceptance criteria

- [ ] Every governing ADR clause has a verdict with file:line evidence.
- [ ] Candidate-ADR list complete (explicitly state if empty).
- [ ] Findings report written under work/active/WO-0004*/; no source/test/ADR edits.
- [ ] Fable DONE block with evidence.

## Model-tier rationale

Mid: architectural-drift judgment over a bounded read-only scope. Escalate to strong only if findings are ambiguous.

## Notes

Findings are claims until the independent review seat checks them (feeds WO-0006). Do not fix drift found here — report it (Iron Law 4).

## Completion disposition

- [ ] RESULT_SUMMARY_KEPT
- [ ] ARCHIVED
