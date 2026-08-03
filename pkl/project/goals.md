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
evidence, not the reset foundation. M0 and pure M1A/M1B/M1C `WO-0145` through `WO-0147` are
effective `CLOSED` after independent acceptance and exact-head Python 3.11/3.12 CI. Their immutable
execution-truth, venue/recovery, and deny-by-default execution-authority centers remain I/O-free
and unwired. Pure M1D `WO-0148` is active for position protection and hybrid trailing only.
`WO-0149`, M2, and every runtime/persistence/cutover slice remain inactive.

## Rules / facts

- Beta target: usable, feature-rich, **paper-only** trading platform. Live trading remains disabled by config.
- Alpaca Paper, one account, a small US-equity symbol set, and manual acquisition/protection
  approval define reset beta. Signal Seat is disabled and unmounted.
- Python 3.11 and 3.12 are supported, Python 3.12 is the development default, and production code
  may not require 3.12-only syntax.
- Legacy migration/event-log/dual-store behavior remains read-only evidence; reset live decisions
  use transactional current state under ADR-020.
- The permanent safety core lives verbatim in `CLAUDE.md` and is never overridden by tooling or convenience defaults.
- Reset implementation advances only through independently reviewed work orders explicitly
  activated after their predecessor gates. `WO-0145` through `WO-0147` are effective `CLOSED`.
  Only pure, unwired `WO-0148` is active; it cannot perform broker effects, authenticate an
  operational fence, persist state, or activate `WO-0149`/M2.

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
- 2026-08-02: The first `WO-0146` closeout candidate failed exact-head Python 3.11 CI in a recursive
  test-oracle rendering path. Reviewer-owned addendum-03 then blocked the first repair, and two
  independent audits blocked an incomplete successor on auxiliary retained maps. Final test-only
  freeze `5a89841` uses a complete iterative graph projector, passed 536 pure cases, 22 stateful
  cases at recursion limit 700, 61 R2 cases, and a 5,124-case repository run at
  `93.00594652069468%` combined coverage. Reviewer-owned addendum-04 accepted exact evidence target
  `982d213` with no unresolved P0/P1. The repaired candidate remains effectively `REVIEW` and
  non-activating until its immutable exact SHA passes Python 3.11/3.12 CI; RESET-WO-03 and every
  later slice remain inactive.
- 2026-08-02: Repaired immutable closeout `7d1c9e5` passed GitHub Actions run #685 on Python 3.11
  and 3.12, satisfying WO-0146's final external gate. Activated only `WO-0147`, the pure execution-
  authority/manual-control/request-budget slice. It cannot authenticate the later M4/cutover
  supervisor fence or perform broker, database, persistence, runtime, merge, deletion, or cleanup
  work. M2 may persist and hydrate the deny-only fence but cannot promote it without those later
  adapter/cutover gates.
- 2026-08-02: Filed the repaired WO-0147 closeout after the 710-case pure kernel, 61-case R2 oracle,
  5,298-test repository gate at `93.02945093976616%` combined coverage, and REV-0049 result
  addendum 02 `ACCEPT` closed every preserved P0/P1. The closeout is effective `REVIEW` until its
  immutable SHA passes unchanged Python 3.11/3.12 CI. WO-0148 and all later slices remain inactive;
  no runtime, persistence, broker, credential, database cutover, merge, deletion, or cleanup
  authority was added.
- 2026-08-02: Immutable WO-0147 closeout `3e39ee6` passed GitHub Actions run #687 on Python 3.11
  job `91626251701` and Python 3.12 job `91626251758`. Closed its external gate and separately
  activated only pure `WO-0148` for exact formula-driven position protection, distinct market-
  occurrence evidence, hybrid trailing, BUY-resolution wait policy, flat finalization, and late-
  fill re-protection. `WO-0149`, M2, broker, credential, persistence, runtime, merge, deletion,
  and cleanup remain inactive.
