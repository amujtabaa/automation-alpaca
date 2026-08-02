---
type: Project Rule
title: Project Goals and Current Posture
status: active
authority: high
owner: Ameen
last_verified: 2026-08-02
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
evidence, not the reset foundation. M0 and pure M1A `WO-0145` are closed. Pure M1B `WO-0146` owns
venue effects, one-to-many concrete acceptances, immutable closure, ambiguity, and ADR-012 recovery
semantics; it is filed as a proposed `CLOSED` closeout whose effective lifecycle remains `REVIEW`
until its immutable exact SHA passes unchanged Python 3.11/3.12 CI. RESET-WO-03 and later slices
remain inactive.

## Rules / facts

- Beta target: usable, feature-rich, **paper-only** trading platform. Live trading remains disabled by config.
- Alpaca Paper, one account, a small US-equity symbol set, and manual acquisition/protection
  approval define reset beta. Signal Seat is disabled and unmounted.
- Python 3.11 and 3.12 are supported, Python 3.12 is the development default, and production code
  may not require 3.12-only syntax.
- Legacy migration/event-log/dual-store behavior remains read-only evidence; reset live decisions
  use transactional current state under ADR-020.
- The permanent safety core lives verbatim in `CLAUDE.md` and is never overridden by tooling or convenience defaults.
- Reset implementation advances only through independently reviewed work orders explicitly activated
  after their predecessor gates. `WO-0145` is `CLOSED`; `WO-0146` is a non-activating closeout
  candidate with effective lifecycle `REVIEW`; no reset implementation work order is active.
  RESET-WO-03 inherits no implementation authority until WO-0146's immutable final closeout SHA
  passes unchanged Python 3.11/3.12 CI and a separate activation commit makes it canonical.

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
- 2026-07-31: After M0 acceptance and exact-head Python 3.11/3.12 CI, Ameen's explicit implementation
  authority activated only the pure, credential-free first reset slice as `WO-0145`.
- 2026-08-01: Closed `WO-0145` after its focused, R2, full-coverage, implementation-checkpoint
  dual-version CI, and independent kernel/test review gates. No reset implementation work order is
  active; all later slices remain inactive pending separate explicit human authorization.
- 2026-08-01: After exact closeout `dfb8ed3` passed independent review and unchanged Python
  3.11/3.12 CI, Ameen authorized options 1–4. Activated only RESET-WO-02 as `WO-0146`, a pure
  I/O-free venue-ownership/recovery kernel; produced a read-only retirement inventory whose
  deletion actions remain gated by complete M1 review, non-squashed merge, and exact-master CI.
- 2026-08-02: Filed the `WO-0146` pure venue-ownership/recovery closeout candidate after 521 pure tests,
  61 R2 cases, a 5,109-case repository run at `93.00594652069468%` combined coverage, ten
  failure-capability mutation groups, and reviewer-owned `REV-0048` addendum-02 `ACCEPT` with no
  unresolved P0/P1. Its effective lifecycle remains `REVIEW` and the candidate is non-activating
  until its unchanged exact SHA passes Python 3.11/3.12 CI; RESET-WO-03 and every later slice remain
  inactive.
