# Project Knowledge Layer

## Definition

The **Project Knowledge Layer (PKL)** is the repository’s curated operational memory. It is OKF-compatible markdown with YAML frontmatter plus a small set of project-governance fields.

PKL is not a dumping ground for chat transcripts. It is where stable, reviewed project truth lives.

## PKL authority hierarchy

```text
1. Code, tests, contracts, migrations
2. Accepted ADRs
3. Active work orders
4. PKL synthesis/module pages
5. Raw source notes
6. Unreviewed AI summaries
```

If PKL conflicts with tests or accepted ADRs, tests and ADRs win.

## Recommended structure

```text
pkl/
  index.md
  log.md
  project/
    overview.md
    goals.md
    non-goals.md
    glossary.md
  architecture/
    architecture-map.md
    architecture-defaults.md
    module-boundaries.md
    testing-model.md
    security-model.md
  modules/
    auth.md
    reports.md
    ai-workflows.md
  decisions/
    adr-0001-default-architecture.md
  drift/
    drift-log.md
    recurring-agent-mistakes.md
  sources/
    raw/
```

## Work orders are not PKL

Work orders live only under `work/` (see `03_IN_USE_STRUCTURE.md` and `12_WORK_ORDER_RETENTION_AND_DISPOSITION.md`). Do not create `pkl/work-orders/`; disposable execution tickets must not live inside durable memory.

## Required frontmatter

```yaml
type: Module Knowledge
title: Reports Module
status: active
authority: medium
owner: architect
last_verified: 2026-07-07
tags: [reports, module]
source_refs: []
supersedes: []
superseded_by: null
```

## Update triggers

Update PKL when:

- An ADR is accepted.
- A module boundary changes.
- A recurring agent mistake is discovered.
- A work order completes and changes project reality.
- A bug fix reveals a durable rule.
- A source is ingested.

Do not update PKL for every tiny code edit.

## PKL lint checks

- Every page has required frontmatter.
- Every page is linked from `index.md` or another page.
- No page marked `active` is contradicted by a newer ADR.
- `log.md` contains entries for accepted architecture changes.
- `source_refs` exists for external claims.
- `last_verified` is not stale for high-authority pages.
