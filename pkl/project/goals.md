---
type: Project Rule
title: Project Goals and Current Posture
status: active
authority: high
owner: Ameen
last_verified: 2026-07-07
tags: [goals, posture, roadmap]
source_refs: [docs/00_START_HERE_SPINE_UPGRADE.md, docs/REARCHITECTURE_ROADMAP.md]
supersedes: []
superseded_by: null
---

# Project Goals and Current Posture

## Summary

Alpaca Clean-Sheet CAPI Option 2.5: a browser-operated, paper-first Alpaca Paper Trading platform built on the Spine v2 execution architecture for capital protection and exit management. The Spine v2 re-architecture and phased migration are **complete and integrated**. Current phase: cleanup → full-repo audit (ADR reconciliation) → project-state determination → roadmap to a usable, feature-rich beta.

## Rules / facts

- Beta target: usable, feature-rich, **paper-only** trading platform. Live trading remains disabled by config.
- Migration-era process (phase discipline, legacy_truth/shadow_evented routing, characterization-before-change mandates) is retired; see `pkl/process/migration-history.md`.
- The permanent safety core lives verbatim in `CLAUDE.md` and is never overridden by tooling or convenience defaults.
- Roadmap work begins only after the ADR audit wave (WO-0001…WO-0006) establishes verified project state.

## Rationale

Roadmapping against an unverified codebase state repeats the failure mode Fable exists to prevent: building on unpasted claims. The audit wave converts "migration is done" from assertion to evidence.

## Applies to

- All planning, roadmap, and feature work.

## Related pages

- `pkl/safety/invariants-rationale.md`
- `pkl/architecture/architecture-map.md`
- `pkl/process/migration-history.md`

## Change log

- 2026-07-07: Created from CLAUDE.md decomposition.
