---
type: Project Rule
title: Project Goals and Current Posture
status: active
authority: high
owner: Ameen
last_verified: 2026-07-31
tags: [goals, posture, roadmap]
source_refs: [docs/adr/ADR-020-current-state-execution-kernel.md, docs/adr/ADR-021-position-protection-liquidity-execution.md, docs/adr/ADR-022-reset-beta-scope-cutover-governance.md, docs/adr/ARCH-RESET-2026-07-RATIFICATION.md]
supersedes: []
superseded_by: null
---

# Project Goals and Current Posture

## Summary

Build a narrow, reliable, browser-operated protection/acquisition engine for Alpaca Paper. The
accepted reset target is a modular monolith with one sequenced writer, one pure transition kernel,
one SQLite production store, transactional current state/outbox, and broker-neutral protection and
side-symmetric liquidity execution. The integrated Spine v2 application and R6 branch are frozen
evidence, not the reset foundation. Current phase: M0 documentation landing and independent review;
implementation is not activated.

## Rules / facts

- Beta target: usable, feature-rich, **paper-only** trading platform. Live trading remains disabled by config.
- Alpaca Paper, one account, a small US-equity symbol set, and manual acquisition/protection
  approval define reset beta. Signal Seat is disabled and unmounted.
- Python 3.11 and 3.12 are supported, Python 3.12 is the development default, and production code
  may not require 3.12-only syntax.
- Legacy migration/event-log/dual-store behavior remains read-only evidence; reset live decisions
  use transactional current state under ADR-020.
- The permanent safety core lives verbatim in `CLAUDE.md` and is never overridden by tooling or convenience defaults.
- No reset implementation work begins until the M0 landing is independently reviewed and Ameen
  explicitly activates the next work order.

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
- 2026-07-31: M0 replaced the completed-Spine-v2 posture with the ratified reset target and retained
  the existing application as frozen evidence. No implementation was activated.
