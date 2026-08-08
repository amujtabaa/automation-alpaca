# PKL Index — Automation Alpaca architecture reset

Curated project truth. Normative safety text lives in `CLAUDE.md`; rationale and facts live here.

## Pages

- `project/goals.md` — reset goal, frozen legacy posture, and bounded beta scope
- `architecture/architecture-map.md` — accepted reset target plus frozen Spine v2 evidence boundary
- `architecture/testing-model.md` — determinism, legacy regression gates, pure-model/SQLite reset gate
- `safety/invariants-rationale.md` — the *why* behind the always-on safety core
- `process/migration-history.md` — retired migration-era process; what remains
- `drift/recurring-agent-mistakes.md` — create on first observed drift (template: `.ai-os/templates/pkl-page.md`)
- `architecture/architecture-defaults.md` — OS-seeded architecture defaults (draft, low authority; refine during the audit wave)
- `log.md` — PKL running log (OS/PKL change history)

## Conventions

- Every page carries `last_verified`; reset-target facts trace to accepted ADR-020 through ADR-022,
  while as-built claims remain explicitly labeled legacy evidence until implementation lands.
- On any conflict with `CLAUDE.md`, `CLAUDE.md` wins and the page is corrected.
