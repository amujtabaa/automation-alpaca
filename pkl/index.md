# PKL Index — Alpaca Spine v2

Curated project truth. Normative safety text lives in `CLAUDE.md`; rationale and facts live here.

## Pages

- `project/goals.md` — goals, current posture (cleanup → audit → beta roadmap)
- `architecture/architecture-map.md` — layers, seams, single-writer rule, stack pins
- `architecture/testing-model.md` — determinism, dual-store parity, CI gate
- `safety/invariants-rationale.md` — the *why* behind the always-on safety core
- `process/migration-history.md` — retired migration-era process; what remains
- `drift/recurring-agent-mistakes.md` — create on first observed drift (template: `.ai-os/templates/pkl-page.md`)
- `architecture/architecture-defaults.md` — OS-seeded architecture defaults (draft, low authority; refine during the audit wave)
- `log.md` — PKL running log (OS/PKL change history)

## Conventions

- Every page carries `last_verified`; the ADR audit wave (WO-0001…WO-0006) refreshes these against code.
- On any conflict with `CLAUDE.md`, `CLAUDE.md` wins and the page is corrected.
